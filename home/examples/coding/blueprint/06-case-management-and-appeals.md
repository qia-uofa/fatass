# 06 — Case Management and Appeals

Specifies `manualModerationAndCases.caseManagement: true` and `manualModerationAndCases.appealsProcess: true` (`appealsNotes` is blank in `spec.json` — the concrete appeal flow below is derived from `integrations.notes: "utilises discord native in-message UI as well as dm"` and the DM entry point already fixed in 05-manual-moderation.md, not invented independently). All models referenced here (`Case`, `ModerationAction`, `Appeal`, `AuditLogEntry`) are defined in 03-data-model.md; all writes go through `api`, the sole database client (02-architecture.md).

## Case Lifecycle

### Creation sources

Every `Case` is created by one function, `CasesService.createCase()` (`api/src/modules/cases/cases.service.ts`), called from exactly two ingress points — there is no third way to create a `Case`:

| Source | Caller | `source` | `filterId` | `moderatorDiscordId` at creation |
|---|---|---|---|---|
| Automod trigger | `bot`'s `AutomodPipeline.handleTrigger()` via `POST /internal/v1/cases` (04-automod-engine.md, Automod-to-Action Pipeline step 2) | `"automod"` | the triggering filter (`spam`, `raid`, `links`, `profanity`, `nsfw_image`, `phishing`, `mass_mention`, `caps_emoji`) | `null` |
| Manual action | `bot`'s interaction handlers via `POST /internal/v1/cases` (05-manual-moderation.md, Manual Action Set step 5) | `"manual"` | `null` | the acting moderator's `discordUserId`, set immediately |

Both call sites pass the same payload shape (`guildId, targetUserId, targetChannelId, source, filterId, actionTaken, evidence, moderatorId`). `createCase()` always writes a `Case` row (`status: "OPEN"`) and an `AuditLogEntry` (`eventType: "case.created"`) in one Prisma transaction; it additionally writes a linked `ModerationAction` (`performedBy: "AUTOMOD"` or `"MODERATOR"` per source) whenever `actionTaken` is non-null — the one exception being the `nsfw_image` queued path (04-automod-engine.md step 3/4), where `actionTaken` is `null` at creation and the `ModerationAction` is written later, on confirmation. `case.created` is emitted on the `guild:{guildId}` Socket.IO room immediately after commit (02-architecture.md step 5/6).

### States and transitions

`CaseStatus` (03-data-model.md): `OPEN`, `CONFIRMED`, `OVERTURNED`, `APPEALED`, `RESOLVED`.

```
                    ┌─────────────┐
   createCase() ───▶│    OPEN     │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   confirm-review    overturn-review     member appeals
         │                 │            (action-bearing case)
         ▼                 ▼                 │
   ┌───────────┐    ┌─────────────┐          │
   │ CONFIRMED │    │  OVERTURNED │          │
   └─────┬─────┘    └─────────────┘          │
         │            (terminal)             │
         │  member appeals                   │
         │  (action-bearing case)            │
         └──────────────┬────────────────────┘
                         ▼
                  ┌─────────────┐
                  │  APPEALED   │
                  └──────┬──────┘
                         │ appeal decided (upheld or reversed)
                         ▼
                  ┌─────────────┐
                  │  RESOLVED   │
                  └─────────────┘
                    (terminal)
```

| Transition | Trigger | Endpoint | Effect |
|---|---|---|---|
| `OPEN → CONFIRMED` | Moderator reviews an already-actioned case and agrees with the verdict, **or** confirms a queued `nsfw_image` case's recommended action | `PATCH /api/v1/guilds/:guildId/cases/:caseId { status: "confirmed", resolutionNotes }` (already-actioned case); `POST /api/v1/guilds/:guildId/cases/:caseId/confirm-action { actionType?, durationSeconds? }` (queued case, 04-automod-engine.md step 4 — this path also creates the `ModerationAction` that didn't exist yet) | `CasesService.updateStatus()` sets `Case.status`, writes `resolutionNotes`, emits `case.updated`; `AuditLogEntry { eventType: "case.updated" }` |
| `OPEN → OVERTURNED` | Moderator reviews and disagrees with the verdict | `PATCH /api/v1/guilds/:guildId/cases/:caseId { status: "overturned", resolutionNotes }` | Same as above; if `case.moderationAction` is non-null, `CasesService.updateStatus()` additionally enqueues a `reverse_action` job (see Reversal Mechanics below) so the live Discord-side effect is undone before the case is marked terminal — `updateStatus()` holds the transition at `OPEN` until the worker reports `action_reversed`, then flips to `OVERTURNED`. If `case.moderationAction` is null (queued path, never confirmed), there is nothing to reverse and the transition is synchronous. |
| `OPEN → APPEALED` or `CONFIRMED → APPEALED` | Member disputes an action-bearing case (`case.moderationAction != null`) | `POST /internal/v1/cases/:caseId/appeals` (DM ingress) or `POST /api/v1/guilds/:guildId/cases/:caseId/appeals` (portal ingress) — see Appeals Process below | `AppealsService.fileAppeal()` creates the `Appeal` row and sets `Case.status = "APPEALED"` in the same transaction |
| `APPEALED → RESOLVED` | Moderator decides the appeal | `PATCH /api/v1/guilds/:guildId/appeals/:appealId { decision: "upheld" | "reversed", notes }` | See Appeals Process, Resolution Outcomes |

