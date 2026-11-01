"""Moon Petal Inn: door click + walk-in, entry film skip rules, 9 hotspots, Tab/Enter, dialogue 1-5/Esc. Writes proofs."""
import os, sys, time, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["HOME"] = tempfile.mkdtemp()          # fresh prefs (first view)
HERE = os.path.dirname(os.path.abspath(__file__)); CLI = os.path.normpath(os.path.join(HERE, "..", "client"))
sys.path.insert(0, CLI); os.chdir(CLI)
import client, pygame, moon_petal_inn as M
PROOF = os.environ.get("PROOF_DIR")
FAILS = []
def check(n, ok):
    print(("PASS " if ok else "FAIL ") + n)
    if not ok: FAILS.append(n)
def shot(g, name):
    if PROOF:
        os.makedirs(PROOF, exist_ok=True); pygame.image.save(g.screen, os.path.join(PROOF, name))
def key(g, k, mod=0):
    g.handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))
def click(g, pos):
    g.handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
M.PREFS = os.path.join(os.environ["HOME"], ".crownfall", "moon_petal.json")
g = client.GameClient(); g.state = "GAME"
mp = g.moon_petal
check("9 hotspots", len(mp.spots) == 9 and {s["name"] for s in mp.spots} == set(M.FAIRIES))
check("tab order floor L->R then loft", [s["name"] for s in mp.spots][-2:] == ["Aerin", "Rhosyn"] and [s["name"] for s in mp.spots][0] == "Ivria")
check("film frames extracted", M.film_available() and M.meta()["frames"] >= 330)
check("portraits for all 9", all(os.path.isfile(os.path.join(M.DIR, "portraits", n.lower() + ".jpg")) for n in M.FAIRIES))
# door: interactable exists; click path + walk-in path
g.interactables = [{"id": "moonpetal_inn_door", "kind": "flavour", "name": "Moonpetal Inn", "x": 21, "y": 82, "stand": [21, 83]}]
g.dungeon = None
check("is_door(21,82)", mp.is_door(21, 82) and not mp.is_door(21, 83))
g.player = {"id": 1, "name": "Tester", "x": 21, "y": 83}
g.fire_action({"type": "MOONPETAL_ENTER", "id": "moonpetal_inn_door"})
check("click/arrive -> film", mp.active and mp.mode == "film")
check("film skippable at once (Space/Esc/click)", mp.film.skip_after == 0.0)
mp.film.start -= 3.0; g.screen.fill((0, 0, 0)); mp.render(g.screen); shot(g, "film_3s.png")
mp.film.start -= 5.0; mp.render(g.screen); shot(g, "film_8s_subtitle.png")
key(g, pygame.K_SPACE); mp.film.ending -= 1.0; mp.render(g.screen)
check("skip -> room", mp.mode == "room")
mp.room_start -= 1; mp.render(g.screen); shot(g, "room_idle.png")
sw, sh = g.screen.get_size()
sel = next(i for i, s in enumerate(mp.spots) if s["name"] == "Selune")
r = mp.hit_rect(mp.spots[sel], sw, sh)
g.handle_game_event(pygame.event.Event(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0)))
check("hover Selune", mp.hover == sel)
mp.render(g.screen); shot(g, "room_hover_selune.png")
loft = [mp.hit_rect(s, sw, sh) for s in mp.spots if s["name"] in M.LOFT]
check("loft min 44px target", all(x.w >= 44 and x.h >= 44 for x in loft))
key(g, pygame.K_TAB); check("Tab focuses first", mp.focus == 0)
key(g, pygame.K_TAB); key(g, pygame.K_RETURN)
check("Enter talks to 2nd (Maelis)", mp.mode == "talk" and mp.talk == mp.spots[1]["name"])
key(g, pygame.K_ESCAPE); key(g, pygame.K_ESCAPE); check("Esc -> farewell -> room", mp.mode == "room")
click(g, r.center); check("click Selune -> talk", mp.mode == "talk" and mp.talk == "Selune")
mp.type_start = 0; mp.render(g.screen); shot(g, "talk_selune_greeting.png")
check("greeting = 4 topics + farewell", [x[0] for x in mp.replies()] == ["The Moon", "The Fae", "Throne & Realm", "Rumours", "Farewell"])
key(g, pygame.K_1); check("1 -> moon", mp.page == "moon")
mp.type_start = time.time() - 0.5; mp.render(g.screen); shot(g, "talk_typewriter.png")
key(g, pygame.K_RETURN); check("Enter completes typewriter", mp.typed_all())
key(g, pygame.K_1); check("Back -> greeting, moon seen", mp.page == "greeting" and mp.replies()[0][2] == "seen")
mp.type_start = 0; mp.render(g.screen); shot(g, "talk_selune_visited.png")
key(g, pygame.K_5); check("5 -> farewell", mp.page == "farewell")
mp.type_start = 0; mp.render(g.screen); shot(g, "talk_selune_farewell.png")
key(g, pygame.K_1); check("farewell -> room", mp.mode == "room")
for n in ("Nyx", "Aerin"):
    mp.open_talk(n); mp.type_start = 0; mp.render(g.screen); shot(g, f"talk_{n.lower()}.png")
mp.mode = "room"
key(g, pygame.K_ESCAPE); check("Esc in room leaves", not mp.active)
check("facing away from door", g._entity_facing.get(("p", 1)) == "front")
# second view: the film plays every time you walk to the door (David, 31 Oct)
mp.enter(); check("2nd entry same session plays film again", mp.mode == "film"); mp.leave()
mp._session_seen = False; mp.enter(); check("new session replays, skippable at once", mp.mode == "film" and mp.film.skip_after == 0.0)
mp.leave()
check("cursor talk on fairy hover", M._CURSOR["kind"] is None)
mp.enter(); mp.mode = "room"; mp.hover = 2; mp.render(g.screen); check("speech-bubble cursor over fairy", M._CURSOR["kind"] == "talk"); mp.leave()
check("cursor restored on leave", M._CURSOR["kind"] is None)
g.screen.fill((40, 60, 40)); M.draw_door_hover(g, pygame.Rect(560, 360, 80, 80)); shot(g, "door_hover_glow.png")
M.set_cursor("door"); check("door cursor", M._CURSOR["kind"] == "door"); M.set_cursor(None)
src = open(os.path.join(CLI, "client.py")).read()
check("client hooks", "MOONPETAL_ENTER" in src and "mp.is_door(nx, ny)" in src)
print("FAILS:", FAILS); sys.stdout.flush(); os._exit(1 if FAILS else 0)
