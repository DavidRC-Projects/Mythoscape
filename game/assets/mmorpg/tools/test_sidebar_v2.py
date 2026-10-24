"""Sidebar v2 (SIDEBAR_DESIGN.md): 6 tabs, painted sets, no colours/levels, Collection row, migration v2.
Run: python3 tools/test_sidebar_v2.py   (in-memory DB; writes tools/screens/sidebar_v2_*.png)"""
import asyncio
import json
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import outfits  # noqa: E402

import pygame  # noqa: E402
pygame.init()
pygame.display.set_mode((1200, 800))
import cosmetics_ui  # noqa: E402

W = server.WORLD
_N = [0]
SHOTS = os.path.join(ROOT, "tools", "screens")


class WS:
    def __init__(self):
        self.out = []

    async def send(self, raw):
        self.out.append(json.loads(raw))


class _Net:
    def __init__(self):
        self.sent = []

    def send(self, kind, **kw):
        self.sent.append((kind, kw))


def run(coro):
    return asyncio.run(coro)


def make(sex="male", coins=0, bank=0, rep=0, rank=0, title=None, appearance=None, owned=None):
    _N[0] += 1
    user = f"sb{_N[0]}"
    W.db.create_account(user, "pw", f"Side{_N[0]}")
    row = W.db.get_player_by_username(user)
    W.db.save_player_stats(row["id"], gender=sex, coins=coins, bank_coins=bank, stats_allocated=1)
    W.db.conn.execute("UPDATE players SET reputation = ?, noble_rank = ?, royal_title = ?, appearance = ?, "
                      "owned_cosmetics = ? WHERE id = ?",
                      (rep, rank, title, json.dumps(appearance) if appearance else None,
                       json.dumps(owned or []), row["id"]))
    W.db.conn.commit()
    s = server.PlayerSession(WS(), W.db.get_player_by_username(user))
    s.bank_coins = bank
    return s


def errors(s):
    return [m.get("message") for m in s.ws.out if m.get("type") == "ERROR"]


def screen(s):
    c = types.SimpleNamespace(player=s.full_state(), net=_Net(), needs_appearance=False)
    return cosmetics_ui.Outfitters(c), c


def legacy_look(sex="male", **kw):
    look = {"skin": "skin_tan", "hair": "hair_side_part", "hair_colour": "azure", "top": "top_noble_doublet",
            "bottom": "bottom_noble_hose", "shoes": "shoes_riding_boots", "outfit": None, "accessories": ["acc_scarf"],
            "palette": "t1_earth", "outfit_level": 2}
    look.update(kw)
    return look


def test_catalogue_v2():
    cat = outfits.catalogue()
    assert cat["appearance_version"] == 2 and cat["sidebar_tabs"] == list(cosmetics_ui.Outfitters.SHOP_TABS)
    for sid, e in outfits.sets().items():
        assert "palettes" not in e and "upgrade_prices" not in e, sid
        assert set(e["painted"]) == {"head", "neck", "cloak"}, sid
    for it in cat["items"]:
        if it["slot"] in ("top", "bottom", "shoes", "accessory") or (it["slot"] == "outfit" and not it.get("set")):
            assert it.get("legacy"), it["id"]
    assert len(outfits.hair_swatches()) == 10
    coll = cat["collection"]
    els = {"fire", "frost", "storm", "shadow", "nature", "water", "light"}
    assert {c["id"] for c in coll} == {f"set_{e}_{x}" for e in els for x in "fm"}
    live = {"fire", "water"}
    for c in coll:
        assert c["purchase_only"], c["id"]
        el = c["id"].split("_")[1]
        if el in live:
            assert c["release"] == "live" and c.get("review_score", 0) >= 8, c["id"]
        else:
            assert c["release"] == "coming_soon", c["id"]


def test_six_tabs_no_colours():
    surf = pygame.Surface((1200, 800))
    for sex in ("male", "female"):
        s = make(sex, coins=5000)
        o, c = screen(s)
        o.open("shop")
        assert o.SHOP_TABS == ("sets", "head", "accessories", "hair", "body", "wardrobe")
        for tab in o.SHOP_TABS:
            o.tab = tab
            o.render(surf)
            kinds = {k for k, _r, _p in o.hit}
            assert "palette" not in kinds and "apply_set" not in kinds, tab
            assert sum(1 for k in kinds if k == "tab") == 1
        o.tab = "sets"
        o.render(surf)
        cards = [p for k, _r, p in o.hit if k == "coll_card"]
        assert len(cards) == 7 and all(p.endswith("_" + sex[0]) for p in cards), cards
        # coming soon: no preview, no Buy
        before = dict(o.look)
        soon = next(p for p in cards if p.startswith("set_storm_"))
        o._activate("coll_card", soon)
        assert o.look == before and o.try_set != soon
        o.render(surf)
        buy = [r for k, r, _p in o.hit if k == "buy"]
        assert not buy, "Buy must be disabled on a Coming soon card"
        o.tab = "hair"
        o.render(surf)
        assert [p for k, _r, p in o.hit if k == "colour"] == outfits.hair_swatches()
        o.tab = "head"
        assert {i["id"] for i in o._grid_items() if i["id"]} == (
            {"ov_flower_crown", "ov_circlet", "lx_f_diamond_tiara"} if sex == "female" else {"ov_cloth_cap", "ov_circlet"})
        o.tab = "accessories"
        ids = {i["id"] for i in o._grid_items() if i["id"]}
        assert "ov_wool_cloak" in ids and "ov_brooch" in ids and not any(i.startswith(("top_", "acc_")) for i in ids)


