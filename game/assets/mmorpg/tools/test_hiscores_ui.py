"""Hiscores modal v1: sort kept, search, jump, keys, guild columns, virtualised 1,200 rows."""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "client"))
import pygame
pygame.init(); pygame.display.set_mode((1200, 800))
import hiscores_ui as H
fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg); ok or fails.append(msg)

def key(c, k, u=""):
    return H.handle_event(c, pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=u))

class C:
    def __init__(self, n=0):
        self.screen = pygame.display.get_surface(); self.player = None
        self.fields = {"username": "x", "char_name": "Luna Meow2"}
        tot = [{"name": "A", "level": 40, "xp": 10}, {"name": "Luna Meow", "level": 40, "xp": 3033},
               {"name": "Luna Meow2", "level": 40, "xp": 3092}, {"name": "Top", "level": 99, "xp": 1}]
        tot += [{"name": f"P{i}", "level": 5, "xp": 1000 - i} for i in range(n)]
        self.leaderboard = {"total": tot, "guild": [{"name": "G", "members": 2, "level": 9, "xp": 9}],
                            "attack": [{"name": "Top", "level": 9, "xp": 99}]}
        self.leaderboard_skills = ["total", "guild", "attack"]; self.leaderboard_skill = "total"
        self.leaderboard_scroll = 0; self.show_leaderboard = True

c = C()
order = [e["name"] for _, e in H.sorted_rows(c, "total")]
check(order == ["Top", "Luna Meow2", "Luna Meow", "A"], f"total sorted by level then XP {order}")
H.draw(c)
check(c.hs_rects.get("search") and c.hs_rects.get("jump") and len(c.hs_rects["skills"]) == 3, "search, jump and skill list drawn")
# search
H.click(c, c.hs_rects["search"].center); check(c.hs_search_focus, "click focuses Find player")
for ch in "luna":
    key(c, pygame.K_a, ch)
rows = H.visible_rows(c, "total")
check([r for r, _ in rows] == [2, 3], f"search filters and keeps real ranks {[r for r,_ in rows]}")
key(c, pygame.K_BACKSPACE); check(c.hs_search == "lun", "backspace edits")
key(c, pygame.K_ESCAPE); check(c.hs_search == "" and c.show_leaderboard, "Esc clears search first")
key(c, pygame.K_ESCAPE); check(not c.hs_search_focus and c.show_leaderboard, "second Esc unfocuses")
# arrows move through the list
key(c, pygame.K_DOWN); check(c.leaderboard_skill == "guild", "Down -> next skill")
H.draw(c); check(c.hs_rects["rows"] and c.hs_rects["rows"][0][1]["name"] == "G", "guild view rows")
key(c, pygame.K_UP); check(c.leaderboard_skill == "total", "Up -> previous skill")
# jump with 1,200 rows
c = C(1200); c.fields["char_name"] = "P900"; H.draw(c)
t0 = time.time(); H.draw(c); dt = time.time() - t0
check(dt < 0.25, f"1,200 rows draw fast ({dt*1000:.0f} ms, virtualised)")
check(H.jump_to_me(c) and c.leaderboard_scroll > 0, "Jump to my rank scrolls")
H.draw(c); names = [e["name"] for _, e in c.hs_rects["rows"]]
check("P900" in names, "my row visible after jump")
check(time.time() - c.hs_pulse < 1.2, "gold pulse running")
# close
H.click(c, c.hs_rects["close"].center); check(not c.show_leaderboard, "close X")
c = C(); H.draw(c); key(c, pygame.K_ESCAPE); check(not c.show_leaderboard, "Esc closes")
print("RESULT", "FAIL" if fails else "PASS", len(fails)); sys.exit(1 if fails else 0)
