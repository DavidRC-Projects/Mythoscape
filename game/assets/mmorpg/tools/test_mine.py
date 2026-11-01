"""Deepdelve Mine (MINE_SPEC.md): map, collision, levels, lift gauntlets, Heartstone vein.

In-process server on 8798 with a temp copy of the test db (never the live world.db).

    CROWNFALL_DB_PATH=/path/to/test/world.db python3 tools/test_mine.py
"""
import asyncio
import os
import random
import shutil
import sys
import tempfile
import time
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV_DIR = os.path.join(ROOT, "server")
CLI = os.path.join(ROOT, "client")
sys.path.insert(0, SRV_DIR)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import content  # noqa: E402
import deepdelve_layout as L  # noqa: E402
import deepdelve as D  # noqa: E402
import world_map as wm  # noqa: E402

FAILS = []
STATE = {}
PORT = 8798


def check(name, fn):
    try:
        fn()
        print("PASS", name)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("FAIL", name, e)
        FAILS.append(name)


def _reach(walk, start):
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and walk(*n):
                seen.add(n)
                q.append(n)
    return seen


def _adj(seen, p):
    return any((p[0] + dx, p[1] + dy) in seen for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))


def _grid():
    # The server's live grid (generate_world plus every later stamp) is what clients receive.
    if "srv" not in STATE:
        _server()
    return STATE["srv"].WORLD.grid


def _walk(g):
    return lambda x, y: wm.is_walkable(g, x, y)


def test_levels():
    lv = {k: content.MONSTERS[k]["level"] for k in
          ("tunnel_scavenger", "ember_crawler", "scavenger_foreman", "mithril_wraith", "shackled_wraith",
           "adamant_golem", "ancient_adamant_golem", "heartstone_colossus")}
    print("   levels", lv)
    assert 240 <= lv["adamant_golem"] <= 250, lv
    assert lv["ancient_adamant_golem"] > lv["adamant_golem"] + 10
    assert lv["heartstone_colossus"] >= lv["ancient_adamant_golem"] + 50
    assert content.MONSTERS["heartstone_colossus"].get("boss")
    order = ["tunnel_scavenger", "ember_crawler", "scavenger_foreman", "mithril_wraith", "shackled_wraith",
             "adamant_golem"]
    assert [lv[k] for k in order] == sorted(lv[k] for k in order)
    for k in lv:
        for d in content.MONSTERS[k]["drops"]:
            items = d[0] if isinstance(d[0], tuple) else (d[0],)
            assert all(i in content.ITEMS for i in items), (k, d)
    for f in (1, 2, 3):
        for m in D.GAUNTLETS[f]:
            assert m in content.MONSTERS


def test_ore_values():
    Y = content.RESOURCE_YIELDS
    for t in ("copper_rock", "tin_rock", "iron_rock", "coal_rock", "mithril_rock", "adamantite_rock",
              "gem_vein", "heart_vein"):
        assert t in Y and t in content.RESOURCE_LABELS, t
    assert L.FLOOR_GATE == {1: Y["iron_rock"]["level_req"], 2: Y["mithril_rock"]["level_req"],
                            3: Y["adamantite_rock"]["level_req"]}
    assert Y["heart_vein"]["item"] == "adamantite_ore" and Y["heart_vein"]["depletion_chance"] == 0
    rng = random.Random(3)
    got = {D.gather_item("gem_vein", Y["gem_vein"], rng) for _ in range(400)}
    assert got <= {"sapphire", "emerald", "ruby", "diamond"} and len(got) == 4, got
    # every gem / ore given exists and smithing consumes the bar ores
    for t in Y:
        if Y[t]["skill"] == "mining":
            assert Y[t]["item"] in content.ITEMS, t


