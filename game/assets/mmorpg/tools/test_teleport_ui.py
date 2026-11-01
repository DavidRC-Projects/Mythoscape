"""Teleport window restyle: states, here/locked, height cap, cast delay, cancel on move, rename."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import client as C
import teleport_ui as T
from content import TELEPORT_DESTINATIONS as D
ok = 0
def check(c, m):
    global ok
    assert c, m; ok += 1; print("ok", m)
labels = {d["id"]: d for d in D}
check(labels["outfitters"]["label"] == "Crownfall Outfitters", "Crownfall Outfitters label")
check(labels["kings_row_south"]["blurb"] == "South-road cottages", "King's Row subtitle")
check(labels["realm"]["label"] == "King's Realm", "realm renamed")
check(len({v for v in T.ICONS.values()}) == 11, "11 painted icons mapped")
for k in set(T.ICONS.values()):
    check(os.path.exists(os.path.join(T._DIR, k + ".png")), f"icon {k}.png exists")
check(all(d["id"] in T.ICONS for d in D), "every destination has an icon")
for sw, sh in ((1200, 800), (1200, 560), (420, 640), (1920, 1080)):
    r = T.window_rect(sw, sh)
    check(r.h == min(760, sh - 48) and r.w <= min(520, sw - 16) and r.bottom <= sh, f"window fits {sw}x{sh}")
C.GameClient._connect_stub = True
g = C.GameClient()
class _Net:
    def __init__(self): self.sent = []
    def send(self, *a, **k): self.sent.append((a, k))
g.net = _Net(); g.dungeon = None
g.player = {"id": 1, "x": 28, "y": 24, "knows_teleport": True, "teleport_marks": ["village", "bank", "realm"]}
items = T.entries(g, D)
st = {d["id"]: d["state"] for d in items}
check(st["village"] == "here" and st["bank"] == "open" and st["void"] == "locked", "here / open / locked states")
check(st["realm"] == "open", "realm entry not 'here' while on the overworld")
check(len(items) == len(D), "all places listed (locked too)")
check([t for t, _ in T.groups(items)] == ["The Kingdom", "King's Realm"], "sections: The Kingdom, King's Realm")
g.screen = pygame.Surface((1200, 800))
g.show_teleport = True
T.draw(g, D, True)
kinds = {}
for k, r, p in g.teleport_row_rects:
    kinds[p] = k
check(kinds.get("village") == "here" and kinds.get("bank") == "dest", "rects carry the state")
lr = next(r for k, r, p in g.teleport_row_rects if k == "locked")
g.handle_teleport_click(*lr.center)
check(g.show_teleport and not g.net.sent and "unlock" in g.teleport_toast["text"], "locked click only toasts")
hr = next(r for k, r, p in g.teleport_row_rects if k == "here")
g.handle_teleport_click(*hr.center)
check(g.show_teleport and not g.net.sent, "'You are here' is disabled")
br = next(r for k, r, p in g.teleport_row_rects if p == "bank")
g.handle_teleport_click(*br.center)
check(not g.show_teleport and not g.net.sent and g.teleport_fx["phase"] == "cast", "click starts the cast, nothing sent yet")
check(abs(g.teleport_fx["until"] - g.teleport_fx["start"] - 0.8) < 1e-6, "cast is 0.8s")
T._feet = lambda c: (600, 400)
g.teleport_fx["until"] = time.time() - 0.01
g.draw_teleport_fx()
check(g.net.sent and g.net.sent[0][1] == {"dest": "bank"}, "TELEPORT sent when the cast ends")
g.net.sent.clear()
g.cast_teleport("village"); g.teleport_fx = None
g.cast_teleport("bank"); g.player["x"] += 1
g.draw_teleport_fx()
check(g.teleport_fx is None and not g.net.sent, "moving cancels the cast")
g.player["x"] = 150; g.player["y"] = 183; g.dungeon = {"id": "castle_realm"}
st = {d["id"]: d["state"] for d in T.entries(g, D)}
check(st["realm"] == "here" and st["village"] == "open", "here inside the King's Realm")
src = open(os.path.join(ROOT, "client", "client.py"), encoding="utf-8").read()
check('"Castle Realm"' not in src and "CASTLE REALM" not in src, "no player-facing 'Castle Realm' in client.py")
print(ok, "checks passed")
