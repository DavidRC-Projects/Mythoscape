"""Economy integrity / anti-dupe checks.

Run:  python3 tools/test_economy_integrity.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
from content import ITEMS, INTERACTABLES, NPCS, QUESTS, INVENTORY_SIZE  # noqa: E402

W = server.WORLD
_N = [0]

BANK_XY = next((s["x"], s["y"]) for s in INTERACTABLES if s.get("kind") == "bank")
SHOP_NPC = next(n for n in NPCS if n.get("shop_id") == "general_store")
JEWELER = next(n for n in NPCS if n.get("quest_id") == "liras_lost_locket" or "liras_lost_locket" in (n.get("quest_ids") or []))


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    def last(self, mtype):
        return next((m for m in reversed(self.sent) if m.get("type") == mtype), None)

    def clear(self):
        self.sent.clear()


def run(coro):
    return asyncio.run(coro)


def _player(x=None, y=None):
    _N[0] += 1
    name = f"econ{_N[0]}"
    W.db.create_account(name, "password12", name.title())
    row = W.db.get_player_by_username(name)
    s = server.PlayerSession(_WS(), row)
    s.inventory = W.db.get_inventory(row["id"])
    s.bank = W.db.get_bank(row["id"])
    s.quests = W.db.get_quest_progress(row["id"])
    s.stats_allocated = True
    if x is not None:
        s.x, s.y = x, y
    W.sessions[s.player_id] = s
    return s


def _count(s, item_id):
    n = sum(int(e["qty"]) for e in s.inventory.values() if e["item_id"] == item_id)
    n += sum(int(e["qty"]) for e in s.bank.values() if e["item_id"] == item_id)
    n += sum(1 for v in (s.equipment or {}).values() if v == item_id)
    return n


def _fill_inventory(s, filler="knife"):
    """Occupy every inventory slot (tab-aware add can leave other tabs open)."""
    for slot in range(INVENTORY_SIZE):
        if slot not in s.inventory:
            s.inventory[slot] = {"item_id": filler, "qty": 1}
            W.db.add_item_to_slot(s.player_id, slot, filler, 1)


def _inv_snapshot(s):
    return sorted((slot, e["item_id"], e["qty"]) for slot, e in s.inventory.items())


def test_collect_quest_turnin_once():
    s = _player(JEWELER["x"] - 1, JEWELER["y"])
    qid = "liras_lost_locket"
    assert QUESTS[qid]["type"] == "collect"
    run(server.handle_quest_accept(s, {"quest_id": qid}))
    assert s.quests[qid]["status"] == "active"
    assert W.add_item_to_inventory(s, "lost_locket", 1)
    coins_before = s.coins
    run(server.handle_quest_turnin(s, {"quest_id": qid}))
    assert s.quests[qid]["status"] == "complete"
    assert _count(s, "lost_locket") == 0
    coins_after = s.coins
    # Second turn-in with a fresh locket must not re-reward
    assert W.add_item_to_inventory(s, "lost_locket", 1)
    s.ws.clear()
    run(server.handle_quest_turnin(s, {"quest_id": qid}))
    err = s.ws.last("ERROR")
    assert err and "already completed" in err["message"].lower()
    assert s.coins == coins_after
    assert _count(s, "lost_locket") == 1  # not consumed on rejected turn-in


def test_trade_rejects_untradeable():
    a = _player()
    b = _player(a.x + 1, a.y)
    assert W.add_item_to_inventory(a, "lost_locket", 1)  # quest item, not tradeable after flags
    # Prefer a known untradeable unique if locket is tradeable somehow
    kit_id = next((iid for iid, it in ITEMS.items() if it.get("unique") and not server.item_is_tradeable(iid)), None)
    if kit_id:
        # clear and use kit
        a.inventory.clear()
        W.db.conn.execute("DELETE FROM inventory WHERE player_id = ?", (a.player_id,))
        W.db.conn.commit()
        assert W.add_item_to_inventory(a, kit_id, 1)
        item_id = kit_id
    else:
        item_id = "lost_locket"
        assert not server.item_is_tradeable(item_id)
    slot = next(k for k, e in a.inventory.items() if e["item_id"] == item_id)
    a.trade_partner_id = b.player_id
    b.trade_partner_id = a.player_id
    run(server.handle_trade_offer(a, {"items": [{"slot_index": slot, "qty": 1}]}))
    assert slot not in a.trade_offer or a.trade_offer.get(slot) is None or item_id not in [
        a.inventory.get(sl, {}).get("item_id") for sl in a.trade_offer
    ]
    # Offer should be empty (untradeable skipped)
    assert a.trade_offer == {}
    assert _count(a, item_id) == 1


def test_trade_room_check_no_item_loss():
    a = _player()
    b = _player(a.x + 1, a.y)
    assert W.add_item_to_inventory(a, "copper_ore", 5)
    slot = next(k for k, e in a.inventory.items() if e["item_id"] == "copper_ore")
    _fill_inventory(b, "knife")
    snap_a, snap_b = _inv_snapshot(a), _inv_snapshot(b)
    a.trade_partner_id = b.player_id
    b.trade_partner_id = a.player_id
    a.trade_offer = {slot: 5}
    b.trade_offer = {}
    a.trade_confirmed = b.trade_confirmed = True
    run(server.execute_trade(a, b))
    assert _inv_snapshot(a) == snap_a
    assert _inv_snapshot(b) == snap_b
    assert _count(a, "copper_ore") == 5


def test_bank_unique_and_dungeon_bound_blocked():
    s = _player(BANK_XY[0] - 1, BANK_XY[1])
    assert W.add_item_to_inventory(s, "mining_bag", 1)
    bag_slot = next(k for k, e in s.inventory.items() if e["item_id"] == "mining_bag")
    run(server.handle_bank_deposit(s, {"slot_index": bag_slot}))
    assert _count(s, "mining_bag") == 1
    assert not any(e["item_id"] == "mining_bag" for e in s.bank.values())
    key_id = next(iid for iid, it in ITEMS.items() if it.get("dungeon_bound"))
    assert W.add_item_to_inventory(s, key_id, 1)
    key_slot = next(k for k, e in s.inventory.items() if e["item_id"] == key_id)
    s.ws.clear()
    run(server.handle_bank_deposit(s, {"slot_index": key_slot}))
    assert _count(s, key_id) == 1
    assert not any(e["item_id"] == key_id for e in s.bank.values())


def test_bank_withdraw_full_inv_no_debit():
    s = _player(BANK_XY[0] - 1, BANK_XY[1])
    s.bank[0] = {"item_id": "copper_ore", "qty": 10}
    W.db.set_bank_slot(s.player_id, 0, "copper_ore", 10)
    _fill_inventory(s, "knife")
    run(server.handle_bank_withdraw(s, {"slot_index": 0, "qty": 5}))
    assert s.bank[0]["qty"] == 10
    inv_ore = sum(int(e["qty"]) for e in s.inventory.values() if e["item_id"] == "copper_ore")
    assert inv_ore == 0
    err = s.ws.last("ERROR")
    assert err and "full" in err["message"].lower()


def test_bag_pack_unpack_conserves_total():
    s = _player()
    assert W.add_item_to_inventory(s, "mining_bag", 1)
    assert W.add_item_to_inventory(s, "copper_ore", 7) or W.add_item_to_inventory(s, "tin_ore", 7)
    ore_id = "copper_ore" if _count(s, "copper_ore") else "tin_ore"
    if _count(s, ore_id) < 7:
        # ensure 7
        while _count(s, ore_id) < 7:
            if not W.add_item_to_inventory(s, ore_id, 1):
                break
    total = _count(s, ore_id) + int(s.mining_bag.get(ore_id) or 0)
    moved = s.deposit_mining_bag(ore_id, total)
    assert moved > 0
    in_bag = int(s.mining_bag.get(ore_id) or 0)
    in_inv = sum(int(e["qty"]) for e in s.inventory.values() if e["item_id"] == ore_id)
    assert in_bag + in_inv == total
    s._withdraw_bag_to_inventory(s.mining_bag, "mining_bag_contents")
    in_bag2 = int(s.mining_bag.get(ore_id) or 0)
    in_inv2 = sum(int(e["qty"]) for e in s.inventory.values() if e["item_id"] == ore_id)
    assert in_bag2 + in_inv2 == total


def test_shop_requires_proximity():
    s = _player(0, 0)  # far from general store
    s.coins = 10_000
    s.ws.clear()
    run(server.handle_shop_buy(s, {"shop_id": "general_store", "item_id": "tinderbox", "qty": 1}))
    err = s.ws.last("ERROR")
    assert err and "shop" in err["message"].lower()
    # Near shop works (tinderbox may already be owned — just no proximity error)
    s.x, s.y = SHOP_NPC["x"] - 1, SHOP_NPC["y"]
    s.ws.clear()
    run(server.handle_shop_buy(s, {"shop_id": "general_store", "item_id": "tinderbox", "qty": 1}))
    err2 = s.ws.last("ERROR")
    assert not err2 or "shop" not in (err2.get("message") or "").lower() or "afford" in (err2.get("message") or "").lower() or "own" in (err2.get("message") or "").lower() or "full" in (err2.get("message") or "").lower() or "stock" in (err2.get("message") or "").lower() or "sell" in (err2.get("message") or "").lower()


def test_mid_trade_blocks_drop_and_bank():
    a = _player(BANK_XY[0] - 1, BANK_XY[1])
    b = _player(a.x + 1, a.y)
    assert W.add_item_to_inventory(a, "copper_ore", 3)
    slot = next(k for k, e in a.inventory.items() if e["item_id"] == "copper_ore")
    a.trade_partner_id = b.player_id
    b.trade_partner_id = a.player_id
    before = _count(a, "copper_ore")
    run(server.handle_drop(a, {"slot_index": slot, "qty": 1}))
    assert _count(a, "copper_ore") == before
    run(server.handle_bank_deposit(a, {"slot_index": slot}))
    assert _count(a, "copper_ore") == before
    assert not any(e["item_id"] == "copper_ore" for e in a.bank.values())


def main():
    tests = [
        test_collect_quest_turnin_once,
        test_trade_rejects_untradeable,
        test_trade_room_check_no_item_loss,
        test_bank_unique_and_dungeon_bound_blocked,
        test_bank_withdraw_full_inv_no_debit,
        test_bag_pack_unpack_conserves_total,
        test_shop_requires_proximity,
        test_mid_trade_blocks_drop_and_bank,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
