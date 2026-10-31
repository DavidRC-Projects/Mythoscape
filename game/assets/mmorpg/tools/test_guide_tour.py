"""Seraphine's first-5-minutes tour (GUIDE_AND_SEWER_PROPOSAL.md v2, section 4) + Equip all.

Throwaway server (free port, temp DB); never 8765 or the live world.db.
  * server: tour progress is per account and validated (one step at a time from the server's own
    step, unknown fields/actions refused, step 7/8 need the gear really worn, replay only after the
    tour ends, sewer choice is go/later only); the bronze set is given once per account, also on skip
    and "I've played before"; EQUIP_ALL only fills empty slots through the normal EQUIP checks
  * client (real server, fresh accounts): intro -> 11 steps, each dims the screen, rings one target
    and waits for that action (other clicks are ignored); chestplate tap, Equip all, eat, skills,
    sewer offer (choice recorded); resume after a disconnect; Skip with confirm; I've played before;
    replay from Settings
Set GUIDE_SHOTS=<dir> to save screenshots.
"""
import os, sys, time, asyncio, tempfile, importlib.util
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV, CLI = os.path.join(ROOT, "server"), os.path.join(ROOT, "client")
sys.path.insert(0, CLI)
spec = importlib.util.spec_from_file_location("_eq", os.path.join(ROOT, "tools", "test_equipment_screen.py"))
EQ = importlib.util.module_from_spec(spec); spec.loader.exec_module(EQ)
_na, pump, click = EQ._na, EQ.pump, EQ.click

RESULTS, STATE = [], {}
SHOTS = os.environ.get("GUIDE_SHOTS")
BRONZE = ("bronze_helmet", "bronze_body", "bronze_legs", "bronze_sword", "bronze_shield")


