# Castle interiors v2

Art and layout pack for the four Mythoscape castle keeps. This replaces the small corner-panel floors (Duskspire 18×12, White Rose 24×11, King's and Sky-Anchor 16×14) with full-screen multi-room planes. It does **not** replace the exteriors.

Flag: `USE_CASTLE_INTERIORS_V2`, default **off**. Old floors stay in use until the flag is on.

Footprint choice is **option B** from `CASTLE_INTERIOR_REDESIGN_PLANS.md`: interior width/height grow past the keep silhouette. Exterior sprites, gates, bailey, and the walk cycle stay as they are.

The White Rose courtyard fountain is **not** in this pack. That pathing fix lives in the plans doc and is a separate change.

## Score

**8.7 / 10** overall (checker in `json/checker_report.json`).

| Head | Score |
|---|---|
| Walkability (every floor BFS, rooms reached) | 9.0 |
| No path blockers (no cones, pillars, or mid-aisle props) | 9.2 |
| Room count and size vs the corner floors | 8.7 |
| Queen's white flowers and candles | 8.8 |
| Period detail (beds, halls, vaults, kitchens) | 8.5 |
| Furniture density (wall-hugging; centers left open on purpose) | 8.4 |

Every floor checker is PASS: reachable walkable tiles equal total walkable tiles.

## What changed inside

Collision is only `#` walls and `x` wall-hugging props (manhattan ≤ 2 from a wall, never in the room aisle). Walkable chars stay `. D E U V`. Doors, stairs, and exits keep a 2-tile straight pad, plus the side tiles of the first step. There are no pillars, cones, columns, or fountain basins.

Center carpets, dance floors, and the marble pools are decor (`blocks: false`). You walk over them.

Realm exit tiles are unchanged (the player still pops out on the same bailey tiles). Only the **interior arrive** tile moves, because the new floor is bigger. Exterior door world tiles do not move.

| Castle | v1 floor | v2 keep floors | Rooms | Arrive (flag on) |
|---|---|---|---|---|
| Duskspire | 18×12 | 40×23, 40×23, 40×23, 32×18 | 24 | (20,21) and (21,21) on `gothic_f1` |
| White Rose | 24×11 | 44×28 ×4 | 25 | (21,26) and (22,26) on `rose_f1` |
| King's keep | 16×14 | 48×32 ×4 | 24 keep + 4 barracks | (25,30) and (26,30) on `king_f1` |
| King's barracks | 7×16 | 20×28 | (included above) | (5,25) on `king_barracks_f1`; realm exit still (171,50) |
| Sky-Anchor | 16×14 | 40×26, 40×26, 40×26, 36×22 | 20 | (18,24) and (19,24) on `sky_f1` |

### Duskspire — 24 rooms

Extends the v1 Hall of Shadows, Great Hall, Lord's Chambers, and Spire.

- F1 Hall of Shadows: Black Chapel, Guard Room, Kitchen, Shadow Corridor, Pantry, Entrance Hall, Crypt Stair Vestibule, Stair Hall
- F2 Great Hall: Great Hall, Armoury, Lord's Solar, Solar Antechamber, Stair Hall
- F3: Lord's Bedchamber, Guest Chamber (decoy chest), Library, Upper Corridor, Questioning Room, Main Vault, Stair Hall
- F4 Spire: Bell Chamber, Battlement Watch, Roof Walk, Stair Head

### White Rose (queen) — 25 rooms

767 wall-mounted white flower drapes and 507 candles across the four floors (non-blocking, on the walls). Extra rooms are marked `fun: true`.

- F1 Rose Hall: Kitchen, Pantry & Still-room, Servants' Hall, Nursery, Gallery Walk, Linen Stillroom, Entrance Hall, Grand Stair
- F2: Great Hall of Roses, **Music Room**, Solar, Rose Antechamber, Grand Stair
- F3: Queen's Bedchamber, **Dressing Room**, Guest Suite (decoy chest), **Candle Chapel**, Long Corridor, Grand Stair, Rose Gallery, Petal Vault, **Petal Bath**
- F4: Roof Terrace, **Glass Conservatory**, Stair Head

### King's Castle — 28 rooms

- F1: Royal Kitchen, Buttery, Service Passage, **Feast Gallery**, Guard Post, Great Hall, Grand Stair, Vestibule
- F2: Throne Room (throne on the north wall, open approach), **Trophy Hall**, Council Chamber, Antechamber, Grand Stair
- F3: King's Bedchamber, Queen's Bedchamber, **Royal Bath**, **War Room** (map table on the north wall, not in the aisle), King's Study (decoy chest), Private Chapel, Royal Treasury, Grand Stair
- F4: Keep Battlements, **Crown Room**, Stair Head
- Barracks: Armoury, Dormitory, Mess Hall, **Captain's Room**

### Sky-Anchor — 20 rooms

- F1 Hall of Chains: Gearworks, Anchor Shrine, Sky Kitchen, Hall of Chains, Crystal Stair, Lift Landing
- F2 Hall of Winds: Hall of Winds, **Observatory**, Crystal Workshop, Wind Antechamber, Crystal Stair
- F3: Stormwarden's Bedchamber, **Meditation Chamber**, Guest Cell (decoy chest), Crystal Vault, Wind Gallery, Crystal Stair
- F4 Crystal Crown: Sky Terrace, Heart-Crystal Chamber, Stair Head

## Files

- `json/duskspire_interiors_v2.json`
- `json/white_rose_interiors_v2.json`
- `json/kings_interiors_v2.json` (keep floors + barracks)
- `json/sky_anchor_interiors_v2.json`
- `json/checker_report.json`
- `previews/<castle>_<plane>.png` — furnished top-down of every floor
- `previews/white_rose_candle_chapel_cutaway.png` — queen's candle chapel, white drapes and candles, clear aisle
- `previews/contact_sheet.png`
- `sprites/prop_four_poster_bed.png`
- `sprites/prop_dining_table.png`
- `sprites/prop_feast_table.png`
- `sprites/prop_candelabra.png`
- `sprites/prop_white_flower_drape.png`
- `sprites/prop_throne.png`
- `sprites/prop_hearth.png`
- `sprites/prop_chest.png`
- `tools/build_interiors_v2.py` — rebuilds JSON, previews, and sprites
- `CASTLE_INTERIORS_V2_CURSOR_PROMPT.md`

Rebuild:

```
python3 tools/build_interiors_v2.py
```

Grid legend: `#` wall, `.` floor, `D` door, `U` stairs up, `V` stairs down, `E` exit to the bailey, `x` blocking wall-hug prop. Rugs and wall drapes are in `decor[]` and do not block.
