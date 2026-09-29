# Void Sanctum v2: dungeon design

**Goal:** turn today's single open room into a 25–35 minute **descent**. Monsters get stronger the deeper you go. The route has locked seals and keys, secret rooms, lore, loot, a narrow bridge over the void and a named boss. Everything sits behind `USE_NEW_VOID_DUNGEON` (default off), and the old Sanctum stays as it is.

**Images:**
- `void_map_full.png`: full map with legend, route and a "before" inset
- `void_zones_gamescale.png`: each zone at game tile size 40, plus a fog-of-war mock
- `void_bridge_boss_closeup.png`
- `void_secret_wall_before_after.png`
- `void_locked_door_and_key.png`

**Data:** `reference_code/void_map.py` (source of truth) and `void_map.json` (the same data exported).

## 1. Layout: a 66 × 100 descent
Enter at the top (the EXIT portal stays where players expect it) and work south. Each zone is sealed from the next.

| # | Zone | Level band | Theme and floor | Gate to the next zone |
|---|---|---|---|---|
| 1 | **Entry Hall** | 55 (shades) | Violet flagstones, sconces, broken pillars | Open corridor |
| 2 | **Shattered Galleries** | 62, mini-boss 68 | Two cracked grey galleries around a hub; sarcophagi | **Door A**: Amethyst Seal |
| 3 | **Hollow Barracks** | 70 / 78 | Brown flagstones, bunk cells on the north wall, weapon racks | **Door B**: Obsidian Seal |
| 4 | **Crystal Depths** | 82 / 88, mini-boss 92 | Blue-violet floor with crystal glints; crystal clusters | **Door C**: Rift Seal |
| 5 | **The Rift Edge** | 91 / 95 | Dark floor with glowing violet fissures | Healing shrine, warning stone, shortcut lever |
| 6 | **The Narrow Way** | Void wind | A 1-tile obsidian bridge over the abyss, 13 tiles long, with 3 rune anchors | |
| 7 | **Eclipse Throne** | Boss, lv 110 | Black oval arena with gold eclipse rings and 4 pylons | |
| S | Whispering Passage | Shortcut | Long dark corridor from the Rift Edge back up to the Entry Hall | Gate opens from the far side only |

### Tile map
Legend:

| Char | Meaning | Char | Meaning |
|---|---|---|---|
| `#` | wall | `.` | floor |
| `~` | abyss | `=` | bridge |
| `a` | rune anchor | `A` `B` `C` | locked seals |
| `X` | shortcut gate | `S` | cracked secret wall |
| `h` | hidden floor | `E` | exit |
| `P` | spawn | `H` | shrine |
| `c` | chest | `k` | key pedestal |
| `l` | lore note | `g` | supply cache |
| `$` | ground loot | `v` | lever |
| `o` | pylon | `i` | pillar / crystal / rack (blocked) |
| `w` | warning stone | `r` | rift pool |
| `b` | boss | | |

