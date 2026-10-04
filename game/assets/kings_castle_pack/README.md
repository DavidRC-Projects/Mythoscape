# Castle Realm phase 3: The King's Castle

- `kings_castle_pack.zip` is the light pack: 1x sprites, floors, JSON, previews, tools, Blender scripts, concepts, prompt and overview. Unzip it into `client/assets/castle_realm/`.
- `kings_castle_hires_and_models_optional.zip` is optional: 2x sprites, full renders and the .blend/.glb models.
- `kings_castle_overview.png` shows the realm map, a before/after at the same pixel scale, hero shots and every floor.
- `previews/` holds one preview per floor (4 keep floors + the barracks), the realm map preview and the gate GIF.
- `KINGS_CASTLE_CURSOR_PROMPT.md` is the Cursor prompt. It plugs into `CASTLE_REALM_CURSOR_PROMPT.md` (step 1 is investigation only, everything sits behind `USE_CASTLE_REALM`, and nothing is merged or pushed).
- To re-check: `python tools/realm_data.py` prints `RESULT: PASS`.
- To rebuild:
  1. `~/bin/blender -b -P blender_scripts/king.py -- --fast`
  2. `~/bin/blender -b -P blender_scripts/king_floors.py --`
  3. `python tools/king_post.py`
