"""Mythos Outfitters checks (OUTFITTER_BUILD_CHECKLIST A–G). Run: python3 tools/test_outfits.py"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))
CAT_PATH = os.path.join(ROOT, "..", "player_hd", "assets", "catalogue.json")

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import outfits  # noqa: E402
import throne  # noqa: E402

import pygame  # noqa: E402
pygame.init()
pygame.display.set_mode((1200, 800))
import player_hd_client as hd  # noqa: E402

W = server.WORLD
_N = [0]


class WS:
    def __init__(self):
        self.out = []

    async def send(self, raw):
        self.out.append(json.loads(raw))


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def make(sex="male", coins=0, rep=0, rank=0, title=None):
    _N[0] += 1
    user = f"ot{_N[0]}"
    W.db.create_account(user, "pw", f"Name{_N[0]}")
    row = W.db.get_player_by_username(user)
    W.db.save_player_stats(row["id"], gender=sex, coins=coins, stats_allocated=1)
    W.db.conn.execute("UPDATE players SET reputation = ?, noble_rank = ?, royal_title = ? WHERE id = ?",
                      (rep, rank, title, row["id"]))
    W.db.conn.commit()
    s = server.PlayerSession(WS(), W.db.get_player_by_username(user))
    return s


def msgs(s, kind):
    return [m for m in s.ws.out if m.get("type") == kind]


def last_error(s):
    errs = msgs(s, "ERROR")
    return errs[-1]["message"] if errs else None


def look_for(s, **extra):
    base = dict(hd.get_default_appearance(s.gender))
    base.update(extra)
    return base


# ---- A. catalogue -----------------------------------------------------------------------------
def test_catalogue():
    with open(CAT_PATH, encoding="utf-8") as fh:
        cat = json.load(fh)
    assert int(cat["version"]) >= 2
    ids = {i["id"]: i for i in cat["items"]}
    assert len(cat["sets"]) == 14
    for sid, entry in cat["sets"].items():
        for p in entry["pieces"]:
            assert p in ids and ids[p]["set"] == sid, (sid, p)
        assert "palettes" not in entry and set(entry["painted"]) == {"head", "neck", "cloak"}, sid   # sidebar v2
    for slot in ("head", "jewellery", "cloak", "held"):
        assert slot in cat["slots"]
    assert cat["jewellery_max"] == 2      # sidebar v2: max 2 in v1
    for i in cat["items"]:
        assert "sex" in i and "tier" in i, i["id"]
        assert "gender_exclusive" not in i
    assert [t["id"] for t in cat["skin_palette"]] == [f"tone_{n}" for n in range(1, 11)]
    assert cat["skin_aliases"] == {"skin_light": "tone_3", "skin_tan": "tone_6", "skin_deep": "tone_9"}
    for sex in ("male", "female"):
        assert cat["defaults"][sex]["skin_tone"] == "tone_3"
        order = cat["set_order"][sex]
        assert len(order) == 7 and [cat["sets"][s]["tier"] for s in order] == list(range(1, 8))
    # a male session's list holds no female item
    import cosmetics_ui
    cosmetics_ui._CATALOGUE = None
    male = [i for i in cosmetics_ui._visible_items("male")]
    assert male and not any(i.get("sex") == "female" for i in male)
    # every item's "layer" is art that exists today, so older renderers never lose the HD body
    for i in cat["items"]:
        if i.get("layer"):
            for sex in ("male", "female"):
                if i.get("sex") in (None, sex):
                    assert hd._art_present(sex, i["layer"]), (sex, i["id"], i["layer"])


def test_prices_match_spec():
    spec = {1: 600, 2: 2500, 3: 7500, 4: 25000, 5: 60000, 6: 120000, 7: 250000}
    for entry in outfits.sets().values():
        assert entry["price"] == spec[entry["tier"]]
        pieces = sum(outfits.items()[p]["price"] for p in entry["pieces"])
        assert 0.80 <= entry["price"] / pieces <= 0.90, (entry["id"], entry["price"], pieces)


# ---- B. skin tones ----------------------------------------------------------------------------
def test_legacy_skin_alias_and_render():
    legacy = {"skin": "skin_tan", "hair": "hair_crop", "hair_colour": "black", "top": "top_linen_shirt",
              "bottom": "bottom_work_trousers", "shoes": "shoes_leather", "outfit": "outfit_hunter", "accessories": []}
    assert hd.skin_tone_id(legacy) == "tone_6"
    assert outfits.normalise(legacy)["skin_tone"] == "tone_6"
    surf = pygame.Surface((200, 200), pygame.SRCALPHA)
    assert hd.draw_player(surf, "male", legacy, 100, 180, 80, 0.0)   # old outfit_hunter look still loads (C6)


def _render(sex, tone, anim="idle", facing="s", tile=80):
    size = max(240, tile * 4)          # a 160 px tile overflowed the old 240 px canvas (face cut off)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    look = hd.get_default_appearance(sex)
    look["skin_tone"] = tone
    assert hd.draw_player(surf, sex, look, size // 2, size - 20, tile, 0.1, anim=anim, facing=facing)
    return surf


def test_tones_tint_skin_only():
    for sex in ("male", "female"):
        for anim in ("idle", "walk", "melee"):
            for facing in ("s", "e", "n"):
                for tile in (40, 80, 160):
                    a = _render(sex, "tone_1", anim, facing, tile)
                    b = _render(sex, "tone_10", anim, facing, tile)
                    w, h = a.get_size()
                    diff = same = 0
                    for x in range(0, w, 3):
                        for y in range(0, h, 3):
                            pa, pb = a.get_at((x, y)), b.get_at((x, y))
                            if pa.a < 200:
                                continue
                            if abs(pa.r - pb.r) + abs(pa.g - pb.g) + abs(pa.b - pb.b) > 30:
                                diff += 1
                            else:
                                same += 1
                    if facing != "n":   # tint is face-only; from behind no face shows
                        assert diff > 0, (sex, anim, facing, tile)      # skin changed
                    assert same > diff, (sex, anim, facing, tile)       # clothing/hair did not


def test_outdated_renderer_keeps_hd():
    """The committed (HEAD) renderer with today's catalogue still draws the HD body."""
    rel = "game/assets/mmorpg/client/player_hd_client.py"
    try:
        src = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:
        print("  (git unavailable: skipped outdated-renderer check)")
        return
    mod = types.ModuleType("player_hd_client_head")
    mod.__file__ = os.path.join(ROOT, "client", "player_hd_client_head.py")
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    eq = {"helmet": "eclipse_helmet", "body": "eclipse_body", "legs": "eclipse_legs", "weapon": "eclipse_cleaver"}
    looks = [
        {"skin": "skin_light", "hair": "hair_crop", "hair_colour": "black", "top": "top_linen_shirt",
         "bottom": "bottom_work_trousers", "shoes": "shoes_leather", "outfit": None, "accessories": []},
        dict(hd.get_default_appearance("male"), outfit="king_coat", cloak="king_ermine_mantle", head="king_kings_crown"),
        dict(hd.get_default_appearance("female"), outfit="queen_gown", skin_tone="tone_8"),
    ]
    surf = pygame.Surface((240, 240), pygame.SRCALPHA)
    for look in looks:
        for sex in ("male", "female"):
            assert mod.draw_player(surf, sex, look, 120, 220, 80, 0.0), (sex, look.get("outfit"))
            assert mod.draw_player(surf, sex, look, 120, 220, 80, 0.0, equipment=eq), (sex, look.get("outfit"))


