# Cursor prompt: replace the 2D interior props with the 3D-looking props pack, safely

Paste everything below the line into Cursor. First unzip `props_pack.zip` somewhere Cursor can read it (for example `~/Downloads/props_pack/`), then fix the path in the "Attached" section.

---

Replace ONLY the visuals of the objects inside buildings (bank, smithy, Pet Emporium, castle keep, plus the wishing well and plaza fountain) with the new pre-rendered OSRS-style props. Work in small, reversible steps. I (David) have to approve after Step 1 and again after the first group.

## Repo
https://github.com/DavidRC-Projects/Mythoscape. Start from current main. The game is the pygame MMORPG under `game/assets/mmorpg/`.

## Attached (read these first)
- `props_pack/` (unzipped `props_pack.zip`) at: `<PATH TO props_pack>`
  - `CURSOR_PROPS_GUIDE.md` is the spec. Read sections 0, 1, 2, 5 and 7 fully before writing any code.
  - `review/contact_town.png`, `contact_castle.png`, `contact_pets.png`, `contact_dungeons.png` show what every prop looks like. Each has the Blender concept, the Panda3D check, a 3/4 view and the real 1x game sprite.
  - `sprites/game/<key>_1x.png` / `_2x` / `_3x` / `_match.png` / `_{s,w,n,e}_1x.png` + `<key>.json` are the transparent sprites and pixel anchors (`origin_px`). This is the 2D route to use.
  - `json/<key>.json` holds the per-prop metadata, including `game.kind`, `game.ids`, `game.drawer`, `game.current_px_at_tile40` and `game.old_base_offset_px`.
  - `glb/`, `bam/`, `tools/prop_loader.py` are the 3D models and Panda3D loader, for later. Don't use them in this task unless I say so.
  - `blender_scripts/` is the source. Don't edit it.

## Goal
The interior objects look like solid 3D OSRS-style props at the game's camera. Everything else behaves exactly as before: banking, smelting, smithing, cooking, wishing, buying pets from Luna, shops, positions, walkability, roof hiding, nameplates, depth sorting, server logic and saves. The new visuals sit behind a `USE_NEW_PROPS` flag, and turning it off gives exactly today's game.

## Do NOT
- Do NOT delete, rename or rewrite the old drawing code (`procedural_sprites_finished.py` drawers, the `draw_furniture` table, the interactable branches). Branch around it: `if USE_NEW_PROPS and <sprite available>: <new blit> else: <old code unchanged>`.
- Do NOT change `INTERACTABLES`, spot ids, kinds, positions, names, variants or colours. Do NOT change walkability, `adjacent_or_same`, `near_forge`, `near_bank`, click handlers, server code, networking or save formats.
- Do NOT add new interactions or behaviour. For example, cages don't become clickable if they weren't before.
- Do NOT touch buildings, monsters, NPCs, UI, dungeon entrances or dungeon interiors in this task.
- Do NOT reformat files, rename things or "clean up" unrelated code. Make the smallest diff that works.
- Do NOT do every group at once. Do ONE group first (Step 3).
- Do NOT hand-edit the PNG/JSON/glb/bam assets. If an asset looks wrong, stop and tell me.

## Process

### Step 1: INVESTIGATE ONLY. No code changes. Then STOP and wait for me.
Report the following. The file names below are **hints from a read of commit 8ee3b49; verify each one, and correct them if they have moved**:
1. **Where each prop is drawn today.** Give file, function and line for each of: the interactable draw loop in `game/assets/mmorpg/client/client.py` (hint: `# Interactables`, ~line 4789, inside `if not self.dungeon:`), its branches (`sprites.draw_furnace`, `sprites.draw_anvil`, `sprites.draw_bank_booth` / `sprites.draw_chest` for `variant == "chest"`, `sprites.draw_fireplace`, `sprites.draw_wishing_well`), `draw_furniture` (hint ~5576, the `drawers` dict), and the drawer functions in `game/assets/characters/procedural_sprites_finished.py` (hints: `draw_furnace` ~3230, `draw_anvil` ~3253, `draw_bank_booth` ~5809, `draw_chest`, `draw_pet_cage` ~6153, `draw_throne` ~6177, `draw_banner_stand` ~6202, `draw_fountain` ~6218, `draw_market_stall` ~6241, `draw_brazier` ~6264).
2. **Draw point, sort and hiding.** How `cx, cy` are computed, the depth-sort keys (hint: `cy + TILE//4`, rugs/fountains `cy - TILE//2`), `entity_hidden_by_roof` and `outdoor_kinds`, and the nameplate positions (`blit_nameplate`). Also say whether `TILE` can change at runtime (zoom).
3. **Camera and scale.** Confirm the view is 2D pygame. Confirm the building bake camera in `game/assets/mmorpg/tools/blender_render_building.py` (hint: ORTHO, rotation X 58°, so 32° elevation). Give the TILE size (hint: `rs_style.TILE_SIZE = 40`) and how camera yaw (`client/camera_yaw.py`, `building_sprites.get_sprite` suffixes `s/w/n/e`) affects props today.
4. **Mapping table.** For every spot in `server/content.py` `INTERACTABLES` (hint ~2088) inside the bank, smithy, Pet Emporium and castle keep, plus `wishing_well` and `city_fountain`, give id, kind, position and pack key. Use guide section 5.3 (e.g. `bank` → `bank_booth` or `vault_chest`, `furnace` → `furnace`, `pet_cage_a` → which cage species?). Mark anything unsure.
5. **Interactions.** For banking, smelting, smithing, cooking, wishing and pet buying, give the exact functions and lines that detect and perform each one. Hints: `near_forge` ~1899, bank checks ~1875, `resolve_landmark_click` ~3135, the WISH flow, server `near_bank`, `near_cook_spot`, `WISH_WELL_POS`, `pet_shop`. Confirm that none of them depend on the drawing code.
6. **Your plan.** Say where the sprites would be copied (exact folder, e.g. next to `client/assets/buildings/`), where `USE_NEW_PROPS` lives, the loader/cache function, and the exact lines you'd branch. Then ask me three questions:
   - **true-scale `_1x` or old-width `_match` sprites?** Guide section 2.
   - **yaw variants: yes or no?** Guide section 5.4.
   - **which species go in `pet_cage_a/_b`?**
   List any risks.

