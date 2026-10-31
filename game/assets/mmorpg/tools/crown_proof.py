"""Crown proofs (David, 29 Oct 2026): crown-free King / Queen faces and crowns as their own layer.
  royal_faces_<sex>.png   the royal face on outfits + armour tiers, crown off / on, facings s e w n
  crown_any_face_<sex>.png  the crown on every face (King's on male faces, Queen's on female)
Run: nice python3 tools/crown_proof.py [out_dir]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [sys.argv[0]] + sys.argv[1:]
src = open(os.path.join(HERE, "faces_proof.py")).read().split("for sex, face in")[0]
exec(compile(src.replace("os.path.dirname(os.path.abspath(__file__))", repr(HERE)), "faces_proof", "exec"))

ROYAL = {"male": ("king", "king_kings_crown"), "female": ("queen", "queen_queens_crown")}
FACINGS = ((0, "s"), (1, "e"), (-1, "w"), ("n", "n"))
for sex, (face, crown) in ROYAL.items():
    cells = []
    picks = [o for o in OUTFITS[sex] if o[0] in ("Villager", "Village Lady", "King", "Queen", "Noble Lord",
                                                 "Countess", "Ember Lord", "Ember Court")]
    for with_crown in (False, True):
        for fv, fl in FACINGS:
            for name, oid in picks:
                a = look(sex, oid, face)
                a["head"] = crown if with_crown else None
                cells.append(cell(sex, a, facing=fv, label=f"{name} {fl} {'crown' if with_crown else 'bare'}"))
            for tier in ("bronze", "eclipse"):
                a = look(sex, picks[0][1], face)
                a["head"] = crown if with_crown else None
                cells.append(cell(sex, a, armour(tier, False), facing=fv,
                                  label=f"{tier} {fl} {'crown' if with_crown else 'bare'}"))
            a = look(sex, picks[0][1], face)
            a["head"] = crown if with_crown else None
            cells.append(cell(sex, a, armour("mithril", True), facing=fv, label=f"mithril+helm {fl}"))
    sheet(cells, len(picks) + 3, f"royal_faces_{sex}.png",
          f"{face} face: no crown (top half) / crown layer (bottom half); helmet hides the crown")
    cells = []
    for fv, fl in FACINGS[:3] + FACINGS[3:]:
        for fid in face_layer.face_ids(sex):
            a = look(sex, OUTFITS[sex][0][1], fid)
            a["head"] = crown
            cells.append(cell(sex, a, facing=fv, label=f"{fid} {fl}"))
    sheet(cells, len(face_layer.face_ids(sex)), f"crown_any_face_{sex}.png", f"{crown} on every {sex} face")
