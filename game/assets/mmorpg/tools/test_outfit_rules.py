"""Outfit / armour / dungeon / fighting rules (David, 17 Oct 2026). Run: python3 tools/test_outfit_rules.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import outfits  # noqa: E402
import gear_rules  # noqa: E402
INTERACTABLES, DUNGEON_META = server.INTERACTABLES, server.DUNGEON_META

W = server.WORLD
_N = [0]
KIT = {"helmet": "bone_crown", "body": "mythos_body", "legs": "mythos_legs",
       "weapon": "bronze_sword", "shield": "mythos_shield"}


class WS:
    def __init__(self):
        self.out = []

    async def send(self, raw):
        self.out.append(json.loads(raw))


def run(coro):
    return asyncio.run(coro)


def make(sex="female", rep=850, title="Queen"):
    _N[0] += 1
    user = f"gr{_N[0]}"
    W.db.create_account(user, "pw", f"Gear{_N[0]}")
    row = W.db.get_player_by_username(user)
    W.db.save_player_stats(row["id"], gender=sex, stats_allocated=1)
    W.db.conn.execute("UPDATE players SET reputation = ?, royal_title = ? WHERE id = ?", (rep, title, row["id"]))
    W.db.conn.commit()
    s = server.PlayerSession(WS(), W.db.get_player_by_username(user))
    for slot in list(s.equipment):
        s.equipment[slot] = None
    s.inventory.clear()
    return s


def errors(s):
    return [m["message"] for m in s.ws.out if m.get("type") == "ERROR"]


def chats(s):
    return [m.get("text") for m in s.ws.out if m.get("type") == "CHAT_MSG"]


def wear_kit(s, slots=KIT):
    for slot, item in slots.items():
        s.equipment[slot] = item
        W.db.set_equipment(s.player_id, slot, item)


def own_queen(s):
    W.db.save_player_stats(s.player_id, owned_cosmetics=json.dumps(list(outfits.sets()["set_queen"]["pieces"])))
    s.row = W.db.get_player_by_id(s.player_id)


def queen_look(s):
    look = dict(s.appearance_state())
    look.update(outfit="queen_gown", cloak="queen_train_cloak", head="queen_queens_crown")
    return look


def stand_at_dungeon(s):
    kinds = {k for m in DUNGEON_META.values() for k in m["entrance_kinds"]}
    for spot in INTERACTABLES:
        if spot.get("kind") in kinds and spot.get("dungeon_id") != "castle_realm":
            s.x, s.y = spot["x"], spot["y"]
            return spot
    raise AssertionError("no dungeon entrance in INTERACTABLES")


# ---- 1. dungeon gate ---------------------------------------------------------------------------
def test_gate_needs_four_slots():
    s = make()
    stand_at_dungeon(s)
    run(server.handle_enter_dungeon(s, {}))
    assert not s.dungeon
    msg = errors(s)[-1]
    assert msg.startswith("The dungeon gate stays shut.") and "chest plate" in msg and "a weapon" in msg, msg
    wear_kit(s, {"body": KIT["body"], "legs": KIT["legs"], "helmet": KIT["helmet"]})
    run(server.handle_enter_dungeon(s, {}))
    assert not s.dungeon and errors(s)[-1].endswith("Missing: a weapon."), errors(s)[-1]


def test_gate_opens_with_full_kit():
    s = make()
    stand_at_dungeon(s)
    wear_kit(s)
    try:
        run(server.handle_enter_dungeon(s, {}))
    except Exception:
        pass      # entering needs a live world; only the gate is under test
    assert not any(e.startswith("The dungeon gate") for e in errors(s)), errors(s)


# ---- 2. no unequipping in a dungeon ------------------------------------------------------------
def test_dungeon_unequip_lock():
    s = make()
    wear_kit(s)
    s.dungeon = {"id": "tidehollow"}
    for slot in ("body", "legs", "helmet", "weapon"):
        run(server.handle_unequip(s, {"equip_slot": slot}))
        assert s.equipment[slot] == KIT[slot], slot
        assert errors(s)[-1] == gear_rules.unequip_locked_message(slot)
    run(server.handle_unequip(s, {"equip_slot": "shield"}))   # not one of the gate slots
    assert s.equipment["shield"] is None
    s.dungeon = None
    run(server.handle_unequip(s, {"equip_slot": "helmet"}))
    assert s.equipment["helmet"] is None
    t = make()
    wear_kit(t)
    t.dungeon = {"id": "castle_realm"}                        # the Castle Realm isn't a dungeon
    run(server.handle_unequip(t, {"equip_slot": "body"}))
    assert t.equipment["body"] is None


# ---- 3. who can fight ---------------------------------------------------------------------------
def test_no_weapon_cannot_attack():
    s = make()
    s.in_combat_with = ("monster", 1)
    run(server.handle_attack(s, {"target_id": 1}))
    assert errors(s)[-1] == "You can't fight dressed like this, run!"
    assert s.in_combat_with is None and not gear_rules.can_fight(s)


def test_outfit_cannot_attack():
    s = make()
    own_queen(s)
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)
    s.equipment["weapon"] = "bronze_sword"     # even forced back in, an outfit never fights
    run(server.handle_attack(s, {"target_id": 1}))
    assert errors(s)[-1] == gear_rules.NO_FIGHT_MSG and not gear_rules.can_fight(s)


def test_armed_can_attack():
    s = make()
    wear_kit(s, {"weapon": "bronze_sword"})
    assert gear_rules.can_fight(s)
    run(server.handle_attack(s, {"target_id": -999}))
    assert gear_rules.NO_FIGHT_MSG not in errors(s)


# ---- 4. an outfit is one whole piece -----------------------------------------------------------
def test_equipping_armour_takes_outfit_off():
    for sex, bottom in (("female", "bottom_long_skirt"), ("male", "bottom_work_trousers")):
        s = make(sex, title="Queen" if sex == "female" else "King")
        if sex == "female":
            own_queen(s)
            look = queen_look(s)
        else:
            W.db.save_player_stats(s.player_id, owned_cosmetics=json.dumps(list(outfits.sets()["set_king"]["pieces"])))
            s.row = W.db.get_player_by_id(s.player_id)
            look = dict(s.appearance_state(), outfit="king_coat")
        run(server.handle_update_appearance(s, {"appearance": look}))
        assert s.appearance_state()["outfit"], errors(s)
        W.add_item_to_inventory(s, "mythos_body", 1)
        idx = next(i for i, e in s.inventory.items() if e["item_id"] == "mythos_body")
        run(server.handle_equip(s, {"slot_index": idx}))
        a = s.appearance_state()
        assert s.equipment["body"] == "mythos_body"
        assert a["outfit"] is None and a["cloak"] is None and a["head"] is None, a
        assert a["top"] == "top_linen_shirt" and a["bottom"] == bottom, a
        assert gear_rules.OUTFIT_OFF_MSG in chats(s)


def test_wearing_outfit_takes_armour_off_to_bag():
    s = make()
    own_queen(s)
    wear_kit(s)
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)
    assert all(s.equipment[k] is None for k in KIT)
    bag = sorted(e["item_id"] for e in s.inventory.values())
    assert bag == sorted(KIT.values()), bag
    assert W.db.get_equipment(s.player_id).get("body") in (None, "") if hasattr(W.db, "get_equipment") else True


def test_full_bag_goes_to_bank_never_lost():
    s = make()
    own_queen(s)
    wear_kit(s)
    filler = "bronze_sword"
    while W.add_item_to_inventory(s, filler, 1):
        pass
    bag_before = len(s.inventory)
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)
    assert len(s.inventory) == bag_before
    banked = sorted(e["item_id"] for e in s.bank.values())
    assert banked == sorted(KIT.values()), banked
    assert all(s.equipment[k] is None for k in KIT)


def test_bag_and_bank_full_refuses_outfit():
    s = make()
    own_queen(s)
    wear_kit(s, {"body": "mythos_body"})
    while W.add_item_to_inventory(s, "bronze_sword", 1):
        pass
    for b in range(server.BANK_SLOTS):
        s.bank[b] = {"item_id": "bronze_sword", "qty": 1}
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.equipment["body"] == "mythos_body"
    assert not s.appearance_state().get("outfit")
    assert "both full" in errors(s)[-1]


def test_no_outfit_change_in_dungeon():
    s = make()
    own_queen(s)
    wear_kit(s)
    s.dungeon = {"id": "tidehollow"}
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert errors(s)[-1] == "You can't change into an outfit inside a dungeon."
    assert s.equipment["body"] == KIT["body"] and not s.appearance_state().get("outfit")


def test_base_look_helper():
    look = {"outfit": "queen_gown", "cloak": "queen_train_cloak", "head": "queen_queens_crown", "held": None,
            "jewellery": ["queen_pearl_choker"], "palette": "x", "outfit_level": 3, "hair": "h", "top": None,
            "bottom": None, "shoes": "shoes_leather"}
    out = gear_rules.base_look(look, "female", outfits.items())
    assert out["outfit"] is None and out["cloak"] is None and out["head"] is None and out["palette"] is None
    assert out["top"] == "top_linen_shirt" and out["bottom"] == "bottom_long_skirt"
    assert out["hair"] == "h" and out["shoes"] == "shoes_leather" and out["outfit_level"] == 1
    for k in ("top_linen_shirt", "bottom_long_skirt", "bottom_work_trousers"):
        assert k in outfits.items(), k


def test_tick_no_swing_no_retaliate():
    s = make()
    m = next(m for m in W.monsters.values() if m.alive and not (m.def_stats() or {}).get("requires_pk"))
    s.x, s.y = m.x + 1, m.y
    s.dungeon = None
    s.in_combat_with = ("monster", m.id)
    s.next_swing_at = 0
    hp0 = m.hp
    W.sessions[s.player_id] = s
    try:
        run(server.process_combat([]))
    finally:
        W.sessions.pop(s.player_id, None)
    assert m.hp == hp0, (m.hp, hp0)
    assert s.in_combat_with is None


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok  ", name)
        except Exception as exc:
            failed += 1
            import traceback
            traceback.print_exc()
            print("FAIL", name, exc)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