```
##################################################################
##################################################################
################################E#################################
########################.................#########################
########################........P........#########################
#############hhhhhhh####..i...........i..#########################
#############hhchhhh####.................#########################
#############hhhhhhh####.................#########################
#############hhhhhhhhhhS.................#########################
#############hhhhhhh####.................X....................####
#############hlhh$hh####.................###################..####
#############hhhhhhh####..i...........i..###################..####
########################.g.............l.###################..####
########################.................###################..####
###############################...##########################..####
###############################...##########################..####
###############################...##########################..####
###############################...##########################..####
#####.....................#...........#...................##..####
#####.c...................#...........#...................##..####
#####...............i.................................i...##..####
#####....ii................................i..............##..####
#####.....................................................##..####
#####.....................#...........#...................##..####
#####.....................#...........#...................##..####
#####..........i..........#####...#####.........ii........##..####
#####.....................#####...#####...................##..####
#####.....................#####...#####...................##..####
#####.......i........i....#####...#####.....i........i....##..####
#####...................l.#####...#####.................$.##..####
#####.....................#####...#####...................##.l####
################################A###########################..####
################################.###########################..####
###############################...##########################..####
###########......#......#.............#......#......########..####
###########.$....#......#.............#......#....c.########..####
###########......#......#.............#......#......########..####
###########......#......#.............#......#......########..####
#############.######.######.###....######.######.###########..####
###hhhhhh#.............................................#####..####
###hchhhh#.............................................#####..####
###hhhhhh#.............................................#####..####
###hhkhhhS........i......i.............i......i........#####..####
###hhhhhh#.............................................#####..####
###hhhhlh#.............................................#####..####
###hhhhhh#....................g...............l........#####..####
##########.............................................#####..####
################################B###########################..####
################################.###########################..####
#############.....................................##########..####
#############.....................................##########.l####
####....i..................i.........i................i....#..####
####...............i..........................i............#..####
####..........................g............................#..####
####.......i...............................................#..####
####...................i.................................i.#..####
####.....................................i.................#..####
####..........i...................................i........#..####
####.l...................................................c.#..####
####.......................................................#..####
################################C############S##############..####
################################.############h##############..####
##############...........................##hhhhhh###########..####
##############.........................$.##hchhlh###########..####
##############...i...................i...##hhhhhh###########..####
##############...........................###################..####
##############.....................................#########..####
##############........i..........................v............####
##############..............................i......###############
##############.............i.......................###############
##############.l................H..................###############
##############................w....................###############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~aa~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~aa~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~aa~~~~~~~~~~~~~~~~~~~~#############
############~~~~~~~~~~~~~~~~~~~~=~~~~~~~~~~~~~~~~~~~~#############
############################.........#############################
#######################...................########################
####################.........................#####################
##################.....o.................o.....###################
#################...............................##################
################.................................#################
################...r.........................r...#################
################................b................#################
################.................................#################
#################...............................##################
##################.....o.................o.....###################
####################.........................#####################
#######################...................########################
##################################################################
##################################################################
```

**Checked by `tools/void_render.py validate()`:**
- no keys: the Barracks and the boss can't be reached;
- Door A only: the Crystal Depths can't be reached;
- Doors A and B: the Rift Edge can't be reached;
- everything open: every chest and the boss can be reached;
- the Obsidian Key needs its secret;
- the shortcut lever alone connects the Entry Hall to the Rift Edge;
- every spawn is on floor.

## 2. Monsters
Existing types are reused wherever possible. The 5 new types only add a `MONSTERS` entry that reuses an existing drawer (`visual`) with a small tint.

| Zone | Monster | Lvl | Count | Respawn (in instance) | Drops (new or notable) |
|---|---|---|---|---|---|
| Entry Hall | Shade (existing) | 55 | 5 | 50 ticks ×1.5, only when no player is within 8 tiles | existing table |
| Galleries | Crypt Ghoul (existing) | 62 | 8 | 55 ×1.5 | existing |
| Galleries | **Gallery Warden** (new; crypt_ghoul visual, gold tint, 1.2× scale) | 68 | 1 | never per visit | **Amethyst Key 100%**, coins 300–600, mithril piece 15% |
| Barracks | Void Imp (existing) | 70 | 6 | 55 ×1.5 | existing |
| Barracks | Obsidian Colossus (existing) | 78 | 4 | 70 ×1.5 | existing |
| Crystal Depths | **Void Crawler** (new; void_imp visual, blue tint) | 82 | 5 | 60 ×1.5 | onyx 10%, crystal shard (lore/craft, optional) |
| Crystal Depths | Shadow Knight (existing) | 88 | 5 | 80 ×1.5 | existing |
| Crystal Depths | **Knight-Captain Vorn** (new; shadow_knight visual, red tint, 1.2×) | 92 | 1 | never | **Rift Sigil 100%**, mythos_dagger/helmet 6%, coins 600–1200 |
| Rift Edge | **Rift Wraith** (new; shade visual, violet tint) | 91 | 4 | 80 ×1.5 | void_ring 1.5%, super potions |
| Rift Edge | Void Horror (existing) | 95 | 3 | 140 ×1.5 | existing |
| Eclipse Throne | **Nyxarath, the Hollow Eclipse** (new; void_horror visual at 1.9× with a gold eclipse halo) | 110 | 1 | never (re-enter for another kill) | see §6 |

