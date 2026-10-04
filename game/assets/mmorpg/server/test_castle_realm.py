import runpy
import sys
import unittest
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import feature_flags
import world_map as wm
import castle_realm

PACK_ROOT = HERE.parent.parent / "realm_map_and_gothic_pack"


class CastleRealmDataTests(unittest.TestCase):
    def test_data_and_walkability(self):
        realm = castle_realm.build_plane("realm")
        self.assertEqual((realm["width"], realm["height"]), (300, 200))
        self.assertEqual(realm["tiles"][43][111], wm.GRASS)
        self.assertEqual(realm["tiles"][182][150], wm.PATH)
        self.assertTrue(castle_realm.walkable("realm", 49, 61))
        self.assertFalse(castle_realm.walkable("realm", 49, 60))
        if feature_flags.USE_CASTLE_INTERIORS_V2:
            self.assertTrue(castle_realm.walkable("gothic_f1", 20, 21))
            self.assertFalse(castle_realm.walkable("gothic_f1", 0, 0))
        else:
            self.assertTrue(castle_realm.walkable("gothic_f1", 8, 10))
            self.assertFalse(castle_realm.walkable("gothic_f1", 3, 1))

    def test_transitions_and_checker(self):
        self.assertEqual(castle_realm.transition_at("realm", 150, 186)["to_plane"], "overworld")
        self.assertEqual(castle_realm.transition_at("realm", 49, 61)["to_plane"], "gothic_f1")
        if feature_flags.USE_CASTLE_INTERIORS_V2:
            self.assertEqual(castle_realm.transition_at("realm", 49, 61)["arrive"], [20, 21])
            self.assertEqual(castle_realm.transition_at("realm", 50, 61)["arrive"], [21, 21])
        else:
            self.assertEqual(castle_realm.transition_at("gothic_f1", 16, 9)["to_plane"], "gothic_f2")

    def test_v2_rooms_reachable(self):
        if not feature_flags.USE_CASTLE_INTERIORS_V2:
            return
        walk = set(".DEUV")
        expected = {
            (49, 61): [20, 21],
            (50, 61): [21, 21],
            (254, 51): [21, 26],
            (255, 51): [22, 26],
            (149, 46): [25, 30],
            (150, 46): [26, 30],
            (171, 49): [5, 25],
            (49, 142): [18, 24],
            (50, 142): [19, 24],
        }
        for tile, arrive in expected.items():
            step = castle_realm.transition_at("realm", tile[0], tile[1])
            self.assertEqual(step["arrive"], arrive)
            self.assertTrue(castle_realm.walkable(step["to_plane"], arrive[0], arrive[1]))
        for name, floor in castle_realm.V2_FLOORS.items():
            rows = floor["rows"]
            pads = [tuple(item["tile"]) for item in floor.get("stairs", []) + floor.get("exits", [])]
            for x, y in pads:
                self.assertNotEqual(rows[y][x], "x", f"{name} pad {(x, y)}")
                self.assertIn(rows[y][x], walk)
            start = next((x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in walk)
            seen = {start}
            queue = deque([start])
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if (nx, ny) in seen:
                        continue
                    if 0 <= ny < len(rows) and 0 <= nx < len(rows[ny]) and rows[ny][nx] in walk:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            total = sum(ch in walk for row in rows for ch in row)
            self.assertEqual(len(seen), total, name)
            for room in floor.get("rooms") or []:
                x0, y0, x1, y1 = room["rect"]
                hit = any((x, y) in seen for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
                self.assertTrue(hit, f"{name} room {room.get('name')}")
        checker = runpy.run_path(str(PACK_ROOT / "tools" / "realm_data.py"))
        import json
        realm = json.loads((PACK_ROOT / "json" / "castle_realm_map.json").read_text())
        gothic = json.loads((PACK_ROOT / "json" / "gothic_castle.json").read_text())
        errors, _log = checker["check"](realm["rows"], gothic, verbose=False)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
