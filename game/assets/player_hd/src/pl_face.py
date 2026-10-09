"""Face polish: per-pixel shader masks from a rest-position attribute (liner, lid crease, socket, lower lid,
nose/philtrum/under-lip shadows, cheek contour, male stubble) + no-glow eyes + stronger brows."""
import bpy
from mathutils import Vector


class N:
    """Tiny shader-math expression builder."""
    nt = None

    def __init__(self, sock): self.s = sock

    @staticmethod
    def c(v): return v if isinstance(v, N) else N(None if v is None else float(v))

    def _op(self, op, o=None, rev=False):
        m = N.nt.nodes.new("ShaderNodeMath"); m.operation = op
        a, b = (o, self) if rev else (self, o)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            x = x if isinstance(x, N) else N(float(x))
            if isinstance(x.s, float):
                m.inputs[i].default_value = x.s
            else:
                N.nt.links.new(x.s, m.inputs[i])
        return N(m.outputs[0])
    def __add__(s, o): return s._op("ADD", o)
    __radd__ = __add__
    def __sub__(s, o): return s._op("SUBTRACT", o)
    def __rsub__(s, o): return s._op("SUBTRACT", o, rev=True)
    def __mul__(s, o): return s._op("MULTIPLY", o)
    __rmul__ = __mul__
    def __truediv__(s, o): return s._op("DIVIDE", o)
    def abs(s): return s._op("ABSOLUTE")
    def mx(s, o): return s._op("MAXIMUM", o)
    def mn(s, o): return s._op("MINIMUM", o)
    def clamp(s): return s.mx(0.0).mn(1.0)


def soft(x, w):
    """1 at x<=0 falling smoothly to 0 at x>=w (x already >=0)."""
    u = (x / w).clamp()
    return 1.0 - u * u * (3.0 - u * 2.0)


def inside(x, lo, hi, f):
    return soft((lo - x).mx(0.0), f) * soft((x - hi).mx(0.0), f)


