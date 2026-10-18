"""Warden Tamsin's welcome kit, tutorial talk and trail flag. Run: python3 tools/test_welcome_kit.py"""
import asyncio
import json
import os
import sys
import time
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import gear_rules  # noqa: E402
import welcome_kit as wk  # noqa: E402
from content import ITEMS, NPCS, INTERACTABLES, SHOPS, STARTER_INVENTORY  # noqa: E402
import world_map as wm  # noqa: E402

W = server.WORLD
GUIDE = server.NPC_BY_ID[wk.GUIDE_ID]
_N = [0]


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    def last(self, mtype):
        return next((m for m in reversed(self.sent) if m.get("type") == mtype), None)


def _player(near=True):
    _N[0] += 1
    name = f"recruit{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    row = W.db.get_player_by_username(name)
    s = server.PlayerSession(_WS(), row)
    s.inventory = W.db.get_inventory(row["id"])
    s.bank = W.db.get_bank(row["id"])
    s.stats_allocated = True
    if near:
        s.x, s.y = GUIDE["x"] - 1, GUIDE["y"]
    W.sessions[s.player_id] = s
    return s


def _opt(s, opt):
    asyncio.run(server.handle_npc_option(s, {"npc_id": wk.GUIDE_ID, "option": opt}))


def _count(s, item_id):
    n = sum(1 for e in s.inventory.values() if e["item_id"] == item_id)
    n += sum(1 for e in s.bank.values() if e["item_id"] == item_id)
    return n + sum(1 for v in s.equipment.values() if v == item_id)


def _kit_total(s):
    return sum(_count(s, i) for i in wk.KIT_IDS)


def _db_inventory_ids(s):
    return sorted(e["item_id"] for e in W.db.get_inventory(s.player_id).values())


def _fill_bag(s):
    while W.add_item_to_inventory(s, "knife", 1):
        pass


def _fill_bank(s):
    for slot in range(server.BANK_SLOTS):
        s.bank.setdefault(slot, {"item_id": "knife", "qty": 1})


def test_kit_items_bound_and_worthless():
    for item_id, slot in wk.KIT:
        it, base = ITEMS[item_id], ITEMS[wk.KIT_BASE[item_id]]
        assert it["equip_slot"] == slot == base["equip_slot"] and it["art_as"] == wk.KIT_BASE[item_id]
        for k in ("def_bonus", "att_bonus", "str_bonus"):
            assert it.get(k) == base.get(k), (item_id, k)
        assert it["value"] == 1 and not server.item_is_tradeable(item_id) and not server.item_is_sellable(item_id)
        assert server.item_is_bankable(item_id)
        assert not any(server.shop_will_buy(shop, item_id) for shop in SHOPS.values())
    s = _player()
    _opt(s, wk.OPT_TAKE)
    slot = next(k for k, e in s.inventory.items() if e["item_id"] == wk.SWORD)
    asyncio.run(server.handle_drop(s, {"slot_index": slot}))
    assert _count(s, wk.SWORD) == 1 and "can't drop" in s.ws.last("ERROR")["message"]
    # the client draws them with the bronze art
    import player_hd_client as hd
    assert hd._art_id("recruit_bronze_body") == "bronze_body" and hd._tier_rgb("recruit_bronze_body") == hd._tier_rgb("bronze_body")


def test_one_grant_path():
    assert all(item_id != "bronze_sword" for item_id, _q in STARTER_INVENTORY)
    s = _player()
    assert not wk.has_weapon_slot_item(s, ITEMS) or all(
        (ITEMS[e["item_id"]].get("type") == "tool") for e in s.inventory.values()
        if ITEMS[e["item_id"]].get("equip_slot") == "weapon")
    assert not wk.geared(s, ITEMS)


