# 04 — Automod Engine

Implements `scope.inScope: automod_engine` and every entry in `automatedModeration.filters` (`spam`, `raid`, `links`, `profanity`, `nsfw_image`, `phishing`, `mass_mention`, `caps_emoji`). Runs entirely inside the `bot` process (02-architecture.md's component split — sub-second latency against the live gateway cache, no round-trip to `api` on the hot path). Per-guild tunables live in the `AutomodFilterConfig` Prisma model (03-data-model.md); `spec.json` gives filter *names* only, so this file fixes the detection approach and default thresholds for each one, plus the two product decisions `automatedModeration.raidThreshold`/`escalationNotes` left blank.

Two entry points on `bot/src/automod/engine.ts`'s `AutomodEngine`:

- `evaluate(message: Message): Promise<void>` — called from the `messageCreate` handler, runs the seven message-scoped filters.
- `evaluateJoin(member: GuildMember): Promise<void>` — called from the `guildMemberAdd` handler, runs `raid` only.

Both resolve a `FilterContext` and hand any non-null `FilterResult` to `AutomodPipeline.handleTrigger()` (Automod-to-Action Pipeline, below). This refines 02-architecture.md's file listing (`bot/src/automod/filters/{spam,raid,links,profanity,nsfwImage,phishing,massMention,capsEmoji}.ts` — one file per filter, all implementing a common interface) by clarifying that `raid.ts` is driven by member-join events rather than message events, even though it lives alongside the message filters and shares their `Filter` interface:

```ts
// bot/src/automod/types.ts
type FilterContext = MessageFilterContext | JoinFilterContext;

interface MessageFilterContext {
  kind: 'message';
  message: Message;              // discord.js Message
  guildId: string;
  member: GuildMember;            // cached row, 03-data-model.md
  config: AutomodFilterConfig;    // this guild's row, Redis-cached (see Config Loading below)
}

interface JoinFilterContext {
  kind: 'join';
  member: GuildMember;
  guildId: string;
  config: AutomodFilterConfig;
}

interface FilterResult {
  filterId: 'spam' | 'raid' | 'links' | 'profanity' | 'nsfw_image' | 'phishing' | 'mass_mention' | 'caps_emoji';
  severity: 'low' | 'medium' | 'high' | 'critical';
  action: ActionType;              // KICK | SOFTBAN | BAN | TIMEOUT | WARN | PURGE | ROLE_STRIP | LOCKDOWN
  targetChannelId?: string;        // set for PURGE/LOCKDOWN-shaped results
  evidence: { messageContent?: string; attachmentUrls?: string[]; metadata?: Record<string, unknown> };
}

interface Filter {
  id: FilterResult['filterId'];
  evaluate(ctx: FilterContext): Promise<FilterResult | null>;
}
```

**Config loading:** `AutomodEngine` reads a guild's `AutomodFilterConfig` through a read-through Redis cache, key `automod:config:{guildId}`, TTL 60s, populated from `GET /internal/v1/guilds/:guildId/automod-config`. When a moderator edits config via `config_editor` (`PATCH /api/v1/guilds/:guildId/automod-config`, 08-web-dashboard.md), `api` publishes on Redis Pub/Sub channel `automod-config-updated:{guildId}`; `bot` subscribes at startup and evicts the matching cache key immediately on message, so edits take effect on the next message/join rather than waiting out the TTL.

**Evaluation order (message filters, short-circuit on first match):** one message produces at most one `FilterResult` — the first filter to fire wins, evaluated in severity order so the highest-harm category always gets first look:

| Order | `filterId` | Severity | Stateful? |
|---|---|---|---|
| 1 | `phishing` | critical | no |
| 2 | `nsfw_image` | high | no |
| 3 | `mass_mention` | high | yes (Redis) |
| 4 | `spam` | medium | yes (Redis) |
| 5 | `links` | medium | no |
| 6 | `caps_emoji` | low | no |
| 7 | `profanity` | low | no |

`raid` is evaluated separately via `evaluateJoin()` and is not part of this ordering.

## Filter Catalog & Detection Logic

Each subsection: inputs consumed, detection approach, and the exact `AutomodFilterConfig` column(s) that hold its configurable thresholds (concrete defaults seeded on guild install by `api/src/modules/guilds/guilds.service.ts`'s `provisionGuild()`, editable per-guild afterward via `config_editor`).

### spam

**Inputs:** `message.authorId`, `message.guildId`, message timestamp.
**Detection:** stateful sliding-window message-rate counter. On every message, `bot/src/automod/filters/spam.ts` runs, against Redis:
```
ZADD automod:spam:{guildId}:{userId} <nowMs> <messageId>
ZREMRANGEBYSCORE automod:spam:{guildId}:{userId} 0 (nowMs - windowSeconds*1000)
ZCARD automod:spam:{guildId}:{userId}
EXPIRE automod:spam:{guildId}:{userId} windowSeconds
```
If the resulting cardinality `>= spamConfig.maxMessages`, the filter fires.
**Config (`spamConfig`):** `{ maxMessages: number, windowSeconds: number, action: ActionType }`. Default: `{ maxMessages: 5, windowSeconds: 7, action: "TIMEOUT" }`.

### raid

**Inputs:** `guildMemberAdd` events (join timestamp, `member.discordUserId`) for the guild.
**Detection:** stateful sliding-window join-rate counter, same ZSET pattern as `spam` but guild-scoped, not user-scoped:
```
ZADD automod:raid:{guildId} <nowMs> <discordUserId>
ZREMRANGEBYSCORE automod:raid:{guildId} 0 (nowMs - windowSeconds*1000)
ZCARD automod:raid:{guildId}
```
Full threshold/escalation behavior is its own section below (raidThreshold/escalationNotes were blank in `spec.json`).
**Config (`raidConfig`):** `{ joinThreshold: number, windowSeconds: number, action: ActionType }`. Default: `{ joinThreshold: 10, windowSeconds: 60, action: "LOCKDOWN" }`.

### links

**Inputs:** `message.content`.
**Detection:** stateless. `bot/src/automod/filters/links.ts` extracts URLs with a regex, resolves each via `new URL(match)`, and checks `hostname` against `linksConfig.allowlist` (exact or subdomain match bypasses). Independently, if `linksConfig.blockInvites` is true, it regex-matches Discord invite patterns (`discord\.gg/\w+`, `discord\.com/invite/\w+`); a matched invite is resolved with `client.fetchInvite(code)` and blocked unless it resolves to the *current* guild (so moderators re-sharing their own server's invite are never blocked). No action override field exists on this config — the fixed default action below always applies.
**Config (`linksConfig`):** `{ allowlist: string[], blockInvites: boolean }`. Default: `{ allowlist: [], blockInvites: true }`. **Fixed action:** delete the offending message (bot-side `message.delete()`, not a `ModerationAction`) plus `WARN` (see Automod-to-Action Pipeline for why `links` has no configurable action).

### profanity

**Inputs:** `message.content`.
**Detection:** stateless wordlist match. `bot/src/automod/filters/profanity.ts` normalizes content (lowercase, strip leading/trailing punctuation, collapse common leetspeak substitutions `@→a, 1→i, 0→o, 3→e, $→s`) and tokenizes on whitespace, checking each token with word-boundary matching against the selected bundled wordlist (`bot/src/automod/data/profanityWordlist.default.json` or `profanityWordlist.strict.json`) unioned with `profanityConfig.customWords`.
**Config (`profanityConfig`):** `{ wordlist: "default" | "strict", customWords: string[] }`. Default: `{ wordlist: "default", customWords: [] }`. **Fixed action:** delete message + `WARN`.

### nsfw_image

**Inputs:** attachments on `message` with a content-type starting `image/`.
**Detection:** stateless, per-attachment ML classification. `bot/src/automod/filters/nsfwImage.ts` downloads each qualifying attachment (via `attachment.url`) and classifies it in-process with `nsfwjs` (TensorFlow.js) — an in-process/self-hosted classifier is used rather than a third-party API because `integrations.externalServices` is `[]` in `spec.json`. The filter fires if the summed `porn + hentai` class probability for any attachment is `>= nsfwImageConfig.confidenceThreshold`.
**Config (`nsfwImageConfig`):** `{ confidenceThreshold: number, action: ActionType }`. Default: `{ confidenceThreshold: 0.75, action: "TIMEOUT" }`. This is the one filter routed to moderator confirmation rather than auto-applied (Automod-to-Action Pipeline, below) — the classifier is probabilistic and carries a real false-positive rate, unlike every other filter's deterministic match.

### phishing

**Inputs:** `message.content` (URLs extracted the same way as `links`).
**Detection:** stateless, two-stage, both stages purely in-house per `phishingConfig.blocklistSource: "in-house"` (no external threat-intel API, consistent with `integrations.externalServices: []`):
1. Exact-match each extracted hostname against a curated blocklist bundled in-repo, `bot/src/automod/data/phishingDomains.json`.
2. Typosquat heuristic: Levenshtein distance (via `fastest-levenshtein`) `<= 2` between the hostname and any entry in a curated high-value brand list (`bot/src/automod/data/phishingBrandTargets.json` — seeded with `discord.com`, `steamcommunity.com`, `store.steampowered.com`, and common NFT/crypto-exchange domains) counts as a match.
**Config (`phishingConfig`):** `{ blocklistSource: "in-house", action: ActionType }`. Default: `{ blocklistSource: "in-house", action: "BAN" }`. Both blocklist files are maintained in-repo and updated via ordinary PRs (11-data-privacy-compliance.md and 12-api-reference.md do not define an external feed for this — none exists per scope).

### mass_mention

**Inputs:** `message.mentions.users.size + message.mentions.roles.size` (+1 for `@everyone`/`@here` if present and the author can trigger them).
**Detection:** stateful, per 02-architecture.md's classification of `mass_mention` as a Redis-sliding-window filter (mentions accumulate across messages, not just within one). `bot/src/automod/filters/massMention.ts` adds the current message's mention count to a per-user ZSET, trimmed to a window, then sums scores in-window:
```
ZADD automod:mention:{guildId}:{userId} <nowMs> <messageId>:<mentionCountInThisMessage>
ZREMRANGEBYSCORE automod:mention:{guildId}:{userId} 0 (nowMs - MASS_MENTION_WINDOW_SECONDS*1000)
```
then sums the encoded per-entry mention counts of remaining members and compares to `massMentionConfig.maxMentions`. `massMentionConfig` has no `windowSeconds` field (unlike `spam`/`raid`), so the window is a fixed engine constant, `MASS_MENTION_WINDOW_SECONDS = 10`, defined in `bot/src/automod/filters/massMention.ts` and not guild-configurable.
**Config (`massMentionConfig`):** `{ maxMentions: number, action: ActionType }`. Default: `{ maxMentions: 8, action: "TIMEOUT" }`.

### caps_emoji

**Inputs:** `message.content`.
**Detection:** stateless, two independent sub-checks, either of which fires the filter:
1. Caps ratio: `(count of uppercase letters) / (count of alphabetic letters)`, computed only when the message has `>= 10` alphabetic characters (avoids false positives on short messages like `"OK"` or `"NO"`); fires if `>= capsEmojiConfig.maxCapsRatio`.
2. Emoji count: unicode emoji (regex-matched) plus custom Discord emoji (`<a?:\w+:\d+>` pattern) counted together; fires if `> capsEmojiConfig.maxEmojiCount`.
**Config (`capsEmojiConfig`):** `{ maxCapsRatio: number, maxEmojiCount: number }`. Default: `{ maxCapsRatio: 0.7, maxEmojiCount: 10 }`. **Fixed action:** delete message + `WARN`.

## Raid Threshold & Escalation Rules

`automatedModeration.raidThreshold` and `escalationNotes` are both blank in `spec.json` — this section is the concrete product decision, so no open question is left for implementation. Detection uses the sliding-window join counter defined under **raid**, above (`automod:raid:{guildId}`, `raidConfig.windowSeconds` default `60`, `raidConfig.joinThreshold` default `10`).

**Escalation ladder — three rungs, warn → auto-action → moderator alert:**

1. **Rung 1 — Watch (informational, no `FilterResult`, no `Case`).** Join count reaches 50% of `raidConfig.joinThreshold` (default: **5 joins within 60s**) within the window. `AutomodEngine.evaluateJoin()` writes an `AuditLogEntry` (`actorType: "SYSTEM"`, `eventType: "raid.watch"`) directly via `POST /internal/v1/audit-log` for `audit_viewer` visibility, but does **not** call `AutomodPipeline.handleTrigger()` — sub-threshold join bursts (e.g. a partnership announcement) are common enough that treating every one as a trigger would create noise. This is intentionally the one signal in this document that does not produce a `Case`, because it is not a filter trigger.
2. **Rung 2 — Auto-action.** Join count reaches 100% of `raidConfig.joinThreshold` (default: **10 joins within 60s**). The `raid` filter returns `FilterResult{ filterId: "raid", severity: "critical", action: "LOCKDOWN" }`, which `AutomodPipeline` auto-applies (below): every text channel where `@everyone` has `SEND_MESSAGES` is locked (permission overwrite removing `SEND_MESSAGES` for `@everyone`) for `durationSeconds: 600` (10 minutes) unless manually lifted sooner, and a `Case` (`source: "automod"`, `filterId: "raid"`) is created.
3. **Rung 3 — Moderator alert.** Either (a) the join counter breaches `raidConfig.joinThreshold` again while a Rung-2 `LOCKDOWN` `ModerationAction` from this guild has not yet reached its `expiresAt` (i.e. the raid is continuing through an active lockdown), or (b) a single 60s window sees joins `>= 2 × raidConfig.joinThreshold` (default: **20 joins within 60s**, an immediate-critical case regardless of prior state). Either condition upgrades the result to `severity: "critical"` and, in addition to the Rung-2 `LOCKDOWN`/`Case` flow, `AutomodPipeline` calls `GET /internal/v1/guilds/:guildId/moderators` (new `api` endpoint — resolves `discordUserId`s holding a `PermissionRole` with the `case.resolve` permission flag, catalog in 09-auth-and-permissions.md, by intersecting `GuildMember.roles` with `PermissionRole.discordRoleIds`) and DMs each one an embed containing the raid `Case`'s deep link (`https://web.<domain>/dashboard/{guildId}/cases/{caseId}`, per 08-web-dashboard.md's `case_detail` route). This is the one out-of-band notification path in this file — every other `Case` surfaces purely through the `live_log` panel's `case.created` Socket.IO event (02-architecture.md).

Rung 2 and Rung 3 both flow through the ordinary Automod-to-Action Pipeline below (`raid` is on the auto-applied list) — Rung 3 only adds the moderator DM on top, it does not change how the `Case`/`ModerationAction` are created.

## Automod-to-Action Pipeline

Every `FilterResult` (from either `evaluate()` or `evaluateJoin()`) is handed to `AutomodPipeline.handleTrigger(result, ctx)` in `bot/src/automod/pipeline.ts`, which decides how the result becomes a `ModerationAction`/`Case` pair.

**Auto-applied vs. queued-for-confirmation** is a fixed, platform-level table — not exposed in `config_editor` — so a misconfigured or compromised guild config can never disable moderator review on the one probabilistic filter:

| `filterId` | Default action | Basis | Routing |
|---|---|---|---|
| `spam` | `TIMEOUT` | deterministic count | auto-applied |
| `raid` | `LOCKDOWN` | deterministic count | auto-applied |
| `links` | `WARN` (+ delete) | deterministic allowlist/invite check | auto-applied |
| `profanity` | `WARN` (+ delete) | deterministic wordlist match | auto-applied |
| `nsfw_image` | `TIMEOUT` | **probabilistic ML classifier** | **queued for moderator confirmation** |
| `phishing` | `BAN` | deterministic domain/typosquat match, high harm if delayed | auto-applied |
| `mass_mention` | `TIMEOUT` | deterministic count | auto-applied |
| `caps_emoji` | `WARN` (+ delete) | deterministic ratio/count | auto-applied |

`nsfw_image` is the only queued filter: it is the only one whose detection is a probability estimate rather than an exact match, so an incorrect `TIMEOUT` is a real (if low-probability) UX cost that an automated system should not impose uncontested. Every other filter is either deterministic or reversible enough (`WARN`) that auto-applying and letting the existing confirm/overturn review (02-architecture.md step 7, 06-case-management-and-appeals.md) catch mistakes after the fact is preferable to the latency of waiting on a moderator.

**Pipeline steps:**

1. **Execute (auto-applied only).** `AutomodPipeline` calls `ModerationActions.execute(actionType, target, reason)` (`bot/src/moderation/actions.ts` — the same module `manual_tools` uses, 02-architecture.md/05-manual-moderation.md) synchronously, *before* contacting `api`, so a `Case` is never created for an action that failed to actually apply (e.g. missing `Manage Roles` permission for `ROLE_STRIP`). On failure, `bot` posts `POST /internal/v1/audit-log` with `eventType: "automod.action_failed"` and stops — no `Case` is created for a non-event.
2. **Record the trigger.** On success (auto-applied) or immediately (queued — nothing to execute yet), `bot` calls:
   ```
   POST /internal/v1/cases
   {
     guildId, targetUserId, targetChannelId,
     source: "automod",
     filterId: result.filterId,
     actionTaken: autoApplied ? result.action : null,
     evidence: result.evidence,
     moderatorId: null
   }
   ```
   This is the mechanism that satisfies `manualModerationAndCases.caseManagement: true` for the automod path: **every** `FilterResult` (i.e. every actual filter trigger, Rung-1 raid watch excluded per above) reaches this call, auto-applied or queued alike.
3. **`CasesService.createCase()`** (`api/src/modules/cases/cases.service.ts`) writes, in one Prisma transaction: a `Case` row (`status: "OPEN"`); when `actionTaken` is non-null, a linked `ModerationAction` row (`performedBy: "AUTOMOD"`); and an `AuditLogEntry` row (`eventType: "case.created"`). When `actionTaken` is null (the `nsfw_image` queued path), only the `Case` and `AuditLogEntry` rows are written — no `ModerationAction` exists yet, which is how the dashboard distinguishes "awaiting confirmation" (`case.moderationAction === null`) from "already acted on."
4. **Confirmation (queued path only).** `case_detail` reads the queued case's recommended action live from the guild's `AutomodFilterConfig.nsfwImageConfig.action` (no separate field is stored on `Case` for this — it is always looked up by `filterId` at review time, so it reflects the *current* config even if edited after the case was created). A moderator confirms via `POST /api/v1/guilds/:guildId/cases/:caseId/confirm-action { actionType?, durationSeconds? }` (defaults to the looked-up recommended action; full confirm/overturn UX in 06-case-management-and-appeals.md). This enqueues `{ type: actionType, guildId, targetUserId, caseId }` onto the same `discord-actions` BullMQ queue used for appeal reversal (02-architecture.md step 10); `bot`'s worker executes it via `ModerationActions`, then reports back with `POST /internal/v1/cases/:id/events { type: "action_confirmed" }`, at which point `api` creates the `ModerationAction` row and sets `Case.status = "CONFIRMED"`.
5. **Surfacing.** Every `case.created` (and, for the queued path, subsequent `case.updated`) event is pushed on the `guild:{guildId}` Socket.IO room exactly as described in 02-architecture.md's end-to-end trace, so `live_log`, `case_detail`, and `analytics_charts` all reflect automod activity with no bespoke notification path — except the Rung-3 raid moderator DM (above), which is deliberately out-of-band because it must reach moderators who don't currently have the dashboard open.
