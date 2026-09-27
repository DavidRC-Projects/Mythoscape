"""Goblins: grunt (melee) and shaman (magic). ~1.1 m tall, hunched, big
head, long ears/nose, long arms, bandy legs."""
from ..mesh_builder import Rig
from ..registry import MonsterStats, register
from .parts import aim, biped_legs, seg

GRUNT = {
    "skin": "#6e7b3c", "skin_dark": "#57622f", "leather": "#6b4c30",
    "leather_dark": "#47331f", "iron": "#6d7072", "bone": "#d3c8a6",
    "eye": "#d8b93c", "wood": "#6f5232", "mouth": "#2e2418",
}
SHAMAN = {
    "skin": "#5d6f45", "skin_dark": "#48583a", "robe": "#6a3a2c",
    "robe_dark": "#4b271e", "leather": "#5a4630", "bone": "#d9d0b3",
    "eye": "#e0c34a", "wood": "#5b4128", "feather": "#8a7a5a",
    "orb": "#9cc24e", "mouth": "#2e2418",
}


def _goblin_head(rig, p, hood=False):
    h = rig.mesh("head")
    h.sphere(0.15, p["skin"], pos=(0, 0.02, 0.12), scale=(1.12, 1.0, 0.95), rings=4, segments=7)
    h.box((0.23, 0.06, 0.05), p["skin_dark"], pos=(0, 0.13, 0.17), hpr=(0, -10, 0))  # brow
    h.cone((0, 0.15, 0.12), (0, 0.29, 0.05), 0.045, p["skin_dark"], segments=5)       # nose
    h.box((0.20, 0.14, 0.07), p["skin"], pos=(0, 0.08, 0.015), taper=(1.0, 1.0))       # jaw
    h.box((0.12, 0.012, 0.014), p["mouth"], pos=(0, 0.151, 0.045))                       # mouth slit
    for sx in (-1, 1):
        h.box((0.035, 0.02, 0.03), p["eye"], pos=(sx * 0.06, 0.148, 0.125))           # eyes
        h.cone((sx * 0.055, 0.14, 0.04), (sx * 0.065, 0.15, 0.10), 0.018, p["bone"], segments=4)  # tusks
        if not hood:
            h.cone((sx * 0.14, 0.0, 0.14), (sx * 0.36, -0.10, 0.24), 0.05, p["skin"],
                   segments=4, squash=0.35)                                           # ears
        else:
            h.cone((sx * 0.14, 0.02, 0.12), (sx * 0.33, -0.06, 0.18), 0.045, p["skin"],
                   segments=4, squash=0.35)
    return h


