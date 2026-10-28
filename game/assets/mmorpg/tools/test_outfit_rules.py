"""Outfit / armour / dungeon / fighting rules (David, 17 Oct 2026; weapon-only rules 23 Oct 2026). Run: python3 tools/test_outfit_rules.py"""
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
ARMOUR = ("helmet", "body", "legs", "shield")


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


# ---- 1. dungeon gate: a sword or axe, nothing else (23 Oct 2026) ------------------------------------
def test_gate_needs_sword_or_axe():
    s = make()
    stand_at_dungeon(s)
    run(server.handle_enter_dungeon(s, {}))
    assert not s.dungeon and errors(s)[-1] == gear_rules.GATE_MSG, errors(s)
    # full armour but no weapon, a bow, or a gathering tool: still shut
    wear_kit(s, {"body": KIT["body"], "legs": KIT["legs"], "helmet": KIT["helmet"], "shield": KIT["shield"]})
    for weapon, tool in ((None, None), ("shortbow", None), (None, "bronze_axe"), (None, "bronze_pickaxe")):
        s.equipment["weapon"], s.equipment["tool"] = weapon, tool
        s.ws.out.clear()
        run(server.handle_enter_dungeon(s, {}))
        assert not s.dungeon and errors(s)[-1] == gear_rules.GATE_MSG, (weapon, tool, errors(s))


def test_gate_opens_with_weapon_only():
    for weapon in ("bronze_sword", "steel_longsword", "iron_battleaxe", "recruit_bronze_sword"):
        s = make()
        stand_at_dungeon(s)
        wear_kit(s, {"weapon": weapon})            # no armour at all
        try:
            run(server.handle_enter_dungeon(s, {}))
        except Exception:
            pass      # entering needs a live world; only the gate is under test
        assert not any(e.startswith("The dungeon gate") for e in errors(s)), (weapon, errors(s))


# ---- 2. nothing is locked on inside a dungeon ----------------------------------------------------------
def test_dungeon_no_unequip_lock():
    s = make()
    wear_kit(s)
    s.dungeon = {"id": "tidehollow"}
    for slot in ("body", "legs", "helmet", "weapon", "shield"):
        run(server.handle_unequip(s, {"equip_slot": slot}))
        assert s.equipment[slot] is None, (slot, errors(s))
    assert not any("can't take off" in e for e in errors(s)), errors(s)
    assert not hasattr(gear_rules, "LOCKED_IN_DUNGEON")


# ---- 3. who can fight: a sword or axe, any armour or none, outfit or not -------------------------
def test_no_weapon_cannot_attack():
    s = make()
    wear_kit(s, {"body": KIT["body"], "legs": KIT["legs"], "helmet": KIT["helmet"]})   # armour is not enough
    s.in_combat_with = ("monster", 1)
    run(server.handle_attack(s, {"target_id": 1}))
    assert errors(s)[-1] == gear_rules.NO_FIGHT_MSG
    assert s.in_combat_with is None and not gear_rules.can_fight(s, server.ITEMS)


def test_bow_or_tool_cannot_attack():
    for weapon, tool in (("shortbow", None), (None, "bronze_axe"), (None, "bronze_pickaxe")):
        s = make()
        s.equipment["weapon"], s.equipment["tool"] = weapon, tool
        assert not gear_rules.can_fight(s, server.ITEMS), (weapon, tool)


def test_armed_can_attack_without_armour():
    for weapon in ("bronze_sword", "mithril_battleaxe", "eclipse_cleaver"):
        s = make()
        wear_kit(s, {"weapon": weapon})
        assert gear_rules.can_fight(s, server.ITEMS), weapon
        run(server.handle_attack(s, {"target_id": -999}))
        assert gear_rules.NO_FIGHT_MSG not in errors(s)
    s = make()
    wear_kit(s, {"weapon": "bronze_sword", "helmet": KIT["helmet"]})   # partial armour
    assert gear_rules.can_fight(s, server.ITEMS)


def test_outfit_keeps_weapon_and_fights():
    s = make()
    own_queen(s)
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)
    W.add_item_to_inventory(s, "iron_battleaxe", 1)
    idx = next(i for i, e in s.inventory.items() if e["item_id"] == "iron_battleaxe")
    run(server.handle_equip(s, {"slot_index": idx}))
    assert s.equipment["weapon"] == "iron_battleaxe"
    assert s.appearance_state()["outfit"] == "queen_gown"         # a weapon never takes the outfit off
    assert gear_rules.OUTFIT_OFF_MSG not in chats(s)
    assert gear_rules.can_fight(s, server.ITEMS)
    run(server.handle_attack(s, {"target_id": -999}))
    assert gear_rules.NO_FIGHT_MSG not in errors(s)


# ---- 4. an outfit is one whole piece -----------------------------------------------------------
def test_equipping_armour_keeps_outfit():   # David, 23 Oct 2026 (was: armour takes the outfit off)
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
        W.add_item_to_inventory(s, "mythos_legs", 1)      # body and legs are a pair (23 Oct 2026)
        idx = next(i for i, e in s.inventory.items() if e["item_id"] == "mythos_body")
        run(server.handle_equip(s, {"slot_index": idx}))
        a = s.appearance_state()
        assert s.equipment["body"] == "mythos_body" and s.equipment["legs"] == "mythos_legs", errors(s)
        assert a["outfit"] == look["outfit"], a
        assert gear_rules.OUTFIT_OFF_MSG not in chats(s)


