# 08 — Web Dashboard

Implements `scope.inScope: web_dashboard` — every entry in `webPortal.dashboardFeatures` (`live_log`, `analytics_charts`, `member_mgmt`, `config_editor`, `audit_viewer`, `multi_server_switch`, `case_detail`, `role_permission_ui`), `webPortal.mobileResponsive: true`, and `webPortal.realtimeUpdates: true`. Runs entirely in the `web` process (02-architecture.md's component split — Next.js 14 App Router + Tailwind CSS), talking only to `api`'s `/api/v1/*` REST routes and its `wss://api.<domain>/realtime` Socket.IO endpoint; `web` never calls `bot` or the datastore directly. Every route below lives under `web/src/app/dashboard/[guildId]/...`, so guild scoping is structural in the URL, matching 03-data-model.md's Multi-Guild Scoping section and 10-multi-guild-support.md. Auth (session cookie, per-route permission-flag gating referenced per feature below) is specified in full in 09-auth-and-permissions.md; this file assumes a valid session and states only which flag gates which page.

## Dashboard Feature Inventory

### live_log

**Purpose:** the passive, always-open "front page" — a reverse-chronological feed of every `Case` as it's created or updated, so a moderator watching the dashboard sees automod and manual activity as it happens without navigating anywhere.

**Route:** `web/src/app/dashboard/[guildId]/live-log/page.tsx`.

**On-screen data:** one row per `Case`: relative timestamp (`createdAt`), a source badge (`AUTOMOD`/`MANUAL`), a label built from `filterId` (automod) or `actionTaken` (manual/confirmed), the target (`targetUsername` + avatar, or `targetChannelId` resolved to a channel name for `PURGE`/`LOCKDOWN` rows), `moderatorDiscordId` resolved to a username when set, and a status pill (`CaseStatus`). Clicking a row does a client-side route push to `case_detail` (`/dashboard/{guildId}/cases/{caseId}`) — no reload, since both routes live under the same App Router segment.

**Backend entity (read-only):** `Case` (03-data-model.md) is the primary read, joined to `ModerationAction` for the `actionTaken` label. Initial/historical load is `GET /api/v1/guilds/:guildId/cases?limit=50&cursor=&status=&source=`, cursor-paginated on `Case`'s `@@index([guildId, createdAt])`; the cursor is the last row's `(createdAt, id)` pair. Live rows arrive over the socket per Realtime Update Mechanism, below — this panel issues no polling.

### analytics_charts

**Purpose:** the aggregate view of moderation volume and outcomes — the operational-health counterpart to `live_log`'s per-event feed, covering every entity this system produces: automod triggers, manual actions, tickets, and appeals.

**Route:** `web/src/app/dashboard/[guildId]/analytics/page.tsx`.

**On-screen data:** a range selector (`7d` / `30d` / `90d`, default `7d`), then: a full-width time-series line chart of `casesByDay`; a two-segment bar/donut of `casesBySource` (`AUTOMOD` vs `MANUAL`); an eight-segment breakdown of `casesByFilter` matching `automatedModeration.filters`' order in 04-automod-engine.md; a `casesByStatus` bar chart, one segment per `CaseStatus` value (03-data-model.md); an eight-segment breakdown of `actionsByType` matching `manualModerationAndCases.manualActions`' order in 05-manual-moderation.md; a four-segment `ticketsByStatus` chart (`TicketStatus`); a three-segment `appealsByOutcome` chart (`PENDING`/`UPHELD`/`REVERSED`).

**Backend entity (read-only):** `Case`, `ModerationAction`, `Ticket`, `Appeal` — all aggregated, never written from this panel. `GET /api/v1/guilds/:guildId/analytics?range=7d|30d|90d` (`api/src/modules/analytics/analytics.controller.ts`) runs Prisma `groupBy` queries (`guildId`, `createdAt >= now() - range`, `deletedAt: null`) and returns:

```ts
interface AnalyticsResponse {
  range: '7d' | '30d' | '90d';
  casesByDay: { date: string; count: number }[];           // ISO date, UTC day bucket
  casesBySource: Record<'AUTOMOD' | 'MANUAL', number>;
  casesByFilter: Record<string, number>;                     // key = FilterResult['filterId'], 04-automod-engine.md
  casesByStatus: Record<CaseStatus, number>;
  actionsByType: Record<ActionType, number>;
  ticketsByStatus: Record<TicketStatus, number>;
  appealsByOutcome: Record<AppealStatus, number>;
}
```

This is the authoritative, full-recompute path on mount and on range change; the socket-pushed `analytics.updated` deltas (Realtime Update Mechanism, below) only patch the chart state this response already populated, they never replace it.

### member_mgmt

**Purpose:** a searchable roster of the guild's members with moderation-relevant context — the entry point for pulling up "everything about this person" (roles, warn history, ban state, case/ticket history) without leaving the dashboard.

**Routes:** list `web/src/app/dashboard/[guildId]/members/page.tsx`; detail `web/src/app/dashboard/[guildId]/members/[discordUserId]/page.tsx`.

**On-screen data:** list — sortable/searchable table (search on `discordUsername`): avatar, username, role chips (`roles`), `warnCount`, an `isBanned` badge, `joinedAt`. Detail — the same member fields plus a case-history list (every `Case` where `targetDiscordUserId` matches, newest first, each linking to `case_detail`) and a ticket-history list (every `Ticket` where `openedByDiscordId` matches).

**Backend entity:** `GuildMember` (read-only — `discordUsername`/`discordAvatarUrl`/`roles` are gateway-synced snapshots per 03-data-model.md, not editable from this panel), plus `Case` and `Ticket` (read-only joins for history). `GET /api/v1/guilds/:guildId/members?search=&page=&pageSize=`; `GET /api/v1/guilds/:guildId/members/:discordUserId` returns the `GuildMember` row joined to its case/ticket history, mirroring `case_detail`'s `target` resolution in 06-case-management-and-appeals.md.

No manual-action buttons live on this panel: per 05-manual-moderation.md, all eight `manualModerationAndCases.manualActions` are triggered exclusively through Discord-native message components and DMs, never the portal. A moderator who wants to act on a member does so from Discord's Moderation Console or from a specific `Case` via `case_detail`'s confirm/overturn actions — `member_mgmt` is read/investigate-only by design, not an omission.

### config_editor

**Purpose:** the UI for `AutomodFilterConfig` (03-data-model.md) — per-guild tuning of the eight automod filters defined in 04-automod-engine.md's Filter Catalog.

**Route:** `web/src/app/dashboard/[guildId]/config/page.tsx`.

**On-screen data:** one card per filter, in the same order as 04-automod-engine.md's evaluation table (`phishing`, `nsfw_image`, `mass_mention`, `spam`, `links`, `caps_emoji`, `profanity`, plus `raid` separately since it's join-triggered not message-triggered) — each card has an enabled toggle (`{filter}Enabled`) and a form for that filter's `{filter}Config` fields: numeric inputs for `maxMessages`/`windowSeconds`/`joinThreshold`/`confidenceThreshold`/`maxMentions`/`maxCapsRatio`/`maxEmojiCount`, a tag-input for `linksConfig.allowlist` and `profanityConfig.customWords`, a wordlist select (`default`/`strict`) for `profanityConfig.wordlist`, and, on every one of the eight cards, an `ActionType` select wherever 04's Automod-to-Action Pipeline table marks that filter's action as guild-configurable (at least `spam`, `raid`, `nsfw_image`, `mass_mention`) — filters 04 fixes with no configurable action (at least `links`, `profanity`, `caps_emoji`) render that fixed `WARN`(+delete) action as read-only text instead; `phishing`'s card follows whichever of the two treatments 04's table assigns it, since this file fixes only the per-filter form layout, not the pipeline's configurability assignment.

