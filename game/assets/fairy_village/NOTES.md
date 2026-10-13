# Fairy Village: map investigation (read-only)

Branch `castle-interiors-v2`, tip **c7128ca4** ("testing", 2026-10-04 18:24 BST). Read with raw.githubusercontent curl and the GitHub MCP tree only. Nothing cloned, committed, or pushed.
To check the overworld I rebuilt it locally. I ran the branch's own `world_map.generate_world()` (with `castle_v2.py`, `buildings_v2.py`, `housing.py`, `feature_flags.py` and their JSON, all at default flags), then applied `explore_dungeons.capture_and_hide()` the same way `server.World.__init__` does (`server.py` 1105). The maps below come from that grid, not from guesses. The checker is `src/layout.py` (`python3 src/layout.py` gives **OVERALL PASS**).

Grid: `WIDTH=200, HEIGHT=145` (`server/world_map.py` 42–43). x is the column (west to east), y is the row (north to south). Rects are `(x0, y0, x1, y1)` inclusive.

## 1. What is there today

### Starting village
- `ZONES["village"] = (1, 1, 92, 52)` (`world_map.py` 46–56). `SPAWN_POINT = (28, 24)` (line 58) is the crossroads.
- The village road runs south on **x = 27–29** (`road_x = 28`, `generate_world` line 193). Wayfinder roads `(28,16)-(28,52)` and `(28,50)-(28,56)`, plus the E–W road `(6,50)-(96,50)` (rows 49–51) (`_lay_wayfinder_roads` 867–926).
- Things near the south edge: Guard Aldric at (28, 50) ("the mine mouth is just south of here", `content.py` 1498–1499), `sign_mine` at (30, 50) ("↓ Mine", 2696), `sign_crossroads` lines "↓ Mine · Dungeon" (2668–2670), Scout Elena (`mine_scout`) at (22, 54) (1544).

### Directly south ("below"): the mine
- `ZONES["mine"] = (1, 56, 40, 88)` (`world_map.py` 51). It is generated in `generate_world` 460–483: a FLOOR rect with a WALL border, a 3-tile north mouth at **(27–29, 56)** facing the village road, a PATH stub from y 52 to 56, and 45 random ORE/IRON_ORE rolls. **39 ore tiles today** (29 ORE + 10 IRON_ORE). Copper/tin is assigned per ORE tile in `build_resource_nodes` (994–1023), so ore type does not depend on the zone.
- Giant rats: `MONSTER_SPAWNS` `content.py` 1299–1300 at (10,60) (18,64) (8,68) (24,60) (12,62) (16,72). Travel "Giant Rats" at (14, 64) (2414).
- Mine ↔ dungeon link (`world_map.py` 501–513): FLOOR rect `(36,66)-(48,76)`, x 39–41 opened on rows 68–74, a few WALL pillars, and a PATH apron `(28,68)-(36,74)` **inside** the mine.
- Wayfinder roads beside the mine: `(42,52,42,72)` (line 896, three wide, x 41–43) and `(36,71,42,71)` (line 897, rows 70–72).

### The dungeon entrance
- `INTERACTABLES` `content.py` 2482–2484: `dungeon_entrance`, kind `dungeon_entrance`, at **(46, 71)**, enter (48, 71), exit (38, 71), `dungeon_id "depths"`, `pack "skeleton_crypt"`.
- Next to it: `dungeon_bank` chest (44, 68) (2480), Hermit Cole `dungeon_hermit` (48, 70) (1551), `sign_dungeon` (40, 66) "↓ Dungeon" (2698). Travel `dungeon_gate` (38, 71), `dungeon_bank` (44, 68), `quest_hermit_cole` (48, 70) (2396–2398, plus the quest-giver list).
- Art: `client.py` 85 has `USE_NEW_ENTRANCES = True` (a hardcoded constant, not an env flag). The draw branch is `client.py` 5789–5801. It calls `dungeon_entrances.draw_pack("skeleton_crypt")` with `client/assets/dungeons/front34/skeleton_crypt_512.png` + `.json`. The scale is 2 tiles per 1.8 m. On screen the crypt is about **11 tiles wide**, rises about **10.5 tiles north** of its tile, and has a stair apron about **5 tiles south** of it. It only draws at yaw 0.
- The interior is **not** on the overworld any more. `explore_dungeons.REGIONS["depths"]` (`server/explore_dungeons.py` 15–21) has region `(44,54)-(90,143)`, pad **(43,69,50,76)**, and entrance (46,71). `capture_and_hide()` (called at `server.py` 1105) snapshots that region and turns the whole overworld copy into **GRASS**, except the pad. Overworld monster spawns inside the region are skipped (`server.py` 1109, `contains_region`). With `USE_NEW_DEPTHS_DUNGEON` (default on) the instance is the hand-authored `depths_v2.build`, which does not read the pad.
- Enter: `_find_dungeon_entrance` (`server.py` 2186) accepts the `entrance_mouth_tiles(x, y)` (`content.py` 2452: dx −1..1, dy 0/−1) or any adjacent tile. Leaving puts you back on `(spot.x, spot.y + 1)` (`server.py` 2385). **Moving the interactable is enough for enter and leave to work.** Nothing else hardcodes (46, 71) except `REGIONS["depths"]["entrance"]`. That value is the interior-side door of the legacy snapshot, so leave it alone.

