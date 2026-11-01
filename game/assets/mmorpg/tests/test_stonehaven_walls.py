"""Stonehaven gates, walls, castles and the King's Row Estate plaza (31 Oct).

Art and collision come from one layout table, so these checks keep them in step:
gates walk, curtain and towers block, HD art loads (old art if it fails), and
the estate walks reach every house door.
"""
import os, sys, unittest
from collections import deque
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("client", "server", "shared"):
    sys.path.insert(0, os.path.join(R, d))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
import world_map as wm

_GRID = None


def grid():
    global _GRID
    if _GRID is None:
        g = wm.generate_world()
        _GRID = g[0] if isinstance(g, tuple) else g
    return _GRID


def walkable(x, y):
    return grid()[y][x] not in (wm.WALL, wm.WATER)


def reach(start, goals, limit=None):
    g = grid(); seen = {start}; q = deque([start]); goals = set(goals)
    while q:
        x, y = q.popleft()
        if (x, y) in goals:
            goals.discard((x, y))
            if not goals:
                return True
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[1] < len(g) and 0 <= n[0] < len(g[0]) and n not in seen and walkable(*n):
                seen.add(n); q.append(n)
    return not goals


class Walls(unittest.TestCase):
    def test_every_blocked_tile_is_wall(self):
        lay = wm.stonehaven_wall_layout()
        bad = [t for t in lay["blocked"] if grid()[t[1]][t[0]] not in (wm.WALL, wm.WATER)]
        self.assertEqual(bad, [])

    def test_gate_openings_walk(self):
        lay = wm.stonehaven_wall_layout()
        self.assertTrue(lay["open"])
        self.assertEqual([t for t in lay["open"] if not walkable(*t)], [])
        xs = {x for x, _y in lay["open"]}
        for x in wm.STONEHAVEN_SOUTH_GATE_XS:
            self.assertIn(x, xs)

    def test_fort_wall_predicate_matches_grid(self):
        lay = wm.stonehaven_wall_layout()
        for t in list(lay["blocked"])[:400]:
            self.assertTrue(wm.is_stonehaven_fort_wall(*t), t)
        for t in lay["open"]:
            self.assertFalse(wm.is_stonehaven_fort_wall(*t), t)

    def test_towers_block(self):
        lay = wm.stonehaven_wall_layout()
        self.assertTrue(lay["towers"])
        self.assertGreaterEqual(len(lay["towers"]), 10)

    def test_gates_connect_inside_and_out(self):
        lay = wm.stonehaven_wall_layout()
        opens = sorted(lay["open"])
        self.assertTrue(reach(opens[0], opens))


class HdArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init(); pygame.display.set_mode((8, 8))

    def test_wall_kit_loads(self):
        import stonehaven_walls_client as S
        self.assertTrue(S._hd_ok())

    def test_castle_hd_used_and_fallback(self):
        import castle_sprites as CS
        base = os.path.join(R, "client", "assets", "buildings", "castle_v2", "1x", "castle_front.png")
        self.assertTrue(os.path.isfile(base[:-4] + "_hd.png"))
        for name in ("king", "gothic", "white_rose", "sky_anchor"):
            d = os.path.join(R, "client", "assets", "castle_realm", name, "sprites", "1x")
            self.assertTrue(any(f.endswith("_hd.png") for f in os.listdir(d)), name)
        # fallback: a broken _hd file next to a good layer still yields the old art
        import tempfile
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "1x"))
        good = os.path.join(d, "1x", "probe.png")
        pygame.image.save(pygame.Surface((40, 20)), good)
        open(good[:-4] + "_hd.png", "wb").write(b"not a png")
        old = CS._DIR
        CS._DIR = d
        try:
            img = CS._surface("probe.png", 40)
            self.assertIsNotNone(img)
            self.assertEqual(img.get_size(), (40, 20))
        finally:
            CS._DIR = old
            CS._cache.pop(("probe.png", 40), None)

    def test_towers_tiles_block(self):
        lay = wm.stonehaven_wall_layout()
        for cx, base in lay["towers"]:
            tiles = wm._sh_tower_tiles(cx, base)
            self.assertTrue(tiles)
            self.assertEqual([t for t in tiles if walkable(*t)], [], (cx, base))


