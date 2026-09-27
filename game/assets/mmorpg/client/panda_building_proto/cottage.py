"""
Original low-poly medieval cottage for the Panda3D prototype.

OSRS-inspired chunky readable geometry — original design, no external assets.
Door is carved into the SOUTH (FRONT) wall; not a separate box pasted in front.

Collision footprint (walls) is independent of roof overhang.
Geometry is built once via BoxMaker / mesh helpers (UHStatic).
"""

from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import NodePath

from .geom_util import BoxMaker, attach_flat_shadow, make_colored_mesh, quad


@dataclass
class CottageConfig:
    """Configurable dimensions in world units (1 unit = 1 tile)."""

    collision_x: float = 8.0
    collision_z: float = 8.0
    wall_height: float = 2.35
    foundation_h: float = 0.22

    roof_overhang: float = 0.55
    roof_rise: float = 2.1
    ridge_along_x: bool = True

    door_width: float = 1.15
    door_height: float = 1.85
    door_recess: float = 0.35
    window_size: float = 0.75
    window_recess: float = 0.22

    beam_thick: float = 0.18
    chimney: bool = True


STONE = (158, 160, 165)
STONE_SIDE = (128, 130, 136)
STONE_DARK = (100, 102, 108)
FOUNDATION = (92, 94, 100)
TIMBER = (78, 52, 34)
TIMBER_DARK = (56, 36, 24)
ROOF = (128, 84, 52)
ROOF_DARK = (96, 60, 36)
DOOR = (62, 40, 26)
WINDOW_GLASS = (155, 180, 190)
WINDOW_FRAME = (48, 34, 24)
CHIMNEY = (138, 140, 146)


def _box(name, min_xyz, max_xyz, color, parent, *, shininess=8.0):
    """Maker-style one-shot box parented under parent."""
    np = (
        BoxMaker(name)
        .set_extents(min_xyz, max_xyz)
        .set_color(color)
        .set_shininess(shininess)
        .generate()
    )
    np.reparentTo(parent)
    return np


def build_cottage(parent: NodePath, cfg: CottageConfig | None = None, name: str = "cottage") -> NodePath:
    """Build cottage geometry once; reparent under parent. Returns root NodePath."""
    cfg = cfg or CottageConfig()
    root = parent.attachNewNode(name)

    hx = cfg.collision_x * 0.5
    hz = cfg.collision_z * 0.5
    y0 = 0.0
    yf = cfg.foundation_h
    yw = yf + cfg.wall_height

    _box("foundation", (-hx, y0, -hz), (hx, yf, hz), FOUNDATION, root, shininess=4.0)
    _build_walls(root, cfg, hx, hz, yf, yw)
    _build_timber(root, cfg, hx, hz, yf, yw)
    _build_door(root, cfg, hx, hz, yf, yw)
    _build_windows(root, cfg, hx, hz, yf, yw)
    _build_roof(root, cfg, hx, hz, yw)
    if cfg.chimney:
        _build_chimney(root, cfg, hx, hz, yw)

    attach_flat_shadow(
        root,
        cx=0.0,
        cz=0.05,
        sx=cfg.collision_x + cfg.roof_overhang * 1.2,
        sz=cfg.collision_z + cfg.roof_overhang * 1.2,
        y=0.015,
    )

    root.setPythonTag("collision_size", (cfg.collision_x, cfg.collision_z))
    root.setPythonTag("roof_overhang", cfg.roof_overhang)
    return root


def _build_walls(root, cfg, hx, hz, yf, yw):
    t = 0.28
    door_w = cfg.door_width
    gap_l = -door_w * 0.5
    gap_r = door_w * 0.5
    _box("wall_s_l", (-hx, yf, hz - t), (gap_l, yw, hz), STONE, root)
    _box("wall_s_r", (gap_r, yf, hz - t), (hx, yw, hz), STONE, root)
    _box("wall_s_lintel", (gap_l, yf + cfg.door_height, hz - t), (gap_r, yw, hz), STONE, root)
    _box("wall_n", (-hx, yf, -hz), (hx, yw, -hz + t), STONE_SIDE, root)
    _box("wall_w", (-hx, yf, -hz), (-hx + t, yw, hz), STONE_SIDE, root)
    _box("wall_e", (hx - t, yf, -hz), (hx, yw, hz), STONE_DARK, root)


def _build_timber(root, cfg, hx, hz, yf, yw):
    b = cfg.beam_thick
    corners = [(-hx, hz), (hx, hz), (hx, -hz), (-hx, -hz)]
    for i, (cx, cz) in enumerate(corners):
        _box(
            f"post_{i}",
            (cx - b * 0.5, yf, cz - b * 0.5),
            (cx + b * 0.5, yw + 0.05, cz + b * 0.5),
            TIMBER,
            root,
            shininess=12.0,
        )
    for z, tag in ((hz, "s"), (-hz, "n")):
        _box(
            f"beam_h_{tag}",
            (-hx + b, yw - b * 1.2, z - b * 0.45),
            (hx - b, yw - b * 0.2, z + b * 0.45),
            TIMBER_DARK,
            root,
            shininess=12.0,
        )
    _box(
        "post_w_mid",
        (-hx - b * 0.15, yf, -b * 0.5),
        (-hx + b * 0.85, yw, b * 0.5),
        TIMBER,
        root,
        shininess=12.0,
    )


