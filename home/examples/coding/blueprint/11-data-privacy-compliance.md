# 11 — Data Privacy & Compliance

Implements `dataAndPrivacy` in full (`dataRetentionDays: "90"`, `gdprCompliance: true`, `piiHandling: "raw"`, `selfHostOption: false`) and the privacy-relevant half of `technical.uptimeTarget: "99.9"`. `03-data-model.md`'s Retention & Lifecycle Fields section and its Raw PII fields table are the field-level input to everything below — this file does not redefine any schema, it specifies the job, endpoints, and deployment configuration that operate on the columns already fixed there.

## Data Retention Policy

`dataAndPrivacy.dataRetentionDays: "90"` applies to the six models 03-data-model.md marks as activity/personal data — `Case`, `ModerationAction`, `Ticket`, `Appeal`, `AuditLogEntry`, `UserSession` — each carrying `createdAt` / `expiresAt` / `deletedAt`. `Guild`, `AutomodFilterConfig`, `PermissionRole`, and `GuildMember` are current-state rows, not swept (`GuildMember` erasure is handled under GDPR Compliance below, not by this job).

**Job:** `api/src/jobs/retentionSweep.ts`, run by a BullMQ `Worker` on a queue named `retention-sweep`, scheduled as a repeatable job registered once at boot (`api/src/jobs/index.ts`):

```ts
retentionQueue.add(
  'sweep',
  {},
  { repeat: { pattern: '0 3 * * *' }, jobId: 'retention-sweep-daily' } // 03:00 UTC, off-peak for a "small" single-Postgres-instance deployment
);
```

The sweep runs in two phases, in a fixed model order that respects the two real foreign keys in the retained set (`ModerationAction.caseId` and `Appeal.caseId` both reference `Case.id`; `Ticket` and `AuditLogEntry` have no FK into the retained set):

```ts
const HARD_DELETE_GAP_DAYS = 7;
const BATCH_SIZE = 500;

// order matters only for phase 2 (hard delete): children of Case before Case itself
const RETAINED_MODELS = ['moderationAction', 'appeal', 'auditLogEntry', 'ticket', 'userSession', 'case'] as const;

export async function runRetentionSweep(prisma: PrismaClient, logger: FastifyBaseLogger) {
  const now = new Date();
  const softDeleted: Record<string, number> = {};
  const hardDeleted: Record<string, number> = {};

  for (const model of RETAINED_MODELS) {
    softDeleted[model] = await softDeleteExpired(prisma, model, now);
  }
  for (const model of RETAINED_MODELS) {
    hardDeleted[model] = await hardDeletePurged(prisma, model, now);
  }

  logger.info({ event: 'retention_sweep.completed', softDeleted, hardDeleted }, 'retention sweep run');
}
```

`softDeleteExpired(prisma, model, now)` runs `prisma[model].updateMany({ where: { expiresAt: { lte: now }, deletedAt: null }, data: { deletedAt: now } })` and returns `result.count` — this is the query 03-data-model.md's Retention & Lifecycle Fields section commits to (`WHERE expiresAt <= now() AND deletedAt IS NULL`). It is not `guildId`-scoped: this is a single system-wide batch job, not a per-request read, so the `[guildId, createdAt]` indexes exist for dashboard queries (`live_log`, `audit_viewer`, etc.) and this job simply doesn't need them.

`hardDeletePurged(prisma, model, now)` permanently removes rows that have already sat soft-deleted for `HARD_DELETE_GAP_DAYS` (7 days — chosen here since `spec.json` fixes no value: long enough to recover from an accidental soft-delete or a moderator dispute filed just before expiry, short enough to keep the "raw" PII in `piiHandling: "raw"` from lingering well past the stated 90-day figure). It batches rather than issuing one unbounded `deleteMany`, since an unindexed `deletedAt` scan against a large accumulated backlog would otherwise hold a long write lock on the single Postgres instance fixed in 02-architecture.md:

```ts
async function hardDeletePurged(prisma: PrismaClient, model: RetainedModel, now: Date): Promise<number> {
  const cutoff = new Date(now.getTime() - HARD_DELETE_GAP_DAYS * 24 * 60 * 60 * 1000);
  let total = 0;
  for (;;) {
    const batch = await (prisma[model] as any).findMany({
      where: { deletedAt: { lte: cutoff } },
      select: { id: true },
      take: BATCH_SIZE,
    });
    if (batch.length === 0) return total;
    await (prisma[model] as any).deleteMany({ where: { id: { in: batch.map((r: { id: string }) => r.id) } } });
    total += batch.length;
  }
}
```