class Plaza(unittest.TestCase):
    def test_walks_reach_every_door(self):
        import estate_plaza as EP
        import housing
        walks = EP.walk_tiles()
        doors = [h["door"]["exit"] for h in housing.houses() if h["footprint"]["x1"] < 45 and h["footprint"]["y0"] > 96]
        self.assertGreaterEqual(len(doors), 6)
        # every door exit is on a walk, and the walks connect them all to the estate entry
        for d in doors:
            self.assertIn(tuple(d), walks, d)
        start = (13, 98); seen = {start}; q = deque([start])
        while q:
            x, y = q.popleft()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in walks and n not in seen:
                    seen.add(n); q.append(n)
        for d in doors:
            self.assertIn(tuple(d), seen, d)

    def test_walks_and_props_are_walkable_ground(self):
        import estate_plaza as EP
        import housing
        houses = [h["footprint"] for h in housing.houses()]
        def in_house(x, y):
            return any(f["x0"] <= x <= f["x1"] and f["y0"] <= y <= f["y1"] for f in houses)
        bad = [t for t in EP.walk_tiles() if not walkable(*t) and not in_house(*t)]
        self.assertEqual(bad, [])
        for x, y in EP.LAMPS + EP.PLANTERS:
            self.assertTrue(walkable(int(x), int(y)), (x, y))

    def test_glow_follows_phase(self):
        import estate_plaza as EP
        self.assertEqual(EP.glow_strength("day"), 0.0)
        self.assertEqual(EP.glow_strength("night"), 1.0)
        self.assertTrue(0 < EP.glow_strength("dusk") < 1)

    def test_art_loads(self):
        import estate_plaza as EP
        pygame.init(); pygame.display.set_mode((8, 8))
        self.assertTrue(EP.available())


if __name__ == "__main__":
    unittest.main()


class EstateWall(unittest.TestCase):
    """Plaza curtain: solid ring, one walk-in entrance, every door reachable."""

    def _bfs(self, start, inside=None):
        g = grid(); seen = {start}; q = deque([start])
        while q:
            x, y = q.popleft()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in seen or not wm.is_walkable(g, *n):
                    continue
                if inside and not inside(*n):
                    continue
                seen.add(n); q.append(n)
        return seen

    def test_wall_tiles_block(self):
        lay = wm.estate_wall_layout()
        g = grid()
        bad = [t for t in lay["blocked"] if wm.is_walkable(g, *t)]
        self.assertEqual(bad, [])
        for x, y in lay["open"]:
            self.assertTrue(wm.is_walkable(g, x, y), (x, y))
        self.assertTrue(all(x <= 44 for x, _ in lay["blocked"]))  # mine untouched

    def test_ring_only_opens_at_entrance(self):
        # from inside, the only tiles that leave the ring are the entrance
        Y = wm.ESTATE_WALL_ROW
        inner = lambda x, y: 0 <= x <= 44 and Y <= y <= wm.HEIGHT - 1
        seen = self._bfs((22, 135), inner)
        exits = {(x, y) for x, y in seen if y == Y}
        self.assertEqual(exits, {(x, Y) for x in wm.ESTATE_GATE_XS})
        self.assertFalse(any(x in (0, 44) or y == wm.HEIGHT - 1 for x, y in seen))

    def test_doors_reachable_from_outside_both_ways(self):
        import housing
        import estate_plaza as EP
        doors = [tuple(h["door"]["exit"]) for h in housing.houses()
                 if h["footprint"]["x1"] < 45 and h["footprint"]["y0"] > 96]
        out = self._bfs((13, 95))
        for d in doors:
            self.assertIn(d, out, d)
            back = self._bfs(d)
            self.assertIn((13, 95), back, d)
        for x, y in EP.LAMPS:
            self.assertTrue(wm.is_walkable(grid(), int(x), int(y)), (x, y))

    def test_forecourt_gap(self):
        # 12+ open rows between the Fairy Glade ring (south edge row 97) and the curtain
        g = grid()
        for y in range(98, wm.ESTATE_WALL_ROW):
            row = [x for x in range(1, 44) if wm.is_walkable(g, x, y)]
            self.assertGreaterEqual(len(row), 40, y)
        self.assertGreaterEqual(wm.ESTATE_WALL_ROW - 98, 12)

    def test_estate_art_queues(self):
        import stonehaven_walls_client as S
        self.assertEqual(len(wm.estate_wall_layout()["towers"]), 6)
        self.assertTrue(S._hd_ok())
