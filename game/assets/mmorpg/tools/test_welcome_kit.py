"""Warden Tamsin's welcome talk and trail (kit retired 30 Oct 2026: only Seraphine gives bronze). Run: python3 tools/test_welcome_kit.py"""
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
    W.add_item_to_inventory(s, wk.SWORD, 1)          # old claimants still hold these
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


BRONZE = ("bronze_helmet", "bronze_body", "bronze_legs", "bronze_sword", "bronze_shield")


def _bronze_counts(s):
    return {i: _count(s, i) for i in BRONZE + wk.KIT_IDS}


def _tour(s, **msg):
    asyncio.run(server.handle_guide_tour(s, {"type": "GUIDE_TOUR", **msg}))


def test_tamsin_offers_no_kit():
    s = _player()
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))
    d = s.ws.last("DIALOGUE")
    ids = [o["id"] for o in d["options"]]
    assert wk.OPT_WEAR not in ids and wk.OPT_TAKE not in ids and wk.OPT_REMIND in ids
    text = " ".join(" ".join(p) for p in d["pages"]).lower()
    assert "kit" not in text and "seraphine" in text
    for word in ("walk", "click the ground", "zoom", "mouse wheel", "travel", "press m", "axe", "pickaxe"):
        assert word in text, word
    for word in ("reputation", "throne", "tribute"):
        assert word not in text, word
    for opt in (wk.OPT_WEAR, wk.OPT_TAKE, wk.OPT_COLLECT, wk.OPT_EQUIP, wk.OPT_SWORD):
        _opt(s, opt)                                     # forged / stale requests: server refuses
    assert _kit_total(s) == 0 and all(v == 0 for v in _bronze_counts(s).values()), _bronze_counts(s)
    # the first talk completes the welcome: trail moves on to Sarah -> Miriam
    st = s.ws.last("WELCOME_STATE")
    assert st["claimed"] and st["show_path"], st
    assert not wk.status(W.db.conn, s, ITEMS)["first_visit"]
    # Remind still works, and the second talk is a single page
    _opt(s, wk.OPT_REMIND)
    remind = " ".join(" ".join(p) for p in s.ws.last("DIALOGUE")["pages"]).lower()
    for word in ("walk", "zoom", "travel", "bank", "miriam", "crypt"):
        assert word in remind, word
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))
    assert s.ws.last("DIALOGUE").get("pages") in (None, []) or len(s.ws.last("DIALOGUE")["pages"]) == 1


def test_banner_and_chat_promise_no_kit():
    s = _player()
    asyncio.run(server.welcome_on_join(s))
    assert "kit" not in ((s.ws.last("CHAT_MSG") or {}).get("text") or "").lower()   # Tamsin greeting removed 30 Oct
    st = s.ws.last("WELCOME_STATE")
    assert st["show_path"] and st["guide"] == {"id": wk.GUIDE_ID, "name": wk.GUIDE_NAME,
                                               "x": GUIDE["x"], "y": GUIDE["y"]}
    asyncio.run(server.welcome_skip(s))
    assert not s.ws.last("WELCOME_STATE")["show_path"]
    import types
    import new_player_guide as g
    assert all("kit" not in line.lower() for line in g.__dict__.get("TRAIL_HINTS", ()) if isinstance(line, str))
    src = open(g.__file__).read()
    assert "for your Bronze kit" not in src
    c = types.SimpleNamespace(state="GAME", player={"x": 28, "y": 24}, dungeon=None, welcome=None, quests={},
                              npcs=[{"id": "innkeeper_sarah", "x": 20, "y": 40}])   # Tamsin stage removed: trail starts at Sarah
    g.on_state(c, {"show_path": True, "guide": {"x": GUIDE["x"], "y": GUIDE["y"]}})
    assert g.visible(c)
    c.dungeon = {"id": "tidehollow"}
    assert not g.visible(c)
    lines = [n for n in NPCS if n["id"] == wk.GUIDE_ID][0].get("lines") or []
    assert all("kit" not in l.lower() for l in lines), lines


def test_well_never_gives_bronze_sword():
    assert "bronze_sword" not in server.WISH_GEAR_POOL and "bronze_sword" not in server.WISH_GEAR_BETTER
    assert "bronze_sword" not in getattr(server, "WISH_MYTHOS_POOL", [])


def test_new_account_gets_exactly_one_bronze_set():
    s = _player()
    s.guide_tour, s.guide_bronze = 0, False
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))          # Tamsin: no kit
    _opt(s, wk.OPT_WEAR)
    _opt(s, wk.OPT_SWORD)                                                # no spare sword before the gift
    assert all(v == 0 for v in _bronze_counts(s).values()), _bronze_counts(s)
    _tour(s, action="start")
    for step in range(1, 5):
        _tour(s, action="advance", step=step)
    assert s.guide_bronze
    counts = _bronze_counts(s)
    assert all(counts[i] == 1 for i in BRONZE) and _kit_total(s) == 0, counts
    # replay + skip + forged messages never add a second set
    _tour(s, action="skip")
    _tour(s, action="replay")
    for step in range(1, 6):
        _tour(s, action="advance", step=step)
    _opt(s, wk.OPT_WEAR)
    _opt(s, wk.OPT_TAKE)
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))
    assert _bronze_counts(s) == counts, (_bronze_counts(s), counts)


def test_softlock_replacement_sword_after_gift():
    s = _player()
    s.guide_bronze = True
    asyncio.run(server.handle_talk(s, {"npc_id": wk.GUIDE_ID}))          # welcome done
    s.equipment["weapon"] = None
    s.inventory = {k: e for k, e in s.inventory.items() if ITEMS[e["item_id"]].get("equip_slot") != "weapon"}
    st = wk.status(W.db.conn, s, ITEMS)
    assert st["sword_offer"] and st["sword_wait"] == 0
    _opt(s, wk.OPT_SWORD)
    assert _count(s, wk.SWORD) == 1
    _opt(s, wk.OPT_SWORD)
    assert _count(s, wk.SWORD) == 1                                      # has a weapon again



def test_next_step_panel_promises_no_kit():
    import types
    import hud_v2
    c = types.SimpleNamespace(welcome={"show_path": True, "claimed": False}, player={"equipment": {}, "inventory": {}})
    step = hud_v2._no_quest_step(c)
    assert step["npc"] != "warden_tamsin"   # Tamsin step removed 30 Oct
    assert all("kit" not in str(step.get(k, "")).lower() for k in ("title", "detail", "hint")), step

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} WELCOME KIT TESTS PASSED")
