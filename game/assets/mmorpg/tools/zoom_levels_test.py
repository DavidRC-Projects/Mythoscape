"""Zoom levels 40..200 step 20, snapping, and HD source choice (never upscale).

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
    assert C.ZOOM_LEVELS == (40, 60, 80, 100, 120, 140, 160, 180, 200)
    snap = lambda v: C.GameClient._snap_zoom(None, v)  # noqa: E731
    cases = {0: 40, 30: 40, 49: 40, 50: 60, 110: 120, 150: 160, 199: 200, 250: 200, 100: 100}
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
    import time
    import emberdeep_v2_client
    emberdeep_v2_client.fp_active = lambda _c: False
    c = C.GameClient.__new__(C.GameClient)
    c.zoom_pct, c._zoom_goal, c._zoom_anim, c._zoom_from, c._zoom_t0 = 100, 100, 100.0, 100.0, 0.0
    c._zoom_latched = False
    c.adjust_zoom(1)
    c._zoom_latched = False
    c.adjust_zoom(1)          # retargets, not queued per frame: goal 140
    assert c._zoom_goal == 140
    c._pump_zoom()
    assert c.zoom_pct == 140 and C.TILE == 40 and c._zoom_view_scale() >= 1.0
    seen = []
    t0 = time.time()
    while c._zoom_anim != 140.0 and time.time() - t0 < 1.0:
        c._pump_zoom()
        seen.append(c._zoom_anim)
        time.sleep(0.01)
    assert c._zoom_anim == 140.0 and C.TILE == 56, (c._zoom_anim, C.TILE)
    assert all(a <= b for a, b in zip(seen, seen[1:])) and 0.15 < time.time() - t0 < 0.4


if __name__ == "__main__":
    test_levels()
    test_hd_scale_for()
    test_ease()
    print("ok zoom_levels_test")
