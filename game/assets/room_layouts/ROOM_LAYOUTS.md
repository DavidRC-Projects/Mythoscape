# Castle room layouts — unique props, feet in front of the walls

Blender **4.2.23 LTS** actually rendered these (EEVEE Next, orthographic 3/4, flat-shaded low poly). Not the old PIL stamp set. Script: `blender/build_room_layouts.py`.

17 new room props + 4 vault centerpieces. None of these are the previous packs (`four_poster_bed`, `hearth`, `feast_table`, `throne`, `chest`, `dining_table`, `candelabra`, `white_flower_drape`, `canopy_bed`, `sideboard`, `banquet_bench`, `harp`, `crystal_altar`, `weapon_rack`, `bathtub`, `suit_of_armour`, `chain_winch`, `tapestry`, `map_table`, `chandelier`, `rose_trellis`, `bookshelf`, `gothic_pew`, `writing_desk`).

Foot pixel for every sprite is in `json/prop_origins.json` (`origin_px`). That pixel is the **front feet**, the lowest opaque row. It is not the image centre.

## Draw-order rule (never paint a prop behind a wall)

Reviewed read-only in `DavidRC-Projects/Mythoscape`, `game/assets/mmorpg/client/client.py` (no commits).

The world draw collects `(sort_y, layer, draw_fn)` and sorts **ascending** (`client.py` 5132–5134, sort at 5733). A **larger** `sort_y` paints later, so it sits in front.

| What | sort_y | layer | Where |
|---|---|---|---|
| Flat `#` wall tile | terrain pass, **before** the list | — | `draw_terrain_tile` 6294–6305. These cannot cover a prop. |
| Tall wall face (dungeon cliff / any y-sorted wall) | `wall_cy + TILE // 2` | **1** | `_queue_volcano_cliffs` 6143–6195. Only walls with open ground toward camera-south. |
| Blocking furniture | `cy + TILE // 4` today | **2** | 5402–5406. `cy` is the **tile centre** (5291: `sy * TILE + TILE // 2`). |
| Rug / fountain | `cy - TILE // 2` | **0** | 5403–5404. Under feet. |
| Sprite blit | `origin_px` + `_BASE_PX` | — | `prop_sprites.py` `draw_prop` 108–164. The origin pixel, not the bitmap centre, lands on the anchor. |

**Why props vanish into walls.** A prop anchored on the wall tile, or on a tile camera-north of the wall face, gets a smaller `sort_y` than that face (`wall_cy + TILE/2` beats `prop_cy + TILE/4`). The wall is drawn on top. The same thing happens if `origin_px` is the sprite centre: half the bitmap hangs south of the anchor, into the wall's screen space, and the wall overwrites it.

**Rule. Do all four.**

1. **Anchor = front feet**, on a floor tile **inside** the room, at least one tile camera-south of the wall the prop stands against. Never on `#`, `D`, `U`/`V`, `E`, or their 2-tile approach pads.
2. **Sprite origin is the feet** (`origin_px` in `json/prop_origins.json`). Blit so that pixel sits on the **south edge** of the anchor tile (`cy + TILE/2`), not the tile centre. At the old 40px tile that is `_BASE_PX = 20`, scaled by `tile/40`. The bitmap must grow **up** the screen from the feet.
3. **sort_y must be strictly greater than the wall face it stands in front of.** Suggested:
   ```
   foot_sy = sy * TILE + TILE          # south edge of the anchor tile
   sort_y = foot_sy
   sort_y = max(sort_y, wall_face_sort_y + 1)
   layer = 2                           # wall faces are layer 1, so a tie still paints the prop in front
   ```
   Never assign a prop a z / sort behind the wall. Do not use a negative sort to "tuck it into" the wall.
4. **Wall art** (`prop_portrait`, `prop_heater_shield`) is `blocks: false`, but it still sorts **with that wall, plus 1**, layer 2. Its origin is the bottom of the frame, lifted off the floor. A rug stays layer 0 and non-blocking; it is a floor decal, not a thing behind the wall.

Blocking props use furniture `hug: wall` (or `pair` for the two exceptions below) and sit on `x` tiles. `decor[]` never blocks.

