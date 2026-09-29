# Cursor prompt: Void Sanctum v2 (new VOID dungeon interior)

You are working in the Mythoscape repo (`game/assets/mmorpg/`). Read `VOID_CODE_REVIEW.md` and `VOID_DUNGEON_DESIGN.md` first, and use `reference_code/void_map.py` (the map data) as the source of truth for the layout.

## Ground rules (every step)
- **Flag:** everything goes behind `USE_NEW_VOID_DUNGEON` in `server/feature_flags.py`, default `"0"`. With the flag off, the game must behave exactly as today, including the old Sanctum.
- **Small incremental edits.** Add new files (`server/void_v2.py`, `client/void_v2_client.py`) and hook into existing code with **small `if USE_NEW_VOID_DUNGEON:` early branches**. **Never rewrite or reformat existing functions.**
- **Don't touch:**
  - other dungeons (Tidehollow, Emberdeep, The Depths);
  - the walk animation;
  - the characters work (`rs_humanoid*`, `gear_v2`, `armour_v2`);
  - the buildings, castle and props packs.
- **Don't call `widen_single_file_passages`** on the v2 map.
- **Screenshots:** take before and after screenshots at the end of each phase (same camera, same spot). Save them to `docs/void_v2/phase_<X>_{before,after}.png`.
- **Git:** never merge, push or open a PR. Commit locally per phase only if asked.
- **STOP** at the end of each step and wait for approval.

## Step 1: investigate only, then STOP
Confirm (or correct) these points from `VOID_CODE_REVIEW.md` with file:line references, and change nothing:
1. The Sanctum is a private per-session instance (`explore_dungeons.build`, `session.dungeon`).
2. Explore-dungeon monsters don't respawn in the instance, and the dungeon AI ignores `aggro_range`.
3. `handle_drop` inside a dungeon writes to the overworld `ground_items`.
4. There's no server-side door, chest, lever or secret logic, and no interact message type.
5. Where you would hook: `explore_dungeons.build`, `handle_enter_dungeon`, `handle_leave_dungeon`, the WebSocket dispatch, `game_loop`, and the client's `draw_terrain_tile`, draw list, click handler and minimap.

Report your hook plan (file:function:line, each as a 1–5 line insertion), then **STOP**.

## Phase A: new layout and zones, existing monsters only, then STOP
- Add `server/void_v2.py`, containing the map data from `reference_code/void_map.py` and `build(session, next_id, monster_cls)`, which creates `session.dungeon` like `explore_dungeons.build` does:
  - tiles: `#` and all blocked chars → WALL; floor chars → FLOOR; `~` → WALL plus a `decor` entry `"abyss"`;
  - spawn at `P`, exit at `E`;
  - monsters: existing types only for now. Map each new type to its nearest existing type: gallery_warden→crypt_ghoul, void_crawler→void_imp, knight_captain_vorn→shadow_knight, rift_wraith→shade, nyxarath→void_horror.
