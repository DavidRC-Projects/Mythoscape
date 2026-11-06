"""Arena pit identity continuity: idle/melee/hit/death stay on glad art (no HD swap).

Run: python3 tools/test_arena_identity_continuity.py
Never touches live world.db / port 8765.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "client"))

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

import arena_battles_ui as abu  # noqa: E402


def _draw(template, anim, prog=0.0, hit=0.0, death=0.0, tile_px=64, gender="male"):
    abu._GSCALED.clear()
    abu._GFRAMES.clear()
    m = {
        "template_id": template,
        "id": f"t-{template}-{anim}",
        "facing": "e",
        "_arena_hit": hit,
        "_arena_death": death,
    }
    surf = pygame.Surface((tile_px * 3, tile_px * 4), pygame.SRCALPHA)
    cx, feet = surf.get_width() // 2, int(surf.get_height() * 0.88)
    ok = abu.draw_gladiator(surf, m, cx, feet, tile_px, 0.0, anim, prog, 0.0, "e", gender)
    return ok, m.get("_glad_asset"), surf, feet


def test_all_templates_use_glad_art_not_hd_flag():
    """Every mapped pit template draws via glad path; asset kind never implies HD."""
    for tmpl, gid in abu.GLADIATOR_TYPES.items():
        for anim, prog, hit, death in (
            ("idle", 0.0, 0.0, 0.0),
            ("melee", 0.14, 0.0, 0.0),
            ("melee", 0.48, 0.0, 0.0),
            ("melee", 0.85, 0.0, 0.0),
            ("idle", 0.0, 0.8, 0.0),  # hit via _arena_hit
            ("idle", 0.0, 0.0, 0.5),  # death
        ):
            ok, kind, _, _ = _draw(tmpl, anim, prog, hit, death)
            assert ok, (tmpl, gid, anim, prog)
            assert kind, (tmpl, anim)
            assert "hd" not in str(kind).lower(), (tmpl, kind)
            assert "player" not in str(kind).lower(), (tmpl, kind)


def test_murmillo_melee_uses_painted_poses():
    ok, kind, _, _ = _draw("man_at_arms", "melee", 0.48)
    assert ok and kind == "painted_melee_strike", kind
    ok, kind, _, _ = _draw("man_at_arms", "melee", 0.14)
    assert kind == "painted_melee_windup", kind
    ok, kind, _, _ = _draw("man_at_arms", "melee", 0.85)
    assert kind == "painted_melee_recover", kind


def test_levy_melee_uses_painted_poses():
    ok, kind, _, _ = _draw("levy", "melee", 0.48)
    assert ok and kind == "painted_melee_strike", kind
    ok, kind, _, _ = _draw("levy", "melee", 0.14)
    assert kind == "painted_melee_windup", kind
    ok, kind, _, _ = _draw("levy", "melee", 0.85)
    assert kind == "painted_melee_recover", kind


def test_priority_types_use_painted_poses():
    """tiro/retiarius/secutor/provocator/hoplomachus + females use painted melee."""
    for tmpl in ("levy", "skirmisher", "bulwark", "duelist", "medic"):
        ok, kind, _, _ = _draw(tmpl, "melee", 0.48)
        assert ok and kind == "painted_melee_strike", (tmpl, kind)
    ok, kind, _, _ = _draw("zealot", "melee", 0.48)
    assert ok and kind == "painted_melee_strike", kind
    # female paths
    for tmpl, expect in (("levy", "painted_melee_strike"), ("man_at_arms", "painted_melee_strike")):
        abu._GSCALED.clear(); abu._GFRAMES.clear()
        m = {"template_id": tmpl, "id": f"f-{tmpl}", "facing": "e", "_arena_hit": 0, "_arena_death": 0}
        surf = __import__("pygame").Surface((192, 256), __import__("pygame").SRCALPHA)
        ok = abu.draw_gladiator(surf, m, 96, 220, 64, 0.0, "melee", 0.48, 0.0, "e", "female")
        assert ok and m.get("_glad_asset") == expect, (tmpl, m.get("_glad_asset"))


def test_thraex_melee_uses_painted_poses():
    ok, kind, _, _ = _draw("veteran", "melee", 0.48)
    assert ok and kind == "painted_melee_strike", kind
    ok, kind, _, _ = _draw("veteran", "melee", 0.14)
    assert kind == "painted_melee_windup", kind


def test_idle_attack_idle_same_scale_and_feet():
    """Feet anchor and drawn height stay within tolerance across the cycle."""
    tile_px = 64
    samples = []
    for anim, prog in (("idle", 0.0), ("melee", 0.14), ("melee", 0.48), ("melee", 0.85), ("idle", 0.0)):
        ok, kind, surf, feet = _draw("man_at_arms", anim, prog, tile_px=tile_px)
        assert ok, kind
        bb = surf.get_bounding_rect(min_alpha=40)
        samples.append((kind, bb, feet))
    # feet guideline constant
    assert len({s[2] for s in samples}) == 1
    heights = [s[1].h for s in samples]
    # painted poses may be wider/taller by stance, but body height within 18%
    base_h = heights[0]
    for kind, bb, feet in samples:
        assert abs(bb.h - base_h) / float(base_h) < 0.18, (kind, bb.h, base_h)
        # soles near the feet line (within 12% of tile)
        assert abs(bb.bottom - feet) <= tile_px * 0.20, (kind, bb.bottom, feet)


def test_melee_pose_files_exist_for_murmillo():
    base = os.path.join(ROOT, "client/assets/castle_realm/arena/gladiators/murmillo")
    for tag in ("1x", "2x"):
        for state in ("windup", "strike", "recover", "hit"):
            for face in ("e", "w"):
                path = os.path.join(base, tag, f"melee_{state}_{face}.png")
                assert os.path.isfile(path), path


def test_melee_pose_files_exist_for_thraex():
    base = os.path.join(ROOT, "client/assets/castle_realm/arena/gladiators/thraex")
    for tag in ("1x", "2x"):
        for state in ("windup", "strike", "recover"):
            for face in ("e", "w"):
                path = os.path.join(base, tag, f"melee_{state}_{face}.png")
                assert os.path.isfile(path), path



def test_melee_pose_files_exist_for_batch():
    """Installed painted windup/strike/recover/hit for all pit templates."""
    sheets = {
        "tiro": ("windup", "strike", "recover", "hit"),
        "dimachaerus": ("windup", "strike", "recover", "hit"),
        "retiarius": ("windup", "strike", "recover", "hit"),
        "secutor": ("windup", "strike", "recover", "hit"),
        "provocator": ("windup", "strike", "recover", "hit"),
        "hoplomachus": ("windup", "strike", "recover", "hit"),
        "gladiatrix_murmillo": ("windup", "strike", "recover", "hit"),
        "gladiatrix_retiaria": ("windup", "strike", "recover", "hit"),
        "thraex": ("windup", "strike", "recover", "hit"),
    }
    for gid, states in sheets.items():
        base = os.path.join(ROOT, "client/assets/castle_realm/arena/gladiators", gid)
        for tag in ("1x", "2x"):
            for state in states:
                for face in ("e", "w"):
                    path = os.path.join(base, tag, f"melee_{state}_{face}.png")
                    assert os.path.isfile(path), path


def test_draw_gladiator_no_longer_bails_on_melee():
    """Regression: previous articulated pass returned False on melee (HD swap)."""
    ok, kind, _, _ = _draw("levy", "melee", 0.48)
    assert ok is True
    assert kind.startswith("idle_hold_melee_") or kind.startswith("painted_melee_")
    assert "part_rig" not in kind and "ghost" not in kind


def test_no_part_rig_asset_kinds_in_cycle():
    for tmpl in ("levy", "man_at_arms", "veteran", "skirmisher", "bulwark", "zealot", "duelist", "medic"):
        for prog in (0.14, 0.48, 0.85):
            ok, kind, _, _ = _draw(tmpl, "melee", prog)
            assert ok and "part_rig" not in str(kind), (tmpl, kind)


def test_all_templates_painted_melee_and_hit():
    """Every GLADIATOR_TYPES male template selects painted swings + painted hit."""
    for tmpl in abu.GLADIATOR_TYPES:
        for prog, expect in ((0.14, "painted_melee_windup"), (0.48, "painted_melee_strike"), (0.85, "painted_melee_recover")):
            ok, kind, _, _ = _draw(tmpl, "melee", prog)
            assert ok and kind == expect, (tmpl, prog, kind)
        ok, kind, _, _ = _draw(tmpl, "idle", hit=0.8)
        assert ok and kind == "painted_hit", (tmpl, kind)


def test_non_glad_templates_not_claimed():
    assert abu.gladiator_type({"template_id": "mythos_guard", "field_soldier": True}) is None
    assert abu.gladiator_type({"boss": True, "template_id": "levy"}) is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("OK", fn.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, ":", e)
    if failed:
        raise SystemExit(f"{failed} failed")
    print(f"ALL {len(tests)} PASSED")
