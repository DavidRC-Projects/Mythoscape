"""Zoomed neck/shoulder sheet: the chosen face on every outfit/armour figure, across facings and
animations (red ticks = the figure's neck line). Writes head_align_<sex>_<face>.png to the given dir."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "client"), os.path.join(HERE, "..", "server")]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.display.set_mode((1, 1))
import face_layer as FL

A = os.path.join(HERE, "..", "..", "player_hd", "assets")
PICKS = [("idle", "s", 0), ("walk", "s", 3), ("melee_axe", "s", 5), ("chop", "s", 3), ("mine", "s", 5),
         ("melee_sword", "s", 5), ("idle", "e", 0), ("walk", "e", 3), ("melee_axe", "e", 4), ("chop", "e", 3),
         ("fish", "e", 4), ("mine", "e", 4), ("melee_sword", "e", 4), ("idle", "n", 0), ("walk", "n", 2),
         ("melee_axe", "n", 4)]
Z, W = 2, 64


def sheet(sex, face, out_dir):
    font = pygame.font.SysFont("arial", 13)
    keys = sorted(k.split("/", 1)[1] for k in FL.meta()["targets"] if k.startswith(sex + "/"))
    o = pygame.Surface((150 + len(PICKS) * W * Z, 20 + len(keys) * W * Z))
    o.fill((30, 30, 36))
    for c, (an, fa, i) in enumerate(PICKS):
        o.blit(font.render(f"{an} {fa}#{i}", True, (230, 230, 230)), (150 + c * W * Z + 4, 3))
    for r, layer in enumerate(keys):
        o.blit(font.render(layer.replace("_hd", ""), True, (230, 230, 230)), (4, 20 + r * W * Z + W))
        for c, (an, fa, i) in enumerate(PICKS):
            p = os.path.join(A, sex, "2x", layer, f"{an}_{fa}.png")
            if not os.path.exists(p):
                continue
            sh = pygame.image.load(p).convert_alpha()
            h = sh.get_height()
            i = min(i, sh.get_width() // h - 1)
            fr = sh.subsurface((i * h, 0, h, h)).copy()
            FL.LAST.clear()
            res = FL.apply(fr, sex, layer, an, fa, i, face, None, None, None, tag="2x")
            img = res if res is not None else fr
            nx, ny = (FL.LAST["tx"], FL.LAST["ty"]) if FL.LAST else (h / 2, h * 0.42)
            cell = pygame.Surface((W, W))
            cell.fill((96, 118, 92))
            cell.blit(img, (int(W / 2 - nx), int(W / 2 + 6 - ny)))
            cell = pygame.transform.scale(cell, (W * Z, W * Z))
            yy = (W // 2 + 6) * Z
            pygame.draw.line(cell, (255, 40, 40), (0, yy), (6, yy), 2)
            pygame.draw.line(cell, (255, 40, 40), (W * Z - 6, yy), (W * Z, yy), 2)
            if res is None:
                pygame.draw.rect(cell, (255, 200, 0), cell.get_rect(), 2)      # orange: own head kept
            elif FL.LAST.get("loose"):
                pygame.draw.rect(cell, (90, 160, 255), cell.get_rect(), 2)     # blue: placed between matches
            o.blit(cell, (150 + c * W * Z, 20 + r * W * Z))
    path = os.path.join(out_dir, f"head_align_{sex}_{face}.png")
    pygame.image.save(o, path)
    return path


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/grokbot_tmp/proofs/faces")
    os.makedirs(d, exist_ok=True)
    for sex, face in (("male", "king"), ("female", "queen"), ("male", "noble_lord")):
        print(sheet(sex, face, d))