def test_map_and_collision():
    g = _grid()
    w = _walk(g)
    bx0, by0, bx1, by1 = L.BOX
    # Entrance gap in the north wall, everything else on the ring solid.
    for x in range(bx0, bx1 + 1):
        assert w(x, by0) == (x in L.DOOR_X), x
    outside = _reach(lambda x, y: w(x, y), (L.DOOR_X[1], by0 - 1))
    yard = {p for p in outside if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1}
    for key in (1, 2, 3):
        cx0, cy0, cx1, cy1 = L.CHAMBERS[key]
        assert not any(cx0 <= x <= cx1 and cy0 <= y <= cy1 for x, y in yard), f"chamber {key} walkable from yard"
    for pad in L.LIFT_PADS.values():
        assert pad in yard, pad
    for pad in L.B0_ARRIVE.values():
        assert pad in yard
    for rx, ry, _t in L.YARD_ROCKS + L.B0_ROCKS:
        assert not w(rx, ry) and _adj(yard, (rx, ry)), (rx, ry)
    BC = {i.rsplit("_", 1)[-1]: (x, y) for i, x, y in L.BANK_CHESTS}
    banks = {(it["x"], it["y"]) for it in content.INTERACTABLES if it.get("kind") == "bank"}
    assert set(BC.values()) <= banks
    for c in ("yard", "b0"):
        assert _adj(yard, BC[c])
    for key in (1, 2, 3):
        ch = _reach(w, L.CHAMBER_ARRIVE[key])
        cx0, cy0, cx1, cy1 = L.CHAMBERS[key]
        assert all(cx0 <= x <= cx1 and cy0 <= y <= cy1 for x, y in ch), f"chamber {key} leaks"
        assert L.LIFT_UP[key] in ch
        assert _adj(ch, BC[f"f{key}"])
        for rx, ry, _t in L.CHAMBER_ROCKS[key]:
            assert not w(rx, ry) and _adj(ch, (rx, ry)), (key, rx, ry)
    ch3 = _reach(w, L.CHAMBER_ARRIVE[3])
    assert L.HEART_DOOR in ch3 and L.HEART_DOOR_STAND in ch3
    for hx, hy, _t in L.HEART_VEIN:
        assert _adj(ch3, (hx, hy))
    # Two-way: every step that is legal one way is legal back (no one-way tiles in the mine).
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            for dx, dy in ((1, 0), (0, 1)):
                a, b = w(x, y), w(x + dx, y + dy)
                if a and b:
                    continue
                # blocked steps: neither side can cross
                assert not (a and b)
    # Blocking props are solid, decorative ones are walkable.
    for x, y, kind, blocks in L.PROPS:
        assert w(x, y) != bool(blocks) or kind in ("rock",), (x, y, kind, blocks)


def test_gauntlet_tiles():
    t = D.gauntlet_tiles()
    w = lambda x, y: D.walkable(t, x, y)  # noqa: E731
    closed = _reach(w, D.G_SPAWN)
    assert D.G_ENTRY_EXIT in closed and D.G_CAGE not in closed
    for i, room in enumerate(D.G_ROOMS):
        assert any(D.in_rect(x, y, room) for x, y in closed) == (i == 0)
    for dx, dy in D.G_DOORS:
        t[dy][dx] = wm.FLOOR
    assert D.G_CAGE in _reach(w, D.G_SPAWN)
    c = D.colossus_tiles()
    assert D.C_EXIT in _reach(lambda x, y: D.walkable(c, x, y), D.C_SPAWN)


def _server():
    import importlib.util
    src = os.environ.get("CROWNFALL_DB_PATH") or os.path.expanduser("~/grokbot_tmp/testdb/world.db")
    assert "server/world.db" not in src and os.path.isfile(src), src
    tmp = tempfile.mkdtemp(prefix="mine_t_")
    db = os.path.join(tmp, "world.db")
    shutil.copy(src, db)
    spec = importlib.util.spec_from_file_location("_eq", os.path.join(ROOT, "tools", "test_equipment_screen.py"))
    EQ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(EQ)
    EQ._na.start_server(PORT, db)
    os.chdir(CLI)
    STATE.update(EQ=EQ, srv=sys.modules["server"], tmp=tmp)


def _session(name):
    EQ, srv = STATE["EQ"], STATE["srv"]
    g = EQ.register(PORT, name)
    EQ.pump(g, 20)
    s = next(s for s in srv.WORLD.sessions.values() if getattr(s, "char_name", None) == g.player["name"])
    return g, s


