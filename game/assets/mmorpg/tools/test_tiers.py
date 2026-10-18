"""Armour tiers: stats, weapon class stats, drops, glows, tier art fallback. Run: python3 tools/test_tiers.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import content as C  # noqa: E402

TABLE = {  # tier: (sword, sword att/str, axe att/str, helm, body, legs)
    "bronze": ("bronze_sword", (4, 5), (3, 9), 5, 14, 11),
    "iron": ("iron_sword", (10, 11), (6, 16), 9, 24, 18),
    "steel": ("steel_longsword", (16, 18), (9, 24), 14, 36, 28),
    "mithril": ("mithril_sword", (26, 28), (14, 36), 20, 52, 40),
    "adamant": ("adamant_sword", (38, 40), (20, 50), 28, 72, 56),
    "mythos": ("mythos_longsword", (100, 100), (54, 128), 100, 100, 100),
}


def test_stats_table():
    for t, (sword, s, a, h, b, l) in TABLE.items():
        it = C.ITEMS
        assert (it[sword]["att_bonus"], it[sword]["str_bonus"]) == s, t
        axe = it[f"{t}_battleaxe"]
        assert (axe["att_bonus"], axe["str_bonus"]) == a, t
        assert it[f"{t}_helmet"]["def_bonus"] == h and it[f"{t}_body"]["def_bonus"] == b
        assert it[f"{t}_legs"]["def_bonus"] == l
    assert C.ITEMS["mythos_helmet"]["att_bonus"] == 100


def test_weapon_class_stats():
    assert C.weapon_stats("bronze_sword") == {"attack_speed": 4, "crit_chance": 0.08, "heavy_bonus": 0.10}
    assert C.weapon_stats("mythos_battleaxe") == {"attack_speed": 5, "crit_chance": 0.05, "heavy_bonus": 0.25}
    e = C.weapon_stats("eclipse_cleaver")
    assert e["attack_speed"] == 5 and abs(e["crit_chance"] - 0.07) < 1e-9 and abs(e["heavy_bonus"] - 0.30) < 1e-9
    e = C.weapon_stats("eclipse_sword")
    assert abs(e["crit_chance"] - 0.10) < 1e-9 and abs(e["heavy_bonus"] - 0.15) < 1e-9
    assert C.weapon_stats("bronze_pickaxe") is None and C.weapon_stats("shortbow") is None
    assert abs(C.SWING_SECONDS_PER_SPEED * 4 - 1.2) < 1e-9     # swords keep the old 1.2s pace


def test_every_tier_item_has_a_source():
    sources = set()
    for shop in C.SHOPS.values():
        sources |= set(shop["stock"])
    for m in C.MONSTERS.values():
        for d in m.get("drops") or []:
            ids = d[0] if isinstance(d[0], tuple) else (d[0],)
            sources |= set(ids)
    for r in (C.CRAFT_RECIPES.values() if isinstance(C.CRAFT_RECIPES, dict) else C.CRAFT_RECIPES):
        out = r.get("output") if isinstance(r, dict) else None
        if out:
            sources.add(out[0])
    for t, (sword, *_r) in TABLE.items():
        for iid in (sword, f"{t}_battleaxe", f"{t}_helmet", f"{t}_body", f"{t}_legs"):
            assert iid in sources, iid


def test_glows():
    import eclipse_fx as fx
    full = lambda t: {"helmet": f"{t}_helmet", "body": f"{t}_body", "legs": f"{t}_legs"}
    for t in ("bronze", "iron", "steel"):
        assert fx.fx_tier(full(t)) is None
    assert fx.fx_tier(full("mithril")) == "mithril" and fx.fx_tier(full("adamant")) == "adamant"
    assert fx.fx_tier(full("mythos")) == "mythos"
    assert fx.fx_tier({"helmet": "mythos_helmet", "body": "mythos_body"}) is None      # full set only
    assert fx.fx_tier({"weapon": "eclipse_sword"}) == "eclipse"                         # any Eclipse piece
    assert fx.SPARKLE_TIERS["mithril"]["aura"] == (156, 212, 255)
    assert fx.SPARKLE_TIERS["adamant"]["aura"] == (156, 255, 180)
    assert fx.SPARKLE_TIERS["mythos"]["aura"] == (255, 156, 156)


def test_tier_art_fallback():
    import player_hd_client as p
    p._TIER_INDEX = {"fake_helmet": [("arm_helm_notyet", {"male", "female"})]}
    p._ART_PRESENT.clear()
    assert p._helm_spec("fake_helmet", "male")[0] == "arm_helm"           # art missing -> tinted generic
    p._TIER_INDEX = None
    assert p.base_layer("wpn_axe_bronze") == "wpn_axe" and p.base_layer("wpn_sword_eclipse") == "wpn_sword"
    assert p.base_layer("arm_platebody_mithril") == "arm_platebody"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
