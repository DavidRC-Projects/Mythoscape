import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from render_common import *
OUT = sys.argv[1]
T = 40
dirs = [("front", "down"), (1, "right"), ("back", "up"), (-1, "left")]
CAST = [("Player (M)", {}, "male", (70, 210, 90), False),
        ("esteph (F)", {}, "female", (168, 92, 118), False),
        ("Lira / NPC", {}, "female", (60, 150, 70), False),
        ("Eclipse set", {"body": "eclipse_body", "legs": "eclipse_legs", "helmet": "eclipse_helmet", "weapon": "eclipse_cleaver", "shield": "eclipse_shield"}, "male", (70, 210, 90), False),
        ("Robed NPC", {}, "male", (90, 70, 130), True)]
cw, ch = 96, 140
S = pygame.Surface((110 + len(dirs) * cw * 2 + 20, 60 + len(CAST) * ch)); tiles(S)
label(S, "OLD", 110 + 2 * cw - 20, 6, (200, 200, 200)); label(S, "NEW", 110 + 6 * cw, 6, (255, 220, 120))
for r, (nm, eq, g, body, robe) in enumerate(CAST):
    label(S, nm, 4, 30 + r * ch + 50, size=12)
    for k, new in enumerate((False, True)):
        for j, (f, dn) in enumerate(dirs):
            x = 110 + (k * 4 + j) * cw + cw // 2 + (20 if k else 0)
            draw_char(S, x, 30 + r * ch + 88, T, new, eq, g, f, body=body, robe=robe)
pygame.image.save(pygame.transform.scale(S, (S.get_width() * 2, S.get_height() * 2)), os.path.join(OUT, "characters_4dir_before_after.png"))
pygame.image.save(S, os.path.join(OUT, "characters_4dir_before_after_gamescale.png"))
