# 03 — Data Model

Canonical schema lives at `api/prisma/schema.prisma` (Prisma + PostgreSQL, per 02-architecture.md — `api` is the sole DB client; `bot` and `web` never see this schema directly, only the DTOs mirrored into `packages/shared-types/` for use across the pnpm workspace). Every model below is one Prisma `model` block in that file. Enum blocks are listed once and reused across models rather than repeated per-field.

```prisma
enum CaseSource      { AUTOMOD MANUAL }
enum CaseStatus      { OPEN CONFIRMED OVERTURNED APPEALED RESOLVED }
enum ActionType       { KICK SOFTBAN BAN TIMEOUT WARN PURGE ROLE_STRIP LOCKDOWN }
enum ActionOrigin     { AUTOMOD MODERATOR }
enum TicketStatus     { OPEN CLAIMED RESOLVED CLOSED }
enum AppealIngress    { DM PORTAL }
enum AppealStatus     { PENDING UPHELD REVERSED }
enum ActorType        { SYSTEM BOT MODERATOR }
```

## Core Entity Schemas

### Guild

Root tenant entity. Every other model below scopes to it (see Multi-Guild Scoping).

```prisma
model Guild {
  id             String   @id                  // Discord guild snowflake, used directly as PK — no surrogate key, Discord IDs are already globally unique
  name           String                          // cached display name, refreshed on guildUpdate gateway events
  iconUrl        String?
  ownerDiscordId String                          // raw PII — Discord user ID of the guild owner
  isActive       Boolean  @default(true)         // false once the bot is removed from the guild; row is kept (not hard-deleted) so Case/AuditLogEntry rows keep a valid FK until 11-data-privacy-compliance.md's guild-teardown purge runs
  modConsoleChannelId String?                    // #mod-actions channel id, set by ensureConsole() (05-manual-moderation.md); null until first provisioned
  modConsoleMessageId String?                    // pinned moderation-console message id, re-pinned idempotently by ensureConsole() if deleted (05-manual-moderation.md)
  createdAt      DateTime @default(now())        // = install time
  updatedAt      DateTime @updatedAt
}
```

### GuildMember

Per-guild membership record — a Discord user has one row per guild they're in, not one global row, because roles/warn history/ban status are all guild-local.

```prisma
model GuildMember {
  id               String   @id @default(cuid())
  guildId          String
  discordUserId    String                        // raw PII
  discordUsername  String                        // raw PII, cached snapshot, refreshed on guildMemberUpdate
  discordAvatarUrl String?
  roles            String[]                       // cached Discord role IDs, refreshed on relevant gateway events (04-automod-engine.md and 09-auth-and-permissions.md both read this cache instead of hitting Discord's REST API per request)
  joinedAt         DateTime?
  warnCount        Int      @default(0)           // denormalized counter surfaced read-only in member_mgmt/case_detail (08-web-dashboard.md); reconciled from ModerationAction rows where actionType = WARN on drift, not the source of truth
  isBanned         Boolean  @default(false)
  createdAt        DateTime @default(now())
  updatedAt        DateTime @updatedAt

  @@unique([guildId, discordUserId])
  @@index([guildId])
}
```

### ModerationAction (Infraction/Action record)

One table, discriminated by `actionType`, covers all eight `manualModerationAndCases.manualActions` values — automated and manual actions share this shape because `bot/src/moderation/actions.ts`'s `ModerationActions` module (02-architecture.md) is the single execution path for both. `caseId` is a 1:1 back-reference: every `ModerationAction` wraps exactly one `Case`.

