"""Sparkle tier rules and aura caching."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import eclipse_fx as fx  # noqa: E402


def _set(tier, body="body", legs="legs"):
    return {"helmet": f"{tier}_helmet", "body": f"{tier}_{body}", "legs": f"{tier}_{legs}"}


def test_fx_tier_rules():
    assert fx.fx_tier({"weapon": "eclipse_sword"}) == "eclipse"
    assert fx.fx_tier(_set("mythos")) == "mythos"
    assert fx.fx_tier({**_set("mythos"), "weapon": "eclipse_cleaver"}) == "eclipse"
    assert fx.fx_tier({"body": "mythos_body"}) is None
    assert fx.fx_tier(_set("mithril", "chainbody", "chainlegs")) == "mithril"
    assert fx.fx_tier(_set("adamant")) == "adamant"
    assert fx.fx_tier({"helmet": "mithril_helmet", "body": "adamant_body", "legs": "adamant_legs"}) is None
    assert fx.fx_tier(_set("steel")) is None
    assert fx.fx_tier({"weapon": "mithril_sword"}) is None
    assert fx.fx_tier({}) is None and fx.fx_tier(None) is None


def test_ids_exist_and_equippable():
    from content import ITEMS
    for spec in fx.SPARKLE_TIERS.values():
        for iid in spec["ids"]:
            assert ITEMS[iid].get("equip_slot"), iid


def test_aura_cached():
    pygame.init()
    s = pygame.Surface((40, 60), pygame.SRCALPHA)
    s.fill((200, 200, 200, 255), (10, 10, 20, 40))
    a = fx.aura_surface(s, 1.0, "eclipse")
    assert fx.aura_surface(s, 1.0, "eclipse") is a
    assert fx.aura_surface(s, 1.0, "mythos") is not a


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
