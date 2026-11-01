"""Teleport window proofs -> ~/grokbot_tmp/teleport_proofs/. Run: .venv/bin/python tools/teleport_proofs.py"""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import client as C
import teleport_ui as T
OUT = os.environ.get("TP_OUT") or os.path.expanduser("~/grokbot_tmp/teleport_proofs"); os.makedirs(OUT, exist_ok=True)
C.GameClient._connect_stub = True
g = C.GameClient()
class _Net:
    sent = []
    def send(self, *a, **k): self.sent.append((a, k))
g.net = _Net()
g.player = {"id": 1, "name": "Aldric", "x": 28, "y": 24, "knows_teleport": True,
            "teleport_marks": ["village", "bank", "outfitters", "stonehaven", "keep", "estate", "kings_row_south", "realm", "king", "arena"],
            "home": {"x": 30, "y": 140, "name": "Ash Manor", "blurb": "Your home — Ash Manor"}}
g.dungeon = None
def backdrop(scr):
    w, h = scr.get_size()
    for y in range(h):
        c = 34 + int(18 * y / h)
        pygame.draw.line(scr, (c - 8, c, c - 14), (0, y), (w, y))
    for i in range(0, w, 64):
        for j in range(0, h, 48):
            pygame.draw.rect(scr, (58, 60, 52), (i + (j // 48 % 2) * 32, j, 62, 46), 1)
mouse = [(0, 0)]
pygame.mouse.get_pos = lambda: mouse[0]
def shot(name, w=1200, h=800, legacy=False, scroll=0, hover=None):
    g.screen = pygame.Surface((w, h))
    backdrop(g.screen)
    g.teleport_scroll = scroll
    mouse[0] = hover or (0, 0)
    if legacy:
        g._draw_teleport_modal_legacy()
    else:
        T.draw(g, C.TELEPORT_DESTINATIONS, True)
    pygame.image.save(g.screen, os.path.join(OUT, name))
    return g.screen
shot("before_window.png", legacy=True)
s = shot("after_window.png")
# hover the Village Bank card (first "dest" row after home)
rows = [r for r in g.teleport_row_rects if r[0] == "dest"]
shot("after_window_hover.png", hover=rows[1][1].center)
locked = next(r for r in g.teleport_row_rects if r[0] == "locked")
here = next(r for r in g.teleport_row_rects if r[0] == "here")
s = shot("after_window.png")
pygame.image.save(s.subsurface(locked[1].inflate(30, 24)), os.path.join(OUT, "after_locked_entry.png"))
pygame.image.save(s.subsurface(here[1].inflate(30, 24)), os.path.join(OUT, "after_you_are_here.png"))
shot("after_scrolled_sticky_ribbon.png", scroll=520)
shot("after_narrow_420x640.png", w=420, h=640)
shot("after_short_1200x560.png", w=1200, h=560)
g.player["knows_teleport"] = False
g.screen = pygame.Surface((1200, 800)); backdrop(g.screen); T.draw(g, C.TELEPORT_DESTINATIONS, False)
pygame.image.save(g.screen, os.path.join(OUT, "after_not_taught.png"))
g.player["knows_teleport"] = True
# rune cast frames
T._feet = lambda client: (600, 420)
def ghost(scr):
    pygame.draw.ellipse(scr, (20, 20, 20), (586, 410, 28, 12))
    pygame.draw.rect(scr, (120, 90, 70), (590, 360, 20, 52), border_radius=6)
    pygame.draw.circle(scr, (200, 170, 140), (600, 352), 10)
for name, t in (("after_rune_cast_0.3s.png", 0.3), ("after_rune_cast_0.6s.png", 0.6), ("after_rune_flash_0.78s.png", 0.78)):
    g.screen = pygame.Surface((1200, 800)); backdrop(g.screen); ghost(g.screen)
    T.start_cast(g, "bank", "Village Bank")
    g.teleport_fx["start"] -= t; g.teleport_fx["until"] -= t
    T.draw_fx(g)
    pygame.image.save(g.screen, os.path.join(OUT, name))
g.screen = pygame.Surface((1200, 800)); backdrop(g.screen); ghost(g.screen)
T.start_arrive(g, "Village Bank"); g.teleport_fx["start"] -= 0.35; g.teleport_fx["until"] -= 0.35
T.draw_fx(g); pygame.image.save(g.screen, os.path.join(OUT, "after_arrive_banner.png"))
print("saved to", OUT)
