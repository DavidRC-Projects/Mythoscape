"""Harbourreach fishing/decking + Tidehollow mouth (north of pier).

Run: python3 tools/test_harbour_tidehollow.py
"""
import os
import sys
import unittest
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import world_map as wm  # noqa: E402
import harbour_seal as HS  # noqa: E402
import content  # noqa: E402
import dungeon  # noqa: E402

W = wm.WALKABLE_TILES


def bfs(grid, start, extra_block=()):
    blocked = set(extra_block)
    H, Wd = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n in seen or not (0 <= n[0] < Wd and 0 <= n[1] < H):
                    continue
                if grid[n[1]][n[0]] in W and n not in blocked:
                    seen.add(n)
                    q.append(n)
    return seen


class HarbourTidehollow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = wm.generate_world()
        cls.reach = bfs(cls.grid, wm.SPAWN_POINT)

    def test_tidehollow_mouth_north_of_pier(self):
        mx, my = wm.TIDEHOLLOW_MOUTH
        self.assertEqual((mx, my), (204, 12))
        self.assertEqual(self.grid[my][mx], wm.FLOOR)
        self.assertIn((mx, my), self.reach)
        # South of old inlet band — no sea channel under the docks.
        inlet = sum(
            1 for y in (43, 44, 45) for x in range(170, 200)
            if self.grid[y][x] == wm.WATER
        )
        self.assertEqual(inlet, 0)

    def test_harbour_sealed_without_wolf_pass(self):
        cut = [(x, y) for x in range(136, 166) for y in range(0, 29)]
        harbour = [p for p in bfs(self.grid, wm.SPAWN_POINT, cut)
                   if 170 <= p[0] <= 198 and 1 <= p[1] <= 42]
        self.assertEqual(harbour, [])
        open_h = [p for p in self.reach if 170 <= p[0] <= 198 and 1 <= p[1] <= 42]
        self.assertGreater(len(open_h), 500)
        # Spur leaves only the pass rows open.
        for y in range(len(self.grid)):
            for x in range(HS.ROCK_X[0], HS.ROCK_X[1] + 1):
                if HS.PASS_Y0 <= y <= HS.PASS_Y1:
                    continue
                if self.grid[y][x] in W:
                    self.fail(f"spur gap at ({x},{y})")

    def test_fishing_water_has_deck_shore(self):
        fish = [
            (x, y) for y in range(8, 30) for x in range(184, 201)
            if self.grid[y][x] == wm.WATER
            and any(
                self.grid[y + dy][x + dx] == wm.PATH
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= x + dx < len(self.grid[0]) and 0 <= y + dy < len(self.grid)
            )
        ]
        self.assertGreaterEqual(len(fish), 40)

    def test_content_mouth_matches_map(self):
        self.assertEqual(dungeon.CAVE_RETURN, wm.TIDEHOLLOW_RETURN)
        mouths = [
            b for b in getattr(content, "BUILDINGS", [])
            if "tidehollow" in b.get("id", "") or "tidehollow" in b.get("name", "").lower()
        ]
        if mouths:
            b = mouths[0]
            self.assertTrue(abs(b.get("enter_x", wm.TIDEHOLLOW_MOUTH[0]) - wm.TIDEHOLLOW_MOUTH[0]) <= 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
