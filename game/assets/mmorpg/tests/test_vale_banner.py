"""Vale banner fires only when walking in through a pass (31 Oct)."""
import os, sys, types
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("client", "server", "shared"):
    sys.path.insert(0, os.path.join(R, d))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import vale_ring_client as V


def _run(path, t0=1000.0):
    V._STATE.update({"inside": None, "until": 0.0, "last": -99.0, "pos": None})
    c = types.SimpleNamespace(dungeon=None, player={"x": 0, "y": 0})
    c.player_xy = lambda: (c.player["x"], c.player["y"])
    fired = []
    for i, (x, y) in enumerate(path):
        c.player["x"], c.player["y"] = x, y
        V.track(c, t0 + i * 0.5)
        fired.append(V._STATE["until"] > t0 + i * 0.5)
    return any(fired)


def test_spawn_in_village_no_banner():
    assert not _run([(46, 26), (46, 27), (47, 27)])


def test_teleport_into_village_no_banner():
    assert not _run([(150, 80), (150, 81), (46, 26), (46, 27)])


def test_walk_in_south_pass():
    assert _run([(31, 56), (31, 55), (31, 54), (31, 53), (31, 52), (31, 51)])


def test_walk_in_east_pass():
    assert _run([(106, 24), (105, 24), (104, 24), (103, 24), (102, 24), (101, 24)])


def test_walk_in_se_pass():
    assert _run([(100, 55), (100, 54), (100, 53), (100, 52)])


def test_walk_out_no_banner():
    assert not _run([(31, 50), (31, 51), (31, 52), (31, 53), (31, 54)])