```prisma
model ModerationAction {
  id                  String       @id @default(cuid())
  guildId             String
  caseId              String       @unique          // FK Case.id
  actionType          ActionType
  performedBy         ActionOrigin
  targetDiscordUserId String?                        // raw PII; null for PURGE and LOCKDOWN (channel-scoped, no single target)
  targetChannelId     String?                         // set for PURGE, LOCKDOWN
  moderatorDiscordId  String?                         // raw PII; null when performedBy = AUTOMOD
  reason              String?                         // raw PII: freeform text, may quote message content
  durationSeconds     Int?                            // TIMEOUT, temp BAN, LOCKDOWN auto-lift
  deleteMessageDays   Int?                            // SOFTBAN, BAN — Discord's 0-7 day purge-on-ban window
  messageCount        Int?                            // PURGE — number of messages removed
  roleIdsRemoved      String[]                        // ROLE_STRIP — role IDs stripped
  reversedAt          DateTime?                       // set when an appeal reverses the action (06-case-management-and-appeals.md step 10)
  reversedByDiscordId String?                         // raw PII
  createdAt           DateTime     @default(now())
  expiresAt           DateTime                        // retention window, see Retention & Lifecycle Fields
  deletedAt           DateTime?

  @@index([guildId])
  @@index([guildId, targetDiscordUserId])
}
```

Type-specific field usage (fields not listed for a type stay `null`):

| `actionType` | Fields populated beyond the base set |
|---|---|
| `KICK` | `targetDiscordUserId`, `reason` |
| `SOFTBAN` | `targetDiscordUserId`, `reason`, `deleteMessageDays` |
| `BAN` | `targetDiscordUserId`, `reason`, `deleteMessageDays`, `durationSeconds` (null = permanent, set = temp-ban) |
| `TIMEOUT` | `targetDiscordUserId`, `reason`, `durationSeconds` (Discord caps this at 28 days) |
| `WARN` | `targetDiscordUserId`, `reason` |
| `PURGE` | `targetChannelId`, `messageCount`, `reason` |
| `ROLE_STRIP` | `targetDiscordUserId`, `reason`, `roleIdsRemoved` |
| `LOCKDOWN` | `targetChannelId`, `reason`, `durationSeconds` (null = manual unlock only) |

### Case

`manualModerationAndCases.caseManagement: true`. The record a moderator reviews/resolves in `web_dashboard`'s `case_detail` panel; wraps one `ModerationAction` and, if disputed, one or more `Appeal` rows.

```prisma
model Case {
  id                  String     @id @default(cuid())
  guildId             String
  targetDiscordUserId String?                         // raw PII; null for PURGE and LOCKDOWN cases (channel-scoped, no single target — mirrors ModerationAction, which this 1:1-wraps)
  targetUsername      String?                         // raw PII snapshot at creation time; null under the same condition as targetDiscordUserId
  targetChannelId     String?                         // set for PURGE, LOCKDOWN cases; mirrors ModerationAction.targetChannelId
  source              CaseSource
  filterId            String?                          // set when source = AUTOMOD — which AutomodFilterConfig filter fired (e.g. "spam", "phishing"); null when source = MANUAL
  moderatorDiscordId  String?                           // raw PII; null until a moderator claims/confirms an AUTOMOD-sourced case
  status              CaseStatus @default(OPEN)
  evidence            Json                              // { messageContent?: string, attachmentUrls?: string[], channelId?: string, messageId?: string } — raw PII, see Retention & Lifecycle Fields
  resolutionNotes     String?
  createdAt           DateTime   @default(now())
  updatedAt           DateTime   @updatedAt
  expiresAt           DateTime
  deletedAt           DateTime?

  @@index([guildId, createdAt])   // live_log / case-list queries
  @@index([guildId, status])      // pending/open case queues
}
```

### AutomodFilterConfig

One `{filter}Enabled` + `{filter}Config` pair per `automatedModeration.filters` entry, all on a single per-guild row — 04-automod-engine.md's per-message pipeline always needs the full filter set together, so one row avoids an 8-way join on every `messageCreate` event.