`OVERTURNED` cases and cases with `moderationAction === null` that were never confirmed (an `nsfw_image` case a moderator overturns without ever confirming) cannot be appealed — `fileAppeal()` rejects with `409 { error: "not_appealable" }` when `case.moderationAction` is null or `case.status` is `"OVERTURNED"` or `"RESOLVED"`. A case that is currently `"APPEALED"` also rejects a second appeal with the same `409` (one open `Appeal` per `Case` at a time — `AppealsService.fileAppeal()` checks `Appeal.findFirst({ caseId, status: "PENDING" })` before inserting).

### Association to Member and Guild

Every `Case` carries `guildId` (tenant key, 03-data-model.md Multi-Guild Scoping) and, for member-targeted cases, `targetDiscordUserId`. `case_detail` resolves the target's live profile via `GuildMember.findUnique({ where: { guildId_discordUserId: { guildId, discordUserId: case.targetDiscordUserId } } })` (the `@@unique([guildId, discordUserId])` index, 03-data-model.md) rather than storing a denormalized copy beyond the `targetUsername` snapshot already on `Case` — this is what lets the panel show current roles/warn count/ban state alongside the point-in-time snapshot of what the moderator saw. Channel-scoped cases (`PURGE`, `LOCKDOWN`) instead resolve `targetChannelId` against the guild's live channel list (fetched from `bot` via cache, not stored redundantly).

### `case_detail` fields

`GET /api/v1/guilds/:guildId/cases/:caseId` (`api/src/modules/cases/cases.controller.ts`) is the sole read path backing `web_dashboard`'s `case_detail` panel (08-web-dashboard.md). Response shape:

```ts
{
  case: {
    id, guildId, status, source, filterId,
    targetDiscordUserId, targetUsername, targetChannelId,
    evidence,              // { messageContent?, attachmentUrls?, channelId?, messageId? } — or lockdown's evidence shape, 05-manual-moderation.md
    resolutionNotes,
    createdAt, updatedAt,
  },
  moderationAction: {      // null for a still-queued nsfw_image case
    actionType, performedBy, moderatorDiscordId,
    durationSeconds, deleteMessageDays, messageCount, roleIdsRemoved,
    reversedAt, reversedByDiscordId,
    createdAt,
  } | null,
  recommendedAction: {     // only present when case.moderationAction is null — looked up live, 04-automod-engine.md step 4
    actionType, source: "AutomodFilterConfig.nsfwImageConfig.action",
  } | null,
  target: {                // GuildMember snapshot, resolved live — null for channel-scoped cases
    discordUsername, discordAvatarUrl, roles, warnCount, isBanned, joinedAt,
  } | null,
  appeals: [{               // full history, most recent first — normally 0 or 1 entries per the one-open-appeal rule
    id, status, reason, ingressPath, submittedByDiscordId,
    decidedByDiscordId, decisionNotes, createdAt, decidedAt,
  }],
  auditTrail: [{             // AuditLogEntry rows filtered by targetType: "case", targetId: caseId, newest first
    eventType, actorType, actorDiscordId, payload, createdAt,
  }],
}
```

The four sections after `case` — `moderationAction`/`recommendedAction`, `target`, `appeals`, `auditTrail` — are exactly what `case_detail`'s four panel regions (action summary, member context, appeals sub-panel, history timeline) render; no additional query is issued client-side beyond this one `GET` plus the `guild:{guildId}` socket subscription for live `case.updated` pushes.

## Appeals Process

`manualModerationAndCases.appealsProcess: true`, `appealsNotes` blank. The flow below is the concrete design that field's absence leaves open, built on the two ingress points 02-architecture.md step 8 and 05-manual-moderation.md already fix as converging on one function, `AppealsService.fileAppeal()` (`api/src/modules/appeals/appeals.service.ts`).

### Submission — DM ingress