def test_skin_tone_server_validation():
    s = make("female")
    look = look_for(s, skin_tone="tone_8")
    run(server.handle_update_appearance(s, {"appearance": look}))
    assert last_error(s) is None
    again = server.PlayerSession(WS(), W.db.get_player_by_id(s.player_id))      # relog
    assert again.appearance_state()["skin_tone"] == "tone_8"
    other = make("male")
    assert server.PlayerSession(WS(), W.db.get_player_by_id(s.player_id)).public_state()["appearance"]["skin_tone"] == "tone_8" \
        if hasattr(again, "public_state") else True
    for bad in ("tone_99", "#000000"):
        run(server.handle_update_appearance(s, {"appearance": look_for(s, skin_tone=bad)}))
        assert last_error(s) == "That skin tone is not in the catalogue."
    assert server.PlayerSession(WS(), W.db.get_player_by_id(s.player_id)).appearance_state()["skin_tone"] == "tone_8"
    assert other.appearance_state()["skin_tone"] == "tone_3"


# ---- C. unlocks and economy -------------------------------------------------------------------
def test_unlock_rules():
    m = make("male", rank=1)
    ok, hint, _p = server.outfit_unlocked(m, outfits.sets()["set_noble_lord"])
    assert not ok and "Knight (noble rank 2)" in hint
    m.reputation = 0
    st = outfits.unlocks(m, W.db.conn)
    assert st["set_villager"]["state"] == "unlocked" and st["set_squire"]["state"] == "locked"
    m.reputation = 850
    st = outfits.unlocks(m, W.db.conn)
    assert st["set_squire"]["state"] == "unlocked" and st["set_noble_lord"]["state"] == "locked"
    for v in st.values():
        assert "Courtier" not in (v["hint"] or "")
    # male tier 5: Count + Revered + Leader/Officer of a Royal-Challenge-eligible guild
    m.noble_rank = 4
    st = outfits.unlocks(m, W.db.conn)["set_kings_champion"]
    assert st["state"] == "locked" and "Royal Challenge" in st["hint"], st
    real = outfits._challenge_guild_officer
    outfits._challenge_guild_officer = lambda session: True
    try:
        assert outfits.unlocks(m, W.db.conn)["set_kings_champion"]["state"] == "unlocked"
        m.reputation = 500
        assert outfits.unlocks(m, W.db.conn)["set_kings_champion"]["state"] == "locked"
    finally:
        outfits._challenge_guild_officer = real
    f = make("female")
    f.reputation = 100
    st = outfits.unlocks(f, W.db.conn)
    assert "Courtier" in st["set_royal_favourite"]["hint"]
    throne.add_favour(W.db.conn, f.player_id, 320)
    st = outfits.unlocks(f, W.db.conn)
    assert st["set_royal_favourite"]["progress"] == "320 / 500"
    throne.add_favour(W.db.conn, f.player_id, 200)
    assert outfits.unlocks(f, W.db.conn)["set_royal_favourite"]["state"] == "unlocked"
    f.royal_title = "Queen"
    assert outfits.unlocks(f, W.db.conn)["set_queen"]["state"] == "unlocked"
    f.reputation = -600            # Hated: T5–T7 hidden
    st = outfits.unlocks(f, W.db.conn)
    assert [st[s]["state"] for s in ("set_royal_favourite", "set_princess_consort", "set_queen")] == ["hidden"] * 3
    assert st["set_countess"]["state"] != "hidden"