### Player housing (King's Row, 10 homes + office)
`server/housing.py` `_LAYOUT` (lines 13–25) moves the pack footprints (`client/assets/housing/estate.json`) onto these plots. Live footprints after `_move`:

| key | footprint | door | exit |
|---|---|---|---|
| estate_office | (2,94)-(10,98) | (6,98) | (6,99) |
| kings_folly | (2,109)-(15,119) | (9,119) | (9,120) |
| crown_villa | (25,109)-(38,118) | (32,118) | (32,119) |
| cedar_townhouse | (16,111)-(23,118) | (20,118) | (20,119) |
| riverview_estate | (2,130)-(13,138) | (8,138) | (8,139) |
| meadow_house | (16,131)-(23,136) | (20,136) | (20,137) |
| stonehaven_row | (26,131)-(35,138) | (31,138) | (31,139) |
| ash_manor / oak_villa / reed_cottage / willow_cottage | south of the city, x 92–141, y 136–142 | | |

The estate lanes are PATH at x = 12 and x = 24 for y 99–139 (`housing.stamp` 176–). Mira spawns on the office `enter` tile. `housing.stamp` never claims x 44–90. Housing sprites rise up to 10 tiles **north** of each footprint on screen (`housing/work/json/render/*.json` "top": 10). Any grass directly north of a 3-storey house (for example x 24–39, y 99–108 above Crown Villa) is visually covered, so I did not put the mine there.

### Other things checked
- Zones are used for drawing only (`client.py` 6745–6905: `"village"`-like zones draw WALL as mountain rock, `"dungeon"` changes AO). Nothing reads `get_zone(...) == "mine"`. `ZONES["mine"]` is only read by `generate_world` (461).
- No water near the target area, and no trees inside it (the census shows the old mine is FLOOR/WALL/PATH/ORE only).
- WATER tiles become **fishing spots** (`build_resource_nodes` 1025–1060), so fountains must block with WALL, not WATER.
- Combat level: `PlayerSession.combat_level()` (`server.py` 837). Quests: `QUESTS`, `quest_status_for` (1388), `QUEST_LOG` packet (client 786). Castle ownership: `server/castle_owners.py` (deed / registry). **No clan or guild system exists on this branch** (searched server.py and content.py for "clan" and "guild"), so the clan objective needs a stub. I found **no separate objectives panel**, only the quest log.
- NPC talk: `handle_talk` (`server.py` 3520) sends `DIALOGUE` with `lines`. The client dialogue dict is at `client.py` 733.

## 2. Proposed layout (all live; no flag, per David)

### A. Fairy village footprint = the old mine zone
**`fairy_village` zone (1, 56)–(40, 88)**, 40 × 33 tiles. The mine floor, walls, ore, link rect and apron all become fairy ground. No walls ring the village, so it is open on every side.