def check(name, fn):
    try:
        fn(); RESULTS.append((name, True)); print("ok  ", name, flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        RESULTS.append((name, False)); print("FAIL", name, repr(e), flush=True)


def shot(g, name):
    import pygame
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pygame.image.save(g.screen, os.path.join(SHOTS, name))
        print("shot", name, flush=True)


# ------------------------------------------------------------------ server unit checks
def _server():
    sys.path.insert(0, SRV)
    cwd = os.getcwd(); os.chdir(SRV)
    import server
    os.chdir(cwd)
    return server


def test_server_validation():
    server = _server()
    sent, saved, given = [], [], []

    async def fake_send(ws, t, **kw):
        sent.append((t, kw))

    class DB:
        def save_player_stats(self, pid, **kw): saved.append(kw)

    class S:
        def __init__(self, step=0, bronze=False):
            self.player_id, self.username, self.ws, self.char_name = 1, "t", None, "T"
            self.guide_tour, self.guide_bronze, self.sewer_choice = step, bronze, ""
            self.inventory, self.equipment, self.hp = {}, {}, 30
        def max_hp(self): return 30
        def full_state(self): return {}

    def add(session, item_id, qty):
        given.append(item_id)
        session.inventory[len(session.inventory)] = {"item_id": item_id, "qty": qty}
        return True

    real = (server.send, server.WORLD.db, server.WORLD.add_item_to_inventory)
    server.send, server.WORLD.db, server.WORLD.add_item_to_inventory = fake_send, DB(), add
    run = lambda s, m: asyncio.run(server.handle_guide_tour(s, m))
    try:
        s = S()
        # junk is refused, nothing written
        for bad in ({"type": "GUIDE_TOUR"}, {"type": "GUIDE_TOUR", "action": 5}, {"action": "teleport"},
                    {"action": "start", "hp": 99}, {"action": "advance", "step": 0}, {"action": "sewer", "choice": "go"},
                    {"action": "replay"}, "start", None):
            assert not run(s, bad), bad
        assert s.guide_tour == 0 and saved == []
        nolog = S(); nolog.player_id = None
        assert not run(nolog, {"action": "start"})
        assert run(s, {"action": "start"}) and s.guide_tour == 1
        assert not run(s, {"action": "start"})                       # only from 0
        assert not run(s, {"action": "advance", "step": 3})           # no jumping
        assert not run(s, {"action": "advance", "step": True})
        assert not run(s, {"action": "advance", "step": "1"})
        for n in range(1, 5):
            assert run(s, {"action": "advance", "step": n}), n
        assert s.guide_tour == 5 and s.guide_bronze and sorted(given) == sorted(list(BRONZE) + ["bread"])
        for n in (5, 6):
            assert run(s, {"action": "advance", "step": n})
        assert not run(s, {"action": "advance", "step": 7})          # chestplate not worn yet
        assert s.guide_tour == 7
        s.equipment["body"] = "bronze_body"
        assert run(s, {"action": "advance", "step": 7})
        assert not run(s, {"action": "advance", "step": 8})          # rest not worn
        s.equipment.update(helmet="bronze_helmet", legs="bronze_legs", weapon="bronze_sword", shield="bronze_shield")
        assert run(s, {"action": "advance", "step": 8}) and s.guide_tour == 9
        assert s.hp == 24                                             # eating step starts at 80% HP
        assert run(s, {"action": "advance", "step": 9}) and run(s, {"action": "advance", "step": 10})
        assert s.guide_tour == 11
        assert not run(s, {"action": "advance", "step": 11})          # the last step is the sewer choice
        assert not run(s, {"action": "sewer", "choice": "yes please"})
        assert not run(s, {"action": "played_before"})
        assert run(s, {"action": "sewer", "choice": "later"}) and s.guide_tour == 100 and s.sewer_choice == "later"
        assert {"sewer_choice": "later"} in saved and {"guide_tour": 100} in saved
        # replay restarts, gift is not given twice
        n_given = len(given)
        assert run(s, {"action": "replay"}) and s.guide_tour == 1
        for n in range(1, 6):
            run(s, {"action": "advance", "step": n})
        assert len(given) == n_given
        assert run(s, {"action": "skip"}) and s.guide_tour == 101 and not run(s, {"action": "skip"})
        # skip / I've played before still give the bronze set (once)
        k = S(step=3); given.clear()
        assert run(k, {"action": "skip"}) and k.guide_tour == 101 and len(given) == 6
        p = S(step=0); given.clear()
        assert run(p, {"action": "played_before"}) and p.guide_tour == 102 and len(given) == 6
        late = S(step=4)
        assert not run(late, {"action": "played_before"})           # only before the tour gets going
        # a full bag waits for room instead of losing the gift
        full = S(step=4)
        full.inventory = {i: {"item_id": "logs", "qty": 1} for i in range(200)}
        given.clear()
        assert run(full, {"action": "advance", "step": 4}) and not full.guide_bronze and given == []
        # EQUIP_ALL: refused with extra fields / logged out
        assert asyncio.run(server.handle_equip_all(S(), {"type": "EQUIP_ALL", "slot": "body"})) == 0
        lo = S(); lo.player_id = None
        assert asyncio.run(server.handle_equip_all(lo, {"type": "EQUIP_ALL"})) == 0
    finally:
        server.send, server.WORLD.db, server.WORLD.add_item_to_inventory = real


def test_db_migration():
    import sqlite3
    sys.path.insert(0, SRV)
    from database import Database
    d = tempfile.mkdtemp(prefix="guide_db_")
    path = os.path.join(d, "w.db")
    db = Database(path)
    cols = [r[1] for r in db.conn.execute("PRAGMA table_info(players)")]
    for c in ("guide_tour", "guide_bronze", "sewer_choice"):
        assert c in cols, c


# ------------------------------------------------------------------ client against a real server
def _fresh(port, name):
    g = EQ.register(port, name)
    oc = getattr(g, "outfitters", None)
    if oc is not None and getattr(oc, "active", False):
        oc.active = False
    g.needs_appearance = False     # the creator was saved (that is when the tour starts)
    g.dialogue = None
    pump(g, 20)
    return g


def _rect(g, key):
    return (getattr(g, "_tour", None) or {}).get("rects", {}).get(key)


def _step(g):
    return int((g.player or {}).get("guide_tour", -1))


def _wait_step(g, n, frames=600):
    return pump(g, frames, until=lambda: _step(g) == n)


def _target(g):
    import guide_tour
    return guide_tour.target_rect(g, _step(g))


def _close_stray_modals(g):
    for flag in ("show_wish", "show_bank", "show_shop"):
        if getattr(g, flag, False):
            setattr(g, flag, False)


def _walk_to(g, tx, ty, frames=900, hop=4):
    """Click toward the tile in short hops (never on clickable scenery), closing stray modals."""
    import guide_tour
    near = lambda: abs(int(g.player["x"]) - tx) <= 1 and abs(int(g.player["y"]) - ty) <= 1
    busy = guide_tour._busy_tiles(g)
    for _ in range(12):
        if near():
            return True
        px, py = int(g.player["x"]), int(g.player["y"])
        dx, dy = tx - px, ty - py
        sx = max(-hop, min(hop, dx)); sy = max(-hop, min(hop, dy))
        cands = [(px + sx, py + sy), (px + sx, py + sy + 1), (px + sx, py + sy - 1),
                 (px + sx - 1, py + sy), (px + sx, py), (px, py + sy)]
        goal = next((c for c in cands if c != (px, py) and (c == (tx, ty) or (c not in busy and not guide_tour._landmark(g, c)))
                     and g.tile_walkable(*c)), (tx, ty))
        r = guide_tour._tile_rect(g, *goal)
        click(g, r.center)
        pump(g, max(60, frames // 6), until=lambda: near() or (int(g.player["x"]), int(g.player["y"])) == goal)
        _close_stray_modals(g)
    return near()


def _bag_count(g, item_id):
    inv = (g.player or {}).get("inventory") or {}
    return sum(1 for e in inv.values() if e and e.get("item_id") == item_id)


def test_full_tour():
    import pygame
    import guide_tour
    port = STATE["port"]
    name = "gt%d" % (int(time.time() * 1000) % 10**7)
    g = _fresh(port, name)
    STATE["name"] = name
    assert _step(g) == 0 and guide_tour.visible(g), _step(g)
    pump(g, 5)
    shot(g, "01_intro.png")
    assert _rect(g, "start") and _rect(g, "played") and _rect(g, "skip")
    click(g, _rect(g, "start").center)
    assert _wait_step(g, 1)
    pump(g, 10)
    # step 1: dims + rings the ground marker; walk there
    st = g._tour
    assert st["marker"] is not None and _target(g) is not None
    shot(g, "02_step1_marker_dim_highlight.png")
    assert _walk_to(g, *st["marker"]), (g.player["x"], g.player["y"], st["marker"])
    assert _wait_step(g, 2)
    pump(g, 10)
    shot(g, "03_step2_trail_to_tamsin.png")
    n = guide_tour._npc(g, guide_tour.TAMSIN)
    _walk_to(g, int(n["x"]) - 1, int(n["y"]) + 1, 1500)
    assert _wait_step(g, 3), (_step(g), g.player["x"], g.player["y"], n)
    pump(g, 10)
    shot(g, "04_step3_talk_tamsin.png")
    if (g.dialogue or {}).get("npc_id") != "warden_tamsin" and _target(g):
        click(g, _target(g).center)
    assert pump(g, 900, until=lambda: (g.dialogue or {}).get("npc_id") == "warden_tamsin"), g.dialogue
    assert _wait_step(g, 4)
    assert not guide_tour.visible(g)            # waits while she talks
    g.dialogue = None
    pump(g, 10)
    assert guide_tour.visible(g)
    # one action at a time: a click on something else (Skills) is swallowed
    sk = g.hud_rects["skills"]
    click(g, sk.center); pump(g, 10)
    assert not getattr(g, "show_skills", False) and _step(g) == 4
    shot(g, "05_step4_quest_log.png")
    click(g, _target(g).center)
    assert _wait_step(g, 5)
    pump(g, 10)
    # the gift arrives with the inventory step
    assert pump(g, 300, until=lambda: all(_bag_count(g, i) for i in BRONZE)), g.player.get("inventory")
    assert _bag_count(g, "bread")
    shot(g, "06_step5_gift_inventory.png")
    click(g, _target(g).center)
    assert _wait_step(g, 6)
    pump(g, 10)
    shot(g, "07_step6_equipment_button.png")
    click(g, _target(g).center)
    assert pump(g, 100, until=lambda: g.show_equipment)
    assert _wait_step(g, 7)
    pump(g, 15)
    tr = _target(g)
    cells = g.inventory_slot_rects()
    body_idx = next(int(k) for k, e in g.player["inventory"].items() if e and e.get("item_id") == "bronze_body")
    assert tr == cells[body_idx], (tr, cells.get(body_idx))
    shot(g, "08_step7_tap_chestplate.png")
    click(g, tr.center)
    pump(g, 3)
    shot(g, "09_step7_chestplate_flash.png")
    assert pump(g, 300, until=lambda: g.player["equipment"].get("body") == "bronze_body")
    assert _wait_step(g, 8)
    pump(g, 10)
    assert _target(g) == g.equip_all_rect
    shot(g, "10_step8_equip_all.png")
    click(g, g.equip_all_rect.center)
    pump(g, 3)
    shot(g, "11_step8_equip_all_flash.png")
    eq_ok = lambda: all(g.player["equipment"].get(s) for s in ("helmet", "body", "legs", "weapon", "shield"))
    assert pump(g, 400, until=eq_ok), g.player["equipment"]
    pump(g, 40)
    shot(g, "12_step8_look_at_you.png")
    assert _wait_step(g, 9, 900)
    g.show_equipment = False
    pump(g, 20)
    hp0 = int(g.player["hp"])
    assert hp0 < int(g.player["max_hp"]) or int(g.player["max_hp"]) <= 1, (hp0, g.player["max_hp"])
    shot(g, "13_step9_health_and_eat.png")
    click(g, _target(g).center)
    pump(g, 200, until=lambda: _step(g) == 10)
    if _step(g) != 10:   # the Eat button may want a pick: click the bread itself
        b = guide_tour._bag_rect(g, "bread")
        click(g, b.center)
    assert _wait_step(g, 10, 900), (_step(g), g.player["hp"])
    pump(g, 10)
    shot(g, "14_step10_skills.png")
    click(g, _target(g).center)
    assert _wait_step(g, 11)
    g.show_skills = False
    pump(g, 10)
    shot(g, "15_step11_sewer_offer.png")
    assert _rect(g, "go") and _rect(g, "later")
    click(g, _rect(g, "later").center)
    assert _wait_step(g, 100)
    assert g.player.get("sewer_choice") == "later"
    pump(g, 20)
    shot(g, "16_tour_done_farewell.png")
    STATE["g"] = g


def test_resume_skip_replay():
    import pygame
    import guide_tour
    g = STATE["g"]
    port, name = STATE["port"], STATE["name"]
    # replay from Settings
    g.show_help = True
    pump(g, 5)
    assert g.guide_tour_replay_rect is not None
    shot(g, "17_settings_replay_button.png")
    click(g, g.guide_tour_replay_rect.center)
    assert _wait_step(g, 1)
    pump(g, 10)
    shot(g, "18_replay_step1.png")
    bronze_before = sum(_bag_count(g, i) for i in BRONZE) + sum(1 for v in g.player["equipment"].values() if v in BRONZE)
    # skip asks first
    click(g, _rect(g, "skip").center); pump(g, 5)
    assert g._tour["confirm_skip"]
    shot(g, "19_skip_confirm.png")
    click(g, _rect(g, "skip_no").center); pump(g, 5)
    assert not g._tour["confirm_skip"] and _step(g) == 1
    # resume after a disconnect: replay is on step 1; push it to step 2, drop, log back in
    g.net.send("GUIDE_TOUR", action="advance", step=1)
    assert _wait_step(g, 2)
    g.logout(); pump(g, 60)
    for attempt in range(4):        # a mid-fight logout lingers ~10s server-side
        try:
            g = EQ.login(port, name)
            break
        except AssertionError:
            if attempt == 3:
                raise
            time.sleep(6)
    g.needs_appearance = False
    pump(g, 20)
    # resumes at saved step 2; already standing by Tamsin, so step 2 may complete itself -> 3
    assert _step(g) in (2, 3) and guide_tour.visible(g), _step(g)
    shot(g, "20_resumed_after_disconnect.png")
    click(g, _rect(g, "skip").center); pump(g, 5)
    click(g, _rect(g, "skip_yes").center)
    assert _wait_step(g, 101)
    bronze_after = sum(_bag_count(g, i) for i in BRONZE) + sum(1 for v in g.player["equipment"].values() if v in BRONZE)
    assert bronze_after == bronze_before, (bronze_before, bronze_after)    # never given twice
    pump(g, 10)
    shot(g, "21_after_skip.png")
    g.logout(); pump(g, 30)


def test_played_before():
    import guide_tour
    port = STATE["port"]
    g = _fresh(port, "gp%d" % (int(time.time() * 1000) % 10**7))
    assert _step(g) == 0
    pump(g, 5)
    pygame = __import__("pygame")
    pygame.mouse.set_pos(_rect(g, "played").center); pump(g, 3)
    shot(g, "22_intro_hover_played_before.png")
    click(g, _rect(g, "played").center)
    assert _wait_step(g, 102)
    assert pump(g, 200, until=lambda: all(_bag_count(g, i) for i in BRONZE))   # skippers get bronze too
    assert not guide_tour.visible(g)
    # Equip all fills everything in one go (server-validated equips)
    g.show_equipment = True; pump(g, 10)
    click(g, g.equip_all_rect.center)
    assert pump(g, 400, until=lambda: all(g.player["equipment"].get(s) == i for s, i in
                                          zip(("helmet", "body", "legs", "weapon", "shield"), BRONZE))), g.player["equipment"]
    pump(g, 30)
    shot(g, "23_played_before_equip_all.png")
    g.logout(); pump(g, 30)


def main():
    import pygame
    pygame.init()
    # start the throwaway server FIRST so the server module binds to the temp db, never a real one
    # smoke mode: GUIDE_PORT=8799 GUIDE_DB=<copy of a real world.db> (never the live db / 8765)
    port = int(os.environ.get("GUIDE_PORT") or _na.free_port())
    assert port != 8765, "never the live server port"
    db = os.environ.get("GUIDE_DB") or os.path.join(tempfile.mkdtemp(prefix="guide_srv_"), "world.db")
    assert "server/world.db" not in os.path.abspath(db), "never the live world.db"
    _na.start_server(port, db)
    STATE.update(port=port, db=db)
    os.chdir(CLI)
    check("server_validation", test_server_validation)
    check("db_migration", test_db_migration)
    check("full_tour", test_full_tour)
    if "g" in STATE:
        check("resume_skip_replay", test_resume_skip_replay)
    check("played_before_and_equip_all", test_played_before)
    ok = sum(1 for _, r in RESULTS if r)
    print(f"{ok}/{len(RESULTS)} guide tour tests passed", flush=True)
    os._exit(0 if ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
