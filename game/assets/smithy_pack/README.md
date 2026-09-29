# Gareth's Smithy v2 pack

Same pipeline, camera and sprite format as `/workspace/buildings/`: ortho, azimuth 0, elevation 32°, Y pre-stretched by 1/sin 32, 40 px per tile at 1x and 80 at 2x, `origin_px` = the NW corner of tile (78,4).

**Inside `smithy_pack.zip`:**
- `sprites/1x/smithy/` and `sprites/2x/smithy/`:
  - `ground.png`, `body.png`, `cutaway.png` (1x also has `meta.json`);
  - FX frames: `body_glow0-2.png` (forge glow pulse) and `smoke0-3.png` (chimney smoke).
- `json/smithy.json` (buildings-pack format plus `fx`) and `json/render/smithy.json`.
- `concepts/`: `smithy_game_1x.png`, `smithy_inside_1x.png`, `smithy_walkability_1x.png`, `smithy_fx_preview.gif` and `hero/smithy.png`.
- `models/smithy.blend` and `.glb`.
- `blender_scripts/`: `smithy_design.py` (the design), `house.py` (the driver, with glow and smoke frames added) and the unchanged kit. Plus `smithy_post.py`.
- `SMITHY_CURSOR_PROMPT.md` and `smithy_before_after.png`.

**Rebuild:**
```
~/bin/blender -b -P blender_scripts/house.py -- --key smithy --out <dir>
python smithy_post.py
```