| Feature | Tiles | Tile id |
|---|---|---|
| Moss base | (1,56)-(40,88) | GRASS (drawn as fairy moss) |
| Petal Avenue (village road continued) | (27,56)-(29,88) | PATH |
| Lantern Walk, east gate to road x 41–43 | (2,70)-(40,72) | PATH |
| Moonstone Plaza | (20,58)-(33,68) | STONE |
| Lily Court ring | (31,76)-(35,80) | STONE |
| South Walk (doors) | (4,86)-(29,87) + (20,85) | PATH |
| Apothecary door path | (37,65)-(37,69) | PATH |
| Crypt Path, SE gate to the dungeon | (30,81)-(48,83) | PATH (x 44–48 are WALL before capture, so paint them before capture and make them the new pad) |
| Avenue south to King's Row | (27,89)-(29,98) | PATH (grass today) |

Blocked footprints (WALL under the sprite; corners trimmed as in `json/collision/*.json`):

| id | footprint | door (interaction) | stand tile |
|---|---|---|---|
| `queens_tree_hall` | (4,77)-(12,85) | (8,85) | (8,86) |
| `moonpetal_inn` | (16,77)-(25,84) | (20,84) | (20,85) |
| `mushroom_apothecary` | (34,58)-(40,64) | (37,64) | (37,65) |
| `moonstone_fountain` | (26,61)-(30,65) | (28,65) | (28,66) |
| `lily_fountain` | (32,77)-(34,79) | (33,79) | (33,80) |

NPC spawns: `elowen_moonwhisper` (24,67), `warden_thorne` (25,57), `tumbleroot` (39,66), `pip_dewdrop` (31,78).
Tall sprites rise north. The big buildings sit in the south half, so their roofs cover the village's own lawns and not the starting village. The NE apothecary is 7 tiles tall and only overlaps the E–W road strip.

### B. Dungeon entrance: moved next to the village's SE gate
| | Old | New |
|---|---|---|
| `dungeon_entrance` x,y | (46, 71) | **(46, 80)** |
| enter / exit | (48,71) / (38,71) | (46,79) / (46,81) |
| mouth tiles | (45–47, 70–71) | (45–47, 79–80) |
| leave-dungeon tile (`spot.y+1`) | (46, 72) | (46, 81) |
| `REGIONS["depths"]["pad"]` | (43,69,50,76) | **(44,79,48,83)** |
| `REGIONS["depths"]["entrance"]` | (46,71) | **unchanged** (interior door of the legacy snapshot) |
| `dungeon_bank` chest + travel | (44,68) | (38,84) |
| Hermit Cole + travel | (48,70) | (40,84) |
| travel `dungeon_gate` | (38,71) | (46,81) |
| `sign_dungeon` | (40,66) "↓ Dungeon" | (41,82) "→ Dungeon" |

The crypt sprite at (46,80) covers about x 41–51, y 70–85 on screen: grass, the end of road x 41–43, and the old pad. It does not cover the village interior (x ≤ 40). Once the pad moves, `capture_and_hide` grasses the old pad by itself. Column x = 43 (outside the region) and the old link FLOOR at x 41–43, y 73–76 become GRASS through the village stamp.
**Fallback with zero risk:** leave the entrance at (46,71). It already touches the village's east gate (x 40 → road x 41–43). Use this only if the moved entrance fails the enter/leave test.

### C. Mine: moved next to the player houses
| | Old | New |
|---|---|---|
| `ZONES["mine"]` | (1,56,40,88) | **(31,90,43,98)** (walled quarry; interior (32,91)-(42,97)) |
| mouth | north (27–29, 56) | **west (31, 93–95)**, with PATH (30, 93–95) to the avenue |
| ore | 39 random | **18 fixed** (12 ORE copper/tin + 6 IRON_ORE), list in `json/mine_layout.json` |
| rats | 6 in the mine | (34,93) (37,94) (40,94) (35,95) (39,93) (33,94) |
| travel "Giant Rats" | (14,64) | (36,94) |
| sign | `sign_mine` (30,50) "↓ Mine" | keep, text "↓ Fairy Village · Mine"; add `sign_quarry` (30,92) "→ Mine" |

