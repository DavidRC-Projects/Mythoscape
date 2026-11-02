"""Safe arrival / logout park proofs. Run: python3 tools/test_safe_points.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import safe_points  # noqa: E402
import content  # noqa: E402
from world_map import is_walkable  # noqa: E402

W = server.WORLD
_N = [0]


class _WS:
    def __init__(self):
        self.sent, self.closed = [], False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self, *a, **k):
        self.closed = True


def _player():
    _N[0] += 1
    name = f"safe{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    W.sessions[s.player_id] = s
    return s


def test_arena_gate_matches_teleport():
    dest = next(d for d in content.TELEPORT_DESTINATIONS if d["id"] == "arena")
    assert (dest["x"], dest["y"]) == safe_points.ARENA_GATE
    import mercenaries
    assert mercenaries.outside_arena_tile() == safe_points.ARENA_GATE


def test_teleport_destinations_walkable():
    for dest in content.TELEPORT_DESTINATIONS:
        x, y = int(dest["x"]), int(dest["y"])
        if dest.get("where") == "castle":
            import castle_realm
            assert castle_realm.walkable("realm", x, y), f"castle {dest['id']} @ {x},{y}"
        else:
            assert is_walkable(W.grid, x, y), f"overworld {dest['id']} @ {x},{y}"


def test_open_arrival_radius():
    s = _player()
    # Exact spawn should resolve
    spot = server._open_arrival(28, 24, lambda x, y: is_walkable(W.grid, x, y), s)
    assert spot is not None
    W.sessions.pop(s.player_id, None)


def test_logout_parks_arena():
    async def go():
        s = _player()
        import castle_realm
        import mercenaries as merc
        castle_realm.enter(s)
        s.dungeon["plane"] = "realm"
        s.x, s.y = merc.arena_coords()["center"][0], merc.arena_coords()["center"][1]
        s.arena_match = {"phase": "fight", "mode": "practice"}
        await server.logout_session(s, "test")
        # Position was parked before session removal — check DB
        row = W.db.get_player_by_id(s.player_id)
        # castle logout saves return portal as overworld pos; arena park mutates realm xy before save
        # For castle_realm, logout saves return_x/y as overworld — park still ran on session
        assert s.arena_match is None
        assert (s.x, s.y) == safe_points.ARENA_GATE
    asyncio.run(go())


def test_idle_logout_arena_park_hook():
    """Extend idle logout coverage: park helper clears match."""
    s = _player()
    s.dungeon = {"id": "castle_realm", "plane": "realm", "return_x": 28, "return_y": 24}
    s.x, s.y = 200, 170
    s.arena_match = {"phase": "preview"}
    ctx, cleared = safe_points.resolve_logout_park(s)
    assert ctx == "arena"
    assert (s.x, s.y) == safe_points.ARENA_GATE
    assert s.arena_match is None
    W.sessions.pop(s.player_id, None)


if __name__ == "__main__":
    test_arena_gate_matches_teleport()
    test_teleport_destinations_walkable()
    test_open_arrival_radius()
    test_logout_parks_arena()
    test_idle_logout_arena_park_hook()
    print("test_safe_points: OK")
