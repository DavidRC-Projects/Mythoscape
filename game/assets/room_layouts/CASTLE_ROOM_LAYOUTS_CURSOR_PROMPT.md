# Cursor prompt: Castle room layouts (unique props, in front of the walls)

You are working in **Mythoscape** (`game/assets/mmorpg/`). The asset pack is `room_layouts_pack.zip`. Unzip it beside `interiors_v2` and `interior_props`. It adds **17 room props** and **4 vault centerpieces**, plus isometric layout previews. It does **not** replace exteriors, the walk cycle, or the old prop files.

Wire these behind the existing flag **`USE_CASTLE_INTERIORS_V2`**. When the flag is off, behaviour must stay byte-for-byte as today.

Read `ROOM_LAYOUTS.md` and `json/prop_origins.json` before editing. The PNGs were rendered in Blender 4.2 (flat-shaded, orthographic). `origin_px` is the **front-foot** pixel.

## David's rules (apply to every step)

1. **Step 1 is investigation only. Change nothing, report back, then STOP.**
2. Prefer the existing flag `USE_CASTLE_INTERIORS_V2` in `server/feature_flags.py` (default `"0"`). Flag off = no new sprites and no sort change.
3. Small hooks only. Don't rewrite exteriors, footprints, gates, baileys, or courtyard art.
4. **Do not change the walk cycle.**
5. **Y-sort props in front of walls.** Never give a prop a sort key behind a wall face. Feet on an interior floor tile. Sprite origin at the feet. See the rule below.
6. **Do not repeat the same prop more than once per room** unless it is a **pair** (`prop_dining_chair`, `prop_prayer_kneeler`). A vault centerpiece already contains its own coins, lock, and one chest — do not stamp extra chests beside it.
7. One phase at a time. Screenshots flag off vs on. Then **STOP and wait for approval**.
8. **Never merge, never push, never open a PR.** Local branch only (e.g. `castle-room-layouts`).

## Step 1: investigation only (then STOP)

Confirm or correct each point, with file:line references. **Don't edit anything.**

- Where `USE_CASTLE_INTERIORS_V2` loads floor JSON / furniture / decor for `gothic_*`, `rose_*`, `king_*`, `sky_*`.
- Where furniture kinds map to sprites (`client.py` `draw_furniture` / `_draw_pack_prop`, `prop_sprites.draw_prop`). Say whether a new kind string can point at `room_layouts/props/*.png` without rewriting the plane builder.
- Draw order, from the current client (verify the lines still match):
  - `client.py` ~5132 builds `draw_list` of `(sort_y, layer, fn)`; ~5733 sorts ascending, so a **larger** sort_y paints **in front**.
  - Tall wall faces queue at `cy + TILE // 2`, **layer 1** (`_queue_volcano_cliffs`, ~6195).
  - Blocking furniture queues at `cy + TILE // 4`, **layer 2** (~5406). `cy` is the tile **centre** (~5291).
  - Rugs / fountains queue at `cy - TILE // 2`, layer 0 (~5404).
  - Flat `#` walls are drawn in the terrain pass **before** the list (~6294), so they are not the thing covering props. Tall y-sorted wall faces are.
  - `prop_sprites.draw_prop` (~108–164) blits with `origin_px`. If that pixel is the bitmap centre, the sprite hangs south into the wall and the wall overwrites it.
- Confirm a prop whose anchor is camera-north of a wall face gets a **smaller** sort_y than that face, which is the "disappears into the wall" bug.
- Confirm the walk-cycle path is not on this hook.
- Confirm collision stays `#` + blocking furniture `x` only. Portrait, heater shield, rugs, and the vault guard mat never block.
- Deliver a short plan: hook points, estimated lines, the sort change (feet at south edge of the anchor tile, `sort_y = max(foot_sy, wall_face_sort + 1)`, layer 2), and the list of new files to register. **STOP.**

Do not start the wiring phase during Step 1.

## Draw-order rule (what the later phase must implement)

Never z a prop behind a wall.

- Place the anchor on a floor tile **inside** the room, one tile camera-south of the wall it stands against. Not on the wall tile. Not on `D` / `U` / `V` / `E` or the 2-tile pad in front of them.
- `origin_px` from `json/prop_origins.json` is the front feet. Land that pixel on the **south edge** of the anchor tile (`cy + TILE/2`). At a 40px tile, `_BASE_PX = 20`.
- ```
  foot_sy = sy * TILE + TILE
  sort_y = max(foot_sy, wall_face_sort_y + 1)
  layer = 2
  ```
  Wall faces stay layer 1. A tie paints the prop in front.
- Wall art (`prop_portrait`, `prop_heater_shield`): `blocks: false`, but the same in-front sort, origin at the bottom of the frame.
- Rugs: layer 0, non-blocking, and still not given a sort behind a wall face.
- Centre a table only when **2 tiles of aisle** remain on every side after the chairs. Otherwise put it on a wall.
- Same sprite **once** per room. Pair exception: two `prop_dining_chair`, or two `prop_prayer_kneeler`, with a gap. Nothing else is a pair.

## What to place (after Step 1 is approved)

Follow `ROOM_LAYOUTS.md`. Previews: `layouts/layout_bedroom.png`, `layout_dining.png`, `layout_chapel.png`, `layout_armoury.png`, `layout_vault_gothic.png`, `layout_vault_white_rose.png`, `layout_vault_king.png`, `layout_vault_sky.png`.

Vault centerpieces, one each, back against the north wall of that vault:

- Duskspire Main Vault (`gothic_f3`): `vaults/vault_gothic_iron.png`
- White Rose Petal Vault (`rose_f3`): `vaults/vault_rose_marble.png`
- King's Royal Treasury (`king_f3`): `vaults/vault_king_gold.png`
- Sky-Anchor Crystal Vault (`sky_f3`): `vaults/vault_sky_crystal.png`

Plus one `prop_relic_rack` on a side wall, and an empty 2×2 guard mat. Do not row chests, shelves, sacks, barrels, banners, or armour stands. The blue figure, the preview bed, and the preview feast table are **not** new sprites (bed and table stay the existing ones).

`prop_cradle` is the nursery (`rose_f1`) only. `prop_spinning_wheel` is one solar or stillroom, once.

Do not move exterior door world tiles. Do not retarget arrive tiles in this pack. Do not build `USE_CASTLE_OWNERS` / `GUARDS` / `VAULTS` gameplay. This pack is sprites, placement, and the y-sort fix only.

## Phase A (only after Step 1 is approved)

- Register the new PNGs behind the flag.
- Apply the foot origin and the in-front sort.
- Replace repeated furniture in one sample room per type (one bedroom, one dining hall, one chapel, one vault) with the lists in `ROOM_LAYOUTS.md`. Leave every other room alone until the next approval.
- Checker still passes: every room reachable, no prop on a transition pad, aisles 2 tiles where the plan says so.
- Screenshots, flag off vs on, same tile: that bedroom, that hall, that chapel, that vault. Props must read **in front of** the wall, and the room must not show the same sprite three times.
- **STOP.**

Do not start Phase A during Step 1.
