"""Rounded shoreline field (visual only). Run: python3 tools/test_shoreline.py"""
import os, sys, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server")); sys.path.insert(0, os.path.join(ROOT, "client"))
import village_ground as VG


def bits(cells):
    b = 0
    for dx, dy in cells:
        b |= 1 << ((dy + 2) * 5 + (dx + 2))
    return b


class Shore(unittest.TestCase):
    N = 48

    def test_straight_bank_sits_on_seam(self):
        f = VG.shore_field(bits([(dx, -1) for dx in range(-2, 3)] + [(dx, -2) for dx in range(-2, 3)]), self.N, 0, 0)
        self.assertTrue(0.3 < f[:, 0].mean() < 0.7)
        self.assertLess(f[:, self.N // 2].max(), 0.3)

    def test_outer_land_corner_is_rounded(self):
        # Land only to the NW diagonal: no square corner poking into this water tile.
        f = VG.shore_field(bits([(-1, -1), (-2, -1), (-1, -2), (-2, -2)]), self.N, 0, 0)
        self.assertLess(f[0, 0], 0.5)

    def test_inner_corner_is_filled(self):
        # Land N, W and NW: the water tile's top-left corner fills with a curve.
        land = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if dx < 0 or dy < 0]
        f = VG.shore_field(bits(land), self.N, 0, 0)
        self.assertGreater(f[0, 0], 0.5)
        self.assertLess(f[self.N // 3, self.N // 3], 0.5)

    def test_continuous_across_seam(self):
        row = [(dx, -1) for dx in range(-2, 3)] + [(dx, -2) for dx in range(-2, 3)]
        a = VG.shore_field(bits(row + [(2, 0), (2, 1), (2, 2), (2, -1)]), self.N, 0, 0)
        shifted = [(dx - 1, dy) for dx, dy in row + [(2, 0), (2, 1), (2, 2), (2, -1)] if -2 <= dx - 1]
        b = VG.shore_field(bits(shifted + [(2, -1), (2, -2)]), self.N, 1, 0)
        self.assertLess(abs(float(a[-1, :].mean()) - float(b[0, :].mean())), 0.08)


if __name__ == "__main__":
    unittest.main(verbosity=2)
