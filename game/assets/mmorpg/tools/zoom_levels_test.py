"""Zoom levels ZOOM_MIN..ZOOM_MAX step ZOOM_STEP, snapping, and HD source choice.

Run: python3 tools/zoom_levels_test.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.argv = sys.argv[:1]

import client as C  # noqa: E402


def test_levels():
    assert C.ZOOM_LEVELS == tuple(range(C.ZOOM_MIN, C.ZOOM_MAX + 1, C.ZOOM_STEP))
    assert C.ZOOM_LEVELS[0] == 100 and C.ZOOM_LEVELS[-1] == 200
    snap = lambda v: C.GameClient._snap_zoom(None, v)  # noqa: E731
    cases = {
        0: 100, 30: 100, 90: 100, 100: 100, 110: 120, 130: 140,
        150: 160, 199: 200, 250: 200,
    }
    for v, want in cases.items():
        assert snap(v) == want, (v, snap(v), want)


def test_hd_scale_for():
    import player_hd_client, npc_hd_client, fairy_village_client
    for mod in (player_hd_client, npc_hd_client, fairy_village_client):
        biggest = max(mod._scale_for(t)[1] for t in range(16, 300))
        for tile in range(16, 81):
            _tag, base = mod._scale_for(tile)
            assert base >= min(tile, biggest), (mod.__name__, tile, base)


def test_ease():
    import emberdeep_v2_client
    emberdeep_v2_client.fp_active = lambda _c: False
    c = C.GameClient.__new__(C.GameClient)
    c.zoom_pct, c._zoom_goal, c._zoom_anim, c._zoom_from, c._zoom_t0 = 100, 100, 100.0, 100.0, 0.0
    c._zoom_latched = False
    c._area_view = False
    base_tile = C.TILE
    c.adjust_zoom(1)
    c._zoom_latched = False
    c.adjust_zoom(1)          # retargets, not queued per frame: goal 140
    assert c._zoom_goal == 140
    c._pump_zoom()
    # Zoom-in above ZOOM_MIN is a cheap view-scale; physical TILE stays at min.
    assert c.zoom_pct == 140 and C.TILE == base_tile
    assert abs(c._zoom_view_scale() - 1.4) < 0.05


if __name__ == "__main__":
    test_levels()
    test_hd_scale_for()
    test_ease()
    print("ok zoom_levels_test")