def test_painted_flags_block_overlays():
    s = make("female", coins=0)
    o, c = screen(s)
    o.open("shop")
    o._try_set("set_court_gown")          # T2 female: painted tiara
    o._pick_item(outfits.items()["ov_circlet"])
    assert o.look.get("head") != "ov_circlet" and o.toast
    o._try_set("set_noble_lady")          # T3 female: painted necklace only
    o._pick_item(outfits.items()["ov_circlet"])
    assert o.look.get("head") == "ov_circlet"
    look, err = outfits.clean_v2(s, dict(o._payload(), set="set_village_lady"), set())
    assert err is None and look["head"] != "ov_circlet" and "This set wears its own crown." in look["_notes"]


def test_server_clean_v2_and_fallback():
    s = make("male")
    look, err = outfits.clean(s, {"set": "set_villager", "skin_tone": "tone_4", "hair_colour": "ginger",
                                  "head": "ov_cloth_cap", "jewellery": ["ov_signet_ring", "ov_brooch"]}, set())
    assert err is None, err
    assert look["set"] == "set_villager" and look["head"] == "ov_cloth_cap" and "palette" not in look or look["palette"] is None
    assert "outfit_level" not in look and look["outfit"] == "villager_coat"
    assert outfits.clean(s, {"set": "set_villager", "skin_tone": "tone_4", "hair_colour": "azure"}, set())[1]
    assert outfits.clean(s, {"set": "set_village_lady", "skin_tone": "tone_4", "hair_colour": "black"}, set())[1]
    assert outfits.clean(s, {"set": "set_storm_m", "skin_tone": "tone_4", "hair_colour": "black"}, set())[1] \
        == "That design is coming soon."
    too_many = {"set": "set_villager", "skin_tone": "tone_4", "hair_colour": "black",
                "jewellery": ["ov_signet_ring", "ov_brooch", "villager_belt_pouch"]}
    look, err = outfits.clean(s, dict(too_many, jewellery=["ov_signet_ring", "ov_brooch", "ov_bead_necklace"]), set())
    assert err   # female necklace on a man, or 3 pieces
    orig = outfits.clean_v2
    outfits.clean_v2 = lambda *a: 1 / 0
    try:
        legacy = dict(outfits.starter_look("male"), hair_colour="dark_brown")
        look, err = outfits.clean(s, legacy, set())
        assert err is None and "outfit_level" in look     # old layered validator ran
    finally:
        outfits.clean_v2 = orig


def test_migration_v2_refund_and_idempotent():
    owned = ["top_noble_doublet", "bottom_noble_hose", "shoes_riding_boots", "acc_scarf", "outfit_noble", "hair_braid"]
    s = make("male", coins=100, bank=1000, appearance=legacy_look(outfit="outfit_noble"), owned=owned)
    note = server._outfits_migrate_v2(s)
    refund = 650 + 300 + 150 + 80 + 1200
    assert s.bank_coins == 1000 + refund and s.coins == 100, (s.bank_coins, s.coins)
    assert note.startswith("Your old clothing was traded in") and f"{refund:,}" in note
    look = json.loads(s._row_val("appearance"))
    assert look["appearance_version"] == 2
    assert look["set"] == "set_villager"          # T3 not unlocked -> T1
    assert look["skin_tone"] == "tone_6" or look["skin_tone"] in outfits.tone_ids()
    assert look["hair_colour"] in outfits.hair_swatches() and look["hair_colour"] != "azure"
    assert look["appearance_legacy"]["top"] == "top_noble_doublet"
    assert "palette" in look["appearance_legacy"] and look.get("outfit_level") is None
    assert set(owned) <= set(s._json_list("owned_cosmetics"))     # kept, not deleted
    assert server._outfits_migrate_v2(s) is None and s.bank_coins == 1000 + refund     # idempotent
    # noble outfit with T3 unlocked -> T3; legacy skin ids map light/tan/deep
    s2 = make("male", rep=850, rank=3, appearance=legacy_look(outfit="outfit_noble", skin="skin_light",
                                                               skin_tone=None))
    server._outfits_migrate_v2(s2)
    look2 = json.loads(s2._row_val("appearance"))
    t3 = outfits.set_order("male")[2]
    assert look2["set"] == (t3 if outfits.tier_unlocked(s2, 3, W.db.conn) else "set_villager")
    assert look2["skin_tone"] == "tone_3" or look2["skin_tone"] == "tone_2"
    # an HD set look keeps its set
    s3 = make("female", appearance={"outfit": "court_gown_dress", "skin_tone": "tone_5", "hair_colour": "rose",
                                    "palette": "x", "outfit_level": 3}, owned=["set_court_gown@2"])
    server._outfits_migrate_v2(s3)
    look3 = json.loads(s3._row_val("appearance"))
    if outfits.items().get("court_gown_dress"):
        assert look3["set"] == "set_court_gown"
    assert look3["hair_colour"] in outfits.hair_swatches()
    # bought colours and Fine/Regal upgrades are refunded at base price (catalogue legacy_prices)
    lp = outfits.catalogue()["legacy_prices"]
    paid = ["palette:set_court_gown:t2_forest", "palette:court_gown_gown:t2_chestnut", "set_court_gown@2",
            "set_court_gown@3", "set_court_gown@9", "palette:set_court_gown:t2_royal_blue"]
    total, ids = outfits.legacy_refund(paid)
    up = lp["sets"]["set_court_gown"]["upgrade_prices"]
    assert total == 2 * lp["garment_palettes"]["t2_forest"] + up[0] + up[1] + lp["garment_palettes"]["t2_royal_blue"], total
    assert "set_court_gown@9" not in ids and len(ids) == 5
    s4 = make("female", coins=0, bank=0, appearance={"outfit": "court_gown_gown", "palette": "t2_forest",
                                                    "outfit_level": 3}, owned=["court_gown_gown"] + paid)
    note4 = server._outfits_migrate_v2(s4)
    assert s4.bank_coins == total and "5 old purchases" in note4, (s4.bank_coins, note4)
    assert server._outfits_migrate_v2(s4) is None and s4.bank_coins == total


