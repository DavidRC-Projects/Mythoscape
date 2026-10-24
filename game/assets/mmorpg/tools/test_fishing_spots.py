"""Fishing spots deplete and move (COMBAT_SKILLING_SPEC part 3, 10-20 shared catches). Run: python3 tools/test_fishing_spots.py"""
import asyncio
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import fishing_spots as fs  # noqa: E402
from content import RESOURCE_YIELDS  # noqa: E402
from world_map import WATER, WALKABLE_TILES  # noqa: E402

W = server.WORLD
W.has_gather_tool = lambda *a, **k: True
W.add_item_to_inventory = lambda *a, **k: True
_N = [0]


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(raw)


def _spot():
    """A live fishing spot with walkable shore beside it, and that shore tile."""
    for pos, node in sorted(W.resource_nodes.items()):
        if node.get("is_fish_spot") and not node["depleted"]:
            shore = fs.shoreline(W.grid, pos[0], pos[1], WATER, WALKABLE_TILES)
            if shore:
                return pos, node, shore
    raise AssertionError("no fishing spot")


def _player(at):
    _N[0] += 1
    name = f"fisher{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    s.level = lambda skill: 99
    s.x, s.y = at
    W.sessions[s.player_id] = s
    return s


def _run(coro):
    return asyncio.run(coro)


def _done(*sessions):
    for s in sessions:
        W.sessions.pop(s.player_id, None)


def test_every_spot_has_shared_stock():
    spots = [n for n in W.resource_nodes.values() if n.get("is_fish_spot")]
    assert spots
    assert all(10 <= n["stock_left"] <= 20 and n["home"] for n in spots)
    rng = random.Random(4)
    seen = set()
    for _ in range(400):
        node = {}
        fs.restock(node, {}, rng)
        seen.add(node["stock_left"])
    assert min(seen) == 10 and max(seen) == 20
    assert all(RESOURCE_YIELDS[n["type"]]["depletion_chance"] == 0.0 for n in spots)


def test_shared_stock_drains_with_two_players_then_moves():
    pos, node, shore = _spot()
    a, b = _player(shore), _player(shore)
    node["stock_left"], node["expires_at"] = 10, None
    a.gathering_node = b.gathering_node = pos
    ticks = 0
    while pos in W.resource_nodes and ticks < 20:
        _run(server.process_gathering([]))
        W.tick_count += 1
        ticks += 1
    left_at = W.tick_count - 1
    assert ticks == 5, ticks                         # two players, one stock of 10: 5 ticks, not 10
    assert pos not in W.resource_nodes and node in W.moving_fish_spots
    assert a.gathering_node is None and b.gathering_node is None
    assert any(fs.MOVED_MSG in m for m in a.ws.sent) and any(fs.MOVED_MSG in m for m in b.ws.sent)
    # the old tile is gone: GATHER there is refused and grants nothing
    xp = dict(a.xp)
    W.tick_count += 1
    _run(server.handle_gather(a, {"x": pos[0], "y": pos[1]}))
    assert a.gathering_node is None and a.xp == xp and "nothing to gather" in a.ws.sent[-1]
    # it comes back 3-6 tiles from home after 15-25 ticks
    assert 15 <= node["respawn_at"] - left_at <= 25
    W.tick_count = node["respawn_at"]
    _run(server.process_fishing_spots())
    new = next(p for p, n in W.resource_nodes.items() if n is node)
    hx, hy = node["home"]
    assert new != pos and 3 <= max(abs(new[0] - hx), abs(new[1] - hy)) <= 6
    assert W.grid[new[1]][new[0]] == WATER and fs.shoreline(W.grid, new[0], new[1], WATER, WALKABLE_TILES)
    others = [p for p, n in W.resource_nodes.items() if n.get("is_fish_spot") and p != new]
    assert all(max(abs(new[0] - x), abs(new[1] - y)) >= fs.MIN_GAP for x, y in others)
    assert 10 <= node["stock_left"] <= 20 and node["expires_at"] is None and not node["depleted"]
    _done(a, b)


def test_lifetime_expiry_moves_spot():
    pos, node, shore = _spot()
    node["stock_left"], node["expires_at"] = 20, None
    assert not fs.take_catch(node, W.tick_count, RESOURCE_YIELDS[node["type"]])
    life = node["expires_at"] - W.tick_count
    assert 34 <= life <= 67
    W.tick_count = node["expires_at"] - 1
    _run(server.process_fishing_spots())
    assert pos in W.resource_nodes
    W.tick_count += 1
    _run(server.process_fishing_spots())
    assert pos not in W.resource_nodes and node in W.moving_fish_spots


def test_one_start_per_tick():
    pos, node, shore = _spot()
    a = _player(shore)
    W.tick_count += 1
    _run(server.handle_gather(a, {"x": pos[0], "y": pos[1]}))
    n = len(a.ws.sent)
    assert a.gathering_node == pos and n >= 1
    a.gathering_node = None
    _run(server.handle_gather(a, {"x": pos[0], "y": pos[1]}))
    assert a.gathering_node is None and len(a.ws.sent) == n + 1  # refused this tick, with a message
    assert "already gathering" in json.dumps(a.ws.sent[-1])
    W.tick_count += 1
    _run(server.handle_gather(a, {"x": pos[0], "y": pos[1]}))
    assert a.gathering_node == pos
    _done(a)


def test_spot_stays_near_home_over_many_moves():
    rng = random.Random(11)
    pos, node, _shore = _spot()
    home = node["home"]
    for _ in range(12):
        cur = next(p for p, n in W.resource_nodes.items() if n is node)
        moving = [fs.depart(W.resource_nodes, cur, 0, {}, rng)]
        moved = fs.return_due(moving, W.resource_nodes, W.grid, 10 ** 6, WATER, WALKABLE_TILES, RESOURCE_YIELDS, rng)
        assert moved and moved[0][0] == cur and moved[0][1] != cur
        nx, ny = moved[0][1]
        assert 3 <= max(abs(nx - home[0]), abs(ny - home[1])) <= 6        # no drift across the map


if __name__ == "__main__":
    tests = [test_every_spot_has_shared_stock, test_shared_stock_drains_with_two_players_then_moves,
             test_lifetime_expiry_moves_spot, test_one_start_per_tick, test_spot_stays_near_home_over_many_moves]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} FISHING SPOT TESTS PASSED")
