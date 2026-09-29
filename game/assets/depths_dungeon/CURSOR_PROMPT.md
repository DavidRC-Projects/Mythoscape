# Cursor prompt: The Depths v2 (crypt descent, new Depths dungeon interior)

You are working in the Mythoscape repo (`game/assets/mmorpg/`). Read `DEPTHS_CODE_REVIEW.md` and `DEPTHS_DUNGEON_DESIGN.md` first; the review refers to `VOID_CODE_REVIEW.md` for the shared systems. Use `reference_code/depths_map.py` (the map data) as the source of truth for the layout.

## Ground rules (every step)
- **Flag:** everything goes behind `USE_NEW_DEPTHS_DUNGEON` in `server/feature_flags.py`, default `"0"`. With the flag off, the game must behave exactly as today, including the old Depths (ore rooms, giants, the Adamant Dragon).
- **Small incremental edits.** Add new files (`server/depths_v2.py`, `client/depths_v2_client.py`) and hook into existing code with **small `if USE_NEW_DEPTHS_DUNGEON:` early branches**. **Never rewrite or reformat existing functions.**
- **Shared systems: reuse, don't duplicate.** The Void Sanctum v2 pack specifies the same systems: doors and keys, secret walls, chests and caches, per-instance ground items, fog of war and the minimap, zone banners, the boss bar and telegraphs, in-instance respawn, the shrine checkpoint, and the shortcut lever.
  - **If they're already built** (for example `server/dungeon_v2_common.py`, `client/dungeon_v2_common_client.py`, or code in `void_v2.py`), **REUSE them.** Where they're void-specific, pull the generic part into a shared module with small edits that keep the Void working. Don't copy them into `depths_v2.py`.
  - **If they don't exist yet**, build them **generically** in `server/dungeon_v2_common.py` and `client/dungeon_v2_common_client.py`. Drive them from map data (`DOORS`, `KEYS`, `SECRETS`, `CHESTS`, `SUPPLY_CACHES`, `LORE`, `ZONES`, `SHRINE`, `LEVER`) so the Void Sanctum v2 can use them unchanged. Only crypt-specific things go in the `depths_v2*` files: tile art, the sarcophagus roll, grasping hands and Morvath.