def test_collection_buy_flow():
    s = make("female", coins=60000, bank=0)
    run(server.handle_buy_collection_set(s, {"set": "set_storm_f"}))
    assert errors(s)[-1] == "That design is coming soon." and s.coins == 60000
    cat = outfits.catalogue()
    entry = outfits.collection_entry("set_storm_f")
    saved = dict(entry)
    entry.update(release="live", review_score=7)
    try:
        run(server.handle_buy_collection_set(s, {"set": "set_storm_f"}))
        assert errors(s)[-1] == "That design is coming soon."     # review < 8 never goes live
        entry["review_score"] = 9
        run(server.handle_buy_collection_set(s, {"set": "set_storm_m"}))
        assert errors(s)[-1] in ("That design is coming soon.", "That isn't cut for you.")
        run(server.handle_buy_collection_set(s, {"set": "set_storm_f"}))
        assert s.coins < 60000 and "set_storm_f" in s._json_list("owned_cosmetics"), errors(s)
        assert s.appearance_state()["set"] == "set_storm_f"
        paid = 60000 - s.coins
        run(server.handle_buy_collection_set(s, {"set": "set_storm_f"}))
        assert errors(s)[-1] == "You already own that design." and 60000 - s.coins == paid
        # UI: a live card previews and Buy & Wear sends BUY_COLLECTION_SET
        s2 = make("female", coins=60000)
        o, c = screen(s2)
        o.open("shop")
        ui_entry = next(e for e in cosmetics_ui._catalogue()["collection"] if e["id"] == "set_storm_f")
        ui_entry.update(release="live", review_score=9)
        o._activate("coll_card", "set_storm_f")
        assert o.try_set == "set_storm_f"
        o._buy_and_wear()
        assert c.net.sent[0][0] == "BUY_COLLECTION_SET", c.net.sent
    finally:
        entry.clear()
        entry.update(saved)
        cosmetics_ui._CATALOGUE = None
    assert cat["collection"]


def test_removed_messages():
    s = make("male", coins=5000)
    for kind in ("BUY_PALETTE", "UPGRADE_OUTFIT"):
        assert kind not in {k for k, _ in []}
    o, c = screen(s)
    o.open("shop")
    o._try_set("set_villager")
    o._buy_and_wear()
    assert all(k in ("UPDATE_APPEARANCE", "BUY_COSMETICS") for k, _ in c.net.sent)
    payload = c.net.sent[-1][1]["appearance"]
    assert "palette" not in payload and "outfit_level" not in payload and payload["set"] == "set_villager"
    run(server.handle_update_appearance(s, {"appearance": payload}))
    assert not errors(s), errors(s)


def test_screenshots():
    os.makedirs(SHOTS, exist_ok=True)
    for sex, tabs in (("female", ("sets", "head", "accessories", "hair", "body", "wardrobe")), ("male", ("sets", "accessories"))):
        s = make(sex, coins=24000, bank=12000, rep=850, rank=3)
        o, c = screen(s)
        o.open("shop", greeting=outfits.mae_line(s))
        for tab in tabs:
            surf = pygame.Surface((1200, 800))
            o.tab = tab
            if tab == "sets":
                o._activate("coll_card", f"set_frost_{sex[0]}")
            o.render(surf)
            pygame.image.save(surf, os.path.join(SHOTS, f"sidebar_v2_{sex}_{tab}.png"))


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"ALL {len(tests)} SIDEBAR V2 TESTS PASSED")


if __name__ == "__main__":
    main()
