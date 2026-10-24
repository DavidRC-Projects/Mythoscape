"""The helmet stays on during actions (David, 23 Oct 2026): every action strip of a whole-figure outfit has a
per-frame head anchor, the anchors move smoothly, and the client draws the helmet on action frames."""
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client"))
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))
import helmet_overlay as H  # noqa: E402
import player_hd_client as P  # noqa: E402

ASSETS = os.path.join(HERE, "..", "..", "player_hd", "assets")


def test_every_action_strip_has_anchors():
    data = json.load(open(os.path.join(ASSETS, "helmets", "action_anchors.json")))
    missing = []
    for sex in ("male", "female"):
        d = os.path.join(ASSETS, sex, "2x", "outfit_villager_hd" if sex == "male" else "outfit_village_lady_hd")
        for fn in os.listdir(d):
            stem = fn[:-4]
            if not fn.endswith(".png") or stem.endswith(("_skin", "_tint")):
                continue
            if stem.rsplit("_", 1)[0] in ("melee_sword", "melee_axe", "chop", "mine", "fish"):
                lst = data.get(f"{sex}/{os.path.basename(d)}/{stem}")
                if not lst or any(a is None for a in lst):
                    missing.append((sex, stem))
    assert not missing, missing


def test_anchors_move_smoothly():
    data = json.load(open(os.path.join(ASSETS, "helmets", "action_anchors.json")))
    bad = []
    for k, lst in data.items():
        pts = [a for a in lst if a]
        for p, q in zip(pts, pts[1:]):
            if ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 > 0.45 * p[2]:
                bad.append(k)
                break
    assert not bad, bad


def test_helmet_drawn_on_action_frames():
    calls = []
    orig = H._blit
    H._blit = lambda *a, **k: (calls.append(a[3]), orig(*a, **k))[1]
    try:
        for sex in ("male", "female"):
            for anim, eq in (("melee", {"weapon": "bronze_sword"}), ("melee", {"weapon": "bronze_battleaxe"}),
                             ("chop", {"tool": "bronze_axe"}), ("mine", {"tool": "bronze_pickaxe"}), ("fish", {})):
                for f in ("front", 1, "back", -1):
                    for p in (0.1, 0.5, 0.9):
                        n = len(calls)
                        surf = pygame.Surface((300, 300), pygame.SRCALPHA)
                        P.draw_player(surf, sex, None, 150, 280, 80, p, anim=anim, facing=f, progress=p,
                                      equipment=dict(eq, helmet="iron_helmet"))
                        assert len(calls) > n, (sex, anim, f, p)
    finally:
        H._blit = orig


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    bad = 0
    for n, f in tests:
        try:
            f(); print("ok  ", n)
        except AssertionError as e:
            bad += 1; print("FAIL", n, e)
    print(f"{len(tests) - bad}/{len(tests)} helmet action tests passed")
    sys.exit(1 if bad else 0)
