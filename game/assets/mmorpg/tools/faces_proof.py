"""Proof sheets for the chosen face (David, 29 Oct 2026). Writes PNGs to the folder given (default ~/grokbot_tmp/proofs/faces).
  faces_<sex>.png       one face on every outfit + 3 armour tiers (helmet off / on), s and e
  face_options_<sex>.png every face option on the starter figure
  hair_tint.png         hair colours on brown / red / gold clothes
  partial_armour.png    outfit -> chest only / legs only (default base) -> armour off (outfit back)
Run: nice python3 tools/faces_proof.py [out_dir]
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client"))
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))
import face_layer  # noqa: E402
import player_hd_client as P  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/grokbot_tmp/proofs/faces")
os.makedirs(OUT, exist_ok=True)
TILE = 150
CELL = (int(TILE * 1.25), int(TILE * 2.3))
FONT = pygame.font.SysFont("helvetica", 15)
OUTFITS = {
    "male": [("Villager", "villager_coat"), ("Squire", "squire_coat"), ("Noble Lord", "noble_lord_coat"),
             ("Count", "count_coat"), ("Champion", "kings_champion_coat"), ("Prince", "prince_consort_coat"),
             ("King", "king_coat"), ("Ember Lord", "set:set_fire_m"), ("Tide", "set:set_water_m")],
    "female": [("Village Lady", "village_lady_gown"), ("Noble Lady", "noble_lady_gown"), ("Countess", "countess_gown"),
               ("Courtier", "court_gown_gown"), ("Favourite", "royal_favourite_gown"),
               ("Princess", "princess_consort_gown"), ("Queen", "queen_gown"), ("Ember Court", "set:set_fire_f"),
               ("Tide", "set:set_water_f")],
}
TIERS = ("bronze", "mithril", "eclipse")


def look(sex, outfit, face, hair="dark_brown"):
    a = P.get_default_appearance(sex, starter=False)
    a.update(face=face, hair_colour=hair, skin_tone="tone_3")
    if outfit.startswith("set:"):
        a["set"] = outfit[4:]
    else:
        a["outfit"] = outfit
    return a


def cell(sex, a, eq=None, facing=1, label="", anim="idle", t=0.0):
    s = pygame.Surface(CELL, pygame.SRCALPHA)
    s.fill((96, 118, 92, 255))
    P.draw_player(s, sex, a, CELL[0] // 2, int(CELL[1] * 0.93), TILE, t, anim=anim, facing=facing, equipment=eq)
    if label:
        s.blit(FONT.render(label, True, (255, 255, 255)), (4, 4))
    return s


def sheet(cells, cols, name, title):
    rows = (len(cells) + cols - 1) // cols
    out = pygame.Surface((cols * CELL[0], rows * CELL[1] + 26))
    out.fill((40, 44, 40))
    out.blit(FONT.render(title, True, (240, 220, 160)), (6, 5))
    for i, c in enumerate(cells):
        out.blit(c, ((i % cols) * CELL[0], 26 + (i // cols) * CELL[1]))
    p = os.path.join(OUT, name)
    pygame.image.save(out, p)
    print(p)


def armour(tier, helm):
    eq = {"body": f"{tier}_body", "legs": f"{tier}_legs"}
    if helm:
        eq["helmet"] = f"{tier}_helmet"
    return eq


for sex, face in (("male", "noble_lord"), ("female", "village_lady")):
    cells = []
    for facing in ("s", "e"):
        fv = 0 if facing == "s" else 1
        for name, oid in OUTFITS[sex]:
            cells.append(cell(sex, look(sex, oid, face), facing=fv, label=f"{name} {facing}"))
        for tier in TIERS:
            for helm in (False, True):
                cells.append(cell(sex, look(sex, OUTFITS[sex][0][1], face), armour(tier, helm), facing=fv,
                                  label=f"{tier}{' +helm' if helm else ''} {facing}"))
    sheet(cells, 15, f"faces_{sex}.png", f"{sex}: face '{face}' on every outfit and 3 armour tiers (helmet off / on)")
    opts = [cell(sex, look(sex, OUTFITS[sex][0][1], f["id"]), label=f["name"]) for f in face_layer.faces(sex)]
    opts += [cell(sex, look(sex, OUTFITS[sex][3][1], f["id"]), label=f["name"]) for f in face_layer.faces(sex)]
    sheet(opts, len(face_layer.faces(sex)), f"face_options_{sex}.png", f"{sex}: every face option (starter / {OUTFITS[sex][3][0]})")
    walk = [cell(sex, look(sex, oid, face), facing=1, anim="walk", t=i * 0.11, label=f"walk {i}") for i, (n, oid) in
            enumerate(OUTFITS[sex][:6])]
    walk += [cell(sex, look(sex, OUTFITS[sex][0][1], face), facing=fv, anim="melee", label=f"swing {fv}",
                  t=0.0) for fv in (0, 1, -1)]
    sheet(walk, 9, f"anims_{sex}.png", f"{sex}: walk frames and a swing keep the same head")

hair_cells = []
for sex, outs in (("male", [("brown", "villager_coat"), ("red", "set:set_fire_m"), ("gold", "kings_champion_coat")]),
                  ("female", [("brown", "village_lady_gown"), ("red", "set:set_fire_f"), ("gold", "royal_favourite_gown")])):
    for cloth, oid in outs:
        for hc in ("black", "copper", "honey", "ash_grey", "bright_red", "light_blue"):
            hair_cells.append(cell(sex, look(sex, oid, face_layer.default_face(sex), hc), label=f"{cloth} / {hc}"))
sheet(hair_cells, 6, "hair_tint.png", "hair colour on brown / red / gold clothes: only the hair changes")

pa = []
for sex in ("male", "female"):
    o = OUTFITS[sex][2][1]
    face = face_layer.default_face(sex)
    pa += [cell(sex, look(sex, o, face), label="outfit"),
           cell(sex, look(sex, o, face), {"body": "steel_body"}, label="chest only"),
           cell(sex, look(sex, o, face), {"legs": "steel_legs"}, label="legs only"),
           cell(sex, look(sex, o, face), armour("steel", True), label="full steel"),
           cell(sex, look(sex, o, face), {}, label="armour off")]
sheet(pa, 5, "partial_armour.png", "partial armour shows the default base; the outfit comes back when it is off")