The soft-deleted window is enforced everywhere else in the app by a Prisma client middleware, `api/src/lib/prisma/softDeleteMiddleware.ts`, registered once via `prisma.$use(...)` and applied to exactly the six `RETAINED_MODELS` above: any `findFirst`/`findMany`/`count` against one of them gets `deletedAt: null` injected into its `where` clause unless the caller explicitly opts out (used only by the sweep job and the GDPR export path below, both of which pass an explicit `{ includeSoftDeleted: true }` flag that the middleware recognizes and skips). This is what 03-data-model.md refers to as "excludes it from all normal reads via a Prisma middleware filter" — `CasesService`, `TicketsService`, `AppealsService`, and the `audit_viewer` read path (08-web-dashboard.md) all go through this one client, so no service has to remember to add `deletedAt: null` itself.

The sweep does not write an `AuditLogEntry` row for its own runs: `AuditLogEntry.guildId` is required and non-null, but a single sweep pass spans every guild, so there is no single correct `guildId` to attach a summary row to, and per-guild aggregation would add a second query pass purely for bookkeeping. Sweep outcomes are observable instead through the structured `pino` log line above (`event: 'retention_sweep.completed'`), consistent with `api`'s existing logger rather than the guild-facing audit trail (whose full `eventType` catalog is fixed in 09-auth-and-permissions.md and intentionally excludes system-maintenance events).

## GDPR Compliance & PII Handling

`dataAndPrivacy.gdprCompliance: true` requires the two data-subject rights `spec.json` gives no further detail on (`dataAndPrivacy.notes` is blank, `selfHostOption: false` means Lamdbalein itself — not a self-hosting guild operator — is the data controller/processor handling these requests): **access/export** and **erasure**. Both are self-service, identity-gated on the requester's own `discordUserId` (from `UserSession`, established in 09-auth-and-permissions.md), not guild-permission-gated — a data subject's right to their own data doesn't depend on holding a `PermissionRole` in any guild, so these routes run `sessionAuth` only and skip `requireGuildAccess` entirely, and they operate across every guild the user has data in, not just one.

**Entry points**, mirroring the existing DM/portal dual-ingress pattern from 02-architecture.md step 8:

- Portal: `web/src/app/settings/privacy/page.tsx`, calling `api` directly under the authenticated session.
- Bot DM: `/privacy` DM flow (`bot/src/dm/privacyFlow.ts`), a `ButtonBuilder` pair ("Export My Data" / "Delete My Data") per `integrations.notes`' no-slash-commands constraint, forwarding to the same service methods over the internal bot→api path (`aud: "bot"` service JWT, per 02-architecture.md).

**Export — `GET /api/v1/privacy/export`** (portal) and **`POST /internal/v1/privacy/export`** (bot, `{ discordUserId }` in the signed-JWT-authenticated body). Both call `PrivacyService.exportUserData(discordUserId)` (`api/src/modules/privacy/privacy.service.ts`), which queries — with the soft-delete middleware's filter explicitly disabled, since a pending-erasure or not-yet-hard-deleted row is still that user's data until it's gone — every model where the field is `discordUserId`-equal:

| Model | Match field(s) queried |
|---|---|
| `GuildMember` | `discordUserId` |
| `Case` | `targetDiscordUserId`, `moderatorDiscordId` |
| `ModerationAction` | `targetDiscordUserId`, `moderatorDiscordId`, `reversedByDiscordId` |
| `Ticket` | `openedByDiscordId`, `claimedByDiscordId` |
| `Appeal` | `submittedByDiscordId`, `decidedByDiscordId` |
| `AuditLogEntry` | `actorDiscordId` |
| `UserSession` | `discordUserId` |

The handler assembles one JSON document, `{ discordUserId, generatedAt, guilds: [{ guildId, guildName, member, casesAsTarget, casesAsModerator, moderationActions, tickets, appeals, auditLogEntries }] }`, grouped per guild (a user's data is guild-scoped everywhere except `UserSession`, which appears once at the document root per 03-data-model.md's Multi-Guild Scoping table). `accessTokenEnc`/`refreshTokenEnc` on `UserSession` are excluded from the export — they are Lamdbalein's own OAuth credentials for acting on the user's behalf, not personal data being disclosed *to* the user, and disclosing them would hand out a live session token. At `targetServerCount: "small"`, the compiled document is returned synchronously (no background job / signed-URL indirection needed) with `Content-Disposition: attachment; filename="lamdbalein-export-{discordUserId}.json"`.

**Erasure — `POST /api/v1/privacy/erasure`** (portal, confirmation-gated in the UI) and **`POST /internal/v1/privacy/erasure`** (bot). Both call `PrivacyService.eraseUserData(discordUserId)`, which treats the six PII-bearing tables differently depending on whether the row's *entire value* is the user's personal data or the user's PII is one field on a record that also serves other purposes:

