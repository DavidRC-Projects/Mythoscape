# Cursor prompt: Castle Realm (phase 1: realm map + Duskspire Keep, the gothic castle)

You are working in **Mythoscape** (`game/assets/mmorpg/`). The asset pack is `realm_map_and_gothic_pack.zip`.
Unzip it to `client/assets/castle_realm/`, keeping the folder structure. The pack contains:

- `json/castle_realm_map.json`: the realm plane. It holds 300×200 tile rows, a legend that maps each char to a server tile name, the spawn, the hub, the return portal, the overworld portal, the roads, and the **castle registry** (4 plots).
- `json/gothic_castle.json`: castle #1. It holds:
  - the 24×24 footprint grid, in the same format and legend as `castle_v2.json` plus a new `D` keep door;
  - trigger tiles, gate frames, sprite layers and the origin;
  - **4 interior floors** (`gothic_f1..f4`), each with 18×12 rows, rooms, doors, stairs, exits and furniture.
- `gothic/sprites/{1x,2x}/gothic_{ground,back,posts,front,cutaway}.png` and `gate/gate_00..11.png`. These use the same camera, scale and anchor rules as castle_v2 (ortho az 0 / el 32, 40 px per tile at 1x).
- `gothic/floors/{1x/,}gothic_f1..4.png`: cutaway interior sprites. The origin is the NW corner of tile (0,0) at `origin_px_1x` = (0,40).
- `tools/realm_data.py`: the data generator and the **multi-floor map checker**. It runs a BFS over every plane and asserts that every room and floor can be reached.

## David's rules (apply to every step)
1. **Step 1 is investigation only. Change nothing, report back, then STOP.**
2. Put everything behind a **new** flag, `USE_CASTLE_REALM`, in `server/feature_flags.py`. Use the existing `_on(name, default=...)` pattern with **default "0"**. When the flag is off, the game must behave byte-for-byte as it does today.
3. Use small hooks only. Don't rewrite anything, and keep the old code paths. Don't touch the existing Stonehaven castle (`castle_v2.py`, `castle_sprites.py`, `USE_NEW_CASTLE`), the other zones, or the dungeon logic. You may only *call* them.
4. Do one phase at a time. At the end of each phase, take **before/after screenshots** (flag off vs on, from the same spot) and list the files you changed with line counts. Then **STOP and wait for approval**.
5. **Never merge, never push, never open a PR.** Work on a local branch `castle-realm-phase-N`.

## Step 1: investigation only (then STOP)
Confirm or correct each point below, with file:line references. **Don't edit anything.**
- Check that `server/world_map.py` is `WIDTH=200, HEIGHT=145` and that tile (111,43) plus its 3×3 neighbourhood is GRASS on your branch. This is the overworld portal site: NW of the live castle and west of the north road at x117–118. If it isn't grass, propose the nearest free 3×3.
- Map out the per-session instance pattern:
  - `session.dungeon` dict: `id, floor, floors, tiles, width, height, exit_x/y, return_x/y`;
  - `handle_enter_dungeon` and `handle_leave_dungeon` (about lines 1950 and 1991 of `server.py`);
  - `_dungeon_payload` (about line 1796);
  - the `handle_move` walkability and exit check (about line 1691);
  - the client messages `DUNGEON_ENTER`, `DUNGEON_FLOOR` and `DUNGEON_EXIT` (`client.py` about 484–492).

  Report whether a non-combat "plane" can reuse this transport as-is. For example: can floor changes be sent without the all-monsters-dead rule, and does the client dungeon view accept arbitrary tiles?
- Find out how an interactable with `{"type":"ENTER_DUNGEON","dungeon_id":...}` is declared (`content.py` about line 2121), and how the client renders dungeon tiles. Check that it can draw GRASS, PATH and WATER, not just FLOOR and WALL.
- Find out how `castle_sprites.py` blits castle_v2 layers and runs the gate trigger. Confirm it can be called with a different JSON path and footprint, possibly through a small parameter.
- Check for multiplayer implications: is `session.dungeon` per player? It is expected to be per player for now, and that's fine.
- Deliver a short plan that lists the exact hook points and the estimated lines per file. **STOP.**

