# CURSOR_PROPS_GUIDE: 3D-looking interior props for Mythoscape

The pack has 40 low-poly OSRS-style props built with Blender Python: bank, smithy, well, fountain, shops, castle keep, Pet Emporium cages and dungeon interiors. They replace the flat procedural 2D drawings of objects inside buildings. The workflow, art style and loader are the same as the dungeon entrance pack (`dungeon_pack.zip`).

> **Scope rule:** these props are *visual replacements*. Every interaction, every position, every collision/walkability rule and all server logic stay exactly as they are. The new art sits behind a `USE_NEW_PROPS` flag, and the old drawing code is kept.

---

## 0. TL;DR for Cursor

1. The overworld is **2D pygame**. Use the **2D route**: blit the pre-rendered sprites in `sprites/game/` (section 5). The 3D files (`glb/`, `bam/`, `tools/prop_loader.py`) are there for a future Panda3D route and for checking the art.
2. Sprites are rendered with the **same camera** the repo uses to bake building PNGs (orthographic, looking north, 32° down). At `_1x` they are at the game's scale: TILE 40 px ≈ 1.49 m, and a 1.8 m player ≈ 48 px.
3. For every prop, `sprites/game/<key>.json` gives `origin_px` (the model origin = tile centre on the ground). Blit so that `origin_px` lands on `(cx, cy + old_base_offset_px * TILE/40)`. `old_base_offset_px` is in `json/<key>.json → game`. The prop then stands where the old drawing stood.
4. Do **one group first**: bank booth + vault chest, furnace, anvil. Take before/after screenshots, then stop for approval.

---

## 1. What the repo does today (read from commit 8ee3b49, 2026-09-25)

**These are hints. Verify each one before relying on it.** Line numbers drift.