That's 43 monsters, up from 18.

**Suggested stats for the new types** (the same curve as the neighbours):

| Monster | HP | Att / Str / Def | def_bonus | xp | attack_range |
|---|---|---|---|---|---|
| gallery_warden | 190 | 62 / 66 / 55 | 26 | 520 | |
| void_crawler | 170 | 80 / 82 / 70 | 36 | 520 | |
| knight_captain_vorn | 320 | 100 / 108 / 96 | 52 | 1100 | |
| rift_wraith | 210 | 98 / 102 / 88 | 46 | 700 | 2 |
| nyxarath | 900 | 125 / 135 / 115 | 60 | 4000 | 3 |

**Progression rules** (server, flagged):
1. Use `aggro_range` inside the v2 dungeon, so monsters wake as you approach instead of the whole room at once. Keep the 2-pursuer cap.
2. `home_room` is the monster's **zone rect**, so a leash never pulls monsters through a seal.
3. In-instance respawn: normal mobs respawn after `respawn_ticks × 1.5`, but only if the player is more than 8 tiles away. Mini-bosses and the boss never respawn during a visit.

## 3. Keys and locked seals
| Seal | Tile | Key | Where the key comes from |
|---|---|---|---|
| A: Amethyst Seal | (32, 31), Galleries → Barracks | `void_key_amethyst` | Gallery Warden, 100% drop straight into the inventory |
| B: Obsidian Seal | (32, 47), Barracks → Crystal Depths | `void_key_obsidian` | Pedestal in the **Quartermaster's Cache** (secret, Barracks west wall) |
| C: Rift Seal | (32, 60), Crystal Depths → Rift Edge | `void_rift_sigil` | Knight-Captain Vorn, 100% drop |

**Key items:**
- flags: `type: "key"`, `stackable: False`, `tradeable: False`, `sellable: False`, `dungeon_bound: "sanctum_v2"`;
- where they're removed: on `handle_leave_dungeon`, on login (disconnect safety) and on death;
- they can't be dropped or banked.

**Unlocking:**
- The player clicks the seal to send `DUNGEON_INTERACT {x, y}`.
- The server checks: the player is adjacent, the seal is still locked in `session.dungeon["opened"]`, and the key is in the inventory.
- If all pass, it consumes the key, adds the seal to `opened`, sets the tile to FLOOR in the session copy, and sends `DUNGEON_TILES {changes: [[x, y, FLOOR]]}` plus chat.
- If the key is missing, the player gets the hint text (for example "It needs an Amethyst Key; the Gallery Warden carries one.").

**Per-player state:** the Sanctum is already a private instance (see the code review), so seal state is just `session.dungeon["opened"]`. Another player's seals are never affected, and every new visit starts locked.

**Look:** the game's own `draw_door`, plus a glowing sigil in the key's colour and chains; the seal opens with the door-open frame. Key icons are coloured to match their seal (amethyst, gunmetal, ember red) and stay readable at the 36 px inventory size (see `void_locked_door_and_key.png`).

## 4. Secret entrances
| Secret | Wall tile | Behind it | Hint text |
|---|---|---|---|
| **Hidden Reliquary** | (23, 8), Entry Hall west wall | Chest, ground loot, lore 2 | "A draught whistles through a crack in the stone." |
| **Quartermaster's Cache** | (9, 42), Barracks west wall | **Obsidian Key** pedestal, chest, ledger | "These bricks are newer than the rest… and loose." |
| **The Starwell** | (45, 60), Crystal Depths south wall | Rare chest, Selwyn's last page (the lore finale) | "Faint starlight leaks from beneath the crystal." |