def _run(coro):
    srv = STATE["srv"]
    sent = []
    orig = srv.send

    async def fake(ws, t, **kw):
        sent.append((t, kw))
    srv.send = fake
    try:
        out = asyncio.new_event_loop().run_until_complete(coro)
    finally:
        srv.send = orig
    return out, sent


def _texts(sent):
    return " | ".join(kw.get("text", "") or kw.get("message", "") for _t, kw in sent)


def test_server_flow():
    if "srv" not in STATE:
        _server()
    srv = STATE["srv"]
    in_box = [m for m in srv.WORLD.monsters.values()
              if L.BOX[0] <= m.x <= L.BOX[2] and L.BOX[1] <= m.y <= L.BOX[3]]
    assert not in_box, [(m.type, m.x, m.y) for m in in_box]
    for rx, ry, t in L.ALL_ROCKS:
        assert srv.WORLD.resource_nodes[(rx, ry)]["type"] == t, (rx, ry, t)
    tag = int(time.time() * 1000) % 10**7
    _g, s = _session("mn%d" % tag)
    # Fresh miner: the floor-1 cage refuses.
    s.x, s.y = L.LIFT_PADS[1]
    moved, sent = _run(D.on_overworld_step(s))
    assert not moved and not s.dungeon and "scratch" in _texts(sent)
    import combat
    s.xp["mining"] = combat.xp_for_level(60)
    assert s.level("mining") >= 46, s.level("mining")
    moved, sent = _run(D.on_overworld_step(s))
    assert moved and D.here(s) and D.state(s)["kind"] == "gauntlet"
    assert any(t == "DUNGEON_ENTER" for t, _ in sent)
    mons = sorted(s.dungeon["monsters"].values(), key=lambda m: m.spawn_x)
    assert [m.type for m in mons] == list(D.GAUNTLETS[1])
    t = s.dungeon["tiles"]
    for i, m in enumerate(mons):
        dx, dy = D.G_DOORS[i]
        assert t[dy][dx] == wm.WALL
        m.alive = False
        m.hp = 0
        _r, sent = _run(D.on_kill(s, m))
        assert t[dy][dx] == wm.FLOOR and any(tt == "DUNGEON_TILES" for tt, _ in sent)
    s.x, s.y = D.G_CAGE
    left, _ = _run(D.on_step(s))
    assert left and not s.dungeon and (s.x, s.y) == L.CHAMBER_ARRIVE[1], (s.x, s.y)
    assert D.unlocked(s, 1) and not D.unlocked(s, 2)
    # Up and straight back down: no gauntlet the second time.
    s.x, s.y = L.LIFT_UP[1]
    _run(D.on_overworld_step(s))
    assert (s.x, s.y) == L.B0_ARRIVE[1]
    s.x, s.y = L.LIFT_PADS[1]
    _run(D.on_overworld_step(s))
    assert not s.dungeon and (s.x, s.y) == L.CHAMBER_ARRIVE[1]
    # Heart door needs floor 3; the vein needs a fresh Colossus kill.
    s.x, s.y = L.HEART_DOOR
    _run(D.on_overworld_step(s))
    assert not s.dungeon and (s.x, s.y) == L.HEART_DOOR_STAND
    assert D.can_gather(s, "heart_vein") and D.can_gather(s, "adamantite_rock") is None
    D.unlock(s, 3)
    s.x, s.y = L.HEART_DOOR
    _run(D.on_overworld_step(s))
    assert D.here(s) and D.state(s)["kind"] == "colossus"
    boss = next(iter(s.dungeon["monsters"].values()))
    assert boss.type == D.COLOSSUS
    boss.alive = False
    _run(D.on_kill(s, boss))
    assert D.can_gather(s, "heart_vein") is None
    s.x, s.y = D.C_EXIT
    _run(srv.handle_leave_dungeon(s, silent=True))
    assert (s.x, s.y) == L.HEART_DOOR_STAND, (s.x, s.y)
    assert not D.heart_open(s, now=time.time() + D.HEART_OPEN_S + 5)


# --------------------------------------------------------------------------- v2: levels
DEEP_ORES = ("mithril_rock", "adamantite_rock")


