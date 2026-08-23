# 01 — Overview

## Product Summary & Goals

**Project name:** Lamdbalein
**Project type:** Discord all-in-one moderation app with web portal
**Target audience:** general purpose (no persona/vertical restriction — the design must not assume large-enterprise or niche-community-specific workflows)

`tagline`, `description`, and `successMetrics` are blank in `spec.json`. No marketing copy, positioning statement, or quantitative success criteria (e.g. adoption numbers, retention targets, latency SLOs framed as "success") should be invented for this document set. Every claim about what the product is must trace back to the structured fields below (`primaryGoals`, `scope`, `automatedModeration`, `manualModerationAndCases`, `webPortal`, `rolesAndPermissions`, `integrations`, `dataAndPrivacy`, `technical`). Where a downstream blueprint file needs a concrete number or copy string that `spec.json` leaves blank, treat it as an open implementation parameter (config value, not a product decision) rather than filling it in from convention.

`primaryGoals` is `["visibility", "scale", "reduce_workload"]`. Translated into concrete product objectives that the rest of the blueprint (02-architecture.md onward) must satisfy:

- **visibility** — moderators and admins can see moderation activity as it happens and after the fact, without digging through Discord's audit log or channel history by hand. Operationally this means: a live-updating activity feed (`webPortal.dashboardFeatures: live_log`, see 08-web-dashboard.md), aggregate trend/volume charts (`analytics_charts`, see 08-web-dashboard.md and cross-reference 04-automod-engine.md for the event stream they're built from), a searchable per-user/per-case audit trail (`audit_viewer`, `case_detail`; see 06-case-management-and-appeals.md), and a permanent record of every automated and manual action (`caseManagement: true`, `auditLogging: true`; see 03-data-model.md for the `Case` and `AuditLogEntry` schemas). Visibility is the umbrella goal that `web_dashboard`, `case_system`, and `analytics` (all in `scope.inScope`) exist to serve.
- **scale** — the app must work whether it's installed on one server or many, and within a server, whether moderation volume is low or a raid is in progress. Operationally this means: the automod engine (04-automod-engine.md) must apply filters (`spam`, `raid`, `links`, `profanity`, `nsfw_image`, `phishing`, `mass_mention`, `caps_emoji`) fast enough to act during a raid spike, not just retroactively; and the data/permission model must be guild-scoped from the start so adding a second, third, or Nth guild is a row insert, not a schema change (`scope.inScope: multi_guild`; see 10-multi-guild-support.md and 03-data-model.md for guild-scoped foreign keys). `technical.targetServerCount` and `scope.targetServerSize` are both `"small"` — see the Scope Summary section below for what that bounds.
- **reduce_workload** — routine moderation decisions should not require a human in the loop. Operationally this means: the automod engine takes first-pass automated action on the eight listed filter categories without moderator intervention (04-automod-engine.md), manual actions are one-click/one-message rather than multi-step flows (`manualActions`: kick, softban, ban, timeout, warn, purge, role_strip, lockdown — see 05-manual-moderation.md), and the case/appeals pipeline (`case_system`, `appeals` in scope; `caseManagement: true`, `appealsProcess: true`) gives moderators a structured queue instead of ad hoc DMs and channel threads (06-case-management-and-appeals.md). Ticketing (`scope.inScope: ticketing`, see 07-ticketing-system.md) extends the same workload-reduction goal to member-initiated requests, not just moderator-initiated actions.

## Scope Summary

`scope.inScope` is the complete, authoritative feature list for this build. Nothing outside this list should be implemented; nothing inside it should be dropped. Each entry maps to the blueprint file that specifies its design in full:

| `scope.inScope` entry | Specifying blueprint file |
|---|---|
| `automod_engine` | 04-automod-engine.md |
| `manual_tools` | 05-manual-moderation.md |
| `web_dashboard` | 08-web-dashboard.md |
| `case_system` | 06-case-management-and-appeals.md |
| `analytics` | 08-web-dashboard.md (analytics_charts panel) |
| `ticketing` | 07-ticketing-system.md |
| `appeals` | 06-case-management-and-appeals.md |
| `multi_guild` | 10-multi-guild-support.md |