def enhance(ctx, face):
    body, eyes, s, kind = ctx.body, ctx.eyes, ctx.s, ctx.kind
    male = kind == "male"
    me = body.data
    mw = body.matrix_world
    if "restP" not in me.attributes:
        a = me.attributes.new("restP", "FLOAT_VECTOR", "POINT")
        for i, v in enumerate(me.vertices):
            a.data[i].vector = mw @ v.co
    E = [(e.matrix_world.translation.copy(), 0.36 * max(e.dimensions) / 2) for e in eyes]   # visible lid opening ~0.36 x eyeball radius
    nose, mouth, ez = face["nose"], face["mouth"], face["eye_z"]
    for mat in ctx.skin_mats.values():
        nt = mat.node_tree; N.nt = nt
        b = nt.nodes["Principled BSDF"]
        lk = b.inputs["Base Color"].links[0]; src = lk.from_socket; nt.links.remove(lk)
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "restP"
        sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(at.outputs["Vector"], sp.inputs[0])
        X, Y, Z = N(sp.outputs[0]), N(sp.outputs[1]), N(sp.outputs[2])
        liner = N(None); shade = N(None)
        liner = None; shade = None
        def acc(cur, v): return v if cur is None else cur.mx(v)
        for ec, er in E:
            sx = 1.0 if ec.x > 0 else -1.0
            dx = (X - ec.x) * sx; dz = Z - ec.z; dy = Y - ec.y
            front = soft((dy - (-0.2 * er)).mx(0.0), 0.5 * er)          # only the face-front of the eye region
            ax = (dx / (1.25 * er)); ax2 = ax * ax
            arc = 0.30 * er + (1.0 - ax2).mx(0.0) * (0.40 * er)
            wid = 1.25 * er if male else 1.45 * er
            lid = soft((dz - arc).abs(), (0.22 if male else 0.28) * er) * inside(dx, -1.15 * er, wid, 0.15 * er) * front
            liner = acc(liner, lid * (0.80 if male else 0.95))
            lower = soft((dz - (-0.36 * er + ax2 * 0.12 * er)).abs(), 0.14 * er) * inside(dx, -0.9 * er, 1.1 * er, 0.2 * er) * front
            liner = acc(liner, lower * 0.35)
            crease = soft((dz - (arc + 0.50 * er)).abs(), 0.30 * er) * inside(dx, -1.0 * er, 1.2 * er, 0.3 * er) * front
            ex2 = (dx / (1.7 * er)); ez2 = ((dz - 0.1 * er) / (1.35 * er))
            sock = soft((ex2 * ex2 + ez2 * ez2).mx(0.0), 1.0) * front
            shade = acc(shade, crease * 0.40 + sock * 0.22)
        AX = X.abs()
        # nose sides + philtrum + under-lip + nostril
        nside = inside(AX, 0.009 * s, 0.019 * s, 0.004 * s) * inside(Z, mouth.z + 0.016 * s, ez - 0.012 * s, 0.006 * s)
        phil = soft(((X / (0.011 * s)) * (X / (0.011 * s)) + ((Z - (nose.z - 0.011 * s)) / (0.005 * s)) * ((Z - (nose.z - 0.011 * s)) / (0.005 * s))), 1.0)
        ulip = soft(((X / (0.013 * s)) * (X / (0.013 * s)) + ((Z - (mouth.z - 0.011 * s)) / (0.0045 * s)) * ((Z - (mouth.z - 0.011 * s)) / (0.0045 * s))), 1.0)
        mline = soft((Z - mouth.z).abs(), 0.0012 * s) * soft((AX - 0.0).mx(0.0) / (0.021 * s), 1.0)   # mouth corner line
        ck = (AX - 0.050 * s) / (0.020 * s); cz = (Z - (mouth.z + 0.018 * s)) / (0.011 * s)
        cheek = soft((ck * ck + cz * cz), 1.0)
        shade = shade.mx(nside * 0.14).mx(phil * 0.20).mx(ulip * 0.20).mx(cheek * (0.16 if male else 0.08)).mx(mline * 0.35)
        dark = nt.nodes.new("ShaderNodeMix"); dark.data_type = "RGBA"; dark.blend_type = "MULTIPLY"
        nt.links.new(shade.clamp().s, dark.inputs["Factor"]); nt.links.new(src, dark.inputs[6])
        dark.inputs[7].default_value = (0.52, 0.36, 0.32, 1)
        out = dark.outputs[2]
        if male:
            # stubble: jaw / chin / upper lip, broken up with fine noise
            st = inside(Z, mouth.z - 0.062 * s, mouth.z + 0.011 * s, 0.006 * s) * inside(AX, -1.0, 0.060 * s, 0.010 * s) \
                * soft((Y - (mouth.y + 0.045 * s)).mx(0.0), 0.02 * s)
            lipm = soft(((X / (0.024 * s)) * (X / (0.024 * s)) + ((Z - mouth.z) / (0.0075 * s)) * ((Z - mouth.z) / (0.0075 * s))), 1.0)
            nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 900; nt.links.new(at.outputs["Vector"], nz.inputs["Vector"])
            stub = st * (1.0 - lipm) * (0.30 + N(nz.outputs["Fac"]) * 0.25)
            sm = nt.nodes.new("ShaderNodeMix"); sm.data_type = "RGBA"; sm.blend_type = "MULTIPLY"
            nt.links.new(stub.clamp().s, sm.inputs["Factor"]); nt.links.new(out, sm.inputs[6]); sm.inputs[7].default_value = (0.55, 0.50, 0.50, 1)
            out = sm.outputs[2]
        lm = nt.nodes.new("ShaderNodeMix"); lm.data_type = "RGBA"
        nt.links.new(liner.clamp().s, lm.inputs["Factor"]); nt.links.new(out, lm.inputs[6]); lm.inputs[7].default_value = (0.06, 0.035, 0.03, 1)
        nt.links.new(lm.outputs[2], b.inputs["Base Color"])
        b.inputs["Subsurface Weight"].default_value = 0.7
        b.inputs["Subsurface Scale"].default_value = 0.012
    # eyes: kill the fairy glow, deepen iris contrast
    for e in eyes:
        for m in e.data.materials:
            if not m or not m.node_tree:
                continue
            bb = m.node_tree.nodes.get("Principled BSDF")
            if bb:
                for l in list(bb.inputs["Emission Strength"].links):
                    m.node_tree.links.remove(l)
                bb.inputs["Emission Strength"].default_value = 0.0
            for n in m.node_tree.nodes:
                if n.type == "VALTORGB":
                    for el in n.color_ramp.elements:
                        if min(el.color[:3]) > 0.6:
                            el.color = (0.60, 0.58, 0.58, 1)
