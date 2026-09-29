# Void Sanctum v2: design pack

This is a design and prototype only. Nothing in the game repo was changed, and nothing was pushed.

| File | What it is |
|---|---|
| `VOID_CODE_REVIEW.md` | How the current Sanctum works, with file:line references (instancing, AI, loot, doors, fog, bosses) |
| `VOID_DUNGEON_DESIGN.md` | The design: tile map, zones, monster table, keys and seals, secrets, items, bridge, boss, extras, score |
| `CURSOR_PROMPT.md` | A step-by-step prompt for Cursor: investigate first, then phases A–G, each behind `USE_NEW_VOID_DUNGEON` and each ending in a stop |
| `void_map_full.png` | The full map, with a legend, the route and a "before" inset |
| `void_zones_gamescale.png` | Each zone at game tile size 40, plus a fog-of-war mock |
| `void_bridge_boss_closeup.png` | Rift Edge, shrine, warning prompt, the Narrow Way with void wind, the Nyxarath arena and the boss bar |
| `void_secret_wall_before_after.png` | Cracked-wall hint (with a 2× zoom), then the Hidden Reliquary revealed |
| `void_locked_door_and_key.png` | Amethyst Seal locked and unlocked, plus the 3 keys at preview and inventory size |
| `reference_code/void_map.py` / `.json` | Map data: grid, zones, spawns, doors, keys, secrets, chests, lore, bridge, boss |
| `tools/void_render.py`, `tools/void_concepts.py` | Headless renderers built on the game's own drawers, with the prototype tile drawers and route validation |

To re-render, run this against a clone of main:

```
SDL_VIDEODRIVER=dummy MYTHO_REPO=<clone> python tools/void_concepts.py <out_dir>
```
