"""Confirm modal proofs -> /workspace/proofs/ui/modals/ (override with PROOF_DIR)."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import client as C
import confirm_modal as M
OUT = os.environ.get("PROOF_DIR", "/workspace/proofs/ui/modals"); os.makedirs(OUT, exist_ok=True)
C.GameClient._connect_stub = True
g = C.GameClient()
class _Net:
    sent = []
    def send(self, *a, **k): self.sent.append((a, k))
g.net = _Net()
mouse = [(0, 0)]
pygame.mouse.get_pos = lambda: mouse[0]
T = [100000]
pygame.time.get_ticks = lambda: T[0]
def backdrop(scr):
    w, h = scr.get_size()
    for y in range(h):
        c = 40 + int(22 * y / h)
        pygame.draw.line(scr, (c - 10, c + 8, c - 18), (0, y), (w, y))
    for i in range(0, w, 48):
        for j in range(0, h, 48):
            pygame.draw.rect(scr, (70, 92, 58), (i, j, 46, 46), 1)
    for k in range(9):
        pygame.draw.circle(scr, (40, 70, 34), (90 + k * 140, 120 + (k % 3) * 160), 40)
    pygame.draw.rect(scr, (24, 26, 30), (w - 250, 0, 250, h))
def shot(name, kind, prompt, w=1280, h=720, legacy=False, hover=None, t=1000):
    g.screen = pygame.Surface((w, h)); backdrop(g.screen)
    mouse[0] = hover or (0, 0)
    if kind == "bone":
        g.bone_prompt = dict(prompt); g.drop_prompt = None
        T[0] = (prompt.get("t0") or 0) + t
        g._draw_bone_prompt_legacy() if legacy else g.draw_bone_prompt()
    else:
        g.drop_prompt = dict(prompt); g.bone_prompt = None
        T[0] = (prompt.get("t0") or 0) + t
        g._draw_drop_prompt_legacy() if legacy else g.draw_drop_prompt()
    pygame.image.save(g.screen, os.path.join(OUT, name))
    return g.screen
bones = {"slot": 3, "item_id": "bones", "name": "Bones", "qty": 6, "t0": 1000}
b = shot("before_bury.png", "bone", bones, legacy=True)
a = shot("after_bury.png", "bone", bones)
shot("after_bury_hover_primary.png", "bone", bones, hover=g.bone_prompt_rects["primary"].center)
shot("after_bury_single.png", "bone", dict(bones, qty=1))
shot("after_bury_dontask_on.png", "bone", dict(bones, dont_ask_on=True, focus=1))
shot("after_bury_open_60ms.png", "bone", bones, t=60)
shot("after_bury_1920.png", "bone", bones, w=1920, h=1080)
shot("after_bury_small_800x520.png", "bone", bones, w=800, h=520)
drop = {"slot": 5, "item_id": "iron_ore", "name": "Iron ore", "qty": 12, "t0": 1000}
shot("before_drop.png", "drop", drop, legacy=True)
shot("after_drop.png", "drop", drop)
shot("after_drop_rare.png", "drop", {"slot": 5, "item_id": "mythos_longsword", "name": "Mythos longsword", "qty": 1, "t0": 1000})
ba = pygame.Surface((1280 * 2 + 30, 720 + 60)); ba.fill((18, 12, 8))
ba.blit(b, (10, 50)); ba.blit(a, (1300, 50))
f = M.font("title", 26)
ba.blit(f.render("BEFORE", True, (168, 152, 122)), (600, 12)); ba.blit(f.render("AFTER", True, (206, 174, 115)), (1890, 12))
pygame.image.save(ba, os.path.join(OUT, "before_after_bury.png"))
print("proofs ->", OUT)
