"""Gather loop strips from player_hd (COMBAT_SKILLING_SPEC part 2 hook-up). Run: python3 tools/test_gather_anims.py"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

import pygame  # noqa: E402
pygame.init()
pygame.display.set_mode((320, 240))
import player_hd_client as hd  # noqa: E402

REAL_META = hd._load_meta


def _with_meta(anims):
    meta = dict(REAL_META())
    meta["anims"] = dict(meta.get("anims") or {}, **anims)
    hd._load_meta = lambda: meta


def test_skill_names_map_to_strips():
    hd._load_meta = REAL_META
    assert hd.gather_anim("woodcutting") == "chop"
    assert hd.gather_anim("mining") == "mine"
    assert hd.gather_anim("fishing") == "fish"
    assert hd.gather_anim("fishing", "harpoon") in ("fish", "fish_harpoon")
    anims = REAL_META().get("anims") or {}
    for a in ("chop", "mine", "fish"):
        assert a in anims, a                                    # today's strips are there to play


def test_today_8_frame_strips_keep_cadence():
    hd._load_meta = REAL_META
    for a in ("chop", "mine", "fish"):
        frames = {hd._frame_for_anim(a, t / 20.0)[1] for t in range(60)}
        assert frames == set(range(8)), (a, frames)


def test_12_frame_strips_use_tables():
    _with_meta({a: {"frames": 12, "facings": ["e"]} for a in ("chop", "mine", "fish")})
    try:
        for a, loop in (("mine", 1.8), ("chop", 1.8), ("fish", 2.4)):
            table = hd.GATHER_PROGRESS[a]
            assert len(table) == 12
            for i, p in enumerate(table):
                t = p * loop + 0.001
                assert hd._frame_for_anim(a, t) == (a, i), (a, i, hd._frame_for_anim(a, t))
            assert hd._frame_for_anim(a, loop + 0.001) == (a, 0)      # loops
    finally:
        hd._load_meta = REAL_META


def test_tool_strip_used_once_baked():
    _with_meta({"fish_harpoon": {"frames": 12, "facings": ["e"], "loop_ms": 2400}})
    try:
        assert hd.gather_anim("fishing", "harpoon") == "fish_harpoon"
        assert hd.gather_anim("fishing", "fishing_rod") == "fish"
        assert hd._frame_for_anim("fish_harpoon", 0.0) == ("fish_harpoon", 0)
    finally:
        hd._load_meta = REAL_META


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} GATHER ANIM TESTS PASSED")
