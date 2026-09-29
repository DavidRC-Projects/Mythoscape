# Cursor prompt: Gareth's Smithy v2 (pre-rendered OSRS-style smithy, same footprint and door)

Paste everything below the line into Cursor. First unzip `smithy_pack.zip` somewhere Cursor can read (for example `~/Downloads/smithy_pack/`) and fix the path in "Attached".

---

Replace the look of **Gareth's Smithy** with the new pre-rendered smithy from the smithy pack. It's the same approach as the 11-building pack (General Store rollout): ground, body and cutaway layers anchored with `origin_px`, drawn behind `USE_NEW_BUILDINGS`, and enabled per building. Work in small, reversible steps. I (David) approve after each step.

## Repo
https://github.com/DavidRC-Projects/Mythoscape, current main. The game is under `game/assets/mmorpg/`.

## Attached
- `smithy_pack/` (unzipped) at `/Users/davidcarr/Downloads/smithy_pack/`:
  - `smithy_before_after.png`: my screenshot vs the new sprite at the same scale.
  - `concepts/smithy_game_1x.png`: the outside view. `smithy_inside_1x.png` is the cutaway view, `smithy_walkability_1x.png` is the tile overlay, and `smithy_fx_preview.gif` shows the glow and smoke.
  - `sprites/1x/smithy/` and `sprites/2x/smithy/`:
    - `ground.png`, `body.png` and `cutaway.png`, plus `meta.json`;
    - optional FX frames: `body_glow0-2.png` and `smoke0-3.png`.
  - `json/smithy.json`: footprint, floor, door, walkability rows, layer draw order and the FX frame spec. It uses the buildings-pack format, plus an `fx` block.
  - `models/` and `blender_scripts/`: source only. Don't use or edit them.

## Goal
The smithy reads as a smithy at the game camera:
- a stone forge hall with a crow-stepped gable, an anvil plaque and a hanging anvil sign;
- an open timber lean-to over a glowing forge, with an anvil and a quench trough;
- a big stone chimney with smoke;
- a weapon rack, shields and an armour stand;
- a walled forge yard with a smelting furnace, coal and a woodpile.

The facade and forge dominate and the roof is modest. **The footprint (78,4)–(94,18), the floor (79,5)–(93,17), the door (86,18), enter (86,16) and exit (86,19) are all unchanged.** No map, collision, content or server change is needed.

## Rules
- **Flag:** use the existing `USE_NEW_BUILDINGS` flag with its per-building enable set (as in the General Store rollout). Add `"smithy"` to that set. Flag off, or `"smithy"` not enabled, must give exactly today's smithy.
- **Small hooks, no rewrites.** Branch around the old code (`if USE_NEW_BUILDINGS and bid in NEW_BUILDINGS_ENABLED: new; else: old unchanged`). Keep `building_volume.draw_world_volume`, the `BUILDINGS` entry, the `_building(78, 4, 94, 18, door_x=86)` stamp and every old drawer. Don't reformat files.
- **Don't touch:** the grid, stamps, `BUILDINGS` rects, interactables, NPCs, shops, the furnace/anvil logic, the server, packets, saves, other buildings, the castle, dungeons, monsters, props or the characters work.
- **Screenshots:** take before/after screenshots at the same camera spot for each step. Take them outside (player at (86,19)), standing in the doorway, inside by the furnace, and inside by the anvil.
- **Git:** never merge or push. Commit locally only if I ask. Don't open a PR unless I say so.
- **STOP** after each step and wait for my approval.

## Step 1: INVESTIGATE ONLY (no code changes), then STOP
Report with file:line references. These were my notes at main `ca336ee`; confirm or correct them:
1. **Flag state.** Does `USE_NEW_BUILDINGS` / `NEW_BUILDINGS_ENABLED` exist yet, and is the General Store v2 drawer merged? At `ca336ee`, `server/feature_flags.py` only had `USE_NEW_CASTLE` and friends. If the flag isn't there, **don't invent a parallel flag.** Report it, and propose adding it exactly as the buildings-pack prompt's Step 2 (`USE_NEW_BUILDINGS`, `NEW_BUILDINGS_ENABLED`, lazy loader, fallback to the old drawer). Then STOP.
2. **How the smithy is drawn today.**
   - `client.py` `_queue_buildings` (≈5863–5929) calls `bvol.draw_world_volume(kind="smithy", material="red_brick")`, sorts at the south wall row, and draws the name label at `rect.y + rect.h*0.14`.
   - The inside outline is drawn with `interior_outline=True`.
   - Check `player_inside_building` (≈5647) and `entity_hidden_by_roof` (≈5725).
   - Check the camera-yaw handling (`camera_yaw.py`): the sprite is azimuth 0 only.
