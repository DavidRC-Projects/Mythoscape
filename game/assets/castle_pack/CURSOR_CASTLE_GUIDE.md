# CURSOR_CASTLE_GUIDE: Stonehaven Castle v2 (bigger 3D-looking castle with moat and working drawbridge)

Pack: `castle_pack.zip`. Everything was built from Mythoscape main @ 8ee3b49 (2026-09-25 12:04 BST). Every repo claim below comes from that commit, so **re-verify each one against current main and against David's local build** before you code.

## 0. TL;DR for Cursor
- A pre-rendered OSRS-style castle drawn as 2D layers. It has 8 round towers with conical roofs, a keep, a gatehouse, a moat, a drawbridge and a portcullis. It fits the current pygame client, uses the same camera and scale as the props pack, and is tile-locked at TILE 40.
- The new footprint is **x 100–123, y 31–54** (24×24 = 576 tiles, 2.33× the old 19×13 = 247). **The world is NOT resized** and no other content moves. The castle grows north over the grass belt and the mountain's south face (rows 31–41) and east past the old city wall (x 119–123). It becomes the city's NE bastion.
- Only the castle's own contents move. Every interior spot, the knights and the champion shift by **(+3, −2)**. Herald Rowan moves onto the south wall-walk at (107,51).
- The gate is a **client-only visual state machine**. When the local player steps onto the trigger tiles, the bridge lowers and then the portcullis rises (12 frames). About 1.5 s after they leave, it plays in reverse. The server keeps treating the bridge and gate tiles as walkable PATH, because it has no door logic today.
- Everything sits behind `USE_NEW_CASTLE` in one shared module that both client and server import. With the flag off, the game must be identical to today (old map, old castle drawing, old spots).
- `tools/castle_map_patch.py` is the reference map stamp plus a flood-fill checker. It must print **ALL PASS**.

## 1. What the repo does today (8ee3b49; verify)
| Area | Where | Today | Hint to verify |
|---|---|---|---|
| World size | `server/world_map.py` | 160×115 grid; `WALKABLE_TILES = {GRASS, PATH, FLOOR, FISH_SPOT, STONE}`; WATER and WALL block | `rg -n "WIDTH\|HEIGHT\|WALKABLE_TILES" server/world_map.py` |
| Castle stamp | `generate_world` ~l.504 | `_rect(100,42,118,54, WALL)`, floor 102..116 × 44..52, gate PATH (108/109, 53/54), STONE plaza 104..114 × 54..58 | `rg -n "_rect\(100" server/world_map.py` |
| City wall | same | `_border(78,40,120,72)`; north road gap at x 98–99, y 40 | `rg -n "_border" server/world_map.py` |
| Zones | `ZONES` | `mountains (105,1,125,34)` is listed **before** `city (78,40,120,72)`; `get_zone` returns the first match | `rg -n "ZONES\|def get_zone" server/world_map.py` |
| Tree clearing | `_BUILDING_FOOTPRINTS` ~l.663 | repeats (100,42,118,54) | `rg -n "_BUILDING_FOOTPRINTS"` |
| Movement | server `handle_move` | 4-neighbour moves; blocked by non-walkable tiles and `WORLD.occupied`; **no door logic** | `rg -n "def handle_move"` |
| Building data | `server/content.py` `BUILDINGS` | `stonehaven_castle` x 100–118, y 42–54 | `rg -n "stonehaven_castle" server/content.py` |
| Doors | content | `castle_gate` (108,54) enter (108,52) exit (108,56); `castle_gate_e` (109,54) | same |
| Interior | content | throne (110,45), rug (110,48), table (106,48), chairs (105/107,48), banners (104/116,45), rack (103,50), chest (115,50), braziers (103/115,46), candle (108,46) | `rg -n "castle_" server/content.py` |
| NPCs | content | Herald Rowan (110,47); knights (108,50),(112,48),(106,46),(110,52),(114,50); champion (110,48); places `stonehaven_castle` (108,50), `quest_herald_rowan` (110,47), `knights` (108,50), `mythos_champion` (110,48) | `rg -n "herald\|knight\|champion" server/content.py` |
| Shared source | client | `client.py` imports `server/world_map.py` and `server/content.py` directly, so one change updates both | `rg -n "world_map\|content" client.py` |
| Castle drawing | `client.py` `draw_building_roofs` ~l.5340 | at yaw 0 blits `client/assets/buildings/stonehaven_castle.png` via `building_sprites.draw_building_sprite`; otherwise `sprites._draw_castle_keep` (`characters/procedural_sprites_finished.py` ~l.5281). Roofs are drawn **after** entities (~l.5152) | `rg -n "draw_building_roofs\|_draw_castle_keep"` |
| Roof hiding | `entity_hidden_by_roof` | hides entities inside x0..y1 while the player is outside | `rg -n "entity_hidden_by_roof"` |
| Inside test | `player_inside_building` ~l.5235 | floor rect **or** door tile | |
| Door anim | loop ~l.4810 | `open_=near` (Chebyshev ≤ 2); `is_gate` for ids containing "castle"; `_building_for_door` skips `volcano`/`castle` kinds | |
| Walkability | `tile_walkable` ~l.2567, `player_xy` ~l.2554 | TILE = 40 | |

