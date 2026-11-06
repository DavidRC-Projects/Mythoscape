"""March intro presentation clock: a load stall before/between intro frames must not
consume the royal-box opening; click-skip still ends the march at once."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena_barracks_fixture  # noqa: F401  (paths, dummy video)
import arena_colosseum as AC

T = [1000.0]
AC.time.time = lambda: T[0]
AC._march_plan = lambda m: ({1: (6.0, [(196.0, 150.0), (196.0, 128.0)])}, {})   # one soldier entering late
AC._is_duel = lambda m: False


class C:
    def __init__(self, m):
        self.arena_match = m; self.monsters = {}


def match():
    return {"active": True, "phase": "preview", "units": {1: {"x": 196, "y": 128, "alive": True, "hp": 10}}, "pit": [178, 113, 214, 143], "center": [196, 128]}


def royal(c):
    return AC.frame_camera(c, c.arena_match, 196.0, 128.0, [{"x": 196, "y": 128}], 12.0) == (196.0, 110.0)


def main():
    c = C(match())
    AC.march_update(c)                    # first intro update, then a 1.75 s load stall
    T[0] += 1.75; AC.march_update(c)
    assert AC.march_active(c) and royal(c), "stall consumed the royal opening"
    for _ in range(60):                   # ~1 s of normal frames: still on the royal box
        T[0] += 1 / 60; AC.march_update(c)
    assert royal(c), "royal opening should last ~1.4 s of rendered intro"
    for _ in range(40):
        T[0] += 1 / 60; AC.march_update(c)
    assert not royal(c), "after the opening the camera follows the parade"
    c2 = C(match()); AC.march_update(c2); T[0] += 2.0; AC.march_update(c2)
    AC._MARCH["skip"] = True; T[0] += 1 / 60; AC.march_update(c2)   # same flag the intro click sets
    assert not AC.march_active(c2), "skip must still end the march"
    c3 = C(match()); AC.march_update(c3)  # 15 s safety cap still applies over steady frames
    for _ in range(16 * 60):
        T[0] += 1 / 60; AC.march_update(c3)
    assert not AC.march_active(c3), "15 s cap"
    print("ALL PASS")


main()
