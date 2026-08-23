# 10 — Multi-Guild Support

Implements `scope.inScope: multi_guild` and `webPortal.dashboardFeatures: multi_server_switch`. 03-data-model.md already fixes the `guildId`-scoping pattern every entity follows (Multi-Guild Scoping section) and 09-auth-and-permissions.md already fixes `requireGuildAccess`/`getFlags()`. This file fixes the piece those two leave implicit — how a guild *enters* the system (bot install → provisioned tenant) and how a moderator's session is bound to one of potentially several guilds at a time — plus the isolation and bot-coexistence guarantees that follow from `scope.targetServerSize: "small"` / `technical.targetServerCount: "small"` and `integrations.coexistWithOtherBots: true`.

## Guild Onboarding & Server Switching

### Bot installation (per guild)

**Invite URL** (`web/src/app/install/page.tsx`'s "Add to Discord" button, and any external marketing link): `https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&scope=bot&permissions={PERMISSIONS_BITFIELD}&guild_id={optional}`. No `applications.commands` scope is requested — `integrations.slashCommands: false` means the bot never registers slash/context-menu commands, so that scope would be unused. `PERMISSIONS_BITFIELD` is not a hand-typed literal; it's computed once at build time in `bot/src/discord/permissions.ts`:

```ts
export const REQUIRED_BOT_PERMISSIONS = [
  'ViewChannel', 'SendMessages', 'EmbedLinks', 'ReadMessageHistory',
  'ManageMessages',   // purge, delete-on-links/profanity/caps_emoji
  'ManageChannels',   // create/maintain the #mod-actions console channel
  'ManageRoles',      // role_strip, lockdown's @everyone overwrite edits
  'KickMembers', 'BanMembers',   // kick, softban, ban
  'ModerateMembers',             // timeout
  'CreatePrivateThreads',        // per-ticket private thread creation under #tickets (07-ticketing-system.md)
  'ManageThreads',                // archive/lock a ticket's thread on close (07-ticketing-system.md)
] as const;
export const PERMISSIONS_BITFIELD = PermissionsBitField.resolve([...REQUIRED_BOT_PERMISSIONS]).toString();
```

Deliberately **not** `Administrator` — requesting only this named set is both the least-privilege default and, per Bot Coexistence below, what keeps the invite screen legible about exactly what this bot can touch alongside any other bot already in the guild.

**Provisioning on install:** discord.js's `guildCreate` event (`bot/src/events/guildCreate.ts`) fires when a server owner completes the OAuth2 authorize flow. The handler:

1. Calls `POST /internal/v1/guilds { guildId, name, iconUrl, ownerDiscordId }`. `GuildsService.provisionGuild()` (`api/src/modules/guilds/guilds.service.ts`) upserts on `Guild.id`: if no row exists, it creates one, seeds `AutomodFilterConfig` with the eight `{filter}Config` defaults fixed in 04-automod-engine.md's Filter Catalog, and seeds the two `PermissionRole` rows (`Admin`, `Moderator`, `isBuiltIn: true`, `discordRoleIds: []`, default `permissions` from 09-auth-and-permissions.md's Default Assignment table) — all in one Prisma transaction, plus an `AuditLogEntry { eventType: "guild.installed", actorType: "SYSTEM" }`. If a row already exists (`isActive: false` from a prior removal), it only flips `isActive: true`, refreshes `name`/`iconUrl`/`ownerDiscordId`, and writes `eventType: "guild.reactivated"` — it never re-seeds `AutomodFilterConfig`/`PermissionRole`, so a guild that removes and re-adds the bot keeps its prior filter tuning and role mappings instead of losing them. Response: `{ guildId, isNewInstall: boolean }`.
2. Calls `guild.members.fetch()` and batch-upserts every member via `POST /internal/v1/guilds/:guildId/members/sync { members: [{ discordUserId, discordUsername, discordAvatarUrl, roles, joinedAt }] }` (`GuildMembersService.syncMembers()`, one `GuildMember` row per member per 03-data-model.md). This is what makes the guild owner and staff resolvable by `PermissionRole.discordRoleIds` the moment a moderator maps a role in `role_permission_ui` — without this sync, the mapping would have nothing to intersect against. Ongoing drift is handled the same way 03/09 already describe: `guildMemberAdd`/`guildMemberUpdate`/`guildMemberRemove` gateway handlers each upsert the one affected `GuildMember` row.
3. Calls `ensureConsole(guildId)` (`bot/src/discord/moderationConsole.ts`, 05-manual-moderation.md) — safe to call unconditionally on both fresh installs and reactivations, since it already keys off `Guild.modConsoleChannelId` rather than assuming absence.

