#!/usr/bin/env python3
"""Mythoscape castle room props. Low-poly, flat-shaded, orthographic 3/4.

Feet sit on z=0. Front of every prop faces -Y (toward the camera / into the room).
The southernmost floor contact is the sprite anchor (see post crop origin_px).
"""
from __future__ import annotations

import math
import os
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT = "/workspace/castle_realm/room_layouts"
PROP_DIR = os.path.join(ROOT, "props")
VAULT_DIR = os.path.join(ROOT, "vaults")
LAYOUT_DIR = os.path.join(ROOT, "layouts")

_N = 0
MATS = {}


def uniq(prefix):
    global _N
    _N += 1
    return f"{prefix}_{_N}"


def M(name, rgb, rough=0.92, metal=0.0, emit=0.0):
    if name in MATS:
        return MATS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metal
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.45 if metal >= 0.4 else 0.12
            break
    if emit > 0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit
    MATS[name] = mat
    return mat


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _finish(mesh, material):
    ob = bpy.data.objects.new(mesh.name, mesh)
    link(ob)
    if material is not None:
        mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = False
    return ob


def box(name, cx, cy, cz, sx, sy, sz, material, rot=(0, 0, 0)):
    mesh = bpy.data.meshes.new(uniq(name))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if rot != (0, 0, 0):
        R = Euler(rot, "XYZ").to_matrix()
        for v in bm.verts:
            v.co = R @ v.co
    for v in bm.verts:
        v.co.x = v.co.x * sx + cx
        v.co.y = v.co.y * sy + cy
        v.co.z = v.co.z * sz + cz
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def cyl(name, cx, cy, cz, radius, depth, material, verts=8, rot=(0, 0, 0)):
    mesh = bpy.data.meshes.new(uniq(name))
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=verts,
        radius1=radius, radius2=radius, depth=depth,
    )
    if rot != (0, 0, 0):
        R = Euler(rot, "XYZ").to_matrix()
        for v in bm.verts:
            v.co = R @ v.co
    for v in bm.verts:
        v.co.x += cx
        v.co.y += cy
        v.co.z += cz
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def cone(name, cx, cy, cz, radius, height, material, verts=7):
    """Base on z=cz, tip up."""
    mesh = bpy.data.meshes.new(uniq(name))
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=verts,
        radius1=radius, radius2=0.001, depth=height,
    )
    for v in bm.verts:
        v.co.z += height * 0.5
        v.co.x += cx
        v.co.y += cy
        v.co.z += cz
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def sphere(name, cx, cy, cz, radius, material, u=8, v=6, scale=(1, 1, 1)):
    mesh = bpy.data.meshes.new(uniq(name))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)
    sx, sy, sz = scale
    for vert in bm.verts:
        vert.co.x = vert.co.x * sx + cx
        vert.co.y = vert.co.y * sy + cy
        vert.co.z = vert.co.z * sz + cz
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def hemi(name, cx, cy, cz, radius, material, segments=10, scale=(1, 1, 1)):
    """Bowl, open top, bottom at cz."""
    mesh = bpy.data.meshes.new(uniq(name))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=max(4, segments // 2), radius=radius)
    bm.verts.ensure_lookup_table()
    kill = [v for v in bm.verts if v.co.z > radius * 0.02]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
    sx, sy, sz = scale
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z = v.co.z * sz + radius * sz
        v.co.x += cx
        v.co.y += cy
        v.co.z += cz
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def prism(name, pts_xz, y0, thickness, material):
    """Extrude an XZ polygon toward -Y by thickness. pts are (x, z)."""
    n = len(pts_xz)
    verts = [(x, y0, z) for x, z in pts_xz]
    verts += [(x, y0 - thickness, z) for x, z in pts_xz]
    faces = [list(range(n))]
    faces.append(list(range(2 * n - 1, n - 1, -1)))
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    mesh = bpy.data.meshes.new(uniq(name))
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    return _finish(mesh, material)


def shade(rgb, amt):
    return tuple(max(0.0, min(1.0, c + amt)) for c in rgb)


# ---------------------------------------------------------------------------
# Props. Local: front = -Y, back = +Y, floor z = 0.
# ---------------------------------------------------------------------------

def build_linen_press():
    oak = M("lp_oak", (0.36, 0.20, 0.10))
    oak_d = M("lp_oak_d", (0.22, 0.12, 0.07))
    panel = M("lp_panel", (0.48, 0.30, 0.16))
    iron = M("lp_iron", (0.22, 0.22, 0.24), metal=0.75, rough=0.4)
    cloth = M("lp_cloth", (0.72, 0.66, 0.55))
    o = []
    o.append(box("plinth", 0, 0.02, 0.08, 1.18, 0.56, 0.16, oak_d))
    o.append(box("body", 0, 0.0, 1.18, 1.08, 0.50, 2.04, oak))
    o.append(box("cornice", 0, -0.02, 2.26, 1.22, 0.58, 0.12, oak_d))
    o.append(box("crown", 0, -0.02, 2.36, 1.06, 0.50, 0.08, oak))
    # two raised doors
    for x, sgn in ((-0.26, -1), (0.26, 1)):
        o.append(box("door", x, -0.24, 1.16, 0.46, 0.06, 1.78, panel))
        o.append(box("inset", x, -0.28, 1.20, 0.32, 0.03, 1.15, oak_d))
        o.append(cyl("knob", x + sgn * -0.16, -0.32, 1.12, 0.035, 0.04, iron, verts=8, rot=(math.pi / 2, 0, 0)))
        for z in (0.55, 1.15, 1.75):
            o.append(box("hinge", x + sgn * 0.22, -0.30, z, 0.06, 0.04, 0.14, iron))
    # linen peeking under door gap
    o.append(box("linen", 0, -0.22, 0.28, 0.70, 0.04, 0.10, cloth))
    o.append(box("stile", 0, -0.27, 1.16, 0.06, 0.04, 1.78, oak_d))
    return o


def build_cheval_mirror():
    wood = M("mir_wood", (0.40, 0.24, 0.12))
    wood_d = M("mir_wood_d", (0.24, 0.14, 0.08))
    gold = M("mir_gold", (0.78, 0.62, 0.22), metal=0.65, rough=0.35)
    glass = M("mir_glass", (0.55, 0.72, 0.78), metal=0.35, rough=0.08, emit=0.15)
    o = []
    # splayed feet
    o.append(box("footL", -0.28, 0.05, 0.06, 0.46, 0.10, 0.08, wood_d, rot=(0, 0.15, 0)))
    o.append(box("footR", 0.28, 0.05, 0.06, 0.46, 0.10, 0.08, wood_d, rot=(0, -0.15, 0)))
    o.append(box("stretcher", 0, 0.08, 0.16, 0.62, 0.06, 0.06, wood))
    o.append(box("postL", -0.30, 0.0, 1.00, 0.08, 0.08, 1.70, wood))
    o.append(box("postR", 0.30, 0.0, 1.00, 0.08, 0.08, 1.70, wood))
    o.append(box("crest", 0, 0.0, 1.88, 0.70, 0.08, 0.10, wood_d))
    # arched crest blocks
    o.append(box("arch", 0, 0.0, 1.78, 0.36, 0.08, 0.16, wood))
    o.append(cyl("glass", 0, -0.02, 1.05, 0.26, 0.03, glass, verts=16, rot=(math.pi / 2, 0, 0)))
    o.append(cyl("frame", 0, 0.015, 1.05, 0.32, 0.045, gold, verts=16, rot=(math.pi / 2, 0, 0)))
    # scale is circular; add side rails so it reads taller than round
    o.append(box("railL", -0.30, -0.01, 1.05, 0.06, 0.05, 1.35, gold))
    o.append(box("railR", 0.30, -0.01, 1.05, 0.06, 0.05, 1.35, gold))
    o.append(box("railB", 0, -0.01, 0.38, 0.60, 0.05, 0.06, gold))
    o.append(box("glass2", 0, -0.035, 1.05, 0.50, 0.02, 1.20, glass))
    return o


def build_washstand():
    wood = M("ws_wood", (0.62, 0.48, 0.32))
    wood_d = M("ws_wood_d", (0.42, 0.30, 0.18))
    basin = M("ws_basin", (0.82, 0.84, 0.86))
    water = M("ws_water", (0.45, 0.62, 0.72), emit=0.08)
    cloth = M("ws_tow", (0.85, 0.82, 0.74))
    cloth_r = M("ws_towr", (0.62, 0.18, 0.20))
    brass = M("ws_brass", (0.72, 0.55, 0.22), metal=0.7, rough=0.32)
    o = []
    for x in (-0.26, 0.26):
        for y in (-0.16, 0.16):
            o.append(box("leg", x, y, 0.38, 0.06, 0.06, 0.76, wood_d))
    o.append(box("shelf", 0, 0, 0.22, 0.58, 0.36, 0.04, wood))
    o.append(box("fold", 0, 0, 0.28, 0.32, 0.22, 0.08, cloth))
    o.append(box("top", 0, 0, 0.78, 0.70, 0.46, 0.06, wood))
    o.append(cyl("bowl", 0, -0.02, 0.86, 0.16, 0.10, basin, verts=12))
    o.append(cyl("water", 0, -0.02, 0.90, 0.12, 0.03, water, verts=12))
    # ewer
    o.append(cyl("ewer", 0.22, 0.08, 0.96, 0.055, 0.18, basin, verts=8))
    o.append(box("spout", 0.30, -0.02, 1.02, 0.10, 0.04, 0.04, basin))
    o.append(cyl("ewer_neck", 0.22, 0.08, 1.08, 0.03, 0.06, basin, verts=8))
    o.append(box("handle", 0.14, 0.08, 1.00, 0.03, 0.03, 0.12, brass))
    # towel rail
    o.append(box("railpL", -0.30, -0.18, 0.62, 0.04, 0.04, 0.28, wood_d))
    o.append(box("railpR", -0.05, -0.18, 0.62, 0.04, 0.04, 0.16, wood_d))
    o.append(cyl("rail", -0.18, -0.20, 0.70, 0.015, 0.28, brass, verts=6, rot=(0, math.pi / 2, 0)))
    o.append(box("towel", -0.18, -0.24, 0.52, 0.20, 0.04, 0.32, cloth_r))
    o.append(box("soap", -0.18, 0.08, 0.84, 0.08, 0.05, 0.03, cloth))
    return o


def build_cradle():
    wood = M("cr_wood", (0.70, 0.55, 0.36))
    wood_d = M("cr_wood_d", (0.48, 0.34, 0.20))
    linen = M("cr_lin", (0.90, 0.86, 0.78))
    rose = M("cr_rose", (0.75, 0.45, 0.52))
    o = []
    # rockers as stepped arcs
    for x in (-0.28, 0.28):
        o.append(box("rock", x, 0.0, 0.06, 0.10, 0.70, 0.08, wood_d))
        o.append(box("rock2", x, 0.0, 0.10, 0.08, 0.48, 0.06, wood_d))
    o.append(box("bed", 0, 0, 0.32, 0.78, 0.42, 0.28, wood))
    for y in (-0.18, 0.18):
        for x in (-0.32, 0, 0.32):
            o.append(box("spindle", x, y, 0.52, 0.04, 0.04, 0.22, wood_d))
    o.append(box("railL", 0, -0.20, 0.62, 0.78, 0.04, 0.06, wood))
    o.append(box("railR", 0, 0.20, 0.62, 0.78, 0.04, 0.06, wood))
    o.append(box("matt", 0, 0, 0.48, 0.68, 0.34, 0.08, linen))
    o.append(box("blank", 0, 0.02, 0.54, 0.62, 0.28, 0.05, rose))
    o.append(box("pillow", 0, 0.10, 0.58, 0.28, 0.16, 0.08, linen))
    # hood
    o.append(box("hood_postL", -0.34, 0.16, 0.70, 0.06, 0.06, 0.70, wood))
    o.append(box("hood_postR", 0.34, 0.16, 0.70, 0.06, 0.06, 0.70, wood))
    o.append(box("hood", 0, 0.12, 1.02, 0.74, 0.28, 0.08, wood_d))
    o.append(box("hoodc", 0, 0.02, 0.78, 0.70, 0.06, 0.42, linen))
    return o


def build_dining_chair():
    wood = M("ch_wood", (0.34, 0.18, 0.09))
    wood_d = M("ch_wood_d", (0.20, 0.10, 0.06))
    red = M("ch_red", (0.55, 0.10, 0.12))
    gold = M("ch_gold", (0.80, 0.64, 0.22), metal=0.7, rough=0.35)
    o = []
    for x in (-0.18, 0.18):
        for y in (-0.18, 0.18):
            o.append(box("leg", x, y, 0.26, 0.055, 0.055, 0.52, wood))
    o.append(box("stF", 0, -0.18, 0.14, 0.32, 0.04, 0.04, wood_d))
    o.append(box("stB", 0, 0.18, 0.14, 0.32, 0.04, 0.04, wood_d))
    o.append(box("stL", -0.18, 0, 0.14, 0.04, 0.30, 0.04, wood_d))
    o.append(box("stR", 0.18, 0, 0.14, 0.04, 0.30, 0.04, wood_d))
    o.append(box("seat", 0, 0, 0.54, 0.46, 0.46, 0.07, wood))
    o.append(box("cush", 0, -0.02, 0.60, 0.38, 0.36, 0.06, red))
    o.append(box("bpL", -0.18, 0.18, 0.98, 0.06, 0.06, 0.82, wood))
    o.append(box("bpR", 0.18, 0.18, 0.98, 0.06, 0.06, 0.82, wood))
    o.append(box("crest", 0, 0.18, 1.40, 0.48, 0.07, 0.08, wood_d))
    o.append(box("finL", -0.22, 0.18, 1.48, 0.06, 0.06, 0.08, gold))
    o.append(box("finR", 0.22, 0.18, 1.48, 0.06, 0.06, 0.08, gold))
    o.append(box("splat", 0, 0.155, 1.00, 0.22, 0.035, 0.58, wood_d))
    o.append(box("splat2", 0, 0.145, 1.00, 0.08, 0.03, 0.40, gold))
    o.append(box("midrail", 0, 0.17, 0.70, 0.36, 0.045, 0.045, wood))
    return o


def build_serving_cart():
    wood = M("sc_wood", (0.45, 0.28, 0.14))
    wood_d = M("sc_wood_d", (0.28, 0.16, 0.09))
    iron = M("sc_iron", (0.18, 0.18, 0.20), metal=0.8, rough=0.4)
    plate = M("sc_plate", (0.82, 0.84, 0.86))
    cloth = M("sc_cloth", (0.55, 0.12, 0.16))
    food = M("sc_food", (0.72, 0.55, 0.28))
    dome = M("sc_dome", (0.75, 0.72, 0.62), metal=0.55, rough=0.3)
    o = []
    for x in (-0.32, 0.32):
        for y in (-0.20, 0.18):
            o.append(box("post", x, y, 0.48, 0.05, 0.05, 0.90, wood_d))
    o.append(box("low", 0, 0.0, 0.28, 0.72, 0.46, 0.04, wood))
    o.append(box("top", 0, -0.02, 0.92, 0.78, 0.50, 0.05, wood))
    o.append(box("cloth", 0, -0.06, 0.78, 0.50, 0.08, 0.22, cloth))
    # handle
    o.append(box("hL", -0.32, -0.36, 0.70, 0.05, 0.28, 0.05, wood))
    o.append(box("hR", 0.32, -0.36, 0.70, 0.05, 0.28, 0.05, wood))
    o.append(cyl("hbar", 0, -0.50, 0.78, 0.02, 0.70, iron, verts=6, rot=(0, math.pi / 2, 0)))
    # wheels
    for x in (-0.38, 0.38):
        for y in (-0.22, 0.20):
            o.append(cyl("wheel", x, y, 0.10, 0.10, 0.04, iron, verts=10, rot=(0, math.pi / 2, 0)))
    # dishes
    o.append(cyl("pl1", -0.16, 0.02, 0.97, 0.10, 0.025, plate, verts=10))
    o.append(cyl("pl2", 0.16, -0.06, 0.97, 0.09, 0.025, plate, verts=10))
    o.append(hemi("cloche", 0.12, 0.10, 0.96, 0.10, dome, segments=8))
    o.append(sphere("loaf", -0.18, -0.08, 1.02, 0.06, food, u=6, v=4, scale=(1.3, 0.8, 0.7)))
    o.append(cyl("jug", -0.05, 0.12, 0.40, 0.06, 0.16, M("sc_jug", (0.35, 0.42, 0.55)), verts=8))
    return o


def build_wine_rack():
    wood = M("wr_wood", (0.18, 0.10, 0.07))
    wood_m = M("wr_wood_m", (0.30, 0.17, 0.10))
    greens = [
        M("wr_g1", (0.18, 0.36, 0.22)),
        M("wr_g2", (0.28, 0.42, 0.20)),
        M("wr_a1", (0.55, 0.32, 0.12)),
        M("wr_a2", (0.40, 0.16, 0.18)),
    ]
    cork = M("wr_cork", (0.72, 0.60, 0.40))
    o = []
    o.append(box("plinth", 0, 0.02, 0.06, 1.15, 0.42, 0.12, wood))
    o.append(box("sideL", -0.52, 0, 0.95, 0.08, 0.40, 1.70, wood_m))
    o.append(box("sideR", 0.52, 0, 0.95, 0.08, 0.40, 1.70, wood_m))
    o.append(box("top", 0, 0, 1.82, 1.16, 0.42, 0.08, wood))
    o.append(box("back", 0, 0.16, 0.95, 1.00, 0.04, 1.60, wood))
    cols = [-0.36, -0.18, 0.0, 0.18, 0.36]
    zs = [0.30, 0.58, 0.86, 1.14, 1.42]
    for i, z in enumerate(zs):
        o.append(box("shelf", 0, 0.02, z - 0.12, 0.98, 0.32, 0.035, wood_m))
        for j, x in enumerate(cols):
            if (i + j) % 2 == 1 and i != 2:
                continue
            g = greens[(i + j) % 4]
            o.append(cyl("bot", x, -0.02, z, 0.045, 0.20, g, verts=7, rot=(math.pi / 2, 0, 0)))
            o.append(cyl("neck", x, -0.14, z, 0.02, 0.06, g, verts=6, rot=(math.pi / 2, 0, 0)))
            o.append(cyl("cork", x, -0.18, z, 0.018, 0.03, cork, verts=6, rot=(math.pi / 2, 0, 0)))
    return o


def build_chapel_altar():
    stone = M("al_stone", (0.62, 0.60, 0.58))
    stone_d = M("al_stone_d", (0.40, 0.38, 0.40))
    cloth = M("al_cloth", (0.45, 0.08, 0.12))
    gold = M("al_gold", (0.82, 0.66, 0.24), metal=0.65, rough=0.32)
    wax = M("al_wax", (0.90, 0.86, 0.72))
    flame = M("al_flame", (1.0, 0.72, 0.25), emit=2.2)
    book = M("al_book", (0.35, 0.18, 0.12))
    page = M("al_page", (0.90, 0.86, 0.74))
    o = []
    o.append(box("step", 0, 0.05, 0.08, 1.70, 0.85, 0.16, stone_d))
    o.append(box("mensa", 0, 0.0, 0.78, 1.45, 0.62, 0.70, stone))
    o.append(box("lip", 0, -0.02, 1.16, 1.55, 0.68, 0.08, stone_d))
    # antependium
    o.append(box("cloth", 0, -0.30, 0.62, 1.20, 0.04, 0.70, cloth))
    o.append(box("goldband", 0, -0.33, 0.95, 1.24, 0.02, 0.06, gold))
    o.append(box("cross_v", 0, -0.34, 0.62, 0.08, 0.02, 0.36, gold))
    o.append(box("cross_h", 0, -0.34, 0.70, 0.22, 0.02, 0.07, gold))
    # candles
    for x in (-0.42, 0.42):
        o.append(cyl("stick", x, -0.08, 1.32, 0.035, 0.28, wax, verts=7))
        o.append(cone("flame", x, -0.08, 1.46, 0.03, 0.08, flame, verts=6))
        o.append(cyl("cup", x, -0.08, 1.20, 0.05, 0.04, gold, verts=7))
    # open book
    o.append(box("bookL", -0.10, 0.05, 1.22, 0.16, 0.12, 0.03, book))
    o.append(box("bookR", 0.10, 0.05, 1.22, 0.16, 0.12, 0.03, page))
    o.append(box("rose", 0, 0.08, 1.24, 0.08, 0.08, 0.04, M("al_rose", (0.75, 0.22, 0.32))))
    return o


def build_lectern():
    wood = M("lec_wood", (0.30, 0.16, 0.09))
    wood_d = M("lec_wood_d", (0.18, 0.10, 0.06))
    gold = M("lec_gold", (0.75, 0.58, 0.20), metal=0.6, rough=0.35)
    page = M("lec_page", (0.88, 0.84, 0.72))
    leather = M("lec_lea", (0.40, 0.14, 0.12))
    o = []
    o.append(box("base", 0, 0, 0.06, 0.48, 0.42, 0.12, wood_d))
    o.append(box("post", 0, 0.02, 0.70, 0.10, 0.10, 1.16, wood))
    o.append(box("collar", 0, 0.02, 0.28, 0.16, 0.16, 0.06, gold))
    # angled book board, tilt toward camera (-Y) so the top leans to -Y
    o.append(box("board", 0, -0.06, 1.28, 0.46, 0.34, 0.04, wood, rot=(0.45, 0, 0)))
    o.append(box("lip", 0, -0.22, 1.12, 0.46, 0.04, 0.05, wood_d, rot=(0.45, 0, 0)))
    o.append(box("pgL", -0.08, -0.08, 1.32, 0.16, 0.20, 0.015, page, rot=(0.45, 0, 0)))
    o.append(box("pgR", 0.09, -0.08, 1.32, 0.16, 0.20, 0.015, leather, rot=(0.45, 0, 0)))
    o.append(box("ribbon", 0.02, -0.10, 1.30, 0.02, 0.22, 0.012, gold, rot=(0.45, 0, 0)))
    return o


def build_prayer_kneeler():
    wood = M("kn_wood", (0.32, 0.18, 0.10))
    wood_d = M("kn_wood_d", (0.20, 0.11, 0.07))
    pad = M("kn_pad", (0.42, 0.10, 0.16))
    page = M("kn_page", (0.88, 0.84, 0.74))
    o = []
    for x in (-0.22, 0.22):
        o.append(box("post", x, 0.10, 0.48, 0.06, 0.06, 0.96, wood))
        o.append(box("leg", x, -0.16, 0.16, 0.06, 0.06, 0.32, wood_d))
    o.append(box("knee", 0, -0.10, 0.32, 0.52, 0.28, 0.08, wood))
    o.append(box("pad", 0, -0.10, 0.38, 0.46, 0.24, 0.06, pad))
    o.append(box("arm", 0, 0.12, 0.92, 0.56, 0.08, 0.06, wood_d))
    o.append(box("bookrest", 0, 0.02, 0.84, 0.36, 0.16, 0.03, wood, rot=(0.5, 0, 0)))
    o.append(box("book", 0, 0.0, 0.90, 0.22, 0.12, 0.02, page, rot=(0.5, 0, 0)))
    o.append(box("stretcher", 0, -0.16, 0.10, 0.44, 0.04, 0.04, wood_d))
    return o


def build_arming_dummy():
    wood = M("dm_wood", (0.42, 0.26, 0.13))
    wood_d = M("dm_wood_d", (0.26, 0.15, 0.08))
    pad = M("dm_pad", (0.55, 0.16, 0.14))
    straw = M("dm_straw", (0.72, 0.58, 0.28))
    iron = M("dm_iron", (0.35, 0.38, 0.42), metal=0.7, rough=0.35)
    o = []
    o.append(cyl("base", 0, 0, 0.06, 0.28, 0.12, wood_d, verts=10))
    o.append(cyl("pole", 0, 0, 0.85, 0.06, 1.45, wood, verts=7))
    o.append(cyl("torso", 0, 0, 1.25, 0.20, 0.48, pad, verts=8))
    o.append(box("arms", 0, 0, 1.42, 0.85, 0.08, 0.08, wood))
    o.append(sphere("helm", 0, 0, 1.68, 0.16, straw, u=8, v=6))
    o.append(cyl("neck", 0, 0, 1.52, 0.07, 0.10, straw, verts=7))
    # shield on the left arm
    o.append(prism(
        "mini_shield",
        [(-0.55, 1.22), (-0.38, 1.22), (-0.34, 1.42), (-0.46, 1.62), (-0.58, 1.42)],
        0.02, 0.05, iron,
    ))
    o.append(box("boss", -0.48, -0.02, 1.40, 0.06, 0.04, 0.06, M("dm_boss", (0.75, 0.58, 0.2), metal=0.6)))
    # rope belt
    o.append(cyl("belt", 0, 0, 1.12, 0.21, 0.05, wood_d, verts=8))
    return o


def build_spinning_wheel():
    wood = M("sw_wood", (0.50, 0.32, 0.16))
    wood_d = M("sw_wood_d", (0.32, 0.18, 0.10))
    wool = M("sw_wool", (0.90, 0.88, 0.82))
    iron = M("sw_iron", (0.25, 0.25, 0.28), metal=0.6, rough=0.4)
    o = []
    o.append(box("bench", 0, 0.05, 0.08, 0.85, 0.36, 0.08, wood_d))
    o.append(box("legL", -0.32, 0.05, 0.22, 0.06, 0.28, 0.28, wood))
    o.append(box("legR", 0.18, 0.05, 0.22, 0.06, 0.28, 0.28, wood))
    # wheel uprights
    o.append(box("upL", -0.22, 0.02, 0.55, 0.05, 0.05, 0.85, wood))
    o.append(box("upR", 0.10, 0.02, 0.55, 0.05, 0.05, 0.70, wood))
    # big wheel facing camera-ish, axis along Y so the disc is seen from the side (XZ)
    o.append(cyl("wheel", -0.06, 0.0, 0.72, 0.36, 0.05, wood, verts=16, rot=(math.pi / 2, 0, 0)))
    o.append(cyl("hub", -0.06, -0.04, 0.72, 0.06, 0.07, wood_d, verts=8, rot=(math.pi / 2, 0, 0)))
    for i in range(6):
        ang = i * math.pi / 3
        o.append(box(
            "spoke",
            -0.06 + math.cos(ang) * 0.16,
            -0.01,
            0.72 + math.sin(ang) * 0.16,
            0.28, 0.02, 0.025,
            wood_d,
            rot=(0, ang, 0),
        ))
    # flyer / maidens
    o.append(box("maid", 0.32, 0.0, 0.55, 0.06, 0.06, 0.70, wood))
    o.append(cyl("flyer", 0.32, -0.08, 0.78, 0.07, 0.04, iron, verts=8, rot=(math.pi / 2, 0, 0)))
    o.append(box("treadle", 0.05, -0.16, 0.10, 0.35, 0.08, 0.03, wood_d))
    o.append(sphere("wool", 0.32, 0.10, 0.28, 0.10, wool, u=7, v=5))
    o.append(box("basket", 0.34, 0.12, 0.12, 0.18, 0.16, 0.10, wood))
    return o


def build_portrait():
    gilt = M("po_gilt", (0.72, 0.55, 0.18), metal=0.55, rough=0.35)
    wood = M("po_wood", (0.28, 0.16, 0.09))
    sky = M("po_sky", (0.45, 0.62, 0.78))
    hill = M("po_hill", (0.30, 0.42, 0.28))
    robe = M("po_robe", (0.40, 0.12, 0.18))
    skin = M("po_skin", (0.86, 0.70, 0.52))
    o = []
    # hangs, bottom of frame around z=0 so a lift places it; build already at hanging height
    o.append(box("plaque", 0, 0.04, 0.70, 0.78, 0.06, 1.15, wood))
    o.append(box("frame", 0, 0.0, 0.72, 0.70, 0.08, 1.05, gilt))
    o.append(box("sky", 0, -0.03, 0.95, 0.52, 0.02, 0.42, sky))
    o.append(box("hill", 0, -0.035, 0.62, 0.52, 0.02, 0.28, hill))
    o.append(box("robe", 0, -0.04, 0.70, 0.18, 0.02, 0.42, robe))
    o.append(sphere("head", 0, -0.05, 1.00, 0.08, skin, u=7, v=5))
    o.append(box("plate", 0, -0.02, 0.28, 0.28, 0.03, 0.08, gilt))
    return o


def build_heater_shield():
    wood = M("sh_wood", (0.34, 0.20, 0.10))
    red = M("sh_red", (0.55, 0.10, 0.12))
    white = M("sh_wh", (0.88, 0.86, 0.80))
    iron = M("sh_iron", (0.55, 0.58, 0.62), metal=0.75, rough=0.3)
    gold = M("sh_gold", (0.80, 0.64, 0.22), metal=0.65, rough=0.32)
    o = []
    o.append(box("plaque", 0, 0.06, 0.85, 0.85, 0.08, 1.25, wood))
    # crossed swords behind
    o.append(box("sw1", 0, 0.02, 0.85, 0.08, 0.04, 1.15, iron, rot=(0, 0.5, 0)))
    o.append(box("sw2", 0, 0.02, 0.85, 0.08, 0.04, 1.15, iron, rot=(0, -0.5, 0)))
    o.append(box("hilt1", 0.15, 0.0, 1.30, 0.16, 0.04, 0.05, gold))
    o.append(box("hilt2", -0.15, 0.0, 1.30, 0.16, 0.04, 0.05, gold))
    kite = [
        (-0.28, 0.35), (0.28, 0.35), (0.34, 0.70), (0.22, 1.15),
        (0.0, 1.40), (-0.22, 1.15), (-0.34, 0.70),
    ]
    o.append(prism("kite", kite, 0.0, 0.07, red))
    # pale bend
    o.append(box("bend", 0.02, -0.06, 0.85, 0.10, 0.02, 0.70, white, rot=(0, 0.35, 0)))
    o.append(cyl("boss", 0, -0.08, 0.82, 0.07, 0.04, gold, verts=8, rot=(math.pi / 2, 0, 0)))
    return o


def build_cauldron():
    iron = M("ca_iron", (0.16, 0.16, 0.18), metal=0.75, rough=0.38)
    iron_d = M("ca_iron_d", (0.10, 0.10, 0.12), metal=0.6, rough=0.45)
    stew = M("ca_stew", (0.45, 0.28, 0.12), emit=0.05)
    log = M("ca_log", (0.35, 0.20, 0.10))
    flame = M("ca_flame", (1.0, 0.55, 0.12), emit=1.8)
    ember = M("ca_ember", (0.9, 0.25, 0.08), emit=1.2)
    o = []
    # tripod
    for ang in (0.4, 2.5, 4.4):
        o.append(box(
            "leg",
            math.sin(ang) * 0.22,
            math.cos(ang) * 0.22,
            0.38,
            0.06, 0.06, 0.78,
            iron_d,
            rot=(0.35 * math.cos(ang), 0.35 * math.sin(ang), 0),
        ))
    o.append(hemi("pot", 0, 0, 0.55, 0.34, iron, segments=12, scale=(1.05, 1.05, 0.85)))
    o.append(cyl("rim", 0, 0, 0.88, 0.36, 0.06, iron_d, verts=12))
    o.append(cyl("stew", 0, 0, 0.86, 0.28, 0.04, stew, verts=10))
    # handles
    o.append(box("hL", -0.40, 0, 0.84, 0.12, 0.06, 0.08, iron))
    o.append(box("hR", 0.40, 0, 0.84, 0.12, 0.06, 0.08, iron))
    # fire
    o.append(box("log1", 0, 0, 0.08, 0.40, 0.08, 0.08, log, rot=(0, 0.4, 0)))
    o.append(box("log2", 0, 0, 0.10, 0.36, 0.08, 0.08, log, rot=(0, -0.5, 0)))
    o.append(cone("fl1", 0.0, -0.02, 0.14, 0.06, 0.16, flame))
    o.append(cone("fl2", 0.08, 0.04, 0.12, 0.04, 0.10, ember))
    # ladle
    o.append(box("ladle", 0.22, -0.28, 0.95, 0.03, 0.28, 0.03, wood_if()))
    o.append(sphere("ladle_cup", 0.22, -0.42, 0.90, 0.05, iron, u=6, v=4))
    return o


def wood_if():
    return M("ca_wood", (0.45, 0.28, 0.14))


def build_relic_rack(theme="gold"):
    if theme == "sky":
        wood = M("rk_wood_sky", (0.35, 0.48, 0.52))
        trim = M("rk_trim_sky", (0.45, 0.85, 0.90), metal=0.4, emit=0.35)
        gem_c = (0.40, 0.95, 1.0)
    elif theme == "rose":
        wood = M("rk_wood_rose", (0.55, 0.48, 0.42))
        trim = M("rk_trim_rose", (0.78, 0.74, 0.70), metal=0.45)
        gem_c = (0.85, 0.45, 0.55)
    elif theme == "gothic":
        wood = M("rk_wood_g", (0.16, 0.12, 0.14))
        trim = M("rk_trim_g", (0.30, 0.30, 0.34), metal=0.7, rough=0.4)
        gem_c = (0.55, 0.12, 0.16)
    else:
        wood = M("rk_wood", (0.34, 0.20, 0.10))
        trim = M("rk_trim", (0.78, 0.62, 0.22), metal=0.65, rough=0.32)
        gem_c = (0.25, 0.65, 0.35)
    gem = M(f"rk_gem_{theme}", gem_c, emit=0.7, metal=0.2, rough=0.2)
    bar = M(f"rk_bar_{theme}", (0.80, 0.64, 0.22), metal=0.75, rough=0.3)
    cup = M(f"rk_cup_{theme}", (0.82, 0.80, 0.74), metal=0.6, rough=0.28)
    book = M(f"rk_book_{theme}", (0.35, 0.14, 0.16))
    o = []
    o.append(box("plinth", 0, 0.02, 0.06, 1.05, 0.40, 0.12, wood))
    o.append(box("postL", -0.46, 0, 1.05, 0.08, 0.32, 1.90, wood))
    o.append(box("postR", 0.46, 0, 1.05, 0.08, 0.32, 1.90, wood))
    o.append(box("corn", 0, 0, 2.02, 1.08, 0.36, 0.08, trim))
    zs = [0.40, 0.85, 1.30, 1.72]
    for i, z in enumerate(zs):
        o.append(box("shelf", 0, 0.0, z, 0.92, 0.34, 0.045, wood))
    # ingots
    for i, x in enumerate((-0.22, 0.0, 0.22)):
        o.append(box("ingot", x, -0.02, 0.48, 0.16, 0.08, 0.05, bar))
    # goblet
    o.append(cyl("gstem", -0.22, -0.02, 1.00, 0.025, 0.16, cup, verts=6))
    o.append(hemi("gcup", -0.22, -0.02, 1.08, 0.07, cup, segments=8))
    o.append(cyl("gfoot", -0.22, -0.02, 0.90, 0.05, 0.03, cup, verts=7))
    # book
    o.append(box("book", 0.18, 0.0, 0.92, 0.20, 0.14, 0.06, book))
    o.append(box("pages", 0.18, -0.02, 0.95, 0.16, 0.10, 0.02, M(f"rk_pg_{theme}", (0.9, 0.86, 0.75))))
    # crown
    o.append(cyl("crown", 0.0, -0.02, 1.40, 0.08, 0.08, trim, verts=7))
    for x in (-0.05, 0, 0.05):
        o.append(cone("cpoint", x, -0.02, 1.44, 0.015, 0.06, trim, verts=4))
    # gem
    o.append(sphere("gem", 0.20, -0.04, 1.82, 0.07, gem, u=6, v=5))
    o.append(box("relic", -0.18, 0.0, 1.78, 0.22, 0.08, 0.06, bar))
    return o


def build_spear_stand():
    wood = M("sp_wood", (0.40, 0.24, 0.12))
    wood_d = M("sp_wood_d", (0.26, 0.15, 0.08))
    iron = M("sp_iron", (0.62, 0.64, 0.68), metal=0.7, rough=0.32)
    shaft = M("sp_shaft", (0.45, 0.30, 0.16))
    red = M("sp_red", (0.50, 0.12, 0.14))
    o = []
    o.append(cyl("tub", 0, 0, 0.22, 0.28, 0.40, wood_d, verts=10))
    o.append(cyl("rim", 0, 0, 0.42, 0.30, 0.06, wood, verts=10))
    o.append(cyl("band", 0, 0, 0.22, 0.29, 0.04, iron, verts=10))
    spears = [(-0.08, 0.02, -0.18), (0.06, -0.04, 0.05), (0.0, 0.06, 0.22), (-0.02, -0.02, -0.05), (0.10, 0.0, 0.12)]
    for i, (x, y, tilt) in enumerate(spears):
        o.append(box("shaft", x, y, 1.15, 0.035, 0.035, 1.55, shaft, rot=(tilt, 0, 0)))
        o.append(cone("tip", x, y - 0.12, 1.95, 0.04, 0.16, iron, verts=4))
    # leaning round shield
    o.append(cyl("rshield", 0.38, 0.05, 0.55, 0.28, 0.05, red, verts=12, rot=(math.pi / 2.4, 0.3, 0)))
    o.append(cyl("rboss", 0.38, -0.08, 0.58, 0.07, 0.04, iron, verts=8, rot=(math.pi / 2.4, 0.3, 0)))
    return o


def coin_stack(o, x, y, radii, color, name="coin"):
    z = 0.0
    for i, r in enumerate(radii):
        h = 0.055
        o.append(cyl(name, x, y, z + h * 0.5, r, h, color, verts=10))
        z += h * 0.82
    return z


def build_vault(theme):
    """Heavy door + lock + coin piles + one chest. Back of the frame is +Y."""
    if theme == "gothic":
        stone = M("vg_stone", (0.20, 0.18, 0.22))
        stone_d = M("vg_stone_d", (0.10, 0.09, 0.12))
        door_c = M("vg_door", (0.14, 0.14, 0.16), metal=0.8, rough=0.42)
        band = M("vg_band", (0.28, 0.28, 0.32), metal=0.75, rough=0.35)
        coin_c = M("vg_coin", (0.62, 0.48, 0.18), metal=0.7, rough=0.35)
        accent = M("vg_accent", (0.45, 0.12, 0.14))
        chest_c = M("vg_chest", (0.22, 0.13, 0.08))
    elif theme == "rose":
        stone = M("vr_stone", (0.84, 0.80, 0.74))
        stone_d = M("vr_stone_d", (0.62, 0.58, 0.54))
        door_c = M("vr_door", (0.78, 0.76, 0.74), metal=0.35, rough=0.4)
        band = M("vr_band", (0.72, 0.68, 0.60), metal=0.45, rough=0.35)
        coin_c = M("vr_coin", (0.78, 0.78, 0.80), metal=0.75, rough=0.28)
        accent = M("vr_accent", (0.74, 0.28, 0.38))
        chest_c = M("vr_chest", (0.70, 0.58, 0.46))
    elif theme == "king":
        stone = M("vk_stone", (0.32, 0.38, 0.50))
        stone_d = M("vk_stone_d", (0.16, 0.20, 0.32))
        door_c = M("vk_door", (0.78, 0.62, 0.20), metal=0.75, rough=0.32)
        band = M("vk_band", (0.90, 0.78, 0.35), metal=0.8, rough=0.28)
        coin_c = M("vk_coin", (0.95, 0.78, 0.28), metal=0.8, rough=0.25)
        accent = M("vk_accent", (0.12, 0.22, 0.55))
        chest_c = M("vk_chest", (0.30, 0.18, 0.10))
    else:  # sky
        stone = M("vs_stone", (0.40, 0.55, 0.60))
        stone_d = M("vs_stone_d", (0.22, 0.34, 0.40))
        door_c = M("vs_door", (0.45, 0.85, 0.92), metal=0.25, rough=0.15, emit=0.45)
        band = M("vs_band", (0.70, 0.95, 1.0), metal=0.3, emit=0.6)
        coin_c = M("vs_coin", (0.55, 0.90, 0.95), metal=0.4, emit=0.35)
        accent = M("vs_accent", (0.30, 0.70, 0.85), emit=0.3)
        chest_c = M("vs_chest", (0.28, 0.45, 0.52))
    iron = M(f"vlock_{theme}", (0.18, 0.18, 0.2), metal=0.8, rough=0.35)
    o = []
    # jambs and stepped gothic / square head
    o.append(box("jambL", -0.85, 0.15, 1.25, 0.28, 0.55, 2.50, stone_d))
    o.append(box("jambR", 0.85, 0.15, 1.25, 0.28, 0.55, 2.50, stone))
    o.append(box("lintel", 0, 0.15, 2.45, 1.70, 0.55, 0.28, stone))
    o.append(box("peak", 0, 0.12, 2.72, 0.70, 0.48, 0.28, stone_d))
    o.append(box("cap", 0, 0.10, 2.92, 0.28, 0.40, 0.18, accent))
    # door leaf
    o.append(box("door", 0, -0.02, 1.20, 1.15, 0.12, 2.15, door_c))
    for z in (0.45, 1.15, 1.80):
        o.append(box("band", 0, -0.09, z, 1.18, 0.04, 0.10, band))
    # rivets
    for x in (-0.42, 0, 0.42):
        for z in (0.30, 0.75, 1.35, 1.90):
            o.append(cyl("rivet", x, -0.10, z, 0.03, 0.03, iron, verts=5, rot=(math.pi / 2, 0, 0)))
    # ring + lock
    o.append(cyl("ring", 0.28, -0.14, 1.15, 0.10, 0.03, iron, verts=10, rot=(math.pi / 2, 0, 0)))
    o.append(box("lock", -0.22, -0.12, 1.15, 0.22, 0.08, 0.28, iron))
    o.append(box("keyhole", -0.22, -0.17, 1.12, 0.05, 0.02, 0.10, stone_d))
    o.append(box("bar", 0, -0.11, 1.55, 0.90, 0.05, 0.08, band))
    # grill window
    o.append(box("win", 0, -0.10, 1.95, 0.36, 0.04, 0.28, stone_d))
    for x in (-0.10, 0, 0.10):
        o.append(box("barv", x, -0.13, 1.95, 0.025, 0.03, 0.26, iron))
    # side banners for king, rose relief, crystal spikes
    if theme == "king":
        o.append(box("banL", -1.15, 0.05, 1.4, 0.08, 0.06, 1.3, accent))
        o.append(box("banR", 1.15, 0.05, 1.4, 0.08, 0.06, 1.3, accent))
        o.append(box("crown", 0, -0.16, 2.55, 0.22, 0.06, 0.10, band))
    elif theme == "rose":
        o.append(sphere("rose", 0, -0.12, 2.15, 0.10, accent, u=6, v=4))
        for ang in range(5):
            a = ang * math.pi * 2 / 5
            o.append(sphere(
                "petal",
                math.cos(a) * 0.10,
                -0.14,
                2.15 + math.sin(a) * 0.10,
                0.045, accent, u=5, v=4,
            ))
    elif theme == "sky":
        for x, z, h in ((-1.05, 0.4, 0.9), (1.05, 0.6, 1.15), (-1.0, 1.8, 0.7), (1.02, 2.0, 0.85), (0, 2.85, 0.45)):
            o.append(cone("shard", x, 0.0, z, 0.08, h, band, verts=4))
    elif theme == "gothic":
        o.append(box("spikeL", -0.55, 0.05, 2.70, 0.08, 0.08, 0.35, stone_d))
        o.append(box("spikeR", 0.55, 0.05, 2.70, 0.08, 0.08, 0.35, stone_d))
    # coins in front of the door (toward -Y)
    coin_stack(o, -0.35, -0.75, [0.28, 0.24, 0.20, 0.16, 0.12], coin_c)
    coin_stack(o, 0.30, -0.95, [0.22, 0.18, 0.14, 0.10], coin_c)
    coin_stack(o, 0.05, -0.60, [0.16, 0.12, 0.09], coin_c)
    # one chest to the right, not a row of chests
    o.append(box("chest", 1.35, -0.35, 0.28, 0.55, 0.38, 0.48, chest_c))
    o.append(box("lid", 1.35, -0.32, 0.56, 0.58, 0.40, 0.10, shade_mat(theme, chest_c)))
    o.append(box("cbands", 1.35, -0.52, 0.32, 0.58, 0.04, 0.08, band))
    o.append(box("clock", 1.35, -0.54, 0.36, 0.10, 0.04, 0.10, iron))
    return o


def shade_mat(theme, src):
    # slightly darker lid — unique material
    return M(f"vlid_{theme}", (0.15, 0.12, 0.10) if theme == "gothic" else (0.55, 0.42, 0.22))


def build_bed_scene():
    """Scene-only stand-in for the EXISTING four-poster. Not exported."""
    wood = M("bed_wood", (0.36, 0.20, 0.11))
    cloth = M("bed_cloth", (0.48, 0.12, 0.16))
    linen = M("bed_lin", (0.88, 0.84, 0.76))
    gold = M("bed_gold", (0.78, 0.62, 0.22), metal=0.5, rough=0.35)
    o = []
    for x in (-0.7, 0.7):
        for y in (-1.0, 0.95):
            o.append(box("post", x, y, 0.85, 0.10, 0.10, 1.70, wood))
            o.append(cone("fin", x, y, 1.70, 0.06, 0.14, gold, verts=4))
    o.append(box("canopy", 0, 0.0, 1.68, 1.55, 2.10, 0.08, cloth))
    o.append(box("frame", 0, 0.0, 0.28, 1.40, 2.00, 0.20, wood))
    o.append(box("matt", 0, -0.05, 0.46, 1.25, 1.85, 0.16, linen))
    o.append(box("blank", 0, -0.15, 0.56, 1.20, 1.30, 0.08, cloth))
    o.append(box("pillow", 0, 0.65, 0.60, 0.70, 0.28, 0.10, linen))
    # side curtain
    o.append(box("curt", -0.72, 0.0, 1.05, 0.04, 1.5, 1.05, cloth))
    return o


def build_table_scene():
    wood = M("tb_wood", (0.40, 0.24, 0.12))
    wood_d = M("tb_wood_d", (0.24, 0.14, 0.08))
    plate = M("tb_plate", (0.85, 0.86, 0.84))
    food = M("tb_food", (0.62, 0.40, 0.22))
    o = []
    o.append(box("top", 0, 0, 0.74, 2.40, 1.05, 0.08, wood))
    for x in (-0.85, 0.85):
        o.append(box("tress", x, 0, 0.36, 0.12, 0.90, 0.64, wood_d))
        o.append(box("foot", x, 0, 0.06, 0.16, 1.00, 0.08, wood))
    for x in (-0.7, 0, 0.7):
        o.append(cyl("plate", x, -0.05, 0.80, 0.16, 0.03, plate, verts=10))
        o.append(sphere("food", x, -0.05, 0.84, 0.06, food, u=6, v=4))
    o.append(cyl("jug", 0.35, 0.25, 0.92, 0.07, 0.18, M("tb_jug", (0.32, 0.40, 0.55)), verts=8))
    return o


def build_rug(w=3.2, d=2.2, rgb=(0.45, 0.12, 0.14)):
    border = M("rug_b", shade(rgb, -0.12))
    field = M("rug_f", rgb)
    motif = M("rug_m", shade(rgb, 0.25))
    o = []
    o.append(box("border", 0, 0, 0.01, w, d, 0.02, border))
    o.append(box("field", 0, 0, 0.025, w - 0.28, d - 0.28, 0.02, field))
    o.append(box("motif", 0, 0, 0.04, 0.45, 0.45, 0.015, motif))
    return o


def build_figure():
    cloth = M("fig_cloth", (0.15, 0.28, 0.62))
    skin = M("fig_skin", (0.86, 0.68, 0.50))
    boot = M("fig_boot", (0.22, 0.14, 0.08))
    o = []
    o.append(box("legL", -0.08, 0, 0.40, 0.12, 0.12, 0.72, cloth))
    o.append(box("legR", 0.08, 0, 0.40, 0.12, 0.12, 0.72, cloth))
    o.append(box("bootL", -0.08, -0.03, 0.06, 0.14, 0.18, 0.12, boot))
    o.append(box("bootR", 0.08, -0.03, 0.06, 0.14, 0.18, 0.12, boot))
    o.append(box("body", 0, 0, 1.05, 0.36, 0.18, 0.52, cloth))
    o.append(box("armL", -0.26, 0, 1.02, 0.10, 0.10, 0.40, cloth))
    o.append(box("armR", 0.26, 0, 1.02, 0.10, 0.10, 0.40, cloth))
    o.append(sphere("head", 0, 0, 1.48, 0.14, skin, u=7, v=5))
    return o


def build_shell(W, D, wall_rgb, floor_a, floor_b, wall_h=2.65):
    dark = M("grout", (0.12, 0.10, 0.09))
    fa = M(f"fa_{wall_rgb[0]:.2f}", floor_a)
    fb = M(f"fb_{wall_rgb[0]:.2f}", floor_b)
    wall = M(f"wall_{wall_rgb[0]:.2f}_{wall_rgb[2]:.2f}", wall_rgb)
    wall_d = M(f"walld_{wall_rgb[0]:.2f}", shade(wall_rgb, -0.12))
    cap = M(f"cap_{wall_rgb[0]:.2f}", shade(wall_rgb, 0.10))
    post = M(f"post_{wall_rgb[0]:.2f}", shade(wall_rgb, -0.18))
    o = []
    o.append(box("slab", W / 2, D / 2, -0.10, W + 1.4, D + 1.6, 0.16, dark))
    for i in range(W):
        for j in range(D):
            o.append(box(
                "tile", i + 0.5, j + 0.5, -0.015, 0.92, 0.92, 0.04,
                fa if (i + j) % 2 == 0 else fb,
            ))
    o.append(box("wn", W / 2, D + 0.22, wall_h / 2, W + 0.9, 0.44, wall_h, wall))
    o.append(box("wnb", W / 2, D + 0.02, 0.16, W + 0.5, 0.10, 0.32, wall_d))
    o.append(box("wnc", W / 2, D + 0.22, wall_h - 0.06, W + 1.05, 0.50, 0.12, cap))
    o.append(box("ww", -0.22, D / 2, wall_h / 2, 0.44, D, wall_h, wall))
    o.append(box("we", W + 0.22, D / 2, wall_h / 2, 0.44, D, wall_h, wall))
    # south stubs leave a wide door so the camera sees in; props stay on the north side
    o.append(box("ws1", 1.15, -0.22, wall_h * 0.55, 2.3, 0.40, wall_h * 1.1, wall))
    o.append(box("ws2", W - 1.15, -0.22, wall_h * 0.55, 2.3, 0.40, wall_h * 1.1, wall))
    for x, y in ((-0.02, -0.02), (W + 0.02, -0.02), (-0.02, D + 0.02), (W + 0.02, D + 0.02)):
        o.append(box("post", x, y, wall_h / 2 + 0.1, 0.36, 0.36, wall_h + 0.25, post))
    return o


def mark_tiles(cells, rgb, key):
    mat = M(key, rgb)
    o = []
    for i, j in cells:
        o.append(box("mark", i + 0.5, j + 0.5, 0.02, 0.88, 0.88, 0.025, mat))
    return o


def bbox_of(objs=None):
    inf = 1e9
    mn = Vector((inf, inf, inf))
    mx = Vector((-inf, -inf, -inf))
    use = objs
    if use is None:
        use = [ob for ob in bpy.context.scene.objects if ob.type == "MESH"]
    for ob in use:
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            mn.x = min(mn.x, w.x)
            mn.y = min(mn.y, w.y)
            mn.z = min(mn.z, w.z)
            mx.x = max(mx.x, w.x)
            mx.y = max(mx.y, w.y)
            mx.z = max(mx.z, w.z)
    return mn, mx


def place_against(objs, anchor_x, anchor_y, yaw=0.0, axis="y", lift=0.0):
    if yaw:
        R = Matrix.Rotation(yaw, 4, "Z")
        for ob in objs:
            ob.matrix_world = R @ ob.matrix_world
    bpy.context.view_layer.update()
    mn, mx = bbox_of(objs)
    if axis == "y":
        dx = anchor_x - (mn.x + mx.x) / 2
        dy = anchor_y - mx.y
    elif axis == "-y":
        dx = anchor_x - (mn.x + mx.x) / 2
        dy = anchor_y - mn.y
    elif axis == "x":
        dx = anchor_x - mx.x
        dy = anchor_y - (mn.y + mx.y) / 2
    elif axis == "-x":
        dx = anchor_x - mn.x
        dy = anchor_y - (mn.y + mx.y) / 2
    else:
        raise ValueError(axis)
    dz = -mn.z + lift
    T = Matrix.Translation((dx, dy, dz))
    for ob in objs:
        ob.matrix_world = T @ ob.matrix_world
    return objs


def place_center(objs, cx, cy, yaw=0.0):
    if yaw:
        R = Matrix.Rotation(yaw, 4, "Z")
        for ob in objs:
            ob.matrix_world = R @ ob.matrix_world
    bpy.context.view_layer.update()
    mn, mx = bbox_of(objs)
    dx = cx - (mn.x + mx.x) / 2
    dy = cy - (mn.y + mx.y) / 2
    dz = -mn.z
    T = Matrix.Translation((dx, dy, dz))
    for ob in objs:
        ob.matrix_world = T @ ob.matrix_world
    return objs


def clear_meshes():
    for ob in list(bpy.data.objects):
        if ob.type == "MESH":
            mesh = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


def setup():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.compression = 15
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 8
    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("RoomWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.60, 0.56, 1)
    bg.inputs[1].default_value = 0.55

    cam_data = bpy.data.cameras.new("IsoCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 4
    cam = bpy.data.objects.new("IsoCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def sun(name, rot, energy, color):
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        light.color = color
        light.angle = math.radians(8)
        ob = bpy.data.objects.new(name, light)
        scene.collection.objects.link(ob)
        ob.rotation_euler = tuple(math.radians(a) for a in rot)

    sun("Key", (58, 0, 40), 4.4, (1.0, 0.96, 0.88))
    sun("Fill", (70, 8, 195), 1.8, (0.72, 0.80, 1.0))
    sun("Rim", (32, -12, -40), 1.3, (1.0, 0.90, 0.75))


def render_to(path, res=680, ortho=None, center=None):
    scene = bpy.context.scene
    if isinstance(res, tuple):
        scene.render.resolution_x, scene.render.resolution_y = res
    else:
        scene.render.resolution_x = scene.render.resolution_y = res
    bpy.context.view_layer.update()
    mn, mx = bbox_of()
    if center is None:
        center = (mn + mx) / 2
        center = Vector((center.x, center.y, center.z))
    else:
        center = Vector(center)
    extent = mx - mn
    if ortho is None:
        ortho = max(extent.x, extent.y, extent.z, 0.5) * 2.15
    cam = bpy.data.objects["IsoCam"]
    offset = Vector((1.05, -1.15, 0.78)).normalized()
    dist = max(extent.length, 3.0) * 2.4
    cam.location = center + offset * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = ortho
    cam.data.clip_start = 0.01
    cam.data.clip_end = 2000
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("SAVED", path, flush=True)


PROP_BUILDERS = [
    ("prop_linen_press", build_linen_press),
    ("prop_cheval_mirror", build_cheval_mirror),
    ("prop_washstand", build_washstand),
    ("prop_cradle", build_cradle),
    ("prop_dining_chair", build_dining_chair),
    ("prop_serving_cart", build_serving_cart),
    ("prop_wine_rack", build_wine_rack),
    ("prop_chapel_altar", build_chapel_altar),
    ("prop_lectern", build_lectern),
    ("prop_prayer_kneeler", build_prayer_kneeler),
    ("prop_arming_dummy", build_arming_dummy),
    ("prop_spinning_wheel", build_spinning_wheel),
    ("prop_portrait", build_portrait),
    ("prop_heater_shield", build_heater_shield),
    ("prop_cauldron", build_cauldron),
    ("prop_relic_rack", lambda: build_relic_rack("gold")),
    ("prop_spear_stand", build_spear_stand),
]

VAULT_BUILDERS = [
    ("vault_gothic_iron", lambda: build_vault("gothic")),
    ("vault_rose_marble", lambda: build_vault("rose")),
    ("vault_king_gold", lambda: build_vault("king")),
    ("vault_sky_crystal", lambda: build_vault("sky")),
]


def render_isolated(name, builder, folder):
    clear_meshes()
    builder()
    path = os.path.join(folder, f"{name}.png")
    render_to(path, res=720)
    return path


def layout_bedroom():
    W, D = 11, 9
    build_shell(W, D, (0.45, 0.32, 0.26), (0.55, 0.40, 0.28), (0.48, 0.34, 0.24))
    # Camera sits southeast, so only the north and west walls are visible.
    # Every prop's back touches one of those walls; nothing is parked on the hidden east wall.
    place_against(build_bed_scene(), 4.0, D - 0.02, axis="y")
    place_against(build_linen_press(), 0.04, 6.6, yaw=math.pi / 2, axis="-x")
    place_against(build_washstand(), 0.04, 3.5, yaw=math.pi / 2, axis="-x")
    place_against(build_cheval_mirror(), 8.3, D - 0.02, axis="y")
    place_center(build_cradle(), 2.6, 5.05)
    place_against(build_portrait(), 4.0, D - 0.02, axis="y", lift=1.55)
    place_center(build_figure(), 5.6, 1.7)
    place_center(build_rug(2.2, 1.5, (0.40, 0.16, 0.18)), 4.0, 5.4)


def layout_dining():
    W, D = 12, 10
    build_shell(W, D, (0.42, 0.30, 0.22), (0.50, 0.36, 0.24), (0.42, 0.30, 0.20))
    place_center(build_table_scene(), 6.0, 5.0)
    place_center(build_rug(3.4, 2.6, (0.38, 0.12, 0.14)), 6.0, 5.0)
    # pair of chairs, facing the table. Table is centered; north chair faces -Y (default), south faces +Y.
    place_center(build_dining_chair(), 6.0, 6.15, yaw=0.0)
    place_center(build_dining_chair(), 6.0, 3.85, yaw=math.pi)
    place_against(build_wine_rack(), 0.04, 6.8, yaw=math.pi / 2, axis="-x")
    place_against(build_serving_cart(), 0.04, 3.6, yaw=math.pi / 2, axis="-x")
    place_against(build_cauldron(), 1.5, D - 0.02, axis="y")
    place_against(build_portrait(), 7.4, D - 0.02, axis="y", lift=1.35)
    place_center(build_figure(), 6.0, 1.6)


def layout_chapel():
    W, D = 11, 10
    build_shell(W, D, (0.28, 0.26, 0.32), (0.38, 0.36, 0.40), (0.32, 0.30, 0.36))
    place_against(build_chapel_altar(), 5.5, D - 0.02, axis="y")
    place_against(build_lectern(), 2.0, D - 0.02, axis="y")
    # pair of kneelers flanking a 2-tile aisle, facing the altar (+Y)
    # Pair only, both north of the door jambs so neither sits inside the south wall.
    place_center(build_prayer_kneeler(), 3.5, 6.7, yaw=math.pi)
    place_center(build_prayer_kneeler(), 6.4, 6.7, yaw=math.pi)
    place_against(build_portrait(), 0.04, 4.2, yaw=math.pi / 2, axis="-x", lift=1.15)
    place_center(build_figure(), 5.5, 2.0)
    # aisle runner, non-blocking, stops short of the kneelers
    place_center(build_rug(1.3, 2.6, (0.32, 0.10, 0.16)), 5.5, 3.6)


def layout_armoury():
    W, D = 10, 8
    build_shell(W, D, (0.32, 0.30, 0.28), (0.40, 0.38, 0.34), (0.34, 0.32, 0.30))
    place_against(build_heater_shield(), 6.4, D - 0.02, axis="y", lift=0.85)
    place_against(build_spear_stand(), 0.04, 5.4, yaw=math.pi / 2, axis="-x")
    place_against(build_arming_dummy(), 2.3, D - 0.02, axis="y")
    place_center(build_figure(), 5.0, 2.0)
    place_center(build_rug(2.2, 1.4, (0.28, 0.14, 0.12)), 5.0, 4.4)


def layout_vault(theme, shell_rgb, fa, fb, rack_theme):
    W, D = 13, 11
    build_shell(W, D, shell_rgb, fa, fb, wall_h=3.05)
    place_against(build_vault(theme), 6.2, D - 0.02, axis="y")
    place_against(build_relic_rack(rack_theme), 0.04, 6.5, yaw=math.pi / 2, axis="-x")
    # guard space: empty darker tiles, south-east, off the center aisle
    # Guard mat on the open southwest floor, off the 2-tile aisle to the door. Empty on purpose.
    mark_tiles([(1, 2), (2, 2), (1, 3), (2, 3)], (0.45, 0.18, 0.14), f"guard_{theme}")
    place_center(build_figure(), 5.2, 2.2)


def render_layout(name, fn, res=(1100, 820), ortho=None, center=None):
    clear_meshes()
    fn()
    path = os.path.join(LAYOUT_DIR, f"{name}.png")
    render_to(path, res=res, ortho=ortho, center=center)
    return path


def main():
    argv = sys.argv
    only = None
    if "--" in argv:
        rest = argv[argv.index("--") + 1:]
        if "--only" in rest:
            only = rest[rest.index("--only") + 1]
    os.makedirs(PROP_DIR, exist_ok=True)
    os.makedirs(VAULT_DIR, exist_ok=True)
    os.makedirs(LAYOUT_DIR, exist_ok=True)
    setup()
    jobs_ok = False
    for name, fn in PROP_BUILDERS:
        if only and only not in name:
            continue
        render_isolated(name, fn, PROP_DIR)
        jobs_ok = True
    for name, fn in VAULT_BUILDERS:
        if only and only not in name:
            continue
        render_isolated(name, fn, VAULT_DIR)
        jobs_ok = True
    layouts = [
        ("layout_bedroom", layout_bedroom, 16.5, (5.5, 4.2, 1.1)),
        ("layout_dining", layout_dining, 18.0, (6.0, 4.6, 1.1)),
        ("layout_chapel", layout_chapel, 17.0, (5.5, 4.6, 1.2)),
        ("layout_armoury", layout_armoury, 15.0, (5.0, 3.8, 1.1)),
        ("layout_vault_gothic", lambda: layout_vault("gothic", (0.22, 0.20, 0.24), (0.28, 0.26, 0.30), (0.22, 0.20, 0.24), "gothic"), 20.0, (6.5, 5.0, 1.3)),
        ("layout_vault_white_rose", lambda: layout_vault("rose", (0.78, 0.74, 0.68), (0.80, 0.76, 0.70), (0.72, 0.68, 0.64), "rose"), 20.0, (6.5, 5.0, 1.3)),
        ("layout_vault_king", lambda: layout_vault("king", (0.30, 0.36, 0.48), (0.36, 0.40, 0.52), (0.28, 0.32, 0.44), "gold"), 20.0, (6.5, 5.0, 1.3)),
        ("layout_vault_sky", lambda: layout_vault("sky", (0.36, 0.52, 0.58), (0.42, 0.58, 0.64), (0.32, 0.48, 0.55), "sky"), 20.0, (6.5, 5.0, 1.3)),
    ]
    for name, fn, ortho, center in layouts:
        if only and only not in name:
            continue
        render_layout(name, fn, ortho=ortho, center=center)
        jobs_ok = True
    if not jobs_ok:
        raise SystemExit(f"nothing matched --only {only}")
    print("ALL_RENDERS_DONE", flush=True)


if __name__ == "__main__":
    main()
