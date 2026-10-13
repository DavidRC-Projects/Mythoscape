# Cursor prompt: Fairy Village (Moonpetal Glade) for Mythoscape

Repo: `DavidRC-Projects/Mythoscape`, branch **`castle-interiors-v2`**. Game code is under `game/assets/mmorpg/`.
Asset pack: `fairy_village_pack.zip` (David copies it into the repo). Everything you need is in the pack: `NOTES.md` (the map investigation with exact coordinates), `json/`, `dialogue/` and `assets/`.

The village is a **permanent** part of the world. There is **no feature flag**: do not add `USE_FAIRY_VILLAGE` or any other switch. When you are done:
- the village sits directly south of the starting village;
- the dungeon entrance has moved next to it;
- the mine has moved next to the player houses.

All of it is live by default.

---

## Hard rules (read first, apply to every step)

1. **Step 1 is investigation only. Change no files, report back, then STOP and wait for my go-ahead.**
2. Use small hooks. Do not rewrite or reorganise existing systems, and do not reformat files you touch.
3. **Never edit**:
   - `pose_walk` and any walk posing in `rs_style.py`;
   - `rs_humanoid.py` and `rs_humanoid_v2.py`;
   - `tools/walk_proof.py`;
   - `draw_humanoid` and `draw_humanoid_detailed`.

   The walk cycle must stay exactly as it is.
4. Do not turn off `USE_LOWPOLY_DRAGONS` or `USE_ANIM_STRIP_MONSTERS`, and do not change any other existing flag.
5. Copy the art into **`game/assets/mmorpg/assets/fairy_village/`**, keeping the pack's folder layout: `buildings/`, `fountains/`, `npcs/`, `tiles/`, `previews/`.
6. Take before and after screenshots of each area you change. They are listed under Step 6.
7. **Never merge, never push, never open a PR.** Work on a local branch, `fairy-village`, cut from `castle-interiors-v2`, and leave it for me to review.
8. If something in this prompt contradicts the code, trust the code. Report the conflict instead of guessing.

---

## Step 1: Investigate, then STOP

Confirm each point below against the current branch and report line numbers. Line numbers are from my read of `castle-interiors-v2` and may have drifted.

- **`server/world_map.py`**
  - `WIDTH=200`, `HEIGHT=145`.
  - `ZONES` (lines 46–56): `mine=(1,56,40,88)`, `dungeon=(44,54,90,143)`.
  - `SPAWN=(28,24)` (line 58).
  - The mine block (460–483: walls, mouth, 45 random ore rolls).
  - The mine↔dungeon FLOOR link and apron (501–513).
  - `housing.stamp(...)` (806), `_BUILDING_FOOTPRINTS` (814), and `_lay_wayfinder_roads` (867): roads `(42,52,42,72)` at line 896 and `(36,71,42,71)` at 897.
  - `build_resource_nodes` (994).
  - Tile ids: GRASS 0, TREE 1, WATER 2, ORE 3, WALL 4, PATH 5, FLOOR 6, IRON_ORE 8, STONE 13. `WALKABLE = {GRASS, PATH, FLOOR, FISH_SPOT, STONE}`.
- **`server/explore_dungeons.py`**: `REGIONS["depths"]`, with `pad` at line 19 = `(43,69,50,76)` and `entrance` at line 20.
- **`server/server.py`**
  - The `capture_and_hide()` call in `World.__init__` (~1105) and `contains_region` spawn skipping (~1109).
  - `_find_dungeon_entrance` and the leave-dungeon return to `(spot.x, spot.y+1)` (~2385).
  - `handle_talk` (~3520) and the `DIALOGUE` packet.
  - `PlayerSession.combat_level()` (837), `quest_status_for` (1388), `QUEST_LOG`, and `handle_chat` (2664).
- **`server/content.py`**
  - Giant rats spawns (1299–1300), Guard Aldric (1498), `mine_scout` (1544), `dungeon_hermit` (1551).
  - Travel pins `dungeon_gate` and `dungeon_bank` (2396–2398) and rats (2414).
  - `entrance_mouth_tiles` (2452), the `dungeon_bank` interactable (2480), `dungeon_entrance` (2482).
  - Signs `sign_crossroads` (2668), `sign_mine` (2696), `sign_dungeon` (2698).
  - `QUESTS` (1811).
