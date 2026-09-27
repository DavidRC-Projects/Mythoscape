"""monsters/lighting.py - OSRS-style lighting for Panda3D 1.10.x."""
from panda3d.core import (AmbientLight, DirectionalLight, Fog, LColor,
                          ShadeModelAttrib, AntialiasAttrib)


def setup_osrs_lighting(render, ambient=0.42, sun=0.85, sun_hpr=(160, -45, 0),
                        fog_color=None, fog_range=(40.0, 120.0)):
    """Ambient + one directional 'sun'. No per-pixel lighting, no shadows.

    * render.set_shader_off() keeps the fixed-function pipeline (never call
      set_shader_auto() for this look - it smooths lighting per pixel).
    * Flat normals come from MeshBuilder's duplicated vertices; the flat
      ShadeModelAttrib is a belt-and-braces extra.
    Returns (ambient_np, sun_np, fog_or_None).
    """
    render.set_shader_off()
    render.set_attrib(ShadeModelAttrib.make(ShadeModelAttrib.M_flat))
    render.set_antialias(AntialiasAttrib.M_none)

    amb = AmbientLight("ambient")
    amb.set_color(LColor(ambient, ambient, ambient * 1.05, 1))
    amb_np = render.attach_new_node(amb)

    dl = DirectionalLight("sun")
    dl.set_color(LColor(sun, sun * 0.96, sun * 0.88, 1))  # slightly warm sun
    sun_np = render.attach_new_node(dl)
    sun_np.set_hpr(*sun_hpr)

    render.set_light(amb_np)
    render.set_light(sun_np)

    fog = None
    if fog_color is not None:
        fog = Fog("distance_fog")
        fog.set_color(*fog_color)
        fog.set_linear_range(*fog_range)
        render.set_fog(fog)
    return amb_np, sun_np, fog
