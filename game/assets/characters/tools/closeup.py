import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from render_common import *
OUT = sys.argv[1]
T = 40
ECL = {"body": "eclipse_body", "legs": "eclipse_legs", "helmet": "eclipse_helmet", "weapon": "eclipse_cleaver", "shield": "eclipse_shield"}
MYT = {"body": "mythos_body", "legs": "mythos_legs", "helmet": "mythos_helmet", "weapon": "mythos_longsword", "shield": "mythos_shield", "amulet": "ruby_amulet"}
dirs = ["front", 1, "back", -1]
cw, ch = 100, 140
# 1x strip: old + new, both sets, 4 dirs + attack frame
S = pygame.Surface((110 + 5 * cw * 2, 30 + 4 * ch)); tiles(S)
rows = [("Eclipse OLD", ECL, False), ("Eclipse NEW", ECL, True), ("Mythos (dragon) OLD", MYT, False), ("Mythos (dragon) NEW", MYT, True)]
for r, (nm, eq, new) in enumerate(rows):
    label(S, nm, 4, 30 + r * ch + 40, (255, 220, 120) if new else (200, 200, 200), size=11)
    for j, f in enumerate(dirs + [1]):
        draw_char(S, 110 + j * cw * 2 // 2 * 1 + j * cw + cw // 2, 30 + r * ch + 95, T, new, eq, "male", f,
                  attacking=0.5 if j == 4 else 0.0, t=0.7)
label(S, "1x game scale (TILE 40)   front / right / back / left / attack", 110, 6, size=12)
big = pygame.transform.scale(S, (S.get_width() * 3, S.get_height() * 3))
# preview-scale renders (equipment preview tile 80) at 1x
Pv = pygame.Surface((4 * 220 + 20, 330)); Pv.fill((34, 30, 26))
for i, (eq, new) in enumerate(((ECL, False), (ECL, True), (MYT, False), (MYT, True))):
    draw_char(Pv, 120 + i * 220, 190, 80, new, eq, "male", 1, action="stand", t=0.7)
    label(Pv, ("NEW " if new else "OLD ") + ("Eclipse" if eq is ECL else "Mythos"), 70 + i * 220, 8, (255, 220, 120) if new else (200, 200, 200))
W = max(big.get_width(), S.get_width())
sheet = pygame.Surface((W, S.get_height() + 20 + big.get_height() + Pv.get_height() + 40)); sheet.fill((24, 22, 20))
sheet.blit(S, (0, 0))
sheet.blit(big, (0, S.get_height() + 20))
sheet.blit(Pv, (0, S.get_height() + 40 + big.get_height()))
label(sheet, "3x zoom of the same 1x pixels", 8, S.get_height() + 2, size=14)
label(sheet, "Equipment-preview scale (tile 80), 1x", 8, S.get_height() + 22 + big.get_height(), size=14)
pygame.image.save(sheet, os.path.join(OUT, "eclipse_dragon_closeup.png"))
pygame.image.save(big, "/tmp/closeup3x.png")
