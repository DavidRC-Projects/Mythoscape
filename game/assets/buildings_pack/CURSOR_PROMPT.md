# Cursor prompt: replace the shared house template with 11 bigger, unique 3D-looking buildings, safely

Paste everything below the line into Cursor. First unzip `buildings_pack.zip` (or `buildings_pack_lite.zip`) somewhere Cursor can read it (for example `~/Downloads/buildings_pack/`), then fix the path in the "Attached" section.

---

Replace the look of the 11 buildings that share today's house template with the new pre-rendered OSRS-style buildings from the buildings pack. They are Elder's Hall, The Resting Ox, General Store, Farmhouse, Village Bank, Pet Emporium, Stonehaven Cottage, Stonehaven House, City Barracks, Kai's Catch and Harbourreach Tackle. Each becomes bigger and unique, and fits its purpose. Work in small, reversible steps. Do ONE building first (the General Store). I (David) have to approve after Step 1 and again after the General Store.

## Repo
https://github.com/DavidRC-Projects/Mythoscape. Start from current main. The game is the pygame MMORPG under `game/assets/mmorpg/`.

## Attached (read these first)
- `buildings_pack/` (unzipped) at: `<PATH TO buildings_pack>`
  - `CURSOR_BUILDINGS_GUIDE.md` is the spec. Read all of it before writing code, especially sections 1, 2, 4 and 5.
  - `concepts/contact_all_game_1x.png`, `contact_village.png`, `contact_stonehaven.png` and `contact_harbour.png` show every design. `before_after_*.png` compares each against my screenshots.
  - `sprites/1x/<key>/{ground,body,cutaway}.png` + `meta.json` (and `sprites/2x/`) are the layers and anchors (`origin_px`). `json/<key>.json` has the footprint, floor, door, walkability rows and the layer draw order.
  - `tools/buildings_map_patch.py` is the reference map stamp plus a flood-fill checker. Use it as your map spec and test.
  - `models/` (glb/bam/blend) and `panda_renders/` are for a later 3D client. Don't use them now. `blender_scripts/` is the source. Don't edit it.

## Goal
Each building looks like a solid 3D OSRS-style building at the game camera, bigger than today (about 1.3–2× footprint), and unique to its purpose. Entering, interiors, NPCs, shops, banking, quests and every interaction behave exactly as before. **Doors don't move.** Everything is behind a `USE_NEW_BUILDINGS` flag with a per-building enable set, and turning it off gives exactly today's game.

## Do NOT
- Do NOT resize the world or move roads, other buildings, NPCs, spawns, zones or interior spots. The ONE planned exception is Lira the Jeweler (NPC + `jeweler` place label) moving from (33,8) to (35,8) when the General Store is enabled.
- Do NOT move any door tile, enter tile or exit tile, and do NOT change any building id, name, kind, style or material.
- Do NOT delete or rewrite the old building code: `_building` stamps, `BUILDINGS` entries, `building_sprites`, `client/assets/buildings/*.png`, `building_shell3d.py` and the procedural shells. Branch around it: `if USE_NEW_BUILDINGS and bid in NEW_BUILDINGS_ENABLED: new else: old unchanged`.
- Do NOT change server logic, packets, saves or interior furniture drawing. Don't touch the castle, dungeons, monsters or props work. Don't reformat files.
- Do NOT push to main or merge anything. Open a PR only when I say so.

## Process

### Step 1: INVESTIGATE ONLY. No code changes. Then STOP and wait for me.
Report, with file:line references:
1. How these 11 buildings are drawn today: `draw_building_roofs`, `building_sprites.draw_building_sprite`, the `client/assets/buildings/<id>.png` + `.json` bakes and which tool made them, the procedural fallback, the name label, and the cutaway when inside. Confirm they are all the same template.
2. Every footprint, floor rect, door/enter/exit tile, and each stamp in `generate_world` (`_building`, aprons, `_BUILDING_FOOTPRINTS`).
3. Entering and roof hiding: `player_inside_building`, `entity_hidden_by_roof`, `building_covering_tile` and door handling.
4. The interiors: every interactable, NPC and spawn inside or next to each building, with coordinates.
5. The free space around each building. Confirm the guide's §2 plan still fits current main: the new rects, only Lira moves, no roads cut apart, the Tackle deck over x 143–146. Run the checker against current main.
6. Which building is the third Stonehaven stone house (the guide says `city_barracks`). Confirm.
Then propose the exact plan: the generalised stamp (rect, floor, doorway column, porch tiles), the content changes under the flag, where each layer is drawn, the doorway handling in `player_inside_building`, where the flag lives, and the per-building enable set. Point out anything in main that differs from the guide. **STOP.**

### Step 2: flag + assets (after my go)
- Add `server/feature_flags.py` with `USE_NEW_BUILDINGS = True` and `NEW_BUILDINGS_ENABLED = {"cottage_ne"}`. Import it in `server/world_map.py`, `server/content.py` and `client.py`.
- Copy `sprites/1x`, `sprites/2x` and the `json/*.json` files into `client/assets/buildings/v2/`. Load them lazily; a missing file falls back to the old sprite.

### Step 3: the General Store ONLY (`cottage_ne`)
- Map: under the flag, stamp the new rect (23,2)–(33,11), floor (24,3)–(32,9), doorway PATH at (27,10) and (27,11), and keep the apron (27,12). Update `_BUILDING_FOOTPRINTS` for it. The checker must print ALL PASS on the flagged grid.
- Content: new `BUILDINGS` rect and floor for `cottage_ne`. Lira + `jeweler` place (33,8) → (35,8). Nothing else.
- Client: draw ground → body (y-sorted at row 11, or where roofs are drawn today; tell me which) → cutaway when inside, using `origin_px` scaled by TILE/40 (use 2× assets when TILE > 40). Make `player_inside_building` count the doorway tiles. Make `entity_hidden_by_roof` hide only the new floor rect. Keep the name label.
- Every other building must be untouched (old rect, old sprite).

### Step 4: verify the General Store, then STOP and summarise
Send me:
- before/after screenshots at the same camera: outside, standing in the doorway, inside;
- proof that Shopkeeper Joe's shop opens, Guard Marcus is inside, and the counter, shelves, crates, barrels and rug are at the same tiles;
- proof that Lira works at (35,8) (talk, shop, quest);
- the checker output;
- a flag-off screenshot identical to today, and the grid hash with the flag on vs off;
- a list of every changed coordinate.
**STOP.** After my go, enable the rest one group at a time (village, Stonehaven, harbour) with the same checks, and stop after each group.

## Preserve (must be identical afterwards)
All door, enter and exit tiles; all interior spots, NPCs, shops, bank, cooking hearths, beds, quests and dialogues; roof hiding for interiors; nameplates; depth sorting of everything else; server movement rules; saves; and the whole map outside the 11 new rects, apart from Lira's one-tile move.

## Hard acceptance (David's bar)
- Each building clearly reads as a solid, unique 3D OSRS-style building (not the shared template, not cardboard) and matches `concepts/contact_*.png`.
- Each building is bigger than before and sits exactly on the tile grid. The door is where it was, and you enter in one smooth walk.
- The checker passes, and no NPC stands in a wall.
- Flag off (or id not enabled) = today's game, byte for byte in the grid and pixel for pixel on screen.
- No new errors or warnings. FPS isn't noticeably worse (cache the scaled layers).

## When done
Summarise the changes and the files touched, and ask me before opening a PR. Don't merge.
