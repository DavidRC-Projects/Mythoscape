"""
Coordinate conventions for the Panda3D building prototype.

World axes (Panda):
  +X = east
  +Y = up
  +Z = south  (matches game map: increasing tile Y goes south)

Tile mapping:
  map tile (tx, ty) → world point (tx, 0, ty)
  1 world unit = 1 map tile (TILE = 40 px in the Pygame client)

Camera yaw (same mental model as camera_yaw.py):
  0 = world north up on screen → camera south of target → sees FRONT (south)
  1 = world east  up → camera west  → sees LEFT  (west)
  2 = world south up → camera north → sees BACK  (north)
  3 = world west  up → camera east  → sees RIGHT (east)

Architecture face-cycle test (press `[`): FRONT → RIGHT → BACK → LEFT

Building faces (world-fixed, never billboard):
  FRONT = south (+Z) — door face
  BACK  = north (-Z)
  LEFT  = west  (-X)
  RIGHT = east  (+X)
  TOP   = up    (+Y)

Collision footprint is the wall shell AABB in XZ; roof overhang is visual-only
and is configured separately from collision_size.
"""

from __future__ import annotations

# Match pygame client tile size conceptually (documentation / scale checks).
TILE_PX = 40

# Farmhouse-scale shell from content.py cottage_se: 8×8 tiles (x0..x1-ish).
DEFAULT_FOOTPRINT_TILES = (8.0, 8.0)


def tile_to_world(tx: float, ty: float, y: float = 0.0) -> tuple[float, float, float]:
    """Map tile coords to Panda world (x, y_up, z)."""
    return (float(tx), float(y), float(ty))


def yaw_camera_offset(yaw: int, distance: float, height: float, bias: float = 0.35) -> tuple[float, float, float]:
    """
    Camera position relative to look-at target for discrete yaw 0..3.
    Building stays fixed; camera orbits.

    `bias` slides the camera slightly off the cardinal axis so two walls
    read in a 3/4 view (closer to the pygame building_volume projector).
    """
    yaw = int(yaw) % 4
    d = float(distance)
    h = float(height)
    b = float(bias) * d
    if yaw == 0:  # from south, look north — bias west so RIGHT (east) also reads
        return (-b, h, d)
    if yaw == 1:  # from west, look east — bias south so FRONT also reads
        return (-d, h, b)
    if yaw == 2:  # from north, look south — bias east so LEFT also reads
        return (b, h, -d)
    return (d, h, -b)  # from east, look west — bias north