def test_ore_locations():
    """Ground level keeps the lower ores; mithril only on Level 2, adamantite only on Level 3."""
    lv_of = {}
    for x, y, t in L.ALL_ROCKS:
        lv_of.setdefault(t, set()).add(L.level_at(x, y))
    assert lv_of["mithril_rock"] == {2}, lv_of
    assert lv_of["adamantite_rock"] == {3}, lv_of
    for t in ("copper_rock", "tin_rock", "iron_rock", "coal_rock"):
        assert lv_of[t] == {1}, (t, lv_of[t])
    assert L.FLOOR_GATE[2] == content.RESOURCE_YIELDS["mithril_rock"]["level_req"]
    assert L.FLOOR_GATE[3] == content.RESOURCE_YIELDS["adamantite_rock"]["level_req"]
    g = _grid()
    bx0, by0, bx1, by1 = L.BOX
    deep_tiles = (wm.MITHRIL_ORE, wm.ADAMANTITE_ORE)
    stray = [(x, y) for y in range(by0 - 6, by1 + 7) for x in range(bx0 - 8, bx1 + 9)
             if 0 <= y < len(g) and 0 <= x < len(g[0]) and g[y][x] in deep_tiles
             and L.level_at(x, y) not in (2, 3)]
    assert not stray, stray
    nodes = STATE["srv"].WORLD.resource_nodes
    for (x, y), n in nodes.items():
        if n["type"] in DEEP_ORES and bx0 - 8 <= x <= bx1 + 8 and by0 - 6 <= y <= by1 + 6:
            want = 2 if n["type"] == "mithril_rock" else 3
            assert L.level_at(x, y) == want, (x, y, n["type"])


def test_level_map():
    """Yard and B0 join on foot (west slope); the shaft tiles are the way down from both sides."""
    g = _grid()
    w = _walk(g)
    trig = set(L.TUNNEL_DOWN)
    walk_no_tunnel = lambda x, y: w(x, y) and (x, y) not in trig  # noqa: E731
    top = _reach(walk_no_tunnel, L.TUNNEL_TOP_STAND)
    assert L.TUNNEL_BOTTOM_STAND in top, "yard and B0 not joined on foot"
    assert L.LIFT_PADS[1] in top
    for xy, back in L.TUNNEL_DOWN.items():
        assert w(*xy) and back in top, (xy, back)
    assert _adj(top, (65, 105)) and _adj(top, (65, 106))
    ch2 = _reach(w, L.CHAMBER_ARRIVE[2])
    assert L.SHAFT_DOWN in ch2 and L.SHAFT_DOWN_STAND in ch2 and L.LIFT_UP[2] in ch2
    assert not (ch2 & top)
    for x, y, _t, _s in L.SIGNPOSTS:
        assert w(x, y), (x, y)
    assert len(set(L.LIFT_PADS)) == 1, "B0 lifts to levels 2/3 should be gone"


