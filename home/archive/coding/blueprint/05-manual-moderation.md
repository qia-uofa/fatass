# 05 — Manual Moderation

Implements `scope.inScope: manual_tools` and every entry in `manualModerationAndCases.manualActions` (`kick`, `softban`, `ban`, `timeout`, `warn`, `purge`, `role_strip`, `lockdown`). Runs entirely in the `bot` process (02-architecture.md's component split) and, per `integrations.slashCommands: false` / `integrations.webhookSupport: false` / `integrations.notes: "utilises discord native in-message UI as well as dm"`, is triggered exclusively through Discord message components (buttons, select menus, modals) and DMs — no `CHAT_INPUT` or context-menu application commands anywhere in this file.

All eight actions share one execution path: `bot/src/moderation/actions.ts`'s `ModerationActions` class, the same module 04-automod-engine.md's `AutomodPipeline` calls for auto-applied filter results. Its dispatcher signature is:

```ts
// bot/src/moderation/actions.ts
type ExecuteParams = {
  guildId: string;
  targetUserId?: string;       // KICK, SOFTBAN, BAN, TIMEOUT, WARN, ROLE_STRIP
  targetChannelId?: string;    // PURGE, LOCKDOWN
  targetChannelIds?: string[]; // LOCKDOWN — full channel list to lock, both server-wide (computed) and channel-specific (moderator-selected, may be one or more) scope
  reason: string;
  durationSeconds?: number;    // TIMEOUT, temp BAN, LOCKDOWN
  deleteMessageDays?: number;  // SOFTBAN, BAN
  messageCount?: number;       // PURGE (requested count; result carries actual deleted count)
  roleIds?: string[];          // ROLE_STRIP
};

class ModerationActions {
  async execute(actionType: ActionType, params: ExecuteParams): Promise<ExecuteResult>;
  // internally delegates to one private method per actionType (kick/softban/ban/timeout/warn/purge/roleStrip/lockdown)
}
```

`execute()` is called identically by `AutomodPipeline.handleTrigger()` (04-automod-engine.md, `performedBy: "AUTOMOD"`) and by this file's interaction handlers (`performedBy: "MODERATOR"`), which is why `ModerationAction.performedBy` (03-data-model.md) is the only field that differs between the two call sites.

## Manual Action Set

**Shared sequence** (all eight actions; per-action deltas are in the table below):

1. A moderator interacts with a component (button/select) laid out in the Discord-Native UI section below. The component's custom ID encodes `{ actionType, guildId, targetUserId | targetChannelId }`.
2. `bot/src/discord/permissionGate.ts`'s `hasActionPermission(moderatorMember, actionType)` resolves the moderator's `PermissionRole` via a Redis-cached (`modperm:{guildId}:{discordUserId}`, TTL 30s) call to `GET /internal/v1/guilds/:guildId/members/:discordUserId/permissions`, and checks the `action.{actionType}` flag (full flag catalog and admin/moderator default mappings in 09-auth-and-permissions.md; this file only fixes the flag name per action, listed in the table below). On failure, bot replies with an ephemeral "You don't have permission for this action" and stops — no modal is shown.
3. Bot opens a `ModalBuilder` (custom ID `mod:{actionType}:modal:{targetUserId|targetChannelId}`) collecting a required `reason` (`TextInputBuilder`, `TextInputStyle.Paragraph`, max 500 chars) plus the action-specific fields in the table below.
4. On modal submit, bot calls `ModerationActions.execute(actionType, params)`.
5. **On success:** bot calls `POST /internal/v1/cases { guildId, targetUserId, targetChannelId, source: "manual", filterId: null, actionTaken: actionType, evidence, moderatorId: <moderator's discordUserId> }`. `CasesService.createCase()` (`api/src/modules/cases/cases.service.ts`) writes `Case` (`status: "OPEN"`, `moderatorDiscordId` set immediately since a moderator, not automod, initiated it), `ModerationAction` (`performedBy: "MODERATOR"`), and `AuditLogEntry` (`eventType: "case.created"`) in one transaction — same write shape as 04-automod-engine.md step 3. Bot then sends the DM template for that action (below) to the target, unless the action is channel-scoped (`purge`, `lockdown`), and edits the originating component message to show a one-line confirmation (`✅ {actionType} by <@{moderatorId}> — case #{caseId}`, replacing the component row so it can't be double-clicked).
6. **On failure** (missing Discord permission for the bot, target left the guild, role-hierarchy violation, etc.): bot replies ephemeral with the underlying `DiscordAPIError` message and does **not** call step 5 — mirrors 04-automod-engine.md's "no `Case` for a non-event" rule.

| `actionType` | Definition | Discord permission (bot must hold) | Internal gating flag | `execute()` call | Modal/select fields beyond `reason` |
|---|---|---|---|---|---|
| `KICK` | Immediately removes the member from the guild; does not add them to the ban list, so they can rejoin on a new invite. | `KICK_MEMBERS` | `action.kick` | `guildMember.kick(reason)` | none |
| `SOFTBAN` | Ban immediately followed by unban, purging the member's recent messages without a permanent ban record on Discord's side. | `BAN_MEMBERS` | `action.softban` | `guild.members.ban(userId, { deleteMessageSeconds: deleteMessageDays * 86400, reason })` then immediately `guild.members.unban(userId, "softban auto-unban")` | `deleteMessageDays` (number select, 0–7, default 1) |
| `BAN` | Removes the member and adds them to the guild ban list; permanent unless `durationSeconds` is set. | `BAN_MEMBERS` | `action.ban` | `guild.members.ban(userId, { deleteMessageSeconds: deleteMessageDays * 86400, reason })`; if `durationSeconds` set, bot also schedules a BullMQ delayed job `unban:{guildId}:{userId}` on the `discord-actions` queue to call `guild.members.unban(userId, "temp-ban expired")` at `durationSeconds` | `deleteMessageDays` (0–7, default 0), `durationSeconds` (select: 1d/7d/30d/permanent) |
| `TIMEOUT` | Applies Discord's native "communication disabled until" state — target can't send messages, react, or join voice until it expires. | `MODERATE_MEMBERS` | `action.timeout` | `guildMember.timeout(durationSeconds * 1000, reason)` | `durationSeconds` (select: 60s/300s/3600s/86400s/604800s — capped at Discord's 28-day max, enforced client-side in the select) |
| `WARN` | Records an infraction and notifies the member; no Discord-side state change. | none — `warn` has no Discord API call beyond the DM | `action.warn` | no-op (skips straight to `CasesService.createCase()`, `actionTaken: "WARN"`) | none |
| `PURGE` | Bulk-deletes recent messages from one channel. | `MANAGE_MESSAGES` | `action.purge` | `channel.bulkDelete(messageCount, true)` (second arg `filterOld` silently skips messages >14 days old, which Discord's API rejects outright) — `ExecuteResult.messageCount` is the actual count of the returned `Collection`, which may be less than requested | `targetChannelId` (via `ChannelSelectMenuBuilder`, channel types `[GuildText]`), `messageCount` (number input, 1–100) |
| `ROLE_STRIP` | Removes one or more roles from the member. | `MANAGE_ROLES`, and the bot's highest role position must exceed every role being removed (Discord role-hierarchy rule — a `DiscordAPIError[50013]` otherwise) | `action.role_strip` | `member.roles.remove(roleIds, reason)` | `roleIds` via `RoleSelectMenuBuilder`, pre-filtered client-side to roles below `guild.members.me.roles.highest.position` so an un-strippable role can't even be selected |
| `LOCKDOWN` | Scope-wide (not member-targeted) — see Lockdown Mechanics, below. | `MANAGE_ROLES` (channel permission-overwrite edits use this permission — Discord's UI labels it "Manage Permissions") | `action.lockdown` | `ModerationActions.lockdown(params)`, detailed below | scope toggle + optional channel select + `durationSeconds`, detailed below |

## Discord-Native UI & DM Interaction Flows

### Moderation Console (member-targeted actions: `kick`/`softban`/`ban`/`timeout`/`warn`/`role_strip`)

With no slash or context-menu commands available, member-targeted actions need a standing entry point that isn't anchored to an existing message. `bot/src/discord/moderationConsole.ts`'s `ensureConsole(guildId)` creates one on guild install (called from the same `provisionGuild()` step that seeds `AutomodFilterConfig`, 04-automod-engine.md) and re-pins it idempotently if deleted. This adds two columns to the `Guild` model (03-data-model.md): `modConsoleChannelId String?`, `modConsoleMessageId String?`. `provisionGuild()` creates a dedicated `#mod-actions` text channel (`guild.channels.create({ name: 'mod-actions', permissionOverwrites: [{ id: everyoneRoleId, deny: [ViewChannel] }] })`, then grants `ViewChannel` to whichever Discord role IDs back the `admin`/`moderator` `PermissionRole` rows), posts the console message, and pins it.

The console is one message, permanently visible, edited in place (never reposted) whenever its selection state changes:

```
Row 1: UserSelectMenuBuilder        customId "modconsole:selectTarget"    placeholder "Select a member…"
Row 2: ButtonBuilder × 6             customId "modconsole:action:{kick|softban|ban|timeout|warn|role_strip}"
                                      styles: kick/timeout/warn/role_strip = Secondary, softban/ban = Danger
                                      disabled: true until a target is selected
```

Selecting a member in the `UserSelectMenuBuilder` triggers an interaction-update that (a) records the selection in a short-TTL Redis key `modconsole:selection:{guildId}:{moderatorId}` (60s TTL — scoped per-moderator so two mods using the console concurrently don't clobber each other) and (b) enables the six action buttons and appends the selected member's tag to the message content. Clicking an action button reads that Redis key for the target and opens the modal from the Manual Action Set sequence, step 3.

### Inline action row on Case embeds (any action, target pre-filled)

Every `Case` posted to `live_log`'s underlying channel feed (the same message described in 02-architecture.md step 6/04-automod-engine.md step 5) carries an inline row so a moderator can escalate directly from the flagged evidence without touching the console:

```
Row: ButtonBuilder × up to 3   customId "mod:{actionType}:{guildId}:{targetUserId}"
     always present: "Warn" (Secondary), "Timeout" (Secondary), "Ban" (Danger)
     present only when case.moderationAction is null (nsfw_image queued path, 04-automod-engine.md step 4): "Confirm" / "Overturn" instead (06-case-management-and-appeals.md)
```

Clicking one of the three quick-action buttons here still runs the Manual Action Set sequence's step 2 permission gate (`hasActionPermission` checked against the clicking moderator, identically to the console path) before jumping straight to step 3's modal — target and `guildId` are already known from the custom ID, so there's no step 1 target-selection UI to show — reusing the identical modal/`execute()`/`createCase()` path.

### Purge and Lockdown consoles (channel-scoped, no member target)

Two additional buttons on the Moderation Console, in a third row, open channel-scoped flows instead of consuming the user-select state:

```
Row 3: ButtonBuilder × 2   customId "modconsole:action:purge"     style Secondary
                            customId "modconsole:action:lockdown"  style Danger
```

`purge` opens the modal directly (`targetChannelId` via `ChannelSelectMenuBuilder` embedded as the modal's first row per discord.js v14's support for select menus inside modals, `messageCount` input, `reason`). `lockdown`'s flow is detailed in Lockdown Mechanics, below.

### DM templates

Every member-targeted action (`kick`, `softban`, `ban`, `timeout`, `warn`, `role_strip`) sends the target a DM — attempted via `user.send()`, and if it fails (DMs closed), the bot records `AuditLogEntry { eventType: "dm.failed", targetType: "case", targetId: caseId }` and continues (a failed DM never blocks or reverses the underlying action). `purge` and `lockdown` are channel/scope-wide and have no single recipient, so no DM is sent for them — `lockdown`'s in-channel announcement is covered in Lockdown Mechanics.

Template (`bot/src/dm/templates.ts`, one `EmbedBuilder` factory per `actionType`, shared shape):

```
EmbedBuilder
  color:  <per-action, e.g. WARN=Yellow, TIMEOUT=Orange, KICK/SOFTBAN=Orange, BAN/ROLE_STRIP=Red>
  title:  "You have been {actioned} in {guild.name}"
  description: reason
  fields: [
    { name: "Action", value: actionType },
    { name: "Duration", value: humanize(durationSeconds), inline: true }   // TIMEOUT, temp BAN only
    { name: "Roles removed", value: roleNames.join(", "), inline: true }   // ROLE_STRIP only
    { name: "Case ID", value: caseId }
  ]
  footer: { text: "Reply here or use the button below if you believe this was a mistake." }
  timestamp: now
Row: ButtonBuilder  customId "appeal:open:{caseId}"  label "Appeal this action"  style Secondary
     disabled if manualModerationAndCases.appealsProcess is false for this deployment (always true per spec.json) — included for completeness, never actually disabled here
```

Clicking "Appeal this action" opens a `ModalBuilder` (`bot/src/dm/appealFlow.ts`, per 02-architecture.md step 8a) with one `TextInputStyle.Paragraph` field, `reason`. On submit, `bot` calls `POST /internal/v1/cases/:caseId/appeals { reason }` (`ingressPath: "DM"`, 03-data-model.md's `Appeal` model), which `AppealsService.fileAppeal()` handles identically to the portal-side ingress path — full lifecycle (status transitions, moderator resolution UI, reversal) specified in 06-case-management-and-appeals.md; this file only fixes the DM-side entry point and its modal shape. `BAN` follows the same execute-then-notify order as every other action — `ModerationActions.ban()` still runs before `CasesService.createCase()`, so the DM (which embeds the real `Case ID`) is only ever sent after the case exists, per the Manual Action Set sequence's step 5. A DM send that fails because the target became unreachable after being banned is not a special case: it falls under the same "DMs closed" handling described above (`dm.failed` `AuditLogEntry`, action not reversed).

## Lockdown Mechanics

`lockdown` is the one `manualModerationAndCases.manualActions` entry that is scope-wide (one or more channels) rather than member-targeted — it has no `targetUserId` and therefore no DM.

**What it locks:** for every target channel, `ModerationActions.lockdown()` edits the `@everyone` role's permission overwrite on that channel to deny `SendMessages` (and `SendMessagesInThreads`, `CreatePublicThreads`) — `channel.permissionOverwrites.edit(guild.roles.everyone, { SendMessages: false, SendMessagesInThreads: false, CreatePublicThreads: false }, { reason })`. Before editing, it snapshots each channel's *prior* `@everyone` overwrite for exactly those three permission flags (not the whole overwrite object, so any other custom overwrite on the channel is left untouched) into `Case.evidence`: `{ lockedChannelIds: string[], previousOverwrites: Record<channelId, { sendMessages: boolean | null, sendMessagesInThreads: boolean | null, createPublicThreads: boolean | null }> }` (`null` = the permission had no explicit overwrite before lockdown, i.e. it was inherited). This is what lets lift restore the exact prior state rather than merely deleting the overwrite outright (which would incorrectly grant `SendMessages` if `@everyone` had it explicitly denied for some other reason before the lockdown).

**Scope — server-wide vs. channel-specific:**

- **Server-wide** (the default, and the only mode automod raid detection uses): `targetChannelIds` = every channel where `channel.permissionsFor(guild.roles.everyone).has('SendMessages')` is currently true (i.e. channels that were actually open, so a channel already locked by a moderator for unrelated reasons isn't touched or later incorrectly unlocked). `ModerationAction.targetChannelId` (03-data-model.md, singular) is left `null` for this mode — the full list lives in `Case.evidence.lockedChannelIds` — while `ModerationAction.targetChannelId` is set to the single channel ID when scope is channel-specific.
- **Channel-specific:** the moderator picks one or more channels via a `ChannelSelectMenuBuilder` (channel types `[GuildText]`) in the lockdown modal; only those are locked, and if more than one is selected the same `Case.evidence.lockedChannelIds` shape is used (with `ModerationAction.targetChannelId` set to the first/primary one for indexing, full list still in `evidence`).

**Triggered manually:** clicking "Lockdown" on the Moderation Console (Discord-Native UI section, above) opens a modal with: a scope toggle (`StringSelectMenuBuilder`, options `"Entire server"` / `"Specific channel(s)"`), a `ChannelSelectMenuBuilder` (only rendered/required when "Specific channel(s)" is chosen), `durationSeconds` (`StringSelectMenuBuilder`: 10m/30m/1h/6h/24h/"Manual lift only"), and `reason`. Submission follows the Manual Action Set sequence exactly (`action.lockdown` gate, `execute()`, `POST /internal/v1/cases` with `source: "manual"`).

**Triggered by automod raid detection:** per 04-automod-engine.md's escalation ladder, Rung 2 (join count reaches `raidConfig.joinThreshold`, default 10/60s) has the `raid` filter return `FilterResult{ filterId: "raid", severity: "critical", action: "LOCKDOWN" }`; `AutomodPipeline.handleTrigger()` calls the identical `ModerationActions.lockdown()` with server-wide scope and `durationSeconds: 600` (10 minutes), then `POST /internal/v1/cases` with `source: "automod"`, `filterId: "raid"`, `performedBy: "AUTOMOD"` — same function, same `Case`/`ModerationAction` write shape as the manual path, per this file's shared-execution-path design. Rung 3's "is a lockdown already active" check (needed to decide whether to also DM moderators) reads the Redis key below rather than re-querying Postgres on every join event.

**Active-lockdown tracking:** on successful lock, `ModerationActions.lockdown()` sets `automod:lockdown:{guildId}` in Redis to the new `Case.id`, with a TTL equal to `durationSeconds` (no TTL / persists until explicit delete when `durationSeconds` is null, i.e. "manual lift only"). This key is what 04-automod-engine.md's Rung 3 condition ("a Rung-2 `LOCKDOWN` `ModerationAction` from this guild has not yet reached its `expiresAt`") checks via a simple `EXISTS`, and what the Moderation Console reads to swap its "Lockdown" button to "Lift Lockdown" (`customId "modconsole:action:lift-lockdown:{caseId}"`) while active.

**Lifted:**

- **Scheduled (has `durationSeconds`):** at lock time, `ModerationActions.lockdown()` also schedules a BullMQ delayed job (`discord-actions` queue, `{ type: 'lift_lockdown', guildId, caseId }`, delay = `durationSeconds * 1000`). `bot`'s worker restores each locked channel's overwrite from `Case.evidence.previousOverwrites` (re-applying the exact prior boolean/`null` per flag — `null` means `channel.permissionOverwrites.delete(guild.roles.everyone)` for that permission if no other flags remain overwritten, otherwise a partial `.edit()` clearing only the three lockdown-related flags), deletes the `automod:lockdown:{guildId}` Redis key, posts `POST /internal/v1/cases/:id/events { type: "lockdown_lifted" }` (`api` writes `AuditLogEntry { eventType: "lockdown.lifted" }` and pushes `case.updated` over the `guild:{guildId}` socket room per 02-architecture.md), and posts a plain-text "🔓 Lockdown lifted (auto-expired)." message into each restored channel.
- **Manual (before or without a scheduled expiry):** a moderator with the `action.lockdown` flag clicks "Lift Lockdown" on the console; bot cancels the pending BullMQ job (if any, by its deterministic job ID `lift_lockdown:{caseId}`) and runs the identical restore-and-report path above, so both lift paths converge on one function, `ModerationActions.liftLockdown(caseId)`.

Every restored channel additionally receives the announcement embed `"🔒 This channel was locked down (case #{caseId}) — {reason}. New messages are disabled until {lifted or expiresAt}."` at lock time (posted once, not per-message), giving members an in-channel explanation without a DM, since lockdown has no single target to DM.
