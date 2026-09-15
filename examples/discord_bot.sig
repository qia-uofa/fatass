# A Node.js Discord bot codebase, with a web control panel, built the
# same way jrpg.sig builds a game design: a Design pipeline decides the
# concrete shape, structured Chains (Commands/Events/Database.Models/
# WebPanel.Pages/WebPanel.ApiRoutes) catalog that shape as data, and a
# Src<Dir> tree (the actual filesystem project, mirroring src/...)
# compiles those catalogs into real code -- one build transform per
# generated area, reading its own source Chain and writing real files
# into its own Dir. Each transform's own "#" comment is its `fatass
# modify` prompt (`fatass touch -p discord_bot.sig -m` reads it and
# fills the transform in right after creating it).
#
# A dep inside a "{...}" block navigates relative to the transform's own
# node's PARENT, same as everywhere else -- a bare name reaches a
# sibling with no ".." needed. Deeper into Src, each generated-code dep
# needs to ascend back out to the top (DiscordBot) before descending
# into its own source Chain -- e.g. from Src.Web.Server (3 levels under
# DiscordBot), "...." (4 dots) ascends 3 levels back to DiscordBot, then
# ".WebPanel.ApiRoutes" descends into it.
#
# Usage: fatass touch -p discord_bot.sig      # scaffold only
#        fatass touch -p discord_bot.sig -m   # scaffold + fill in

