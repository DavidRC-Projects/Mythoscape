"""Pet Emporium props: cages with the game's actual pets inside (content.PETS: cat, white
husky, skeleton, green dragon ...) + a pet bed.   blender -b -P blender_scripts/props_pets.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prop_parts import OLD_BASE_PX, new_kit, run, cage, bone  # noqa: E402


def game(k, kind, ids, drawer, cur_px, pet=None, note=""):
    k.meta["group"] = "pets"
    k.meta["game"] = {"kind": kind, "ids": ids, "drawer": drawer, "current_px_at_tile40": cur_px,
                      "footprint_tiles": [1, 1], "old_base_offset_px": OLD_BASE_PX.get(k.key), "pet_species": pet, "note": note}


def bowl(k, x, y, z, food="plank"):
    k.cyl((x, y, z), 0.07, 0.09, 0.05, "blue", segs=6)
    k.cyl((x, y, z + 0.045), 0.075, 0.075, 0.01, food, segs=6)


def eyes(k, x, y, z, sep, s=0.035):
    for sx in (-1, 1):
        k.box((x + sx * sep, y, z), (s, 0.015, s), "eye", jitter=False)


def cat(k, x, y, z, fur="fur_ginger"):
    """Sitting cat facing -Y, ~0.38 m tall."""
    k.box((x, y + 0.04, z + 0.1), (0.2, 0.3, 0.2), fur, taper=0.85)                # haunches
    k.box((x, y - 0.04, z + 0.2), (0.15, 0.14, 0.24), fur, taper=0.8)              # chest
    k.box((x, y - 0.07, z + 0.35), (0.17, 0.15, 0.13), fur)                        # head
    k.box((x, y - 0.15, z + 0.33), (0.07, 0.03, 0.05), "cream", jitter=False)     # muzzle
    k.box((x, y - 0.168, z + 0.345), (0.025, 0.01, 0.02), "pink", jitter=False)
    for sx in (-1, 1):
        k.cone((x + sx * 0.055, y - 0.07, z + 0.41), 0.04, 0.08, fur, segs=3)
        k.box((x + sx * 0.05, y - 0.1, z + 0.02), (0.05, 0.08, 0.04), "cream")    # paws
    eyes(k, x, y - 0.148, z + 0.37, 0.04, 0.03)
    for i, dz in enumerate((0.12, 0.22)):                                           # stripes
        k.box((x, y + 0.04, z + dz), (0.205, 0.2, 0.025), "red_d" if fur == "fur_ginger" else "fur_dark",
              jitter=False)
    k.tube(k.arc_pts((x + 0.08, y + 0.17, z + 0.03), (x + 0.26, y + 0.1, z + 0.05), (x + 0.18, y - 0.1, z + 0.08), 4),
           [0.03, 0.03, 0.028, 0.026, 0.02], fur, segs=4)


def husky(k, x, y, z):
    """Lying husky facing -Y (white/grey), ~0.35 m tall, 0.75 m long."""
    k.box((x, y + 0.06, z + 0.13), (0.3, 0.52, 0.24), "fur_white", taper=0.9)
    k.box((x, y + 0.08, z + 0.24), (0.26, 0.44, 0.04), "fur_grey", jitter=False)   # grey saddle
    k.box((x, y - 0.22, z + 0.24), (0.22, 0.2, 0.18), "fur_white")                 # head
    k.box((x, y - 0.22, z + 0.33), (0.2, 0.18, 0.03), "fur_grey", jitter=False)
    k.box((x, y - 0.35, z + 0.2), (0.11, 0.12, 0.09), "fur_white")                 # snout
    k.box((x, y - 0.415, z + 0.225), (0.05, 0.02, 0.04), "nose", jitter=False)
    for sx in (-1, 1):
        k.cone((x + sx * 0.07, y - 0.2, z + 0.33), 0.05, 0.11, "fur_grey", segs=3)
        k.box((x + sx * 0.09, y - 0.3, z + 0.04), (0.08, 0.2, 0.07), "fur_white")  # front paws
    k.box((x - 0.1, y - 0.312, z + 0.27), (0.03, 0.012, 0.025), "gem_b", jitter=False)   # blue eyes
    k.box((x + 0.1, y - 0.312, z + 0.27), (0.03, 0.012, 0.025), "gem_b", jitter=False)
    k.tube(k.arc_pts((x + 0.08, y + 0.3, z + 0.18), (x + 0.3, y + 0.3, z + 0.3), (x + 0.2, y + 0.05, z + 0.3), 4),
           [0.05, 0.06, 0.055, 0.045, 0.02], "fur_grey", segs=5)


def skeleton_pet(k, x, y, z):
    """Small sitting skeleton, ~0.5 m tall."""
    k.box((x, y, z + 0.06), (0.18, 0.12, 0.08), "bone")                             # pelvis
    k.tube([(x, y + 0.02, z + 0.1), (x, y + 0.03, z + 0.34)], [0.022, 0.022], "bone", segs=4)
    for j, zz in enumerate((0.18, 0.24, 0.3)):
        w = 0.13 - j * 0.0 + (0.02 if j == 1 else 0)
        k.tube(k.arc_pts((x - w, y + 0.0, z + zz), (x, y - 0.1, z + zz + 0.02), (x + w, y + 0.0, z + zz), 3),
               [0.014] * 4, "bone", segs=3)
    k.skull((x, y - 0.02, z + 0.36), 0.14, "bone", "black")
    for sx in (-1, 1):
        bone(k, (x + sx * 0.08, y, z + 0.05), (x + sx * 0.1, y - 0.2, z + 0.06), r=0.018)         # legs
        bone(k, (x + sx * 0.1, y - 0.2, z + 0.06), (x + sx * 0.1, y - 0.24, z + 0.01), r=0.016)
        bone(k, (x + sx * 0.15, y, z + 0.32), (x + sx * 0.19, y - 0.1, z + 0.18), r=0.016)         # arms
    k.box((x + 0.14, y - 0.22, z + 0.02), (0.14, 0.05, 0.03), "bone")               # chew bone


def dragon_hatchling(k, x, y, z, body="scale_g", belly="scale_gl"):
    """Green dragon pet (hatchling) sitting on straw, wings half open, ~0.55 m tall."""
    k.rock((x, y + 0.05, z + 0.14), (0.17, 0.2, 0.15), body, subdiv=1, rough=0.08, rot=(0, 0, 0))
    k.box((x, y - 0.1, z + 0.2), (0.14, 0.08, 0.2), belly, taper=0.8)
    k.tube([(x, y - 0.02, z + 0.22), (x, y - 0.08, z + 0.36), (x, y - 0.14, z + 0.42)], [0.07, 0.06, 0.05],
           body, segs=5)
    k.box((x, y - 0.2, z + 0.45), (0.14, 0.18, 0.1), body)                         # head
    k.box((x, y - 0.3, z + 0.43), (0.1, 0.08, 0.07), body, taper=0.8)               # snout
    for sx in (-1, 1):
        k.cone((x + sx * 0.05, y - 0.14, z + 0.49), 0.025, 0.12, "bone", segs=4, rot=(-35, sx * 15, 0))
        k.box((x + sx * 0.05, y - 0.29, z + 0.475), (0.03, 0.012, 0.025), "gold", jitter=False)
        # wings: two-triangle membranes with a bone strut
        wx = x + sx * 0.1
        k.add([(wx, y + 0.02, z + 0.3), (wx + sx * 0.28, y + 0.12, z + 0.5), (wx + sx * 0.3, y + 0.16, z + 0.2),
               (wx + sx * 0.12, y + 0.1, z + 0.14)], [(0, 1, 2, 3), (3, 2, 1, 0)], belly)
        k.tube([(wx, y + 0.02, z + 0.3), (wx + sx * 0.28, y + 0.12, z + 0.5)], [0.018, 0.012], body, segs=3)
        k.box((x + sx * 0.08, y - 0.06, z + 0.03), (0.07, 0.12, 0.06), body)         # feet
    for i in range(4):                                                                # back spikes
        k.cone((x, y + 0.02 + i * 0.07, z + 0.3 - i * 0.05), 0.025, 0.07, "bone", segs=3)
    k.tube(k.arc_pts((x, y + 0.2, z + 0.08), (x + 0.3, y + 0.25, z + 0.04), (x + 0.28, y - 0.05, z + 0.03), 4),
           [0.05, 0.045, 0.035, 0.022, 0.0], body, segs=4)
    for (ex, ey) in ((-0.22, 0.1), (-0.25, -0.02)):                                  # egg shell bits
        k.rock((x + ex, y + ey, z + 0.04), (0.06, 0.05, 0.04), "egg", subdiv=1, rough=0.3)


def cage_prop(key, title, species, pet_fn, seed, w=0.95, d=0.75, h=0.78, bar="steel", roof="wood",
              extra=None, pet_scale=1.3):
    k = new_kit(key, seed=seed, title=title)
    zf, w, d = cage(k, 0, 0, w=w, d=d, h=h, roof=roof, bar=bar)
    mark = len(k.verts)
    pet_fn(k, zf)
    k.transform_since(mark, origin=(0, 0.0, zf), scale=pet_scale)   # pets read bigger than life
    if extra:
        extra(k, zf)
    # price tag hanging on the front
    k.box((-0.26, -d / 2 - 0.05, zf + h * 0.25), (0.16, 0.012, 0.1), "cream", rot=(0, 8, 0), jitter=False)
    k.collider("cage", (0, 0, (zf + h + 0.3) / 2), (w + 0.15, d + 0.15, zf + h + 0.3))
    k.interact((0, -d / 2 - 0.6, 1.0), (1.3, 1.0, 2.0))
    game(k, "pet_cage", ["pet_cage_a", "pet_cage_b", "(one sprite per pet)"], "draw_furniture -> draw_pet_cage (x0.62)",
         (32, 32), species, "click -> existing buy/adopt pet flow")
    k.finish()


def cage_cat():
    def pet(k, z):
        cat(k, -0.06, 0.02, z)
        bowl(k, 0.2, -0.1, z)
    cage_prop("cage_cat", "Cat Cage", "cat", pet, 51)


def cage_husky():
    def pet(k, z):
        husky(k, 0.0, 0.05, z)
    cage_prop("cage_husky", "White Husky Cage", "husky", pet, 52, w=1.15, d=0.95, h=0.72, pet_scale=1.12)


def cage_skeleton():
    def pet(k, z):
        skeleton_pet(k, 0.0, 0.05, z)
    cage_prop("cage_skeleton", "Skeleton Pet Cage", "skeleton_pet", pet, 53, bar="iron", roof="slate", h=0.82,
              pet_scale=1.25)


def cage_dragon():
    def pet(k, z):
        dragon_hatchling(k, 0.0, 0.05, z)
    cage_prop("cage_dragon", "Dragon Hatchling Cage", "dragon_pet (green; recolour for crimson/frost/shadow/mythic)",
              pet, 54, w=1.1, d=0.85, h=0.85, bar="iron", roof="red_d", pet_scale=1.2)


def pet_bed():
    k = new_kit("pet_bed", seed=55, title="Pet Bed")
    n = 10
    ring = [(math.cos(2 * math.pi * i / n) * 0.42, math.sin(2 * math.pi * i / n) * 0.34, 0.12) for i in range(n + 1)]
    k.tube(ring, [0.12] * (n + 1), "red", segs=5)
    k.cyl((0, 0, 0), 0.44, 0.44, 0.06, "red_d", segs=10, scale=(1, 0.8, 1))
    k.cyl((0, 0, 0.06), 0.34, 0.33, 0.07, "cream", segs=10, scale=(1, 0.8, 1))
    k.rock((0.2, -0.05, 0.19), (0.07, 0.07, 0.07), "gem_b", subdiv=1, rough=0.05)     # toy ball
    k.box((-0.15, 0.05, 0.15), (0.2, 0.05, 0.035), "bone")                           # chew bone
    for sx in (-0.1, 0.1):
        k.rock((-0.15 + sx, 0.05, 0.15), (0.04, 0.04, 0.03), "bone", subdiv=1, rough=0.05)
    k.collider("bed", (0, 0, 0.12), (0.95, 0.8, 0.25))
    game(k, "pet_bed", ["pet_bed_a", "pet_bed_b"], "draw_furniture -> draw_pet_bed", (34, 14))
    k.finish()


BUILDERS = {"cage_cat": cage_cat, "cage_husky": cage_husky, "cage_skeleton": cage_skeleton,
            "cage_dragon": cage_dragon, "pet_bed": pet_bed}

if __name__ == "__main__":
    run(BUILDERS)
