"""Outfits vs armour, the dungeon gear gate and who may fight (David, 17 Oct 2026; revised 23 Oct 2026).

- An outfit is one whole piece. Equipping armour no longer takes it off (David, 23 Oct 2026): partial armour and
  shields keep the outfit's painted figure (stats apply, the gear isn't drawn); a full matching tier set shows that
  tier's painted armour figure. Putting an outfit on still takes every armour piece off, into the inventory, or the
  bank when the inventory is full. Nothing is ever lost. (base_look / OUTFIT_OFF_MSG are kept for that path's tools.)
- Weapons and tools are not armour: they can be equipped while wearing an outfit and stay on when one goes on.
- Dungeons (not the Castle Realm) need only a sword or axe equipped to enter. Nothing is locked on inside.
- Anyone can fight with partial or no armour, in an outfit or not, but only with a sword or axe equipped.
"""
import json

ARMOUR_SLOTS = ("helmet", "body", "legs", "shield")   # the pieces that clash with an outfit
FIGHT_KINDS = ("sword", "axe")
NO_FIGHT_MSG = "You need a sword or axe equipped to fight. Run!"
GATE_MSG = "The dungeon gate stays shut. You need a sword or axe equipped to enter."
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


def weapon_kind(item_id, items=None):
    """'sword', 'axe', 'bow' or None. Gathering tools (hatchet, pickaxe) are not weapons."""
    if not item_id:
        return None
    if items is None:
        from content import ITEMS as items
    item = items.get(item_id) or {}
    if item.get("equip_slot") != "weapon":
        return None
    if item.get("weapon_kind"):
        return item["weapon_kind"]
    if item.get("weapon_type") == "bow" or "bow" in item_id:
        return "bow"
    if item.get("type") != "weapon":
        return None
    if "axe" in item_id or "cleaver" in item_id:
        return "axe"
    if "sword" in item_id:
        return "sword"
    return None


def has_fight_weapon(session, items=None):
    eq = getattr(session, "equipment", None) or {}
    return weapon_kind(eq.get("weapon"), items) in FIGHT_KINDS


def can_fight(session, items=None):
    return has_fight_weapon(session, items)


def gate_missing(session, items=None):
    return [] if has_fight_weapon(session, items) else ["a sword or axe"]


def gate_message(missing=None):
    return GATE_MSG


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


# ---- body + legs pair (David, 23 Oct 2026) -------------------------------------------------------------
# Body and legs are equipped and removed together, and both are needed: equipping one puts on its matching
# partner from the bag; taking one off takes both off. Pieces with no partner (goblin mail) work alone.
PAIR_SLOTS = ("body", "legs")
PAIR_NEED_MSG = "Body and legs are worn as a pair. You need the matching {partner} in your bag as well."
PAIR_ROOM_MSG = "You need two free bag spaces to take off your body and legs together."
_PAIR_SUFFIX = {"body": "legs", "chainbody": "chainlegs", "legs": "body", "chainlegs": "chainbody"}
_PAIR_EXPLICIT = {"leather_body": "leather_chaps", "leather_chaps": "leather_body"}


def pair_slot(slot):
    return {"body": "legs", "legs": "body"}.get(slot)


def pair_candidates(item_id, items=None):
    """Partner ids for a body or legs piece, best first ([] = works alone)."""
    if items is None:
        from content import ITEMS as items
    if item_id in _PAIR_EXPLICIT:
        cands = [_PAIR_EXPLICIT[item_id]]
    else:
        stem, _, suffix = str(item_id).rpartition("_")
        if not stem or suffix not in _PAIR_SUFFIX:
            return []
        first = f"{stem}_{_PAIR_SUFFIX[suffix]}"
        other = {"body": "chainlegs", "chainbody": "legs", "legs": "chainbody", "chainlegs": "body"}[suffix]
        cands = [first, f"{stem}_{other}"]
    want = pair_slot((items.get(item_id) or {}).get("equip_slot"))
    return [c for c in cands if (items.get(c) or {}).get("equip_slot") == want]


def find_partner_in_bag(item_id, inventory, items=None):
    """(slot_index, partner_id) for the first partner found in the bag, None when there is none,
    or ('solo', None) when the piece has no partner at all."""
    cands = pair_candidates(item_id, items)
    if not cands:
        return ("solo", None)
    for cand in cands:
        for idx, ent in sorted((inventory or {}).items()):
            if ent and ent.get("item_id") == cand:
                return (idx, cand)
    return None


def pair_need_message(item_id, items=None):
    if items is None:
        from content import ITEMS as items
    cands = pair_candidates(item_id, items)
    name = (items.get(cands[0]) or {}).get("name", cands[0]) if cands else "piece"
    return PAIR_NEED_MSG.format(partner=name)