- **`GuildMember`** — immediate hard delete (`prisma.guildMember.delete(...)`), per 03-data-model.md's explicit note that erasure against `GuildMember` is "an immediate delete of that row (not a soft-delete-then-sweep)" since the row is a pure per-user membership snapshot.
- **`UserSession`** — immediate hard delete, plus a best-effort `POST https://discord.com/api/oauth2/token/revoke` using the still-decryptable `accessTokenEnc` before the row is dropped (same revoke call as the logout path in 09-auth-and-permissions.md).
- **`Case`, `ModerationAction`, `Ticket`, `Appeal`, `AuditLogEntry`** — these rows are not deleted outright: a `Case`/`ModerationAction` row is one guild's moderation-history record, which other members (the moderator, or a member wrongly implicated by the same evidence) have an independent, ongoing interest in, and dropping it mid-appeal would break the FK chain and the `audit_viewer` history other users are entitled to see. Instead `PrivacyService.redactUserPii(discordUserId)` runs field-level redaction, nulling only the columns 03-data-model.md's Raw PII fields table attributes to that user's identity, leaving row structure, status, and non-PII fields (e.g. `actionType`, `status`, timestamps) intact:

  | Model | Fields redacted when `discordUserId` matches |
  |---|---|
  | `Case` | `targetDiscordUserId → null`, `targetUsername → null`, `evidence.messageContent`/`evidence.attachmentUrls` stripped from the JSON blob (when the user is the target); `moderatorDiscordId → null` (when the user is the moderator) |
  | `ModerationAction` | `targetDiscordUserId → null`, `reason → null` (when target); `moderatorDiscordId → null` (when moderator); `reversedByDiscordId → null` (when reverser) |
  | `Ticket` | `openedByDiscordId → null`, `initialMessage → null` (when opener); `claimedByDiscordId → null` (when claimant) |
  | `Appeal` | `submittedByDiscordId → null`, `reason → null` (when submitter); `decidedByDiscordId → null` (when decider) |
  | `AuditLogEntry` | `actorDiscordId → null` (when actor); `payload` passed through `redactPayloadPii(payload, discordUserId)`, a best-effort walk that replaces any string value equal to `discordUserId` with the literal `"[redacted]"` |

  Each redaction is a targeted `updateMany` keyed on the matching field (e.g. `prisma.case.updateMany({ where: { targetDiscordUserId: discordUserId }, data: { targetDiscordUserId: null, targetUsername: null, evidence: redactEvidence } })`), run once per matching field per model so a row where the same person appears in two roles (e.g. moderator on one case, target on another) gets both passes applied to the rows where each role matches.

  After redaction, `PrivacyService` writes one `AuditLogEntry` per affected guild (`actorType: SYSTEM`, `eventType: "privacy.erasure_completed"`, `targetType: "member"`, `targetId: discordUserId`, `payload: { rowsRedacted: { case: n, moderationAction: n, ticket: n, appeal: n, auditLogEntry: n } }`) — counts only, no redacted content, so the completion record doesn't itself reintroduce the erased PII. `privacy.erasure_completed` is a new value this file adds to the `eventType` set — 09-auth-and-permissions.md's Full `eventType` catalog table and 03-data-model.md's `AuditLogEntry.eventType` field comment predate it and list neither this value nor 11 among the catalog's source files, so implementing this route also means adding this row (`eventType: "privacy.erasure_completed"`, `actorType: SYSTEM`, `Written by: PrivacyService.eraseUserData()`, `targetType`/`targetId`: `"member"` / `discordUserId`) to that table and its `audit_viewer` filter-dropdown catalog, the same way this file's own retention sweep note above (Data Retention Policy) documents why the sweep itself deliberately does *not* add a row there.

This two-tier design — hard delete for rows that *are* the user's data (`GuildMember`, `UserSession`) versus field redaction for rows that *reference* the user's data alongside other guild members' legitimate moderation-history interest (`Case`, `ModerationAction`, `Ticket`, `Appeal`, `AuditLogEntry`) — is the concrete mechanism `dataAndPrivacy.piiHandling: "raw"` implies is otherwise missing: since nothing is hashed or truncated at write time, an explicit erasure request is the only way any of these raw fields ever stops being plaintext PII before the routine 90-day sweep would have hard-deleted the whole row anyway.

## Uptime & Reliability Target