def _build_door(root, cfg, hx, hz, yf, yw):
    dw = cfg.door_width
    dh = cfg.door_height
    rec = cfg.door_recess
    z_outer = hz
    z_inner = hz - rec

    _box("door_jamb_l", (-dw * 0.5, yf, z_inner), (-dw * 0.5 + 0.08, yf + dh, z_outer), STONE_DARK, root)
    _box("door_jamb_r", (dw * 0.5 - 0.08, yf, z_inner), (dw * 0.5, yf + dh, z_outer), STONE_DARK, root)
    _box("door_head", (-dw * 0.5, yf + dh - 0.08, z_inner), (dw * 0.5, yf + dh, z_outer), STONE_DARK, root)
    _box(
        "door_leaf",
        (-dw * 0.5 + 0.06, yf + 0.02, z_inner),
        (dw * 0.5 - 0.06, yf + dh - 0.1, z_inner + 0.06),
        DOOR,
        root,
        shininess=6.0,
    )
    _box(
        "door_handle",
        (dw * 0.22, yf + dh * 0.48, z_inner + 0.06),
        (dw * 0.28, yf + dh * 0.55, z_inner + 0.12),
        (25, 25, 28),
        root,
        shininess=20.0,
    )


def _build_windows(root, cfg, hx, hz, yf, yw):
    ws = cfg.window_size
    rec = cfg.window_recess
    cy = yf + 1.15

    def window_at(cx, cz, facing: str, tag: str):
        half = ws * 0.5
        if facing == "s":
            z0, z1 = cz - rec, cz
            _box(f"win_frame_{tag}", (cx - half, cy - half, z0), (cx + half, cy + half, z1), WINDOW_FRAME, root)
            _box(
                f"win_glass_{tag}",
                (cx - half + 0.06, cy - half + 0.06, z0 + 0.02),
                (cx + half - 0.06, cy + half - 0.06, z0 + 0.05),
                WINDOW_GLASS,
                root,
                shininess=40.0,
            )
        elif facing == "n":
            z0, z1 = cz, cz + rec
            _box(f"win_frame_{tag}", (cx - half, cy - half, z0), (cx + half, cy + half, z1), WINDOW_FRAME, root)
            _box(
                f"win_glass_{tag}",
                (cx - half + 0.06, cy - half + 0.06, z1 - 0.05),
                (cx + half - 0.06, cy + half - 0.06, z1 - 0.02),
                WINDOW_GLASS,
                root,
                shininess=40.0,
            )
        elif facing == "w":
            x0, x1 = cx, cx + rec
            _box(f"win_frame_{tag}", (x0, cy - half, cz - half), (x1, cy + half, cz + half), WINDOW_FRAME, root)
            _box(
                f"win_glass_{tag}",
                (x0 + 0.02, cy - half + 0.06, cz - half + 0.06),
                (x0 + 0.05, cy + half - 0.06, cz + half - 0.06),
                WINDOW_GLASS,
                root,
                shininess=40.0,
            )

    window_at(-2.2, hz, "s", "s_l")
    window_at(2.2, hz, "s", "s_r")
    window_at(-1.8, -hz, "n", "n_l")
    window_at(1.8, -hz, "n", "n_r")
    window_at(-hx, 0.0, "w", "w")


def _build_roof(root, cfg, hx, hz, yw):
    o = cfg.roof_overhang
    peak_y = yw + cfg.roof_rise
    x0, x1 = -hx - o, hx + o
    z0, z1 = -hz - o, hz + o
    ridge_z = 0.0

    sw = (x0, yw + 0.05, z1)
    se = (x1, yw + 0.05, z1)
    re = (x1, peak_y, ridge_z)
    rw = (x0, peak_y, ridge_z)
    make_colored_mesh("roof_s", quad(sw, se, re, rw), ROOF, shininess=6.0).reparentTo(root)

    nw = (x0, yw + 0.05, z0)
    ne = (x1, yw + 0.05, z0)
    make_colored_mesh("roof_n", quad(ne, nw, rw, re), ROOF_DARK, shininess=6.0).reparentTo(root)

    make_colored_mesh(
        "gable_w",
        [((x0 + 0.02, yw, -hz), (x0 + 0.02, yw, hz), (x0 + 0.02, peak_y, 0.0))],
        STONE_SIDE,
    ).reparentTo(root)
    make_colored_mesh(
        "gable_e",
        [((x1 - 0.02, yw, hz), (x1 - 0.02, yw, -hz), (x1 - 0.02, peak_y, 0.0))],
        STONE_DARK,
    ).reparentTo(root)

    _box(
        "ridge",
        (x0 + 0.1, peak_y - 0.08, -0.08),
        (x1 - 0.1, peak_y + 0.06, 0.08),
        TIMBER_DARK,
        root,
        shininess=12.0,
    )


def _build_chimney(root, cfg, hx, hz, yw):
    cx = hx + 0.35
    cz = -1.2
    w, d = 0.85, 0.7
    top = yw + cfg.roof_rise * 0.55 + 0.9
    _box("chimney", (cx - w * 0.5, yw - 0.3, cz - d * 0.5), (cx + w * 0.5, top, cz + d * 0.5), CHIMNEY, root)
    _box(
        "chimney_cap",
        (cx - w * 0.55, top, cz - d * 0.55),
        (cx + w * 0.55, top + 0.12, cz + d * 0.55),
        STONE_DARK,
        root,
    )
    _box(
        "smoke",
        (cx - 0.15, top + 0.2, cz - 0.15),
        (cx + 0.2, top + 0.55, cz + 0.18),
        (220, 220, 225),
        root,
        shininess=1.0,
    )