```prisma
model AutomodFilterConfig {
  id                 String   @id @default(cuid())
  guildId            String   @unique

  spamEnabled        Boolean  @default(true)
  spamConfig         Json     @default("{}")   // { maxMessages: number, windowSeconds: number, action: ActionType }
  raidEnabled        Boolean  @default(true)
  raidConfig         Json     @default("{}")   // { joinThreshold: number, windowSeconds: number, action: ActionType }
  linksEnabled       Boolean  @default(true)
  linksConfig        Json     @default("{}")   // { allowlist: string[], blockInvites: boolean }
  profanityEnabled   Boolean  @default(true)
  profanityConfig    Json     @default("{}")   // { wordlist: "default" | "strict", customWords: string[] }
  nsfwImageEnabled   Boolean  @default(true)
  nsfwImageConfig    Json     @default("{}")   // { confidenceThreshold: number, action: ActionType }
  phishingEnabled    Boolean  @default(true)
  phishingConfig     Json     @default("{}")   // { blocklistSource: "in-house", action: ActionType }
  massMentionEnabled Boolean  @default(true)
  massMentionConfig  Json     @default("{}")   // { maxMentions: number, action: ActionType }
  capsEmojiEnabled   Boolean  @default(true)
  capsEmojiConfig    Json     @default("{}")   // { maxCapsRatio: number, maxEmojiCount: number }

  updatedAt          DateTime @updatedAt
  updatedByDiscordId String?                    // raw PII — last moderator to edit via the config_editor panel
}
```

Per-filter tunable shapes (the `*Config` JSON payloads) are defined in full in 04-automod-engine.md; this file only fixes that each filter gets its own enabled flag and config blob, and that both are guild-scoped.

### Ticket

```prisma
model Ticket {
  id                 String       @id @default(cuid())
  guildId            String
  openedByDiscordId  String                          // raw PII
  channelId          String?                          // Discord channel/thread bot provisions for the ticket; null until provisioned
  status             TicketStatus @default(OPEN)
  claimedByDiscordId String?                           // raw PII
  subject            String
  initialMessage     String                            // raw PII: message content snippet from the opening DM/modal
  createdAt          DateTime     @default(now())
  updatedAt           DateTime     @updatedAt
  closedAt           DateTime?
  expiresAt          DateTime
  deletedAt          DateTime?

  @@index([guildId, status])
}
```

### Appeal

`manualModerationAndCases.appealsProcess: true`. Linked to the `Case` it disputes; `ingressPath` records which of 02-architecture.md's two entry points (bot DM modal vs. portal form) it came through.

```prisma
model Appeal {
  id                   String        @id @default(cuid())
  guildId              String
  caseId               String                              // FK Case.id
  submittedByDiscordId String                               // raw PII
  reason               String                               // raw PII: freeform text
  ingressPath          AppealIngress
  status               AppealStatus  @default(PENDING)
  decidedByDiscordId   String?                               // raw PII
  decisionNotes        String?
  createdAt            DateTime      @default(now())
  decidedAt            DateTime?
  expiresAt            DateTime
  deletedAt            DateTime?

  @@index([caseId])
  @@index([guildId, status])   // pending-appeals queue view (06-case-management-and-appeals.md)
}
```

### AuditLogEntry

`rolesAndPermissions.auditLogging: true`. One row per state-changing event system-wide — case lifecycle, appeal decisions, config edits, permission edits, ticket lifecycle — so `audit_viewer` has a single source to query rather than reconstructing history from other tables.

```prisma
model AuditLogEntry {
  id             String    @id @default(cuid())
  guildId        String
  actorType      ActorType
  actorDiscordId String?                       // raw PII; null when actorType = SYSTEM (e.g. the retention sweep)
  eventType      String                         // "case.created" | "case.updated" | "appeal.filed" | "appeal.resolved" | "action_reversed" | "config.updated" | "permission.updated" | "ticket.created" | "ticket.closed" — full catalog in 06/07/08/09-*.md
  targetType     String?                        // "case" | "ticket" | "appeal" | "member" | "config" | "permission"
  targetId       String?
  payload        Json                           // event-specific diff/detail; raw PII where the event touches user data (old/new config values, message-content references)
  createdAt      DateTime  @default(now())
  expiresAt      DateTime
  deletedAt      DateTime?

  @@index([guildId, createdAt])
}
```

### PermissionRole (Custom Permission)

`rolesAndPermissions.customPermissionBuilder: true`. The two baseline `permissionLevels` (`admin`, `moderator`) are seeded as `isBuiltIn: true` rows on guild install; `role_permission_ui` creates additional rows through the same model. Full permission-flag catalog and evaluation logic live in 09-auth-and-permissions.md — this file only fixes storage.

