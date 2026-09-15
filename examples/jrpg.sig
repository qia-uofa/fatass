# One single node, using the "{...}" transforms-block syntax (see
# fatass.signature.FULL_SIGNATURE / `fatass ls -r`): each node's own
# transforms are declared right inside its own "<Type>{...}" suffix,
# bare (no node-path prefix -- the node is already known), each preceded
# by a "#" comment (multi-line where the prompt is long) holding its own
# `fatass modify` prompt -- `fatass touch -p jrpg.sig -m` reads those
# comments and, for every transform IT JUST CREATED, silently runs
# `modify` with that comment as the prompt, right after scaffolding.
# Re-running the same command later (e.g. after adding a node+transform
# here) only creates/modifies what's new -- everything already there is
# left untouched, same as `touch` itself.
#
# A dep inside a "{...}" block navigates relative to the transform's own
# node's PARENT, same as everywhere else -- a bare name reaches a
# sibling with no ".." needed, regardless of where this file is touched
# from.
Jrpg<Node>(
    Design<Node>(
        BrainStorm<Chat prompt:str="Brainstorm freely about this JRPG's core concept, world, and hook. Nothing here is final.">,
        WorldBuilding<Chat prompt:str="Explore this JRPG's world, factions, history, and cosmology in depth.">,
        ArtDirection<Chat prompt:str="Discuss and iterate on this JRPG's visual style, palette, and art references.">,
        MusicDirection<Chat prompt:str="Discuss and iterate on this JRPG's music direction, instrumentation, and mood per area.">,
        Overview<SingleMd>{
            # Read design.brain_storm's session artifacts (its home dir
            # -- see readable=[...] access) and write a structured game
            # overview to design.overview: title, tagline, one-paragraph
            # elevator pitch, genre, and target audience. Use
            # Overview.write(...).
            build(BrainStorm);
        },
        Pillars<Chain>{
            # Read design.overview. Derive 3-5 design pillars -- short,
            # memorable statements that act as tiebreakers when feature
            # ideas conflict. For each: Pillars.extend(), then write its
            # Info Tuple's 'name' and 'description' fields.
            build(Overview);
        }(
            Info<Tuple name description>
        ),
        CoreLoop<SingleMd>{
            # Read design.pillars. Write design.core_loop: the
            # moment-to-moment gameplay loop in this pillars' own terms
            # (the game's actual verbs, not generic 'explore/fight/loot'
            # placeholders) -- what the player does, how it changes game
            # state, how that state carries forward, and how the player
            # perceives the consequence. Use CoreLoop.write(...).
            build(Pillars);
        },
        Mechanics<Chain>{
            # Read design.core_loop. Break the loop down into individual
            # mechanics as 'feature briefs' -- for each: Mechanics.extend(),
            # then write its Info Tuple's 'name' (short), 'player_promise'
            # (what the player gets out of it), 'dependencies' (other
            # mechanics/systems it needs), and 'summary' (2-3 sentences,
            # buildable, not vague).
            build(CoreLoop);
        }(
            Info<Tuple name player_promise dependencies summary>
        ),
        Scope<Chain>{
            # Read design.mechanics. For each mechanic (and any other
            # feature under discussion), Scope.extend() one entry:
            # 'feature' (name), 'status' (In / Out / Maybe), 'rationale'
            # (why) -- the scope matrix, the authoritative record of what's
            # actually being built.
            build(Mechanics);
        }(
            Info<Tuple feature status rationale>
        ),
        Economy<SingleMd>,
        DecisionLog<Chain>(
            Info<Tuple date decision rationale sync_status>
        ),
        StoryOutline<SingleMd>{
            # Read design.world_building's session artifacts. Write
            # design.story_outline: a 3-act (or however many the story
            # actually needs) outline of the main plot beats. Use
            # StoryOutline.write(...).
            build(WorldBuilding);
        },
        Lore<SingleMd>{
            # Read design.story_outline and design.world_building's
            # session artifacts. Write design.lore: the world's history,
            # factions, cosmology, and whatever background the story
            # outline assumes but doesn't explain inline. Use
            # Lore.write(...).
            build(StoryOutline,WorldBuilding);
        },
        Glossary<SingleMd>{
            # Read design.lore. Extract every setting-specific term,
            # proper noun, and piece of jargon introduced there and write
            # design.glossary as an alphabetized list of term -> one-line
            # definition. Use Glossary.write(...).
            build(Lore);
        },
        ArtBible<SingleMd>{
            # Read design.art_direction's session artifacts. Write
            # design.art_bible: the visual style guide -- palette,
            # silhouette/readability rules, reference touchstones, and
            # any accessibility notes (e.g. colorblind-safe palette
            # choices) discussed there. Use ArtBible.write(...).
            build(ArtDirection);
        },
        AudioDesign<SingleMd>{
            # Read design.music_direction's session artifacts. Write
            # design.audio_design: music direction and instrumentation
            # per area/mood, plus a starter catalog of what SFX
            # categories the game will need. Use AudioDesign.write(...).
            build(MusicDirection);
        },
        UxUi<SingleMd>,
        TechnicalDesign<SingleMd>,
        ProjectPlanning<Node>(
            Milestones<Chain>(
                Info<Tuple name target_date deliverables>
            ),
            Risks<Chain>(
                Info<Tuple risk likelihood impact mitigation>
            )
        )
    ),
    System<Node>(
        Info<Tuple title currency_unit>,
        StartingParty<Chain>,
        Vocabulary<Tuple term_level term_hp term_mp term_tp term_exp>,
        BattleSystem<Tuple view_type turn_type>
    ),
    Content<Node>(
        Characters<Chain>(
            Info<Tuple name nickname profile class_name initial_level max_level>,
            Graphics<Tuple face_image character_image battler_image>,
            Stats<Tuple mhp mmp atk def mat mdf agi luk>,
            Equipment<Tuple weapon shield head body accessory>,
            Traits<Chain>(
                Info<Tuple code data_id value>
            )
        ),
        Classes<Chain>(
            Info<Tuple name>,
            ExpCurve<Tuple base_value extra_value acceleration_a acceleration_b>,
            StatGrowth<Tuple mhp mmp atk def mat mdf agi luk>,
            LearnableSkills<Chain>(
                Info<Tuple level skill>
            ),
            Traits<Chain>(
                Info<Tuple code data_id value>
            )
        ),
        Skills<Chain>(
            Info<Tuple name icon description skill_type>,
            Cost<Tuple mp_cost tp_cost>,
            Usage<Tuple occasion required_weapon>,
            Scope<Tuple faction number status>,
            Activation<Tuple speed success_rate repeats tp_gain hit_type animation>,
            Damage<Tuple type element formula variance critical>,
            Message<Tuple line1 line2>
        ),
        Items<Chain>(
            Info<Tuple name icon description item_type>,
            Price<Tuple price consumable>,
            Usage<Tuple occasion>,
            Scope<Tuple faction number status>,
            Activation<Tuple speed success_rate repeats tp_gain hit_type animation>,
            Damage<Tuple type element formula variance critical>
        ),
        Weapons<Chain>(
            Info<Tuple name icon description weapon_type>,
            Price<Tuple price>,
            ParamBonus<Tuple mhp mmp atk def mat mdf agi luk>,
            Traits<Chain>(
                Info<Tuple code data_id value>
            ),
            Animation<Tuple attack_animation>
        ),
        Armors<Chain>(
            Info<Tuple name icon description armor_type equip_slot>,
            Price<Tuple price>,
            ParamBonus<Tuple mhp mmp atk def mat mdf agi luk>,
            Traits<Chain>(
                Info<Tuple code data_id value>
            )
        ),
        Enemies<Chain>(
            Info<Tuple name image>,
            Stats<Tuple mhp mmp atk def mat mdf agi luk>,
            Rewards<Tuple exp gold>,
            Drops<Chain>(
                Info<Tuple item item_type drop_rate>
            ),
            ActionPatterns<Chain>(
                Info<Tuple skill condition rating>
            ),
            Traits<Chain>(
                Info<Tuple code data_id value>
            )
        ),
        Troops<Chain>(
            Info<Tuple name>,
            Members<Chain>(
                Info<Tuple enemy position_x position_y>
            ),
            BattleEvents<Chain>
        ),
        States<Chain>(
            Info<Tuple name icon priority>,
            Restriction<Tuple type>,
            Removal<Tuple at_battle_end by_restriction turns by_damage_percent by_walking>,
            Message<Tuple on_add on_remove>,
            Traits<Chain>(
                Info<Tuple code data_id value>
            )
        ),
        CommonEvents<Chain>(
            Info<Tuple name trigger>,
            Commands<Chain>
        ),
        Quests<Chain>(
            Info<Tuple name description>,
            Objectives<Chain>,
            Rewards<Tuple exp gold items>
        ),
        Dialogue<Chain>(
            Info<Tuple scene speaker>,
            Lines<Chain>
        ),
        Tilesets<Chain>(
            Info<Tuple name mode>,
            Images<Tuple set_a set_b set_c set_d set_e>,
            Passage<Tuple passability passage_4dir ladder damage_floor bush counter terrain_tag>
        ),
        Locations<Chain>(
            Info<Tuple name description tileset width height scroll_type encounter_steps>,
            Audio<Tuple autoplay_bgm autoplay_bgs>,
            Parallax<Tuple image loop_horizontal loop_vertical scroll_x scroll_y>,
            Connections<Chain>,
            Encounters<Chain>(
                Info<Tuple troop weight region_scope>
            ),
            Events<Chain>(
                Info<Tuple name trigger>
            )
        ),
        Shops<Chain>(
            Info<Tuple name>,
            Inventory<Chain>(
                Info<Tuple item price>
            )
        )
    ),
    # Content -> Generated "compile" pipeline: one build transform per
    # content type below, reading its Content.<Type> source Chain and
    # writing real files into this same Dir. Each dep navigates relative
    # to its OWN transform's node's parent (Project.Assets.Generated) --
    # "...." (4 dots) ascends 3 levels back to Jrpg, then descends into
    # Content.<Type>.
    Project<Dir>(
        Assets<Dir Assets>(
            Scripts<Dir Scripts>,
            Scenes<Dir Scenes>,
            Prefabs<Dir Prefabs>,
            Materials<Dir Materials>,
            Sprites<Dir Sprites>(
                Characters<Dir Characters>,
                Faces<Dir Faces>,
                Enemies<Dir Enemies>,
                SvActors<Dir SvActors>,
                SvEnemies<Dir SvEnemies>,
                Battlebacks1<Dir Battlebacks1>,
                Battlebacks2<Dir Battlebacks2>,
                Parallaxes<Dir Parallaxes>,
                Pictures<Dir Pictures>,
                TilesetGraphics<Dir Tilesets>,
                Titles1<Dir Titles1>,
                Titles2<Dir Titles2>,
                SystemGraphics<Dir System>
            ),
            Audio<Dir Audio>(
                Bgm<Dir Bgm>,
                Bgs<Dir Bgs>,
                Me<Dir Me>,
                Se<Dir Se>
            ),
            UserInterface<Dir UI>,
            Fonts<Dir Fonts>,
            Localization<Dir Localization>,
            Generated<Dir Generated>(
                Characters<Dir Characters>{
                    # Read content.characters (its Info/Stats/Equipment/Traits
                    # schema children, per item). For each
                    # character, write a Unity C# ScriptableObject-style
                    # script (or JSON asset, whichever this project's
                    # convention is -- check project.assets.scripts for
                    # an existing convention first) into this Dir's own
                    # home directory, one file per character, encoding
                    # all of its Info/Stats/Equipment/Traits fields.
                    build(....Content.Characters);
                },
                Classes<Dir Classes>{
                    # Read content.classes (Info/ExpCurve/StatGrowth/LearnableSkills/Traits
                    # per item). Generate one
                    # Unity asset per class encoding its EXP curve,
                    # per-level stat growth, and learnable-skill list.
                    build(....Content.Classes);
                },
                Skills<Dir Skills>{
                    # Read content.skills (Info/Cost/Usage/Scope/Activation/Damage/Message
                    # per item). Generate one
                    # Unity asset per skill encoding its full definition,
                    # ready for a battle system to consume.
                    build(....Content.Skills);
                },
                Items<Dir Items>{
                    # Read content.items (Info/Price/Usage/Scope/Activation/Damage
                    # per item). Generate one Unity
                    # asset per item.
                    build(....Content.Items);
                },
                Weapons<Dir Weapons>{
                    # Read content.weapons (Info/Price/ParamBonus/Traits/Animation
                    # per item). Generate one Unity
                    # asset per weapon.
                    build(....Content.Weapons);
                },
                Armors<Dir Armors>{
                    # Read content.armors (Info/Price/ParamBonus/Traits
                    # per item). Generate one Unity asset per armor
                    # piece.
                    build(....Content.Armors);
                },
                Enemies<Dir Enemies>{
                    # Read content.enemies (Info/Stats/Rewards/Drops/ActionPatterns/Traits
                    # per item). Generate one
                    # Unity asset per enemy.
                    build(....Content.Enemies);
                },
                Troops<Dir Troops>{
                    # Read content.troops (Info/Members/BattleEvents per
                    # item). Generate one Unity asset per troop,
                    # referencing its member enemies by name.
                    build(....Content.Troops);
                },
                States<Dir States>{
                    # Read content.states (Info/Restriction/Removal/Message/Traits
                    # per item). Generate one Unity asset
                    # per status effect.
                    build(....Content.States);
                },
                CommonEvents<Dir CommonEvents>{
                    # Read content.common_events (Info/Commands per
                    # item). Generate one Unity asset/script per
                    # reusable event.
                    build(....Content.CommonEvents);
                },
                Quests<Dir Quests>{
                    # Read content.quests (Info/Objectives/Rewards per
                    # item). Generate one Unity asset per quest.
                    build(....Content.Quests);
                },
                Dialogue<Dir Dialogue>{
                    # Read content.dialogue (Info/Lines per item).
                    # Generate one Unity asset per dialogue scene,
                    # preserving line order.
                    build(....Content.Dialogue);
                },
                Tilesets<Dir Tilesets>{
                    # Read content.tilesets (Info/Images/Passage per
                    # item). Generate one Unity tileset configuration
                    # asset per entry, encoding its passage rules and
                    # terrain tags.
                    build(....Content.Tilesets);
                },
                Locations<Dir Locations>{
                    # Read content.locations (Info/Audio/Parallax/Connections/Encounters/Events
                    # per item). Generate
                    # one Unity scene-configuration asset per location,
                    # referencing its tileset (content.tilesets) and
                    # encounter troops (content.troops) by name.
                    build(....Content.Locations);
                },
                Shops<Dir Shops>{
                    # Read content.shops (Info/Inventory per item).
                    # Generate one Unity asset per shop, referencing its
                    # inventory items (content.items) by name.
                    build(....Content.Shops);
                }
            )
        )
    ),
    BuildLog<Chain>,
    Playtest<Chain>(
        Info<Tuple build tester notes>
    ),
    Localization<Chain>(
        Info<Tuple language status notes>
    )
)
