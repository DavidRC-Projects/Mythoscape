# Cursor prompt: Fairy Village ground detail (tiles, edges, decals, no more dark blocks)

Repo `DavidRC-Projects/Mythoscape`. Work on your existing local branch **`fairy-village`** (cut from `castle-interiors-v2`). Game code lives under `game/assets/mmorpg/`.
Pack: `fairy_ground_pack.zip` (or `fairy_ground_pack_part*.zip`; every part unzips into the same `fairy_village/` folder). This is a **follow-up** to `FAIRY_VILLAGE_CURSOR_PROMPT.md`. It only changes how the village **ground** is drawn. Collision, NPCs and buildings are not touched.

The village is permanent, so **there is no feature flag**. Do not add one.

---

## Hard rules (these apply to every step)

1. **Step 1 is investigation only. Change no files. Report back, then STOP and wait for my go-ahead.**
2. Use small hooks. Never rewrite, reorganise or reformat existing code. Put the new drawing code in **one new module**, `client/fairy_ground.py`, and call it from at most three one-line hooks in `client.py`.
3. **Never edit** any of these:
   - `pose_walk`, or any walk posing in `rs_style.py`
   - `rs_humanoid.py`, `rs_humanoid_v2.py`
   - `tools/walk_proof.py`
   - `draw_humanoid`, `draw_humanoid_detailed`

   The walk cycle must stay byte-for-byte the same.
4. Leave every existing flag alone, and add none.
5. **Never merge, never push, never open a PR.**
6. Take before and after screenshots of each spot listed in Step 4. Save them in `game/assets/mmorpg/tools/screens/fairy_ground/`.
7. **Collision must not change.** Every WALL tile stays WALL. This work is drawing only. Decals never block movement and never take clicks.
8. If this prompt contradicts the code, trust the code and report the conflict.

---

## What the pack contains

| pack path | copy to (`game/assets/mmorpg/assets/fairy_village/...`) | what |
|---|---|---|
| `assets/tiles/{fairy_moss,petal_path}_v1..v5_{40,80,160}.png` | `tiles/` (replaces the old v1–v3 files with the same names) | seamless base tiles; all 5 variants of a set tile seamlessly next to each other |
| `assets/tiles/moonstone_paving_v1..v16_{40,80,160}.png` | `tiles/` (replaces the old v1–v3) | one seamless 4×4-tile paving texture cut into 16 tiles, so the stone joints run across tile borders (no tile grid) |
| `assets/tiles/edges/{path,paving}_grass_edge_<mask>_{40,80,160}.png` | `tiles/edges/` | 46 transparent overlays per family: grass spilling onto a path or paving tile |
| `assets/decals/<id>/<id>_{1x,2x,4x}.png` + `meta.json` | `decals/<id>/` | 9 ground decals + 3 contact skirts (transparent) |
| `json/ground_under.json`, `json/ground_decals.json`, `json/contact_decals.json` | `data/` | which ground to draw under collision WALL tiles, decal placements, contact skirts |
| `json/collision_trimmed/*.json` | `data/collision_trimmed/` | **proposal only.** Do not apply it unless I say so (see Step 1, item 6) |
| `previews/ground_village_mock.png`, `ground_before_after.png`, `ground_seam_tests.png` | `previews/` | what the result should look like |

The draw rules below are the same ones the pack's preview script (`src/ground/ground_mock.py`) uses, so the game should match `previews/ground_village_mock.png`.

---

## Step 1: Investigate, then STOP

Report file and line numbers for each item:

1. **`client/client.py` `draw_terrain_tile`** (~6838). Find the fairy-village branch that the first prompt added (the plaza already draws `moonstone_paving`, which proves it exists). Report:
   - where it is;
   - how it picks the variant and scales;
   - whether it returns **before** the wall-AO block at the end of the function. The AO block calls `_wall_neighbors` / `draw_tile_wall_ao`.
2. **Why the dark blocks appear.** In my screenshots there are hard black squares around the Moonstone Fountain and the Queen's Tree-Hall. Confirm the cause:
   - fairy collision tiles are `WALL`, so they fall through to `sprites.draw_wall(...)`;
   - zone `fairy_village` is not in the village / city list, so they draw the dark `(35,33,38)` tile;
   - neighbouring tiles may also get wall-AO strips.
