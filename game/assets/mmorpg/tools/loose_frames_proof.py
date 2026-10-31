"""Every action frame the head tracker could not match on its own (placed from its neighbours), with the
chosen face applied, in pages of 240: loose_<sex>_<n>.png. Orange border = the figure's own head kept."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "client"), os.path.join(HERE, "..", "server")]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.display.set_mode((1, 1))
import face_layer as FL
A = os.path.join(HERE, "..", "..", "player_hd", "assets")
FACE = {"male": "king", "female": "queen"}
W, Z, COLS, PER = 72, 2, 16, 128


def main(d, only=None):
    tr = json.load(open(os.path.join(A, "faces", "targets", "track.json")))
    font = pygame.font.SysFont("arial", 11)
    for sex in ("male", "female"):
        cells = []
        for key, lst in sorted(tr.items()):
            sx, layer, af = key.split("/")
            if sx != sex or (only and only not in key):
                continue
            anim, _, fa = af.rpartition("_")
            if anim.startswith(("idle", "walk", "fx")):
                continue
            idx = [i for i, v in enumerate(lst) if len(v) > 4]
            if not idx:
                continue
            sh = pygame.image.load(os.path.join(A, sex, "2x", layer, af + ".png")).convert_alpha()
            h = sh.get_height()
            for i in idx:
                fr = sh.subsurface((i * h, 0, h, h)).copy()
                FL.LAST.clear()
                res = FL.apply(fr, sex, layer, anim, fa, i, FACE[sex], None, None, None, tag="2x")
                nx, ny = (FL.LAST["tx"], FL.LAST["ty"]) if FL.LAST else (h / 2, h * 0.42)
                c = pygame.Surface((W, W)); c.fill((96, 118, 92))
                c.blit(res if res is not None else fr, (int(W / 2 - nx), int(W / 2 + 10 - ny)))
                c = pygame.transform.scale(c, (W * Z, W * Z))
                if res is None:
                    pygame.draw.rect(c, (255, 200, 0), c.get_rect(), 3)
                c.blit(font.render(f"{layer[:-3].replace('outfit_','').replace('armour_','')} {af}#{i}", True,
                                   (255, 255, 255)), (2, 2))
                cells.append(c)
        for p in range(0, len(cells), PER):
            ch = cells[p:p + PER]
            o = pygame.Surface((COLS * W * Z, ((len(ch) + COLS - 1) // COLS) * W * Z))
            for j, c in enumerate(ch):
                o.blit(c, ((j % COLS) * W * Z, (j // COLS) * W * Z))
            path = os.path.join(d, f"loose_{sex}_{p // PER}.png")
            pygame.image.save(o, path)
            print(path, len(ch))


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/grokbot_tmp/proofs/faces/loose")
    os.makedirs(d, exist_ok=True)
    main(d, sys.argv[2] if len(sys.argv) > 2 else None)
