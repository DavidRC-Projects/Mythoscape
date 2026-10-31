"""Rat attack stall (playtest round 3): a click-attack on a wandering rat must keep
re-pathing until in reach, then send ATTACK; an unreachable foe times out with a message.
RAT_CHASE_CLIENT=<dir> tests a scratch client.py (default: this tree's client/)."""
import os, sys, time, importlib.util
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "client")
for p in (os.path.join(os.path.dirname(ROOT), "characters"), os.path.join(ROOT, "shared"), os.path.join(ROOT, "server"), CLI):
    sys.path.insert(0, p)
os.chdir(CLI)
src = os.path.join(os.environ.get("RAT_CHASE_CLIENT") or CLI, "client.py")
spec = importlib.util.spec_from_file_location("client", src)
client = importlib.util.module_from_spec(spec); sys.modules["client"] = client; spec.loader.exec_module(client)
import world_map as wm  # noqa

GRASS = next(iter(wm.WALKABLE_TILES))
WALL = next(t for t in range(0, 300) if t not in wm.WALKABLE_TILES)


class Net:
    def __init__(self): self.sent = []
    def send(self, t, **k): self.sent.append((t, k))


def make(w=30, h=20):
    g = client.GameClient()
    g.net = Net(); g.state = "GAME"; g.dungeon = None
    g.tiles = [[GRASS] * w for _ in range(h)]; g.world_w = w
    g.player = {"id": "p1", "x": 5, "y": 10, "equipment": {"weapon": "bronze_sword"}, "hp": 10}
    g.players = {"p1": dict(g.player)}
    g.monsters = {}; g.chat_log = []
    return g


def run(g, frames, each=None):
    for i in range(frames):
        if each: each(i)
        g._next_walk_at = 0; g._move_deny_until = 0
        g.update_walk()
        g.players["p1"].update(x=g.player["x"], y=g.player["y"])
        if any(t == "ATTACK" for t, _ in g.net.sent):
            return i
    return None


def test_parks_out_of_reach_then_attacks():
    """Root cause: flank stand-offs at 3-4 tiles were valid path goals but out of
    melee reach (2); arriving there left pending ATTACK with no path forever."""
    g = make()
    g.monsters = {7: {"id": 7, "type": "giant_rat", "x": 10, "y": 10, "alive": True}}
    g.tiles[10][8] = WALL; g.tiles[10][12] = WALL      # gap-2 flanks blocked
    g.player.update(x=7, y=10)                        # on the gap-3 flank tile
    g.pending_action = {"type": "ATTACK", "target_id": 7}; g.walk_path = []
    assert run(g, 40) is not None, "stalled at stand-off tile"


def test_wandering_rat_is_chased():
    g = make()
    rat = {"id": 7, "type": "giant_rat", "x": 15, "y": 10, "alive": True}
    g.monsters = {7: rat}
    g.begin_attack(7)
    def wander(i):
        if i % 2 == 0 and rat["x"] < 26: rat["x"] += 1; rat["y"] = 10 + (i // 2) % 3
    assert run(g, 80, wander) is not None


def test_unreachable_times_out_with_message():
    g = make()
    g.monsters = {7: {"id": 7, "type": "giant_rat", "x": 20, "y": 10, "alive": True}}
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if max(abs(dx), abs(dy)) == 3: g.tiles[10 + dy][20 + dx] = WALL
    g.combat_target_id = 7
    g.pending_action = {"type": "ATTACK", "target_id": 7}; g.walk_path = []
    g._chase_started_at = time.time() - client.GameClient.ATTACK_CHASE_TIMEOUT - 1
    run(g, 3)
    assert g.pending_action is None and g.combat_target_id is None
    assert any("catch" in str(l).lower() for l in g.chat_log), g.chat_log[-3:]


def test_engaged_rat_wanders_off_is_rechased():
    """Live repro (round 3): ATTACK accepted, combat_target_id set, pending cleared; the rat
    wanders out of reach, the server stays silent, and the client stood still until idle logout."""
    g = make()
    rat = {"id": 7, "type": "giant_rat", "x": 7, "y": 10, "alive": True}
    g.monsters = {7: rat}; g.combat_target_id = 7; g.pending_action = None; g.walk_path = []
    rat["x"], rat["y"] = 12, 12                        # wandered off mid-fight
    t0 = time.time()
    hit = None
    for i in range(200):
        g._next_walk_at = 0; g._move_deny_until = 0; g.update_walk()
        g.players["p1"].update(x=g.player["x"], y=g.player["y"])
        if any(t == "ATTACK" for t, _ in g.net.sent): hit = i; break
        time.sleep(0.01)
    assert hit is not None, ("never re-chased", g.player_xy())


if __name__ == "__main__":
    bad = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try: f(); print("PASS", n)
            except Exception as e: bad += 1; print("FAIL", n, repr(e))
    print("ALL PASSED" if not bad else f"{bad} FAILED"); sys.exit(1 if bad else 0)