`technical.uptimeTarget: "99.9"` allows roughly 43 minutes of downtime per month. 02-architecture.md's Deployment & Hosting Model section fixes the process topology this budget runs on (`bot`: 1 instance, `api`: 2 instances, `web`: stateless alongside `api`, 1 managed Postgres, 1 managed Redis); this section fixes the concrete health-check, restart, and isolation configuration that makes that topology actually hit the target.

**Health checks, per component:**

- `bot` exposes `GET /healthz` on a minimal Fastify listener bolted onto the same process (not a separate service — `bot` holds the one Discord gateway connection, so its liveness check must run in-process to observe `client.ws.status`). Handler returns `200 { status: 'ok' }` when `client.ws.status === Status.Ready`, else `503`.
- `api` exposes two routes on its existing Fastify instance: `GET /healthz` (process liveness — always `200` once the process is up, no dependency checks) and `GET /readyz` (`200` only if a `SELECT 1` against Postgres via the pooled Prisma client and a `PING` against Redis both succeed within a short timeout, else `503`) — the split matters because a replica whose DB connection dropped should stop receiving traffic (`/readyz` fails) without the platform concluding the *process* is dead and needlessly restarting it (`/healthz` still passes).
- `web` relies on the hosting platform's default HTTP check against `/` (Next.js SSR — a 200 response is a sufficient liveness signal; it has no direct DB/Redis dependency per 02-architecture.md's component table).

**Restart policy**, configured on the PaaS process supervisor fixed in 02-architecture.md (Fly.io or equivalent — shown as `fly.toml` here, the same shape applies to Railway's health-check config):

```toml
# bot's fly.toml
[[services]]
  internal_port = 8081
  protocol = "tcp"
  [[services.http_checks]]
    path              = "/healthz"
    interval          = "15s"
    timeout           = "5s"
    grace_period      = "30s"   # covers discord.js's own gateway reconnect window before the supervisor concludes the process itself is unrecoverable
    restart_limit     = 3       # 3 consecutive failed checks (45s) before a hard process restart

# api's fly.toml
[[services]]
  internal_port = 3000
  protocol = "tcp"
  [[services.http_checks]]
    path      = "/healthz"
    interval  = "10s"
    timeout   = "3s"
  [[services.http_checks]]
    path      = "/readyz"
    interval  = "10s"
    timeout   = "3s"
```

`discord.js`'s built-in gateway auto-reconnect (WebSocket close codes 4000–4009 and network drops) is the first line of defense for `bot` and handles the overwhelming majority of transient failures without ever failing `/healthz`; the supervisor-level restart above only fires for the residual case where the process itself has wedged (e.g. an unhandled exception in an event handler) and `client.ws.status` never recovers. Because `bot` is a deliberate single instance (02-architecture.md — Discord gateway sessions can't be load-balanced), this restart path is the only recovery mechanism for it, so `grace_period`/`restart_limit` are tuned to be forgiving of normal reconnect latency but still bounded well inside the 43-minute monthly budget even if several restarts happen in a month.

**Failure isolation between components:**

- `bot` and `api` are separate deployable processes (02-architecture.md's System Components table) with no shared runtime — a `bot` crash and restart cycle (worst case: the `grace_period` + `restart_limit` window above, ~45s) never takes `api` or `web` down, and vice versa. The only coupling is the `discord-actions` BullMQ queue and the bot→api HTTP calls, both of which are designed to tolerate either side being briefly unavailable: `discord-actions` jobs (`api → bot` commands like `reverse_action`) are configured with `{ attempts: 5, backoff: { type: 'exponential', delay: 2000 } }`, so a job enqueued while `bot` is mid-restart is simply picked up once its worker reconnects rather than being lost; `bot → api` calls (case/ticket/audit-log writes) use a short-timeout HTTP client with retry-on-5xx, so a moment where one `api` replica is cycling doesn't drop an automod action's case record — the load balancer routes the retry to the other replica.
- `api`'s 2 replicas behind the platform load balancer mean a rolling deploy or an unplanned single-replica crash is invisible to both `web` and `bot`'s internal calls, per 02-architecture.md — this is what actually absorbs the bulk of the 99.9% budget, since `api` is on the request path for every dashboard action and every case/ticket/appeal write.
- The two shared-fate dependencies — the single managed Postgres instance and the single managed Redis instance (02-architecture.md, sized for `targetServerCount: "small"`) — are the residual single points of failure the topology accepts rather than engineers around, consistent with the no-Kubernetes/no-multi-region posture blank `budgetNotes` implies; their contribution to the downtime budget is bounded by the managed provider's own SLA rather than anything this app's code controls, which is why `api`'s `/readyz` check (above) is what converts a Postgres/Redis blip into "traffic drains off the affected replica" rather than "user-visible 500s."