def _goblin_body(name, p, shaman=False):
    rig = Rig(name)
    rig.joint("hips", "root", (0, 0, 0.50))
    leg_col = p["skin"]
    biped_legs(rig, "hips", 0.11, -0.02, 0.24, 0.23, 0.06, 0.05, leg_col,
               p["leather_dark"] if not shaman else p["leather"], knee_bend=12)
    # torso, leaning forward (negative pitch = top tips toward +Y)
    rig.joint("torso", "hips", (0, 0, 0.02), (0, -16, 0))
    t = rig.mesh("torso")
    t.sphere(0.18, p["skin"], pos=(0, 0.02, 0.17), scale=(1.05, 0.95, 0.95), rings=4, segments=7)
    t.box((0.36, 0.22, 0.20), p["skin_dark"] if not shaman else p["robe"],
          pos=(0, 0.0, 0.31), taper=(1.12, 1.0))
    if not shaman:
        t.box((0.40, 0.28, 0.14), p["leather"], pos=(0, 0.02, 0.02), taper=(0.95, 0.95))  # kilt
        t.box((0.41, 0.29, 0.04), p["leather_dark"], pos=(0, 0.02, 0.10))                    # belt
        t.box((0.07, 0.03, 0.05), p["iron"], pos=(0, 0.17, 0.10))                            # buckle
        t.box((0.15, 0.20, 0.08), p["iron"], pos=(0.20, 0.0, 0.40), hpr=(0, 0, -25))        # pauldron
        t.box((0.30, 0.02, 0.05), p["leather_dark"], pos=(0.02, 0.115, 0.26), hpr=(0, 0, 35))  # strap
    else:
        # ragged robe skirt down to the knees + rope belt + bone necklace
        t.box((0.44, 0.34, 0.36), p["robe"], pos=(0, 0.0, -0.08), taper=(0.80, 0.78))
        t.box((0.42, 0.33, 0.04), p["leather"], pos=(0, 0.02, 0.10))
        for i, x in enumerate((-0.10, -0.04, 0.02, 0.08)):
            t.cone((x, 0.125, 0.36), (x * 1.1, 0.14, 0.31), 0.016, p["bone"], segments=4)
    # head
    rig.joint("head", "torso", (0, 0.05, 0.40), (0, 22, 0))
    _goblin_head(rig, p, hood=shaman)
    if shaman:
        h = rig.mesh("head")
        h.box((0.37, 0.33, 0.25), p["robe_dark"], pos=(0, -0.05, 0.155), taper=(0.62, 0.7))  # hood
        h.cone((0, -0.16, 0.22), (0, -0.34, 0.06), 0.09, p["robe_dark"], segments=5)          # hood tail
        for sx in (-1, 1):
            h.cone((sx * 0.06, -0.02, 0.30), (sx * 0.22, -0.16, 0.50), 0.03,
                   p["feather"], segments=3, squash=0.3)
    # arms: shoulder -> elbow -> hand
    arm_col = p["skin"]
    for side, sx in (("l", -1), ("r", 1)):
        seg(rig, f"{side}_arm", "torso", (sx * 0.21, 0.02, 0.34), (0, 0, -0.25),
            0.058, 0.045, p["robe"] if shaman else arm_col, hpr=(0, 18, sx * -10))
        m = seg(rig, f"{side}_forearm", f"{side}_arm", (0, 0, -0.25), (0, 0, -0.24),
                0.047, 0.04, arm_col, hpr=(0, 30, 0))
        m.box((0.085, 0.08, 0.09), p["skin_dark"], pos=(0, 0.01, -0.28))
        if shaman:
            m.box((0.11, 0.11, 0.08), p["robe_dark"], pos=(0, 0, -0.03))  # sleeve cuff
        rig.joint(f"{side}_hand", f"{side}_forearm", (0, 0.01, -0.28))
    if not shaman:
        # crude spiked club in the right hand, held forward and up
        rig["r_arm"].set_hpr(0, 25, -35)      # club arm out, ready to swing
        rig["r_forearm"].set_hpr(0, 45, 0)
        aim(rig, "r_hand", (0.85, 0.35, 0.6))
        c = rig.mesh("r_hand")
        c.tube((0, 0, -0.10), (0, 0, 0.30), 0.03, 0.065, p["wood"], segments=5)
        c.tube((0, 0, 0.30), (0, 0, 0.44), 0.07, 0.05, p["wood"], segments=5)
        for a, b in (((0.06, 0, 0.36), (0.12, 0, 0.38)), ((-0.06, 0, 0.33), (-0.12, 0.0, 0.34)),
                     ((0, 0.06, 0.40), (0, 0.12, 0.42)), ((0, -0.06, 0.30), (0, -0.12, 0.31))):
            c.cone(a, b, 0.018, p["iron"], segments=4)
        # small round hide shield on the left forearm
        s = rig.mesh("l_forearm")
        s.tube((-0.06, 0.0, -0.12), (-0.10, 0.0, -0.12), 0.16, 0.15, p["leather"], segments=7)
        s.cone((-0.10, 0, -0.12), (-0.14, 0, -0.12), 0.05, p["iron"], segments=5)
    else:
        # gnarled staff topped with a skull and a glowing orb
        rig["l_arm"].set_hpr(0, 10, 28)       # arm out to the side
        rig["l_forearm"].set_hpr(0, 45, -10)
        rig["l_hand"].set_hpr(0, -39, -18)    # cancel parent tilt -> staff upright
        st = rig.mesh("l_hand")
        st.tube((0, 0, -0.62), (0, 0, 0.42), 0.022, 0.028, p["wood"], segments=5)
        st.tube((0, 0, 0.42), (0.03, 0.0, 0.50), 0.028, 0.02, p["wood"], segments=5)
        st.sphere(0.075, p["bone"], pos=(0, 0.02, 0.56), scale=(1, 1.1, 0.95), rings=3, segments=6)
        st.box((0.028, 0.01, 0.025), "#1e1a14", pos=(-0.028, 0.10, 0.575))
        st.box((0.028, 0.01, 0.025), "#1e1a14", pos=(0.028, 0.10, 0.575))
        for a in (-1, 1):
            st.cone((a * 0.03, -0.02, 0.60), (a * 0.10, -0.10, 0.72), 0.018, p["bone"], segments=4)
        rig.joint("staff_orb", "l_hand", (0, 0.0, 0.68))
        rig.mesh("staff_orb").sphere(0.045, p["orb"], rings=3, segments=6)
        rig["r_arm"].set_hpr(0, 60, -25)   # casting pose
        rig["r_forearm"].set_hpr(0, 40, 0)
    return rig


@register("goblin_grunt", "Goblin Grunt", "goblin", "small", "biped",
          MonsterStats(5, 12, "melee (crush)", 2, 2.4, "stab / fire spells",
                       aggressive=True, notes="Travels in packs of 3-5."),
          GRUNT, 1.15)
def build_goblin_grunt():
    return _goblin_body("goblin_grunt", GRUNT).bake()


@register("goblin_shaman", "Goblin Shaman", "goblin", "small", "biped",
          MonsterStats(13, 22, "magic (earth bolt)", 4, 3.0, "melee (slash)",
                       aggressive=True, notes="Heals nearby goblins for 2 every 10 s."),
          SHAMAN, 1.35)
def build_goblin_shaman():
    rig = _goblin_body("goblin_shaman", SHAMAN, shaman=True).bake()
    rig["staff_orb"].set_light_off()   # unlit = reads as glowing
    return rig