| What | Where (hint) | Notes |
|---|---|---|
| Client main file | `game/assets/mmorpg/client/client.py` (~10.4k lines) | pygame only. `requirements.txt` = pygame + websockets, no Panda3D at runtime |
| Sprite module | `game/assets/characters/procedural_sprites_finished.py`, imported as `sprites` | Every prop is drawn procedurally with `pygame.draw` calls. There is **no existing prop art/PNGs** |
| Scale helpers | `rs_style.TILE_SIZE = 40`, `_s(tile, "object") = tile/32 * OBJECT_SCALE (2.55)` | about 3.19 px per design unit at TILE 40, then each drawer multiplies by its own factor (0.48 … 1.55) |
| Interactable draw loop | `client.py` ~4789 `# Interactables` (inside `if not self.dungeon:`) | Branches: `furnace → sprites.draw_furnace`, `anvil → draw_anvil`, `forge`, `door`, `bank → draw_bank_booth` (or `draw_chest` if `spot["variant"] == "chest"`), entrances, `range`/`fireplace → draw_fireplace`, `wishing_well → draw_wishing_well`, everything else → `self.draw_furniture(kind, cx, cy, t, spot)` |
| Furniture table | `client.py` ~5576 `def draw_furniture` → `drawers` dict | table, chair(`facing`), bed, chest, barrel, crate, bookshelf, shelf, counter, fireplace, range, candle, rug(`color`), weapon_rack, workbench, quench_bucket, pet_bed, pet_cage, stool, wishing_well, throne, fountain, market_stall, brazier, and banner → `draw_banner_stand(color)` |
| Draw point | `cx, cy = sx*TILE + TILE//2, sy*TILE + TILE//2` (tile centre on screen) | Depth sort key `cy + TILE//4`. Rugs and fountains use `cy - TILE//2` (under feet). Nameplates use `blit_nameplate(...)` at `cy - TILE//2 - 2..10` |
| Roof hiding | `entity_hidden_by_roof(x, y)` ~5259 | Indoor props are skipped while the roof is up. `outdoor_kinds` = door, entrances, wishing_well, warning_sign, fountain, market_stall |
| Camera yaw | `client/camera_yaw.py`: yaw 0..3 (0 = north up) | Positions rotate with yaw, but prop drawers do **not** (same art at every yaw). `building_sprites.py` uses suffixes `("s","w","n","e")[yaw]` and says *never rotate PNGs*. Our `_s/_w/_n/_e` sprites follow that naming |
| Building bake camera | `game/assets/mmorpg/tools/blender_render_building.py` | `cam.data.type = "ORTHO"`, `rotation_euler = (58°, 0, 0)`, so it looks north, **32° elevation**. Sun rotation (40°, 15°, −30°). Our sprites use exactly this |
| Placement data | `game/assets/mmorpg/server/content.py` ~2088 `INTERACTABLES` | Each spot is one tile: `{"id","kind","x","y","name",...}`. Examples: `smithy_furnace` (52,6), `smithy_anvil` (59,6), `bank_booth` (38,16) + `_w/_e`, `bank_chest_a/_b` "Vault Chest" (variant chest), `dungeon_bank`, `pet_cage_a/_b` (51,25)/(52,25), `pet_bed_a/_b`, `wishing_well` (30,21), `city_fountain` (98,58), `castle_throne` (110,45), `castle_banner_w/_e` (colour [160,40,48]), `castle_rack` "Armoury Rack", `castle_table` "Council Table" + 2 chairs, `castle_brazier_w/_e`, `castle_candle`, `void_altar` ("Forbidden Tomes", drawn as a bookshelf) |
| Walkability | `server/world_map.py is_walkable()`: tile-grid only | **Props do not block movement by themselves.** Nothing about collision changes in the 2D route |
| Interactions | server: `adjacent_or_same()` (Chebyshev ≤ 1 tile), `near_bank`, `near_cook_spot`, `WISH_WELL_POS = (30,21)`. client: `near_forge(kind)` ~1899, `resolve_landmark_click` ~3135, bank UI `draw_bank` ~8864 (`show_bank`), WISH flow ~2677/7117 | "Bank vault" in the UI is the bank window; the physical objects are `bank` booths/chests. Pets are **bought from Luna's `pet_shop`** (content.py ~1178/1339). `pet_cage` spots are decorative today |
| Dungeon interiors | `characters/dungeon_interior_3d.py draw_dungeon_props(..., zone="shadow_crypt")`, called at client.py ~5121 **only for the overworld `shadow_crypt` zone** (Void Sanctum) | Private instances (Tidehollow cave, Emberdeep lava; `self.dungeon` set from the server's dungeon message ~2522) draw tiles, monsters and an exit mouth only. **No interior props today** |

### Current on-screen sizes (TILE 40) vs the new props

The old sizes are measured from the drawer code (unit 3.1875 px × drawer factor). They are approximate. "new 1x" is the true-scale sprite at 26.9 px/m. The `_match` sprite is scaled so its width equals the old width.

---

## 2. Camera and scale match

- **Game view = orthographic, azimuth 0 (camera south of the prop, looking north), elevation 32°.** It is identical to `tools/blender_render_building.py`, so the props sit in the same projection as the baked building shells. Every prop's front faces −Y (towards the camera).
- **Scale:** the player is ~15.5 design units × 3.125 px ≈ 48 px tall for 1.8 m, so **26.9 px/m**, and 1 tile = 40 px ≈ 1.49 m. All models are true metres (1 unit = 1 m), and `_1x` sprites are rendered at 26.9 px/m.
- The old drawers are not to scale with each other. For example, the anvil is drawn 60 px wide (≈ 2.2 m) and the wishing well 148×188 px (≈ 5.5 m wide). So each prop has two sprite choices:
  - `<key>_1x.png`: **true scale**, consistent with the player and buildings. This is the recommended default.
  - `<key>_match.png`: **same width as the old 2D drawing**, for zero visual footprint change.
  - Ask David which one he wants (Step 1 of the prompt).
- The concept renders (`images/<key>_concept.png`) and the Panda3D check (`panda_renders/<key>_panda.png`) both use the game camera. `panda_renders/<key>_panda34.png` and `sprites/osrs/` are the OSRS 3/4 view (az 35°, el 30°).

---

## 3. The props

Groups: **town** (bank, smithy, landmarks, shops), **castle**, **pets**, **dungeons**. Contact sheets are at `review/contact_<group>.png`. Each prop shows: concept | Panda game camera | Panda 3/4 | the real 1x sprite on 40 px tiles, with the old width drawn as a red bar.

### Town
| key | title | replaces (kind -> ids) | old 2D drawer | old px @TILE40 | new 1x px | tris / budget | solid / interact | glow | score |
|---|---|---|---|---|---|---|---|---|---|
| `bank_booth` | Bank Booth | bank -> bank_booth, bank_booth_w, bank_booth_e | sprites.draw_bank_booth | 80x70 | 77x79 | 612 / 900 (M) | yes / INTERACT_use | - | 9/10 |
| `vault_chest` | Vault Chest | bank -> bank_chest_a, bank_chest_b, dungeon_bank | sprites.draw_chest (bank variant='chest') | 34x26 | 55x37 | 334 / 400 (S) | yes / INTERACT_use | - | 8/10 |
| `vault_door` | Bank Vault Door | bank (optional decor) -> - | none - NEW optional prop | - | 92x81 | 556 / 900 (M) | yes / INTERACT_use | - | 9/10 |
| `furnace` | Furnace | furnace -> smithy_furnace | sprites.draw_furnace | 67x79 | 67x87 | 634 / 900 (M) | yes / INTERACT_use | fire, fire_core, ember | 9/10 |
| `anvil` | Anvil | anvil -> smithy_anvil | sprites.draw_anvil | 60x28 | 32x34 | 228 / 400 (S) | yes / INTERACT_use | ember | 9/10 |
| `workbench` | Workbench | workbench -> smithy_workbench | draw_furniture -> draw_workbench | 52x35 | 51x46 | 236 / 400 (S) | yes / - | - | 8/10 |
| `weapon_rack` | Weapon Rack | weapon_rack -> smithy_rack, castle_rack (Armoury Rack) | draw_furniture -> draw_weapon_rack | 40x42 | 44x63 | 315 / 400 (S) | yes / - | - | 8/10 |
| `quench_bucket` | Quench Tub | quench_bucket -> smithy_quench | draw_furniture -> draw_quench_bucket | 15x14 | 26x25 | 164 / 400 (S) | yes / - | - | 8/10 |
| `wishing_well` | Wishing Well | wishing_well -> wishing_well | sprites.draw_wishing_well (x1.55 scale) | 148x188 | 84x97 | 728 / 900 (M) | yes / INTERACT_use | water, water_hi | 8/10 |
| `fountain` | Plaza Fountain | fountain -> city_fountain | draw_furniture -> draw_fountain (x0.78) | 70x62 | 86x71 | 440 / 900 (M) | yes / INTERACT_use | water, water_hi | 9/10 |
| `market_stall` | Market Stall | market_stall -> market_stall_a, market_stall_b, market_stall_c | draw_furniture -> draw_market_stall (x0.7) | 54x45 | 79x73 | 634 / 900 (M) | yes / INTERACT_use | - | 9/10 |
| `shop_counter` | Shop Counter | counter -> shop_counter, tackle_counter, fish_counter, pet_counter | draw_furniture -> draw_counter | 54x30 | 66x43 | 328 / 400 (S) | yes / INTERACT_use | - | 8/10 |
| `hearth` | Hearth / Range | range / fireplace -> general_range, house_hearth, ... | sprites.draw_fireplace | 60x60 | 60x90 | 436 / 900 (M) | yes / INTERACT_use | fire, fire_core, ember | 8/10 |
| `barrel` | Barrel | barrel -> ore barrels, feed barrel, plaza barrel... (14 spots) | draw_furniture -> draw_barrel | 21x25 | 26x33 | 174 / 400 (S) | yes / - | - | 8/10 |

### Castle
| key | title | replaces (kind -> ids) | old 2D drawer | old px @TILE40 | new 1x px | tris / budget | solid / interact | glow | score |
|---|---|---|---|---|---|---|---|---|---|
| `throne` | Castle Throne | throne -> castle_throne | draw_furniture -> draw_throne (x0.72) | 46x57 | 57x89 | 252 / 400 (S) | yes / - | - | 9/10 |
| `banner_stand` | Castle Banner | banner -> castle_banner_w, castle_banner_e | draw_banner_stand(color=...) | 31x42 | 36x79 | 253 / 400 (S) | yes / - | - | 9/10 |
| `banquet_table` | Council / Banquet Table | table -> castle_table (Council Table), any long table | draw_furniture -> draw_table | 48x30 | 89x47 | 690 / 900 (M) | yes / - | candle | 9/10 |
| `castle_chair` | Castle Chair | chair -> castle_chair_a, castle_chair_b, other chairs | draw_furniture -> draw_chair(facing) | 21x35 | 19x45 | 156 / 400 (S) | yes / - | - | 8/10 |
| `suit_of_armour` | Suit of Armour | suit_of_armour (NEW) -> - | none - NEW optional prop | - | 31x66 | 392 / 900 (M) | yes / - | - | 9/10 |
| `chandelier` | Chandelier | chandelier (NEW) -> - | none - NEW optional prop; castle has 'castle_candle' + braziers | - | 41x41 | 442 / 900 (M) | - / - | candle | 8/10 |
| `brazier` | Brazier | brazier -> castle_brazier_w, castle_brazier_e | draw_furniture -> draw_brazier | 21x38 | 25x36 | 338 / 400 (S) | yes / - | fire, fire_core, ember | 8/10 |

### Pets (Pet Emporium)
| key | title | replaces (kind -> ids) | old 2D drawer | old px @TILE40 | new 1x px | tris / budget | solid / interact | glow | score |
|---|---|---|---|---|---|---|---|---|---|
| `cage_cat` | Cat Cage | pet_cage -> pet_cage_a, pet_cage_b, (one sprite per pet) | draw_furniture -> draw_pet_cage (x0.62) | 32x32 | 34x51 | 654 / 900 (M) | yes / INTERACT_use | - | 9/10 |
| `cage_husky` | White Husky Cage | pet_cage -> pet_cage_a, pet_cage_b, (one sprite per pet) | draw_furniture -> draw_pet_cage (x0.62) | 32x32 | 40x53 | 612 / 900 (M) | yes / INTERACT_use | - | 8/10 |
| `cage_skeleton` | Skeleton Pet Cage | pet_cage -> pet_cage_a, pet_cage_b, (one sprite per pet) | draw_furniture -> draw_pet_cage (x0.62) | 32x32 | 34x52 | 906 / 1300 (L) | yes / INTERACT_use | - | 9/10 |
| `cage_dragon` | Dragon Hatchling Cage | pet_cage -> pet_cage_a, pet_cage_b, (one sprite per pet) | draw_furniture -> draw_pet_cage (x0.62) | 32x32 | 38x55 | 686 / 900 (M) | yes / INTERACT_use | - | 9/10 |
| `pet_bed` | Pet Bed | pet_bed -> pet_bed_a, pet_bed_b | draw_furniture -> draw_pet_bed | 34x14 | 32x19 | 250 / 400 (S) | yes / - | - | 8/10 |

### Dungeons (2 per entrance theme)
| key | title | replaces (kind -> ids) | old 2D drawer | old px @TILE40 | new 1x px | tris / budget | solid / interact | glow | score |
|---|---|---|---|---|---|---|---|---|---|
| `dragon_hoard` | Dragon Treasure Hoard | dungeon_prop (NEW) -> theme: dragon_lair | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 70x51 | 1045 / 1300 (L) | yes / - | - | 9/10 |
| `dragon_egg_nest` | Dragon Egg Nest | dungeon_prop (NEW) -> theme: dragon_lair | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 66x38 | 818 / 1300 (L) | yes / - | ember | 9/10 |
| `goblin_campfire` | Goblin Campfire | dungeon_prop (NEW) -> theme: goblin_cave | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 63x35 | 496 / 900 (M) | yes / - | fire, fire_core, ember | 9/10 |
| `goblin_loot` | Goblin Loot Pile & Lean-to | dungeon_prop (NEW) -> theme: goblin_cave | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 67x57 | 544 / 900 (M) | yes / - | - | 8/10 |
| `crypt_sarcophagus` | Crypt Sarcophagus | dungeon_prop (NEW) -> theme: skeleton_crypt | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 70x44 | 360 / 900 (M) | yes / - | candle | 8/10 |
| `crypt_candelabra` | Crypt Candelabra & Urns | dungeon_prop (NEW) -> theme: skeleton_crypt | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 46x55 | 627 / 900 (M) | yes / - | candle | 8/10 |
| `spider_cocoons` | Web-wrapped Cocoons | dungeon_prop (NEW) -> theme: spider_nest | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 64x55 | 414 / 900 (M) | yes / - | - | 8/10 |
| `spider_egg_sacs` | Spider Egg Sacs | dungeon_prop (NEW) -> theme: spider_nest | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 59x35 | 350 / 900 (M) | yes / - | egg_glow | 8/10 |
| `void_altar` | Void Altar | dungeon_prop (NEW) -> void_altar | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 62x59 | 250 / 900 (M) | yes / INTERACT_use | void, void_core, candle | 9/10 |
| `void_crystals` | Void Crystal Cluster | dungeon_prop (NEW) -> theme: void_rift | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 50x52 | 296 / 400 (S) | yes / - | void, void_core | 9/10 |
| `giant_table` | Giant's Table | dungeon_prop (NEW) -> theme: giants_cavern | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 100x75 | 368 / 900 (M) | yes / - | - | 9/10 |
| `giant_throne` | Giant's Throne | dungeon_prop (NEW) -> theme: giants_cavern | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 74x130 | 556 / 900 (M) | yes / - | - | 8/10 |
| `wolf_bone_pile` | Wolf Den Bone Pile | dungeon_prop (NEW) -> theme: wolf_den | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 46x25 | 1071 / 1300 (L) | yes / - | - | 8/10 |
| `wolf_den_bed` | Wolf Straw Bed | dungeon_prop (NEW) -> theme: wolf_den | none yet - dungeon_interior_3d.draw_dungeon_props only has 'shadow_crypt' | - | 57x31 | 476 / 900 (M) | yes / - | - | 8/10 |

Notes on the lists:
- **Pets in cages** are the game's real pets from `content.PETS`: cat, white husky, skeleton, green dragon. The dragon hatchling can be recoloured for the crimson/frost/shadow/mythic variants. Map `pet_cage_a/_b` to whichever species David wants. The cages are decoration unless the old code gives them an action.
- **Castle:** the keep really has a throne, 2 banners, an Armoury Rack (use `weapon_rack`), a Council Table + 2 chairs (use `banquet_table` + `castle_chair`), braziers and a candle. `suit_of_armour` and `chandelier` are **new optional** props; the keep has neither today. `vault_door` is **optional** bank set-dressing.
- **The 7 dungeon themes** come from the entrance pack. Suggested placement: Void Sanctum (`shadow_crypt` zone) → `void_*` + `crypt_*`; Emberdeep → `dragon_*`; Tidehollow floors → `goblin_*`, `spider_*`, `wolf_*`, `giant_*` by floor. This needs a **client-only decoration list**. Put props only on tiles that are already non-walkable or on room edges, never on the exit or a path, with no server change (section 5.6).
- Not modelled (low value or covered by the dungeon pack): rug, bed, candle (castle_candle), crate, stool, shelf/bookshelf, table (generic), chair (generic). They keep their old drawers. `castle_chair`/`banquet_table` can stand in for chair/table if David wants.

---

## 4. Art rules and triangle budgets

- **OSRS look:** low poly, flat shading, one material per palette colour plus `.d`/`.l` per-face variants for colour noise, muted palette (hex in `blender_scripts/prop_parts.py → P`), chunky readable shapes, no textures and no UVs.
- **Never** flat cardboard planes or pasted-on boxes. Cloth has thickness (banner strips, pelts). Cages have real bars and a gable roof. Mouths and recesses are real geometry.
- **Budgets** (checked by `tools/verify_props.py`):
  - S = small 1-tile furniture ≤ **400** tris.
  - M = 1–2 tile props ≤ **900**.
  - L = showpiece clutter or a cage with a detailed pet ≤ **1300**.
  - The whole pack is 19121 tris for 40 props. For comparison, the dungeon entrances were 1.4k–4k each.
- **Emission:** glowing parts use palette keys listed in json `"emissive"` with a Blender strength:

  | key | strength |
  |---|---|
  | fire, fire_core | 6 / 8 |
  | ember | 3 |
  | candle | 6 |
  | void, void_core | 5 / 7 |
  | egg_glow | 2.5 |
  | water, water_hi | 0.45 / 0.6 |

  panda3d-gltf's legacy mode drops glTF emission, so `prop_loader.py` rebuilds it:
  - strength ≥ 2 → full-bright;
  - below 2 → a soft glow that keeps some shading (water).

  The furnace fire, void crystals and altar runes, well and fountain water, chandelier/table/crypt candles, braziers, hearth and campfire all pass this check.

---

## 5. 2D route (recommended for the current pygame client)

### 5.1 Files
- `sprites/game/<key>_1x.png`, `_2x`, `_3x`: true scale at 26.9 / 53.8 / 80.7 px per metre, transparent.
- `sprites/game/<key>_match.png`: width = old drawer width (only for props that replace an existing drawer).
- `sprites/game/<key>_{s,w,n,e}_1x.png` (and `_2x`): yaw variants, where `s` = front (yaw 0), `w` = yaw 1, `n` = yaw 2, `e` = yaw 3, as in `building_sprites.get_sprite`.
- `sprites/game/<key>.json`: for every image, `w`, `h`, `px_per_m`, `origin_px`, `collider_px` (solid footprints) and `interact_px` (interaction volume footprint), all as ground polygons in sprite pixels.
- `sprites/osrs/<key>_2x.png` + json: 3/4 view (az 35, el 30), for UI/icons or a future camera.

### 5.2 Blit
```python
# behind USE_NEW_PROPS; cache per (key, variant, TILE)
def blit_prop(screen, key, cx, cy, tile, variant="1x", yaw=0, base_px=0):
    name = f"{key}_{('s','w','n','e')[yaw]}_1x" if yaw else f"{key}_{variant}"
    img, meta = PROP_CACHE.get((name, tile)) or load_prop_sprite(key, name, tile)   # scales by tile/40
    ox, oy = meta["origin_px"]                     # already scaled with the image
    screen.blit(img, (round(cx - ox), round(cy + base_px * tile / 40 - oy)))
```
- `base_px` = `json/<key>.json → game.old_base_offset_px`, which is where the old drawer's contact shadow sits below the tile centre. Examples: furnace 30, anvil 21, bank booth 25, vault chest 9, well 69.
- If `TILE != 40`, scale with `pygame.transform.smoothscale` by `TILE/40` **once** and cache the result. Or pick `_2x`/`_3x` for zoomed views.
- Keep the same depth-sort key, layer and nameplate call as the old branch, and the same `entity_hidden_by_roof` rule.
- Fountains keep sorting at `cy - TILE//2` (under feet). Check the new sprite still looks right with the player walking in front of it. If a tall prop (well roof, chimney) is wrongly drawn over the player behind it, that is the existing depth rule and must not be "fixed" in this task.
- The chandelier hangs 2.1–3.6 m up and has no ground footprint. Draw it after the Y-sorted list (overhead) or skip it in 2D.

### 5.3 Per-kind details
- `bank`: `variant == "chest"` → `vault_chest`, otherwise `bank_booth`. `dungeon_bank` is a chest.
- `banner`: the spot's `color` must still apply. Tint only the `banner` pixels: render once with a key colour or multiply a mask, or pre-render one PNG per colour in use (only [160,40,48] today).
- `chair`: pick the yaw sprite that matches `facing` (s/w/n/e).
- `pet_cage`: one sprite per species (`cage_cat`, `cage_husky`, `cage_skeleton`, `cage_dragon`). Choose by spot id or a new optional `pet` field in the **client-side** mapping only.
- `range`/`fireplace` → `hearth`, `counter` → `shop_counter`, `weapon_rack` → `weapon_rack` (also `castle_rack`), `table` in the keep → `banquet_table`, `brazier` → `brazier`, `throne` → `throne`, `market_stall`, `fountain`, `wishing_well`, `workbench`, `quench_bucket`, `barrel`, `pet_bed` → same-name props.
- Animated bits in the old drawers (furnace glow pulse, chimney smoke, bank sparkle): optional. Either keep drawing the old smoke puff on top, or skip it. Don't add new animation systems.

### 5.4 Yaw
The old drawers ignore yaw. Keeping `_1x` at every yaw is the like-for-like choice. Using `_w/_n/_e` at yaw 1/2/3 is an optional upgrade and needs David's OK.

### 5.5 Collision and interaction in 2D
Nothing changes. Walkability stays the tile grid, and interactions stay `adjacent_or_same` / `near_forge` / click handlers. `collider_px` and `interact_px` in the json are for debugging overlays only.

### 5.6 Dungeon props (new, optional, later)
Private dungeon instances draw no interior props today, and the overworld interactable loop is skipped when `self.dungeon` is set. Adding dungeon props means a new **client-only** decoration list: `(dungeon id / zone, floor) → [(prop key, x, y)]`, drawn with the same blit and Y-sort. Only use tiles the server already treats as non-walkable, or wall-adjacent corners. Keep them off the exit and paths. Don't change the server. This is a separate step after the town groups.

---

## 6. 3D route (Panda3D, future)

```python
from prop_loader import load_prop, add_prop_collision, setup_osrs_lighting, PROP_SUN_HPR
model, meta = load_prop(base.loader, "assets/props/bam/furnace.bam")   # or glb/ + json/
model.reparent_to(render); model.set_pos(x_m, y_m, 0); model.set_h(heading)
solids, interact_np = add_prop_collision(model, meta)   # COL_* solids (bit 1), INTERACT_use (bit 2)
```
- `prop_loader.py` generalises the dungeon pack's `entrance_loader.py`:
  - same fixes (linear → sRGB, ambient = diffuse, flat shading, attrib-locked materials rebuilt);
  - emission scaled by strength;
  - `INTERACT_*` or `TRIGGER_*` nodes treated as the interaction volume;
  - `load_entrance`/`add_entrance_collision` kept as aliases, so it can replace entrance_loader.
- `.bam` files come from blend2bam (legacy materials) with the COLLISION collection as invisible CollisionBoxes. The json has the same boxes (`colliders`, `interact`) in model metres.
- Interaction volumes exist on: bank booth, vault chest, vault door, furnace, anvil, well, fountain, the 4 cages, shop counter, market stall, hearth and void altar. They sit in front (−Y) of the prop, about 1 m deep. Wire them to the **existing** handlers only. The server's `adjacent_or_same` rule remains the authority.

---

## 7. Interactions that must keep working (checklist)

| Interaction | Prop(s) | Existing code (hints) |
|---|---|---|
| Banking | `bank_booth`, `vault_chest` (bank variant chest, dungeon_bank) | client `near` bank checks ~1875–1890, `show_bank`, `draw_bank` ~8864; server `near_bank` ~1226 |
| Smelting | `furnace` | `near_forge("furnace")` ~1899–1926, forge UI (`show_forge`) |
| Smithing | `anvil` | `near_forge("anvil")` |
| Cooking | `hearth` (range/fireplace) | server `near_cook_spot` |
| Wishing | `wishing_well` | `resolve_landmark_click` ~3010/3141 → `walk_and_act({"type": "WISH"})` → `WISH`, `WISH_STAT_CHOICE`, `WISH_RESULT`; server `WISH_WELL_POS` |
| Buying pets | cages (visual), Luna's `pet_shop` (real) | content.py `pet_shop`, client `draw_pets_modal` ~10000 |
| Shops | `shop_counter`, `market_stall` | existing shop NPC/dialogue flow |
| Void altar | `void_altar` (only if placed in the Void Sanctum) | existing `void_altar` spot action |

---

## 8. Rebuilding or editing

```
python3 tools/build_all.py                          # Blender -> blend/glb/json/images/ref -> bam -> panda -> sprites -> verify -> sheets
python3 tools/build_all.py --groups pets            # one group
python3 tools/build_all.py --only furnace anvil     # individual props
```
- `blender_scripts/osrs_kit.py`: the dungeon pack's kit, extended with:
  - `interact()`;
  - `transform_since()`;
  - the game camera (ortho az 0 / el 32) for concepts;
  - an auto-placed 1.8 m reference figure;
  - `concept_ground`.
- `blender_scripts/prop_parts.py`: palette, emission strengths, `OLD_BASE_PX` and shared parts (barrel, crate, chest, candle, flame, logs, cage, stool, coin pile, sword, bone).
- `blender_scripts/props_{town,castle,pets,dungeons}.py`: one function per prop. Pass `-- --only key1,key2` to build a subset.
- Tools: `panda_render.py`, `render_sprites.py` (`--yaws`), `verify_props.py`, `make_contact_sheets.py`, `prop_loader.py`.
- Needs Blender 4.2 LTS, Panda3D 1.10.x, panda3d-gltf, panda3d-blend2bam and pillow.

---

## 9. Verification done (automated + visual)

- **In-engine:** every glb and bam loads through `prop_loader` in Panda3D 1.10.15 + panda3d-gltf 1.3.0 under the monster pack's OSRS lighting. The Panda render matches the Blender concept from the same camera (contact sheets).
- **Glow:** every required emissive material glows after the loader fixes.
- **Collision:** the bam CollisionNodes equal the json boxes. A 0.35 m two-sphere player walking in from 3.5–4 m in front enters `INTERACT_use` before touching a solid box, and walking into the prop is blocked.
- **Budgets:** every prop is inside its triangle class.
- **Sprites:** 1x/2x/3x, match, 4 yaw variants and the 3/4 view exist for all 40 props, with anchors.
- **Review:** every prop is scored ≥ 8/10 against the rubric in `review/scores.json`. Props that scored < 8 on the first pass were rebuilt (see the table).

```
PASS  town     anvil              tris  228/ 400(S)  glow ember                          interact reachable; solid blocks
PASS  town     bank_booth         tris  612/ 900(M)  glow -                              interact reachable; solid blocks
PASS  castle   banner_stand       tris  253/ 400(S)  glow -                              solid blocks
PASS  castle   banquet_table      tris  690/ 900(M)  glow candle                         solid blocks
PASS  town     barrel             tris  174/ 400(S)  glow -                              solid blocks
PASS  castle   brazier            tris  338/ 400(S)  glow fire,fire_core,ember           solid blocks
PASS  pets     cage_cat           tris  654/ 900(M)  glow -                              interact reachable; solid blocks
PASS  pets     cage_dragon        tris  686/ 900(M)  glow -                              interact reachable; solid blocks
PASS  pets     cage_husky         tris  612/ 900(M)  glow -                              interact reachable; solid blocks
PASS  pets     cage_skeleton      tris  906/1300(L)  glow -                              interact reachable; solid blocks
PASS  castle   castle_chair       tris  156/ 400(S)  glow -                              solid blocks
PASS  castle   chandelier         tris  442/ 900(M)  glow candle                         
PASS  dungeons crypt_candelabra   tris  627/ 900(M)  glow candle                         solid blocks
PASS  dungeons crypt_sarcophagus  tris  360/ 900(M)  glow candle                         solid blocks
PASS  dungeons dragon_egg_nest    tris  818/1300(L)  glow ember                          solid blocks
PASS  dungeons dragon_hoard       tris 1045/1300(L)  glow -                              solid blocks
PASS  town     fountain           tris  440/ 900(M)  glow water,water_hi                 interact reachable; solid blocks
PASS  town     furnace            tris  634/ 900(M)  glow fire,fire_core,ember           interact reachable; solid blocks
PASS  dungeons giant_table        tris  368/ 900(M)  glow -                              solid blocks
PASS  dungeons giant_throne       tris  556/ 900(M)  glow -                              solid blocks
PASS  dungeons goblin_campfire    tris  496/ 900(M)  glow fire,fire_core,ember           solid blocks
PASS  dungeons goblin_loot        tris  544/ 900(M)  glow -                              solid blocks
PASS  town     hearth             tris  436/ 900(M)  glow fire,fire_core,ember           interact reachable; solid blocks
PASS  town     market_stall       tris  634/ 900(M)  glow -                              interact reachable; solid blocks
PASS  pets     pet_bed            tris  250/ 400(S)  glow -                              solid blocks
PASS  town     quench_bucket      tris  164/ 400(S)  glow -                              solid blocks
PASS  town     shop_counter       tris  328/ 400(S)  glow -                              interact reachable; solid blocks
PASS  dungeons spider_cocoons     tris  414/ 900(M)  glow -                              solid blocks
PASS  dungeons spider_egg_sacs    tris  350/ 900(M)  glow egg_glow                       solid blocks
PASS  castle   suit_of_armour     tris  392/ 900(M)  glow -                              solid blocks
PASS  castle   throne             tris  252/ 400(S)  glow -                              solid blocks
PASS  town     vault_chest        tris  334/ 400(S)  glow -                              interact reachable; solid blocks
PASS  town     vault_door         tris  556/ 900(M)  glow -                              interact reachable; solid blocks
PASS  dungeons void_altar         tris  250/ 900(M)  glow void,void_core,candle          interact reachable; solid blocks
PASS  dungeons void_crystals      tris  296/ 400(S)  glow void,void_core                 solid blocks
PASS  town     weapon_rack        tris  315/ 400(S)  glow -                              solid blocks
PASS  town     wishing_well       tris  728/ 900(M)  glow water,water_hi                 interact reachable; solid blocks
PASS  dungeons wolf_bone_pile     tris 1071/1300(L)  glow -                              solid blocks
PASS  dungeons wolf_den_bed       tris  476/ 900(M)  glow -                              solid blocks
PASS  town     workbench          tris  236/ 400(S)  glow -                              solid blocks

40/40 props PASS
```

### Scores

| key | score | first pass | notes |
|---|---|---|---|
| `bank_booth` | 9 | - | desk + barred teller window + sign; gold arch replaced by a plain window rail (pass 2) |
| `vault_chest` | 8 | 7 | iron-banded chest on stone plinth; lightened wood in pass 3 (read too black) |
| `vault_door` | 9 | - | round steel door with wheel + bolts in a stone wall section; optional decor |
| `furnace` | 9 | 6 | brick furnace + chimney; pass 1 had the fire mouth buried inside the body -> projecting firebox |
| `anvil` | 9 | - | anvil on a rooted stump, hot bar glows, hammer + tongs |
| `workbench` | 8 | - | bench with vice, saw, tool board |
| `weapon_rack` | 8 | - | swords, spear, axe, leaning shield |
| `quench_bucket` | 8 | 6 | pass 1 lid cap hid the water -> open tub with cooling blade |
| `wishing_well` | 8 | - | stone ring, glowing water, windlass + bucket, shingled roof (roof reads flatter from the game camera) |
| `fountain` | 9 | - | octagonal basin, tiered bowl, glowing water sheets and ripples |
| `market_stall` | 9 | - | striped canopy, produce crates, bread |
| `shop_counter` | 8 | - | panelled counter, balance scales, cloth rolls, coin bowl |
| `hearth` | 8 | 7 | pass 1 chimney breast was a plain grey block -> masonry courses, bigger fire |
| `barrel` | 8 | - | hooped barrel + sack |
| `throne` | 9 | - | dais + carpet runner, crimson/gold throne with crest |
| `banner_stand` | 9 | - | waved cloth strips with thickness, crown emblem, recolourable 'banner' material |
| `banquet_table` | 9 | - | trestle table, runner, candelabra (glows), plates, goblets, roast |
| `castle_chair` | 8 | - | high-back chair; yaw sprites for 'facing' |
| `suit_of_armour` | 9 | - | plate armour with plume + halberd on a stand |
| `chandelier` | 8 | - | iron ring, 6 glowing candles, hangs 2.1-3.6 m (overhead layer) |
| `brazier` | 8 | - | tripod brazier with glowing coals + flame |
| `cage_cat` | 9 | 7 | pass 1: flat roof panel + 6 bars hid a tiny cat -> gable roof, 5 bars, pet x1.3 |
| `cage_husky` | 8 | 7 | lying white husky with blue eyes (same cage fix) |
| `cage_skeleton` | 9 | 7 | sitting skeleton pet, slate roof, iron bars (same cage fix) |
| `cage_dragon` | 9 | 7 | green hatchling with wings, horns, egg shell (same cage fix) |
| `pet_bed` | 8 | - | round cushion bed with ball + chew bone |
| `dragon_hoard` | 9 | - | coin mounds, gold-banded chest, sword, shield, crown, gems |
| `dragon_egg_nest` | 9 | - | charred stone ring, glowing embers, 3 speckled eggs, skull |
| `goblin_campfire` | 9 | - | stone ring fire (glows), spit roast, log stools, pot |
| `goblin_loot` | 8 | - | hide lean-to, sacks, broken crate, crude shield, spear |
| `crypt_sarcophagus` | 8 | 7 | pass 1 faced end-on so the effigy was hidden -> turned 90 deg, bolder effigy, glowing candles |
| `crypt_candelabra` | 8 | - | iron candelabra on a skull tripod (glows), two urns |
| `spider_cocoons` | 8 | - | wrapped victims, strung cocoon, corner web, leg remains |
| `spider_egg_sacs` | 8 | - | egg sac cluster with faint glow, web strands |
| `void_altar` | 9 | - | runed altar (glows), floating crystal, forbidden tomes, obelisks; pass 2 removed a full-bright disc |
| `void_crystals` | 9 | - | emissive crystal cluster on dark rock |
| `giant_table` | 9 | - | 1.7 m high table, giant mug, drumstick, knife |
| `giant_throne` | 8 | 6 | pass 1: flat grey pelt read as a wooden door -> bear pelt with head/claws, masonry seams, fur cushion |
| `wolf_bone_pile` | 8 | - | bones, ribcage, antlered skull, blood stain |
| `wolf_den_bed` | 8 | - | straw ring nest with sleeping pup |

---

## 10. Known limitations

- Nothing was run inside the actual pygame client from here. Before/after screenshots in the game are Cursor's job (prompt Step 4).
- `old_base_offset_px` and the old px sizes come from reading the drawer code, not from screenshots. Fine-tune by comparing before/after.
- True-scale sprites differ in size from some old drawings. The anvil and wishing well were drawn much larger; the chest and quench tub smaller. Use `_match` if David wants identical footprints.
- The old sprites animate (furnace glow pulse, smoke, bank sparkle). The new sprites are static.
- The banner colour needs a tint step. Chairs need facing → yaw sprite mapping.
- The dungeon props need a new client-only decoration list. There is no hook for private instances today.
