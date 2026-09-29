# Castle Realm, phase 1: realm map + Duskspire Keep (gothic castle #1)
- `realm_map_and_gothic_pack.zip` holds the JSON (realm map, castle data, checker result), the sprites (1x and 2x layers, 12 gate frames, 4 floor cutaways), the models (.blend/.glb), the previews, the tools and the Blender scripts.
- `castle_realm_overview.png` shows the realm map, the before (Stonehaven) and after (Duskspire) castles, a 3/4 hero render and the 4 floor previews.
- `work/previews/gothic_floor1..4_preview.png` are the per-floor previews with room labels, doors, stairs, the exit and the checker result. `realm_map_preview.png` is the realm map and `gothic_gate.gif` is the gate animation.
- `CASTLE_REALM_CURSOR_PROMPT.md` is the step-by-step prompt. Everything sits behind `USE_CASTLE_REALM`.

To rebuild:
```
~/bin/blender -b -P work/blender_scripts/gothic.py -- --fast
~/bin/blender -b -P work/blender_scripts/floors.py
python work/tools/realm_data.py    # the checker (exit code 1 on failure)
python work/tools/realm_post.py
```
