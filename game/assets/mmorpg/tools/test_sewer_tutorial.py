"""Optional sewer tutorial ('Below the Village').

Pure checks (map, stats, quest data) plus an in-process server check on 8799
with a temp copy of the test db: reward once (server-validated), death costs
nothing, 'Not now' adds the optional quest.

    CROWNFALL_DB_PATH=~/grokbot_tmp/testdb/world.db python3 tools/test_sewer_tutorial.py
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
import combat  # noqa: E402
import sewer_tutorial as S  # noqa: E402
import world_map as wm  # noqa: E402

FAILS = []


def check(name, fn):
    try:
        fn()
        print("PASS", name)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("FAIL", name, e)
        FAILS.append(name)


def _reach(tiles, start):
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and S.dungeon_walkable(tiles, *n):
                seen.add(n)
                q.append(n)
    return seen


def _adj(seen, p):
    return any((p[0] + dx, p[1] + dy) in seen for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def test_map():
    t = S.build_tiles()
    assert len(t) == S.H and len(t[0]) == S.W
    closed = _reach(t, S.SPAWN)
    assert S.EXIT in closed
    assert all((x, y) in closed for x in range(S.ROOM1[0], S.ROOM1[2] + 1) for y in (S.ROOM1[1] + 2,))
    assert not any(S.in_rect(x, y, S.ROOM2) for x, y in closed), "room 2 reachable with the web gate shut"
    for g in S.GATE:
        t[g[1]][g[0]] = wm.FLOOR
    opened = _reach(t, S.SPAWN)
    assert S.LADDER2 in opened
    for p in (S.CHEST1, S.CRATE1, S.CRATE2, S.REWARD_CHEST, *S.NEST):
        assert _adj(opened, p), p
    for kind, x, y in S.VILLAGE_RATS:
        assert content.MONSTERS[kind]["aggro_range"] == 0


def test_stats_fresh_bronze():
    kit = ("recruit_bronze_helmet", "recruit_bronze_body", "recruit_bronze_legs")
    P = {"attack": 1, "strength": 1, "defence": 1, "attack_bonus": 4, "strength_bonus": 5,
         "defence_bonus": sum(content.ITEMS[k].get("def_bonus", 0) for k in kit)}
    M = content.MONSTERS
    for k in ("village_rat", "sewer_rat", "sewer_spider", "spiderling"):
        assert combat.max_hit(M[k]["strength"]) <= 1, k
        assert M[k]["hp"] <= 8, k
    random.seed(7)

    def fight(wave, food, hp=10):
        foes = [{"t": k, "hp": M[k]["hp"], "n": 0.6} for k in wave]
        t = nxt = 0.0
        while foes:
            t += 0.6
            for f in foes[:2]:
                if t >= f["n"]:
                    hp -= combat.resolve_hit(M[f["t"]], P)[0]
                    f["n"] = t + M[f["t"]].get("attack_cooldown", 2.4)
            if hp <= 0:
                return False
            if hp <= 5 and food:
                hp, food, nxt = min(10, hp + 3), food - 1, t + 1.2
                continue
            if t >= nxt:
                foes[0]["hp"] -= combat.resolve_hit(P, M[foes[0]["t"]])[0]
                nxt = t + 1.2
                if foes[0]["hp"] <= 0:
                    foes.pop(0)
        return True
    r1 = sum(fight(["sewer_rat"] * 3, S.ENTRY_SHRIMP) for _ in range(1000)) / 1000
    r2 = sum(fight(["sewer_rat", "sewer_rat", "sewer_spider", "sewer_spider"], 6) for _ in range(1000)) / 1000
    print(f"  win rate room1 {r1:.3f}  room2 (+crate) {r2:.3f}")
    assert r1 >= 0.95 and r2 >= 0.85


def test_quest_and_items():
    q = content.QUESTS["below_the_village"]
    assert q.get("optional") and q.get("hidden_until_offered") and q["type"] == "sewer"
    assert content.QUESTS["wolves_on_the_pass"]["count"] == 4 if "wolves_on_the_pass" in content.QUESTS else True
    wolves = [d for d in content.QUESTS.values() if d.get("type") == "kill" and d.get("target") == "wolf"]
    assert wolves and min(d["count"] for d in wolves) == 4
    it = content.ITEMS["ratcatcher_charm"]
    assert it["name"] == "Rat-Tail Charm" and it.get("tradeable") is False
    assert os.path.isfile(os.path.join(ROOT, "assets", "items", "realistic", "ratcatcher_charm.png"))
    assert content.entrance_mouth_tiles(25, 30, "sewer_grate") == {(25, 30)}
    assert content.MONSTERS["sewer_rat"].get("quest_as") == "giant_rat"


def test_nest_hit_aggros():
    """Hitting the nest must wake spiders (locked) or hatch+aggro spiderlings (cleared)."""
    class FakeWS:
        pass

    class FakeDB:
        def set_quest_progress(self, *a, **k):
            pass

    class FakeWorld:
        db = FakeDB()

        def add_item_to_inventory(self, *a):
            return True

    class FakeSrv:
        WORLD = FakeWorld()
        log = type("L", (), {"warning": lambda *a, **k: None})()
        _id = 500
        sent = []

        def next_id(self):
            self._id += 1
            return self._id

        async def send(self, ws, t, **kw):
            self.sent.append((t, kw))

        class MonsterInstance:
            def __init__(self, mid, mtype, x, y, no_respawn=False):
                self.id = mid
                self.type = mtype
                self.x = x
                self.y = y
                self.spawn_x = x
                self.spawn_y = y
                self.alive = True
                d = content.MONSTERS[mtype]
                self.max_hp = d["hp"]
                self.hp = d["hp"]
                self.target_player_id = None
                self.home_room = None
                self.stats = None
                self.frozen_until = 0
                self.next_attack_at = 0
                self.patrol_steps_left = 0
                self.patrol_leg = ""
                self.no_respawn = no_respawn

    srv = FakeSrv()
    old = S._srv
    S._srv = lambda: srv
    try:
        class Sess:
            pass

        # Locked nest: room 2 still has spiders — they must aggro on disturb.
        s = Sess()
        s.player_id = 1
        s.ws = FakeWS()
        s.quests = {S.QUEST_ID: {"status": "active", "progress": S.B_STARTED | S.B_ENTERED | S.B_ROOM1}}
        s.dungeon = None
        s.x, s.y = 21, 4
        s.in_combat_with = None
        s.inventory = {}
        s.coins = 0
        s.hp = 10
        s.quest_log_dirty = False
        s.pet_id = None
        S.build(s)
        asyncio.get_event_loop().run_until_complete(S._hit_nest(s))
        spiders = [m for m in s.dungeon["monsters"].values() if m.type == "sewer_spider" and m.alive]
        assert spiders and all(m.target_player_id == s.player_id for m in spiders)
        assert s.in_combat_with and s.in_combat_with[0] == "monster"
        assert s.dungeon["sewer"]["nest_hits"] == 0

        # Cleared nest: first hit hatches spiderlings already targeting the player.
        s2 = Sess()
        s2.player_id = 2
        s2.ws = FakeWS()
        s2.quests = {
            S.QUEST_ID: {
                "status": "active",
                "progress": S.B_STARTED | S.B_ENTERED | S.B_ROOM1 | S.B_ROOM2,
            }
        }
        s2.dungeon = None
        s2.x, s2.y = 21, 4
        s2.in_combat_with = None
        s2.inventory = {}
        s2.coins = 0
        s2.hp = 10
        s2.quest_log_dirty = False
        s2.pet_id = None
        S.build(s2)
        for m in s2.dungeon["monsters"].values():
            m.alive = False
        asyncio.get_event_loop().run_until_complete(S._hit_nest(s2))
        kids = [m for m in s2.dungeon["monsters"].values() if m.alive and m.type == "spiderling"]
        assert len(kids) == 2
        assert all(m.target_player_id == s2.player_id for m in kids)
        assert s2.in_combat_with and s2.in_combat_with[0] == "monster"
        assert s2.dungeon["sewer"]["nest_hits"] == 1
        tiles = s2.dungeon["tiles"]
        for m in kids:
            assert S.dungeon_walkable(tiles, m.x, m.y)
            assert S.in_rect(m.x, m.y, S.ROOM2)
    finally:
        S._srv = old


STATE = {}


def _server():
    import importlib.util
    src = os.environ.get("CROWNFALL_DB_PATH") or os.path.expanduser("~/grokbot_tmp/testdb/world.db")
    if not os.path.isfile(src):     # box mirror keeps its copy next to the repo
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "testdb", "world.db")
    assert "server/world.db" not in src
    tmp = tempfile.mkdtemp(prefix="sewer_t_")
    db = os.path.join(tmp, "world.db")
    shutil.copy(src, db)
    spec = importlib.util.spec_from_file_location("_eq", os.path.join(ROOT, "tools", "test_equipment_screen.py"))
    EQ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(EQ)
    EQ._na.start_server(8799, db)
    os.chdir(CLI)
    STATE.update(EQ=EQ, srv=sys.modules["server"], tmp=tmp)


def _session(name):
    EQ, srv = STATE["EQ"], STATE["srv"]
    g = EQ.register(8799, name)
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
    S._srv().send = fake
    try:
        out = asyncio.new_event_loop().run_until_complete(coro)
    finally:
        srv.send = orig
    return out, sent


def test_server_rules():
    _server()
    srv = STATE["srv"]
    tag = int(time.time() * 1000) % 10**7
    # 'Not now' puts the optional quest in the log, without entering.
    g2, s2 = _session("sl%d" % tag)
    _run(S.offer_choice(s2, "later"))
    assert S.status(s2) == "active" and not s2.dungeon
    row = srv.WORLD.db.conn.execute(
        "SELECT status FROM quest_progress WHERE player_id=? AND quest_id=?", (s2.player_id, S.QUEST_ID)
    ).fetchone() if _has_table(srv, "quest_progress") else ("active",)
    assert row and row[0] == "active"
    # Reward: refused before the nest, granted once, refused after.
    g, s = _session("sr%d" % tag)
    _run(S.enter(s))
    assert S.here(s), s.dungeon
    ok, _ = _run(S.claim_reward(s))
    assert ok is False
    # Death in the sewer: full HP, back at the ladder, nothing lost, +3 shrimp.
    coins0 = s.coins
    sh0 = srv.WORLD.count_item(s, "cooked_shrimp")
    inv0 = {k: dict(v) for k, v in (s.inventory or {}).items() if v} if isinstance(s.inventory, dict) else None
    s.hp = 0
    s.x, s.y = 15, 15
    events = []
    _run(S.on_death(s, events, None))
    assert s.hp == s.max_hp() and (s.x, s.y) == S.SPAWN
    assert s.coins == coins0
    assert srv.WORLD.count_item(s, "cooked_shrimp") == sh0 + S.DEATH_SHRIMP
    assert events and events[0]["data"]["coins_lost"] == 0
    if inv0 is not None:
        for k, v in inv0.items():
            if v.get("item_id") != "cooked_shrimp":
                assert any(e and e.get("item_id") == v.get("item_id") for e in s.inventory.values()), v
    S._save_progress(s, S.progress(s) | S.B_ROOM1 | S.B_ROOM2 | S.B_NEST)
    coins1 = s.coins
    ok, sent = _run(S.claim_reward(s))
    assert ok is True and s.coins == coins1 + S.REWARD_COINS
    assert srv.WORLD.count_item(s, S.CHARM_ID) == 1
    assert S.title_for(s) == "Ratcatcher" and S.status(s) == "complete"
    assert any(t == "SEWER_REWARD" for t, _ in sent)
    assert abs(S.xp_mult(s, "attack") - 1.10) < 1e-6 and S.xp_mult(s, "woodcutting") == 1.0
    ok, _ = _run(S.claim_reward(s))
    assert ok is False and s.coins == coins1 + S.REWARD_COINS
    assert srv.WORLD.count_item(s, S.CHARM_ID) == 1
    # Even with the quest row reset, the db flag blocks a second payout.
    s.quests[S.QUEST_ID]["status"] = "active"
    ok, _ = _run(S.claim_reward(s))
    assert ok is False and srv.WORLD.count_item(s, S.CHARM_ID) == 1
    assert s.public_state().get("title_line") == "Ratcatcher"


def _has_table(srv, name):
    return bool(srv.WORLD.db.conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def main():
    check("map connectivity + web gate", test_map)
    check("stats beatable by fresh bronze", test_stats_fresh_bronze)
    check("quest, items, wolves 4, mouth tile", test_quest_and_items)
    check("nest hit aggros spiders / spiderlings", test_nest_hit_aggros)
    check("server: later quest, reward once, death no loss", test_server_rules)
    tmp = STATE.get("tmp")
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SEWER TUTORIAL TEST", "FAILED: " + ", ".join(FAILS) if FAILS else "PASSED")
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
