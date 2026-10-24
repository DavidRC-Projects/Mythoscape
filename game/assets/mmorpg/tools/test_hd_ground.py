"""HD trees, stumps and the seamless meadow."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "client"), os.path.join(HERE, "..", "server")]
import pygame
pygame.init(); pygame.display.set_mode((8, 8))
import hd_trees, village_ground


def test_all_tree_art_present():
    assert hd_trees.ready()
    s = pygame.Surface((400, 400), pygame.SRCALPHA)
    for n in hd_trees.TREE_TYPES + ("stump",):
        s.fill((0, 0, 0, 0))
        assert hd_trees.draw(s, n, 200, 300, 48, 3, 4)
        assert pygame.mask.from_surface(s).count() > 500, n


def test_ghost_alpha_is_lighter():
    a = pygame.Surface((400, 400)); b = pygame.Surface((400, 400))
    a.fill((0, 0, 0)); b.fill((0, 0, 0))
    hd_trees.draw(a, "oak_tree", 200, 300, 48, 1, 1)
    hd_trees.draw(b, "oak_tree", 200, 300, 48, 1, 1, alpha=95)
    assert sum(b.get_at((200, 150))[:3]) < sum(a.get_at((200, 150))[:3])


def test_meadow_has_no_tile_seams():
    t = 48
    s = pygame.Surface((t * 4, t))
    for i in range(4):
        assert village_ground.draw_world_grass(s, pygame.Rect(i * t, 0, t, t), 10 + i, 7)
    tex = village_ground._grass_texture(t)
    ref = tex.subsurface(pygame.Rect((10 % 24) * t, 7 * t, t * 4, t))
    for x in range(t * 4):
        assert s.get_at((x, t // 2)) == ref.get_at((x, t // 2))


def test_meadow_wraps_period():
    t = 32
    a = pygame.Surface((t, t)); b = pygame.Surface((t, t))
    village_ground.draw_world_grass(a, pygame.Rect(0, 0, t, t), 5, 5)
    village_ground.draw_world_grass(b, pygame.Rect(0, 0, t, t), 5 + 24, 5 + 48)
    assert pygame.image.tobytes(a, "RGB") == pygame.image.tobytes(b, "RGB")


class _Cli:
    """Tiny client: a 6x6 world, water at x>=3, a path row at y=2."""
    def __init__(self):
        import world_map as wm
        self.world_w = 6
        self.tiles = [[wm.WATER if x >= 3 else (wm.PATH if y == 2 else wm.GRASS) for x in range(6)] for y in range(6)]
    def world_to_view(self, x, y): return x, y
    def view_to_world(self, x, y): return x, y
    def _is_pier_tile(self, x, y): return False


def test_path_is_seamless_mid_road_and_soft_at_edges():
    t = 48; c = _Cli()
    s = pygame.Surface((t, t))
    assert village_ground.draw_world_path(s, pygame.Rect(0, 0, t, t), 1, 2, c)
    # grass on N and S: fringe makes the top rows greener than the middle row
    top = s.get_at((t // 2, 1)); mid = s.get_at((t // 2, t // 2))
    assert top.g - top.r > mid.g - mid.r


def test_water_animates_and_has_shore():
    t = 48; c = _Cli()
    a = pygame.Surface((t, t)); b = pygame.Surface((t, t))
    village_ground.draw_world_water(a, pygame.Rect(0, 0, t, t), 3, 4, 0.0, c)
    village_ground.draw_world_water(b, pygame.Rect(0, 0, t, t), 3, 4, 3.0, c)
    assert pygame.image.tobytes(a, "RGB") != pygame.image.tobytes(b, "RGB")
    # west neighbour is land: west edge differs from open water's west edge
    o = pygame.Surface((t, t))
    village_ground.draw_world_water(o, pygame.Rect(0, 0, t, t), 5, 4, 0.0, c)
    assert a.get_at((1, t // 2))[:3] != o.get_at((1, t // 2))[:3]