DiscordBot<Node>(
    Design<Node>(
        BrainStorm<Chat prompt:str="Brainstorm freely about this Discord bot's core purpose, target community/server type, and one standout feature. Nothing here is final.">,
        Overview<SingleMd>{
            # Read design.brain_storm's session artifacts. Write a
            # structured overview to design.overview: name, one-line
            # pitch, target community, core feature set at a glance, and
            # the moderation/permission model (who can use what). Use
            # Overview.write(...).
            build(BrainStorm);
        },
        TechStack<SingleMd>{
            # Read design.overview. Decide and document the concrete
            # tech stack: Node.js version, discord.js version, the web
            # framework for the panel (e.g. Express) and its rendering
            # approach (server-rendered views vs. a separate frontend
            # build), the database/ORM choice, and how the bot process
            # and web server share state. Use TechStack.write(...).
            build(Overview);
        },
        Architecture<SingleMd>{
            # Read design.tech_stack. Write a module-by-module
            # architecture doc matching src's own real layout
            # (src/bot/commands, src/bot/events, src/database/models,
            # src/web/server/routes, src/web/server/views, src/shared)
            # -- what lives where and how modules import each other.
            # Use Architecture.write(...).
            build(TechStack);
        }
    ),
    Commands<Chain>{
        # Read design.overview. For each slash command this bot needs,
        # Commands.extend(), then write its Info Tuple's 'name'
        # (lowercase, no spaces), 'description' (shown in Discord's
        # command picker), and 'category' (e.g. moderation/fun/utility).
        # For a command with its own arguments, also populate its
        # Options child Chain -- one entry per option, with 'name',
        # 'type' (STRING/INTEGER/BOOLEAN/USER/CHANNEL/...),
        # 'description', and 'required' (true/false).
        build(Design.Overview);
    }(
        Info<Tuple name description category>,
        Options<Chain>(
            Info<Tuple name type description required>
        )
    ),
    Events<Chain>{
        # Read design.architecture. For each discord.js client event
        # this bot needs to react to (e.g. interactionCreate,
        # guildMemberAdd, messageCreate), Events.extend(), then write
        # its Info Tuple's 'name' (the exact discord.js event name) and
        # 'description' (what this handler does when it fires).
        build(Design.Architecture);
    }(
        Info<Tuple name description>
    ),
    Database<Node>(
        Models<Chain>{
            # Read design.overview. For each persistent data model this
            # bot needs (e.g. guild config, user warnings, leveling
            # stats), Models.extend(), then write its Info Tuple's
            # 'name' and 'description'. For each model, also populate
            # its Fields child Chain -- one entry per column, with
            # 'name', 'type', 'required' (true/false), and 'default'
            # (leave blank if none).
            build(..Design.Overview);
        }(
            Info<Tuple name description>,
            Fields<Chain>(
                Info<Tuple name type required default>
            )
        )
    ),
    WebPanel<Node>(
        Pages<Chain>{
            # Read design.overview. For each page the web control panel
            # needs (e.g. dashboard, guild settings, command log),
            # Pages.extend(), then write its Info Tuple's 'route' (URL
            # path), 'name', 'description', and 'auth_required'
            # (true/false -- whether Discord OAuth2 login is required to
            # view it).
            build(..Design.Overview);
        }(
            Info<Tuple route name description auth_required>
        ),
        ApiRoutes<Chain>{
            # Read web_panel.pages. For each backend API endpoint the
            # panel's own pages need to load or save their data,
            # ApiRoutes.extend(), then write its Info Tuple's 'method'
            # (GET/POST/PATCH/DELETE), 'path', 'description', and
            # 'auth_required' (true/false).
            build(Pages);
        }(
            Info<Tuple method path description auth_required>
        )
    ),
    # Src is the actual Node.js project -- leave its own PATH
    # unconfigured for now (`fatass dir set-path` once you know where it
    # should really live); every nested Dir below already carries its
    # own relative PATH matching its own name, so the whole tree
    # resolves correctly the moment Src's own root is set.
    Src<Dir>{
        # Read design.tech_stack and database.models. Write the
        # project's root-level scaffolding directly into this Dir's own
        # home directory: package.json (discord.js, express, and
        # whatever ORM/db driver tech_stack decided on, plus start/dev
        # scripts), tsconfig.json if tech_stack chose TypeScript
        # (otherwise skip it), .gitignore (node_modules, .env, database
        # files), .env.example (DISCORD_TOKEN, DISCORD_CLIENT_ID,
        # DISCORD_CLIENT_SECRET, SESSION_SECRET, DATABASE_URL, and
        # anything else the stack needs), and a README.md explaining how
        # to configure and run the bot and web panel together.
        build(Design.TechStack,Database.Models);
    }(
        Bot<Dir Bot>(
            Commands<Dir Commands>{
                # Read commands (each item's own Info and, where
                # present, Options child Chain). For each command, write
                # one discord.js SlashCommandBuilder-based command
                # module into this Dir's own home directory (one file
                # per command, named after it) -- its data
                # (name/description/options, per Options if any) and its
                # execute(interaction) handler stub with a TODO matching
                # its own description.
                build(...Commands);
            },
            Events<Dir Events>{
                # Read events (each item's own Info). For each event,
                # write one discord.js event-handler module into this
                # Dir's own home directory (one file per event, named
                # after it), exporting its event name, whether it's
                # once-only (e.g. 'ready') or recurring, and an
                # execute(...) handler stub with a TODO matching its own
                # description.
                build(...Events);
            }
        ),
        Database<Dir Database>(
            Models<Dir Models>{
                # Read database.models (each item's own Info and Fields
                # child Chain). For each model, write one ORM
                # model/schema definition into this Dir's own home
                # directory (one file per model, named after it),
                # encoding every one of its Fields (name, type,
                # required, default).
                build(...Database.Models);
            }
        ),
        Web<Dir Web>(
            Server<Dir Server>(
                Routes<Dir Routes>{
                    # Read web_panel.api_routes (each item's own Info).
                    # For each API route, write its Express route
                    # handler into this Dir's own home directory,
                    # grouped one file per resource area, wiring up its
                    # method/path and an auth-check middleware where its
                    # own auth_required is true, with a TODO matching
                    # its own description.
                    build(....WebPanel.ApiRoutes);
                },
                Views<Dir Views>{
                    # Read web_panel.pages (each item's own Info). For
                    # each page, write its server-rendered view template
                    # into this Dir's own home directory (one file per
                    # page, named after its own route), with a TODO
                    # matching its own description, and gate it behind
                    # the login check where its own auth_required is
                    # true.
                    build(....WebPanel.Pages);
                }
            ),
            Public<Dir Public>
        ),
        Shared<Dir Shared>(
            Config<Dir Config>,
            Utils<Dir Utils>
        )
    ),
    BuildLog<Chain>,
    Deployment<Chain>(
        Info<Tuple date environment version notes>
    )
)