**How it plays:**
- **Visual hint:** the wall block is a touch lighter, with a jagged crack, a few chips on the floor beside it and 2–3 slow pale motes drifting out (see `void_secret_wall_before_after.png`). It's noticeable if you look, invisible if you're rushing.
- **Interaction:** click it and the context label reads "Search Cracked wall". Searching takes one tick. The server then checks adjacency, turns the wall and hidden tiles to FLOOR in the session copy, and sends a `DUNGEON_TILES` patch with the message "You push the loose stones. A hidden passage grinds open!"
- **No leaks:** hidden tiles (`h`) are sent as WALL until revealed, so the minimap and fog can't give them away.

## 5. Items around the place
- **Chests (6), per player, once per visit.** Opening one rolls its loot table straight into the inventory, and the chest shows its open frame afterwards.

  | Chest | Loot |
  |---|---|
  | `gallery_chest` | coins 200–500, super attack, mithril arrows |
  | `barracks_chest` | coins 300–700, adamant piece 10%, food |
  | `crystal_chest` | coins 500–900, onyx, super defence |
  | `reliquary_chest` | ruby/diamond ring or amulet (one), coins 400 |
  | `quartermaster_chest` | adamant bars, potions |
  | `starwell_chest` | coins 1500, void_ring 5%, void_amulet 4%, onyx ×2 |

- **Supply caches (3):** Entry, Barracks and Crystal Depths. Once per visit each, they give 3 cooked lobster and 1 health potion, which keeps runs sustainable.
- **Ground loot piles (4):** pre-placed per-instance ground items (coins, arrows, a gem). They need the new `session.dungeon["ground"]`, which also fixes the drop bug.
- **Lore notes (10):** the story of the Circle of Selwyn opening the Rift and feeding their light to Nyxarath (texts in `void_map.py` `LORE`). Clicking one opens a small parchment modal; reading all 10 could later reward a title or cosmetic (optional).
- **Healing shrine (checkpoint):** at the Rift Edge by the bridge head. Standing next to it restores 50% HP once per visit and sets the **respawn point** for the visit: dying past the shrine returns you there with the dungeon state kept, instead of kicking you out.

## 6. The bridge and the boss
### The Narrow Way (bridge)
- **Layout:** 1 tile wide, 13 tiles long, over a starfield abyss (the abyss is blocked, like water). There are 2-wide **rune anchors** at y = 75, 79 and 83.
- **Void wind (kept simple):**
  - Every 10 s a gust is telegraphed 2 s ahead (violet streaks and a chat or overhead line).
  - If the player is on a plain bridge tile when it lands, they take 8 damage and are **pushed 2 tiles back** toward the Rift Edge.
  - Standing on an anchor is safe.
  - There's no falling or instant death, and it works purely on the tile grid.
- **Warning stone:** at the bridge head it shows "Beyond lies Nyxarath…" with a recommended combat level and [Cross] / [Not yet]. It appears once per visit, as a client-only modal.

### Nyxarath, the Hollow Eclipse (lv 110)
The arena is an oval with 4 **eclipse pylons** and 2 **rift pools**. A **boss health bar** shows at the top while you're in the arena. The boss is confined to the arena and leashes back to the throne.

| Phase | HP | Mechanic (every mechanic is a telegraphed tile effect) |
|---|---|---|
| 1: Umbra | 100–66% | Melee plus **Umbral Orbs**: 3 tiles near the player glow for 2 s, then deal 25 damage. Step off them. |
| 2: Rift Tide | 66–33% | Summons 2 **Void Crawlers** from the rift pools (one wave per 20 s, max 2 alive). Nyxarath takes 50% damage while adds are alive. The orbs continue. |
| 3: Eclipse | 33–0% | The arena darkens. Every 6 s an **Eclipse Pulse** hits for 30 unless you stand within 1 tile of a lit pylon. Each pulse snuffs one pylon until it relights 12 s later, so you move around. |