## Do not copy-paste

`interiors_v2` floors stamp the same kind many times (gothic_f1: 8 shelves, 8 sacks, 8 barrels; king_f2: 20 banners, 13 armour stands; king_f3: 16 chairs, 18 candles). That is the repeat David called out.

**The same prop file appears at most once per room.** The only exception is a **pair**: `prop_dining_chair` (two, facing the table) and `prop_prayer_kneeler` (two, with a clear aisle between). Candles, the cross, and the book are **part of** `prop_chapel_altar`, not extra candle props. Coin piles, the lock, and the single chest are **part of** the vault centerpiece, not a row of chests.

## Aisles

OSRS POH / manor, not a furniture warehouse.

- Bed, press, altar, vault door, racks: **back against a wall**. Front feet on the first interior floor tile.
- A table may sit in the **centre only if 2 clear tiles** remain on every side, including the chairs. Otherwise shove it to a long wall.
- Rugs are non-blocking and must not cover a door, stair, or exit pad.
- Guard space in a vault is an **empty** 2×2 floor (the salmon tiles in the vault previews). No prop on it.
- The blue figure in the layout PNGs is a 1.8 m scale marker. It is **not** a prop. The bed and the feast table in the previews are scene-only stand-ins for the **existing** `four_poster` / `canopy_bed` and `feast_table` / `dining_table`. Do not add new files for them.

## Props

| File | Blocks | Hug | Use |
|---|---|---|---|
| `props/prop_linen_press.png` | yes | wall | Bedchamber / dressing / linen stillroom. One wardrobe, not seven. |
| `props/prop_cheval_mirror.png` | yes | wall | Dressing room, one bedchamber. |
| `props/prop_washstand.png` | yes | wall | Basin, ewer, towel. Not the bathtub. |
| `props/prop_cradle.png` | yes | wall or open corner | **White Rose nursery only** (`rose_f1`). Not every bedroom. |
| `props/prop_dining_chair.png` | yes | **pair** | Exactly two, facing one table. Not 15 chairs. |
| `props/prop_serving_cart.png` | yes | wall | One per hall. |
| `props/prop_wine_rack.png` | yes | wall | Buttery, pantry, or one hall wall. |
| `props/prop_chapel_altar.png` | yes | wall, north | One per chapel. Replaces a row of pews as the focal object. |
| `props/prop_lectern.png` | yes | wall | One, beside the altar or in a library. |
| `props/prop_prayer_kneeler.png` | yes | **pair** | Two, aisle between them. Not a pew grid. |
| `props/prop_arming_dummy.png` | yes | wall | Armoury / guard room. Once. |
| `props/prop_spinning_wheel.png` | yes | wall | Solar or linen stillroom. Once. No room preview; the sprite is the layout. |
| `props/prop_portrait.png` | no | wall decor | One painting per room. Sort in front of that wall. |
| `props/prop_heater_shield.png` | no | wall decor | Armoury, trophy hall, guard room. Not a second weapon rack. |
| `props/prop_cauldron.png` | yes | wall / hearth corner | Kitchen or hall corner. Once. |
| `props/prop_relic_rack.png` | yes | wall | Vault side wall. Ingots, cup, crown, book, gem. Once. |
| `props/prop_spear_stand.png` | yes | wall | Armoury. Tub, spears, leaning round shield. Not `weapon_rack`. |

## Room plans

Tile numbers below match the preview renders (1 tile = 1 m). North is the back wall. Front feet stay on interior floor. Centre aisle stays at least 2 tiles wide.

### Bedroom — `layouts/layout_bedroom.png`

Lord's / Queen's / King's / Stormwarden's bedchamber. One of each:

- Existing four-poster, head against the north wall (scene stand-in in the preview).
- `prop_portrait` on the north wall above the head. Decor, non-blocking.
- `prop_cheval_mirror` against the north wall, to the side of the bed, not overlapping the posts.
- `prop_linen_press` against the west wall.
- `prop_washstand` against the west wall, south of the press, with a walk gap.
- `prop_cradle` only if this room **is** the nursery. The preview shows it once, in the open west floor, clear of the aisle. Do not also drop it in the guest chamber.
- One rug under the bed foot, non-blocking.
- Do not add a second bed, a second chair, or a row of candles.

