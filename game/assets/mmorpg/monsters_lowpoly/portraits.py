"""monsters/portraits.py - render small portrait icons of 3D monsters
offscreen, for pygame UI (bestiary, target panel, slayer task icons...).

Usage inside a running ShowBase app:

    from monsters.portraits import render_portrait, portrait_to_pygame
    rgba_bytes, size = render_portrait(base, "goblin_grunt", size=96)
    surf = portrait_to_pygame(rgba_bytes, size)     # pygame.Surface with alpha
    # or cache to disk once:  save_portrait_png(base, "goblin_grunt", "icons/goblin_grunt.png")

The render uses its own tiny scene graph + camera, so it never disturbs the
main world render. Cache results - don't re-render every frame.
"""
from __future__ import annotations

import math

from panda3d.core import (Camera, FrameBufferProperties, NodePath, PerspectiveLens,
                          Texture)

from . import registry
from .lighting import setup_osrs_lighting


def render_portrait(base, key: str, size: int = 96, az: float = 35.0, el: float = 12.0,
                    head_only: bool = False, bg=(0, 0, 0, 0)):
    """Returns (rgba_bytes_top_to_bottom, (w, h))."""
    if not registry.MONSTERS:
        registry.load_all()
    fbp = FrameBufferProperties()
    fbp.set_rgba_bits(8, 8, 8, 8)
    fbp.set_depth_bits(24)
    tex = Texture("portrait")
    buf = base.win.make_texture_buffer(f"portrait_{key}", size, size, tex, True, fbp)
    buf.set_clear_color_active(True)
    buf.set_clear_color(bg)
    try:
        scene = NodePath("portrait_scene")
        setup_osrs_lighting(scene)
        rig = registry.MONSTERS[key].build()
        rig.root.reparent_to(scene)
        target = rig.joints.get("head") if head_only else None
        lo, hi = (target or rig.root).get_tight_bounds(scene)
        centre = (lo + hi) / 2
        span = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
        lens = PerspectiveLens()
        lens.set_fov(30)
        lens.set_near_far(0.05, 200)
        cam_np = scene.attach_new_node(Camera("portrait_cam", lens))
        dist = span / (2 * math.tan(math.radians(15))) * 1.15
        a, e = math.radians(az), math.radians(el)
        cam_np.set_pos(centre.x + dist * math.sin(a) * math.cos(e),
                       centre.y + dist * math.cos(a) * math.cos(e),
                       centre.z + dist * math.sin(e))
        cam_np.look_at(centre)
        dr = buf.make_display_region()
        dr.set_camera(cam_np)
        base.graphics_engine.render_frame()
        base.graphics_engine.render_frame()
        base.graphics_engine.extract_texture_data(tex, base.win.get_gsg())
        data = tex.get_ram_image_as("RGBA")      # bottom-to-top rows
        raw = bytes(data)
        row = size * 4
        flipped = b"".join(raw[i:i + row] for i in range(len(raw) - row, -1, -row))
        return flipped, (size, size)
    finally:
        base.graphics_engine.remove_window(buf)


def portrait_to_pygame(rgba: bytes, size):
    import pygame
    return pygame.image.frombuffer(rgba, size, "RGBA").copy()


def save_portrait_png(base, key: str, path: str, size: int = 96, **kw):
    rgba, (w, h) = render_portrait(base, key, size, **kw)
    try:
        from PIL import Image
        Image.frombytes("RGBA", (w, h), rgba).save(path)
    except ImportError:
        import pygame
        pygame.image.save(portrait_to_pygame(rgba, (w, h)), path)