**Loot:**

| Drop | Chance |
|---|---|
| coins | 100% (2,000–5,000) |
| dragon_bones | 100% |
| onyx | 100% (2–4) |
| super potion bundle | 60% |
| adamantite_bar ×3 | 40% |
| void_amulet | 10% |
| void_ring | 12% |
| mythos piece (longsword, body or shield) | 6% |
| Eclipse piece (helmet, legs, body or shield) | 1/60 each |
| cosmetic pet "Voidling" (optional) | 1/250 |

Eclipse gear is currently commented out as "not enabled yet" in `server/content.py:977-980`, so enabling it is David's call. The first kill also sends a gold global chat line, reusing the Tidehollow completion pattern.

## 7. Extra fun and UX (in priority order)
1. **Zone banners:** a centred banner fades in for 2.5 s when you cross into a zone ("Hollow Barracks · Lv 70s"). This is client-only, from the zone rects.
2. **Fog of war:** the client keeps a per-visit explored set (radius 7) and draws unexplored tiles dark. The minimap only paints explored tiles. This is client-only, since hidden rooms are already masked by the server.
3. **Boss health bar and phase name** at the top of the screen in the arena.
4. **Permanent shortcut:** a lever at the Rift Edge opens the Whispering Passage gate into the Entry Hall. It's stored per player (`quest_progress` row `void_shortcut`, so no schema change). Re-runs can go Entry → passage → Rift Edge → bridge → boss.
5. **Warning before the boss** (the warning stone modal) and a **checkpoint** at the shrine.
6. **Ambient danger:**
   - a vignette that deepens with zone depth;
   - occasional whisper lines in chat from lore snippets (at most one per 60 s);
   - a slow pulse on the rift fissures and abyss.
7. **Threat colours on level badges** relative to the player (already in the client: `monster_threat_color`).
8. **Optional later:** a run timer and personal best, shown when the boss dies.

**Deliberately out of scope:** co-op instances, falling deaths, puzzles beyond keys and levers, new art packs, and changes to other dungeons.

## 8. Implementation shape (for Cursor)
- **New files:**
  - `server/void_v2.py`: map data, `build(session)`, interaction handlers, boss tick;
  - `client/void_v2_client.py`: tile drawers, banners, fog, boss bar, seal and secret drawing.
- **Hooks into existing code:** 1 in `explore_dungeons.build`, 1 in `handle_enter_dungeon`, 1 new message type, and 1 tick hook in `game_loop`. The client adds a draw hook and a click hook.
- **Tiles:**
  - The server tiles stay WALL/FLOOR. The abyss is sent as WALL, with a separate `decor` layer that tells the client to draw it as abyss.
  - Seals, the gate and secrets are WALL until opened.
  - The bridge is FLOOR, so walkability stays tile-grid only.
- **Don't call `widen_single_file_passages`** on this map.
- **Flag off:** today's Sanctum is untouched.

## 9. Honest score
**8/10 as a design** against a good OSRS dungeon (Stronghold of Security, Kourend Catacombs feel).
- **What it does well:**
  - a real descent with a clear level ramp;
  - gated progression that needs exploration (one key is hidden behind a secret);
  - secrets with fair hints;
  - lore that pays off at the boss;
  - a readable bridge hazard;
  - a boss with three distinct, telegraphed phases;
  - a permanent shortcut for re-runs.
- **Why not 9:**
  - The layout is still rectangular-room based rather than organic caverns.
  - The new monsters are tinted re-uses of existing drawers, and Nyxarath is a scaled Void Horror with a halo, not bespoke art.
  - The concept images use prototype tile drawers, not final art.
