"""Stats screen v2: point rules, presets, Custom switch, confirm gate, name fallback, layouts fit."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import stats_screen_v2 as S
from client_screens import STAT_PRESETS

BASE = {"attack": 5, "strength": 5, "defence": 5, "archery": 1}
Z = lambda: {"attack": 0, "strength": 0, "defence": 0, "archery": 0}
ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("ok", msg)


a = Z()
check(S.remaining(a) == 10 and not S.ready(a), "fresh: 10 left, not ready")
check(not S.can_minus(a, "attack"), "minus disabled at 0")
check(S.can_plus(a, "attack", BASE), "plus enabled with points")
full = {"attack": 10, "strength": 0, "defence": 0, "archery": 0}
check(S.ready(full) and not S.can_plus(full, "strength", BASE), "all spent: ready, plus blocked")
check(S.plus_block_reason(full, "strength", BASE) == "No points left", "block reason: no points")
check(S.stat_max_bonus("archery", {"archery": 40}) == 0 and
      S.plus_block_reason(Z(), "archery", {"archery": 40}) == "Max for now", "block reason: max level")
for name, pts in STAT_PRESETS:
    check(sum(pts.values()) == 10, f"preset {name} sums to 10")

import client as C
C.GameClient._connect_stub = True
g = C.GameClient()
g.player = {"id": 1, "name": "54545454455"}
g.state = "STAT_ALLOC"; g.stat_gender = "male"; g.stat_alloc_error = ""; g.login_error = ""
g.stat_alloc = Z(); g.stat_alloc_base = dict(BASE)
check(S.display_name(g.player) == "Traveller", "numeric name -> Traveller")
check(S.display_name({"name": "Aldric"}) == "Aldric", "real name kept")

S.apply_preset(g, STAT_PRESETS[1][0])
check(S.ready(g.stat_alloc) and S.mode_label(g) == STAT_PRESETS[1][0], "preset applies & labels mode")
S.edit(g, "attack", "minus")
check(S.mode_label(g) == "Custom" and S.remaining(g.stat_alloc) == 1, "edit switches to Custom")
S.reset(g)
check(S.remaining(g.stat_alloc) == 10, "reset restores 10")

# confirm gated: Enter with points left must not submit
sent = []
class _Net:
    def send(self, *a, **k): sent.append((a, k))
g.net = _Net()
S.handle_event(g, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
check(not sent and g.state == "STAT_ALLOC" and "left" in g.stat_alloc_error, "confirm blocked while points remain")
S.apply_preset(g, STAT_PRESETS[0][0])
S.handle_event(g, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
check(len(sent) == 1 and sent[0][0][0] == "ALLOCATE_STATS", "confirm sends once all spent")

for (w, h), mode in (((1200, 800), "full"), ((600, 900), "stack")):
    g.screen = pygame.Surface((w, h))
    g.stat_alloc = Z()
    S.draw(g)
    cr = g.stat_confirm_rect
    check(g.screen.get_rect().contains(cr), f"{w}x{h}: confirm fully on screen")
    L = g._stats_layout
    check(L["mode"] == mode, f"{w}x{h}: layout {mode}")
    rects = [r for r in g.stat_alloc_rects.values()] + [r for r, _ in g.stat_preset_rects]
    check(all(g.screen.get_rect().contains(r) for r in rects), f"{w}x{h}: all controls on screen")
print(f"test_stats_screen: {ok} ok")