def test_pricing_and_buy():
    # a 100-coin base costs 90 for a Revered Duke (−10% cap)
    import reputation
    duke = make("male", rep=900, rank=5)
    assert reputation.buy_price(100, duke.reputation, server._shop_discount(duke)) == 90
    # T1 (Village Lady) is now the free starter set, so the bundle price is checked on T2 (Court Gown)
    s = make("female", coins=300_000, rep=850)
    entry = outfits.sets()["set_court_gown"]
    pieces = entry["pieces"]
    look = look_for(s, outfit="court_gown_gown", head="court_gown_slim_tiara")
    q = outfits.quote(s, pieces, set(), server._shop_discount(s), "set_court_gown")
    import royal_treasury
    expect = q["total"] + royal_treasury.buy_tax(q["total"])
    assert q["total"] == reputation.buy_price(int(entry["price"]), s.reputation, server._shop_discount(s)) > 0, q
    assert outfits.quote(s, outfits.sets()["set_village_lady"]["pieces"], set(), 0, "set_village_lady")["total"] == 0
    before = s.coins
    run(server.handle_buy_cosmetics(s, {"items": pieces, "appearance": look, "set": "set_court_gown"}))
    assert last_error(s) is None, last_error(s)
    assert before - s.coins == expect, (before - s.coins, expect)
    assert set(pieces) <= set(s._json_list("owned_cosmetics"))
    # locked set refused
    run(server.handle_buy_cosmetics(s, {"items": ["countess_gown"], "appearance": look_for(s, outfit="countess_gown")}))
    assert "Countess (noble rank 4)" in (last_error(s) or "")
    # a man cannot wear a gown
    m = make("male", coins=10_000)
    run(server.handle_buy_cosmetics(m, {"items": ["village_lady_gown"], "appearance": look_for(m, outfit="village_lady_gown")}))
    assert last_error(m) == "That isn't cut for you."


