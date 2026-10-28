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
        # Mid-pass floor is 6–7 tiles (authored); ends flare to 8. Bounds moved with SHIFT_X.
        mid = [w for x, w in widths.items() if x0 + 3 <= x <= x1 - 3]
        self.assertTrue(mid and all(w in (4, 5, 6, 7, 8) for w in mid))
        self.assertTrue(any(w in (6, 7) for w in mid))

    def test_no_old_grey_tiles(self):
        import castle_v2
        mx0, my0, mx1, my1 = wm.ZONES["mountains"]
        cx0, cy0, cx1, cy1 = castle_v2.footprint_tiles() if castle_v2.active() else (-1, -1, -2, -2)
        spur = set()
        if castle_v2.active():
            # Flank spurs + north cap from _stamp_stonehaven_walls (join keep to ridge).
            x0, y0, x1, y1 = cx0, cy0, cx1, cy1
            west_x = x0 - castle_v2.MOAT_SIDE - 1
            east_x = x1 + castle_v2.MOAT_SIDE + 1
            city_y0 = wm.city_bounds()[1]
            for y in range(max(0, y0 - castle_v2.MOAT_BACK), city_y0 + 1):
                for x in (west_x, west_x - 1, east_x, east_x + 1):
                    spur.add((x, y))
            cap_y = max(0, y0 - castle_v2.MOAT_BACK - 1)
            for x in range(west_x - 1, east_x + 2):
                spur.add((x, cap_y))
        for y in range(my0, my1 + 1):
            for x in range(mx0, mx1 + 1):
                if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                    continue  # the moved castle's own walls (drawn by castle_sprites)
                if (x, y) in spur:
                    continue
                if self.grid[y][x] == wm.WALL:
                    self.assertTrue(WP.blocked(x, y), (x, y))

    def test_wolves(self):
        wolves = WP.wolf_spawns()
        self.assertEqual(len(wolves), 6)
        self.assertEqual(
            sorted(s for s in content.MONSTER_SPAWNS if s in wolves),
            sorted(wolves),
        )
        zx0, zy0, zx1, zy1 = WP.wolf_zone()
        self.assertEqual((zx1 - zx0 + 1, zy1 - zy0 + 1), (12, 6))
        for _m, x, y in wolves:
            self.assertTrue(zx0 <= x <= zx1 and zy0 <= y <= zy1)
            self.assertIn(self.grid[y][x], wm.WALKABLE_TILES)
        self.assertEqual(content.MONSTERS["wolf"]["leash_area"], WP.leash_area())
        self.assertEqual(content.MONSTERS["wolf"]["level"], 116)


if __name__ == "__main__":
    unittest.main()
