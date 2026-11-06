"""After a bout or logout the server parks players on safe_points.ARENA_GATE; R must still
open Marshal Branna's barracks there, without widening the arena reach elsewhere."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena_barracks_fixture  # noqa: F401  (paths, dummy video, client imports)
import safe_points, mercenaries
import castle_realm_renderer as R


class G:
    dungeon = {"id": "castle_realm", "plane": "realm"}
    player = {"x": 0, "y": 0}


def near(xy):
    g = G(); g.player_xy = lambda: xy
    return R.near_arena(g)


def main():
    assert tuple(R.ARENA_GATE_STAND) == tuple(safe_points.ARENA_GATE), "client gate stand out of sync"
    assert tuple(mercenaries.outside_arena_tile()) == tuple(safe_points.ARENA_GATE)
    gx, gy = safe_points.ARENA_GATE
    fp = R._arena_blob()["footprint"]
    assert gy > fp[3] + 8, "gate stand was already in reach; test premise changed"
    for xy in [(gx, gy), (gx - 2, gy + 2), (gx + 2, gy - 2), (gx, fp[3] + 8), (gx, 140)]:
        assert near(xy), f"R should reach the barracks from {xy}"
    for xy in [(gx, gy + 3), (gx + 3, gy), (fp[2] + 9, gy), (gx, gy + 20)]:
        assert not near(xy), f"R reach must not widen to {xy}"
    print("ALL PASS")


main()