- **`server/castle_owners.py`**: `owners(conn)` (136).
- **`server/database.py`**: `_migrate` (104) and `save_player_stats` (280).
- **`client/client.py`**
  - `USE_NEW_ENTRANCES` (85) and the entrance draw branch (~5789).
  - `draw_terrain_tile` (~6838).
  - The `DIALOGUE` handler (~733) and the `QUEST_LOG` handler (~786).
  - Sidebar tabs (~9575; 4 tabs at `w // 4`) and how housing or prop sprites are loaded and depth-sorted (`housing_sprites.py`, `house_sprites.py`).
- **Map checks** (render the map or print the grid around them):
  - The mine rect `(1,56,40,88)` really is the area directly south of the starting village.
  - The grass band `(31,90,43,98)` is empty: no NPC, spawn, interactable, travel pin or house sprite.
  - The crypt sprite at `(46,80)` would not cover anything important.

Report what you found, including anything that differs from `NOTES.md`, then **STOP**.

---

## Step 2: Map changes (after my go-ahead)

All coordinates come from `NOTES.md` §2 and `json/`. The checker `src/layout.py` in the pack encodes the same plan.

### 2a. Fairy village zone
- Add `ZONES["fairy_village"] = (1, 56, 40, 88)`.
- Add a small module `server/fairy_village.py` with `stamp(grid)`. It applies the paint ops from `json/village_layout.json` in order (GRASS base, PATH and STONE strips), then stamps WALL on every `blocked_tiles` cell of each `json/collision/*.json`.
  - Fountains must be WALL, **never WATER**. WATER would turn them into fishing spots.
- Call it next to `housing.stamp(...)` (~806), **before** `_lay_wayfinder_roads`. Keep roads `(42,52,42,72)` and `(36,71,42,71)`.

### 2b. Mine moves next to the player houses
- Change `ZONES["mine"]` to `(31, 90, 43, 98)`.
- In the mine block (~460–483), when the rect is the new one:
  - draw a WALL ring with FLOOR inside `(32,91)-(42,97)`;
  - put the mouth on the **west** side at `(31,93..95)`, with PATH at `(30,93..95)` joining the avenue;
  - place the **18 fixed ore tiles** from `json/mine_layout.json` (12 ORE, 6 IRON_ORE) instead of the 45 random rolls, which would fill the small quarry.
- Remove or neutralise the mine↔dungeon link and apron (~501–513), because the village now covers that area.
- **content.py**:
  - giant rats → `(34,93) (37,94) (40,94) (35,95) (39,93) (33,94)`;
  - travel pin "Giant Rats" `(14,64)` → `(36,94)`;
  - `sign_mine` text → `"↓ Fairy Village · Mine"`;
  - add `sign_quarry` at `(30,92)` facing east, `"→ Mine"`.

### 2c. Dungeon entrance moves next to the village
| | old | new |
|---|---|---|
| `dungeon_entrance` | (46,71) | **(46,80)** |
| `entrance_mouth_tiles` | (45–47, 70–71) | **(45–47, 79–80)** |
| `REGIONS["depths"]["pad"]` | (43,69,50,76) | **(44,79,48,83)** |
| `REGIONS["depths"]["entrance"]` | (46,71) | **unchanged** |
| `dungeon_bank` interactable + travel pin | (44,68) | (38,84) |
| Hermit Cole (`dungeon_hermit`) + its travel pin | (48,70) | (40,84) |
| travel `dungeon_gate` | (38,71) | (46,81) |
| `sign_dungeon` | (40,66) "↓ Dungeon" | (41,82) "→ Dungeon" |

- The Crypt Path `(30,81)-(48,83)` must be PATH **before** `capture_and_hide()` runs, because x 44–48 are WALL today. `capture_and_hide()` then grasses the old pad by itself.
- **Fallback:** if enter or leave fails at `(46,80)` and cannot be fixed with a one-line change, put the entrance back at `(46,71)` (old pad and old tiles). It still touches the village's east gate. Tell me if you had to do this.

### 2d. Fairy terrain look
- In `draw_terrain_tile`, add one branch: tiles inside `ZONES["fairy_village"]` draw the pack's seamless tiles instead of the default grass, path and stone:
  - GRASS → `tiles/fairy_moss_*`;
  - PATH → `tiles/petal_path_*`;
  - STONE → `tiles/moonstone_paving_*`.
- Use the 40, 80 or 160 px variant that matches the current zoom.

