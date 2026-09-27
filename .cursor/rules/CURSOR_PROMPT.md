# Cursor prompt: replace dungeon entrance exteriors (Blender pack), safely

Paste everything below the line into Cursor. Unzip `dungeon_pack.zip` somewhere Cursor can read it
first (for example `~/Downloads/dungeon_pack/`) and fix the path in the "Attached" section.

---

Replace ONLY the exterior visuals of the dungeon entrances with the new Blender-built 3D entrance pack. Work in small, reversible steps. I (David) have to approve after Step 1.

## Repo
https://github.com/DavidRC-Projects/Mythoscape. Start from current main. The game is the Pygame MMORPG under `game/assets/mmorpg/`. It uses pygame and Panda3D, and I don't know which one draws the overworld and entrances. Find out; don't assume.

## Attached (read these first)
- `dungeon_pack/` (unzipped `dungeon_pack.zip`) at: `<PATH TO dungeon_pack>`
  - `CURSOR_DUNGEON_ENTRANCE_GUIDE.md`: the spec. Read sections 0, 4, 5 and 6 fully before writing code
  - `images/contact_sheet.png`: what the seven entrances look like (Blender concept | Panda3D render)
  - `glb/`, `bam/`, `json/`: 3D models + collision/trigger metadata (3D route)
  - `sprites/<view>/<key>_<size>.png` + `<key>.json`: transparent pre-rendered sprites + pixel anchors (2D route)
  - `tools/entrance_loader.py`: drop-in Panda3D loader (fixes the sRGB, ambient and emission problems, and adds collision boxes and the doorway trigger)
  - `blender_scripts/`: the source of the models. Don't edit them in this task
- The seven entrance types: `dragon_lair`, `goblin_cave`, `skeleton_crypt`, `spider_nest`, `void_rift`, `giants_cavern`, `wolf_den`.

## Goal
Every dungeon entrance's outside looks like its new 3D OSRS-style entrance. Everything else behaves exactly as before: entering, positions, interiors, server logic, saves. The new visuals sit behind a `USE_NEW_ENTRANCES` flag, and turning the flag off gives exactly today's game.

## Do NOT
- Do NOT delete, rename or rewrite the old entrance drawing code. Keep it and branch around it with `if USE_NEW_ENTRANCES: ... else: <old code unchanged>`.
- Do NOT change entrance positions, ids, kinds, tile footprints, enter-dungeon triggers or their conditions, dungeon interiors, server/dungeon logic, networking or save formats.
- Do NOT rewrite or "clean up" unrelated code, reformat files, or rename things. Make the smallest diff that works.
- Do NOT regenerate or touch other buildings, monsters or UI.
- Do NOT do all seven entrance types at once. Do ONE type first (Step 3).
- Do NOT hand-edit the .glb/.bam/.png assets or the Blender scripts. If an asset looks wrong, stop and tell me.
- Do NOT write a new enter-dungeon function. Reuse the existing one.

## Process

### Step 1: INVESTIGATE ONLY. No code changes. Then STOP and wait for me.
Search the whole repo (client and server) and report:
1. **Every file and function that draws, places or positions a dungeon entrance exterior.** Give paths, function names and line numbers. Include sprite loaders, procedural drawers, building/shell drawers, map/place tables, and any asset PNGs used for entrances. These are hints to check, not facts: `client/building_sprites.py`, `client/assets/buildings/*.png` (e.g. `void_sanctum.png`), `building_shell3d.py` (`draw_crypt_shell`, `_recessed_entrance`), `building_textures.py`, `camera_yaw.py`, `tools/render_buildings.sh`, `server/content.py` places with `kind` values like `dungeon_entrance`, `cave_entrance`, `volcano_entrance`, and the ids `dungeon_entrance`, `tidehollow_cave`, `emberdeep_mouth`, `void_sanctum_portal`.
2. **How entering works, end to end:** what the player does, which code detects it (tile, rect, distance, click, server message), which function performs the enter, and what hides the exterior on enter. Give exact files, functions and line numbers.
3. **2D or 3D?** Say whether the overworld (and so the entrances) is rendered with pygame 2D (blitting surfaces/sprites) or Panda3D 3D (NodePaths in a scene graph), and show the evidence (the main render loop, file and line). If it's a hybrid (e.g. Panda3D used offline to bake sprites), say exactly how.
4. **Camera/projection** of the overworld (top-down, 3/4, isometric, yaw rotation?), the on-screen size of today's entrances in px, and how buildings are depth-sorted.
5. **Mapping table:** each existing entrance (id, kind, position) and which of the seven new types fits it best (e.g. generic cave -> `goblin_cave`, void sanctum portal -> `void_rift`, volcano/ember -> `dragon_lair`). Mark any you are unsure about.
6. **Your proposed plan**, 2D route (sprites) or 3D route (glb/bam + `entrance_loader.py`), following guide section 4 or 6. Include which sprite view/size or which model format you'd use, where the assets would be copied (exact folder), where `USE_NEW_ENTRANCES` would live, and the exact lines you would branch. List any risks.