def test_guide_tile_clear_and_reachable():
    gx, gy = GUIDE["x"], GUIDE["y"]
    assert wm.is_walkable(W.grid, gx, gy)
    others = {(n["x"], n["y"]) for n in NPCS if n["id"] != wk.GUIDE_ID and not n.get("plane")}
    assert (gx, gy) not in others and (gx, gy) not in W.resource_nodes
    assert (gx, gy) not in {(i["x"], i["y"]) for i in INTERACTABLES}
    sx, sy = wm.SPAWN_POINT
    assert 5 <= max(abs(gx - sx), abs(gy - sy)) <= 12
    seen, q = {(sx, sy)}, deque([(sx, sy)])
    goals = {(gx + dx, gy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)}
    found = False
    while q and not found:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (x + dx, y + dy)
            if p in seen or not wm.is_walkable(W.grid, *p):
                continue
            if p in goals:
                found = True
                break
            seen.add(p)
            q.append(p)
    assert found


def test_claim_once():
    s = _player()
    _opt(s, wk.OPT_TAKE)
    assert all(_count(s, i) == 1 for i in wk.KIT_IDS)
    assert wk.record(W.db.conn, s.player_id)["claimed_at"] is not None
    assert set(wk.KIT_IDS) <= set(_db_inventory_ids(s))            # committed, not just in memory
    for opt in (wk.OPT_TAKE, wk.OPT_WEAR):
        _opt(s, opt)
    assert _kit_total(s) == 4
    assert not wk.take_claim(W.db.conn, s.player_id)
    W.db.conn.rollback()
    st = wk.status(W.db.conn, s, ITEMS)
    assert st["claimed"] and not st["can_claim"] and not st["show_path"]


def test_double_request_and_second_client():
    s = _player()

    async def spam():
        await asyncio.gather(*[server.handle_npc_option(s, {"npc_id": wk.GUIDE_ID, "option": o})
                               for o in (wk.OPT_WEAR, wk.OPT_TAKE, wk.OPT_WEAR, wk.OPT_TAKE)])
    asyncio.run(spam())
    assert _kit_total(s) == 4
    # a second session object for the same account (another client) can't claim again
    twin = server.PlayerSession(_WS(), W.db.get_player_by_id(s.player_id))
    twin.inventory, twin.bank = W.db.get_inventory(s.player_id), {}
    twin.inventory = {k: v for k, v in twin.inventory.items() if v["item_id"] not in wk.KIT_IDS}
    twin.equipment = {k: None for k in twin.equipment}
    twin.x, twin.y = s.x, s.y
    _opt(twin, wk.OPT_TAKE)
    assert _kit_total(twin) == 0 and twin.ws.last("DIALOGUE") is not None


def test_full_bag_goes_to_bank_then_owed():
    s = _player()
    _fill_bag(s)
    _opt(s, wk.OPT_TAKE)
    assert all(any(e["item_id"] == i for e in s.bank.values()) for i in wk.KIT_IDS)
    assert any("sent your" in line for line in s.ws.last("DIALOGUE")["lines"])
    # bag and bank both full: everything owed, nothing lost, collect later
    s2 = _player()
    _fill_bag(s2)
    _fill_bank(s2)
    _opt(s2, wk.OPT_TAKE)
    assert _kit_total(s2) == 0 and wk.record(W.db.conn, s2.player_id)["owed"] == list(wk.KIT_IDS)
    assert any("keep your" in line for line in s2.ws.last("DIALOGUE")["lines"])
    assert any(o["id"] == wk.OPT_COLLECT for o in s2.ws.last("DIALOGUE")["options"])
    st = wk.public_state(wk.status(W.db.conn, s2, ITEMS), GUIDE)
    assert st["owed"] == 4 and not st["show_path"]
    knives = [k for k, e in s2.inventory.items() if e["item_id"] == "knife"][:2]
    for k in knives:
        del s2.inventory[k]
        W.db.clear_slot(s2.player_id, k)
    _opt(s2, wk.OPT_COLLECT)
    assert _kit_total(s2) == 2 and len(wk.record(W.db.conn, s2.player_id)["owed"]) == 2
    _opt(s2, wk.OPT_TAKE)                                            # still can't re-claim
    assert _kit_total(s2) == 2