**Important:** David's screenshot shows a castle with round towers, conical roofs and marbled stone. **That version is not on main or on the `cursor/*` branches at 8ee3b49**, so it is probably a local, uncommitted change. Find it (`git status`, `git stash list`, `git branch -a`, recently changed files under `client/assets/buildings/` and `characters/`). If it is what David runs today, it is the flag-off fallback and must stay intact.

## 2. Design
- Concentric castle: moat → curtain wall with 4 corner towers, 2 east/west mid towers and 2 gate towers (8 round towers, conical dark roofs, red flags) → bailey (well, training dummies, archery target, hay cart, sheds, barrels) → keep with bartizans and a central tower with lit windows.
- Gatehouse: brick-voussoir arch, machicolations, coat of arms, winch house and chains. A **drawbridge** spans the moat to the south apron, and there is an iron **portcullis**. Braziers stand on the bridge-abutment posts; there are torches, banners and arrow slits.
- Palette: grey stone, dark slate roofs, red banners (matches the monsters, dungeons and props packs).
- Tris: 17,962 total (body 11,695). The model is `models/stonehaven_castle_v2.{blend,glb,bam}`.
- Camera: ortho, azimuth 0, elevation 32°, sun (40,15,−30). Scene Y is pre-stretched by 1/sin 32° so **ground rows are exactly TILE px apart**, which makes the sprite tile-locked to the grid.

### 2.1 Walkability grid (24×24, x 100–123 left→right; row = world y)
```
y 31 MMMMMMMMMMMMMMMMMMMMMMMM
y 32 MMMMMMMMMMMMMMMMMMMMMMMM
y 33 MMWWWWWWWWWWWWWWWWWWWWMM
y 34 MMWWWWWWWWWWWWWWWWWWWWMM
y 35 MMWWFFFKKKKKKKKKKFFFWWMM
y 36 MMWWFFFKKKKKKKKKKFFFWWMM
y 37 MMWWFFFKKKKKKKKKKFFFWWMM
y 38 MMWWFFFKKKKKKKKKKFFFWWMM
y 39 MMWWFFFKKKKKKKKKKFFFWWMM
y 40 MMWWFFFKKKKKKKKKKFFFWWMM
y 41 MMWWFFFFFFFFFFFFFFFFWWMM
y 42 MMWWFFFFFFFFFFFFFFFFWWMM
y 43 MMWWFFFFFFFFFFFFFFFFWWMM
y 44 MMWWFFFFFFFFFFFFFFFFWWMM
y 45 MMWWFFFFFFFFFFFFFFFFWWMM
y 46 MMWWFFFFFFFFFFFFFFFFWWMM
y 47 MMWWFFFFFFFFFFFFFFFFWWMM
y 48 MMWWFFFFFFFFFFFFFFFFWWMM
y 49 MMWWFFFFFFFFFFFFFFFFWWMM
y 50 MMWWFFFFFFFFFFFFFFFFWWMM
y 51 MMWWWAAAWWWPPWWWAAAWWWMM
y 52 MMWWWWWWWWWGGWWWWWWWWWMM
y 53 MMMMMMMMMMMBBMMMMMMMMMMM
y 54 MMMMMMMMMMMBBMMMMMMMMMMM
```
Legend: M moat · B bridge · G portcullis/gate tile · P gate passage · A wall-walk (y 51, x 105–107 and 116–118) · W wall/tower · K keep · F floor/bailey.
- **Server mapping:** M → WATER; W, K → WALL; F, A, P → FLOOR; B, G → PATH (always walkable).
- **Client (optional):** treat B/G as blocked while the gate isn't fully open, for local prediction only. If you do, a server-accepted move onto them must still be honoured. The simplest safe option is to leave them walkable; the trigger fires one tile early, so the animation leads the player.

