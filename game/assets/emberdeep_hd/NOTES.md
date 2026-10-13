# Emberdeep HD (camera, walls, combat, wyrm)

The prompt is in `.cursor/rules/EMBERDEEP_UX_CURSOR_PROMPT.md`. Run it after `CUSTOMISATION_FIX_CURSOR_PROMPT.md` has been pushed.

## Textures v2 (honest scores against commercial dungeon textures)
| file | what | v1 | v2 |
|---|---|---|---|
| wall_stone.png | remeshed Blender ashlar, irregular chipped faces, hairline cracks, gritty mortar, per-stone tint | 7.5 | 8 |
| wall_stone_b.png | cooler grey-blue variant | 7.5 | 8 |
| wall_stone_lava.png | same stone, joints filled with crusted molten lava, glow bleeding onto the stone edges | 7.5 | 8 |
| floor_flagstone.png | worn flagstones with chipped edges and grit joints (2×2 tiles per repeat) | 7.5 | 8 |
| wall_top.png | rough split capstones seen from above | 7 | 8 |
| lava_flow.png | Voronoi crust plates, red→yellow seams (scrolled in game) | 7.5 | 8 |
| wall_base_trim.png / wall_cap_trim.png | Blender plinth with chamfered ledge / dentil cornice, graded to the wall palette | 7.5 | 8 (base trim 7.5–8) |
| torch_sconce_strip.png | Blender iron sconce (plate, arm, cage cup, glowing coals) + painted rising flame, 4 frames | 7 | 8 |
| door_boss.png | NEW: 512×1024 carved gate pillar, ember-lit rune panel with a dragon-eye sigil, iron bands | 4 (old) | 8 |

Method: `tools/bake_stones2.py` (voxel-remeshed stones, instanced 3×3 so the bake tiles) → `tools/grade.py`.
Props: `tools/bake_props.py` (trim_base, trim_cap, torch, door) → `grade_trim.py`, `make_torch.py`, `grade_door.py`. Lava: `make_lava2.py`.

## Dragon (wyrm) frames
`tools/wyrm_build.py` builds a procedural rigged dragon in Blender and renders `dragon/frames/`; `tools/assemble_dragon.py` makes the strips, `meta.json` and `previews/dragon_frames_sheet.png`.

## Reference renderer
`reference/emberdeep_view3d.py`: a numpy per-pixel ray march over a wall-block height field. It handles real pitch, smooth zoom, the cutaway, AO, baked torch and lava light, fog, a depth buffer for sprite occlusion, and picking. Timings on the box: 480×300 in about 85 ms, 400×250 in about 59 ms, 320×200 in about 34 ms.

The previews compose the HD player exactly like player_hd_client (z-order, hair tint, tier tint) in a coloured noble doublet, hose, boots and cloak.

Note: running `tools/make_textures.py` on its own writes the older numpy draft versions into `textures/`. The shipped wall, floor and top textures come from `bake_stones.py` followed by `grade.py`.
