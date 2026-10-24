"""Wolf Pass massif checks (MOUNTAIN_SPEC.md). Run: python3 tools/test_wolf_pass.py"""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import world_map as wm, wolf_pass as WP, content, feature_flags


class WolfPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        g = wm.generate_world()
        cls.grid = g[0] if isinstance(g, tuple) else g

    def test_flag_and_art(self):
        self.assertTrue(feature_flags.USE_WOLF_PASS)
        for n in ("north_ridge.png", "south_ridge.png", "wolf_pass.json", "collision_mask.png"):
            self.assertTrue(os.path.exists(os.path.join(WP.PACK, n)), n)
        size = sum(os.path.getsize(os.path.join(WP.PACK, n)) for n in os.listdir(WP.PACK))
        self.assertLess(size, 12 * 1024 * 1024)

    def test_road_clear_full_length(self):
        x0, _y0, x1, _y1 = WP.bounds()
        for x in range(x0 - 2, x1 + 2):
            for y in range(14, 18):
                self.assertIn(self.grid[y][x], wm.WALKABLE_TILES, (x, y))

    def test_floor_widths(self):
        x0, _y0, x1, _y1 = WP.bounds()
        widths = {}
        for x in range(x0, x1 + 1):
            ft, fb = WP.floor_rows(x)
            widths[x] = fb - ft + 1
            for y in range(ft, fb + 1):
                self.assertIn(self.grid[y][x], wm.WALKABLE_TILES, (x, y))
            self.assertEqual(self.grid[ft - 1][x] if WP.blocked(x, ft - 1) else wm.WALL, wm.WALL)
        self.assertEqual(widths[x0], 8); self.assertEqual(widths[x1], 8)
        self.assertEqual(min(widths.values()), 4)
        self.assertTrue(all(w in (6, 7) for x, w in widths.items() if x0 + 3 <= x <= 146 or 155 <= x <= x1 - 3))

    def test_no_old_grey_tiles(self):
        import castle_v2
        mx0, my0, mx1, my1 = wm.ZONES["mountains"]
        cx0, cy0, cx1, cy1 = castle_v2.footprint_tiles() if castle_v2.active() else (-1, -1, -2, -2)
        for y in range(my0, my1 + 1):
            for x in range(mx0, mx1 + 1):
                if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                    continue  # the moved castle's own walls (drawn by castle_sprites)
                if self.grid[y][x] == wm.WALL:
                    self.assertTrue(WP.blocked(x, y), (x, y))

    def test_wolves(self):
        wolves = [s for s in content.MONSTER_SPAWNS if s[0] == "wolf" and 130 <= s[1] <= 170 and s[2] < 45]
        self.assertEqual(len(wolves), 6)
        zx0, zy0, zx1, zy1 = WP.wolf_zone()
        self.assertEqual((zx1 - zx0 + 1, zy1 - zy0 + 1), (12, 6))
        for _m, x, y in wolves:
            self.assertTrue(zx0 <= x <= zx1 and zy0 <= y <= zy1)
            self.assertIn(self.grid[y][x], wm.WALKABLE_TILES)
        self.assertEqual(content.MONSTERS["wolf"]["leash_area"], WP.leash_area())
        self.assertEqual(content.MONSTERS["wolf"]["level"], 116)


if __name__ == "__main__":
    unittest.main()
