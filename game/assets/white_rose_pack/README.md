# Castle Realm, phase 2: White Rose Castle (48×48 tiles, 4× the Stonehaven area)
- `white_rose_pack.zip`: sprites, floors, JSON, previews, tools and scripts. The 2x sprites, full reference renders and models (.blend/.glb) are in `white_rose_hires_and_models_optional.zip`.
- `white_rose_overview.png`: the realm map, before (Stonehaven at the same pixel scale) and after, hero shots and the 4 floors.
- `work/previews/rose_floor1..4_preview.png`: the floor previews. `rose_gate.gif` and `rose_fountain.gif` show the animations; `realm_map_preview.png` is the map.
- `WHITE_ROSE_CURSOR_PROMPT.md` plugs into `../CASTLE_REALM_CURSOR_PROMPT.md`.

To rebuild:
```
~/bin/blender -b -P work/blender_scripts/rose.py -- --fast
~/bin/blender -b -P work/blender_scripts/rose_floors.py
python work/tools/realm_data.py
python work/tools/rose_post.py
```
