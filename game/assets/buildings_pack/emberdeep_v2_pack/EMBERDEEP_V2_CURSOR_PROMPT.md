# Emberdeep v2 integration

Pack root: the folder that contains this file (`backdrop/`, `interior/`, `fp/`).

Add `USE_EMBERDEEP_V2` default OFF through `feature_flags._on`, the same helper `USE_NEW_VOID_DUNGEON` uses, but pass default `"0"`. Do not tie it to `USE_NEW_VOID_DUNGEON`, `USE_NEW_DEPTHS_DUNGEON`, `USE_NEW_ENTRANCES`, or any other flag. There is currently no emberdeep flag. `DUNGEON_MODS["emberdeep"]` always points at `emberdeep.py`.

## Step 1 — investigate only, then STOP

Read these and do not edit anything:

- `emberdeep.py` `generate_floor_tiles`. The live map is 20 by 16, one oval carve, not a room list. Tile codes are `WALL` 4, `FLOOR` 6, and `WATER` 2. Inside Emberdeep, `WATER` is lava and is not walkable. Spawn is `(10, 13)`. The generator writes the exit as the southern floor on the spawn column (`tiles[h - 1][sx] = FLOOR`), which is `(10, 15)`. Eight floors share that generator with a different seed and monster level. They are not eight different maps.
- Client `draw_map`. The overworld volcano apron is tiles `(154, 58)` through `(190, 94)`. Those are flat rects from `draw_terrain_tile` (walls, floors, and lava) drawn before sprites.
- `dungeon_entrances` pack sprite `dragon_lair`, drawn for the interactable mouth at world tile `(164, 84)`. It is the cave the player sees. Do not plan a second mouth.
- Enter and leave. `ENTER_DUNGEON` builds the emberdeep instance. Leaving is the southern floor tile, the Leave button, or a click next to the exit. Those paths already exist.

Stop after this read. Do not edit, commit, or push.

## Step 2 — only after the user says continue

Keep the hooks small.

When `USE_EMBERDEEP_V2` is on, blit `backdrop/mountain_topdown.png` behind the entrance, over the volcano tile apron `(154, 58)`–`(190, 94)`, instead of those flat tiles. Use `backdrop/mountain.json`: 1536 by 1024, anchor south center `(768, 1024)`. Draw the existing `dragon_lair` mouth sprite on top at `(164, 84)`. Do not draw a second cave. `backdrop/mountain_front.png` (1024 by 768) is the same mesh from the south if the camera yaws. Do not touch walk-cycle files: `rs_style.py` `pose_walk`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, or `draw_humanoid`.

When the flag is on, replace `generate_floor_tiles` with the hand grid in `interior/emberdeep_v2_floor.txt`. Map characters onto the codes the server already uses: `#` to `WALL`, `.` to `FLOOR`, `L` to `WATER` (lava, not walkable). `B` is a walkable floor tile with lava on both sides, not a new blocking type. `E` is the single exit and must stay the southern exit tile. `S` is the spawn. `H` and `N` mark the existing hoard and nest props; do not drop those props. `K` is the boss door and it is a floor tile. Keep one south exit. All eight floors can use this same layout for now. Do not invent eight different maps. See `interior/README_LAYOUT.md` for the rooms.

First person is a second flag, `USE_EMBERDEEP_FIRST_PERSON`, also `_on(..., default="0")`, also independent. It changes the view only while the player is inside an emberdeep instance. The overworld, combat outside, and every other dungeon stay on the current top-down pygame view. Inside, draw a simple raycast or wall slices with the textures in `fp/` (`wall_rock.png`, `wall_lava.png`, `floor_stone.png`, `floor_lava_edge.png`, `ceiling_dark.png`, `door_boss.png`). Face from the existing 4-direction `CameraYaw`. Movement stays on the tile grid. The Leave button and the exit tile still work. `fp/preview_corridor.png` is a reference still of a 3-tile-wide corridor, not a sprite to blit. If a full-dungeon raycast is too large for one step, stop after a working single-corridor prototype and say so. Do not add Dungeon Keeper digging, imps, or a base-building sim.

## Non-goals

No walk-cycle edits. No merge and no push. No new items. No bank cap change.
