# CURSOR_BUILDINGS_GUIDE: 11 bigger, unique 3D-looking houses for Mythoscape

Pack: `buildings_pack.zip`. Built from Mythoscape main @ 8ee3b49 (2026-09-25 12:04 BST). Every repo claim below comes from that commit, so **re-verify each one against current main** before coding.

## 0. TL;DR for Cursor
- Eleven buildings share one house template today: gabled roof, grey chimney, arched double door, plinth with a ramp, two windows. Each one is replaced by its own pre-rendered OSRS-style low-poly building. They use the same camera and tile lock as the castle pack (ortho, looking north, 32°, 40 px tiles).
- Every footprint grows to about 1.33–2.07× its old size. **Doors never move.** Each building keeps its door tile and its south wall row (`y1`); it grows north, west and east into free space. Door, enter and exit tiles, every interior spot, every NPC inside and every interaction stay exactly where they are.
- **Only one thing outside a building moves:** Lira the Jeweler (NPC + the `jeweler` place label) goes from (33,8) to (35,8), because the General Store grows east over her tile.
- The world is not resized. No roads are cut apart. `tools/buildings_map_patch.py` stamps the new footprints and runs a flood-fill checker: **ALL PASS**.
- Everything sits behind `USE_NEW_BUILDINGS` in one shared module, with the old code kept. With the flag off, the game is identical to today. Roll it out one building at a time, starting with the **General Store**.