3. **Why the path in front of the Tree-Hall looks like plain brown gravel.** Is the fairy branch drawing PATH tiles at all? Or does it fall back to `sprites.draw_path`?
4. **`draw_map`** (~5524). Find:
   - the terrain loop;
   - `emberdeep_v2_client.blit_backdrop(self)`;
   - `draw_walk_markers`, and where `draw_list` (entities) starts.

   The overlay hook goes between the terrain loop and the entities. Confirm `self.camera_yaw` is always 0 (line ~168), and confirm what `map_screen_rect(wx, wy, cam_x, cam_y)` returns.
5. **Tile cache.** Report:
   - how the existing fairy tile images are loaded and cached;
   - what happens on zoom change (`TILE_ZOOM_SIZES = (40, 32, 24, 16, 12)`, `set_zoom`);
   - where the art folder `assets/fairy_village/` is resolved.
6. **Collision overhang (report only).** The pack's `json/collision_trimmed/*.json` lists blocked tiles that stick out past the visible sprite, meaning less than 50 % of the tile is covered by the 1x sprite:
   - Tree-Hall: 10 tiles;
   - Inn: 3;
   - Apothecary: 9;
   - Lily Fountain: 2;
   - Moonstone Fountain: 0.

   Door and stand tiles stay as they are. The pack's `src/trim_check.py` shows that every stand tile, NPC and dungeon tile is still reachable with the trimmed lists. **Do not apply it.** Tell me whether `server/fairy_village.py` reads `blocked_tiles` straight from the collision JSON. If it does, applying the trim later would only mean swapping the JSON files.

Then **STOP** and report.

---

## Step 2: Ground drawing (after my go-ahead)

### 2a. Copy the art
Copy the files using the table above. Keep the old `tiles/` file names (`fairy_moss_v1_40.png` and so on). Moss and path v4–v5 are new; paving v4–v16 are new.

### 2b. `client/fairy_ground.py` (new module)
It owns everything below. It loads the three JSON files once, lazily, from `assets/fairy_village/data/`.

**Variant per tile.** Use this deterministic hash, and make sure it is the same function everywhere:
```python
def fairy_variant(x, y):
    h = (x * 73856093) ^ (y * 19349663)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) % 5 + 1          # 1..5

def paving_variant(x, y):            # moonstone_paving only: position inside the 4x4 macro texture
    return (y % 4) * 4 + (x % 4) + 1 # 1..16
```
- `fairy_moss` and `petal_path` use `fairy_variant(x, y)`.
- `moonstone_paving` uses `paving_variant(x, y)`. Do not hash the paving: its 16 tiles only fit together in this order. Use world tile coordinates, never screen coordinates.

**Ground kind of a tile:**
- `GRASS` → `fairy_moss`
- `PATH` → `petal_path`
- `STONE` → `moonstone_paving`
- `WALL` and `"x,y"` in `ground_under.json["tiles"]` → the ground named there:
  - fountain footprints sit on `STONE`;
  - building footprints sit on `GRASS`.

  The tile stays WALL for collision. Only the drawing changes.

**Edge overlay (autotile), only inside `ZONES["fairy_village"]`.** Applies to a tile whose kind is `PATH` or `STONE` and whose real id is not `WALL`:

```text
bit   N=1  NE=2  E=4  SE=8  S=16  SW=32  W=64  NW=128
```

1. A bit is set when that neighbour is **grass-like**. That means:
   - its tile id is `GRASS` (the same counts outside the zone); or
   - it is a `WALL` whose `ground_under` is `GRASS`.

   `PATH` next to `STONE` gets no overlay. `TREE` ids count as grass if any exist.
2. Reduce the diagonals. A diagonal bit is kept only when **neither** of its two orthogonal neighbours is set:
   - NE needs N and E clear;
   - SE needs S and E clear;
   - SW needs S and W clear;
   - NW needs N and W clear.

   This leaves 47 masks. Mask 0 means no overlay.
3. Blit `tiles/edges/path_grass_edge_{mask:03d}_{px}.png` (for PATH) or `paving_grass_edge_{mask:03d}_{px}.png` (for STONE) on top of the base tile.