def test_level_travel():
    """Down the shaft to Level 2, down the ladder to Level 3, and back up each way."""
    if "srv" not in STATE:
        _server()
    import combat
    tag = int(time.time() * 1000) % 10**7
    _g, s = _session("lv%d" % tag)
    # Too low: refused at the shaft, put back on the side you came from.
    for xy, back in ((65, 105), L.TUNNEL_TOP_STAND), ((69, 106), L.TUNNEL_BOTTOM_STAND):
        s.x, s.y = xy
        moved, sent = _run(D.on_overworld_step(s))
        assert moved and not s.dungeon and (s.x, s.y) == back, (xy, s.x, s.y)
        assert "Mining 40" in _texts(sent)
    s.xp["mining"] = combat.xp_for_level(42)
    # First time down: the Level 2 gauntlet (wraiths), then Level 2.
    s.x, s.y = 67, 105
    moved, _ = _run(D.on_overworld_step(s))
    assert moved and D.here(s) and D.state(s)["mine_floor"] == 2
    assert tuple((s.dungeon["return_x"], s.dungeon["return_y"])) == L.UP_ARRIVE[2]
    s.x, s.y = D.G_CAGE
    _run(D.on_step(s))
    assert not s.dungeon and (s.x, s.y) == L.CHAMBER_ARRIVE[2] and L.level_at(s.x, s.y) == 2
    # Up again, then straight down (no gauntlet the second time).
    s.x, s.y = L.LIFT_UP[2]
    _run(D.on_overworld_step(s))
    assert (s.x, s.y) == L.TUNNEL_BOTTOM_STAND and L.level_at(s.x, s.y) == 1
    s.x, s.y = 66, 106
    _run(D.on_overworld_step(s))
    assert not s.dungeon and (s.x, s.y) == L.CHAMBER_ARRIVE[2]
    # Level 2 -> Level 3 ladder: Mining 46 gate.
    s.x, s.y = L.SHAFT_DOWN
    moved, sent = _run(D.on_overworld_step(s))
    assert moved and not s.dungeon and (s.x, s.y) == L.SHAFT_DOWN_STAND and "Mining 46" in _texts(sent)
    s.xp["mining"] = combat.xp_for_level(50)
    s.x, s.y = L.SHAFT_DOWN
    _run(D.on_overworld_step(s))
    assert D.here(s) and D.state(s)["mine_floor"] == 3
    assert [m.type for m in sorted(s.dungeon["monsters"].values(), key=lambda m: m.spawn_x)] == list(D.GAUNTLETS[3])
    assert tuple((s.dungeon["return_x"], s.dungeon["return_y"])) == L.SHAFT_DOWN_STAND
    s.x, s.y = D.G_CAGE
    _run(D.on_step(s))
    assert (s.x, s.y) == L.CHAMBER_ARRIVE[3] and L.level_at(s.x, s.y) == 3
    s.x, s.y = L.LIFT_UP[3]
    _run(D.on_overworld_step(s))
    assert (s.x, s.y) == L.SHAFT_DOWN_STAND and L.level_at(s.x, s.y) == 2
    s.x, s.y = L.SHAFT_DOWN
    _run(D.on_overworld_step(s))
    assert not s.dungeon and (s.x, s.y) == L.CHAMBER_ARRIVE[3]
    # Mining there works and gives the deep ore.
    assert D.can_gather(s, "adamantite_rock") is None


def test_client_levels():
    """Client: other levels are hidden, rails meet at a curved junction, painted husky draws."""
    import importlib
    sys.path.insert(0, CLI)
    import pygame
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    DC = importlib.import_module("deepdelve_client")
    assert DC._masked(2, 78, 124) and DC._masked(2, 60, 110) and not DC._masked(2, 66, 124)
    assert DC._masked(3, 66, 124) and not DC._masked(3, 78, 124)
    assert DC._masked(1, 66, 124) and DC._masked(1, 78, 124) and not DC._masked(1, 55, 124)
    assert not DC._masked(1, 60, 110)
    pts = set(L.RAILS)
    assert (68, 112) not in pts and (67, 112) in pts and (67, 111) in pts
    for p_ in ("props/signpost.png", "props/shaft_down.png", "props/crystals.png"):
        assert DC._raw(p_) is not None, p_
    P = importlib.import_module("pets_hd_client")
    surf = pygame.Surface((200, 200), pygame.SRCALPHA)
    for face in ("n", "e", "s", "w"):
        surf.fill((0, 0, 0, 0))
        assert P.draw(surf, "pet_husky", 100, 180, 88, 1.0, facing=face)
        bb = surf.get_bounding_rect()
        assert bb.h > 60 and bb.bottom >= 170, (face, bb)


def main():
    check("monster levels in band, drops real", test_levels)
    check("ore values match mining table", test_ore_values)
    check("map: sealed chambers, reach, two-way collision", test_map_and_collision)
    check("gauntlet + arena tiles", test_gauntlet_tiles)
    check("server: gate, gauntlet unlock, lifts, heart vein", test_server_flow)
    check("v2: ore locations by level", test_ore_locations)
    check("v2: level map (west slope, shaft, ladder)", test_level_map)
    check("v2: travel down and up between levels", test_level_travel)
    check("v2: client level mask, rails, painted husky", test_client_levels)
    tmp = STATE.get("tmp")
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print("FAILED:", FAILS) if FAILS else print("ALL PASS")
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