Per `integrations.notes: "utilises discord native in-message UI as well as dm"`: every DM `bot` sends for a member-targeted action (`kick`, `softban`, `ban`, `timeout`, `warn`, `role_strip` — 05-manual-moderation.md's DM template) carries an `"Appeal this action"` button, `customId "appeal:open:{caseId}"`. Clicking it opens a `ModalBuilder` (`bot/src/dm/appealFlow.ts`) with one required field, `reason` (`TextInputStyle.Paragraph`, max 1000 chars). On submit, `bot` calls:

```
POST /internal/v1/cases/:caseId/appeals
{ reason }
```

authenticated with the same service JWT as other bot→api calls; `bot` derives `submittedByDiscordId` from the DM's author (the interaction's `user.id`) and passes it in the body alongside `reason`. `ingressPath: "DM"` is set by this route handler, not the client.

### Submission — portal ingress

`case_detail` (08-web-dashboard.md) shows an "Appeal" action on any case where `case.targetDiscordUserId === session.discordUserId` and the case is appealable (see Case Lifecycle, above) — the underlying `GET .../cases/:caseId` route admits the case's own target even without the `case.view` flag via the ownership bypass fixed in 12-api-reference.md, so a member with no `PermissionRole` can still load the one case naming them. Submitting the form calls:

```
POST /api/v1/guilds/:guildId/cases/:caseId/appeals
{ reason }
```

authenticated with the portal session cookie (`discord_oauth`, 09-auth-and-permissions.md). The route handler rejects with `403` if `session.discordUserId !== case.targetDiscordUserId` — a member can only appeal their own case, never another member's, regardless of their `PermissionRole`. `ingressPath: "PORTAL"` is set here. *(Note: `AppealIngress` in 03-data-model.md enumerates `DM | PORTAL`; the DM-path route above sets the literal `"DM"` value.)*

### `fileAppeal()`

Both routes converge on:

```ts
// api/src/modules/appeals/appeals.service.ts
async fileAppeal(caseId: string, params: { reason: string; submittedByDiscordId: string; ingressPath: "DM" | "PORTAL" }): Promise<Appeal>
```