- **Hook:** at the top of `explore_dungeons.build`, `if dungeon_id == "sanctum" and USE_NEW_VOID_DUNGEON: return void_v2.build(...)`.
- **Temporary:** for this phase only, treat seals, the gate and secret walls as FLOOR (a `debug_open=True` argument), so the whole map can be walked.
- **Client:** in `draw_terrain_tile`, when `self.dungeon.get("v2")`, call `void_v2_client.draw_tile(...)`, using the per-zone floor, wall and abyss drawers from `tools/void_render.py` (copy them; don't import the tool). Skip the cliff "spike" pass for v2 and draw the wall faces instead.
- **Test:**
  - flag off → enter the Sanctum: identical to before;
  - flag on → enter: you spawn under the EXIT;
  - walk the whole route to the arena; the exit still works;
  - the abyss can't be walked on; the bridge is 1 tile wide.

## Phase B: monster progression and spawns, then STOP
- Add the 5 new `MONSTERS` entries (stats in the design §2) with a `visual` key. The client draws `visual` if it's present (a 1-line change where the monster type picks its drawer), plus an optional tint and scale.
- **AI:** in `process_dungeon_ai`, for v2 only:
  - use `aggro_range` (a monster acquires only within range);
  - `home_room` = zone rect;
  - normal mobs respawn in-instance after `respawn_ticks*1.5` when the player is more than 8 tiles away;
  - `NO_RESPAWN` types never respawn.
- **Test:** the levels shown match the table; monsters wake on approach, not all at once; leaving a zone drops aggro; a killed shade respawns only when you're away; mini-bosses stay dead.

## Phase C: doors and keys, then STOP
- Add the 3 key items (`type: "key"`, `tradeable: False`, `sellable: False`, `dungeon_bound: "sanctum_v2"`).
  - Strip them in `handle_leave_dungeon`, on login and on death.
  - Block dropping and banking them.
- Mini-boss kills grant their key straight into the inventory (explore loot already goes to the inventory).
- Add the `DUNGEON_INTERACT {x, y}` message. The server validates:
  - adjacency;
  - the target is a seal still locked for this session;
  - the key is present.
  On success it consumes the key, records the seal in `session.dungeon["opened"]`, sets the tile to FLOOR and sends `DUNGEON_TILES {changes}`. On failure it sends the hint text.
- **Client:** draw the seal (the `draw_door` + sigil drawer from the tool); clicking it sends `DUNGEON_INTERACT`; apply `DUNGEON_TILES` patches (tiles + minimap rebuild).
- Remove `debug_open` for the seals.
- **Test:**
  - the seal blocks without the key;
  - the key opens it and is consumed;
  - leaving removes any unused key;
  - a second player entering at the same time still has locked seals (use two clients).

## Phase D: secret walls, then STOP
- Hidden tiles are sent as WALL until revealed.
- The cracked-wall hint drawer comes from the tool; hovering shows "Search Cracked wall".
- The same `DUNGEON_INTERACT` on an `S` tile reveals the wall and its rects via a `DUNGEON_TILES` patch and shows chat text. The Obsidian Key pedestal gives the key once per visit.
- **Test:** the hidden rooms don't show on the minimap before searching; searching opens them; the Obsidian Key can only be obtained through the secret; re-entering hides them again.

## Phase E: chests, items and lore, then STOP
- **Per-instance ground items:** `session.dungeon["ground"]`, sent in the dungeon `STATE_UPDATE`. Route `handle_drop`, `handle_pickup` and vacuum to it when in v2 (this fixes the overworld-drop bug for v2 only).
- **Chests:** roll once per visit, straight into the inventory, and show the open frame afterwards. **Supply caches:** once per visit. **Ground loot piles:** placed at build.
- **Lore notes** open a small parchment modal (client), with the texts from `LORE`.
- **Healing shrine:** heals 50% once per visit and sets the visit respawn point (death past the shrine returns you there).
- **Test:** each chest pays once per visit per player; dropped items stay inside the dungeon and disappear on leave; lore opens and closes; the shrine heals once.

## Phase F: the bridge and the boss, then STOP
- **Void wind:** in `void_v2.tick(session)`, from the `game_loop` hook, every 10 s with a 2 s telegraph (`VOID_WIND` event → client streaks). Off an anchor: 8 damage and pushed 2 tiles back along the bridge. Anchors are safe.
- **Nyxarath** (`void_v2.boss_tick`): the phases from the design §6.
  - Umbral Orbs: telegraphed tiles, sent as `BOSS_TELEGRAPH {tiles, at}`.
  - Phase 2 adds: spawn from the rift pools; 50% damage reduction while adds are alive.
  - Phase 3: pylon pulses.
  - Add the loot table. Nyxarath is confined to the arena.
- **Client:** telegraph tiles, a boss HP bar with the phase name, and the warning-stone modal.
- **Test:**
  - the wind pushes you back only when you're off the anchors;
  - each phase triggers at its HP threshold;
  - the telegraphs match the damage tiles;
  - leaving the arena resets the boss;
  - loot arrives in the inventory.

## Phase G: polish and UX, then STOP
- Zone banners; fog of war with the minimap showing explored tiles only; a depth vignette; whisper chat lines (at most one per 60 s).
- The shortcut lever and gate, persisted as the `quest_progress` row `void_shortcut`: the gate is FLOOR at build if the row exists.
- A gold chat line on the first kill.
- **Test:**
  - banners show once per zone entry;
  - fog lifts as you walk;
  - pulling the lever opens the gate, and it stays open on the next visit;
  - flag off → everything is as before.

## Test commands (every phase)
```
cd game/assets/mmorpg && python -m pytest -q        # if tests exist; must stay green
USE_NEW_VOID_DUNGEON=0 python server/server.py & python client/client.py   # old Sanctum
USE_NEW_VOID_DUNGEON=1 python server/server.py & python client/client.py   # new Sanctum
```
