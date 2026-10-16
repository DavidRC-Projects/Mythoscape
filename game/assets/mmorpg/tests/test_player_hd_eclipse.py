"""Eclipse HD layers: catalogue entries, files on disk, item -> layer mapping.

Run: python3 tests/test_player_hd_eclipse.py   (or pytest tests/)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import player_hd_client as hd  # noqa: E402

LAYERS = [
    "arm_helm_eclipse", "arm_platebody_eclipse", "arm_platelegs_eclipse",
    "arm_gauntlets_eclipse", "arm_sabatons_eclipse",
    "wpn_sword_eclipse", "wpn_axe_eclipse",
]


def test_catalogue_has_eclipse_layers():
    cat = hd._load_catalogue()
    ids = {e["id"] for g in ("armour_layers", "weapon_layers") for e in cat[g]}
    for layer in LAYERS:
        assert layer in ids, layer


def test_files_exist_all_scales():
    for sex in ("male", "female"):
        for scale in ("1x", "2x", "4x"):
            for layer in LAYERS:
                for strip in ("idle_s", "melee_e"):
                    path = os.path.join(hd._BASE, sex, scale, layer, strip + ".png")
                    assert os.path.isfile(path), path


def test_item_mapping():
    assert hd._helm_spec("eclipse_helmet") == ("arm_helm_eclipse", None)
    assert [n for n, _t in hd._body_spec("eclipse_body")] == ["arm_platebody_eclipse", "arm_gauntlets_eclipse"]
    assert [n for n, _t in hd._legs_spec("eclipse_legs")] == ["arm_platelegs_eclipse", "arm_sabatons_eclipse"]
    assert hd._weapon_spec("eclipse_cleaver") == ("wpn_axe_eclipse", None)
    assert hd._weapon_spec("eclipse_sword") == ("wpn_sword_eclipse", None)
    # other tiers unchanged
    assert hd._weapon_spec("steel_axe")[0] == "wpn_axe"
    assert hd._helm_spec("steel_helmet")[0] == "arm_helm"


def test_covers():
    kept, swing = hd._apply_covers(
        [("hair_crop", None, {}, "hair"), ("top_linen_shirt", None, {}, "top"),
         ("shoes_leather", None, {}, "shoes"), ("acc_leather_gloves", None, {}, "acc_leather_gloves")],
        {"helmet": "eclipse_helmet", "body": "eclipse_body", "legs": "eclipse_legs", "weapon": "eclipse_cleaver"},
        "idle",
    )
    names = [k[0] for k in kept]
    for gone in ("hair_crop", "top_linen_shirt", "shoes_leather", "acc_leather_gloves"):
        assert gone not in names
    assert swing == "wpn_axe_eclipse"


def test_draw_headless():
    import pygame
    pygame.display.init()
    pygame.display.set_mode((8, 8))
    surf = pygame.Surface((400, 400), pygame.SRCALPHA)
    eq = {"helmet": "eclipse_helmet", "body": "eclipse_body", "legs": "eclipse_legs", "weapon": "eclipse_cleaver"}
    for sex in ("male", "female"):
        for tile in (32, 48, 64, 96):
            for anim, prog in (("idle", None), ("walk", None), ("melee", 0.5)):
                for face in ("s", "e", "n", "w"):
                    assert hd.draw_player(surf, sex, None, 200, 300, tile, 0.3, anim=anim,
                                          progress=prog, facing=face, equipment=eq) is not False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