The quarry is one tile below the village's south edge and directly east of the avenue that leads into King's Row (estate office (2,94)-(10,98), lanes x 12/24 from y 99). It sits in the open grass band y 89–98, the only band near the houses that no house sprite covers (Crown Villa's roof covers y 99–108). It is outside the dungeon region (x ≤ 43), so rat spawns are not skipped. Today it is 100% GRASS, and the 1-tile halo around it holds no NPC, spawn, interactable or travel pin.
The old random roll (`for _ in range(45)` over the rect) would fill this small quarry. Use the fixed ore list instead.

### Checker (`python3 src/layout.py`)
All PASS. Every new NPC, door stand tile, fountain stand tile, dungeon mouth and return tile is reachable from SPAWN (28,24). Every ore has a reachable neighbour, and every rat spawn is on reachable quarry floor. 1,513 tiles change, all inside the planned rects. No house footprint changes, all 11 house exits are still reachable, and no unplanned entity sits on a changed tile. The overworld goblin (50,72) and skeleton (50,70) spawns sit on the old pad, but they are already skipped by `contains_region`.

## 3. Code touch points (for the Cursor prompt)
- `server/world_map.py`: `ZONES["mine"]` → new rect, add `ZONES["fairy_village"]`. Mine block 460–483: use the fixed ore list and the west mouth when the rect is the new one. Remove or neutralise the link/apron 501–513, which a village stamp can overwrite. Add a `fairy_village.stamp(grid, wm)` call next to `housing.stamp` (806), **before** `_lay_wayfinder_roads`. Roads: keep `(42,52,42,72)`, `(36,71,42,71)`.
- `server/explore_dungeons.py` line 19: pad → (44,79,48,83).
- `server/content.py`: the coords in the tables above (1299–1300, 1544 untouched, 1551, 2396–2414, 2480–2484, 2668–2698), plus 4 new NPCs.
- `client/client.py`: `draw_terrain_tile` (6838) gets a fairy tile branch for zone `fairy_village`. Building, fountain and NPC sprites follow the `housing_sprites.py` / `prop_sprites.py` pattern.

## Not found / caveats
- No clan or guild system on this branch (a minimal one is designed in the last section), and no dedicated objectives panel.
- `client.py` and `server.py` were read as raw files; I did not run the game itself. Cursor must confirm by running it (before/after screenshots, enter dungeon, mine ore).

## Clan system (minimal, added at David's request; objective `clan_25`)

No clan or guild code exists on `castle-interiors-v2`. Design for the smallest hook:

- **New module `server/clans.py`**. It owns two new SQLite tables, created with `CREATE TABLE IF NOT EXISTS` from `Database._migrate` (database.py line 104), the same pattern as the existing tables:
  - `clans(clan_id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE, leader_id INTEGER, created_at REAL)`
  - `clan_members(player_id INTEGER PRIMARY KEY, clan_id INTEGER, joined_at REAL)`. One clan per player. The member count is `SELECT COUNT(*)`, so it persists with the save database and needs no extra player column.
- **Pending invites** live only in memory (`{invitee_player_id: (clan_id, inviter, expires_at)}`, 120 s) and are not saved.
- **API:** `create(session, name)`, `invite(session, target_name)`, `accept(session)`, `leave(session)`, `kick(session, target_name)` (leader only), `members(clan_id)`, `clan_of(player_id)`, `member_count(clan_id)`.
  - If the leader leaves, the oldest member becomes leader. If the last member leaves, the clan is deleted.
  - Names are 3–20 characters, letters, digits and spaces only.
- **Hooks:**
  - **Server:** one early-return branch at the top of `handle_chat` (server.py 2664). Text starting with `/clan` goes to `clans.handle_command(session, text)` and is never broadcast. After any change the server pushes a `CLAN_INFO` packet (`name`, `leader`, `members[]`, `count`) to every online member.
  - **Client:** a `CLAN_INFO` handler next to `QUEST_LOG` (client.py around line 786), plus a 3-line clan summary at the top of the existing Quests sidebar tab (tabs at client.py 9575; a 5th tab would not fit the `w // 4` layout).
- **Objectives** are computed server-side for Elowen's talk and the quest log:
  - combat: `PlayerSession.combat_level()` (server.py 837);
  - castle: `castle_owners.owners(conn)` (castle_owners.py 136), owned when `owner_id == session.player_id`;
  - quests: `quest_status_for` (server.py 1388) over `QUESTS` (content.py 1811);
  - clan: `clans.member_count(...) >= 25`. Progress is shown as `14/25 members`.
- No feature flag. Clan code is applied as a separate section after the village works.