`scope.outOfScope` is an empty string in `spec.json`. This is not an omission to fill in — it must be read literally: **the spec excludes nothing.** No feature area should be marked out-of-scope in downstream blueprint files on the assumption that "moderation apps typically don't include X." If a capability isn't covered by one of the eight `inScope` entries above, it is simply unspecified, not forbidden — flag it as an open question rather than silently excluding it.

`scope.targetServerSize` is `"small"`, matching `technical.targetServerCount: "small"` (see the Launch Platforms section and 11-data-privacy-compliance.md for the retention/compliance angle on this same field). Both fields set the scale envelope the design targets:

- 02-architecture.md must size infrastructure (worker concurrency, queue throughput, DB connection pooling) for small guild counts and small per-guild member counts, not for a multi-million-member/thousands-of-guilds SaaS deployment. This affects concrete choices such as whether a single-process bot host is sufficient versus requiring a sharded gateway connection manager.
- 11-data-privacy-compliance.md must scope its data-retention and deletion-job design (`dataAndPrivacy.dataRetentionDays: "90"`) for a small-data regime — e.g. retention sweeps can be a straightforward scheduled job over a modest row count rather than a partitioned/batched pipeline.

## Launch Platforms & Explicit Non-Goals

`scope.launchPlatforms` names three surfaces the product ships on at launch: `discord_bot`, `web_portal`, `mobile_web`. All three are in scope for this build — the web portal is not a "future" surface, and `mobile_web` specifically means the web portal must be responsive on mobile browsers rather than requiring a native app (`webPortal.mobileResponsive: true` corroborates this; see 08-web-dashboard.md for responsive layout requirements). There is no native mobile app in scope, and none should be designed for.

The following are explicit non-goals per `spec.json`'s `integrations` block, and must be treated as constraints on every interaction design in this blueprint set, not just as an omitted nice-to-have:

- **`integrations.slashCommands: false`** — no Discord slash commands anywhere in the design. This is a hard constraint on 05-manual-moderation.md, 07-ticketing-system.md, and any other file that specifies a Discord-side interaction: moderator- and member-facing actions must be built from Discord's native in-message UI components (buttons, select menus, modals attached to messages/embeds) and DMs instead.
- **`integrations.webhookSupport: false`** — no inbound or outbound webhook integration points (e.g. no "post case updates to an external webhook URL" feature). Case/ticket/log delivery stays inside Discord (channels, DMs) and the web portal, per `integrations.notes`.
- **`integrations.externalServices: []`** — no third-party service integrations (no external link-scanning API, no third-party image moderation API, etc.) are in scope. Filters listed under `automatedModeration.filters` (e.g. `phishing`, `nsfw_image`) must be designed as self-contained/in-house logic in 04-automod-engine.md rather than assuming a bound external service, unless a later blueprint file explicitly revisits this.

`integrations.notes` — *"utilises discord native in-message UI as well as dm"* — is the mandated interaction paradigm for the entire product, not a note specific to one feature. Combined with `slashCommands: false`, every moderator- and member-facing flow (manual moderation actions, case review, appeals submission, ticket creation) must be specified in 05-manual-moderation.md, 06-case-management-and-appeals.md, and 07-ticketing-system.md as Discord message components (buttons/selects/modals on embeds) and direct messages — never as slash commands, and never as a Discord feature requiring an external webhook round-trip.

`integrations.coexistWithOtherBots: true` is a constraint carried into 10-multi-guild-support.md: the bot must not assume it is the only moderation bot in a guild. Concretely, this rules out design choices such as claiming exclusive ownership of the guild's audit log interpretation, requiring it to be the sole source of role/mute state, or any behavior that would conflict with another bot acting on the same guild concurrently — 10-multi-guild-support.md must specify how the bot detects/defers to state it doesn't own (e.g. role changes made by another bot).
