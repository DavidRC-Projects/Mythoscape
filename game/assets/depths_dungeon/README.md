# The Depths v2 pack: crypt descent

| File | What it is |
|---|---|
| `DEPTHS_CODE_REVIEW.md` | what the Depths is today and what's Depths-specific (shared systems → `/workspace/void_dungeon/VOID_CODE_REVIEW.md`) |
| `DEPTHS_DUNGEON_DESIGN.md` | zones, tile map, monsters and stats, keys/doors, secrets, sarcophagi, lore, bridge hazard, boss phases and loot, extras, route check, score |
| `CURSOR_PROMPT.md` | the phased build prompt: Step 1 investigate → Phases A–G, flag `USE_NEW_DEPTHS_DUNGEON`, reuse the void shared systems |
| `depths_map_full.png` | the full map with legend, route and a before inset |
| `depths_bridge_boss_closeup.png` | the Bone Bridge (grasping hands) and Morvath's arena |
| `depths_secret_wall_before_after.png` | the skull-lever Drowned Reliquary, before and after |
| `depths_locked_door_and_key.png` | the Bone Gate locked and unlocked, plus the three keys |
| `depths_sarcophagus_search_ambush.png` | search → loot / ambush |
| `depths_zones_gamescale.png` | the zones at game scale, plus fog of war |
| `reference_code/depths_map.py`, `.json` | the map data (source of truth) |
| `tools/depths_render.py`, `tools/depths_concepts.py` | the renderer (adapted from the void tools) and the route check |

To regenerate (needs pygame and a clone of the repo; set REPO in `depths_render.py`):
`cd tools && python depths_render.py /tmp/out` (route check), then `python depths_concepts.py <outdir>`.
