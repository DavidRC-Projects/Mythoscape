# Interior props — placement guide

All furniture **hugs walls or corners** (manhattan ≤ 2 from a `#` wall).
Centers of rooms stay open for walkways. **Never** place props on `D` doors,
`U`/`V` stairs, `E` exits, or their 2-tile approach pads.

The spiral stair is the exception: it is a **stair tile cluster** with a clear
step-on pad (green sector in the art), not a cone in the middle of a hall.
Prefer existing Stair Hall / Grand Stair / Crystal Stair rooms.

## Spiral staircase

| Castle | Stair art | Prefer rooms |
|---|---|---|
| Duskspire | `spiral_stair/spiral_stair_duskspire.png` | Stair Hall (all floors), Crypt Stair Vestibule |
| White Rose | `spiral_stair/spiral_stair_white_rose.png` | Grand Stair (f1–f4), Stair Head |
| King's | `spiral_stair/spiral_stair_king.png` | Grand Stair (keep), Stair Head |
| Sky-Anchor | `spiral_stair/spiral_stair_sky_anchor.png` | Crystal Stair, Lift Landing |

Base + layers live in `spiral_stair/`. See `spiral_stair/RECOLOR_NOTES.md`.

## New props by room (wall / corner only)

### Shared / multi-castle

| Prop | File | Rooms |
|---|---|---|
| Canopy bed | `props/prop_canopy_bed.png` | Lord's / Queen's / King's / Stormwarden's Bedchamber; Guest chambers (against head wall) |
| Sideboard | `props/prop_sideboard.png` | Great halls, solars, kitchens, antechambers — long wall |
| Banquet bench | `props/prop_banquet_bench.png` | Great Hall, Feast Gallery, Mess Hall — against long walls beside tables |
| Tapestry | `props/prop_tapestry.png` | Corridors, Throne Room, Great Hall, Trophy Hall — on wall tiles / decor layer OK |
| Weapon rack | `props/prop_weapon_rack.png` | Armoury, Guard Room, Barracks Armoury — wall |
| Bookshelf | `props/prop_bookshelf.png` | Library, Study, Solar, War Room, Council — wall |
| Bathtub | `props/prop_bathtub.png` | Petal Bath, Royal Bath, any bath room — corner or wall |
| Writing desk | `props/prop_writing_desk.png` | Study, Solar, Captain's Room, Observatory — wall |
| Chandelier | `props/prop_chandelier.png` | Great Hall, Throne, Candle Chapel, Hall of Winds — ceiling decor (non-blocking) |
| Suit of armour | `props/prop_suit_of_armour.png` | Trophy Hall, Armoury, Vestibule, Entrance Hall — corner |

### Castle-themed exclusives

| Prop | File | Castle / rooms |
|---|---|---|
| Rose trellis | `props/prop_rose_trellis.png` | **White Rose** — Rose Gallery, Glass Conservatory, Gallery Walk, Roof Terrace corners |
| Crystal altar | `props/prop_crystal_altar.png` | **Sky-Anchor** — Anchor Shrine, Heart-Crystal Chamber, Meditation Chamber (north wall) |
| Gothic pew | `props/prop_gothic_pew.png` | **Duskspire** — Black Chapel (wall-hug rows, aisle clear) |
| War map table | `props/prop_map_table.png` | **King's** — War Room (north wall, not aisle) |
| Harp | `props/prop_harp.png` | **White Rose** — Music Room (corner) |
| Chain winch | `props/prop_chain_winch.png` | **Sky-Anchor** — Gearworks, Hall of Chains (wall) |

## Density rules (match interiors_v2)

- Blocking props use furniture `hug: wall` and sit on `x` tiles.
- Chandeliers, tapestries, rose drapes may be `decor[]` with `blocks: false`.
- Leave room centers open; full-screen planes (40×23 … 48×32) need readable aisles.
- Spiral stair walk-pad must remain walkable `.` (or the stair `U`/`V` cluster).

## Existing sprites (interiors_v2) — still valid

four_poster_bed, hearth, feast_table, throne, chest, dining_table, candelabra, white_flower_drape.
This pack **adds** larger detailed alternatives; it does not delete the v2 set.