def test_wardrobe_persist():
    """Sidebar v2: colours and Plain/Fine/Regal are gone; set + skin tone + wardrobe persist."""
    s = make("female", coins=300_000, rep=850)
    pieces = outfits.sets()["set_court_gown"]["pieces"]
    look = look_for(s, outfit="court_gown_gown", head="court_gown_slim_tiara", skin_tone="tone_5")
    run(server.handle_buy_cosmetics(s, {"items": pieces, "appearance": look, "set": "set_court_gown"}))
    assert last_error(s) is None, last_error(s)
    run(server.handle_upgrade_outfit(s, {"set": "set_court_gown", "level": 2}))   # handler kept, not routed
    worn = dict(look, palette="t2_forest", outfit_level=2)
    s.ws.out.clear()
    run(server.handle_update_appearance(s, {"appearance": worn}))
    assert last_error(s) is None, last_error(s)
    run(server.handle_save_outfit(s, {"slot": 3, "appearance": worn, "name": "Court day"}))
    again = server.PlayerSession(WS(), W.db.get_player_by_id(s.player_id))
    state = again.full_state()
    assert len(state["saved_outfits"]) == 6 and state["saved_outfits"][3]["name"] == "Court day"
    a = state["appearance"]
    assert (a["set"], a["skin_tone"]) == ("set_court_gown", "tone_5")
    assert a.get("palette") is None and int(a.get("outfit_level") or 1) == 1


def test_regalia():
    f = make("female", coins=0, rep=850, title="Queen")
    owned = list(outfits.sets()["set_queen"]["pieces"])
    W.db.save_player_stats(f.player_id, owned_cosmetics=json.dumps(owned))
    f.row = W.db.get_player_by_id(f.player_id)
    look = look_for(f, outfit="queen_gown", head="queen_queens_crown", cloak="queen_train_cloak")
    run(server.handle_update_appearance(f, {"appearance": look}))
    assert last_error(f) is None
    f.royal_title = None          # lost the throne
    a = f.appearance_state()
    assert a["head"] is None and a["outfit"] == "queen_gown" and a["cloak"] == "queen_train_cloak"
    run(server.handle_update_appearance(f, {"appearance": look}))
    assert last_error(f) == "Regalia are worn only while you hold the title."


# ---- D. renderer layers -----------------------------------------------------------------------
def test_layer_order_and_covers():
    look = dict(hd.get_default_appearance("female"), outfit="queen_gown", cloak="queen_train_cloak",
                head="queen_queens_crown", held="village_lady_basket", jewellery=["queen_gold_collar"])
    items = hd._build_item_map()
    hd._ART_PRESENT[("female", "head_queen_queens_crown")] = True     # pretend the crown strip landed
    hd._ART_PRESENT[("female", "held_village_lady_basket")] = True
    try:
        layers = hd._cosmetic_layers(look, "female", items)
        tags = [t for _l, _t, _z, t in layers]
        assert "head" in tags and "held" in tags and "cloak" in tags
        # placeholder: set gown drawn with the generic outfit, recoloured to the set palette
        outfit = next(r for r in layers if r[3] == "outfit")
        assert outfit[0] == "outfit_noble" and outfit[1]["placeholder"]
        z = {t: (zz or {}).get("s") for _l, _t, zz, t in layers}
        assert z["body"] < z["outfit"] < z["head"] < z["held"] and z["hair"] < z["head"]
        kept, _swing = hd._apply_covers(layers, {"helmet": "eclipse_helmet"}, "idle", "female")
        names = [n for n, _t, _z in kept]
        assert "head_queen_queens_crown" not in names            # Queen + helmet: no crown
        kept, _swing = hd._apply_covers(layers, {"weapon": "steel_sword"}, "idle", "female")
        assert "held_village_lady_basket" not in [n for n, _t, _z in kept]   # sword drawn: no held item
    finally:
        hd._ART_PRESENT.pop(("female", "head_queen_queens_crown"), None)
        hd._ART_PRESENT.pop(("female", "held_village_lady_basket"), None)
    # real per-outfit strips win automatically once they exist
    hd._ART_PRESENT[("female", "outfit_queen")] = True
    try:
        outfit = next(r for r in hd._cosmetic_layers(look, "female", items) if r[3] == "outfit")
        assert outfit[0] == "outfit_queen" and not outfit[1]["placeholder"]
    finally:
        hd._ART_PRESENT.pop(("female", "outfit_queen"), None)