```prisma
model PermissionRole {
  id             String   @id @default(cuid())
  guildId        String
  name           String                          // "Admin", "Moderator", or a custom name from the builder
  isBuiltIn      Boolean  @default(false)
  discordRoleIds String[]                         // Discord role IDs mapped to this permission role; membership is resolved at request time from GuildMember.roles, never cached on the user
  permissions    String[]                         // flags, e.g. "case.view", "case.resolve", "config.edit", "ticket.claim", "appeal.decide", "permission.edit" — catalog in 09-auth-and-permissions.md
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  @@unique([guildId, name])
  @@index([guildId])
}
```

### UserSession

`webPortal.authMethod: "discord_oauth"`. Backs NextAuth's session (02-architecture.md); deliberately **not** guild-scoped — one login session covers every guild the user has access to, with per-guild authorization checked per-request (see Multi-Guild Scoping).

```prisma
model UserSession {
  id                 String   @id @default(cuid())
  discordUserId      String                        // raw PII
  discordUsername    String                        // raw PII, snapshot at login
  accessTokenEnc     String                         // Discord OAuth2 access token, encrypted at rest — key management in 09-auth-and-permissions.md
  refreshTokenEnc    String
  activeGuildId      String?                        // last guild selected via multi_server_switch; null until first selection
  oauthExpiresAt     DateTime                        // Discord token expiry — distinct from the retention expiresAt below
  createdAt          DateTime @default(now())
  lastSeenAt         DateTime @updatedAt
  expiresAt          DateTime                        // 90-day retention window
  deletedAt          DateTime?

  @@index([discordUserId])
}
```

`accessTokenEnc`/`refreshTokenEnc` are additionally revoked and cleared on logout or Discord-side token invalidation, independent of the 90-day retention sweep — they're security-sensitive credentials, not just retained personal data.

## Multi-Guild Scoping

`scope.inScope` includes `multi_guild` and `webPortal.dashboardFeatures` includes `multi_server_switch`: every entity that holds guild-specific data carries a `guildId` column, and every guild-scoped query filters and indexes on it first so adding a guild is a row insert (per 10-multi-guild-support.md), never a schema change.

| Entity | `guildId` role | Uniqueness / index rule |
|---|---|---|
| `Guild` | is the tenant key | `id` (PK) |
| `GuildMember` | tenant key | `@@unique([guildId, discordUserId])` — one row per user *per guild*, so a user in 5 guilds has 5 independent role/warn/ban states |
| `Case` | tenant key | `@@index([guildId, createdAt])`, `@@index([guildId, status])` |
| `ModerationAction` | tenant key | `@@index([guildId])`, `@@index([guildId, targetDiscordUserId])` |
| `AutomodFilterConfig` | tenant key | `@@unique([guildId])` — exactly one config row per guild by construction, so there is no "default/global" row a lookup could accidentally fall back to across guilds |
| `Ticket` | tenant key | `@@index([guildId, status])` |
| `Appeal` | tenant key | `@@index([guildId, status])` |
| `AuditLogEntry` | tenant key | `@@index([guildId, createdAt])` |
| `PermissionRole` | tenant key | `@@unique([guildId, name])` — role names are unique *within* a guild, not globally, so "Moderator" in guild A and guild B are independent rows with independent `permissions` arrays |
| `UserSession` | **not** guild-scoped | authorization for a given `guildId` is resolved per-request, never stored on the session |

For `UserSession`, every `api` route under `/api/v1/guilds/:guildId/*` runs a Fastify `preHandler` (`api/src/plugins/guildAccess.ts`, `requireGuildAccess`) that: (1) loads the caller's `GuildMember` row for that `:guildId` via `discordUserId` from the session, (2) resolves their `PermissionRole` for that guild via `discordRoleIds` ∩ `GuildMember.roles`, and (3) 403s if no `GuildMember` row exists for that guild — this is what stops a session valid in guild A from reading guild B's `AutomodFilterConfig` or `PermissionRole` rows even though the session itself carries no guild key. The same scoping is mirrored on the realtime side: Socket.IO rooms are `guild:{guildId}` (02-architecture.md), and the server only joins a socket to a room after the same `requireGuildAccess` check passes on connection. Full authorization flow in 09-auth-and-permissions.md.

