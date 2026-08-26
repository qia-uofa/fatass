# 12 — API Reference

The definitive request/response contract for every `api` route consumed by `web` (08-web-dashboard.md's eight `webPortal.dashboardFeatures` panels) and by `bot` (the case/ticket/appeal/audit-log write paths fixed in 04/05/06/07-*.md). All routes are served by the single Fastify `api` process (02-architecture.md); all schemas below are DTOs over the Prisma models fixed in 03-data-model.md, mirrored into `packages/shared-types/` per 02-architecture.md's workspace layout so `bot`, `api`, and `web` share one type definition per payload rather than three independently-drifting copies. Authorization mechanics referenced throughout (`requireGuildAccess`, `requirePermission`, permission flags) are fixed in full in 09-auth-and-permissions.md and only summarized here per-endpoint; guild-isolation guarantees are fixed in 10-multi-guild-support.md.

## Conventions

- **Base URLs:** public routes (session-authenticated, consumed by `web`) live under `https://api.<domain>/api/v1/*`; internal routes (service-JWT-authenticated, consumed by `bot`, plus one exception consumed by `web`'s server-side OAuth callback) live under `https://api.internal/internal/v1/*` (02-architecture.md). Realtime: `wss://api.<domain>/realtime` (Socket.IO).
- **Content type:** `application/json` for every request/response body; no endpoint in this catalog accepts `multipart/form-data` or query-string-encoded bodies.
- **Timestamps:** ISO 8601 UTC strings (`2026-08-23T04:50:19.586Z`) on the wire; `DateTime` in Prisma.
- **Pagination:** cursor-based on every list route, matching the Prisma index the route queries (03-data-model.md's `@@index` combos). Request: `?limit=<n>&cursor=<opaque>`. Response envelope: `{ items: T[], nextCursor: string | null }`. The opaque cursor encodes the last row's `(createdAt, id)` pair (or `(joinedAt, id)` for `members`), base64'd — never a raw offset, so pages stay stable under concurrent inserts.
- **Guild scoping:** every route under `.../guilds/:guildId/*` (public and internal) takes `guildId` as a URL path segment, never from the request body — this is 10-multi-guild-support.md's Per-Guild Configuration Isolation guarantee applied uniformly, not a per-route choice.
- **Enums on the wire:** `CaseStatus`, `CaseSource`, `ActionType`, `ActionOrigin`, `TicketStatus`, `AppealIngress`, `AppealStatus`, `ActorType` (03-data-model.md) are serialized as their Prisma enum string values (e.g. `"CONFIRMED"`, `"TIMEOUT"`) in every request and response body below.

## Endpoint Catalog

### Session & Guild Switching (`multi_server_switch`)

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds` | List every guild the caller can access, for `GuildSwitcher` (08/10) | none | `200 { guilds: { id: string, name: string, iconUrl: string \| null }[] }` — `GuildsService.listAccessibleGuilds()` result (10-multi-guild-support.md), owner-guilds and role-mapped guilds unioned, `isActive: true` only |
| `PATCH /api/v1/session/active-guild` | Persist the last-viewed guild (`UserSession.activeGuildId`) | `{ guildId: string }` | `204` no body |
| `POST /api/v1/session/logout` | Revoke the Discord OAuth grant and end the session | none (session cookie only) | `204` no body — `UserSession.deletedAt` set immediately (09-auth-and-permissions.md) |
| `POST /internal/v1/sessions` | Called by `web`'s NextAuth `signIn` server callback (not `bot`) to mint a `UserSession` after Discord token exchange | `{ discordUserId: string, discordUsername: string, discordAvatarUrl: string \| null, accessToken: string, refreshToken: string, expiresIn: number }` | `200 { sessionId: string }` |

### `live_log`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/cases` | Historical/paged feed backing `live_log`; live rows arrive over the socket (Realtime section, below) | Query: `limit?: number (default 50), cursor?: string, status?: CaseStatus, source?: CaseSource` | `200 { items: CaseSummary[], nextCursor: string \| null }` — `CaseSummary` per the wire shape below |

```ts
interface CaseSummary {
  id: string; guildId: string; createdAt: string; updatedAt: string;
  source: 'AUTOMOD' | 'MANUAL';
  filterId: string | null;
  targetDiscordUserId: string | null; targetUsername: string | null; targetChannelId: string | null;
  actionTaken: ActionType | null;       // null = nsfw_image queued path, 04-automod-engine.md
  moderatorDiscordId: string | null;
  status: CaseStatus;
}
```

### `case_detail`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/cases/:caseId` | Full case record for the review/action surface | none | `200 CaseDetailResponse` (shape below, 06-case-management-and-appeals.md) |
| `PATCH /api/v1/guilds/:guildId/cases/:caseId` | Confirm or overturn an already-actioned case | `{ status: 'confirmed' \| 'overturned', resolutionNotes?: string }` | `200 { case: CaseSummary }` — on `overturned` with a linked `ModerationAction`, `Case.status` stays `OPEN` until the async `reverse_action` job reports back (06-case-management-and-appeals.md); the response reflects the state immediately after this call, not the eventual reversal |
| `POST /api/v1/guilds/:guildId/cases/:caseId/confirm-action` | Confirm a queued `nsfw_image` case's recommended action | `{ actionType?: ActionType, durationSeconds?: number }` — both optional, default to the live-looked-up `AutomodFilterConfig.nsfwImageConfig.action` | `202 { case: CaseSummary }` — accepted, not yet applied; `bot`'s worker executes it via the `discord-actions` queue (04-automod-engine.md step 4) |
| `POST /api/v1/guilds/:guildId/cases/:caseId/appeals` | Member-initiated appeal, portal ingress | `{ reason: string }` (max 1000 chars) | `201 { appeal: AppealSummary }` — `ingressPath: "PORTAL"` set server-side; `403` if `session.discordUserId !== case.targetDiscordUserId` (06-case-management-and-appeals.md) |
| `GET /api/v1/guilds/:guildId/appeals?status=pending` | Pending-appeals queue view | Query: `status?: AppealStatus` | `200 { items: AppealSummary[] }` — each joined to parent `Case.targetUsername`/`filterId`/`moderationAction.actionType` (06-case-management-and-appeals.md) |
| `PATCH /api/v1/guilds/:guildId/appeals/:appealId` | Uphold or reverse an appeal | `{ decision: 'upheld' \| 'reversed', notes: string }` | `200 { appeal: AppealSummary }` — `404` if missing, `409` if `status !== "PENDING"` (06-case-management-and-appeals.md) |

```ts
interface CaseDetailResponse {
  case: {
    id: string; guildId: string; status: CaseStatus; source: CaseSource; filterId: string | null;
    targetDiscordUserId: string | null; targetUsername: string | null; targetChannelId: string | null;
    evidence: { messageContent?: string; attachmentUrls?: string[]; channelId?: string; messageId?: string };
    resolutionNotes: string | null;
    createdAt: string; updatedAt: string;
  };
  moderationAction: {                      // null for a still-queued nsfw_image case
    actionType: ActionType; performedBy: ActionOrigin; moderatorDiscordId: string | null;
    durationSeconds: number | null; deleteMessageDays: number | null; messageCount: number | null;
    roleIdsRemoved: string[]; reversedAt: string | null; reversedByDiscordId: string | null;
    createdAt: string;
  } | null;
  recommendedAction: { actionType: ActionType; source: 'AutomodFilterConfig.nsfwImageConfig.action' } | null;
  target: {                                 // null for channel-scoped cases (PURGE, LOCKDOWN)
    discordUsername: string; discordAvatarUrl: string | null; roles: string[];
    warnCount: number; isBanned: boolean; joinedAt: string | null;
  } | null;
  appeals: AppealSummary[];
  auditTrail: { eventType: string; actorType: ActorType; actorDiscordId: string | null; payload: unknown; createdAt: string }[];
}

interface AppealSummary {
  id: string; caseId: string; status: AppealStatus; reason: string; ingressPath: AppealIngress;
  submittedByDiscordId: string; decidedByDiscordId: string | null; decisionNotes: string | null;
  createdAt: string; decidedAt: string | null;
}
```

### `analytics_charts`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/analytics` | Full-recompute aggregate load, on mount and on range change | Query: `range: '7d' \| '30d' \| '90d'` (default `7d`) | `200 AnalyticsResponse` (08-web-dashboard.md) |

```ts
interface AnalyticsResponse {
  range: '7d' | '30d' | '90d';
  casesByDay: { date: string; count: number }[];
  casesBySource: Record<'AUTOMOD' | 'MANUAL', number>;
  casesByFilter: Record<string, number>;      // key = filterId, 04-automod-engine.md's eight filters
  casesByStatus: Record<CaseStatus, number>;
  actionsByType: Record<ActionType, number>;
  ticketsByStatus: Record<TicketStatus, number>;
  appealsByOutcome: Record<AppealStatus, number>;
}
```

### `member_mgmt`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/members` | Searchable roster | Query: `search?: string, page?: number (default 1), pageSize?: number (default 25)` | `200 { items: MemberSummary[], total: number }` |
| `GET /api/v1/guilds/:guildId/members/:discordUserId` | Member detail + history | none | `200 MemberDetailResponse` |

```ts
interface MemberSummary {
  discordUserId: string; discordUsername: string; discordAvatarUrl: string | null;
  roles: string[]; warnCount: number; isBanned: boolean; joinedAt: string | null;
}

interface MemberDetailResponse extends MemberSummary {
  cases: CaseSummary[];        // every Case where targetDiscordUserId matches, newest first
  tickets: { id: string; subject: string; status: TicketStatus; createdAt: string; closedAt: string | null }[];
}
```

### `config_editor`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/automod-config` | Current filter config for the eight cards | none | `200 AutomodConfigResponse` |
| `PATCH /api/v1/guilds/:guildId/automod-config` | Partial update, one or more filters at once | `Partial<AutomodConfigWriteBody>` (any subset of `{filter}Enabled`/`{filter}Config` keys) | `200 AutomodConfigResponse` — publishes `automod-config-updated:{guildId}` on Redis Pub/Sub (04-automod-engine.md) so `bot` evicts its cache immediately |

```ts
interface AutomodConfigResponse {
  spamEnabled: boolean;        spamConfig: { maxMessages: number; windowSeconds: number; action: ActionType };
  raidEnabled: boolean;        raidConfig: { joinThreshold: number; windowSeconds: number; action: ActionType };
  linksEnabled: boolean;       linksConfig: { allowlist: string[]; blockInvites: boolean };
  profanityEnabled: boolean;   profanityConfig: { wordlist: 'default' | 'strict'; customWords: string[] };
  nsfwImageEnabled: boolean;   nsfwImageConfig: { confidenceThreshold: number; action: ActionType };
  phishingEnabled: boolean;    phishingConfig: { blocklistSource: 'in-house'; action: ActionType };
  massMentionEnabled: boolean; massMentionConfig: { maxMentions: number; action: ActionType };
  capsEmojiEnabled: boolean;   capsEmojiConfig: { maxCapsRatio: number; maxEmojiCount: number };
  updatedAt: string; updatedByDiscordId: string | null;
}
type AutomodConfigWriteBody = Omit<AutomodConfigResponse, 'updatedAt' | 'updatedByDiscordId'>;
```

### `audit_viewer`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/audit-log` | Filterable system-wide event feed | Query: `eventType?: string, actorType?: ActorType, targetType?: string, before?: string, after?: string, cursor?: string, limit?: number (default 50)` | `200 { items: AuditLogEntrySummary[], nextCursor: string \| null }` |

```ts
interface AuditLogEntrySummary {
  id: string; guildId: string; actorType: ActorType; actorDiscordId: string | null;
  eventType: string;    // full catalog in 09-auth-and-permissions.md's Audit Logging table, plus guild.* from 10-multi-guild-support.md and privacy.erasure_completed from 11-data-privacy-compliance.md
  targetType: string | null; targetId: string | null;
  payload: unknown; createdAt: string;
}
```

### `role_permission_ui`

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/permission-roles` | List all `PermissionRole` rows for the table | none | `200 { items: PermissionRoleSummary[] }` |
| `POST /api/v1/guilds/:guildId/permission-roles` | Create a custom role | `{ name: string, discordRoleIds: string[], permissions: PermissionFlag[] }` | `201 { role: PermissionRoleSummary }` |
| `PATCH /api/v1/guilds/:guildId/permission-roles/:id` | Edit a role (built-in or custom) | `{ name?: string, discordRoleIds?: string[], permissions?: PermissionFlag[] }` | `200 { role: PermissionRoleSummary }` |
| `DELETE /api/v1/guilds/:guildId/permission-roles/:id` | Delete a custom role | none | `204` no body |

```ts
interface PermissionRoleSummary {
  id: string; guildId: string; name: string; isBuiltIn: boolean;
  discordRoleIds: string[]; permissions: PermissionFlag[]; createdAt: string; updatedAt: string;
}
```

### Ticketing queue (supporting read — see note)

`scope.inScope` includes `ticketing`, but `ticketing` is not itself one of `webPortal.dashboardFeatures`' eight named panels (08-web-dashboard.md's Dashboard Feature Inventory). 07-ticketing-system.md nonetheless fixes one read endpoint that feeds a dashboard queue view "structurally identical to `live_log`" — included here for completeness since an implementing agent building the dashboard shell will otherwise have no route for it:

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `GET /api/v1/guilds/:guildId/tickets` | Open-ticket queue view | Query: `status?: TicketStatus, cursor?: string, limit?: number (default 50)` | `200 { items: TicketSummary[], nextCursor: string \| null }` |

```ts
interface TicketSummary {
  id: string; guildId: string; openedByDiscordId: string; channelId: string | null;
  status: TicketStatus; claimedByDiscordId: string | null; subject: string;
  createdAt: string; updatedAt: string; closedAt: string | null;
}
```

Ticket state transitions (`claim`/`resolve`/`close`) have no portal-side write endpoint — per 05-manual-moderation.md's and 07-ticketing-system.md's design, every ticket lifecycle action is triggered exclusively through Discord message components inside the ticket's thread, mirroring `member_mgmt`'s read-only design for manual moderation actions.

### Bot-Facing Internal API

Every route below is called by `bot` (02-architecture.md's `bot → api` path, service JWT `aud: "bot"`) and is how `automod_engine`, `manual_tools`, `case_system`, `ticketing`, and `appeals` writes actually reach Postgres — `bot` never writes to the datastore directly.

| Method & Path | Purpose | Request | Response |
|---|---|---|---|
| `POST /internal/v1/cases` | Create a `Case` (+ `ModerationAction` when action-bearing) | `{ guildId: string, targetUserId?: string, targetChannelId?: string, source: CaseSource, filterId: string \| null, actionTaken: ActionType \| null, evidence: object, moderatorId: string \| null }` | `201 { case: CaseSummary }` — 04-automod-engine.md step 2/3, 05-manual-moderation.md step 5 |
| `POST /internal/v1/cases/:id/events` | Report async job completion back to `api` | `{ type: 'action_confirmed' \| 'action_reversed' \| 'lockdown_lifted' }` | `200 { case: CaseSummary }` — 04-automod-engine.md step 4, 06-case-management-and-appeals.md's Reversal Mechanics, 05-manual-moderation.md's Lifted section |
| `POST /internal/v1/cases/:caseId/appeals` | File an appeal, DM ingress | `{ reason: string, submittedByDiscordId: string }` | `201 { appeal: AppealSummary }` — `ingressPath: "DM"` set server-side (06-case-management-and-appeals.md) |
| `POST /internal/v1/tickets` | Create a `Ticket` | `{ guildId: string, openedByDiscordId: string, channelId: string, subject: string, initialMessage: string }` | `201 { ticket: TicketSummary }` (07-ticketing-system.md) |
| `POST /internal/v1/tickets/:id/claim` | `OPEN → CLAIMED` | `{ claimedByDiscordId: string }` | `200 { ticket: TicketSummary }` — `409` if `status !== "OPEN"` |
| `POST /internal/v1/tickets/:id/resolve` | `CLAIMED → RESOLVED` | `{ resolvedByDiscordId: string }` | `200 { ticket: TicketSummary }` — `409` if `status !== "CLAIMED"` |
| `POST /internal/v1/tickets/:id/close` | `* → CLOSED` | `{ closedByDiscordId: string }` | `200 { ticket: TicketSummary }` — `409` if `status === "CLOSED"` |
| `POST /internal/v1/audit-log` | Write a standalone `AuditLogEntry` with no owning service call | `{ guildId: string, actorType: ActorType, actorDiscordId?: string, eventType: string, targetType?: string, targetId?: string, payload?: object }` | `201 { id: string }` — used for `raid.watch`, `automod.action_failed`, `dm.failed`, `appeal.reversal_failed` (04/05/06-*.md) |
| `GET /internal/v1/guilds/:guildId/automod-config` | Read-through cache source for `bot`'s `AutomodEngine` | none | `200 AutomodConfigResponse` (same shape as the public route) — 04-automod-engine.md's Config Loading |
| `GET /internal/v1/guilds/:guildId/moderators` | Resolve DM recipients for raid Rung-3 escalation | none | `200 { moderators: { discordUserId: string }[] }` — intersects `GuildMember.roles` with `PermissionRole.discordRoleIds` where `permissions` includes `case.resolve` (04-automod-engine.md) |
| `GET /internal/v1/guilds/:guildId/members/:discordUserId/permissions` | Resolve a moderator's flags for `bot`'s permission gate | none | `200 { flags: PermissionFlag[] }` — `getFlags()` (09-auth-and-permissions.md), Redis-cached by `bot` 30s at `modperm:{guildId}:{discordUserId}` |
| `GET /internal/v1/guilds/:guildId/roles` | Validate `discordRoleIds` on `PermissionRole` writes | none | `200 { roles: { id: string, name: string, color: number }[] }` — resolved from `bot`'s `guild.roles.cache` (09-auth-and-permissions.md) |
| `POST /internal/v1/guilds` | Provision or reactivate a guild on install | `{ guildId: string, name: string, iconUrl: string \| null, ownerDiscordId: string }` | `200 { guildId: string, isNewInstall: boolean }` — seeds `AutomodFilterConfig` + `Admin`/`Moderator` `PermissionRole` rows only on true first install (10-multi-guild-support.md) |
| `POST /internal/v1/guilds/:guildId/members/sync` | Batch-upsert `GuildMember` rows | `{ members: { discordUserId: string, discordUsername: string, discordAvatarUrl: string \| null, roles: string[], joinedAt: string \| null }[] }` | `200 { synced: number }` |
| `POST /internal/v1/guilds/:guildId/deactivate` | Mark a guild inactive on bot removal | none | `200 { guildId: string, isActive: false }` — row kept, not deleted (03/10-*.md) |

### Realtime (WebSocket)

One Socket.IO connection per guild-scoped route subtree (`GuildSocketProvider`, 08-web-dashboard.md), authenticated by the same session cookie as `/api/v1/*`, admitted into room `guild:{guildId}` only after `requireGuildAccess` passes on connection (03-data-model.md's Multi-Guild Scoping section).

| Event | Room | Payload | Emitted by |
|---|---|---|---|
| `case.created` | `guild:{guildId}` | `CaseSummary` | `CasesService.createCase()` |
| `case.updated` | `guild:{guildId}` | `CaseSummary & { resolutionNotes: string \| null }` | `CasesService.updateStatus()`, `confirmAction()`, `discordActionsWorker` report-backs |
| `ticket.created` | `guild:{guildId}` | `TicketSummary` | `TicketsService.createTicket()` |
| `ticket.updated` | `guild:{guildId}` | `TicketSummary` | `claimTicket()`/`resolveTicket()`/`closeTicket()` |
| `appeal.filed` / `log.appended` | `guild:{guildId}` | `AppealSummary` | `AppealsService.fileAppeal()` |
| `analytics.updated` | `guild:{guildId}` | `{ guildId: string, metric: keyof AnalyticsResponse, key: string, delta: number }` | every service method above, alongside its primary emit (08-web-dashboard.md) |

## Authentication & Authorization per Endpoint

### Session mechanism (public routes)

Every `/api/v1/*` route runs `api/src/plugins/sessionAuth.ts`'s `sessionAuth` `preHandler` first: verifies the NextAuth JWT (shared `NEXTAUTH_SECRET`) from the `next-auth.session-token` cookie, loads the referenced `UserSession` row, and `401`s if `deletedAt` is set or `expiresAt` has passed; on success it attaches `request.session = { discordUserId, sessionId }` (09-auth-and-permissions.md). `GET /api/v1/guilds`, `PATCH /api/v1/session/active-guild`, and `POST /api/v1/session/logout` require nothing further — they run `sessionAuth` alone.

### Guild access (guild-scoped public routes)

Every `/api/v1/guilds/:guildId/*` route additionally runs `requireGuildAccess` (`api/src/plugins/guildAccess.ts`) immediately after `sessionAuth`: loads the caller's `GuildMember` row for that `:guildId`, resolves their `PermissionRole`s via `discordRoleIds ∩ GuildMember.roles`, and `403`s if no `GuildMember` row exists for the guild (03-data-model.md) — **except** when `session.discordUserId === Guild.ownerDiscordId`, which is admitted unconditionally even before a `GuildMember` row exists (10-multi-guild-support.md's owner-bootstrap gap).

### Permission-flag gate (write routes and most reads)

`requirePermission(flag: PermissionFlag)` (`api/src/plugins/requirePermission.ts`) runs immediately after `requireGuildAccess` wherever a flag is listed below, calling `getFlags(guildId, discordUserId)` and `403`ing if the resolved flag set doesn't have it (09-auth-and-permissions.md). The guild owner bypasses this check too — `getFlags()` returns the full `PERMISSION_FLAGS` set for `discordUserId === Guild.ownerDiscordId` with no `PermissionRole` lookup at all.

| Endpoint | Gate |
|---|---|
| `GET /api/v1/guilds` | `sessionAuth` only |
| `PATCH /api/v1/session/active-guild` | `sessionAuth` only — `guildId` in the body is checked against `listAccessibleGuilds()`, not `requireGuildAccess` (there is no `:guildId` path segment on this route) |
| `POST /api/v1/session/logout` | `sessionAuth` only |
| `GET /api/v1/guilds/:guildId/cases` | `requireGuildAccess` + `case.view` |
| `GET /api/v1/guilds/:guildId/cases/:caseId` | `requireGuildAccess` + (`case.view` **or** `session.discordUserId === case.targetDiscordUserId`) — the ownership bypass is what lets a member with no `PermissionRole` load their own case to see the "Appeal" action (06-case-management-and-appeals.md), mirroring the same bypass already fixed on the appeals-filing route below |
| `PATCH /api/v1/guilds/:guildId/cases/:caseId` | `requireGuildAccess` + `case.resolve` |
| `POST .../cases/:caseId/confirm-action` | `requireGuildAccess` + `case.resolve` |
| `POST .../cases/:caseId/appeals` | `requireGuildAccess` only, **plus** the case-ownership check (`session.discordUserId === case.targetDiscordUserId`, `403` otherwise) — deliberately no `PermissionRole` flag gates a member appealing their own case |
| `GET /api/v1/guilds/:guildId/appeals` | `requireGuildAccess` + `case.view` (no separate `appeal.view` flag exists in the catalog) |
| `PATCH /api/v1/guilds/:guildId/appeals/:appealId` | `requireGuildAccess` + `appeal.decide` |
| `GET /api/v1/guilds/:guildId/analytics` | `requireGuildAccess` + `analytics.view` |
| `GET /api/v1/guilds/:guildId/members` | `requireGuildAccess` + `member.view` |
| `GET /api/v1/guilds/:guildId/members/:discordUserId` | `requireGuildAccess` + `member.view` |
| `GET /api/v1/guilds/:guildId/automod-config` | `requireGuildAccess` + `config.edit` (no separate `config.view` flag exists) |
| `PATCH /api/v1/guilds/:guildId/automod-config` | `requireGuildAccess` + `config.edit` |
| `GET /api/v1/guilds/:guildId/audit-log` | `requireGuildAccess` + `audit.view` |
| `GET/POST/PATCH/DELETE .../permission-roles[/:id]` | `requireGuildAccess` + `permission.edit` on all four (09-auth-and-permissions.md: "All four routes carry `preHandler: [requireGuildAccess, requirePermission('permission.edit')]`") |
| `GET /api/v1/guilds/:guildId/tickets` | `requireGuildAccess` + `ticket.claim` (no separate `ticket.view` flag exists) |

### Internal routes (bot- and web-server-facing)

Every `/internal/v1/*` route (Bot-Facing Internal API table, above) runs `api/src/plugins/internalAuth.ts`'s `internalAuth` `preHandler` instead of `sessionAuth`/`requireGuildAccess`: verifies a signed service JWT with `aud: "bot"` (02-architecture.md), issued out-of-band to the `bot` process at deploy time — there is no per-moderator identity on this path, since these routes represent `bot`'s own write authority (already gated upstream by `hasActionPermission`/`permissionGate.ts` inside `bot` itself, 05-manual-moderation.md). `POST /internal/v1/sessions` is the one exception: it is called by `web`'s server-side NextAuth callback, not `bot`, before any `UserSession` exists to authenticate with — it is instead gated by a shared `INTERNAL_API_SECRET` known only to `web`'s server runtime and `api`, checked via a header (`X-Internal-Secret`) rather than a bot-scoped JWT, since it has no `aud: "bot"` claim to verify.

## Error Cases

Every non-2xx response uses one envelope:

```ts
interface ApiError {
  error: string;        // machine-readable code, stable across versions — see tables below
  message: string;       // human-readable, safe to render directly
  details?: unknown;     // present only on 400 (validation) responses
}
```

### 401 — Unauthorized

Missing, malformed, or expired credential — the request never reaches route logic.

| Cause | `error` | Applies to |
|---|---|---|
| Missing/invalid `next-auth.session-token` cookie, or `sessionAuth` finds no matching `UserSession` | `"unauthorized"` | every `/api/v1/*` route |
| `UserSession.deletedAt` set or `UserSession.expiresAt` passed | `"session_expired"` | every `/api/v1/*` route — `web` redirects to `/login` on receiving this code |
| Missing/invalid service JWT, or `aud` claim isn't `"bot"` | `"unauthorized"` | every `/internal/v1/*` route except `POST /internal/v1/sessions` |
| Missing/invalid `X-Internal-Secret` header | `"unauthorized"` | `POST /internal/v1/sessions` only |

### 403 — Forbidden by permission level

Two distinct sub-cases, since `requireGuildAccess` and `requirePermission` fail for different reasons and `web` renders each differently (10-multi-guild-support.md's `GuildAccessDenied` component vs. an inline permission notice):

| Cause | `error` | Response body detail |
|---|---|---|
| Caller has no `GuildMember` row for `:guildId` (and isn't `Guild.ownerDiscordId`) | `"guild_access_denied"` | `{ error: "guild_access_denied", message: "You don't have access to this server." }` — the guild's existence is never confirmed or denied in the message (10-multi-guild-support.md) |
| Caller has guild access but lacks the required `PermissionFlag` | `"insufficient_permission"` | `{ error: "insufficient_permission", message: "...", details: { requiredFlag: PermissionFlag } }` |
| Member attempts to appeal a case that isn't their own | `"insufficient_permission"` | `{ error: "insufficient_permission", message: "You can only appeal your own case." }` — same code as the flag case, since it's the same class of "not authorized for this specific write" (06-case-management-and-appeals.md) |

### 404 — Not Found

Applies uniformly to every path-parameterized resource once `requireGuildAccess`/`requirePermission` have already passed — a `404` here means the guild is real and the caller has standing in it, but the nested resource doesn't exist (or belongs to a different guild, which resolves identically to not existing per 10-multi-guild-support.md's write-scoping guarantee):

| Cause | `error` | `details.resource` |
|---|---|---|
| `:caseId` not found (or belongs to another `guildId`) | `"not_found"` | `"case"` |
| `:ticketId` (`:id` on ticket routes) not found | `"not_found"` | `"ticket"` |
| `:appealId` not found | `"not_found"` | `"appeal"` |
| `:id` on `permission-roles` not found (or belongs to another guild) | `"not_found"` | `"permission_role"` |
| `:discordUserId` has no `GuildMember` row in this guild | `"not_found"` | `"member"` |
| `:guildId` itself doesn't resolve to an active `Guild` row | `"not_found"` | `"guild"` — only reachable on internal routes, since `requireGuildAccess` already intercepts this case on public routes with a `403 guild_access_denied` before a `404` would ever be evaluated |

### 409 — State Conflict

Every status-transition endpoint in this catalog enforces a fixed state machine (06/07-*.md) and rejects a call that doesn't match the resource's current state, rather than silently no-oping or overwriting:

| Cause | `error` | Endpoint(s) |
|---|---|---|
| `Case.status !== "OPEN"` on a confirm/overturn attempt already resolved another way | `"invalid_state_transition"` | `PATCH .../cases/:caseId`, `POST .../confirm-action` |
| Case is `OVERTURNED`/`RESOLVED`, or `moderationAction` is null and was never confirmed | `"not_appealable"` | `POST .../cases/:caseId/appeals`, `POST /internal/v1/cases/:caseId/appeals` |
| An `Appeal` with `status: "PENDING"` already exists for this case | `"appeal_already_pending"` | both appeal-filing routes above |
| `Appeal.status !== "PENDING"` on a resolution attempt (already decided, or a concurrent decision won the race) | `"invalid_state_transition"` | `PATCH .../appeals/:appealId` |
| `Ticket.status !== "OPEN"` on claim | `"invalid_state_transition"` | `POST /internal/v1/tickets/:id/claim` |
| `Ticket.status !== "CLAIMED"` on resolve | `"invalid_state_transition"` | `POST /internal/v1/tickets/:id/resolve` |
| `Ticket.status === "CLOSED"` on close | `"invalid_state_transition"` | `POST /internal/v1/tickets/:id/close` |
| `PermissionRole` name already used in this guild | `"duplicate_name"` | `POST .../permission-roles` |
| Rename attempted on an `isBuiltIn: true` role | `"builtin_immutable"` | `PATCH .../permission-roles/:id` |
| Delete attempted on an `isBuiltIn: true` role | `"builtin_immutable"` | `DELETE .../permission-roles/:id` |

### 400 — Validation Failure

Fastify's typebox route schemas (`@fastify/type-provider-typebox`, 02-architecture.md) reject malformed bodies before any handler or `PermissionsService` call runs; `details` carries the schema validator's field-level errors:

| Cause | `error` | Endpoint(s) |
|---|---|---|
| `permissions[]` contains a value outside `PERMISSION_FLAGS` | `"validation_failed"` | `POST`/`PATCH .../permission-roles[/:id]` (09-auth-and-permissions.md) |
| `discordRoleIds[]` contains an ID not present in this guild's `bot`-cached role list | `"invalid_discord_role"` | `POST`/`PATCH .../permission-roles[/:id]` — distinct code from generic `validation_failed` since it requires the `GET /internal/v1/guilds/:guildId/roles` round-trip rather than pure schema validation |
| `name` outside 1–50 chars | `"validation_failed"` | `POST`/`PATCH .../permission-roles[/:id]` |
| `reason` missing or exceeds the field's max length (500 chars for moderation-action modals, 1000 for appeals) | `"validation_failed"` | `POST .../cases/:caseId/appeals`, `POST /internal/v1/cases/:caseId/appeals`, `POST /internal/v1/cases` |
| `status`/`decision`/enum-typed body field outside its Prisma enum's values | `"validation_failed"` | any `PATCH` accepting an enum field |
| `range` query param outside `'7d' \| '30d' \| '90d'` | `"validation_failed"` | `GET .../analytics` |
| `[filter]Config` payload shape doesn't match that filter's schema (03-data-model.md/04-automod-engine.md per-filter config shapes) | `"validation_failed"` | `PATCH .../automod-config` |

### 429 — Rate Limiting

`spec.json` specifies no rate-limiting policy; the concrete scheme below closes that gap using `@fastify/rate-limit` backed by the same shared Redis instance 02-architecture.md's Technology Stack table already provisions (no fourth Redis responsibility beyond the three already listed — this is a variant of the existing counter usage). Every limited response carries a `Retry-After` header (seconds) and the standard error envelope with `error: "rate_limited"`:

```json
{ "error": "rate_limited", "message": "Too many requests, try again shortly.", "details": { "retryAfterSeconds": 12 } }
```

| Scope | Key | Limit | Applies to |
|---|---|---|---|
| Default, session-authenticated | `discordUserId` | 100 requests / 60s | every `/api/v1/*` route not listed below |
| Write-heavy / state-changing | `discordUserId` | 20 requests / 60s | `PATCH`/`POST`/`DELETE` on `cases`, `appeals`, `automod-config`, `permission-roles` |
| Unauthenticated (pre-session) | IP address | 10 requests / 60s | `POST /api/v1/session/logout`, the NextAuth OAuth callback route |
| Internal (service JWT / shared secret) | fixed key per caller (`"bot"` or `"web-server"`) | 600 requests / 60s | every `/internal/v1/*` route — high headroom since `bot` is a single trusted process (02-architecture.md's single-instance deployment), not a per-user multiplier; still capped so a `bot` retry storm (e.g. during a Discord outage) can't overwhelm `api`'s 2 replicas |

Rate-limit state lives in Redis keyed `ratelimit:{scope}:{key}`, TTL 60s, incremented via `INCR`/`EXPIRE` — the same sliding-window primitive 04-automod-engine.md's filter counters already use, applied here to inbound `api` traffic instead of Discord message/join events.
