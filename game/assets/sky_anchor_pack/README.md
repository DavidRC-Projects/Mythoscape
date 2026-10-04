# Castle Realm phase 4: Sky-Anchor Citadel

- `sky_anchor_pack.zip` — light pack (1x sprites, floors, JSON, previews, tools, scripts, concepts, prompt, overview). Unzip into `client/assets/castle_realm/`.
- `sky_anchor_hires_and_models_optional.zip` — 2x sprites, full renders, .blend/.glb.
- `sky_anchor_overview.png` — realm map with all 4 castles, before/after, heroes, floors.
- `previews/` — floor previews, realm map, gate + waterfall GIFs.
- `SKY_ANCHOR_CURSOR_PROMPT.md` — Cursor prompt (investigation first; `USE_CASTLE_REALM`; never merge/push).
- Footprint: **48×48** at realm (26,118)–(73,165), 4× Stonehaven. Gate apron (49,166)/(50,166).
- Re-check: `python tools/realm_data.py` → `RESULT: PASS`.
- Rebuild: `~/bin/blender -b -P blender_scripts/sky.py -- --fast` then `sky_floors.py` then `python tools/sky_post.py` (needs libEGL on PATH / LD_LIBRARY_PATH).