def test_grant_is_atomic():
    s = _player()
    _fill_bag(s)
    before_mem = json.dumps(s.inventory, sort_keys=True, default=str)
    before_db = _db_inventory_ids(s)
    real = server._bank_put
    calls = [0]

    def flaky(session, item_id, qty=1):
        calls[0] += 1
        if calls[0] == 3:
            raise RuntimeError("server died mid-grant")
        return real(session, item_id, qty)
    server._bank_put = flaky
    try:
        _opt(s, wk.OPT_TAKE)
        raise AssertionError("expected the crash")
    except RuntimeError:
        pass
    finally:
        server._bank_put = real
    assert wk.record(W.db.conn, s.player_id)["claimed_at"] is None            # no claim recorded
    assert _db_inventory_ids(s) == before_db and not W.db.get_bank(s.player_id)
    assert json.dumps(s.inventory, sort_keys=True, default=str) == before_mem and not s.bank
    _opt(s, wk.OPT_TAKE)                                                     # and they can still claim
    assert _kit_total(s) == 4


def test_veteran_eligibility():
    vet = _player()
    vet.equipment["weapon"], vet.equipment["helmet"] = "iron_sword", "bronze_helmet"
    st = wk.status(W.db.conn, vet, ITEMS)
    assert st["veteran"] and not st["can_claim"] and not st["show_path"]
    _opt(vet, wk.OPT_TAKE)
    assert _kit_total(vet) == 0
    assert not any(o["id"] in (wk.OPT_TAKE, wk.OPT_WEAR) for o in wk.options(st))
    # a veteran whose armour is in the bank still counts as geared
    vet2 = _player()
    vet2.equipment["weapon"] = "bronze_battleaxe"
    vet2.bank[0] = {"item_id": "iron_legs", "qty": 1}
    assert wk.geared(vet2, ITEMS)
    # sword but no armour, or armour but no weapon: may claim once
    a = _player()
    a.inventory[50] = {"item_id": "bronze_sword", "qty": 1}
    b = _player()
    b.equipment["body"] = "leather_body"
    assert wk.status(W.db.conn, a, ITEMS)["can_claim"] and wk.status(W.db.conn, b, ITEMS)["can_claim"]


def test_softlock_replacement_sword():
    s = _player()
    _opt(s, wk.OPT_WEAR)
    assert s.equipment["weapon"] == wk.SWORD
    # loses every weapon-slot item (e.g. a dungeon death)
    s.equipment["weapon"] = None
    s.inventory = {k: e for k, e in s.inventory.items() if ITEMS[e["item_id"]].get("equip_slot") != "weapon"}
    st = wk.status(W.db.conn, s, ITEMS)
    assert st["sword_offer"] and st["sword_wait"] == 0 and not st["can_claim"]
    assert any("Gareth" in line for line in wk.greeting(st, "X"))
    _opt(s, wk.OPT_SWORD)
    assert _count(s, wk.SWORD) == 1
    _opt(s, wk.OPT_SWORD)                                     # has a weapon again: not offered
    assert _count(s, wk.SWORD) == 1
    s.inventory = {k: e for k, e in s.inventory.items() if e["item_id"] != wk.SWORD}
    st = wk.status(W.db.conn, s, ITEMS)
    opt = next(o for o in wk.options(st) if o["id"] == wk.OPT_SWORD)
    assert opt.get("ok") is False and "min" in opt["why"]
    _opt(s, wk.OPT_SWORD)
    assert _count(s, wk.SWORD) == 0                            # cooldown holds on the server
    W.db.conn.execute("UPDATE welcome_kit SET sword_at = ? WHERE player_id = ?",
                      (time.time() - wk.SWORD_COOLDOWN_S - 1, s.player_id))
    W.db.conn.commit()
    _opt(s, wk.OPT_SWORD)
    assert _count(s, wk.SWORD) == 1
    # an axe is enough to fight with, so no free sword
    t = _player()
    _opt(t, wk.OPT_TAKE)
    t.inventory = {k: e for k, e in t.inventory.items() if e["item_id"] != wk.SWORD}
    assert wk.has_weapon_slot_item(t, ITEMS) and not wk.status(W.db.conn, t, ITEMS)["sword_offer"]


