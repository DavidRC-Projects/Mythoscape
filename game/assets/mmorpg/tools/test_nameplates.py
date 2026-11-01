"""Nameplates package: layout, modes, bands, trail, collapse and clamp (headless)."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "client"))
import pygame
pygame.init(); pygame.display.set_mode((1200, 800))
import nameplates as N
MAP_W, MAP_H = 900, 640
fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg); ok or fails.append(msg)

class C:
    def __init__(self):
        self.screen = pygame.Surface((1200, 800)); self.chat = []; self.dungeon = None
        self.np_mode_override = N.MODE_ALL
    def player_xy(self): return (0, 0)
    def player_combat_level(self): return 20
    def add_chat(self, s, *a, **k): self.chat.append(s)

# nameplates reads MAP_W/MAP_H from the client's module; register one so the test
# works whether it runs as __main__ or is loaded by a harness under another name.
import types
_view = types.ModuleType("np_test_view"); _view.MAP_W, _view.MAP_H = MAP_W, MAP_H
sys.modules["np_test_view"] = _view; C.__module__ = "np_test_view"

def sub(c, key, x, y, **kw):
    kw.setdefault("kind", "mon"); kw.setdefault("rel", "hostile")
    N.submit(c, key, x, y, kw.pop("name", "Giant Rat"), feet=kw.pop("feet", y + 40), **kw)

# 1. stacked crowd: no overlaps among named plates, bar inside/below name row
N._STATE.clear(); c = C()
for i in range(5):
    sub(c, f"r{i}", 400, 300, level=3, hp=5, max_hp=10, in_combat=True)
pl = N.flush(c)
named = [p["rect"] for p in pl if p.get("name_on") and not p.get("collapsed")]
check(len(pl) == 5, "five plates laid out")
check(all(not a.colliderect(b) for i, a in enumerate(named) for b in named[i + 1:]), "named plates do not overlap")
check(any(p.get("collapsed") for p in pl), "4th+ stacked plate collapses to bar only")
check(any(p.get("pushed") for p in pl), "overlapping plates are pushed up")
# 2. clamp to map
N._STATE.clear(); c = C(); sub(c, "edge", 895, 2, level=3, hp=10, max_hp=10)
r = N.flush(c)[0]["rect"]
check(r.right <= MAP_W - 4 and r.top >= 4, f"edge plate clamped inside map {r}")
# 3. level band
check(N.level_band(30, 20) == N.BAND_R and N.level_band(20, 20) == N.BAND_A and N.level_band(10, 20) == N.BAND_G, "level_band 1.15/0.85")
# 4. V toggle
c = C(); c.np_mode_override = None; m0 = N.mode(c); N.toggle_mode(c)
check(N.mode(c) != m0 and c.chat and "(V)" in c.chat[-1], "toggle_mode flips mode and posts chat")
# 5. target mode hides untargeted hostile names, keeps target + npc
N._STATE.clear(); c = C(); c.np_mode_override = N.MODE_TARGET
sub(c, "a", 200, 200, level=3, hp=10, max_hp=10)
sub(c, "t", 500, 200, level=3, hp=4, max_hp=10, targeted=True)
N.submit(c, "n", 700, 200, "Bob", rel="npc", kind="std", feet=240)
d = {p["key"]: p for p in N.flush(c)}
check("a" not in d or not d["a"]["name_on"], "target mode: idle hostile name hidden")
check(d["t"]["name_on"] and d["n"]["name_on"], "target mode: target and NPC keep names")
check(getattr(c, "np_target_frame_rect", None) is not None, "target frame drawn")
# 6. damage trail
st = {}; N._trail(st, 10, 10, 0.0); N._trail(st, 4, 10, 0.1)
check(st.get("from", 10) > 4 or st.get("shown", 10) > 4, "damage chunk trail lingers above new hp")
# 7. draws without exceptions over many frames
c = C(); ok = True
try:
    for f in range(30):
        sub(c, "z", 300, 300, level=50, hp=max(1, 30 - f), max_hp=100, in_combat=True, stars=2)
        N.flush(c, 1.4, -50, -20)
except Exception as e:
    ok = False; print(e)
check(ok, "30 zoomed frames draw cleanly")
print("RESULT", "FAIL" if fails else "PASS", len(fails)); sys.exit(1 if fails else 0)