def test_wearing_outfit_keeps_armour():   # David, 23 Oct 2026 (was: outfit takes the armour off to the bag)
    s = make()
    own_queen(s)
    wear_kit(s)
    bag_before = sorted(e["item_id"] for e in s.inventory.values())
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)
    assert all(s.equipment[k] == KIT[k] for k in ARMOUR)
    assert s.equipment["weapon"] == KIT["weapon"]
    assert sorted(e["item_id"] for e in s.inventory.values()) == bag_before


def test_full_bag_and_bank_still_wear_outfit():
    s = make()
    own_queen(s)
    wear_kit(s, {"body": "mythos_body"})
    while W.add_item_to_inventory(s, "bronze_sword", 1):
        pass
    for b in range(server.BANK_SLOTS):
        s.bank[b] = {"item_id": "bronze_sword", "qty": 1}
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert s.equipment["body"] == "mythos_body"
    assert s.appearance_state()["outfit"] == "queen_gown", errors(s)


def test_no_outfit_change_in_dungeon():
    s = make()
    own_queen(s)
    wear_kit(s)
    s.dungeon = {"id": "tidehollow"}
    run(server.handle_update_appearance(s, {"appearance": queen_look(s)}))
    assert errors(s)[-1] == "You can't change into an outfit inside a dungeon."
    assert s.equipment["body"] == KIT["body"] and s.appearance_state().get("outfit") != "queen_gown"


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


# ---- 5. body + legs are a pair (David, 23 Oct 2026) -----------------------------------------------
def _bag(s, *ids):
    for i in ids:
        W.add_item_to_inventory(s, i, 1)


def _idx(s, item_id):
    return next(i for i, e in s.inventory.items() if e and e["item_id"] == item_id)


def test_pair_body_needs_legs():
    s = make()
    _bag(s, "bronze_body")
    run(server.handle_equip(s, {"slot_index": _idx(s, "bronze_body")}))
    assert s.equipment["body"] is None and s.equipment["legs"] is None
    assert errors(s)[-1] == gear_rules.pair_need_message("bronze_body", server.ITEMS), errors(s)
    assert "Bronze" in errors(s)[-1] or "legs" in errors(s)[-1].lower()


def test_pair_equip_puts_both_on():
    for body, legs, click in (("bronze_body", "bronze_legs", "bronze_body"), ("iron_chainbody", "iron_chainlegs", "iron_chainlegs"),
                              ("recruit_bronze_body", "recruit_bronze_legs", "recruit_bronze_legs"),
                              ("leather_body", "leather_chaps", "leather_body")):
        s = make()
        _bag(s, body, legs)
        run(server.handle_equip(s, {"slot_index": _idx(s, click)}))
        assert s.equipment["body"] == body and s.equipment["legs"] == legs, (body, errors(s))
        assert not any(e["item_id"] in (body, legs) for e in s.inventory.values() if e)


def test_pair_swap_returns_old_pair():
    s = make()
    wear_kit(s, {"body": "bronze_body", "legs": "bronze_legs"})
    _bag(s, "steel_body", "steel_legs")
    run(server.handle_equip(s, {"slot_index": _idx(s, "steel_legs")}))
    assert (s.equipment["body"], s.equipment["legs"]) == ("steel_body", "steel_legs"), errors(s)
    bag = sorted(e["item_id"] for e in s.inventory.values() if e)
    assert bag == ["bronze_body", "bronze_legs"], bag


def test_pair_unequip_takes_both_off():
    for slot in ("body", "legs"):
        s = make()
        wear_kit(s, {"body": "mithril_body", "legs": "mithril_legs"})
        run(server.handle_unequip(s, {"equip_slot": slot}))
        assert s.equipment["body"] is None and s.equipment["legs"] is None, (slot, errors(s))
        bag = sorted(e["item_id"] for e in s.inventory.values() if e)
        assert bag == ["mithril_body", "mithril_legs"], bag


def test_pair_unequip_needs_two_spaces():
    s = make()
    wear_kit(s, {"body": "mithril_body", "legs": "mithril_legs"})
    while W.add_item_to_inventory(s, "bronze_sword", 1):
        pass
    s.inventory.pop(_idx(s, "bronze_sword"))          # exactly one free space
    run(server.handle_unequip(s, {"equip_slot": "body"}))
    assert errors(s)[-1] == gear_rules.PAIR_ROOM_MSG
    assert s.equipment["body"] == "mithril_body" and s.equipment["legs"] == "mithril_legs"


def test_pair_solo_piece_works_alone():
    s = make()
    _bag(s, "bronze_helmet")
    # Helmet has no body/legs partner — equips alone.
    run(server.handle_equip(s, {"slot_index": _idx(s, "bronze_helmet")}))
    assert s.equipment[server.ITEMS["bronze_helmet"]["equip_slot"]] == "bronze_helmet", errors(s)


def test_pair_ui_hint():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import equipment_ui_v2
    assert "pair" in equipment_ui_v2._slot_hint("body") and "pair" in equipment_ui_v2._slot_hint("legs")
    assert equipment_ui_v2._slot_hint("helmet").startswith("Helmet slot")


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