def test_equip_for_me_takes_outfit_off():
    s = _player()
    look = {"skin": "skin_base", "hair": "hair_side_part", "top": "top_linen_shirt",
            "bottom": "bottom_work_trousers", "outfit": "set_kings_champion"}
    W.db.save_player_stats(s.player_id, appearance=json.dumps(look))
    s.row = W.db.get_player_by_id(s.player_id)
    assert gear_rules.wearing_outfit(gear_rules.saved_look(s)) and not gear_rules.can_fight(s)
    _opt(s, wk.OPT_WEAR)
    assert [s.equipment[slot] for _i, slot in wk.KIT] == list(wk.KIT_IDS)
    assert not gear_rules.wearing_outfit(gear_rules.saved_look(s))
    assert gear_rules.can_fight(s) and gear_rules.gate_missing(s) == []
    # take-only, then Equip it for me later
    t = _player()
    _opt(t, wk.OPT_TAKE)
    assert any(o["id"] == wk.OPT_EQUIP for o in t.ws.last("DIALOGUE")["options"])
    _opt(t, wk.OPT_EQUIP)
    assert gear_rules.gate_missing(t) == []
    _opt(t, wk.OPT_EQUIP)                                       # spam: nothing more to do
    assert _kit_total(t) == 4


def test_path_visibility_flag():
    s = _player()
    asyncio.run(server.welcome_on_join(s))
    st = s.ws.last("WELCOME_STATE")
    assert st["show_path"] and st["guide"] == {"id": wk.GUIDE_ID, "name": wk.GUIDE_NAME,
                                               "x": GUIDE["x"], "y": GUIDE["y"]}
    assert s.ws.last("CHAT_MSG")["from"] == wk.GUIDE_NAME
    asyncio.run(server.welcome_skip(s))
    assert not s.ws.last("WELCOME_STATE")["show_path"]
    assert wk.status(W.db.conn, s, ITEMS)["can_claim"]           # skipping keeps the kit claimable
    t = _player()
    _opt(t, wk.OPT_TAKE)
    assert not t.ws.last("WELCOME_STATE")["show_path"]
    # client side: only in the overworld, only while the server says so
    import types
    import new_player_guide as g
    c = types.SimpleNamespace(state="GAME", player={"x": 28, "y": 24}, dungeon=None, welcome=None)
    g.on_state(c, {"show_path": True, "guide": {"x": GUIDE["x"], "y": GUIDE["y"]}})
    assert g.visible(c)
    c.dungeon = {"id": "tidehollow"}
    assert not g.visible(c)
    c.dungeon = None
    g.on_state(c, {"show_path": False, "guide": {"x": GUIDE["x"], "y": GUIDE["y"]}})
    assert not g.visible(c)


def test_dialogue_flow():
    s = _player()
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))
    d = s.ws.last("DIALOGUE")
    assert d["npc_name"] == wk.GUIDE_NAME and d["lines"] == d["pages"][0] and len(d["pages"]) == 1 + len(wk.TOUR)
    ids = [o["id"] for o in d["options"]]
    assert ids[:2] == [wk.OPT_WEAR, wk.OPT_TAKE] and wk.OPT_REMIND in ids and wk.OPT_SKIP in ids
    text = " ".join(" ".join(p) for p in d["pages"]).lower()
    for word in ("walk", "zoom", "weapon", "outfit", "run", "chest plate", "leg armour", "helmet", "skills",
                 "bank", "reputation", "throne", "miriam"):
        assert word in text, word
    _opt(s, wk.OPT_WEAR)
    d = s.ws.last("DIALOGUE")
    assert d["pages"] is None and "Recruit's Bronze kit" in d["lines"][0]
    ids = [o["id"] for o in d["options"]]
    assert wk.OPT_WEAR not in ids and wk.OPT_SKIP not in ids and wk.OPT_REMIND in ids
    _opt(s, wk.OPT_REMIND)
    assert len(s.ws.last("DIALOGUE")["pages"]) == 1 + len(wk.TOUR)
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))
    assert s.ws.last("DIALOGUE")["pages"] is None                  # later visits are short
    far = _player(near=False)
    far.x, far.y = GUIDE["x"] + 6, GUIDE["y"]
    _opt(far, wk.OPT_TAKE)
    assert _kit_total(far) == 0 and "too far" in far.ws.last("ERROR")["message"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} WELCOME KIT TESTS PASSED")