## Design (what the phases build)
- **Planes.** A plane is one tile layer: `realm`, `gothic_f1`, `gothic_f2`, `gothic_f3`, `gothic_f4`, and later `rose_f1..`, `king_f1..`, `sky_f1..`. Each floor is its own plane. Stairs, doors to interiors, exits and portals are **transition tiles** `{tile, to_plane, arrive}`. Stepping onto one moves the player to `arrive` on `to_plane`.
- **Transport.** Reuse the dungeon instance. `session.dungeon = {"id": "castle_realm", "plane": <plane>, "tiles": ..., "width": ..., "height": ..., "transitions": {...}, "return_x": 111, "return_y": 45}`. A plane change sends the existing `DUNGEON_FLOOR`-style payload, or a new `REALM_PLANE` message if Step 1 shows `DUNGEON_FLOOR` has side effects. Don't add monsters, and don't apply the floor-advance-on-kill rule to `castle_realm`.
- **Castle registry.** `castle_realm_map.json["castles"]` lists each castle's `id`, `plot`, `footprint`, `gate_apron`, `data` file and `status`. The code loops over the registry, and **adding a castle means adding a data file only**. Reserved plots are walkable grass until their castle ships.
- **Realm walkability.** Walkability comes from the realm legend (`walkable`). Tiles marked `c` (castle footprint) defer to that castle's `walkability` grid, where the walkable chars are `F P G B D`. `A` (the wall-walk) is for NPCs only.

## Phase A: flag + plane module (server only)
- Add `USE_CASTLE_REALM` (default off).
- Add a new file, `server/castle_realm.py` (about 150 lines). It should:
  - load both JSONs;
  - `build_plane(name)` → `{tiles, width, height, transitions}`, converting realm chars through the legend into `wm.GRASS/PATH/WALL/WATER` and floor chars into `FLOOR/WALL`;
  - `walkable(plane, x, y)`;
  - `transition_at(plane, x, y)`.
- Add a unit test that loads the data and runs `realm_data.check()`, so the checker must pass.
- Before/after: none yet (server only). Show the test output. **STOP.**

## Phase B: overworld portal
- Add one interactable at (111,43), "Castle Realm portal". Its action is `ENTER_DUNGEON` with `dungeon_id="castle_realm"`, and it only exists when the flag is on.
- `handle_enter_dungeon` should branch to `castle_realm.enter(session)` when the id is `castle_realm`. That puts the player on spawn (150,182) on plane `realm`.
- The return portal at (150,186) sends the player back to (111,45).
- Draw the portal with an existing portal or prop sprite for now.
- Take before/after screenshots at the portal site. **STOP.**

## Phase C: realm rendering
- Draw the realm plane with the normal overworld tile drawers: grass, path, water, and trees for `T`.
- For each registry castle with `status: built`, blit its sprite layers exactly as castle_v2 does, using `origin_px` and the draw order. Run the gate animation with its own trigger tiles by calling `castle_sprites` with this castle's JSON. Don't fork it.
- Take screenshots of the plaza, the roads and the gothic castle with the gate closed and open. **STOP.**

## Phase D: doors and stairs
- In `handle_move`, and only when `session.dungeon["id"] == "castle_realm"`, check `castle_realm.transition_at` after the walkability check:
  - keep door `D` → `gothic_f1`;
  - `U` and `V` stairs → next or previous floor;
  - `E` → back to the bailey.
- Send the plane payload. The client swaps tiles, repositions the player, and briefly fades.
- Take screenshots walking bailey → F1 → F2 → F3 → F4 and back down. **STOP.**

## Phase E: interior sprites
- Draw `gothic/floors/1x/gothic_fN.png` under entities, anchored at the tile (0,0) origin `origin_px_1x`.
- Use rows/legend only for collision. Furniture tiles `x` are blocked.
- Label rooms on hover from `rooms[].name`.
- Take screenshots of each floor. **STOP.**

## Phase F: checker + regression
- Wire `tools/realm_data.py --check` into the test suite.
- Run the existing castle and dungeon tests with the flag both off and on.
- Record a short video or GIF of a full walk from the portal to the spire top. **STOP.**

## Later castles (phases 2–4 of the art job)
Each future castle comes as one data file (`white_rose_castle.json`, `king_castle.json`, `sky_anchor_castle.json`) with the same schema:
- `footprint`, `walkability`, `keep_doors`, `trigger_tiles`, `layers`, `gate`, `floors[]`.

To add one:
1. Set its registry entry to `status: built`.
2. Re-run `realm_data.py`. The checker must pass.
3. Take before/after screenshots. No code changes should be needed beyond Phase C and D.

Plane names are prefixed with the castle id.