## 3. The exact map expansion plan (no resize)
Put this in `server/world_map.py` inside `generate_world`, **after** the city wall, mountains and old castle are stamped, and **before** the tree scatter. Use the same sequence as `apply_new_castle(grid, wm)` in `tools/castle_map_patch.py`:
1. `if USE_NEW_CASTLE:` run steps 2–5. Keep the old castle stamp in place (it is fully overwritten, because the old footprint lies inside the new one) or put it in an `else`. The result must be the same either way.
2. Stamp x 100–123, y 31–54 from the grid above: M → WATER, W/K → WALL, F/A/P → FLOOR, B/G → PATH. This replaces the city-wall segments at y = 40 (x 100–120) and x = 120 (y 41–54). There, the castle's wall and moat are the city wall. The north road gap at x 98–99 is untouched. The city wall joins the castle's west moat at x 99/100 on y 40 and its south moat at x 120 on y 55. The checker confirms there is no leak.
3. Apron: y 55, x 104–119 → STONE, with PATH at x 111–112 for y 55–56. The old STONE plaza south of it stays.
4. `_BUILDING_FOOTPRINTS`: replace (100,42,118,54) with (100,31,123,55) so no trees spawn in the moat. The only tree lost is the maple at (100,34).
5. Zones: `get_zone` returns the first match and `mountains (105,1,125,34)` overlaps rows 31–34. Either add a special case at the top of `get_zone` (`if USE_NEW_CASTLE and 100<=x<=123 and 31<=y<=55: return "city"`) or set mountains y1 = 30 under the flag. The mountain pass (row 30 is solid rock) stays unchanged; the checker verifies this.

Checker (`python3 tools/castle_map_patch.py --repo <repo>`) results at 8ee3b49: **ALL PASS**. The inside is reachable only through the gate, the moat and walls don't leak, no previously reachable area outside the castle is lost, the mountain pass is unchanged and Herald Rowan is reachable. Tiles replaced: GRASS 184, WALL 210, STONE 44, FLOOR 135, PATH 2, MAPLE 1.

## 4. Content changes (`server/content.py`, under the flag)
- `BUILDINGS["stonehaven_castle"]`: x0 100, y0 31, x1 123, y1 54; floor 104,35 → 119,51 (keep id, name, kind, style and material).
- Doors: `castle_gate` (111,52) enter (111,50) exit (111,55); `castle_gate_e` (112,52) enter (112,50) exit (112,55).
- Interior spots (old + (3,−2); same layout, same ids and kinds):

| spot | new |
|---|---|
| castle_throne | (113, 43) |
| castle_rug | (113, 46) |
| castle_table | (109, 46) |
| castle_chair_a | (108, 46) |
| castle_chair_b | (110, 46) |
| castle_banner_w | (107, 43) |
| castle_banner_e | (119, 43) |
| castle_rack | (106, 48) |
| castle_chest | (118, 48) |
| castle_brazier_w | (106, 44) |
| castle_brazier_e | (118, 44) |
| castle_candle | (111, 44) |

- NPCs, spawns and place labels:

