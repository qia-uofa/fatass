# 07 — Ticketing System

Implements `scope.inScope: ticketing`, the one in-scope feature `spec.json` names with zero further detail anywhere in the file — no fields, states, or channel are implied elsewhere, so this file fixes a concrete minimal design from scratch rather than expanding on existing spec content. It is sized throughout for `scope.targetServerSize: "small"` (03-data-model.md, 02-architecture.md's Deployment section) and built on the same constraints 05-manual-moderation.md already establishes: `integrations.slashCommands: false`, `integrations.webhookSupport: false`, and `integrations.notes: "utilises discord native in-message UI as well as dm"`. The `Ticket` model and `TicketStatus` enum are already fixed in 03-data-model.md; this file specifies the lifecycle built on that schema and the Discord-side flow that populates it. `bot/src/dm/ticketFlow.ts → POST /internal/v1/tickets` and the `ticket.created` push into a dashboard queue view "structurally identical to `live_log`" are already fixed in 02-architecture.md's End-to-End Data Flow — this file is the full specification of that path.

## Ticket Data Model & Lifecycle

Recap of the schema this section builds on (full field list, indexes, and retention columns in 03-data-model.md):

```prisma
enum TicketStatus { OPEN CLAIMED RESOLVED CLOSED }

model Ticket {
  id                 String       @id @default(cuid())
  guildId            String
  openedByDiscordId  String                          // raw PII
  channelId          String?                          // Discord thread bot provisions for the ticket; null until provisioned
  status             TicketStatus @default(OPEN)
  claimedByDiscordId String?                           // raw PII
  subject            String
  initialMessage     String                            // raw PII: message content snippet from the opening DM/modal
  createdAt          DateTime     @default(now())
  updatedAt          DateTime     @updatedAt
  closedAt           DateTime?
  expiresAt          DateTime
  deletedAt          DateTime?

  @@index([guildId, status])
}
```

**Why this shape and no more:** at `targetServerSize: "small"` a single flat queue is sufficient — no `priority`, no `category`, no SLA/due-date fields, and no department routing. One permission flag (`ticket.claim`, below) rather than a tiered queue-ownership model. One Discord channel per guild (`#tickets`) holding one private thread per ticket, rather than a channel-per-ticket layout that would burn into Discord's 500-channel-per-guild cap at any real ticket volume — threads don't count against that limit, which is the concrete reason a small deployment should use them instead of channels.

### States and transitions

```
                    ┌─────────────┐
   createTicket() ─▶│    OPEN     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         claimTicket() closeTicket()    │
              │            │            │
              ▼            ▼            │
        ┌───────────┐ ┌─────────┐       │
        │  CLAIMED  │ │ CLOSED  │◀──────┘
        └─────┬─────┘ └─────────┘
              │            ▲   (terminal)
        ┌─────┴─────┐      │
        │           │      │
  resolveTicket() closeTicket()
        │           │      │
        ▼           └──────┘
  ┌───────────┐            │
  │ RESOLVED  │────────────┘
  └───────────┘   closeTicket()
     (terminal once CLOSED)
```

| Transition | Trigger | Endpoint | Effect |
|---|---|---|---|
| `— → OPEN` | Member submits the ticket modal (either entry point, below) | `POST /internal/v1/tickets` | `TicketsService.createTicket()` (`api/src/modules/tickets/tickets.service.ts`) writes `Ticket` (`status: "OPEN"`, `expiresAt: createdAt + 90 days` per 03-data-model.md's Retention & Lifecycle Fields) and `AuditLogEntry { eventType: "ticket.created", targetType: "ticket", targetId: ticket.id }` in one transaction, then emits `ticket.created` on the `guild:{guildId}` Socket.IO room (02-architecture.md) |
| `OPEN → CLAIMED` | A moderator with `ticket.claim` clicks "Claim Ticket" | `POST /internal/v1/tickets/:id/claim { claimedByDiscordId }` | `TicketsService.claimTicket()` loads the `Ticket`, 404s if missing, 409s if `status !== "OPEN"` (first click wins, same "first `PATCH` wins" concurrency rule 06-case-management-and-appeals.md uses for appeals), else sets `claimedByDiscordId`, `status: "CLAIMED"`, writes `AuditLogEntry { eventType: "ticket.claimed" }`, emits `ticket.updated` |
| `CLAIMED → RESOLVED` | The claimant (or any `ticket.claim` holder — see Permission scope, below) clicks "Mark Resolved" | `POST /internal/v1/tickets/:id/resolve { resolvedByDiscordId }` | Loads the `Ticket`, 404s if missing, 409s if `status !== "CLAIMED"`; else sets `status: "RESOLVED"`, writes `AuditLogEntry { eventType: "ticket.resolved" }`, emits `ticket.updated`. Thread is **not** archived here — resolution just signals the reported issue is handled; the thread stays open for follow-up until explicitly closed. |
| `OPEN → CLOSED`, `CLAIMED → CLOSED`, `RESOLVED → CLOSED` | Any `ticket.claim` holder clicks "Close Ticket" | `POST /internal/v1/tickets/:id/close { closedByDiscordId }` | Loads the `Ticket`, 404s if missing, 409s if `status === "CLOSED"`; else sets `status: "CLOSED"`, `closedAt: now()`, writes `AuditLogEntry { eventType: "ticket.closed" }`, emits `ticket.updated`. This is the only path into `CLOSED` — an unclaimed ticket (spam, duplicate, or a member self-resolving outside the thread) is closed directly from `OPEN` without ever passing through `CLAIMED`/`RESOLVED`. |

`CLOSED` is terminal — there is no reopen path; a member with a follow-up question after closure opens a new ticket (`createTicket()` again), keeping the state machine linear and consistent with the "no SLA/reopen tracking" sizing decision above.

### Permission scope

One flag, `ticket.claim` (already named as an example in 03-data-model.md's `PermissionRole.permissions` catalog; full catalog in 09-auth-and-permissions.md), gates all three moderator-side transitions — `claim`, `resolve`, and `close` are not split into separate flags, unlike 05-manual-moderation.md's per-action flags, because a small deployment's moderator team is exactly the set of people trusted to handle any ticket end-to-end. `resolve`/`close` are deliberately **not** restricted to the original claimant: any `ticket.claim` holder can close or resolve any ticket regardless of who claimed it, so a moderator going offline mid-conversation doesn't strand a ticket with no way to close it short of an admin override.

### Association to Guild and Member

`Ticket.guildId` is the tenant key (03-data-model.md's Multi-Guild Scoping table already lists `Ticket`'s `@@index([guildId, status])`). Like `Case` (06-case-management-and-appeals.md's Association to Member and Guild), `Ticket` stores only raw Discord IDs (`openedByDiscordId`, `claimedByDiscordId`) and resolves live profile data on read rather than denormalizing it: `TicketsService.getTicket()` joins `GuildMember.findUnique({ where: { guildId_discordUserId: { guildId, discordUserId: ticket.openedByDiscordId } } })` (the same `@@unique([guildId, discordUserId])` index) to attach the opener's current username/avatar/roles to the API response. `subject` and `initialMessage` are the only ticket-specific content fields — everything else needed to display a ticket (member context, moderator context) comes from `GuildMember` at read time, exactly mirroring how `case_detail` resolves `Case.targetDiscordUserId`.

## Ticket Interaction Channels

With `integrations.slashCommands: false` and `integrations.webhookSupport: false`, opening a ticket and responding to one both go through the same two mechanisms 05-manual-moderation.md establishes for moderation — Discord message components and DMs — applied here to a member-initiated flow instead of a moderator-initiated one. Both entry points converge on one function, `openTicket()` (`bot/src/tickets/openTicket.ts`), which `bot/src/dm/ticketFlow.ts` (the DM entry point, already named in 02-architecture.md) and `bot/src/discord/ticketConsole.ts` (the in-guild entry point, named below) both call.

### Entry point 1 — the ticket console (in-guild)

`provisionGuild()` (04-automod-engine.md, 05-manual-moderation.md) is extended to create a second pair of channels alongside `#mod-actions`: a public `#open-a-ticket` text channel (`ViewChannel` granted to `@everyone`, `SendMessages` denied — members interact only through the button, never by typing) and a private `#tickets` text channel (`ViewChannel` denied to `@everyone`, granted to the Discord role IDs backing `admin`/`moderator` `PermissionRole` rows, mirroring `#mod-actions`'s overwrite pattern exactly). `bot/src/discord/ticketConsole.ts`'s `ensureTicketConsole(guildId)` posts and pins one permanent message in `#open-a-ticket`:

```
Row: ButtonBuilder   customId "ticket:open"   label "🎫 Open a Ticket"   style Primary
```

Clicking it opens a `ModalBuilder` (`customId "ticket:open:modal"`):

```
subject          TextInputBuilder, TextInputStyle.Short, max 100 chars, required
initialMessage   TextInputBuilder, TextInputStyle.Paragraph, max 1000 chars, required
```

### Entry point 2 — direct DM

`bot`'s `messageCreate` handler, when the message's `channel.type === ChannelType.DM` and the author isn't the bot itself, invokes `bot/src/dm/ticketFlow.ts`'s `handleDm()`. Since there is no slash command to carry an explicit guild argument, the guild is resolved from the bot's own mutual-guild list for that user (`client.guilds.cache.filter(g => g.members.cache.has(author.id))`):

- **Exactly one mutual guild:** bot replies in the DM with a single button, `customId "ticket:open:{guildId}"`, label `"🎫 Open a Ticket in {guild.name}"`.
- **More than one mutual guild:** bot replies with a `StringSelectMenuBuilder` (`customId "ticket:selectGuild"`, one option per mutual guild, label = guild name). Selecting an option edits the reply in place to show the same single button as above, scoped to the chosen `guildId`.
- **Zero mutual guilds** (shouldn't normally be reachable — a DM to the bot implies at least one shared guild — handled defensively): bot replies `"I couldn't find a shared server to open a ticket in."` and stops.

Clicking the scoped button opens the identical modal from Entry point 1 (`customId "ticket:open:modal:{guildId}"`, same two fields), keeping the modal shape and the downstream handler identical regardless of which entry point was used — the only difference between the two paths is how `guildId` is determined before the modal opens.

### Provisioning and moderator response

On modal submit (either entry point), `openTicket()` runs, in this order:

1. Creates a private thread under `#tickets`: `ticketsChannel.threads.create({ name: 'ticket-' + subject.slice(0, 30).toLowerCase().replace(/\s+/g, '-'), type: ChannelType.PrivateThread, invitable: false, reason: 'ticket opened' })`. `invitable: false` means only the bot (via `MANAGE_THREADS`, already held for the moderation console) and users explicitly added can invite others — the opening member can't invite unrelated users into their own ticket.
2. Adds the opener to the thread: `thread.members.add(openedByDiscordId)`. This is what grants that member access to a thread under a channel they otherwise can't view — Discord's private-thread membership model grants access per-thread independent of parent-channel permissions. Moderators need no explicit add: Discord grants visibility into every private thread under a channel to anyone whose Discord role holds `MANAGE_THREADS` on that channel, so a guild whose `admin`/`moderator` Discord roles carry that permission (a reasonable baseline for staff roles, though not itself enforced by this bot) lets all moderators browse `#tickets` without being added to each thread individually.
3. Posts the opening message into the new thread — an `EmbedBuilder` (`title: subject`, `description: initialMessage`, `footer: "Opened by @{openedByUsername}"`) followed by:
   ```
   Row: ButtonBuilder   customId "ticket:claim:{ticketId}"   label "Claim Ticket"   style Primary
   ```
   (`{ticketId}` is filled in after step 4, since the DB row doesn't exist yet at thread-creation time — the message is posted with a placeholder and edited once `createTicket()` returns, or equivalently the thread is created first and its ID passed into the same `POST /internal/v1/tickets` call as `channelId`, avoiding a second round-trip; either way `channelId` is populated in the same transaction as ticket creation in the normal path, and is nullable in the schema only to cover the narrow window where thread creation succeeds but the follow-up API call fails and must be retried.)
4. Calls `POST /internal/v1/tickets { guildId, openedByDiscordId, channelId: thread.id, subject, initialMessage }` (see States and transitions, above, for what this writes).
5. Replies to the original interaction (the modal submit) ephemerally: `"✅ Ticket opened — continue here: {thread.url}"` for the in-guild path, or in the DM for the DM path (a member who opened via DM can still open the thread link directly since they were added to it in step 2, even without otherwise browsing `#tickets`).

A moderator responds entirely inside the thread — plain messages, no further modals needed for the conversation itself. The claim/resolve/close buttons posted in step 3 drive the lifecycle:

- **Claim:** clicking "Claim Ticket" runs the same `hasActionPermission`-style gate as 05-manual-moderation.md's `permissionGate.ts` (`hasActionPermission(moderatorMember, "ticket.claim")`), calls `POST /internal/v1/tickets/:id/claim`, and edits the opening message to append `"🎫 Claimed by <@{claimedByDiscordId}>"` and replace the button row with:
  ```
  Row: ButtonBuilder × 2   customId "ticket:resolve:{ticketId}"   label "Mark Resolved"   style Secondary
                            customId "ticket:close:{ticketId}"     label "Close Ticket"    style Danger
  ```
- **Resolve:** calls `POST /internal/v1/tickets/:id/resolve`, edits the message to prefix `"✅ Resolved — "` before the claimed line, keeps the "Close Ticket" button (resolve doesn't remove it, since the thread often stays open a little longer for the member to confirm), removes "Mark Resolved".
- **Close:** calls `POST /internal/v1/tickets/:id/close`, then `thread.setArchived(true)` and `thread.setLocked(true)` (locking prevents the opener from un-archiving it by posting again), and posts a final plain message `"🔒 Ticket closed by <@{closedByDiscordId}>."` before archiving.

### Dashboard and audit surface

Every state change above emits `ticket.updated` (creation emits `ticket.created`) on the `guild:{guildId}` Socket.IO room per 02-architecture.md, feeding a queue view — `GET /api/v1/guilds/:guildId/tickets?status=open` — structurally identical to 06-case-management-and-appeals.md's `GET /api/v1/guilds/:guildId/appeals?status=pending` pending-appeals list; full panel layout is specified in 08-web-dashboard.md, not here. The full `AuditLogEntry.eventType` catalog this file contributes (03-data-model.md's `AuditLogEntry` already names `"ticket.created"` and `"ticket.closed"` as examples): `ticket.created`, `ticket.claimed`, `ticket.resolved`, `ticket.closed` — each written with `targetType: "ticket"`, `targetId: ticket.id`, matching the shape 06-case-management-and-appeals.md uses for `case.*`/`appeal.*` events.