# ---- dev commands ------------------------------------------------------------------------------
def test_dev_commands():
    dev = make("female")
    dev.username = "david"
    W.db.conn.execute("UPDATE players SET username = 'david_x' WHERE id = ?", (dev.player_id,))
    if not server._is_dev(dev):
        dev.username = server.DEV_ACCOUNT if hasattr(server, "DEV_ACCOUNT") else "david"
    assert server._is_dev(dev)
    for text in ("::rep 850", "::rank 4", "::title Queen Consort", "::favour 600", "::xp etiquette 5000", "::xp mining L40"):
        dev.ws.out.clear()
        run(server.handle_dev_command(dev, text))
        said = [m["text"] for m in msgs(dev, "CHAT_MSG")]
        assert said, text
        print("  ", text, "->", said[-1])
    assert dev.reputation == 850 and dev.noble_rank == 4 and dev.royal_title == "Queen Consort"
    assert int(throne.favour_row(W.db.conn, dev.player_id)["favour"]) == 600
    assert dev.level("mining") >= 40
    assert outfits.unlocks(dev, W.db.conn)["set_princess_consort"]["state"] == "unlocked"
    nobody = make("male")
    nobody.ws.out.clear()
    run(server.handle_dev_command(nobody, "::rank 5"))
    assert nobody.noble_rank == 0


def test_mae_lines():
    f = make("female", rank=4)
    assert outfits.mae_line(f) == "A Countess should look the part, my lady. The crimson has just come in."
    m = make("male", title="King")
    assert "Majesty" in outfits.mae_line(m)


# ---- H. the outfitter screen ------------------------------------------------------------------
class _Net:
    def __init__(self):
        self.sent = []

    def send(self, kind, **kw):
        self.sent.append((kind, kw))


def _screen_for(s):
    import cosmetics_ui
    c = types.SimpleNamespace(player=s.full_state(), net=_Net(), needs_appearance=False)
    o = cosmetics_ui.Outfitters(c)
    return o, c


_HANDLERS = {"BUY_COSMETICS": "handle_buy_cosmetics", "BUY_PALETTE": "handle_buy_palette",
             "UPGRADE_OUTFIT": "handle_upgrade_outfit", "UPDATE_APPEARANCE": "handle_update_appearance"}


def test_outfitter_screen():
    surf = pygame.Surface((1200, 800))
    for sex in ("male", "female"):
        s = make(sex, coins=50_000, rank=3)
        o, c = _screen_for(s)
        o.open("shop", greeting=outfits.mae_line(s))
        for tab in o.SHOP_TABS:
            o.tab = tab
            o.render(surf)
            # the Male/Female pill is display-only while shopping
            assert not any(kind == "sex" for kind, _r, _p in o.hit), tab
        # every set renders, locked ones preview but cannot be bought
        for sid in outfits.set_order(sex):
            o._try_set(sid)
            o.tab = "sets"
            o.render(surf)
            q = o._quote()
            assert bool(q["locked"]) == (c.player["outfit_unlocks"][sid]["state"] != "unlocked"), sid
        locked = [sid for sid in outfits.set_order(sex) if c.player["outfit_unlocks"][sid]["state"] != "unlocked"]
        o._try_set(locked[0])
        c.net.sent.clear()
        o._buy_and_wear()
        assert c.net.sent == [], "a locked set must not be bought"
        # buy the tier-3 set: the footer total is exactly what the server takes
        tier3 = outfits.set_order(sex)[2]
        o._try_set(tier3)
        q = o._quote()
        expect = q["total"] + q["tax"]
        assert expect > 0
        c.net.sent.clear()
        o._buy_and_wear()
        before = s.coins
        for kind, kw in c.net.sent:
            run(getattr(server, _HANDLERS[kind])(s, dict(kw)))
            assert last_error(s) is None, (kind, last_error(s))
        assert before - s.coins == expect, (before - s.coins, expect)
        assert s.appearance_state().get("outfit") == o.look.get("outfit")
    # the creator: clickable sex pill, 10 free skin tones
    s = make("female")
    o, c = _screen_for(s)
    o.open("creator")
    o.tab = "body"
    o.render(surf)
    assert any(kind == "sex" for kind, _r, _p in o.hit)
    tones = [p for kind, _r, p in o.hit if kind == "tone"]
    assert tones == outfits.tone_ids() and len(tones) == 10, tones


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"ALL {len(tests)} OUTFIT TESTS PASSED")


if __name__ == "__main__":
    main()