Then **STOP**. Post the report and wait for my reply. Don't copy assets or edit code until I say go.

### Step 2: copy the assets (after my go)
- Copy ONLY what the chosen route needs into the folder I approved:
  - 2D: `sprites/<view>/*` + the matching json
  - 3D: `bam/*` (or `glb/*` + `json/*`) + `tools/entrance_loader.py`, plus `panda3d-gltf` in requirements if you use glb
- Add `USE_NEW_ENTRANCES` to the existing config/constants module, defaulting to `True`, with a one-line comment. It must be trivially switchable to `False`.

### Step 3: ONE entrance type first
- Pick the type I approved in the mapping (default: the most common one). Replace only its exterior drawing behind the flag. Anchor it at the SAME position the old visual used: 2D uses `origin_px` from the sprite json, 3D uses the model origin = doorway threshold, front faces -Y, then rotate to the old facing.
- Keep the existing enter-dungeon trigger exactly as it is. In 3D, use the pack's solid collision boxes only if the old code had solid collision there, and wire `TRIGGER_door` to the EXISTING enter function only if the old code used a collision trigger. Otherwise leave the old trigger alone (guide section 5).
- 3D only: use the monster pack's OSRS lighting (`set_shader_off`, flat shading) and `load_entrance()`. Entrances face -Y, so use `ENTRANCE_SUN_HPR` or rotate the model.
- The old code path must still run unchanged when `USE_NEW_ENTRANCES = False`.

### Step 4: verify (for that one type), then STOP and summarise
- Run the game (or the project's screenshot/render tool). Capture before/after screenshots of that entrance at the normal game camera, with the player next to it for scale.
- Check and report each of these:
  - Walking in still enters the dungeon exactly as before, the same interior loads, and leaving puts you back in the same place.
  - The exterior still hides on enter.
  - Nothing else on the map changed.
  - Flag `False` gives an identical old look.
  - No new errors or warnings in the console.
  - FPS is about the same.
- Summarise: files changed with a one-line reason each, the diff size, screenshots, anything that didn't match the guide, and your proposed mapping for the remaining six. Then STOP and wait for my OK before doing the other types one at a time in the same way.

## Preserve (must be identical afterwards)
Entrance ids, kinds, positions and footprints; enter/exit triggers and conditions; dungeon interiors (including `dungeon_interior_3d.py` if present); exterior-hides-on-enter behaviour; server content; save data; every non-entrance building and monster; controls; performance.

## Hard acceptance (David's bar)
- Each replaced entrance reads as a solid 3D OSRS-style entrance: low poly, flat-shaded, muted per-face colours, chunky shapes. It matches `images/contact_sheet.png`.
- The doorway is a deep, walkable opening with a DARK interior (the void rift shows its purple portal). It must never look like a flat facade with a door pasted on, a residential brown door with a knob, or cardboard planes.
- Correct scale: a 1.8 m player fits the doorway easily (giant's door is huge). Placed exactly where the old entrance was, on the ground, not floating, not clipped.
- No gaps or seams, no debug/construction lines, no grids, no missing faces, no z-fighting, no too-dark or washed-out colours. In 3D, use `load_entrance()`.
- Entering works exactly as before. The flag off restores the old visuals exactly. The old code is still in the file.
- Don't claim success without the before/after screenshots and the checklist above.

## When done (after all approved types)
Open a PR (don't merge) titled "New 3D dungeon entrance exteriors behind USE_NEW_ENTRANCES". In the description, list the files changed, the entrance -> type mapping, the screenshots, and how to switch the flag off.