**Backend entity (read + write — the only panel in this inventory with a dedicated config write path, as opposed to status-transition endpoints):** `AutomodFilterConfig`. `GET /api/v1/guilds/:guildId/automod-config` (already named in 04-automod-engine.md's Config Loading section); `PATCH /api/v1/guilds/:guildId/automod-config { [filter]Enabled?, [filter]Config? }` — partial update, gated by the `config.edit` permission flag (09-auth-and-permissions.md), sets `updatedByDiscordId` to the editing moderator's `discordUserId`, and publishes on Redis Pub/Sub channel `automod-config-updated:{guildId}` (04-automod-engine.md) so `bot` evicts its cached copy and picks up the change on the next message/join rather than waiting out the 60s TTL.

### audit_viewer

**Purpose:** the read surface for `rolesAndPermissions.auditLogging: true` — a single filterable feed of every state-changing event system-wide (case lifecycle, appeal decisions, config edits, permission edits, ticket lifecycle), so history never has to be reconstructed from other tables (03-data-model.md's `AuditLogEntry` rationale).

**Route:** `web/src/app/dashboard/[guildId]/audit-log/page.tsx`.

**On-screen data:** a filter bar (`eventType`, `actorType`, `targetType`, date range) above a table: timestamp, actor (`actorDiscordId` resolved to a username via `GuildMember`, or "System"/"Bot" when `actorType` is `SYSTEM`/`BOT`), an `eventType` badge (catalog spans 04/05/06/07's `case.*`/`appeal.*`/`ticket.*`/`raid.watch`/`dm.failed`/`automod.action_failed` events plus this file's `config.updated`, 09-auth-and-permissions.md's `permission.updated`, 10-multi-guild-support.md's `guild.*` group, and 11-data-privacy-compliance.md's `privacy.erasure_completed`), a target link (deep-links to `case_detail` when `targetType === "case"`, the member detail route when `targetType === "member"`, etc.), and an expandable inline payload viewer for the `payload` JSON.

**Backend entity (read-only):** `AuditLogEntry`. `GET /api/v1/guilds/:guildId/audit-log?eventType=&actorType=&targetType=&before=&after=&cursor=`, cursor-paginated on `@@index([guildId, createdAt])`.

### multi_server_switch

**Purpose:** lets a moderator who holds access to more than one guild move between dashboards without re-authenticating — the UI expression of `UserSession` being deliberately not guild-scoped (03-data-model.md) and the mechanism 10-multi-guild-support.md builds on.

**Location:** not a standalone page — a persistent element in the dashboard shell, `web/src/app/dashboard/layout.tsx`, rendering a `GuildSwitcher` component (`web/src/components/GuildSwitcher.tsx`) present on every route under `[guildId]`.

**On-screen data:** a list of every guild the session has access to (icon, name), current guild highlighted; selecting one navigates to `/dashboard/{newGuildId}/{same-subpath}` — switching guilds while on `live_log` stays on `live_log` for the new guild, since the subpath is preserved and only the `[guildId]` segment changes.

**Backend entity:** `Guild` and `GuildMember` (read — `GET /api/v1/guilds` resolves every `Guild` row with a `GuildMember` row matching `session.discordUserId`, i.e. `guildMember.findMany({ where: { discordUserId: session.discordUserId } })` joined to `Guild`); `UserSession.activeGuildId` (write — `PATCH /api/v1/session/active-guild { guildId }` persists the choice so the next login/SSR page load defaults to the last-viewed guild instead of forcing a fresh pick every session).

### case_detail

**Purpose:** the single-case review/action surface. Its data contract and every write endpoint are already fully specified in 06-case-management-and-appeals.md (`GET /api/v1/guilds/:guildId/cases/:caseId`'s response shape, `confirm-action`, status-transition `PATCH`, appeal-resolution `PATCH`); this entry exists so the Dashboard Feature Inventory is complete and adds only the routing/composition detail 06 doesn't cover.

**Route:** `web/src/app/dashboard/[guildId]/cases/[caseId]/page.tsx` — the exact deep-link target 04-automod-engine.md's Rung-3 raid moderator DM and every `live_log` row already point to (`https://web.<domain>/dashboard/{guildId}/cases/{caseId}`).

**On-screen data:** four regions matching 06's response shape one-to-one: action summary (`case` + `moderationAction`/`recommendedAction`, with Confirm/Overturn buttons wired to `POST .../confirm-action` and `PATCH .../cases/:caseId`), member/channel context (`target`), an appeals sub-panel (`appeals`, rendering `PENDING` entries with Uphold/Reverse forms per 06's Reviewer states, `PATCH .../appeals/:appealId` on submit), and a history timeline (`auditTrail`).

**Backend entity:** `Case`, `ModerationAction`, `Appeal`, `AuditLogEntry`, `GuildMember` — reads via 06's single `GET`; writes via 06's endpoints listed above. Also subscribes to `case.updated` filtered to `event.id === caseId` (Realtime Update Mechanism, below, applies here as well as to `live_log`/`analytics_charts`).

### role_permission_ui

**Purpose:** the UI for `rolesAndPermissions.customPermissionBuilder: true` — CRUD over `PermissionRole` rows and their Discord-role/permission-flag mappings. 03-data-model.md fixes storage only; the full flag catalog and evaluation logic are in 09-auth-and-permissions.md.

**Route:** `web/src/app/dashboard/[guildId]/permissions/page.tsx`.

**On-screen data:** a table of `PermissionRole` rows — name, an `isBuiltIn` badge for the two seeded rows (`Admin`, `Moderator`), mapped Discord-role chips (`discordRoleIds`, resolved to role names/colors via `bot`'s cached role list), and a permission-flag checklist (e.g. `case.view`, `case.resolve`, `config.edit`, `ticket.claim`, `appeal.decide`, `permission.edit` — full catalog in 09-auth-and-permissions.md). "New Role" opens a form (name, Discord-role multi-select, permission-flag checkbox grid). Built-in rows' `discordRoleIds`/`permissions` remain editable but the row itself can't be deleted or renamed (`isBuiltIn: true` guards delete/rename per 03-data-model.md's seeding note).

**Backend entity (read + write):** `PermissionRole`. `GET /api/v1/guilds/:guildId/permission-roles`; `POST /api/v1/guilds/:guildId/permission-roles { name, discordRoleIds, permissions }`; `PATCH /api/v1/guilds/:guildId/permission-roles/:id { name?, discordRoleIds?, permissions? }`; `DELETE /api/v1/guilds/:guildId/permission-roles/:id` (404 if missing, 409 if `isBuiltIn`). All four gated by the `permission.edit` flag — editing permissions is self-gated by the same flag system it manages, full rule in 09-auth-and-permissions.md.

## Mobile Responsiveness

`webPortal.mobileResponsive: true` and `scope.launchPlatforms` includes `mobile_web` — there is no separate native app or mobile codebase; Tailwind CSS's responsive utility classes (02-architecture.md's Technology Stack) carry the whole requirement on the one Next.js codebase. Breakpoints are Tailwind's defaults, used consistently across every feature below: `sm 640px`, `md 768px`, `lg 1024px`, `xl 1280px`. The dashboard is built mobile-first — base (unprefixed) classes target `<768px` ("mobile"), `md:`-prefixed classes target 768–1024px ("tablet"), `lg:`/`xl:`-prefixed classes target `≥1024px` ("desktop").

**Shell (`web/src/app/dashboard/layout.tsx`):** the persistent left sidebar nav (links to all eight features plus the `GuildSwitcher` header) renders at `lg:` and above (`hidden lg:flex lg:w-64 lg:flex-col`). Below `1024px`, eight nav destinations don't fit a bottom tab bar, so it collapses to a hamburger-triggered slide-over drawer instead (`Sheet` component, trigger visible only `lg:hidden`).

| Feature | `<768px` (mobile) | `768–1024px` (tablet) | `≥1024px` (desktop) |
|---|---|---|---|
| `live_log` | Table becomes a stacked single-column card list (`grid grid-cols-1 gap-2`); each card shows timestamp, status pill, and target only, with filter/action detail collapsed behind a tap-to-expand accordion (no hover tooltip on touch). | 2-column card grid. | Full table, all columns visible, no collapsing. |
| `analytics_charts` | Chart grid stacks to one column (`grid-cols-1`), each chart full-width; `casesByFilter`/`actionsByType` switch from side-by-side bars to a vertically scrollable horizontal-bar list so labels aren't truncated. | 2-column chart grid. | 3-column grid — the `casesByDay` time series spans the full width on its own row, the six breakdown charts fill the columns below it. |
| `member_mgmt` | Table replaced by a stacked card list (avatar, username, badges); search bar is `sticky top-0`; tapping a card is a full-page navigation to the detail route (no room for a side panel). | Data table with sortable columns; detail opens as a right-side drawer at `md:` and above instead of full navigation. | Same as tablet, wider drawer. |
| `config_editor` | The 8 filter cards render as a single-column accordion, one filter expanded at a time, to avoid scrolling past eight fully-expanded forms. | 2-column card grid, all cards expanded. | 2–3 column grid depending on viewport width. |
| `audit_viewer` | Table becomes a stacked list; the filter bar collapses into a single "Filters" sheet trigger; tapping a row opens the payload JSON viewer full-screen (a JSON tree can't render legibly inline at this width). | Inline filter bar returns; payload still opens in a slide-over rather than inline. | Inline filter bar + inline expandable rows, no modal. |
| `multi_server_switch` | `GuildSwitcher` becomes a full-width control in the mobile top app bar; tapping it opens a bottom sheet listing guilds. | Same as mobile. | Dropdown anchored in the sidebar header. |
| `case_detail` | The four regions (action summary, member context, appeals, history) stack vertically in fixed order (action summary first, history last); appeals and history collapse into tabs to shorten the single-column scroll. | Same stacked order, no tabs — enough vertical room. | 2-column grid, `lg:grid-cols-[2fr_1fr]` — action summary + appeals in the main column, member context + history in a sidebar column. |
| `role_permission_ui` | The role×flag matrix doesn't fit — degrades to a list of roles; tapping one opens a full-page edit form showing that role's flags as a vertical checklist instead of a grid column. | Same list/detail split as mobile. | Full matrix table, roles as rows, flags as columns. |

## Realtime Update Mechanism

`webPortal.realtimeUpdates: true`. Transport is Socket.IO, per 02-architecture.md's Technology Stack table: the server half runs in `api` with the Socket.IO Redis adapter (so events reach every connected client regardless of which of `api`'s 2 replicas holds the socket), the client half connects from `web` at `wss://api.<domain>/realtime`. Every socket joins exactly one room, `guild:{guildId}`, and only after the server's `requireGuildAccess` check passes on connection (03-data-model.md's Multi-Guild Scoping section) — so a client can never receive another guild's events even transiently.

**Connection lifecycle:** one socket per guild-scoped route subtree, not one per panel. `web/src/lib/socket-provider.tsx`'s `GuildSocketProvider` (mounted in `web/src/app/dashboard/[guildId]/layout.tsx`) opens the connection once per `guildId` (memoized on that param, torn down via `socket.disconnect()` in a `useEffect` cleanup on unmount or guild switch), so every panel open under that guild — `live_log`, `analytics_charts`, `case_detail`, etc. — shares one connection via React context rather than each opening its own. Reconnection uses Socket.IO's built-in exponential backoff (02-architecture.md's rationale for choosing it). Because events emitted while a client is disconnected are not queued or replayed to it, both hooks below re-issue their initiating `GET` on the socket's `connect` event — not just on first mount — so a reconnect after a network blip resynchronizes state instead of trusting a delta stream with a gap.

**Event catalog relevant to this file** (full catalog, including `ticket.*`, spans 02/04/06/07-*.md):

```ts
interface CaseCreatedEvent {   // event: "case.created", room: guild:{guildId}
  id: string; guildId: string; createdAt: string;           // ISO 8601
  source: 'AUTOMOD' | 'MANUAL';
  filterId: string | null;
  targetDiscordUserId: string | null; targetUsername: string | null; targetChannelId: string | null;
  actionTaken: ActionType | null;                            // null = nsfw_image queued path, 04-automod-engine.md step 3
  moderatorDiscordId: string | null;
  status: CaseStatus;
}

interface CaseUpdatedEvent extends CaseCreatedEvent {         // event: "case.updated", room: guild:{guildId}
  updatedAt: string;
  resolutionNotes: string | null;
}

interface AnalyticsUpdatedEvent {                              // event: "analytics.updated", room: guild:{guildId}
  guildId: string;
  metric: 'casesBySource' | 'casesByFilter' | 'casesByStatus' | 'casesByDay'
        | 'actionsByType' | 'ticketsByStatus' | 'appealsByOutcome';
  key: string;    // e.g. "AUTOMOD", "spam", "OPEN", "2026-08-23"
  delta: number;  // always +1 or -1
}
```

`CaseCreatedEvent`/`CaseUpdatedEvent` are emitted at the exact points 02-architecture.md/06-case-management-and-appeals.md already fix (`CasesService.createCase()`, `updateStatus()`, `confirmAction()`, the `discordActionsWorker`'s report-back calls) — this file only fixes the wire payload shape consumed client-side, trimmed to what a feed row or case-detail patch needs so no follow-up `GET` is required per event. `AnalyticsUpdatedEvent` is emitted by the same service methods, one extra `socket.to('guild:'+guildId).emit('analytics.updated', ...)` call alongside their existing `case.created`/`case.updated`/`ticket.created`/`ticket.updated`/`appeal.filed`/`appeal.resolved` emit, computed directly from the row the service just wrote (e.g. `createCase()` knows `source`/`filterId` without a lookup) — 02-architecture.md's end-to-end trace describes this as `api` "updates that guild's running analytics counters" in the same step it emits `case.created`; this file resolves that running-counter store as **client-side only** (the reducer below), not a new server-side persistence layer, so it doesn't add a fourth Redis responsibility beyond the three 02-architecture.md's Technology Stack table already enumerates. Postgres (via the `GET /analytics` endpoint) remains the sole source of truth; the deltas only keep an already-rendered chart current between full reloads.

**`live_log` consumption** (`web/src/app/dashboard/[guildId]/live-log/useLiveLogFeed.ts`):

1. On mount (and on socket `connect`), fetch `GET /api/v1/guilds/:guildId/cases?limit=50` into local state.
2. Subscribe to `case.created` — prepend the event payload directly as a new row (no follow-up fetch).
3. Subscribe to `case.updated` — patch the row matching `event.id` in place (updates `status`/`resolutionNotes`/`updatedAt`); if the row has scrolled out of the loaded page, the update is dropped (it'll be picked up correctly on next full reload).

**`analytics_charts` consumption** (`web/src/app/dashboard/[guildId]/analytics/useAnalyticsRealtime.ts`):

1. On mount (and on socket `connect`, and on range-selector change), fetch `GET /api/v1/guilds/:guildId/analytics?range=` into local state (the shape in Dashboard Feature Inventory, above).
2. Subscribe to `analytics.updated` — apply each event through a pure reducer, `reduceAnalyticsEvent(state, event)`: `state[event.metric][event.key] += event.delta`, creating the key if absent (e.g. a new `casesByDay` bucket when the day rolls over while the page is open). This patches the chart in place with no re-aggregation query, keeping the live update cost at O(1) per event regardless of guild data volume.