### 2e. Check nothing overlaps (required, because there is no switch)
Write `tools/fairy_village_check.py`, or run equivalent asserts once and paste the output into your report. It must confirm:
1. Every changed tile lies inside the planned rects: the village zone, the quarry ring, the crypt path and pad, and the avenue `(27,89)-(29,98)`.
2. No house footprint, house exit, castle tile or existing NPC, interactable or travel pin sits on a changed tile, except the ones this prompt moves.
3. From `SPAWN (28,24)`, a BFS over `WALKABLE` reaches:
   - every fairy NPC tile;
   - every door and fountain `stand_tile`;
   - all 6 dungeon mouth tiles and the return tile `(46,81)`;
   - one neighbour of every ore tile;
   - every rat spawn.
4. The crypt sprite (about 11 tiles wide, rising about 10.5 tiles north, apron 5 tiles south) does not cover any fairy building or NPC.

---

## Step 3: Buildings, fountains, NPC sprites

- Load sprites the same way `housing_sprites.py` / `house_sprites.py` do. Depth-sort by the footprint's south edge.
- Each `assets/buildings/<id>/meta.json` and `assets/fountains/<id>/meta.json` gives:
  - `origin_px`: the pixel of the footprint's NW corner;
  - `tiles`: the overhang in tiles;
  - the PNG at 1x (40 px/tile), 2x and 4x.
- Fountains have 10 frames (`frames/f00..f09.png`) that loop at about 10 fps.

| id | footprint (x0,y0)-(x1,y1) | door / interact tile | stand tile |
|---|---|---|---|
| `queens_tree_hall` | (4,77)-(12,85) | (8,85) | (8,86) |
| `moonpetal_inn` | (16,77)-(25,84) | (20,84) | (20,85) |
| `mushroom_apothecary` | (34,58)-(40,64) | (37,64) | (37,65) |
| `moonstone_fountain` | (26,61)-(30,65) | (28,65) | (28,66) |
| `lily_fountain` | (32,77)-(34,79) | (33,79) | (33,80) |

- **Doors.** Clicking a door tile from its stand tile shows a one-line flavour message. The buildings are not enterable in v1.
  - "The Queen's Tree-Hall hums with old magic."
  - "The Moonpetal Inn smells of honey bread."
  - Tumbleroot's door opens his shop if `content.py` has a simple shop pattern you can reuse; otherwise the same flavour message.
- **Fountains.** The interaction "Drink Moonwater" heals a small amount once per minute (reuse any existing heal helper) and shows a message.
- **NPCs** go in `content.py` as normal NPC entries, using the existing NPC dict pattern. Spawns come from `json/npc_spawns.json`:

| id | name | tile | role / sprite folder |
|---|---|---|---|
| `elowen_moonwhisper` | Lady Elowen Moonwhisper | (24,67) | story fairy, no wander |
| `warden_thorne` | Warden Thorne Briarwing | (25,57) | elder / gate guard |
| `tumbleroot` | Tumbleroot the Gnome | (39,66) | potion shopkeeper |
| `pip_dewdrop` | Pip Dewdrop | (31,78) | child fairy gardener |

- Sprites live in `assets/npcs/<id>/sprite_{1x,2x,4x}/{s,e,n,w}/f00..f07.png`.
  - The 1x canvas is 96×128 with the feet at (48,118). `meta.json` holds `feet_px`.
  - Frame 0 is the idle for that facing. f00–f07 is the idle / wing-flutter loop at about 8 fps.
  - Draw NPCs through the existing NPC sprite path if there is one. **Do not** route them through `draw_humanoid`, `draw_humanoid_detailed` or the walk-cycle code.

---

## Step 4: Elowen's story dialogue and the 4 objectives

- Data: `dialogue/fairy_story.json` (`pages`, `objectives`, `repeat_pages`, and `other_npcs` for the other three NPCs).
- Talking to `elowen_moonwhisper` opens the `DIALOGUE` packet with her pages in order: 2–3 lines per page, Next / Close as in existing dialogues. Show her portrait `assets/npcs/elowen_moonwhisper/portrait_bust.png` if the dialogue box already supports portraits; otherwise skip the portrait.
- The first talk starts quest `fairy_oath`, "The Moonwater Oath", in the existing quest log.
- Later talks show `repeat_pages.in_progress`, with `{objectives_status}` filled in. Once all four objectives are done, show `repeat_pages.all_done`.
- The objectives are computed **server-side from real data** every time she is talked to and every time the quest log is sent:

| id | done when | progress text |
|---|---|---|
| `combat_100` | `session.combat_level() >= 100` | `Combat 64/100` |
| `buy_castle` | any row of `castle_owners.owners(conn)` has `owner_id == session.player_id` | `Castle 0/1` |
| `all_quests` | every quest in `QUESTS` (except `fairy_oath` itself) has `quest_status_for(session, q)["status"] == "complete"` | `Quests 9/14` |
| `clan_25` | the player's clan has **25 or more members** (Step 5) | `14/25 members` |

- Show the four lines with ✓ or progress in Elowen's dialogue, and in the quest log entry for `fairy_oath`. There is no separate objectives panel on this branch, so do not add one.
- Until Step 5 exists, `clan_25` shows `0/25 members` and is never auto-completed.
- The other three NPCs get their short `other_npcs` lines through the same dialogue path.

---

## Step 5: Minimal clan system (separate section; do this only after Steps 2–4 work)

This supports `clan_25`. Keep it small, with no flag and no rewrites. The design is in `NOTES.md`, last section.

- **New module `server/clans.py`.**
  - Create two tables from `Database._migrate` with `CREATE TABLE IF NOT EXISTS`, following the existing pattern:
    - `clans(clan_id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE, leader_id INTEGER, created_at REAL)`
    - `clan_members(player_id INTEGER PRIMARY KEY, clan_id INTEGER, joined_at REAL)`
  - One clan per player. Membership is saved in the same SQLite save file, so the member count is persistent.
  - Functions: `create(session, name)`, `invite(session, target_name)`, `accept(session)`, `leave(session)`, `kick(session, target_name)`, `members(clan_id)`, `clan_of(player_id)`, `member_count(clan_id)`.
  - Rules:
    - names are 3–20 characters, letters, digits and spaces;
    - only the leader can invite and kick;
    - invites are held in memory for 120 s;
    - if the leader leaves, the oldest member becomes leader;
    - when the last member leaves, delete the clan.
- **Smallest hook: chat commands.** At the top of `handle_chat` (~2664), text starting with `/clan` goes to `clans.handle_command(session, text)` and returns without broadcasting:
  - `/clan create <name>`
  - `/clan invite <player>`
  - `/clan accept`
  - `/clan leave`
  - `/clan kick <player>`
  - `/clan list` (members, with the leader marked, and `N/25 members`)
  - `/clan` (help)

  Reply to the sender with the existing system-message or chat packet.
- After any change, push `CLAN_INFO {name, leader, members[], count}` to every online member. Also push it on login.
- **Client:** add a `CLAN_INFO` handler next to the `QUEST_LOG` handler, and draw a 3-line clan summary at the top of the existing **Quests** sidebar tab: clan name, leader, `14/25 members`. Do not add a 5th tab, because the 4-tab row uses `w // 4`.
- `clan_25` reads `clans.member_count(clans.clan_of(player_id)) >= 25`.
- Test with two local clients. Create a clan, invite, accept, then leave and kick. Restart the server and confirm the clan and member count survive.

---

## Step 6: Verify (required) and screenshots

Run the game locally and confirm each of the following, pasting the evidence into your report:

1. **Dungeon:** walk from spawn down the Crypt Path to `(46,80)` and enter the dungeon. Leave it and confirm you come out at `(46,81)` on walkable ground. The dungeon bank `(38,84)` and Hermit Cole `(40,84)` work.
2. **Mine:** walk to the quarry `(31,93)`, mine at least one copper/tin ore and one iron ore, and confirm the ore respawns. Giant rats spawn and can be fought inside the quarry. The "Giant Rats" travel pin lands at `(36,94)`.
3. **Village:**
   - all 4 NPCs stand on their tiles;
   - Elowen's dialogue plays fully, and objective progress shows real numbers;
   - doors and fountains respond from their stand tiles;
   - you cannot walk through buildings or fountains, and fountains are not fishing spots.
4. **No overlap:** paste the output of the Step 2e checker. Confirm the starting village, King's Row houses, roads and castle look unchanged.
5. **Walk cycle:** `git diff --stat` shows no change to any protected file listed in Hard rules §3. Your character still walks normally.
6. **Clan:** the Step 5 tests pass, and the Quests tab shows `N/25 members`.

**Screenshots** (before and after, saved to `game/assets/mmorpg/tools/screens/fairy_village/`):
- the starting village looking south;
- the village plaza with the Moonstone Fountain and Elowen;
- the Tree-Hall and Inn row;
- the apothecary;
- the dungeon entrance;
- the quarry beside King's Row;
- Elowen's dialogue with objectives;
- the clan summary in the Quests tab.

Then stop. **Do not merge or push.** Report the files you changed, the checker output, the screenshots, and anything you had to deviate on.
