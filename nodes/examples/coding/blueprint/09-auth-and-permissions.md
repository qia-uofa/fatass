# 09 — Auth & Permissions

Implements `webPortal.authMethod: "discord_oauth"` and all of `rolesAndPermissions` (`permissionLevels: ["admin", "moderator"]`, `customPermissionBuilder: true`, `auditLogging: true`). Runs across `web` (login UI, session cookie) and `api` (token exchange, session/permission storage, the sole DB client per 02-architecture.md); `bot` only ever calls `api`'s internal permission-check route, never Discord's OAuth endpoints itself. `UserSession` and `PermissionRole` schemas are already fixed in 03-data-model.md's Core Entity Schemas; `AuditLogEntry` likewise. This file fixes the OAuth mechanism end-to-end, the full permission-flag catalog and evaluation logic 03/05/06/07/08 all defer to, and the audit-logging write path 08's `audit_viewer` reads from.

## Discord OAuth Flow

**Provider:** NextAuth.js in `web`, with a custom Discord OAuth2 provider (`web/src/lib/auth/discordProvider.ts`) rather than a generic `next-auth` community package, so the callback can write directly into `api`'s `UserSession` table instead of NextAuth's default adapter schema. Discord app credentials (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`) and the encryption key for token-at-rest storage (`SESSION_TOKEN_KEY`, AES-256-GCM, used by `api` — see Token Storage below) are read from environment, never committed.

**Scopes:** `identify` only. Dashboard guild access is *not* derived from Discord's OAuth `guilds`/`guilds.members.read` scopes — it's resolved server-side per-request from `GuildMember` (kept in sync by `bot`'s gateway connection) intersected with `PermissionRole.discordRoleIds`, exactly as 03-data-model.md's Multi-Guild Scoping section and `requireGuildAccess` already fix. Requesting `guilds` would only duplicate data the bot's gateway cache already owns more accurately (a user's OAuth guild list can be stale relative to real-time role changes), so it's deliberately omitted.

**Authorization Code flow (`web/src/app/api/auth/[...nextauth]/route.ts`):**

1. User clicks "Login with Discord" (`web/src/components/LoginButton.tsx`). NextAuth redirects to `https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={encoded callback URL}&response_type=code&scope=identify&state={CSRF token}`, the `state` param generated and verified by NextAuth's built-in CSRF protection.
2. Discord redirects back to `https://web.<domain>/api/auth/callback/discord?code={code}&state={state}`.
3. NextAuth's provider `token` handler exchanges the code server-side: `POST https://discord.com/api/oauth2/token` with `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `client_secret` (form-encoded) — returns `{ access_token, refresh_token, expires_in, token_type: "Bearer" }`.
4. The provider's `userinfo` handler calls `GET https://discord.com/api/users/@me` with `Authorization: Bearer {access_token}`, returning `{ id, username, avatar, ... }` — this `id` is the canonical `discordUserId` used everywhere in 03-data-model.md.
5. NextAuth's `signIn` callback calls `POST /internal/v1/sessions` on `api` with `{ discordUserId, discordUsername, discordAvatarUrl, accessToken, refreshToken, expiresIn }`. `api`'s `SessionsService.upsertSession()` (`api/src/modules/sessions/sessions.service.ts`) encrypts both tokens (AES-256-GCM, `SESSION_TOKEN_KEY`) into `accessTokenEnc`/`refreshTokenEnc`, and upserts a `UserSession` row (`discordUserId`, `discordUsername`, `oauthExpiresAt: now() + expiresIn`, `expiresAt: now() + 90 days` per 03-data-model.md's retention rule, `activeGuildId: null` on first login) keyed on `discordUserId` — one `UserSession` row per Discord user, re-used across logins rather than accumulating one row per session. It returns `{ sessionId }`.
6. NextAuth's `jwt` callback embeds `sessionId` (the `UserSession.id`, not the Discord tokens themselves) into its signed JWT; the `session` callback exposes `session.user.discordUserId`/`sessionId` to `web`'s client code. The cookie NextAuth sets (`next-auth.session-token`) is `httpOnly`, `Secure`, `SameSite=Lax` — it never carries the Discord access/refresh token in cleartext to the browser.
7. Every subsequent `web → api` request attaches the cookie; `api`'s `sessionAuth` Fastify `preHandler` (`api/src/plugins/sessionAuth.ts`) verifies the NextAuth JWT signature (shared `NEXTAUTH_SECRET`), loads the referenced `UserSession` row, 401s if `deletedAt` is set or `expiresAt` has passed, and attaches `request.session = { discordUserId, sessionId }` for downstream handlers — including 03-data-model.md's `requireGuildAccess`, which runs immediately after this on every `/api/v1/guilds/:guildId/*` route.

**Token refresh:** on each `sessionAuth` check, if `oauthExpiresAt` is within 5 minutes of expiring, `api` transparently calls `POST https://discord.com/api/oauth2/token` with `grant_type=refresh_token` using the decrypted `refreshTokenEnc`, and updates `accessTokenEnc`/`refreshTokenEnc`/`oauthExpiresAt` in place — the dashboard session never visibly expires mid-use as long as Discord hasn't revoked the grant. If the refresh call itself 401s (user revoked app access on Discord's side), `api` sets `UserSession.deletedAt = now()` and the next request 401s, forcing `web` to redirect to `/login`.

**Guild membership mapping (login → dashboard access):** the OAuth flow above only establishes *who* the user is (`discordUserId`); it grants no guild access by itself. `multi_server_switch` (08-web-dashboard.md) resolves *which* guilds that identity can act in via `GET /api/v1/guilds`, i.e. `guildMember.findMany({ where: { discordUserId: session.discordUserId } })` joined to `Guild` — a Discord user only appears there for guilds where `bot` has already synced a `GuildMember` row for them (they're a real member of a guild the bot is installed in) **and** that `GuildMember`'s `roles` intersects at least one `PermissionRole.discordRoleIds` for that guild (Permission Levels, below) — a guild member with no mapped Discord role sees that guild nowhere in the switcher, since they hold zero permission flags there. This is the same `requireGuildAccess` check 03-data-model.md already fixes; this file adds no second access-control path, only the identity that feeds it.

**Logout:** `POST /api/v1/session/logout` (`web`'s logout button) — `api` calls `POST https://discord.com/api/oauth2/token/revoke` with the decrypted `accessTokenEnc` (`token_type_hint=access_token`), then sets `UserSession.deletedAt = now()` immediately (03-data-model.md notes this is independent of the 90-day sweep), and NextAuth clears the cookie client-side.

## Permission Levels & Custom Permission Builder

**Storage:** every permission level — the two built-ins and every custom one — is a `PermissionRole` row (03-data-model.md). There is no separate "level" enum or column: `rolesAndPermissions.permissionLevels: ["admin", "moderator"]` are just the two rows `provisionGuild()` (04-automod-engine.md / 05-manual-moderation.md) seeds on guild install with `isBuiltIn: true`, `name: "Admin"` / `"Moderator"`, `discordRoleIds: []` (unmapped until a moderator assigns Discord roles via `role_permission_ui`), and the default `permissions` arrays below. `customPermissionBuilder: true` means `role_permission_ui` can create arbitrary additional `PermissionRole` rows through the identical model — "custom permission set" is not a different mechanism from the two built-ins, it's the same table with `isBuiltIn: false`.

**Permission-flag catalog:** a fixed, versioned list — not user-definable strings — declared once in `packages/shared-types/src/permissions.ts`:

```ts
export const PERMISSION_FLAGS = [
  // read/view flags — gate the dashboard panels listed in 08-web-dashboard.md
  'case.view',        // live_log, case_detail, member_mgmt's case-history join
  'member.view',      // member_mgmt roster + detail
  'analytics.view',   // analytics_charts
  'audit.view',       // audit_viewer (this file's own read gate)
  // write/action flags — gate the endpoints/components fixed in 05/06/07/08
  'case.resolve',      // confirm/overturn a case (06), raid Rung-3 moderator DM recipients (04)
  'appeal.decide',     // uphold/reverse an appeal (06)
  'ticket.claim',      // claim/resolve/close a ticket — one flag for all three (07)
  'config.edit',       // AutomodFilterConfig writes (08's config_editor)
  'permission.edit',   // PermissionRole CRUD (08's role_permission_ui — self-gated)
  // one flag per manual moderation action (05's Manual Action Set table)
  'action.kick',
  'action.softban',
  'action.ban',
  'action.timeout',
  'action.warn',
  'action.purge',
  'action.role_strip',
  'action.lockdown',
] as const;
export type PermissionFlag = typeof PERMISSION_FLAGS[number];
```

This module is imported by `api` (Fastify typebox route schemas validate `PermissionRole.permissions` bodies against it — `POST`/`PATCH /api/v1/guilds/:guildId/permission-roles` in 08-web-dashboard.md 400s on an unknown flag) and by `web` (the flag checklist / role×flag matrix in `role_permission_ui` renders directly off this array, grouped by the three comment sections above, so a new flag added here needs no separate UI change).

**Default assignment for the two built-ins** (seeded once at install; editable afterward like any other `PermissionRole` — a guild admin can strip flags from `Moderator` or grant `permission.edit` to it, the seed is only a starting point):

| Flag group | `Admin` | `Moderator` |
|---|---|---|
| `case.view`, `member.view`, `analytics.view`, `audit.view` | ✓ | ✓ |
| `case.resolve`, `appeal.decide`, `ticket.claim` | ✓ | ✓ |
| `action.kick` … `action.lockdown` (all 8) | ✓ | ✓ |
| `config.edit` | ✓ | — |
| `permission.edit` | ✓ | — |

Rationale: day-to-day moderation (viewing, resolving cases/appeals/tickets, every manual action) is the `Moderator` level's entire job per `manualModerationAndCases`, so it gets every operational flag by default; `config.edit` and `permission.edit` are held back for `Admin` because they change *how* moderation behaves guild-wide (automod tuning, who holds what power) rather than performing a moderation action — a guild that wants a flatter default can grant either flag to `Moderator` (or a custom role) from `role_permission_ui` with no schema change, since both are just entries in `PermissionRole.permissions`.

**Custom Permission Builder — schema and UI (`role_permission_ui`, 08-web-dashboard.md §`role_permission_ui`):** already routed at `web/src/app/dashboard/[guildId]/permissions/page.tsx` and backed by `GET/POST/PATCH/DELETE /api/v1/guilds/:guildId/permission-roles`; this section fixes the write-path validation those endpoints enforce, all inside `PermissionRolesService` (`api/src/modules/permissionRoles/permissionRoles.service.ts`):

- `createRole({ name, discordRoleIds, permissions })`: `name` 1–50 chars, unique per guild (`@@unique([guildId, name])`, 03-data-model.md — a duplicate name 409s); `permissions` filtered to only values in `PERMISSION_FLAGS` (a request containing an unknown flag 400s, per the typebox schema above) and defaults to `[]` — a newly created custom role grants nothing until flags are explicitly checked, so creating a role is never accidentally privilege-escalating; `discordRoleIds` validated against `bot`'s cached role list (`GET /internal/v1/guilds/:guildId/roles`, resolved from `guild.roles.cache` — a Discord role ID that doesn't exist in the guild 400s) but is **not** a live Discord-side FK: if a mapped Discord role is later deleted in Discord, the stale ID is simply inert in `hasPermission()`'s intersection (below), not an error, since `bot` has no gateway hook re-validating `PermissionRole.discordRoleIds` continuously. `isBuiltIn` is never client-settable — it's hardcoded `false` on every row this endpoint creates.
- `updateRole(id, { name?, discordRoleIds?, permissions? })`: same field validation as create; `isBuiltIn` rows accept `discordRoleIds`/`permissions` changes but reject `name` changes (409, per 08's note that built-in rows "can't be deleted or renamed").
- `deleteRole(id)`: 404 if missing, 409 if `isBuiltIn: true` (08-web-dashboard.md).
- All four routes carry `preHandler: [requireGuildAccess, requirePermission('permission.edit')]` — see Evaluation & Gating, below.

**Evaluation logic — `hasPermission()`:** the single function every gate in 05/06/07/08 ultimately calls, `PermissionsService.getFlags()` (`api/src/modules/permissions/permissions.service.ts`):

```ts
async function getFlags(guildId: string, discordUserId: string): Promise<Set<PermissionFlag>> {
  const member = await prisma.guildMember.findUnique({ where: { guildId_discordUserId: { guildId, discordUserId } } });
  if (!member) return new Set();                       // no GuildMember row ⇒ zero flags, mirrors requireGuildAccess's 403
  const roles = await prisma.permissionRole.findMany({ where: { guildId } });
  const flags = new Set<PermissionFlag>();
  for (const role of roles) {
    if (role.discordRoleIds.some(id => member.roles.includes(id))) {
      role.permissions.forEach(p => flags.add(p as PermissionFlag));
    }
  }
  return flags;
}
```

Permissions are **additive across roles**: a `GuildMember` whose Discord roles map to both `Moderator` and a custom "Ticket Lead" `PermissionRole` holds the union of both roles' `permissions`, not just the higher/lower one — there is no rank ordering between `PermissionRole` rows, only flag membership.

**How this gates every action in 05/06/07/08:**

- **`web`/`api` writes:** a `requirePermission(flag: PermissionFlag)` Fastify `preHandler` (`api/src/plugins/requirePermission.ts`) runs immediately after `requireGuildAccess` (03-data-model.md) on every write route: `getFlags(guildId, session.discordUserId)` then `.has(flag)`, 403 if absent. This is the mechanism behind every flag named in 06/07/08 — `case.resolve` on the `confirm-action`/status-transition routes (06), `appeal.decide` on the appeal-resolution `PATCH` (06), `ticket.claim` on claim/resolve/close (07), `config.edit` on the `automod-config` `PATCH` (08), `permission.edit` on the `permission-roles` routes above — and the corresponding `*.view` flags gate their sibling `GET` routes (`case.view` on `/cases`/`/cases/:caseId`, `member.view` on `/members`, `analytics.view` on `/analytics`, `audit.view` on `/audit-log`) — `/cases/:caseId` alone also admits the caller when `session.discordUserId === case.targetDiscordUserId`, even absent `case.view` (12-api-reference.md), so the case's own target can load it to appeal.
- **`bot` writes:** 05-manual-moderation.md's `hasActionPermission(moderatorMember, actionType)` (`bot/src/discord/permissionGate.ts`) is a thin client over the same logic — it calls `GET /internal/v1/guilds/:guildId/members/:discordUserId/permissions` (an internal route that runs `getFlags()` directly and returns `{ flags: PermissionFlag[] }`), Redis-caches the result 30s (`modperm:{guildId}:{discordUserId}`), and checks `flags.includes('action.' + actionType.toLowerCase())` — the exact `action.{actionType}` mapping the table in 05-manual-moderation.md's Manual Action Set already fixes per action.
- **Realtime/socket access:** 03-data-model.md's Multi-Guild Scoping section already ties Socket.IO room admission to `requireGuildAccess`; this file adds no separate flag check there — a connected socket sees every event for guilds it has *any* `PermissionRole` in (even one with zero flags checked would still hold `case.view` implicitly false and thus get 403'd off the `GET` that seeds `live_log`, so in practice a flag-less member's dashboard renders empty panels rather than erroring the socket itself).

## Audit Logging

`rolesAndPermissions.auditLogging: true`. `AuditLogEntry` (schema fixed in 03-data-model.md — `id`, `guildId`, `actorType: SYSTEM | BOT | MODERATOR`, `actorDiscordId`, `eventType: string`, `targetType`, `targetId`, `payload: Json`, `createdAt`, plus the standard `expiresAt`/`deletedAt` retention pair) is the single append-only table every state-changing write across the system inserts into, in the same transaction as the state change itself — never a best-effort side call, so the log can't drift from what actually happened.

**Full `eventType` catalog** (collecting every value fixed across the files that own each write path — this file adds only `permission.updated`):

| `eventType` | `actorType` | Written by | `targetType` / `targetId` |
|---|---|---|---|
| `case.created` | `AUTOMOD` / `MODERATOR` | `CasesService.createCase()` (04-automod-engine.md step 3, 05-manual-moderation.md step 5, 06-case-management-and-appeals.md) | `"case"` / `Case.id` |
| `case.updated` | `MODERATOR` | `CasesService.updateStatus()` / `confirmAction()` (06-case-management-and-appeals.md) | `"case"` / `Case.id` |
| `raid.watch` | `SYSTEM` | `AutomodEngine.evaluateJoin()` (04-automod-engine.md Rung 1 — the one event with no `Case`) | `"case"` / `null` |
| `automod.action_failed` | `SYSTEM` | `AutomodPipeline` on a failed auto-applied action (04-automod-engine.md) | `null` / `null` |
| `dm.failed` | `MODERATOR` | any member-targeted manual action whose DM send fails (05-manual-moderation.md) | `"case"` / `Case.id` |
| `lockdown.lifted` | `SYSTEM` | scheduled lockdown-expiry worker (05-manual-moderation.md) | `"case"` / `Case.id` |
| `appeal.filed` | `MODERATOR` | `AppealsService.fileAppeal()` (06-case-management-and-appeals.md) | `"case"` / `Case.id`, `payload: { appealId, ingressPath }` |
| `appeal.resolved` | `MODERATOR` | `AppealsService.resolveAppeal()` (06-case-management-and-appeals.md) | `"case"` / `Case.id`, `payload: { appealId, decision, notes }` |
| `appeal.reversal_failed` | `SYSTEM` | `bot`'s `discordActionsWorker` on a failed `reverse_action` job (06-case-management-and-appeals.md) | `"case"` / `Case.id` |
| `ticket.created` | `MODERATOR`* | `TicketsService.createTicket()` (07-ticketing-system.md) | `"ticket"` / `Ticket.id` |
| `ticket.claimed` | `MODERATOR` | `TicketsService.claimTicket()` (07-ticketing-system.md) | `"ticket"` / `Ticket.id` |
| `ticket.resolved` | `MODERATOR` | `TicketsService.resolveTicket()` (07-ticketing-system.md) | `"ticket"` / `Ticket.id` |
| `ticket.closed` | `MODERATOR` | `TicketsService.closeTicket()` (07-ticketing-system.md) | `"ticket"` / `Ticket.id` |
| `config.updated` | `MODERATOR` | `AutomodConfigService`'s `automod-config` `PATCH` handler (08-web-dashboard.md's `config_editor`) | `"config"` / `AutomodFilterConfig.id`, `payload`: `{ before, after }` diff of changed `{filter}Enabled`/`{filter}Config` fields only |
| `permission.updated` | `MODERATOR` | `PermissionRolesService`'s create/update/delete handlers, above (this file, `role_permission_ui`) | `"permission"` / `PermissionRole.id`, `payload`: `{ action: "created" \| "updated" \| "deleted", before?, after? }` — `before` omitted on create, `after` omitted on delete |
| `guild.installed` | `SYSTEM` | `GuildsService.provisionGuild()` on a true first install (10-multi-guild-support.md) | `null` / `null` |
| `guild.reactivated` | `SYSTEM` | `GuildsService.provisionGuild()` when a previously-deactivated guild re-adds the bot (10-multi-guild-support.md) | `null` / `null` |
| `guild.deactivated` | `SYSTEM` | `guildDelete` handler → `POST /internal/v1/guilds/:guildId/deactivate` (10-multi-guild-support.md) | `null` / `null` |
| `privacy.erasure_completed` | `SYSTEM` | `PrivacyService.eraseUserData()` (11-data-privacy-compliance.md) | `"member"` / `discordUserId`, `payload: { rowsRedacted: { case, moderationAction, ticket, appeal, auditLogEntry } }` |

\* `ticket.created`'s `actorDiscordId` is the *opening member's* `discordUserId`, not a moderator's — `actorType: MODERATOR` here is a simplification the code should correct to a member-actor distinction only if 07-ticketing-system.md's `ActorType` enum usage says otherwise; per 03-data-model.md's `ActorType` enum (`SYSTEM | BOT | MODERATOR`) there is no fourth "member" value, so a ticket-opening member is recorded as the acting Discord user with `actorType: MODERATOR` regardless of their `PermissionRole` — the enum tracks *who acted* (a real Discord user vs. the bot vs. the system), not their permission level.

**`permission.updated` write detail:** each of `PermissionRolesService`'s `createRole()`/`updateRole()`/`deleteRole()` (above) writes its `AuditLogEntry` in the same Prisma transaction as the `PermissionRole` mutation, with `actorDiscordId` set to `session.discordUserId` from the `permission.edit`-gated request. `payload.before`/`payload.after` are the role's `{ name, discordRoleIds, permissions }` shape pre/post mutation, so `audit_viewer` can render exactly which flags were added or removed without a separate diffing step client-side — the diff is computed once, server-side, at write time.

**Powering `audit_viewer` (08-web-dashboard.md):** the panel's `GET /api/v1/guilds/:guildId/audit-log?eventType=&actorType=&targetType=&before=&after=&cursor=` is a direct, cursor-paginated read of this table (`@@index([guildId, createdAt])`, 03-data-model.md) — no aggregation, no secondary index. The `eventType` filter dropdown is populated client-side from the fixed catalog above (grouped by prefix — `case.*`, `appeal.*`, `ticket.*`, `config.*`, `permission.*`, plus the four standalone system events), so `audit_viewer` never has to discover valid values dynamically. Row rendering resolves `actorDiscordId` to a username via `GuildMember` (falling back to "System"/"Bot" text for `actorType: SYSTEM`/`BOT`, since those rows carry `actorDiscordId: null`) and deep-links `targetType: "case"` rows to `case_detail` (`/dashboard/{guildId}/cases/{targetId}`) and `targetType: "ticket"` rows to the ticket queue view, exactly as 08 already fixes; this file's contribution is only ensuring every writer above actually produces a row with the `targetType`/`targetId` shape 08's link logic expects. Access to the panel itself is gated by `audit.view` (Permission Levels, above) — `Admin` and `Moderator` both hold it by default, so audit history is visible to the same population that can act, not restricted to `Admin` alone, consistent with `rolesAndPermissions.auditLogging` being a transparency feature rather than an admin-only control panel.

`AuditLogEntry` rows are themselves subject to the 90-day retention sweep like every other activity table (03-data-model.md's Retention & Lifecycle Fields, `expiresAt`/`deletedAt`) — full sweep mechanics in 11-data-privacy-compliance.md. This means `audit_viewer`'s history window is bounded at 90 days, matching every other activity surface in the system rather than being a permanent, unbounded log.