3. **Footprint and collision.**
   - `server/world_map.py:227` `_building(78, 4, 94, 18, door_x=86)`.
   - The `BUILDINGS` entry at `server/content.py:2439-2444` (id `smithy`, kind `smithy`, style 1, `red_brick`, floor 79–93 × 5–17).
   - The door interactable at `content.py:2202-2203`.
   - Compare the pack's `walkability.rows` with the stamped grid. They must match exactly: row 4 is a walkable grass strip apart from the corners; rows 5–17 are floor; row 18 is wall except the 3-wide PATH gap (85–87,18) from `_punch_south_door`.
4. **Interior.**
   - furnace (80,6) and anvil (87,6) at `content.py:2200-2201`;
   - places (80,7) and (87,7) at `content.py:2099-2102`;
   - props at `content.py:2280-2288`;
   - Blacksmith Gareth (86,8) at `content.py:1192`.
   Confirm that none of these move.
5. **The plan.** Where the three layers go in the draw list (ground after floor tiles; body y-sorted at row 18; cutaway replacing the body while inside), how the label is kept, what happens at yaw ≠ 0 (fall back to the old drawer), and the exact hook lines (1–5 lines each).
**STOP.**

## Step 2: static sprite for the smithy only (after my go)
- Copy `sprites/1x/smithy`, `sprites/2x/smithy` and `json/smithy.json` into `client/assets/buildings/v2/` (the same folder as the General Store). Load them lazily; a missing file means the old drawer.
- When `USE_NEW_BUILDINGS and "smithy" in NEW_BUILDINGS_ENABLED` and yaw == 0, for building `smithy`:
  - blit `ground` (after floor tiles, before entities);
  - blit `body`, y-sorted like an entity on row 18;
  - blit `cutaway` instead of `body` while `player_inside_building` is true (the floor rect, or the doorway gap tiles (85–87,18) that it already counts).
  - Blit at `(tile_screen_x(78) - origin_px.x*TILE/40, tile_screen_y(4) - origin_px.y*TILE/40)`, scaled by TILE/40, using the 2x assets when TILE > 40. Cache the scaled surfaces.
  - Skip the old `draw_world_volume` call for the smithy only.
- Keep the "Gareth's Smithy" name label. Place it above the parapet: the pack's anvil plaque sits at about 7 tiles above row 18.
- Don't change `entity_hidden_by_roof` for the smithy. The rect is unchanged.
- **Test and screenshots:**
  - outside, doorway, inside by the furnace, inside by the anvil;
  - Gareth talks and his shop opens;
  - smelting at the furnace and smithing at the anvil still work;
  - the quest giver works;
  - flag off: pixel-identical to today;
  - the grid hash is the same with the flag on and off;
  - FPS is unchanged.
**STOP** and send me the screenshots and a list of the files touched.

## Step 3 (optional, after my go): forge glow and chimney smoke
- The `fx` block in `json/smithy.json` covers two effects:
  - **Glow:** replace `body` with `body_glow{0,1,2}` in the sequence `[0,1,2,1]` at 4 fps.
  - **Smoke:** draw `smoke{0..3}` right after `body` at 5 fps. The frames are already masked behind the chimney.
- Outside view only. Same size and origin as `body`; cache every frame. Add a tiny `SMITHY_FX = True` sub-toggle next to the enable set so it can be switched off alone.
- **Test:** before/after screenshots (or a short GIF), FPS unchanged, and nothing drawn while inside.
**STOP.**

## Hard acceptance
- It reads as a smithy at a glance, matching `concepts/smithy_game_1x.png`: forge, chimney, anvil sign, lean-to, trough, racks. The roof is modest.
- The door, collision, interior, NPCs, shop and stations are all unchanged. The walkability rows match the grid.
- Flag off (or not enabled) = today's game, byte for byte in the grid and pixel for pixel on screen.
- No new errors or warnings. Never merge or push.