In one Prisma transaction: (1) loads the `Case`, 404s if missing, 409s per the appealability rules in Case Lifecycle above; (2) inserts an `Appeal` row (`status: "PENDING"`, `expiresAt` = `createdAt + 90 days` per 03-data-model.md's Retention & Lifecycle Fields); (3) sets `Case.status = "APPEALED"`; (4) writes `AuditLogEntry { eventType: "appeal.filed", targetType: "case", targetId: caseId, payload: { appealId, ingressPath } }`. After commit it emits `case.updated` (so `live_log`/`case_detail` reflect the new status immediately) and `log.appended`, which feeds the pending-appeals queue view:

```
GET /api/v1/guilds/:guildId/appeals?status=pending
```

— a flat list (`Appeal` joined to its parent `Case`'s `targetUsername`/`filterId`/`moderationAction.actionType`) that backs a dedicated "Appeals" queue panel in `web_dashboard`, structurally the same list-view pattern 07-ticketing-system.md uses for open tickets.

### Reviewer states

An `Appeal` is always in exactly one of `AppealStatus`'s three states:

| State | Meaning | Who can act on it |
|---|---|---|
| `PENDING` | Filed, awaiting moderator review | Any `PermissionRole` holding the `appeal.decide` flag (catalog in 09-auth-and-permissions.md) can claim/decide it — there is no separate "claim" step; the first `PATCH` to reach `resolveAppeal()` wins, and a second concurrent decision attempt 409s (`decidedAt` already set) |
| `UPHELD` | Moderator reviewed and agrees the original action stands | Terminal |
| `REVERSED` | Moderator reviewed and agrees the original action was wrong | Terminal |

`case_detail`'s appeals sub-panel renders a `PENDING` appeal with the submitted `reason`, the original `Case`'s evidence (already loaded alongside it, no extra query), and two buttons, "Uphold" and "Reverse", each opening a small form for the required `notes` field. A resolved appeal (`UPHELD`/`REVERSED`) renders as a read-only history entry: decision, `decidedByDiscordId`, `decisionNotes`, `decidedAt`.

### Resolution

```
PATCH /api/v1/guilds/:guildId/appeals/:appealId
{ decision: "upheld" | "reversed", notes: string }
```

Gated by the `appeal.decide` permission flag (same `hasActionPermission`-style check as 05-manual-moderation.md's action gate, resolved server-side here via `requireGuildAccess` + a permission-flag check rather than the bot's Redis-cached `permissionGate.ts`, since this call originates from `web` or from the bot's DM-side "Uphold"/"Reverse" quick-reply, both of which already carry a resolved `discordUserId`). `AppealsService.resolveAppeal()`:

1. Loads the `Appeal`, 404s if missing, 409s if `status !== "PENDING"`.
2. Sets `Appeal.status = decision === "upheld" ? "UPHELD" : "REVERSED"`, `decidedByDiscordId`, `decisionNotes: notes`, `decidedAt: now()`.
3. Writes `AuditLogEntry { eventType: "appeal.resolved", targetType: "case", targetId: caseId, payload: { appealId, decision, notes } }`.
4. Branches on `decision`:
   - **`upheld`** — no Discord-side effect to undo. `Case.status` is set to `"RESOLVED"` synchronously in the same transaction. `api` enqueues `{ type: "notify_appeal_decision", guildId, targetUserId: case.targetDiscordUserId, caseId, appealId, decision: "upheld", notes }` onto the `discord-actions` BullMQ queue (02-architecture.md) purely for the member DM below — fire-and-forget, no report-back, since there is no case state left to update once the transaction commits.
   - **`reversed`** — `Case.status` stays `"APPEALED"` until the underlying action is actually undone (mirrors the `OPEN → OVERTURNED` rule above: never mark a case terminal ahead of the real Discord-side effect). `api` enqueues `{ type: "reverse_action", guildId, targetUserId: case.targetDiscordUserId, caseId, appealId }` onto `discord-actions`.
5. Both branches emit `case.updated` immediately after the transaction (reflecting `APPEALED`→`RESOLVED` for upheld right away; the reversed branch emits again once the worker reports back, step below).

### Reversal Mechanics

`bot`'s `discord-actions` worker (`bot/src/queue/discordActionsWorker.ts`, 02-architecture.md) handles the `reverse_action` job — the same job type 04-automod-engine.md's step 4 confirm-action flow enqueues, but here initiated by an appeal decision rather than a moderator's confirm/overturn click:

1. Looks up the `Case`'s linked `ModerationAction` and calls the matching undo on `ModerationActions` (`bot/src/moderation/actions.ts`, 05-manual-moderation.md): `TIMEOUT` → `guildMember.timeout(null, reason)`; `BAN`/`SOFTBAN` → `guild.members.unban(userId, reason)`; `ROLE_STRIP` → `member.roles.add(roleIdsRemoved, reason)`; `WARN` → no Discord API call (decrements `GuildMember.warnCount` via `api` instead); `KICK` → no undo possible (member must rejoin voluntarily — the DM notification below says so explicitly); `LOCKDOWN`/`PURGE` are channel-scoped and not member-appealable in practice (no `targetDiscordUserId` to submit an appeal against), so this path is reached only for the six member-targeted action types.
2. On success, sends the appeal-decision DM (below) directly to the target — bot already holds an open connection to the user from the undo call, so it sends the notification itself rather than round-tripping through another queue message.
3. Reports `POST /internal/v1/cases/:caseId/events { type: "action_reversed" }`. `api` sets `ModerationAction.reversedAt = now()`, `ModerationAction.reversedByDiscordId` to the deciding moderator's `discordUserId` (from the `Appeal.decidedByDiscordId` this job was enqueued with), and `Case.status = "RESOLVED"`, then pushes the final `case.updated` over `guild:{guildId}`.
4. On failure (target unreachable, permission error), `bot` posts `POST /internal/v1/audit-log { eventType: "appeal.reversal_failed" }` and does **not** report `action_reversed` — the case stays `"APPEALED"` and surfaces as a stuck item in the appeals queue view for manual follow-up, rather than silently claiming success.

The `OPEN → OVERTURNED` direct-overturn path (Case Lifecycle table, above) reuses this identical `reverse_action` job and worker — the only difference is the job is enqueued by `CasesService.updateStatus()` instead of `AppealsService.resolveAppeal()`, and step 3 sets `Case.status = "OVERTURNED"` instead of `"RESOLVED"` on report-back.

### Notification back to the member

`bot/src/dm/templates.ts` gains one more `EmbedBuilder` factory, `appealDecisionEmbed(decision, notes, caseId)`, sent via `user.send()` with the same failure handling as every other DM in this system (`dm.failed` `AuditLogEntry`, non-blocking — 05-manual-moderation.md):

```
EmbedBuilder
  color:  UPHELD = Red, REVERSED = Green
  title:  decision === "upheld" ? "Your appeal was reviewed — the action stands" : "Your appeal was reviewed — the action has been reversed"
  description: notes                          // the moderator's decisionNotes
  fields: [
    { name: "Case ID", value: caseId },
    { name: "Outcome", value: decision === "upheld" ? "Upheld" : "Reversed" },
    { name: "Note", value: "This action cannot be undone by rejoining.", inline: true }   // KICK only, reversed branch
  ]
  timestamp: now
```

For the `upheld` branch, the `discord-actions` worker's generic `notify_appeal_decision` job handler sends this same embed directly (no Discord-side undo precedes it, so there's no "already connected" shortcut as in the reversed branch — it's a standalone `user.send()` call, same `dm.failed` fallback). Either way, this DM is the **only** notification path for an appeal decision — there is no separate portal notification/email, consistent with `integrations.externalServices: []` and the DM-first design `integrations.notes` establishes; a member who submitted via the portal still finds out via DM, and can review the same outcome by reopening `case_detail`.