## 1. What the repo does today (8ee3b49; verify)
| Area | Where | Today |
|---|---|---|
| Map stamp | `server/world_map.py` `generate_world` → `_building(x0,y0,x1,y1,door_x)` (~l.144–165 village, ~l.331–332 harbour; city houses are stamped with the city block) | WALL rect, FLOOR inset by 1, south row WALL, `grid[y1][door_x] = PATH`, then apron PATH tiles below each door (~l.170–180) |
| Buildings | `server/content.py` `BUILDINGS` (~l.2283+) | `cottage_nw` Elder's Hall, `cottage_ne` General Store, `cottage_sw` The Resting Ox, `cottage_se` Farmhouse, `bank`, `pet_emporium`, `harbour_tackle`, `harbour_fishmonger` (Kai's Catch), `city_house_nw` Stonehaven Cottage, `city_house_sw` Stonehaven House, `city_barracks` City Barracks |
| Doors | `content.INTERACTABLES` `*_door` (kind `door`, `building` id) | door at (door_x, y1), enter = 2 tiles north, exit = 1 tile south |
| Interiors | `INTERACTABLES` blocks per building (note: some `# floor …` comments are stale, e.g. the General Store's says 16–22) | furniture spots inside the old floor rects |
| Tree clearing | `world_map._BUILDING_FOOTPRINTS` (~l.663) | copy of every rect ("keep in sync with content.BUILDINGS") |
| Drawing | `client/client.py` `draw_building_roofs` (~l.5340). At yaw 0 it calls `client/building_sprites.draw_building_sprite(rect, id)`, which blits `client/assets/buildings/<id>.png` stretched into the footprint rect using the sidecar `<id>.json` pads. Otherwise it uses `sprites.draw_building_roof` (procedural, `characters/building_shell3d.py`). The PNGs are bakes from `tools/bake_building_sprite.py` / `tools/blender_render_building.py` of **one shared template** | drawn after entities; the name label is drawn at `rect.y + 0.14*h` |
| Inside | `player_inside_building` (~l.5235) | floor rect **or** the door tile → cutaway (`sprites.draw_building_cutaway`) |
| Roof hiding | `entity_hidden_by_roof` (~l.5259) | hides entities inside x0..x1 × y0..y1 while the player is outside |
| Movement | server `handle_move`, `WALKABLE_TILES` | 4-neighbour; WALL blocks |

The third Stonehaven stone house (label cut off in the screenshot) is **`city_barracks` "City Barracks"** (110,58)–(118,68), door (114,68). It is the only other `city_*` house entry with the same template. It's designed as a stepped stone corner house with a balcony and barracks touches (shield, banner, weapon rack, training dummy), so it matches the Stonehaven set and still fits its purpose.

## 2. Map plan (exact; no resize)
| Building | old rect (tiles) | new rect (tiles, ×) | new floor | door (unchanged) | 1x sprite @ origin_px | tris |
|---|---|---|---|---|---|---|
| Elder's Hall (`cottage_nw`) | 3,3–11,11 (81) | 2,2–17,11 (160, 1.98×) | 3,3–16,9 | (7,11) enter (7, 9) exit (7, 12) | 800×760 @ (80.0, 320.0) | 2100 |
| The Resting Ox (`cottage_sw`) | 3,24–11,32 (81) | 2,21–15,32 (168, 2.07×) | 3,22–14,30 | (7,32) enter (7, 30) exit (7, 33) | 640×840 @ (40.0, 320.0) | 3368 |
| General Store (`cottage_ne`) | 23,3–31,11 (81) | 23,2–33,11 (110, 1.36×) | 24,3–32,9 | (27,11) enter (27, 9) exit (27, 12) | 520×640 @ (40.0, 200.0) | 2628 |
| Farmhouse (`cottage_se`) | 23,24–31,32 (81) | 23,23–35,32 (130, 1.60×) | 24,24–30,30 | (27,32) enter (27, 30) exit (27, 33) | 600×640 @ (40.0, 200.0) | 1602 |
| Village Bank (`bank`) | 34,14–42,20 (63) | 33,13–43,20 (88, 1.40×) | 34,14–42,18 | (38,20) enter (38, 18) exit (38, 21) | 520×600 @ (40.0, 240.0) | 1595 |
| Pet Emporium (`pet_emporium`) | 50,24–60,32 (99) | 50,22–63,32 (154, 1.56×) | 51,23–59,30 | (55,32) enter (55, 30) exit (55, 33) | 640×680 @ (40.0, 200.0) | 3434 |
| Stonehaven Cottage (`city_house_nw`) | 82,44–90,52 (81) | 81,42–91,52 (121, 1.49×) | 82,43–90,50 | (86,52) enter (86, 50) exit (86, 53) | 520×720 @ (40.0, 240.0) | 1336 |
| Stonehaven House (`city_house_sw`) | 82,58–90,66 (81) | 80,58–92,66 (117, 1.44×) | 81,59–91,64 | (86,66) enter (86, 64) exit (86, 67) | 600×720 @ (40.0, 320.0) | 2276 |
| City Barracks (`city_barracks`) | 110,58–118,68 (99) | 109,57–119,68 (132, 1.33×) | 110,58–118,66 | (114,68) enter (114, 66) exit (114, 69) | 520×720 @ (40.0, 200.0) | 2402 |
| Kai's Catch (`harbour_fishmonger`) | 134,20–142,28 (81) | 130,20–143,28 (126, 1.56×) | 135,21–142,26 | (138,28) enter (138, 26) exit (138, 29) | 640×600 @ (40.0, 200.0) | 2254 |
| Harbourreach Tackle (`harbour_tackle`) | 134,6–142,14 (81) | 134,6–146,14 (117, 1.44×) | 135,7–141,12 | (138,14) enter (138, 12) exit (138, 15) | 600×720 @ (40.0, 320.0) | 2338 |

Rules used for every building:
1. The south wall row `y1` and the door tile (door_x, y1) are unchanged. The new rect contains the old one.
2. **Floor** = the new interior (it contains every old interior spot and NPC). The row(s) between the floor and `y1` are the **porch / stoop** zone: WALL tiles where props stand (barrels, benches, the ice counter, the birdcage and so on). The **doorway column** (door_x, floor_y1+1 … y1) is PATH, so you walk in exactly as before: exit tile → door tile → doorway → enter tile.
3. Yard parts inside the rect (Farmhouse barn + veg patch, Pet Emporium pen, Kai's market shed, the Tackle dock deck) are WALL. Players can't walk through fences, the pen or over the water.
4. Stamp it with the same `_building` logic, generalised to take a floor rect. Put it in `world_map.generate_world` behind the flag, update `_BUILDING_FOOTPRINTS` to the new rects, and keep the apron PATH tiles below each door.
5. Content under the flag: the new `x0..y1` and `floor_*` in `BUILDINGS`. Move `jeweler_lira` NPC and the `jeweler` place from (33,8) to (35,8). **Nothing else changes.**

Checker (`python3 tools/buildings_map_patch.py --repo <repo> [--dump]`) results at 8ee3b49: **ALL PASS**.
- Old rects match `content.BUILDINGS`, and the doors are unchanged.
- No footprint overlaps or touches another building; there is at least a 1-tile gap, including the castle, smithy and void sanctum.
- The only entity on a newly blocked tile is the planned Lira move, and her target is walkable.
- Every old interior spot and NPC stays inside its new floor.
- No walkable tile outside the footprints loses reachability from spawn.
- Every floor is fully reachable, and each building is sealed except through its door.
- Door zones are unchanged.
- Tiles changed: GRASS→WALL 273, GRASS→FLOOR 96, TREE→WALL 2, WATER→WALL 21 (Tackle deck), WALL→FLOOR 148, PATH→WALL 15, PATH→FLOOR 9, FLOOR→WALL 68 (old front floor row → porch), FLOOR→PATH 11, STONE→WALL 86, STONE→PATH 3, STONE→FLOOR 24.

Notes:
- **Bank:** the east–west village road at y 18 already runs into the bank's walls. The wider bank moves those two dead ends one tile out ((33,18) and (43,18)). No route is lost; the checker confirms it.
- **Tackle:** the deck covers the shore path x 143 (y 6–14) and 21 harbour water tiles (x 144–146, y 8–14). The shore strip stays reachable around it, and fishing still works from the rest of the harbour edge.
- **The old front floor row becomes porch.** No interior spot is on it (the checker verifies this), but a player standing there at deploy time would be inside a wall. Server login/teleport code should nudge them to the nearest walkable tile, as it does for other map edits. Please verify.

Walkability examples (W wall, F floor, D doorway PATH, P porch/yard WALL); all 11 are in `json/<key>.json`:
**General Store** (origin (23, 2))
```
WWWWWWWWWWW
WFFFFFFFFFW
WFFFFFFFFFW
WFFFFFFFFFW
WFFFFFFFFFW
WFFFFFFFFFW
WFFFFFFFFFW
WFFFFFFFFFW
PPPPDPPPPPP
PPPPDPPPPPP
```

**Farmhouse** (origin (23, 23))
```
WWWWWWWWWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
PPPPDPPPPPPPP
PPPPDPPPPPPPP
```

**Harbourreach Tackle** (origin (134, 6))
```
WWWWWWWWWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
WFFFFFFFWWWWW
PPPPDPPPPPPPP
PPPPDPPPPPPPP
```

## 3. The designs
Village (grass, warm timber, brown/red roofs):
- **Elder's Hall**: a longhall with dark log walls and a steep shingled roof with carved dragon-head finials. A cross gable projects over the door as a porch on carved pillars, with more pillars along a lean-to veranda, red and green banners, wide steps and a gold bargeboard.
- **The Resting Ox**: a two-storey inn. Stone ground floor, jettied timber-framed upper floor, two dormers and two chimneys. There is a stable wing with a stone arch and hay, a hanging ox-head sign, lanterns, benches and a table, stacked ale barrels and warm lit windows.
- **General Store** (v2b, facade-first): a tall two-storey front block (plank ground floor, jettied timber-framed upper floor with flower boxes). A **stepped false front** carries a red and gold shop signboard with a sack emblem and hides the low roof behind it. The rear block is lower, with a low side-gabled roof. It has a big display window under a red/cream awning, a hanging sack sign, a lean-to storeroom, and crates, sacks and barrels on the stoop.
- **Farmhouse**: a whitewashed thatched cottage with a thick hipped thatch roof and an eyebrow dormer. It has a red barn lean-to with X-braced doors and a hay loft, a fenced veg patch with cabbages and a scarecrow, hay bales, a water trough and a cart wheel.
- **Village Bank**: a solid grey ashlar block with a rusticated base and a hipped slate roof. A marble portico has 4 columns and a pediment with a gold coin emblem. There is a heavy iron-banded door, barred windows, lanterns and marble steps.
- **Pet Emporium** (v2b, facade-first): a tall two-storey teal front with yellow pilasters. A **scalloped pink false front** carries a big round paw-print medallion. The low purple roof sits behind it, and the rear block is lower. It has round-framed upper windows, twin awnings (yellow/pink and teal/cream), a hanging paw sign, a gold birdcage with a yellow bird by the door, flower boxes, and a fenced pen with a red-roofed kennel, a dog and a bowl.

Stonehaven (grey stone, slate roofs; a matching set with different shapes):
- **Stonehaven Cottage**: a small single-storey stone cottage with a hipped slate roof, a dormer, a big end chimney, corner quoins, flower boxes, planters and a bench.
- **Stonehaven House**: a two-storey townhouse with a string course, twin front gables and a projecting bay window with a slate roof. It has a blue door, blue shutters, two chimneys and a flower planter.
- **City Barracks** (v2b, facade-first): **terraced flat roofs with crenellated parapets**. The tall front block has corbels under its battlements and steps down to a lower crenellated rear terrace with crates. A round corner watch turret with a slate cone and a red flag stands at the front right. It has a timber balcony over an iron-banded door, a red shield plaque, twin red and gold banners, barred ground windows, arrow slits, a weapon rack, a training dummy and lanterns. It still matches the grey Stonehaven set.

Harbour:
- **Kai's Catch** (v2b, facade-first): a **side-gabled** (east–west ridge, eaves facing the camera), low-pitch two-storey white clapboard front with blue corner boards and shuttered upper windows. A big fish signboard stands above the eaves. The rear block is lower. It has a blue/white awning over an ice counter of fish, a hanging fish sign and nets on the wall. An open market shed has drying nets and hanging fish, plus barrels, crates and rope.
- **Harbourreach Tackle**: weathered blue-grey clapboard with a green roof, raised on a deck. A dock deck on stilts over the water holds a rod rack, coiled rope, lobster pots, a crate, a barrel and railings. There is an anchor sign, a lifebuoy and a lantern post.

## 4. Client drawing (2D layers)
Files: `sprites/1x/<key>/{ground,body,cutaway}.png` (TILE 40), `sprites/2x/<key>/…` (TILE 80 / zoom), and `sprites/1x/<key>/meta.json` (= `json/<key>.json`). `origin_px` is the pixel of the NW corner of tile (x0,y0):
```python
# behind USE_NEW_BUILDINGS and only for ids in NEW_BUILDINGS_ENABLED; cache scaled surfaces per (key, layer, TILE)
s = TILE / 40
sx = tile_screen_x(x0) - origin_px[0] * s
sy = tile_screen_y(y0) - origin_px[1] * s
screen.blit(layer_scaled, (sx, sy))
```
Draw order:
1. **ground**: after floor tiles, before entities (porch boards, steps, yard soil or grass, dock water).
2. **body**: y-sorted like an entity standing on row `y1`. Draw it after entities with y ≤ y1 and before entities with y > y1. If the current code can't y-sort buildings, drawing it where `draw_building_roofs` does today (after entities) is acceptable for step 1; say which you chose.
3. **cutaway**: replaces the body while the local player is inside.
- Under the flag, `player_inside_building` should also return True on the **doorway tiles** (`door.doorway_path_tiles`), not just the door tile, so the roof doesn't pop back while you walk through the 2-tile doorway.
- `entity_hidden_by_roof`: under the flag, hide only entities on the new **floor** rect. Entities on porch/doorway tiles stay visible, because props stand there and the player walks there.
- Name label: keep it. Use the same code, positioned against the new rect.
- Skip `building_sprites.draw_building_sprite` / the procedural shell for enabled ids, but keep that code.
- Sprites have a **1.4× vertical exaggeration** (`sprite_z_exaggeration`), because the old template's doors are ~93 px at TILE 40 (≈1.4× real scale). The 3D models are true scale.
- Interior furniture keeps drawing from the existing code at unchanged spots.

## 5. Feature flag
`server/feature_flags.py`: `USE_NEW_BUILDINGS = True` and `NEW_BUILDINGS_ENABLED = {"cottage_ne"}`, then grow the set one building at a time. Import it in `world_map.py`, `content.py` and `client.py`. A building uses the new rect, floor, stamp and sprites only if the flag is on **and** its id is in the set. Otherwise the old code runs unchanged. The Lira move happens only when `cottage_ne` is enabled. With the flag off, the tile-grid hash and `BUILDINGS` are identical to today.

## 6. 3D route (Panda3D, later)
`models/<key>.glb` and `.bam` (converted with `gltf2bam`) are one static node each (`<key>_body`, `<key>_ground`), true scale, local origin = NW corner of the footprint, +X east, −Y south. Verified: all 11 glb and bam load in Panda3D offscreen, and tris match (1,336–3,434 each). Renders are in `panda_renders/`.

## 7. Verification to do in the repo (per building)
1. Checker ALL PASS (adapt `tools/buildings_map_patch.py` to run on the flagged `generate_world`).
2. Before/after screenshots at the same camera: outside, standing on the doorway, inside (cutaway).
3. Enter and leave through the door. Every interior interaction works (for example, Shopkeeper Joe's shop opens and Guard Marcus is still inside). NPCs are at the same tiles.
4. Flag off (or id not enabled) → identical grid hash and screenshots.
5. For the General Store: Lira at (35,8), her dialogue, quest and gem shop work, and the `jeweler` label moved.

## 8. Pack contents
- `sprites/1x|2x/<key>/{ground,body,cutaway}.png`, `sprites/1x/<key>/meta.json`
- `json/<key>.json`, `json/buildings_v2.json` (all 11), `json/render/<key>.json` (camera/bounds)
- `models/<key>.{blend,glb,bam}`
- `concepts/contact_{village,stonehaven,harbour}.png` (game view + 3/4 view), `concepts/contact_all_game_1x.png` (all 11 side by side, same scale), `concepts/before_after_{village,stonehaven,harbour}.png`, `concepts/game/<key>_{game,inside}_1x.png`, `concepts/hero/<key>.png`
- `panda_renders/`
- `tools/`: `buildings_map_patch.py`, `houses_post.py`, `build_all.sh`, `panda_buildings_check.py`. `blender_scripts/`: `house.py` (driver), `houses_designs.py` (one function per building), `houses_geo.py` (helpers), `osrs_kit.py`, `prop_parts.py`. Rebuild with `tools/build_all.sh && python3 tools/houses_post.py`.

## 9. Scores and known limitations
Scores (/10). Round 1 gave one redo pass to the four under 8. Round 2 (v2b) redid the four deep buildings facade-first so the front, not the roof, is the main thing you see:

| Building | Score |
|---|---|
| Resting Ox | 8.5 |
| Elder's Hall | 8 |
| General Store | **8.5** (v2b; was 8) |
| Farmhouse | 8 |
| Bank | 8 |
| Pet Emporium | **8.5** (v2b; was 8.5, facade now leads) |
| Stonehaven Cottage | 8 |
| Stonehaven House | 8 |
| City Barracks | **8.5** (v2b; was 7.5) |
| Kai's Catch | **8.5** (v2b; was 8) |
| Harbourreach Tackle | 8 |

v2b technique (use it for any future deep building): a tall 2-storey front block about 4 tiles deep with a low-pitch or side-gabled roof, plus a false front or parapet that hides that roof from the 32° camera. The rear block is 1 storey with a low roof or flat terrace, so the tile-locked depth reads as "building behind", not "giant roof". Footprints, doors, floors and the map plan are unchanged, and the checker still passes.

Known limitations:
- In the tile-locked 32° view the building's top surfaces still fill the footprint depth. For the four v2b buildings this is now low rear roofs and terraces behind a tall facade. The other seven (Elder's Hall, Ox, Farmhouse, Bank, the two Stonehaven houses and the Tackle shop) still show a lot of roof; that's acceptable for their depth, but they could get the same treatment. The Barracks' rear terrace is a large flat plane (crates break it up).
- Roofs are flat-coloured shingle courses with no texture.
- Only the south faces carry detail, because side walls are edge-on at azimuth 0. There is no yaw 1–3 art: at other yaws the old procedural shell is used.
- There is no front layer, so the porch props are part of the body and y-sort with it.
- In the concepts, players stand at the doors using the castle pack's reference figure.