| id | kind | old | new | where |
|---|---|---|---|---|
| herald_rowan | npc | (110, 47) | (107, 51) | south wall-walk, west of the gatehouse (drawn lifted) (lift 118 px) |
| quest_herald_rowan | place label | (110, 47) | (107, 51) | follows Herald Rowan |
| mythos_champion | monster spawn + place | (110, 48) | (113, 46) | inner bailey in front of the keep (quest text says courtyard) |
| knight#1 | monster spawn | (108, 50) | (111, 48) | bailey, inside the gate |
| knight#2 | monster spawn | (112, 48) | (115, 46) | bailey |
| knight#3 | monster spawn | (106, 46) | (109, 44) | bailey |
| knight#4 | monster spawn | (110, 52) | (109, 55) | gate guard, west of the bridge on the apron (outside) |
| knight#5 | monster spawn | (114, 50) | (114, 55) | gate guard, east of the bridge on the apron (outside) |
| knights (place) | place label | (108, 50) | (111, 48) |  |
| stonehaven_castle (place) | place label | (108, 50) | (111, 45) |  |
| wall_walk_extra_w | optional ambient spot | — | (105, 51) |  (lift 118 px) |
| wall_walk_extra_e | optional ambient spot | — | (117, 51) |  (lift 118 px) |

## 5. Client drawing (2D layers)
Files are in `sprites/1x/` (TILE 40) and `sprites/2x/` (for TILE 80 or zoom). Full layers are 1040×1400 at 1× with `origin_px` [40,400], and 2080×2800 at 2× with origin [80,800]. `origin_px` is the pixel of the NW corner of tile (x0,y0) = (100,31) inside every full layer.
```python
# behind USE_NEW_CASTLE; cache scaled surfaces per (layer, TILE)
s = TILE / 40
sx = tile_screen_x(100) - 40 * s
sy = tile_screen_y(31) - 400 * s
screen.blit(layer_scaled, (sx, sy))
# gate frame: blit at (sx + 466*s, sy + 1027*s)   # crop_1x = [466,1027,574,1377]
```
Draw order (world space, same camera offset as the tiles):
1. **ground** (`castle_ground.png`): after floor tiles, before any entity. Moat water with soft glow, banks, reeds, lilies, abutment and apron lip.
2. Entities with y < 31 (north of the castle).
3. **back** (`castle_back.png`): walls, towers, keep, gatehouse, bailey.
4. **gate** (`gate/gate_NN.png`, current frame): right after back.
5. Entities with 31 ≤ y ≤ 54, y-sorted. Wall-walk NPCs (y 51, x 105–107 / 116–118) are drawn **lifted 118 px × TILE/40**.
6. **posts** (`castle_posts.png`): y-sorted like an entity on row 54.
7. Entities with y ≥ 55.
8. **front** (`castle_front.png`): after all entities. South parapets; wall-walk NPCs stand behind them.
9. **Inside** (player on the floor rect or a door tile): draw **cutaway** instead of back + front; ground, gate and posts are still drawn. The cutaway cuts walls, towers and keep at 1.6 m so the interior spots and props show.
- Under the flag, skip the old castle roof/keep drawing (`draw_building_sprite` / `_draw_castle_keep`) for this building only. Keep that code.
- `entity_hidden_by_roof`: under the flag, hide only entities on bailey F/P tiles, as today. Never hide entities on moat, bridge, apron or wall-walk tiles, and never hide the gate guards at (109,55)/(114,55).
- Interior props (props pack) keep drawing at their shifted spots.
- Existing door-proximity loop: skip the `castle_gate*` door visuals under the flag. The gate animation replaces them.

## 6. Gate state machine (client-only visual)
- Frames 0–11: `BRIDGE_DEG = [-88,-84,-74,-58,-38,-16,0,0,0,0,0,0]`, `PORTCULLIS_UP_M = [0,0,0,0,0,0,0,0.4,0.95,1.5,1.95,2.25]`, `DUR_MS = [220,80,80,80,80,80,140,90,90,90,90,200]`. Frame 0 = closed (bridge up), frame 11 = open.
- Trigger tiles: outer (110–113, 55); hold (111–112, 51–54); inner (111–112, 49–50).
- The gate opens (plays forward from the current frame) while the **local** player stands on any trigger tile. It closes (plays in reverse) once they have been off all of them for `close_delay_ms` = 1500. It can reverse mid-animation.
- Other players don't drive it. It's purely visual: no server messages and no persistence.