What the masks look like:
- `001` = grass on N (a straight edge);
- `005` = N+E (the path's rounded outer corner);
- `002` = only NE (a small inner-corner nub);
- `085` = N+E+S+W (an isolated path tile).

The overlays' opaque border pixels are copied from `fairy_moss_v1`. All moss variants share that border, so the overlay always meets the grass tile next door without a seam.

**`draw_tile(client, rect, tile_id, wx, wy)`**:
- returns `False` outside the zone, or for tile ids it doesn't own;
- otherwise draws the base tile and then the edge overlay, and returns `True`.

**`draw_overlays(client, cam_x, cam_y, vis_w, vis_h)`** draws, in this order:
1. **contact skirts** from `contact_decals.json`:
   - Tree-Hall roots and moss skirt;
   - Moonstone and Lily fountain damp stone rim and moss ring.

   Each one is anchored at its footprint's NW tile: `blit at (rect.x - origin_px.x * s, rect.y - origin_px.y * s)`, where `rect = client.map_screen_rect(x0, y0, cam_x, cam_y)` and `s = TILE / 40` when using the 1x art.
2. **ground decals** from `ground_decals.json["decals"]` (`id`, `x`, `y` = the NW footprint tile). Use the same blit rule with `assets/decals/<id>/meta.json` → `origin_px`.

Skip anything whose canvas lies fully off screen. Decals are visual only: they have no collision, no click targets and no tooltips.

### 2c. Hooks in `client.py` (one line each)
1. **Top of the non-dungeon path in `draw_terrain_tile`**, before the per-id branches:
   ```python
   if not self.dungeon and fairy_ground.draw_tile(self, rect, tile_id, wx, wy): return
   ```
   - This must replace or short-circuit the earlier fairy branch. Keep that branch if removing it would mean rewriting code; it is fine for it to become unreachable.
   - Because it returns early, fairy tiles skip the wall-AO block. That is intended, because AO next to collision tiles also makes dark strips.
   - If that is not enough, make `_wall_neighbors` ignore WALL tiles that are in `ground_under`. Do this only with a one-line guard.
2. **In `draw_map`**, right after the terrain loop and `blit_backdrop`, before walk markers and `draw_list`:
   ```python
   fairy_ground.draw_overlays(self, cam_x, cam_y, vis_w, vis_h)
   ```
   Building and fountain sprites are drawn later, in the y-sorted entity pass, so they sit on top of their skirts.
3. The import line.

### 2d. Cache-friendly scaling
- Key the cache by `(name, TILE)`.
- Pick the smallest source that is at least `TILE`: `40` for `TILE <= 40`, `80` for `TILE <= 80`, otherwise `160`.
- Scale with `pygame.transform.smoothscale` once, and keep the surface (`convert()` for tiles, `convert_alpha()` for edges and decals).
- On `set_zoom`, the cache simply fills for the new `TILE`. You may drop entries for other sizes if memory matters.
- Total per zoom level: 26 base tiles (5 moss + 5 path + 16 paving) + up to 92 edges + 12 decals.
- Never scale inside the per-tile loop without the cache.
- Decals use the `1x` art at `TILE <= 40` and the `2x` art above that, with factor `TILE / tile_px`.

---

## Step 3: Checks (paste the output)

Run these from the pack folder, or copy the scripts into `tools/`:
- `python3 src/decal_check.py` must print `OVERALL PASS`. It confirms that no decal lies on:
  - a collision tile;
  - a door, interaction or stand tile;
  - an NPC tile;
  - a fountain;
  - a dungeon mouth, enter, exit or return tile;
  - a moved NPC or interactable tile;
  - anything other than GRASS in the zone.
- `python3 src/layout.py` must still print `OVERALL PASS`, which means collision is unchanged.
- `git diff --stat` must show:
  - no protected file from Hard rule 3;
  - no server change;
  - only `client/fairy_ground.py` (new), three hook lines in `client/client.py`, and the copied art and data.

---

## Step 4: Verify in game and take screenshots (before and after)

Save to `game/assets/mmorpg/tools/screens/fairy_ground/`:
1. **The Moonstone Fountain plaza** (fountain plus Elowen). There must be no dark squares around the fountain: paving goes right up to the basin, with a damp rim and moss ring at its base.
2. **The Queen's Tree-Hall and the South Walk.** There must be no dark squares: moss and roots around the trunk, and the walk in front drawn as the new `petal_path`, not plain brown gravel.
3. **The Lily Court** (Lily Fountain plus Pip).
4. **The Moonpetal Inn front and Petal Avenue**, showing the soft grass edges on the path and the lanterns.
5. **The Apothecary and its door path** (a 1-tile path with grass on both sides, which uses edge masks `068` / `064` / `004`).
6. **The village border with the normal grass at y = 56 and x = 40**, so I can judge the zone seam.
7. **All of the above at the 40 % zoom (`TILE = 16`)**, to show the scaling cache works and nothing shimmers.

Then confirm:
- you still cannot walk through buildings or fountains;
- the doors and fountains still respond from their stand tiles;
- the player walks over decals freely;
- the walk cycle is unchanged.

Then **stop**. Do not merge or push. Report:
- the files you changed;
- the check output;
- the screenshots;
- any deviation from this prompt.
