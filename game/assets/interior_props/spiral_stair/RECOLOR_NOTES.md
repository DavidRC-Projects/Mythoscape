# Spiral stair recolor notes

Base design: `spiral_stair_base.png` (512×512) — grey medieval stone spiral with central newel,
14 treads, outer curb, and a **green walk-pad** sector at the foot (step-on tile cluster).

## Per-castle light recolors (already rendered)

| Castle | File | Palette |
|---|---|---|
| Duskspire (gothic) | `spiral_stair_duskspire.png` | Near-black stone, maroon accents, iron rail spikes on outer lip |
| White Rose | `spiral_stair_white_rose.png` | Pale limestone, cream mortar, white rose finial on newel |
| King's | `spiral_stair_king.png` | Blue-grey ashlar, gold studs every 3rd tread, gold finial |
| Sky-Anchor | `spiral_stair_sky_anchor.png` | Teal stone, cyan crystal shard on newel, crystal studs |

## Layers (for compositor / multi-frame)

1. `spiral_stair_layer_00_pad.png` — walk pad only (must stay clear; player steps here)
2. `spiral_stair_layer_01_lower_steps.png`
3. `spiral_stair_layer_02_mid_steps.png`
4. `spiral_stair_layer_03_upper_steps.png`
5. `spiral_stair_layer_04_column_curb.png`

Stack bottom→top for the full stair. Pad sits at the entrance wedge; do **not** place furniture on the pad or on U/V stair tiles.

## Placement

- Stair is a **tile cluster**, not a mid-hall cone.
- Prefer existing Stair Hall / Grand Stair / Crystal Stair corners already marked `U`/`V`.
- Keep a 2-tile straight approach pad free of blocking props.