## 7. Feature flag
Create `server/feature_flags.py` with `USE_NEW_CASTLE = True` (it may also read an env var). Import it in `world_map.py`, `content.py` and `client.py`. Every change is `if USE_NEW_CASTLE: new else: old unchanged`. With the flag off, the `generate_world` grid must be identical to today (compare a hash of the tile grid) and the castle must look exactly as it does now.

## 8. 3D route (Panda3D, future)
`tools/prop_loader.py` loads `models/stonehaven_castle_v2.glb` or `.bam`. Separate nodes: `castle_bridge`, `castle_portcullis`, `castle_chain_l`, `castle_chain_r` (pivots already set). `json/render_info.json` has per-frame matrices; the glb also contains an `Animation` clip. In the bam, the blend2bam collision nodes (`COL_*`, `TRIGGER_*`, 14 in total) are **visible by default**, so hide every `+CollisionNode` after loading (`tools/panda_castle_check.py` does this). Verified: glb and bam both load, all 4 gate nodes are found and posed, and the renders are in `panda_renders/`.

## 9. Verification to do in the repo
1. Flood-fill check on the flagged `generate_world` grid (adapt `tools/castle_map_patch.py`) → ALL PASS.
2. Screenshots at the same camera, before (flag off) and after (flag on): outside with the gate closed, player on the bridge with the gate open, inside (cutaway), Herald on the wall-walk, knights and champion in the bailey.
3. A GIF or frame strip of the gate opening and closing as the player walks in and out.
4. Enter through the gate. Talk to Herald Rowan, fight knights and the champion, and use every interior interactable at its new spot.
5. Flag off → identical grid hash and identical screenshots.
6. No other building, NPC, zone or road changed (diff the content tables with the flag on vs off, outside the castle).

## 10. Pack contents
- `sprites/1x`, `sprites/2x`: ground/back/posts/front/cutaway, `gate/gate_00..11.png`, `player_ref_1p8m.png`; `sprites/castle_v2.json` (same as `json/castle_v2.json`).
- `concepts/`: `castle_closed_game_1x.png`, `castle_open_game_1x.png`, `castle_inside_cutaway_1x.png`, `castle_walkability_overlay.png`, `before_after_game_scale.png`, `before_after_front_closeup.png`, `hero_34.png`, `hero_gate.png`, `gate_open_close.gif`, `gate_frames_sheet.png`.
- `models/`: `.blend` (full pack only), `.glb`, `.bam`, `ref_player_1p8m.glb`.
- `panda_renders/`, `json/render_info.json`, `json/stonehaven_castle_v2.json`.
- `tools/`: `castle_map_patch.py`, `castle_post.py`, `panda_castle_check.py`, `prop_loader.py`. `blender_scripts/`: `castle.py` (driver), `castle_geo.py`, `osrs_kit.py`, `prop_parts.py`. To rebuild: `blender -b -P blender_scripts/castle.py`, then `python3 tools/castle_post.py`.

## 11. Scores and known limitations
Self-score about 8.5/10. It reads as a solid 3D OSRS-style castle, not cardboard, and matches the other packs.
- In the game view, part of the south moat is hidden behind the gate and corner tower bases.
- The Y-stretch makes the conical roofs look slightly bulbous.
- The gate frame crop is tall (108×350 at 1×), which works but isn't minimal.
- The lowered bridge and raised portcullis don't cast shadows on the static layers.
- The raised portcullis teeth are only just visible under the arch.
- Knights and the herald in the concept images are recoloured reference figures; the game uses its own sprites.
- Gate tiles are always walkable server-side (there is no door logic), so the gate is a visual only.