**Removal:** `guildDelete` fires when the bot is kicked or the guild deletes itself. `bot/src/events/guildDelete.ts` calls `POST /internal/v1/guilds/:guildId/deactivate`, which sets `Guild.isActive = false` (row kept, per 03-data-model.md's rationale — `Case`/`AuditLogEntry` FKs stay valid) and writes `AuditLogEntry { eventType: "guild.deactivated" }`. `GuildsService.listAccessibleGuilds()` (below) always filters `isActive: true`, so a deactivated guild silently drops out of every moderator's `GuildSwitcher` without any row deletion.

**Extending the audit catalog:** `guild.installed`/`guild.reactivated`/`guild.deactivated` are a new `guild.*` prefix group on top of 09-auth-and-permissions.md's `eventType` catalog and 08-web-dashboard.md's `audit_viewer`, which enumerates that catalog as closed (`case.*`/`appeal.*`/`ticket.*`/`config.*`/`permission.*` plus four standalone system events) for its filter dropdown and badge rendering — `audit_viewer`'s dropdown and prefix grouping must add this fifth group, `targetType`/`targetId` left `null` (the row's own `guildId` column already identifies it, and there's no `case`/`ticket`/`member` to deep-link to), rendering as a plain badge with no target link.

**Owner bootstrap gap:** immediately after install, `Admin.discordRoleIds` is still `[]` (09-auth-and-permissions.md — mapping is a deliberate opt-in human step via `role_permission_ui`), so the guild owner would otherwise see zero flags and the new guild wouldn't even appear in their `GuildSwitcher`. This file closes that gap with one addition on top of 09's `getFlags()` and 03's `requireGuildAccess`: both treat `discordUserId === Guild.ownerDiscordId` as an implicit, unconditional `Admin`-equivalent — `PermissionsService.getFlags()` returns the full `PERMISSION_FLAGS` set for the owner without needing a `GuildMember`/`PermissionRole` intersection at all, and `requireGuildAccess` admits the owner even before their `GuildMember` row exists. This is scoped to `ownerDiscordId` only (never inherited, never delegated) purely so the person who just installed the bot can immediately open `config_editor`/`role_permission_ui` and map real staff roles — day-to-day moderation still runs entirely on `PermissionRole` mappings, not ownership.

### Accessible guild list (login → `GuildSwitcher`)

`GET /api/v1/guilds` (already routed in 08-web-dashboard.md's `multi_server_switch` section) is served by `GuildsService.listAccessibleGuilds(discordUserId)`:

```ts
async function listAccessibleGuilds(discordUserId: string): Promise<Guild[]> {
  return prisma.guild.findMany({
    where: {
      isActive: true,
      OR: [
        { ownerDiscordId: discordUserId },
        { members: { some: {
            discordUserId,
            roles: { hasSome: /* flattened discordRoleIds of every PermissionRole for this guild */ },
        } } },
      ],
    },
  });
}
```

(Implemented as two queries — one for the guild's `PermissionRole.discordRoleIds` per candidate guild, one `GuildMember` lookup — rather than a single Prisma `hasSome` against a dynamic per-row array, since Prisma can't express a cross-row array intersection in one query; `GuildsService` composes them application-side.) This is 09's guild-membership mapping rule plus the owner-bootstrap OR clause above; no third access path exists.

### Portal switching UI

Already routed as `GuildSwitcher` (`web/src/components/GuildSwitcher.tsx`, mounted in `web/src/app/dashboard/layout.tsx`, 08-web-dashboard.md). This file fixes the two states 08 doesn't cover:

- **Landing without a guild segment** (`web/src/app/dashboard/page.tsx`, no `[guildId]`): resolves the target guild server-side as `session.activeGuildId` (`UserSession.activeGuildId`, 03-data-model.md) if it's still present in `listAccessibleGuilds()`'s result, else the first guild in that list ordered by `name`, and redirects (`redirect()` in the Next.js server component) to `/dashboard/{guildId}/live-log`. `PATCH /api/v1/session/active-guild` (08) keeps `activeGuildId` current on every explicit switch.
- **Zero accessible guilds:** `web/src/app/dashboard/page.tsx` renders `web/src/components/NoGuildsEmptyState.tsx` instead of redirecting — copy explaining that either the bot isn't installed anywhere they moderate, or no `PermissionRole` maps their Discord role yet, with the "Add to Discord" install link and a "Ask an admin to grant you a role in Settings → Permissions" note.
- **Direct navigation to an inaccessible `guildId`:** the same `requireGuildAccess` check gating every `/api/v1/guilds/:guildId/*` route also runs in `web/src/app/dashboard/[guildId]/layout.tsx`'s server-side data fetch; a 403 there renders `web/src/components/GuildAccessDenied.tsx` (guild name withheld — the layout only has the raw `guildId` param, not a name, since fetching it would itself require access) rather than silently falling back to another guild, so a moderator never lands somewhere they didn't intend to be.

## Per-Guild Configuration Isolation

`config_editor` (`web/src/app/dashboard/[guildId]/config/page.tsx`, 08-web-dashboard.md) writes `AutomodFilterConfig`; `role_permission_ui` (`web/src/app/dashboard/[guildId]/permissions/page.tsx`) writes `PermissionRole`. Both are sized for `scope.targetServerSize: "small"` / `technical.targetServerCount: "small"` with **row-level tenancy in one shared Postgres + one shared Redis instance** (02-architecture.md's Deployment section already rules out a Kubernetes/multi-region footprint for this scale) — there is no per-guild schema, database, or namespace-per-guild isolation anywhere in this system; isolation is enforced structurally at the query layer instead, as follows.

**The `guildId` a write applies to is always the URL path segment, never request-body data.** `PATCH /api/v1/guilds/:guildId/automod-config` and `POST/PATCH/DELETE /api/v1/guilds/:guildId/permission-roles[/:id]` both run `requireGuildAccess` (03-data-model.md) then `requirePermission('config.edit' | 'permission.edit')` (09-auth-and-permissions.md) as Fastify `preHandler`s keyed on that same `:guildId` param before the handler body ever executes — there is no field in either request payload that names a target guild, so there is nothing for a crafted request to override. A session with `config.edit` in guild A that calls `PATCH /api/v1/guilds/{guildB}/automod-config` gets **403 from `requireGuildAccess`**, not a 404 or a silent no-op — the route doesn't leak whether guild B exists to a caller with no standing in it.

**The write itself is scoped by construction, not by a `WHERE guildId = ...` an implementer could forget:**

```ts
// AutomodConfigService.updateConfig — api/src/modules/automodConfig/automodConfig.service.ts
prisma.automodFilterConfig.update({ where: { guildId }, data: patch });
```

`AutomodFilterConfig.guildId` is `@unique` (03-data-model.md), so this call signature has no way to address any row but the one for the `guildId` already validated by `requireGuildAccess` — there is no multi-row update path in this service. `PermissionRolesService`'s create/update/delete (09-auth-and-permissions.md) are scoped the same way: `create` sets `guildId` from the path param only, and `update`/`delete` resolve the target row via `prisma.permissionRole.findFirst({ where: { id, guildId } })` before mutating — an `id` that exists but belongs to a different guild resolves to nothing (404), same as if it didn't exist at all, so a role ID leaked or guessed from another guild is not a usable write target.

**Cache isolation mirrors DB isolation:** `bot`'s read-through cache for `AutomodFilterConfig` is keyed `automod:config:{guildId}` (04-automod-engine.md), and a `config_editor` write triggers eviction only for that key via the `automod-config-updated:{guildId}` Redis Pub/Sub channel — one guild's edit never invalidates or races another guild's cached config, since the channel name and cache key are the same string.

**Permission-role Discord-role validation stays within the editing guild:** `PermissionRolesService.createRole()`'s `discordRoleIds` check (09-auth-and-permissions.md) calls `GET /internal/v1/guilds/:guildId/roles` — resolved from that specific guild's `guild.roles.cache` in `bot` — so a Discord role ID belonging to a different guild the bot is also in is rejected as "doesn't exist in the guild" (400), the same as a made-up ID; `discordRoleIds` can never point cross-guild.

**Acceptance shape for this section:** for any two guilds A and B, (1) a `config.edit`/`permission.edit` holder in A can never mutate B's `AutomodFilterConfig`/`PermissionRole` rows regardless of what `id`/`guildId` values a crafted request body contains, because those values are never read from the body; (2) reading B's config/roles through A's session 403s at `requireGuildAccess` before any row is touched; (3) `PermissionRole` names collide freely across guilds (`@@unique([guildId, name])`, 03-data-model.md) since the constraint is guild-scoped, not global.

## Bot Coexistence

`integrations.coexistWithOtherBots: true`, and `integrations.notes` ("utilises discord native in-message UI as well as dm") already rules out slash-command namespace collisions by construction (`integrations.slashCommands: false`, 05-manual-moderation.md). The remaining coexistence surface is Discord role hierarchy, channel state, and double-handling of the same event by two bots — none of which the platform prevents automatically.

**No exclusive-authority assumption on Discord roles.** `PermissionRole.discordRoleIds` (03/09) starts empty at seed and is only ever populated by an explicit human action in `role_permission_ui` (Guild Onboarding, above) — the bot never infers moderation authority from role heuristics like "highest non-managed role" or "role named Mod/Admin," which could otherwise accidentally grant power to a role another bot created and owns (e.g. a leveling bot's "VIP" role, or another mod bot's own staff role). This is the direct answer to "avoiding duplicate role/permission assumptions": authority here is always an explicit opt-in mapping scoped to this bot's own `PermissionRole` table, never inferred from Discord's role list itself.

**Role-hierarchy failures degrade, they don't escalate.** `ROLE_STRIP` and `LOCKDOWN`'s permission-overwrite edits both require this bot's highest role to sit above the roles/overwrites they touch (05-manual-moderation.md — `guild.members.me.roles.highest.position`). If a server admin places another moderation bot's role higher in the hierarchy such that a strip/lockdown target is now above this bot, Discord rejects the call (`DiscordAPIError[50013]`); per the Manual Action Set's step 6 and `AutomodPipeline`'s step 1, this is handled as an ordinary execution failure — ephemeral error to the moderator, `automod.action_failed`/no-`Case` for the automod path — never a forced/retried override. This bot never requests `Administrator` (Guild Onboarding, above) specifically so a server admin can position it deliberately relative to other bots rather than needing to reason about a blanket-permission bot's implicit precedence.

**Lockdown touches only the three flags it owns.** `ModerationActions.lockdown()` (05-manual-moderation.md) edits exactly `SendMessages`/`SendMessagesInThreads`/`CreatePublicThreads` on the `@everyone` overwrite, snapshotting and restoring only those three fields (`Case.evidence.previousOverwrites`) — it never touches per-role overwrites (so another moderation bot's own role-scoped channel overwrites are left exactly as they were) and never touches other `@everyone` permission flags another bot or the server owner may have set. `ROLE_STRIP` is likewise scoped to the exact `roleIds` a moderator selected (05) — never "remove all roles" — so it can't incidentally strip a role another bot assigned for unrelated purposes (e.g. a leveling bot's rank role).

**Duplicate-reaction idempotency.** Because another moderation bot may react to the same trigger concurrently, every Discord write this system makes in response to automod/manual triggers tolerates having already happened:

- Message deletion (the fixed "delete message" component of `links`/`profanity`/`caps_emoji`'s `WARN` action, 04-automod-engine.md) wraps `message.delete()` in `bot/src/automod/pipeline.ts`'s trigger handler with a catch on `DiscordAPIError` code `10008` ("Unknown Message") — treated as success (the intended end state, message gone, was already achieved by whoever deleted it first), not routed through the `automod.action_failed` failure path; the `WARN` `Case`/`ModerationAction` is still recorded normally.
- Member-removal actions (`kick`, `timeout`) in `ModerationActions.execute()` (05-manual-moderation.md) catch codes `10007`/`10013` ("Unknown Member"/"Unknown User" — the member already left or was already removed by another bot's concurrent action) and treat them as a **confirmed no-op success**: the `Case`/`ModerationAction` is still written (the desired outcome — member gone/restricted — holds true regardless of actor), with `evidence.metadata: { preExistingState: true }` set so `case_detail`/`audit_viewer` (08/09-*.md) can render it as "already applied" rather than a silent success indistinguishable from a normal one.
- `BAN` needs no special-case: Discord's `guild.members.ban()` succeeds idempotently on an already-banned user, so no additional handling is required beyond the existing success path.

**Channel-name collisions are never adopted.** `ensureConsole()` (05-manual-moderation.md) identifies its own console channel solely by the ID persisted in `Guild.modConsoleChannelId`, never by searching for a channel literally named `#mod-actions` — if another bot happens to have created a same-named channel, `ensureConsole()` creates its own distinct channel (Discord channel names need not be unique) rather than adopting or posting into the other bot's channel.
