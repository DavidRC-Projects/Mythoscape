# Cursor prompt: replace Stonehaven Castle with the bigger 3D-looking castle (moat + drawbridge), safely

Paste everything below the line into Cursor. First unzip `castle_pack.zip` (or `castle_pack_lite.zip`) somewhere Cursor can read it (for example `~/Downloads/castle_pack/`), then fix the path in the "Attached" section.

---

Replace Stonehaven Castle with the new pre-rendered OSRS-style castle from the castle pack. It is bigger and has 8 round towers with conical roofs, a keep, a moat, a drawbridge and a portcullis. The castle footprint grows, the map gets an exact local expansion, and the gate animates open and closed as I walk through it. Work in small, reversible steps. I (David) have to approve after Step 1 and again after Step 4.

## Repo
https://github.com/DavidRC-Projects/Mythoscape. Start from current main. The game is the pygame MMORPG under `game/assets/mmorpg/`. My local build may have uncommitted castle changes (see Step 1).

## Attached (read these first)
- `castle_pack/` (unzipped) at: `<PATH TO castle_pack>`
  - `CURSOR_CASTLE_GUIDE.md` is the spec. Read all of it before writing any code, especially sections 1, 3, 4, 5 and 6.
  - `concepts/castle_closed_game_1x.png`, `castle_open_game_1x.png`, `castle_inside_cutaway_1x.png`, `before_after_game_scale.png`, `gate_open_close.gif` and `castle_walkability_overlay.png` show the target.
  - `sprites/1x/` and `sprites/2x/` hold the layers (ground, back, posts, front, cutaway) and the gate frames `gate/gate_00..11.png`. The metadata is in `sprites/castle_v2.json`: anchor `origin_px`, draw order, frame timings, walkability grid, trigger tiles, doors, interior shift and NPC spots.
  - `tools/castle_map_patch.py` is the reference map stamp (`apply_new_castle`) plus a flood-fill checker. Use it as your map spec and test.
  - `models/` (glb/bam/blend), `tools/prop_loader.py` and `panda_renders/` are for a later 3D client. Don't use them now.
  - `blender_scripts/` is the source. Don't edit it.

## Goal
At the game camera, the castle looks like a solid 3D OSRS-style castle at about 2.3× the old footprint (x 100–123, y 31–54 including the moat), and it is still the city's castle. The bridge lowers and the portcullis rises when I walk up to the gate, and they close about 1.5 s after I leave. Entering the keep, Herald Rowan and his quest, the knights, the Mythos Champion and every interior interactable keep working, at their moved positions. Everything is behind a `USE_NEW_CASTLE` flag, and turning it off gives exactly today's game.

## Do NOT
- Do NOT resize the world (`WIDTH`/`HEIGHT`) or move any content outside the castle: other buildings, roads, NPCs, spawns, zones, trees apart from the one maple at (100,34), fishing spots.
- Do NOT delete or rewrite the old castle code (`_draw_castle_keep`, `stonehaven_castle.png`, the old stamp in `generate_world`, the old content entries). Branch around it: `if USE_NEW_CASTLE: new else: old unchanged`.
- Do NOT change ids, kinds, names or behaviour of castle spots, doors, NPCs or quests. Only their coordinates change, exactly as in guide §4.
- Do NOT add server-side door logic, new packets or save-format changes. The gate animation is client-only.
- Do NOT touch dungeons, monsters, other props or unrelated files. Don't reformat files.
- Do NOT push to main or merge anything. Open a PR only when I say so.

## Process