### Dining — `layouts/layout_dining.png`

Great Hall, Feast Gallery, Mess Hall:

- One existing feast table in the centre. Chairs included, the footprint still leaves **2 tiles** to the walls and to the door.
- `prop_dining_chair` **twice** (a pair), one each long side, facing the table. Stop there.
- `prop_wine_rack` on the west wall.
- `prop_serving_cart` on the west wall, south of the rack, gap between them.
- `prop_cauldron` in the north-west corner (hearth side), not in the aisle.
- `prop_portrait` on the north wall.
- One rug under the table only.
- No second table, no bench row, no banner every tile.

### Chapel — `layouts/layout_chapel.png`

Black Chapel, Candle Chapel, Private Chapel:

- `prop_chapel_altar` centred on the north wall.
- `prop_lectern` on the north wall, west of the altar, not blocking the centre approach.
- `prop_prayer_kneeler` **twice**, left and right of a 2-tile aisle, both north of the door jambs so the south wall cannot cover them.
- `prop_portrait` on the west wall (decor).
- One narrow runner up the aisle, non-blocking, stopping short of the kneelers.
- Do not instance `gothic_pew` six times. If a pew is kept at all, one pair maximum, and then **drop** the kneelers so the room does not have both.

### Armoury — `layouts/layout_armoury.png`

Duskspire armoury, King's barracks armoury, guard room:

- `prop_spear_stand` on the west wall.
- `prop_arming_dummy` against the north wall.
- `prop_heater_shield` on the north wall, east of the dummy (decor, in front of the wall).
- One small rug, non-blocking.
- Do not add seven weapon racks or four armour stands. The old `weapon_rack` / `suit_of_armour` may remain **once** in a different room (trophy hall), not stacked here on top of these.

### Vaults

Heavy door, lock, coin piles, and **one** chest are one sprite. A relic rack is the only other blocking prop. The salmon 2×2 is empty guard space, off the aisle, `blocks: false`.

| Castle | Room | Centerpiece | Preview |
|---|---|---|---|
| Duskspire | `gothic_f3` Main Vault | `vaults/vault_gothic_iron.png` — dark stone jambs, iron door, rivets, bar, ring, lock, grilled window, gold piles, one iron-bound chest | `layouts/layout_vault_gothic.png` |
| White Rose | `rose_f3` Petal Vault | `vaults/vault_rose_marble.png` — pale marble, rose on the door, silver piles, one light chest | `layouts/layout_vault_white_rose.png` |
| King's | `king_f3` Royal Treasury | `vaults/vault_king_gold.png` — blue-grey stone, gold door, blue side banners, crown on the head, gold piles | `layouts/layout_vault_king.png` |
| Sky-Anchor | `sky_f3` Crystal Vault | `vaults/vault_sky_crystal.png` — cyan crystal door, shards in the frame, pale crystal piles, one crystal chest | `layouts/layout_vault_sky.png` |

Shared vault dressing, once: `prop_relic_rack` on the west wall. Recolour is optional; do not place a second rack. Nothing on the guard mat. The approach from the door to the vault door stays 2 tiles clear (the piles belong to the centerpiece and sit at the end of that approach, against the door, not as scatter).

### Where the spinning wheel goes

`prop_spinning_wheel.png` — White Rose solar (`rose_f2`) or the linen stillroom (`rose_f1`), one, against a side wall. Not in the bedroom preview, so the bedroom does not collect every domestic prop.

## Ideas used (not copied assets)

OSRS POH and a manor plan, not Jagex art: bed's head to the wall, washstand and press on the side walls, one focal altar, kneelers as a pair with an aisle (not a pew grid), vault as a door you walk up to with the hoard at its foot and a guard standing off to the side, centre kept walkable. Same read as the OSRS note already in the repo (`OSRS_DESIGN_REFERENCE.md`): few props, placed on purpose, hard-shaded, feet on the tile.