- **Don't touch:**
  - other dungeons (the Void Sanctum's own content, Tidehollow, Emberdeep) beyond the shared-module extraction above;
  - the walk animation;
  - the characters work (`rs_humanoid*`, `gear_v2`, `armour_v2`);
  - the buildings, castle and props packs;
  - overworld mining or the `world_map.py` generator.
- **Keep:** the entrance at (46,71), the pad and the dungeon bank chest.
- **Don't call `widen_single_file_passages`** on the v2 map.
- **Screenshots:** take before and after screenshots at the end of each phase (same camera, same spot). Save them to `docs/depths_v2/phase_<X>_{before,after}.png`.
- **Git:** never merge, push or open a PR. Commit locally per phase only if asked.
- **STOP** at the end of each step and wait for approval.

## Step 1: investigate only, then STOP
Confirm (or correct) these points from `DEPTHS_CODE_REVIEW.md` with file:line references, and change nothing:
1. The Depths is the `depths` explore dungeon: `explore_dungeons.py` region, `DUNGEON_META`, and the `dungeon_entrance` interactable at (46,71). `skeleton_crypt` is only its entrance art pack.
2. Its interior comes from `world_map.py` (the zone `"dungeon"` rooms), and ores inside it can't be gathered (`handle_gather`).
3. Its spawns and levels (`content.py:1064-1090`) and the Adamant Dragon's Mythos drop.
4. **Whether the Void v2 shared systems exist yet**, and where. List every reusable function/module, or say "not built".
5. Where you would hook: `explore_dungeons.build`, `handle_enter_dungeon`, `handle_leave_dungeon`, the WebSocket dispatch, `game_loop`, `process_dungeon_ai`, and the client's `draw_terrain_tile`, draw list, click handler and minimap.

Report your hook plan (file:function:line, each as a 1–5 line insertion) and your **reuse-or-build-generic decision** for each shared system, then **STOP**.

## Phase A: new layout and zones, existing monsters only, then STOP
- Add `server/depths_v2.py`, containing the map data from `reference_code/depths_map.py` and `build(session, next_id, monster_cls)`, which creates `session.dungeon` like `explore_dungeons.build` does:
  - tiles: `#` and all blocked chars (`W`, `Z`, `~`) → WALL; floor chars (`.`, `%`, `=`, `i` where walkable, `g`, `c`-adjacent) → FLOOR;
  - `~` also gets a `decor` entry `"pit"`, `W` gets `"deep_water"`, `%` gets `"shallow_water"` and `Z` gets `"sarcophagus"`;
  - spawn at `P`, exit at `E`.
- **Monsters:** existing types only for now. Map each new type to its nearest existing type: ossuary_keeper→big_skeleton, drowned_dead→skeleton, barrow_knight→shadow_knight (level overridden to 44), sir_aldric→shadow_knight, morvath→big_skeleton. Keep the `dragon` exactly as today.
- **Hook:** at the top of `explore_dungeons.build`, `if dungeon_id == "depths" and USE_NEW_DEPTHS_DUNGEON: return depths_v2.build(...)`.
- **Temporary:** for this phase only, treat doors, the gate X and secret walls as FLOOR (a `debug_open=True` argument), so the whole map can be walked.
- **Client:** in `draw_terrain_tile`, when `self.dungeon.get("v2") == "depths"`, call `depths_v2_client.draw_tile(...)`. Use the per-zone floor, wall, water, pit and sarcophagus drawers from `tools/depths_render.py` (copy them; don't import the tool). Skip the cliff "spike" pass for v2 and draw the wall faces instead.
- **Test:**
  - flag off → enter the Depths: identical to before (ores, giants, dragon);
  - flag on → enter: you spawn under the EXIT in the chapel;
  - walk the whole route to the arena; the exit still works;
  - the pit and deep water can't be walked on; shallow water can; the bridge is 1 tile wide.

## Phase B: monster progression and spawns, then STOP
- Add the 5 new `MONSTERS` entries (stats in the design §3) with a `visual`, `tint` and `scale` key. If the Void work already added `visual` support, reuse it; otherwise add it as a 1-line change where the monster type picks its drawer.
- **AI:** use the shared v2 AI rules if they exist (aggro range, zone leash, in-instance respawn after `respawn_ticks×1.5` when the player is more than 8 tiles away, `NO_RESPAWN`). Otherwise add them to `process_dungeon_ai` behind a generic `session.dungeon.get("v2")` check so the Void gets them too.
- Drowned dead "rise from the shallows": spawn hidden and appear when the player is within 4 tiles.
- **Test:**
  - the levels shown match the table (8→70);
  - monsters wake on approach;
  - leaving a zone drops aggro;
  - a killed skeleton respawns only when you're away;
  - the keeper, Aldric and the dragon stay dead for the visit.

## Phase C: doors and keys, then STOP
- **Reuse or build generically:** the `DUNGEON_INTERACT {x, y}` message, key items bound to the dungeon, key stripping on leave/login/death, the door-open `DUNGEON_TILES` patch, and the door drawer.
- **Depths data:**
  - the 3 keys `depths_bone_key`, `depths_tide_key` and `depths_knight_seal` (`dungeon_bound: "depths_v2"`);
  - the Ossuary Keeper and Sir Aldric grant their keys at 100%;
  - the Tide Key comes from the pedestal (3,38), and only after the reliquary secret (Phase D).
- Hover texts come from the design §4.
- Remove `debug_open` for the doors.
- **Test:**
  - each door blocks without its key;
  - the key opens it and is consumed;
  - leaving removes unused keys;
  - a second player entering at the same time still has locked doors (use two clients);
  - if the Void v2 exists, its seals still work.

## Phase D: secret walls, then STOP
- **Reuse or build generically:** hidden tiles sent as WALL, the reveal patch, the chat text, and hiding them again on re-entry.
- **Depths data:** 2 `loose_bricks` walls (22,9) and (6,59), plus 1 `skull_lever` niche (7,39). Use the hint drawers from the tool: fresh mortar, the wrong-way skull with glinting eyes, and leaning candle flames. The hover texts come from `SECRETS`.
- The Tide Key pedestal gives the key once per visit.
- **Test:**
  - the hidden rooms don't show on the minimap before revealing;
  - revealing opens them;
  - the Tide Key can only be obtained through the reliquary;
  - re-entering hides them again.

## Phase E: chests, sarcophagi, items and lore, then STOP
- **Reuse or build generically:** per-instance ground items (this fixes the overworld-drop bug for v2), chests and caches once per visit, ground loot piles, the lore parchment modal, and the shrine heal and checkpoint.
- **Depths-specific: sarcophagi.**
  - "Search Knight's sarcophagus" takes 2 ticks and rolls once per visit per sarcophagus using `SARCOPHAGUS_ROLL` (loot 55 / ambush 30 / empty 15).
  - Loot goes into the inventory.
  - An ambush spawns `AMBUSH["tomb"]` 1 tile away after the "The dead stir!" line. Ambush mobs don't respawn.
  - Draw the lid slid open (loot) or the green glow (ambush).
- **Test:**
  - each chest and sarcophagus pays once per visit per player;
  - the rates look right over 50 searches (debug log);
  - dropped items stay inside and disappear on leave;
  - lore opens and closes;
  - the shrine heals once and sets the respawn point.

## Phase F: the bridge and the boss, then STOP
- **Grasping hands**, in `depths_v2.tick(session)` from the `game_loop` hook:
  - every ~4 s, pick 2–3 random bridge tiles and send `BOSS_TELEGRAPH {tiles, at, kind: "hands"}` 1.5 s ahead (the client draws the glowing cracks);
  - at trigger: a player on one of those tiles is **rooted 2–3 ticks and takes 5–6 damage**;
  - no push, no fall.
- **Morvath** (`depths_v2.boss_tick`): the phases from the design §7.
  - Bone Storm: row/column lines with a 2-tick telegraph.
  - Raise the Dead: adds from the 4 arena sarcophagi, at most 4 alive; 50% damage reduction while any add lives.
  - Crypt Collapse: debris tiles; 25% faster attacks.
  - Add the loot table (§7). Morvath is confined to the arena; leaving resets him.
- **Reuse** the shared telegraph renderer, boss HP bar and warning-stone modal if they exist. Otherwise build them generically (name, phase label, phase markers).
- **Test:**
  - hands only root you if you're standing on a telegraphed tile;
  - each phase triggers at 66% and 33%;
  - the telegraphs match the damage tiles;
  - the adds halve the damage;
  - leaving the arena resets the boss;
  - loot arrives in the inventory.

## Phase G: polish and UX, then STOP
- **Reuse or build generically:** zone banners, fog of war (the minimap shows explored tiles only), and a gold first-kill chat line.
- **Depths flavour:**
  - candlelight glow;
  - dripping-water and whisper chat lines, at most one per 60 s;
  - banner texts from `ZONES`.
- **Shortcut:** the lever (50,72) opens gate X (44,10), persisted as the `quest_progress` row `depths_shortcut`. The gate is FLOOR at build if the row exists.
- **Test:**
  - banners show once per zone entry;
  - fog lifts as you walk;
  - the lever opens the stair, and it stays open next visit;
  - flag off → everything is as before;
  - the Void v2 (if present) still passes its own tests.

## Test commands (every phase)
```
cd game/assets/mmorpg && python -m pytest -q          # if tests exist; must stay green
USE_NEW_DEPTHS_DUNGEON=0 python server/server.py & python client/client.py   # old Depths
USE_NEW_DEPTHS_DUNGEON=1 python server/server.py & python client/client.py   # new Depths
python /path/to/depths_dungeon/tools/depths_render.py /tmp/out   # route check: 12/12 PASS on the map data
```