### Step 1: INVESTIGATE ONLY. No code changes. Then STOP and wait for me.
Report, with file:line references:
1. How the castle is drawn today: `draw_building_roofs`, `building_sprites.draw_building_sprite` with `client/assets/buildings/stonehaven_castle.png`, and `sprites._draw_castle_keep`. **My screenshot shows round towers with conical roofs and marbled stone. The pack author couldn't find that on main at 8ee3b49.** Check `git status`, `git stash list`, branches and recently modified asset or drawer files, and tell me where my current castle comes from.
2. The castle footprint and every stamp that touches x 100–123, y 31–55 in `generate_world`: castle rect, floor, gate PATH, STONE plaza, city `_border`, mountains, trees, `_BUILDING_FOOTPRINTS`.
3. The map space north and east of the castle (rows 31–41, columns 119–123). Confirm it is grass or mountain rock with nothing important there, and confirm the mountain pass at row ≤ 30 is unaffected.
4. How entering works: doors (`castle_gate`, `castle_gate_e`), `player_inside_building`, `entity_hidden_by_roof`, the door-proximity loop and `_building_for_door`.
5. Every castle-related NPC, spawn, place label and interior spot, with current coordinates (Herald Rowan, knights, Mythos Champion, throne, rug, table, chairs, banners, rack, chest, braziers, candle), plus any quest text that refers to their location.
6. Walkability on both sides: `WALKABLE_TILES`, server `handle_move` and `WORLD.occupied`, client `tile_walkable`.
7. `get_zone` and the mountains/city overlap.
Then propose the exact plan: the tile-by-tile stamp (guide §3), the +3/−2 interior shift, the NPC moves (guide §4), where each layer is drawn (guide §5), the gate state machine (guide §6) and where the flag lives. Point out anything in current main that differs from the guide. **STOP.**

### Step 2: flag + assets (after my go)
- Add `server/feature_flags.py` with `USE_NEW_CASTLE = True`. Import it in `server/world_map.py`, `server/content.py` and `client.py`.
- Copy `sprites/1x`, `sprites/2x` and `castle_v2.json` into `client/assets/buildings/castle_v2/`. Load them lazily; a missing file falls back to the old castle.

### Step 3: map + content (server and client share these modules)
- In `generate_world`, under the flag, apply the stamp from guide §3 / `apply_new_castle`: grid codes → WATER/WALL/FLOOR/PATH, apron at y 55, `_BUILDING_FOOTPRINTS` (100,31,123,55), and the zone fix so the castle counts as "city".
- Adapt the checker to run on the real flagged grid. **It must print ALL PASS**: inside reachable only through the gate, no leaks, nothing previously reachable lost, mountain pass intact, Herald reachable.
- In content, under the flag: the new `BUILDINGS` rect and floor, new door coordinates, the interior spots shifted by (+3,−2), and the moved NPCs, spawns and place labels exactly as in guide §4.
- With the flag off, the tile grid hash and the content tables must be identical to before.

### Step 4: client drawing + gate, then verify and STOP
- Draw the layers in the guide §5 order: ground → back → gate frame → y-sorted entities with posts at row 54 → front. Use the cutaway instead of back + front while I'm inside. Use `origin_px` and scale by TILE/40 (use 2× assets when TILE > 40).
- Wall-walk NPCs (y 51) are drawn lifted 118 px × TILE/40. Update `entity_hidden_by_roof` exemptions (moat, bridge, apron, wall-walk, gate guards).
- Skip the old castle drawing and the old castle door visuals under the flag.
- Gate state machine (guide §6): trigger tiles and frame timings from `castle_v2.json`, local player only, 1500 ms close delay, reversible mid-animation.
- Verify and send me:
  - before/after screenshots at the same camera: outside closed, on the bridge open, inside, Herald on the wall-walk, knights/champion;
  - a GIF or frame strip of me walking in and out with the gate opening and closing;
  - the checker output;
  - a flag-off screenshot that matches the old castle exactly;
  - a list of every changed coordinate.
- **STOP** and summarise.

## Preserve (must be identical afterwards)
Entering and leaving the keep, Herald Rowan's dialogue and quest, knight and champion combat and respawn, every castle interactable's behaviour, roof hiding for the bailey, nameplates, depth sorting, server movement rules, saves, and everything outside x 100–123 / y 31–56.

## Hard acceptance (David's bar)
- The castle clearly reads as 3D OSRS-style, not flat or cardboard, and matches `concepts/castle_closed_game_1x.png`.
- It is at least 2× the old footprint, sits exactly on the tile grid, the moat blocks, the bridge is the only way in, and the flood-fill checker passes.
- The gate animation plays smoothly both ways as I approach and leave.
- No NPC stands in a wall, the moat or the keep. Herald Rowan and the champion are reachable and working.
- Flag off = today's game, byte for byte in the grid and pixel for pixel on screen.
- No new errors or warnings. FPS isn't noticeably worse (cache the scaled layers).

## When done
Summarise the changes and the files touched, and ask me before opening a PR. Don't merge.
