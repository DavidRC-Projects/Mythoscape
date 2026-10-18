"""Outfits vs armour, the dungeon gear gate and who may fight (David, 17 Oct 2026).

- An outfit is one whole piece. Equipping any armour piece or weapon takes the outfit off and puts the player in the
  plain base clothes (the starter Linen Shirt + Work Trousers / Long Wool Skirt). Putting an outfit on takes every
  armour piece and weapon off, into the inventory, or the bank when the inventory is full. Nothing is ever lost.
- Dungeons (not the Castle Realm) need a chest plate, leg armour, a helmet and a weapon to enter, and those four
  can't be taken off inside.
- A player in an outfit, or with no weapon, can't fight.
"""
import json

ARMOUR_SLOTS = ("helmet", "body", "legs", "weapon", "shield")
GATE_SLOTS = (("body", "a chest plate"), ("legs", "leg armour"), ("helmet", "a helmet"), ("weapon", "a weapon"))
LOCKED_IN_DUNGEON = {"body": "chest plate", "legs": "leg armour", "helmet": "helmet", "weapon": "weapon"}
NO_FIGHT_MSG = "You can't fight dressed like this, run!"
BASE_TOP = "top_linen_shirt"
BASE_BOTTOM = {"male": "bottom_work_trousers", "female": "bottom_long_skirt"}
OUTFIT_OFF_MSG = "You take off your outfit and change into your plain base clothes."


def in_real_dungeon(session):
    d = getattr(session, "dungeon", None)
    return bool(d) and d.get("id") != "castle_realm"


def saved_look(session):
    raw = session._row_val("appearance") if hasattr(session, "_row_val") else None
    if not raw:
        return None
    try:
        look = json.loads(raw)
    except Exception:
        return None
    return look if isinstance(look, dict) else None


def wearing_outfit(look):
    return bool(isinstance(look, dict) and look.get("outfit"))


def can_fight(session):
    if wearing_outfit(saved_look(session)):
        return False
    return bool((getattr(session, "equipment", None) or {}).get("weapon"))


def gate_missing(session):
    eq = getattr(session, "equipment", None) or {}
    return [label for slot, label in GATE_SLOTS if not eq.get(slot)]


def gate_message(missing):
    need = "a chest plate, leg armour, a helmet and a weapon"
    return (f"The dungeon gate stays shut. You need {need} equipped to enter. "
            f"Missing: {', '.join(missing)}.")


def unequip_locked_message(slot):
    return f"You can't take off your {LOCKED_IN_DUNGEON[slot]} inside a dungeon."


def worn_armour(session):
    eq = getattr(session, "equipment", None) or {}
    return [(s, eq[s]) for s in ARMOUR_SLOTS if eq.get(s)]


def base_look(look, sex, set_items=None):
    """The same look with the outfit and its set pieces off, in the plain base clothes. Hair, skin and shoes stay."""
    out = dict(look or {})
    table = set_items or {}

    def is_set_piece(item_id):
        return bool(item_id) and bool((table.get(item_id) or {}).get("set"))
    out["outfit"] = None
    for key in ("cloak", "head", "held"):
        if out.get(key) and (is_set_piece(out[key]) or not table):
            out[key] = None
    out["jewellery"] = [j for j in out.get("jewellery") or [] if table and not is_set_piece(j)]
    out["palette"] = None
    out["outfit_level"] = 1
    out["top"] = BASE_TOP
    out["bottom"] = BASE_BOTTOM.get("female" if str(sex).lower() == "female" else "male")
    return out
