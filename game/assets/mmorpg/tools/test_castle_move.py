"""Castle move + harbour seal + Fairy Glade + position migration.
Run: python3 tools/test_castle_move.py"""
import os, sqlite3, sys, tempfile, unittest
from collections import deque
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import world_map as wm, castle_v2, harbour_seal, fairy_glade as FG, content, politics
import position_migrations as PM

W = wm.WALKABLE_TILES


def bfs(grid, start, extra_block=()):
    blocked = set(extra_block)
    H, Wd = len(grid), len(grid[0])
    seen = {start}; q = deque([start])
    while q:
        x, y = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n in seen or not (0 <= n[0] < Wd and 0 <= n[1] < H):
                    continue
                if grid[n[1]][n[0]] in W and n not in blocked:
                    seen.add(n); q.append(n)
    return seen


class CastleMove(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        g = wm.generate_world()
        cls.grid = g[0] if isinstance(g, tuple) else g
        cls.reach = bfs(cls.grid, wm.SPAWN_POINT)

    def harbour(self, reach):
        return [p for p in reach if 170 <= p[0] <= 198 and 1 <= p[1] <= 42]

    def test_harbour_sealed_without_wolf_pass(self):
        cut = [(x, y) for x in range(136, 166) for y in range(0, 29)]
        self.assertEqual(self.harbour(bfs(self.grid, wm.SPAWN_POINT, cut)), [])
        self.assertGreater(len(self.harbour(self.reach)), 500)

    def test_castle_reachable(self):
        self.assertTrue(castle_v2.active())
        self.assertIn((153, 57), self.reach)
        self.assertIn((153, 50), self.reach)
        for (x, y) in castle_v2.outer_moat_cells():
            self.assertNotIn(self.grid[y][x], W, (x, y))

    def test_glade_only_via_lanes(self):
        ring = set(FG.ring_cells()); lanes = set(FG.lane_cells())
        for (x, y) in ring:
            self.assertEqual(self.grid[y][x], wm.WALL)
        for (x, y) in lanes:
            self.assertIn(self.grid[y][x], W)
        x0, y0, x1, y1 = FG.BUILDINGS
        def box(reach):
            return [p for p in reach if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]
        self.assertGreater(len(box(self.reach)), 200)
        self.assertEqual(box(bfs(self.grid, wm.SPAWN_POINT, lanes)), [])
        north = {p for p in lanes if p[1] < 75}; south = lanes - north
        # The southern meadows were only reachable through the village before
        # the glade too, so the exit lane is checked from that side.
        self.assertTrue(box(bfs(self.grid, (20, 99), north)))
        self.assertTrue(box(bfs(self.grid, wm.SPAWN_POINT, south)))
        self.assertNotIn((20, 99), bfs(self.grid, wm.SPAWN_POINT, south))
        self.assertIn((31, 52), self.reach); self.assertIn((13, 97), self.reach)
        self.assertIn((13, 98), self.reach)

    def test_glade_v2_arches_paths_fence(self):
        import fairy_village as FV
        posts = FG.arch_posts()
        self.assertEqual(len(posts), 4)
        for (x, y) in posts:
            self.assertEqual(self.grid[y][x], wm.WALL, (x, y))        # posts collide
        for name, (ax, ay), (bx, by) in FG.ARCHES:
            for x in range(ax + 1, bx):
                self.assertIn(self.grid[ay][x], W, (name, x, ay))     # the span is open
                self.assertIn((x, ay), self.reach)
        self.assertEqual(set(FG.tree_cells()), set(FG.ring_cells()) - set(posts))
        self.assertFalse(FV.fence_cells())                               # picket fence gone
        # Both winding lanes are long (> 25 tiles of walking each).
        lanes = set(FG.lane_cells())
        for start, lo, hi in (((31, 52), 50, 63), ((13, 97), 87, 97)):
            sub = {p for p in lanes if lo <= p[1] <= hi}
            dist = {start: 0}; q = deque([start])
            while q:
                c = q.popleft()
                for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (c[0] + d[0], c[1] + d[1])
                    if n in sub and n not in dist:
                        dist[n] = dist[c] + 1; q.append(n)
            self.assertGreater(max(dist.values()), 25, start)

    def test_back_moat_reaches_mountain(self):
        x0, y0, x1, y1 = castle_v2.footprint_tiles()
        ridge = castle_v2.ridge_moat_cells(x0 - castle_v2.MOAT_SIDE, x1 + castle_v2.MOAT_SIDE,
                                           y0 - castle_v2.MOAT_BACK)
        self.assertGreater(len(ridge), 40)
        for (x, y) in ridge:
            self.assertEqual(self.grid[y][x], wm.WATER, (x, y))
        # every back-moat column runs unbroken from the castle wall up to the cliff
        for x in range(x0, x1 + 1):
            top = min(y for (cx, y) in ridge if cx == x)
            for y in range(top, y0):
                self.assertEqual(self.grid[y][x], wm.WATER, (x, y))
            self.assertEqual(self.grid[top - 1][x], wm.WALL, (x, top - 1))

    def test_lanes_four_wide(self):
        lanes = set(FG.lane_cells())
        self.assertEqual(FG.LANE_WIDTH, 4)
        # every lane tile sits inside some fully-open 3x3 lane block
        for (x, y) in lanes:
            ok = any(all((x + ox + i, y + oy + j) in lanes for i in range(4) for j in range(4))
                     for ox in (-3, -2, -1, 0) for oy in (-3, -2, -1, 0))
            self.assertTrue(ok, (x, y))
        for name, (ax, ay), (bx, by) in FG.ARCHES:
            self.assertGreaterEqual(bx - ax - 1, 4, name)

    def test_apothecary_moved_clear_of_trees(self):
        import json
        p = os.path.join(ROOT, "assets", "fairy_village", "data", "collision", "mushroom_apothecary.json")
        a = json.load(open(p))
        f = a["footprint"]
        self.assertEqual((f["x0"], f["y0"], f["x1"], f["y1"]), (32, 61, 38, 67))
        ring = set(FG.ring_cells())
        for (x, y) in a["blocked_tiles"]:
            self.assertEqual(self.grid[y][x], wm.WALL)
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    self.assertNotIn((x + dx, y + dy), ring, (x, y))
        self.assertIn(tuple(a["stand_tile"]), self.reach)
        door = [s for s in content.INTERACTABLES if s.get("id") == "mushroom_apothecary_door"] \
            if hasattr(content, "INTERACTABLES") else []
        for d in door:
            self.assertEqual((d["x"], d["y"]), tuple(a["door_tile"]))
            self.assertIn(tuple(d["stand"]), self.reach)

    def test_npcs_walkable(self):
        pts = list(politics.PROTESTER_SPOTS) if hasattr(politics, "PROTESTER_SPOTS") else []
        for p in pts:
            xy = p if isinstance(p, tuple) else (p[0], p[1])
            self.assertIn(self.grid[xy[1]][xy[0]], W, xy)
        keep = [d for d in content.TELEPORT_DESTINATIONS if d.get("id") == "keep"]
        self.assertTrue(keep)
        for d in keep:
            self.assertIn((d["x"], d["y"]), self.reach)
        for k in ("crier_square", "notice_board_square"):
            v = getattr(politics, k, None)
            if isinstance(v, tuple) and len(v) == 2:
                self.assertIn(v, self.reach, k)

    def test_migration_once_with_backup(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "world.db")
        c = sqlite3.connect(path)
        c.execute("create table players (id integer primary key, username text, x int, y int, dungeon_resume text)")
        c.execute("insert into players values (1,'a',160,3,NULL)")          # cut-off north strip
        c.execute("insert into players values (2,'b',28,24,NULL)")          # fine
        c.execute("""insert into players values (3,'c',28,24,'{"return_x":46,"return_y":81}')""")
        c.commit()
        logs = []
        PM.run_once(c, self.grid, W, wm.SPAWN_POINT, db_path=path, log=logs.append)
        rows = {r[0]: r for r in c.execute("select id,x,y,dungeon_resume from players")}
        self.assertIn((rows[1][1], rows[1][2]), self.reach)
        self.assertEqual(rows[2][1:3], (28, 24))
        import json
        dr = json.loads(rows[3][3]); self.assertIn((dr["return_x"], dr["return_y"]), self.reach)
        self.assertTrue(os.path.exists(os.path.join(d, "world.db.pre_castle_move.bak")))
        c.execute("update players set x=160, y=3 where id=1"); c.commit()
        PM.run_once(c, self.grid, W, wm.SPAWN_POINT, db_path=path, log=logs.append)
        self.assertEqual(c.execute("select x,y from players where id=1").fetchone(), (160, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