Then **STOP**. Post the report and wait for my reply. Don't copy assets or edit code until I say go.

### Step 2: copy the assets (after my go)
- Copy ONLY the sprites needed for the approved group (`sprites/game/<key>_*.png` + `<key>.json`) into the folder I approved. Don't copy glb/bam/blend.
- Add `USE_NEW_PROPS = True` to the existing config/constants module with a one-line comment. It must be trivially switchable to `False`.
- Load sprites once and cache them per (key, variant, TILE). If TILE isn't 40, scale by TILE/40 with smoothscale once. If a file is missing, fall back to the old drawer.

### Step 3: ONE group first — bank booth + vault chest, furnace, anvil
- Replace only these drawings, behind the flag:
  - `bank`: booth → `bank_booth`, and `variant == "chest"` → `vault_chest`, including `dungeon_bank`;
  - `furnace` → `furnace`;
  - `anvil` → `anvil`.
- Anchor each sprite so its `origin_px` lands on `(cx, cy + game.old_base_offset_px * TILE / 40)` (guide 5.2). Keep the same sort key, layer, nameplate call and roof-hiding rule as the old branch.
- Leave every interaction, position and walkability rule untouched. The flag only switches which picture is drawn.

### Step 4: verify that group, then STOP and summarise
- Run the game. Capture before (flag off) / after (flag on) screenshots of the bank interior and the smithy interior at the normal camera, with the player standing next to the booth, chest, furnace and anvil for scale. Include one screenshot with the player standing *behind* the furnace to show depth sorting.
- Check and report each of these:
  - Banking opens the same bank window from the booth and the vault chest.
  - Smelting at the furnace and smithing at the anvil work exactly as before (same UI, same adjacency).
  - Nothing moved: the sprites sit on the same tiles as the old drawings and the nameplates are in the same place.
  - Props still hide under the roof like before.
  - With the flag off, the game looks identical to before.
  - There are no new console errors.
  - FPS is about the same.
- Summarise:
  - the files changed, with a one-line reason each;
  - the diff size;
  - the screenshots;
  - anything that didn't match the guide;
  - your proposed order for the rest: town (well, fountain, shops, hearth, workbench, rack, tub, barrel), then castle, then pets, and dungeon props last as a separate client-only decoration step (guide 5.6).
- Then STOP and wait for my OK. Do each remaining group the same way, one at a time.

## Preserve (must be identical afterwards)
Spot ids, kinds, positions, names, variants and colours; all interactions and their adjacency rules; walkability; roof hiding; nameplates; depth order; server content; save data; every building, NPC, monster and entrance; controls; performance.

## Hard acceptance (David's bar)
- Each replaced prop reads as a solid 3D OSRS-style object: low poly, flat-shaded, muted per-face colours, chunky shapes. It matches the contact sheets. It must never look like a flat cardboard cut-out or a box pasted on the floor.
- It is correctly placed: standing on its tile, not floating or clipped, same spot as before, sensible scale against the player.
- Glowing parts glow: furnace fire, anvil hot bar, and later the well/fountain water, candles and braziers.
- No blurry rescaling artefacts. Use the right size PNG, or smoothscale once and cache it. No per-frame rescaling.
- Every interaction works exactly as before, the flag off restores the old visuals exactly, and the old code is still in the file.
- Don't claim success without the before/after screenshots and the checklist above.

## When done (after all approved groups)
Open a PR (don't merge) titled "New 3D-look interior props behind USE_NEW_PROPS". In the description, list the files changed, the spot → prop mapping, the screenshots, and how to switch the flag off.
