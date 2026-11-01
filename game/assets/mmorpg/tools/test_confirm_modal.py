"""Confirm modal restyle: layout, button order, keys, debounce, destructive lock, don't-ask-again, fallback."""
import os, sys, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import client as C
import confirm_modal as M
M._PREFS = os.path.join(tempfile.mkdtemp(), "prefs.json")
ok = 0
def check(c, m):
    global ok
    assert c, m; ok += 1; print("ok", m)
T = [10000]
pygame.time.get_ticks = lambda: T[0]
pygame.mouse.get_pos = lambda: (0, 0)
C.GameClient._connect_stub = True
g = C.GameClient()
class _Net:
    def __init__(self): self.sent = []
    def send(self, *a, **k): self.sent.append((a, k))
g.net = _Net()
key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")
entry = {"item_id": "bones", "qty": 6}
def open_bones(q=6):
    g.open_bone_prompt(3, dict(entry, qty=q)); T[0] += 1000
for sw, sh in ((1280, 720), (1920, 1080), (800, 520)):
    g.screen = pygame.Surface((sw, sh)); open_bones(); g.draw_bone_prompt()
    r = g.bone_prompt_rects
    check(r["box"].h <= 420 * 1.0 + 1 and r["box"].left >= 0 and r["box"].right <= sw, f"modal fits {sw}x{sh}")
    check(r["cancel"].x < r["secondary"].x < r["primary"].x and r["primary"].w > r["secondary"].w, f"Cancel, Bury 1, Bury all order {sw}")
    check(r["primary"].h >= int(46 * 0.8), f"46px buttons {sw}")
spec = g.bone_prompt["_spec"]
check(spec["buttons"][2]["label"] == "Bury all (6)", "primary label has count")
check(("Bury all: +108 Karma XP", "total") in spec["lines"] and ("+18 Karma XP each", "gain") in spec["lines"], "totals computed 6 x 18")
check(spec["count"] == 6, "count badge 6")
s1 = M.bury_spec({"item_id": "bones", "qty": 1}, C.ITEMS)
check([b["role"] for b in s1["buttons"]] == ["cancel", "primary"], "single bone: Cancel + Bury")
# debounce
g.screen = pygame.Surface((1280, 720)); g.open_bone_prompt(3, entry); g.draw_bone_prompt()
g.handle_game_event(key(pygame.K_RETURN))
check(g.bone_prompt is not None and not g.net.sent, "Enter ignored within 150ms")
g.handle_bone_prompt_click(*g.bone_prompt_rects["primary"].center)
check(g.bone_prompt is not None and not g.net.sent, "click ignored within 150ms")
T[0] += 200
g.handle_game_event(key(pygame.K_RETURN))
check(g.net.sent[-1] == (("USE_ITEM",), {"slot_index": 3, "action": "bury_all"}) and g.bone_prompt is None, "Enter = Bury all")
open_bones(); g.draw_bone_prompt(); g.handle_game_event(key(pygame.K_1))
check(g.net.sent[-1] == (("USE_ITEM",), {"slot_index": 3}), "1 = Bury 1")
open_bones(); g.draw_bone_prompt(); n = len(g.net.sent); g.handle_game_event(key(pygame.K_ESCAPE))
check(g.bone_prompt is None and len(g.net.sent) == n, "Esc cancels")
open_bones(); g.draw_bone_prompt(); g.handle_game_event(key(pygame.K_TAB))
check(g.bone_prompt["focus"] == 0, "Tab cycles focus to Cancel")
g.handle_game_event(key(pygame.K_RETURN))
check(g.bone_prompt is None and len(g.net.sent) == n, "Enter on focused Cancel cancels")
open_bones(); g.draw_bone_prompt(); g.handle_bone_prompt_click(*g.bone_prompt_rects["close"].center)
check(g.bone_prompt is None, "close X cancels")
open_bones(); g.draw_bone_prompt(); g.handle_bone_prompt_click(5, 5)
check(g.bone_prompt is None, "backdrop click cancels")
open_bones(); g.draw_bone_prompt(); g.handle_bone_prompt_click(*g.bone_prompt_rects["secondary"].center)
check(g.net.sent[-1] == (("USE_ITEM",), {"slot_index": 3}), "click Bury 1")
# don't ask again
open_bones(); g.draw_bone_prompt(); g.handle_bone_prompt_click(*g.bone_prompt_rects["dont_ask"].center)
check(g.bone_prompt["dont_ask_on"], "checkbox toggles")
g.draw_bone_prompt(); g.handle_bone_prompt_click(*g.bone_prompt_rects["secondary"].center)
check(M.skip("bones"), "don't-ask saved")
n = len(g.net.sent); g.open_bone_prompt(4, entry)
check(g.bone_prompt is None and g.net.sent[-1] == (("USE_ITEM",), {"slot_index": 4}) and len(g.net.sent) == n + 1, "next bones bury 1 directly")
M.set_skip("bones", False)
# drop
g.open_drop_prompt(5, {"item_id": "iron_ore", "qty": 12}); T[0] += 1000; g.draw_drop_prompt()
check(("Others can pick this up.", "loss") in g.drop_prompt["_spec"]["lines"], "drop warning line")
g.handle_game_event(key(pygame.K_RETURN))
check(g.net.sent[-1] == (("DROP",), {"slot_index": 5, "qty": 12}), "drop Enter = Drop all")
g.open_drop_prompt(6, {"item_id": "mythos_longsword", "qty": 1}); T[0] += 1000; g.draw_drop_prompt()
check(g.drop_prompt["_spec"]["destructive"] and "dont_ask" not in g.drop_prompt_rects, "valuable drop is destructive, no don't-ask")
n = len(g.net.sent); g.handle_game_event(key(pygame.K_RETURN)); g.handle_drop_prompt_click(3, 3)
check(g.drop_prompt is not None and len(g.net.sent) == n, "destructive: Enter + backdrop locked")
g.handle_drop_prompt_click(*g.drop_prompt_rects["primary"].center)
check(g.net.sent[-1] == (("DROP",), {"slot_index": 6, "qty": 1}) and g.drop_prompt is None, "destructive click drops 1")
# sell / dismiss variants
s = M.sell_spec("Iron ore", "iron_ore", 12, 7)
check(("+84 coins", "coin") in s["lines"] and s["buttons"][1]["label"] == "Sell 1", "sell variant totals")
check(M.dismiss_spec("Tiro")["destructive"], "dismiss is destructive")
# animation + fallback
open_bones(); T[0] -= 1000 - 30; g.draw_bone_prompt()
check(g.bone_prompt_rects["box"].w < 560, "opening scale < 1 at 30ms")
real = M.draw
M.draw = lambda *a, **k: 1 / 0
T[0] += 1000; g.draw_bone_prompt(); M.draw = real
check("one" in g.bone_prompt_rects, "legacy modal kept as error fallback")
print(ok, "checks passed")
