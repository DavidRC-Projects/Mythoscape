"""Bare-head Bronze (David, 23 Oct 2026): body + legs alone show the set; no helmet = bare head with the hair
tinted to the player's hair colour (face stays skin-tinted); a helmet goes on as the overlay, in actions too."""
import json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "..", "player_hd", "assets")
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init(); pygame.display.set_mode((8, 8))
import player_hd_client as P
import helmet_overlay as H

ANIMS = ("idle", "walk", "melee_sword", "melee_axe", "chop", "mine", "fish")
BODY_LEGS = {"body": "bronze_body", "legs": "bronze_legs"}
TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "mythos", "eclipse")
BH = [t for t in TIERS if os.path.isdir(os.path.join(ASSETS, "male", "2x", f"armour_{t}_bh_hd"))]


def test_set_needs_body_and_legs_only():
    assert P.set_tier(BODY_LEGS) == "bronze"
    assert P.set_tier({"body": "recruit_bronze_chainbody", "legs": "bronze_chainlegs"}) == "bronze"
    assert P.set_tier({"body": "bronze_body", "legs": "iron_legs"}) is None
    for sex in ("male", "female"):
        assert P.armour_layer_for(sex, BODY_LEGS) == "armour_bronze_bh_hd"
        assert P.armour_layer_for(sex, dict(BODY_LEGS, helmet="iron_helmet")) == "armour_bronze_bh_hd"
        for t in TIERS:
            bl = {"body": f"{t}_body", "legs": f"{t}_legs"}
            if t in BH:  # bare-head art installed: body + legs alone show the set
                assert P.armour_layer_for(sex, bl) == f"armour_{t}_bh_hd", t
                assert P.armour_layer_for(sex, dict(bl, helmet=f"{t}_helmet")) == f"armour_{t}_bh_hd", t
            elif os.path.isdir(os.path.join(ASSETS, sex, "2x", f"armour_{t}_hd")):  # full-set rule kept
                assert P.armour_layer_for(sex, bl) is None, t
                assert P.armour_layer_for(sex, dict(bl, helmet=f"{t}_helmet")) == f"armour_{t}_hd", t


def test_strips_complete():
    anchors = json.load(open(os.path.join(ASSETS, "helmets", "action_anchors.json")))
    for sex in ("male", "female"):
        for sc in ("1x", "2x"):
            for a, t in ((a, t) for t in BH for a in ANIMS):
                for f in "sen":
                    b = os.path.join(ASSETS, sex, sc, f"armour_{t}_bh_hd", f"{a}_{f}")
                    for suf in ("", "_skin", "_hair"):
                        assert os.path.isfile(b + suf + ".png"), b + suf
                    if sc == "2x" and a not in ("idle", "walk"):
                        k = f"{sex}/armour_{t}_bh_hd/{a}_{f}"
                        assert k in anchors and all(anchors[k]), k


def _draw(sex, eq, anim, appearance=None, facing=1):
    surf = pygame.Surface((240, 240), pygame.SRCALPHA)
    P.draw_player(surf, sex, appearance, 120, 210, 96, 0.4, anim=anim, progress=0.5, facing=facing, equipment=eq)
    return surf


def test_helmet_overlay_only_when_worn():
    calls = []
    real = H.draw, H.draw_action
    # record only calls that would put a helmet on (H.draw returns early when none is worn)
    H.draw = lambda *a, **k: calls.append("draw") if H.helmet_tier(a[5]) else None
    H.draw_action = lambda *a, **k: calls.append("action") if H.helmet_tier(a[4]) else None
    try:
        _overlay_checks(calls)
    finally:
        H.draw, H.draw_action = real


def _overlay_checks(calls):
    for sex in ("male", "female"):
        for anim in ("idle", "walk", "melee", "chop"):
            eq = dict(BODY_LEGS, weapon="bronze_sword")
            calls.clear(); _draw(sex, eq, anim)
            assert P.last_draw.get("whole") == "armour_bronze_bh_hd", (sex, anim, P.last_draw)
            assert not calls, (sex, anim, calls)
            calls.clear(); _draw(sex, dict(eq, helmet="bronze_helmet"), anim)
            assert P.last_draw.get("whole") == "armour_bronze_bh_hd"
            assert calls == (["draw"] if anim in ("idle", "walk") else ["action"]), (sex, anim, calls)


def test_hair_follows_hair_colour_and_face_follows_skin():
    import numpy as np
    for sex in ("male", "female"):
        base = P.get_default_appearance(sex)
        px = lambda look: pygame.surfarray.array3d(_draw(sex, BODY_LEGS, "idle", look)).astype(int)
        dark = px(dict(base, hair_colour="black"))
        blonde = px(dict(base, hair_colour="blonde"))
        diff = np.abs(dark - blonde).sum(-1) > 30
        assert diff.sum() > 50, sex
        ys = np.nonzero(diff.any(0))[0]
        # hair changes stay in the head (top quarter of the figure), never the armour
        fig = np.nonzero(pygame.surfarray.array_alpha(_draw(sex, BODY_LEGS, "idle", base)).any(0))[0]
        assert ys.max() < fig.min() + 0.25 * (fig.max() - fig.min()), (sex, ys.max(), fig.min(), fig.max())


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    bad = 0
    for n, f in tests:
        try:
            f(); print("ok  ", n)
        except AssertionError as e:
            bad += 1; print("FAIL", n, e)
    print(f"{len(tests) - bad}/{len(tests)} bare-head bronze tests passed")
    sys.exit(1 if bad else 0)