## Retention & Lifecycle Fields

`dataAndPrivacy.dataRetentionDays: "90"` and `gdprCompliance: true` apply to **activity/personal data**, not to live configuration or live state: `Case`, `ModerationAction`, `Ticket`, `Appeal`, `AuditLogEntry`, and `UserSession` carry the three lifecycle columns below; `Guild`, `AutomodFilterConfig`, `PermissionRole`, and `GuildMember` are exempt from the 90-day sweep, not personal data subject to a rolling purge. `Guild` and `AutomodFilterConfig` are current-state configuration despite holding raw PII (`ownerDiscordId`, `updatedByDiscordId`) that persists until the guild uninstalls the bot or a moderator explicitly changes it; `PermissionRole` holds no PII at all. `GuildMember` is likewise current-state, not an activity record — it is a live membership snapshot kept in sync with Discord's gateway (`guildMemberUpdate` events overwrite `discordUsername`/`discordAvatarUrl`/`roles` in place) rather than an append-only log of events like `Case`/`Ticket`/`Appeal`/`AuditLogEntry`, so it carries no `expiresAt`/`deletedAt` pair and is out of scope for the timed sweep; a GDPR erasure request against a `GuildMember` row is handled as an immediate delete of that row (not a soft-delete-then-sweep), specified in full in 11-data-privacy-compliance.md.

Every retained entity has:

- **`createdAt: DateTime`** — set at insert (`@default(now())`), never updated.
- **`expiresAt: DateTime`** — set at insert to `createdAt + 90 days`, computed application-side (not a DB default, since Prisma can't express a relative-to-another-column default) in each service's create path (e.g. `CasesService.createCase()`, `AppealsService.fileAppeal()`, `api/src/jobs/retentionSweep.ts` reads this column). Indexed (`@@index` combos above already cover it via `[guildId, createdAt]`; the sweep itself queries `WHERE expiresAt <= now() AND deletedAt IS NULL`).
- **`deletedAt: DateTime?`** — null until the retention sweep (11-data-privacy-compliance.md) soft-deletes the row (excludes it from all normal reads via a Prisma middleware filter), giving a grace window before a second, later sweep phase hard-deletes rows past a fixed soft-delete-to-hard-delete gap. `UserSession.deletedAt` is additionally set immediately on explicit logout, independent of the 90-day timer.

`dataAndPrivacy.piiHandling: "raw"` means these fields are stored exactly as received from Discord — no hashing, truncation, or anonymization — so the 90-day purge above is the *only* privacy control on them, not a defense-in-depth layer on top of redaction:

| Entity | Raw PII fields |
|---|---|
| `Guild` | `ownerDiscordId` |
| `GuildMember` | `discordUserId`, `discordUsername`, `discordAvatarUrl` |
| `Case` | `targetDiscordUserId`, `targetUsername`, `moderatorDiscordId`, `evidence.messageContent`, `evidence.attachmentUrls` |
| `ModerationAction` | `targetDiscordUserId`, `moderatorDiscordId`, `reason`, `reversedByDiscordId` |
| `Ticket` | `openedByDiscordId`, `claimedByDiscordId`, `initialMessage` |
| `Appeal` | `submittedByDiscordId`, `decidedByDiscordId`, `reason` |
| `AuditLogEntry` | `actorDiscordId`, `payload` (may embed user IDs / message-content references) |
| `PermissionRole` | none directly (`discordRoleIds` identify Discord roles, not users) |
| `AutomodFilterConfig` | `updatedByDiscordId` |
| `UserSession` | `discordUserId`, `discordUsername`, `accessTokenEnc`/`refreshTokenEnc` (credentials, handled per the note above rather than the 90-day PII path) |

This table is the field-level input to 11-data-privacy-compliance.md, which specifies the sweep job's query shape, the soft-delete → hard-delete gap length, and the GDPR data-subject-request (export/erasure) endpoints that read these same PII columns on demand.
