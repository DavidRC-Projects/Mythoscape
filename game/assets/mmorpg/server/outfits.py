"""Mythos Outfitters rules: catalogue cache, story unlocks, regalia, pricing, appearance cleaning.

Pure functions over a session + sqlite connection so they can be tested without the websocket server.
Rules: OUTFITS_SPEC.md §3–5. Catalogue: player_hd/assets/catalogue.json (sets, garment_palettes, skin_palette).
"""
import json
import os
import time

import nobility
import reputation

CAT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets", "catalogue.json")
_CACHE = {"mtime": None, "data": None, "items": None}
REP_ORDER = ["Hated", "Distrusted", "Neutral", "Respected", "Honoured", "Revered"]
HIDDEN_BELOW_NEUTRAL = 5          # T5–T7 hidden while Hated/Distrusted
REIGN_DAYS_FOR_REGAL_T7 = 7
REGALIA_TITLES = {
    6: {"female": ("Queen Consort", "Queen"), "male": ("Prince Consort", "King")},
    7: {"female": ("Queen",), "male": ("King",)},
}
APPEARANCE_KEYS = ("skin", "skin_tone", "hair", "hair_colour", "top", "bottom", "shoes", "outfit",
                   "accessories", "cloak", "head", "jewellery", "held", "palette", "outfit_level")
SAVED_SLOTS = 6
# Account-only wardrobe: these usernames skip story unlocks for one sex of set.
# esteph → every dress (female gown sets). david → every outfit (male coat sets).
# Anyone else still has to meet the normal reputation, rank and title rules.
ACCOUNT_WARDROBE = {
    "esteph": "female",
    "david": "male",
}


# ---- catalogue ---------------------------------------------------------------------------------
def catalogue():
    """Parsed catalogue, re-read only when the file changes (review gap 11)."""
    try:
        mtime = os.path.getmtime(CAT_PATH)
    except OSError:
        mtime = None
    if _CACHE["data"] is None or mtime != _CACHE["mtime"]:
        with open(CAT_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        _CACHE.update(mtime=mtime, data=data, items={e["id"]: e for e in data.get("items") or []})
    return _CACHE["data"]


def items():
    catalogue()
    return _CACHE["items"]


def sets():
    return catalogue().get("sets") or {}


def set_order(sex):
    return list((catalogue().get("set_order") or {}).get(_sex(sex)) or [])


def _sex(sex):
    return "female" if str(sex or "").lower() == "female" else "male"


def tone_ids():
    return [t.get("id") for t in catalogue().get("skin_palette") or []]


def default_tone():
    return ((catalogue().get("defaults") or {}).get("male") or {}).get("skin_tone") or "tone_3"


# ---- player facts ------------------------------------------------------------------------------
def _rep_tier(session):
    return reputation.tier(getattr(session, "reputation", 0))


def _favour(session, conn):
    if conn is None:
        return 0
    try:
        import throne
        return int(throne.favour_row(conn, session.player_id)["favour"] or 0)
    except Exception:
        return 0


def courtier_started(session, conn):
    """Women only. The path counts as started once any court favour is earned or the path is open."""
    if _sex(getattr(session, "gender", "")) != "female":
        return False
    if _favour(session, conn) > 0:
        return True
    try:
        import throne
        return bool(throne.courtier_eligible(session, conn)[0])
    except Exception:
        return False


def reign_days(session, conn):
    if conn is None:
        return 0
    try:
        rows = conn.execute("SELECT started_at, ended_at, days FROM reigns WHERE player_id = ?",
                            (session.player_id,)).fetchall()
    except Exception:
        return 0
    total = 0.0
    now = time.time()
    for started, ended, days in rows:
        if started:
            total += max(0.0, (float(ended) if ended else now) - float(started)) / 86400.0
        else:
            total += float(days or 0)
    return int(total)


# ---- unlock rules ------------------------------------------------------------------------------
def _account_name(session):
    return (getattr(session, "username", "") or "").strip().lower()


def account_wardrobe(session):
    """'female' (dresses), 'male' (outfits), or None when the account earns sets normally."""
    return ACCOUNT_WARDROBE.get(_account_name(session))


def _item_sex(item):
    """Sex of a set entry or catalogue piece (via its set when the piece has no sex)."""
    if not item:
        return None
    sex = item.get("sex")
    if sex in ("female", "male"):
        return sex
    sid = item.get("set") or item.get("id")
    entry = sets().get(sid) if sid else None
    sex = (entry or {}).get("sex")
    return sex if sex in ("female", "male") else None


def account_unlocks(session, item):
    """True when this account is gifted every set of the item's sex."""
    gift = account_wardrobe(session)
    return bool(gift and _item_sex(item) == gift)


def _rank_hint(rank, sex):
    name = nobility.rank_name(rank, sex)
    return f"Become a {name} (noble rank {rank}) — petition Lord Chamberlain Aric."


def _challenge_guild_officer(session):
    """Leader or Officer of a guild whose strength makes it Royal-Challenge eligible."""
    try:
        import clans
        cid = clans.clan_of(session.player_id)
        if not cid or clans.rank_of(session.player_id) not in ("Leader", "Officer"):
            return False
        return bool(clans.royal_challenge_strength(cid)[3])
    except Exception:
        return False


def _check_one(rule, session, conn):
    """One rule object (all keys must hold) -> (ok, hint, progress)."""
    sex = _sex(getattr(session, "gender", ""))
    for key in ("rep", "rank", "courtier_favour", "title", "challenge_guild"):
        if key not in rule:
            continue
        if key == "rep":
            have = _rep_tier(session)
            if REP_ORDER.index(have) < REP_ORDER.index(rule["rep"]):
                return False, f"Reach {rule['rep']} reputation (you are {have}).", None
        elif key == "rank":
            rank = int(getattr(session, "noble_rank", 0) or 0)
            if rank < int(rule["rank"]):
                return False, _rank_hint(int(rule["rank"]), sex), f"rank {rank} / {int(rule['rank'])}"
        elif key == "courtier_favour":
            need = int(rule["courtier_favour"])
            if sex != "female":
                return False, "", None            # men never see Courtier wording
            have = _favour(session, conn)
            if not courtier_started(session, conn):
                return False, f"Start the Courtier's Path, then earn {need:,} Court Favour.", f"0 / {need:,}"
            if have < need:
                return False, f"Court Favour {need:,} on the Courtier's Path (you have {have:,}).", \
                    f"{have:,} / {need:,}"
        elif key == "challenge_guild":
            if not _challenge_guild_officer(session):
                return False, ("Lead or be an Officer of a guild that can make the Royal Challenge "
                               "(12 players with recruits)."), None
        elif key == "title":
            titles = list(rule["title"])
            if getattr(session, "royal_title", None) not in titles:
                return False, f"Worn only by the reigning {titles[0]}.", None
    return True, "", None


def check_rule(rule, session, conn=None):
    if not rule:
        return True, "", None
    if "any" in rule:
        hints = []
        for sub in rule["any"]:
            ok, hint, progress = _check_one(sub, session, conn)
            if ok:
                return True, "", None
            if hint:
                hints.append((hint, progress))
        if not hints:
            return False, "Locked.", None
        parts = [h.rstrip(".") for h, _p in hints]
        text = parts[0] + "".join(", or " + p[:1].lower() + p[1:] for p in parts[1:]) + "."
        return False, text, hints[0][1]
    return _check_one(rule, session, conn)


def tier_hidden(session, tier):
    return int(tier or 0) >= HIDDEN_BELOW_NEUTRAL and _rep_tier(session) in ("Hated", "Distrusted")


def outfit_unlocked(session, item, conn=None):
    """(ok, hint, progress) for buying a catalogue item or a set entry."""
    if not item:
        return False, "That item is not in the catalogue.", None
    sex = item.get("sex")
    if sex and sex != _sex(getattr(session, "gender", "")):
        return False, "That isn't cut for you.", None
    if account_unlocks(session, item):
        return True, "", None
    if tier_hidden(session, item.get("tier")):
        return False, "Mae won't show that to someone of your standing.", None
    return check_rule(item.get("unlock"), session, conn)


def tier_unlocked(session, tier, conn=None):
    """True when this player's own set of that tier is unlocked."""
    for sid in set_order(getattr(session, "gender", "")):
        entry = sets().get(sid) or {}
        if int(entry.get("tier") or 0) == int(tier):
            return outfit_unlocked(session, entry, conn)[0]
    return False


REGALIA_REFUSED = "Regalia are worn only while you hold the title."


def regalia_ok(session, item):
    if not item or not item.get("regalia"):
        return True
    if account_unlocks(session, item):
        return True
    allowed = (REGALIA_TITLES.get(int(item.get("tier") or 0)) or {}).get(_sex(getattr(session, "gender", ""))) or ()
    return getattr(session, "royal_title", None) in allowed


def unlocks(session, conn=None):
    """outfit_unlocks for full_state: set id -> {state, hint, progress}; plus tier flags for upgrades."""
    out = {}
    for sid in set_order(getattr(session, "gender", "")):
        entry = sets().get(sid) or {}
        if account_unlocks(session, entry):
            out[sid] = {"state": "unlocked", "hint": "", "progress": None}
            continue
        if tier_hidden(session, entry.get("tier")):
            out[sid] = {"state": "hidden", "hint": "", "progress": None}
            continue
        ok, hint, progress = outfit_unlocked(session, entry, conn)
        out[sid] = {"state": "unlocked" if ok else "locked", "hint": hint, "progress": progress}
    return out


# ---- ownership ---------------------------------------------------------------------------------
def owned_level(owned, set_id):
    level = 1
    for n in (2, 3):
        if f"{set_id}@{n}" in owned:
            level = n
    return level


def palette_owned(owned, item, palette_id):
    pals = list(item.get("palettes") or [])
    if not pals or palette_id in (None, pals[0]):
        return True
    return f"palette:{item.get('set')}:{palette_id}" in owned or f"palette:{item['id']}:{palette_id}" in owned


def upgrade_requirement(session, set_entry, level, conn=None):
    """(ok, hint) for reaching Fine (2) or Regal (3)."""
    if account_unlocks(session, set_entry):
        return True, ""
    tier = int(set_entry.get("tier") or 1)
    need_tier = min(7, tier + (1 if level == 2 else 2))
    names = {}
    for sid in set_order(getattr(session, "gender", "")):
        names[int((sets().get(sid) or {}).get("tier") or 0)] = (sets().get(sid) or {}).get("name", sid)
    label = "Fine" if level == 2 else "Regal"
    if not tier_unlocked(session, need_tier, conn):
        return False, f"Unlock the {names.get(need_tier, f'tier {need_tier}')} tier to reach {label}."
    if level == 3 and tier + 2 > 7:
        days = reign_days(session, conn)
        if days < REIGN_DAYS_FOR_REGAL_T7:
            return False, f"Reign {REIGN_DAYS_FOR_REGAL_T7} days to reach Regal ({days} / {REIGN_DAYS_FOR_REGAL_T7})."
    return True, ""


# ---- pricing -----------------------------------------------------------------------------------
def quote(session, piece_ids, owned, discount, set_id=None):
    """Cost before tax for the unowned pieces. A whole set bought together gets the set price (≈15% off)."""
    table = items()
    want = [i for i in dict.fromkeys(piece_ids or []) if i in table and not table[i].get("starter") and i not in owned]
    score = getattr(session, "reputation", 0)
    lines = []
    total = 0
    bundle = None
    entry = sets().get(set_id) if set_id else None
    if entry:
        unowned = [p for p in entry.get("pieces") or [] if p not in owned]
        if unowned and all(p in want for p in unowned):
            pieces = [p for p in unowned if not _free_regalia(session, table.get(p))]
            if len(unowned) == len(entry.get("pieces") or []) and len(pieces) == len(unowned):
                base = int(entry.get("price") or 0)
            else:
                share = 1.0 - float(catalogue().get("set_bundle_discount") or 0.15)
                base = int(round(sum(int(table[p].get("price") or 0) for p in pieces) * share))
            bundle = {"set": set_id, "pieces": unowned, "base": base}
            cost = reputation.buy_price(base, score, discount) if base else 0
            lines.append((set_id, cost))
            total += cost
            want = [i for i in want if i not in unowned]
    for item_id in want:
        base = 0 if _free_regalia(session, table[item_id]) else int(table[item_id].get("price") or 0)
        cost = reputation.buy_price(base, score, discount) if base else 0
        lines.append((item_id, cost))
        total += cost
    return {"total": total, "lines": lines, "bundle": bundle,
            "pieces": [i for i in dict.fromkeys(piece_ids or []) if i in table and not table[i].get("starter")
                       and i not in owned]}


def _free_regalia(session, item):
    """The T7 crown comes free with the coronation."""
    return bool(item and item.get("regalia") and int(item.get("tier") or 0) == 7 and regalia_ok(session, item))


# ---- starter outfit ----------------------------------------------------------------------------
def starter_set(sex):
    """Everyone starts as a peasant: the tier 1 set for their sex (catalogue starter_sets)."""
    return (catalogue().get("starter_sets") or {}).get(_sex(sex))


def starter_look(sex, base=None):
    """The free tier 1 set worn over a base look (tone, hair colour, shoes kept), like picking the set at Mae's."""
    sex = _sex(sex)
    look = normalise(dict(base or (catalogue().get("defaults") or {}).get(sex) or {}))
    entry = sets().get(starter_set(sex) or "") or {}
    if not entry:
        return look
    table = items()
    pals = entry.get("palettes") or [None]
    look.update(outfit=None, cloak=None, head=None, held=None, jewellery=[], outfit_level=1,
                palette=look.get("palette") if look.get("palette") in pals else pals[0])
    for pid in entry.get("pieces") or []:
        slot = (table.get(pid) or {}).get("slot")
        if slot == "jewellery":
            look["jewellery"].append(pid)
        elif slot in ("outfit", "cloak", "head", "held"):
            look[slot] = pid
    # hair stays the player's own pick: the set's styled hair is a shop item, not part of the free starter
    return look


def has_outfit(look):
    return bool((look or {}).get("outfit") or (look or {}).get("set"))


# ---- appearance --------------------------------------------------------------------------------
def normalise(appearance):
    """Fill new keys on an old saved look (legacy skin ids -> tones). Never fails."""
    if not isinstance(appearance, dict):
        return appearance
    cat = catalogue()
    look = dict(appearance)
    aliases = cat.get("skin_aliases") or {}
    if look.get("skin_tone") not in tone_ids():
        look["skin_tone"] = aliases.get(look.get("skin")) or default_tone()
    if look.get("skin") in aliases and "skin_base" in items():
        look["skin"] = "skin_base"
    look.setdefault("outfit", None)
    look.setdefault("accessories", [])
    for key in ("cloak", "head", "held", "palette"):
        look.setdefault(key, None)
    look["jewellery"] = list(look.get("jewellery") or [])
    look["outfit_level"] = int(look.get("outfit_level") or 1)
    return look


def strip_regalia(session, look):
    """Regalia vanish from the look while the title isn't held; the rest of the set stays."""
    if not isinstance(look, dict):
        return look
    table = items()
    out = dict(look)
    for key in ("head", "held", "cloak"):
        if out.get(key) and not regalia_ok(session, table.get(out[key])):
            out[key] = None
    out["jewellery"] = [j for j in out.get("jewellery") or [] if regalia_ok(session, table.get(j))]
    return out


def clean_legacy(session, appearance, owned):
    """Pre-sidebar layered validator. Kept only as the error fallback of clean() (SIDEBAR_DESIGN §8)."""
    if not isinstance(appearance, dict):
        return None, "Invalid appearance data."
    cat = catalogue()
    table = items()
    sex = _sex(getattr(session, "gender", ""))
    aliases = cat.get("skin_aliases") or {}
    tone = appearance.get("skin_tone")
    if tone is None:
        tone = aliases.get(appearance.get("skin")) or default_tone()
    if tone not in tone_ids():
        return None, "That skin tone is not in the catalogue."
    skin_id = appearance.get("skin") or "skin_base"
    if skin_id in aliases and "skin_base" in table:
        skin_id = "skin_base"
    look = {
        "skin": skin_id, "skin_tone": tone,
        "hair": appearance.get("hair"), "hair_colour": appearance.get("hair_colour"),
        "top": appearance.get("top"), "bottom": appearance.get("bottom"), "shoes": appearance.get("shoes"),
        "outfit": appearance.get("outfit") or None, "accessories": [],
        "cloak": appearance.get("cloak") or None, "head": appearance.get("head") or None,
        "held": appearance.get("held") or None, "jewellery": [],
        "palette": appearance.get("palette") or None, "outfit_level": 1,
    }
    if look["hair_colour"] not in {e.get("id") for e in cat.get("hair_palette") or []}:
        return None, "That hair colour is not in the catalogue."

    def usable(item_id, slot, what):
        item = table.get(item_id)
        if not item or item.get("slot") != slot:
            return f"That {what} is not in the catalogue." if slot not in ("skin", "hair", "top", "bottom", "shoes") \
                else "That look uses an unknown item."
        if item.get("sex") and item["sex"] != sex:
            return "That isn't cut for you."
        if not item.get("starter") and item_id not in owned:
            return "You do not own every piece of that look." if slot in ("skin", "hair", "top", "bottom", "shoes") \
                else f"You do not own that {what}."
        if not regalia_ok(session, item):
            return "Regalia are worn only while you hold the title."
        return None

    for slot in ("skin", "hair", "top", "bottom", "shoes"):
        err = usable(look[slot], slot, slot)
        if err:
            return None, err
    for slot, what in (("outfit", "outfit"), ("cloak", "cloak"), ("head", "headwear"), ("held", "held item")):
        if look[slot]:
            err = usable(look[slot], slot, what)
            if err:
                return None, err
    acc_max = int(cat.get("accessory_max") or 2)
    for item_id in appearance.get("accessories") or []:
        err = usable(item_id, "accessory", "accessory")
        if err:
            return None, err
        if item_id not in look["accessories"]:
            look["accessories"].append(item_id)
        if len(look["accessories"]) > acc_max:
            return None, "Too many accessories."
    jmax = int(cat.get("jewellery_max") or 3)
    for item_id in appearance.get("jewellery") or []:
        err = usable(item_id, "jewellery", "jewellery")
        if err:
            return None, err
        if item_id not in look["jewellery"]:
            look["jewellery"].append(item_id)
        if len(look["jewellery"]) > jmax:
            return None, "Too much jewellery (3 at most)."
    outfit = table.get(look["outfit"]) if look["outfit"] else None
    if look["palette"]:
        palette_item = outfit or table.get(look["cloak"] or "") or {}
        if look["palette"] not in (cat.get("garment_palettes") or {}):
            return None, "That colour is not in the catalogue."
        if palette_item.get("palettes") and look["palette"] in palette_item["palettes"] \
                and not palette_owned(owned, palette_item, look["palette"]):
            return None, "Buy that colour first."
    try:
        level = int(appearance.get("outfit_level") or 1)
    except (TypeError, ValueError):
        return None, "Invalid outfit level."
    if level not in (1, 2, 3):
        return None, "Invalid outfit level."
    if level > 1 and (not outfit or not outfit.get("set") or owned_level(owned, outfit["set"]) < level):
        return None, "Upgrade that outfit first."
    look["outfit_level"] = level
    return look, None

# ---- sidebar v2: painted sets + small overlays (SIDEBAR_DESIGN.md) ---------------------------------
APPEARANCE_VERSION = 2
OVERLAY_SLOTS = ("head", "cloak", "jewellery")
TRADE_IN_MAIL = "Your old clothing was traded in"


def hair_swatches():
    cat = catalogue()
    ids = list(cat.get("hair_swatches") or [])
    return ids or [h.get("id") for h in cat.get("hair_palette") or [] if not h.get("legacy")]


def nearest_swatch(colour_id):
    """Old or retired hair colour -> nearest of the 10 swatches (RGB distance)."""
    swatches = hair_swatches()
    if colour_id in swatches:
        return colour_id
    pal = {h.get("id"): h for h in catalogue().get("hair_palette") or []}
    src = (pal.get(colour_id) or {}).get("mul")
    if not src:
        return swatches[1] if len(swatches) > 1 else (swatches[0] if swatches else colour_id)
    def dist(sid):
        rgb = (pal.get(sid) or {}).get("mul") or (0, 0, 0)
        return sum((int(a) - int(b)) ** 2 for a, b in zip(src, rgb))
    return min(swatches, key=dist)


def collection(sex=None):
    rows = list(catalogue().get("collection") or [])
    if sex is not None:
        rows = [r for r in rows if r.get("sex") == _sex(sex)]
    return rows


def collection_entry(set_id):
    return next((r for r in collection() if r.get("id") == set_id), None)


def collection_live(entry):
    """Live only when released and reviewed >= 8/10 (§6.2: the server refuses live below 8)."""
    if not entry or entry.get("release") != "live":
        return False
    try:
        return float(entry.get("review_score") or 0) >= 8
    except (TypeError, ValueError):
        return False


def set_of(look):
    """The painted set a look wears: 'set', else the set of its outfit piece."""
    if not isinstance(look, dict):
        return None
    if look.get("set"):
        return look["set"]
    outfit = items().get(look.get("outfit") or "") or {}
    return outfit.get("set")


def painted(set_id):
    entry = sets().get(set_id) or collection_entry(set_id) or {}
    flags = entry.get("painted") or {}
    return {k: bool(flags.get(k)) for k in ("head", "neck", "cloak")}


def overlay_blocked(item, set_id):
    """Why an overlay can't go on this set (None when it can)."""
    flags = painted(set_id)
    slot = item.get("slot")
    if slot == "head" and flags["head"]:
        return "This set wears its own crown."
    if slot == "cloak" and flags["cloak"]:
        return "This set has its own cloak."
    if slot == "jewellery" and flags["neck"] and item.get("anchor") == "neck":
        return "This set has its own necklace."
    return None


def set_render(set_id, sex):
    """Render fields for a set: its painted pieces in the old slots, so the renderer is unchanged."""
    entry = sets().get(set_id) or {}
    defaults = (catalogue().get("defaults") or {}).get(_sex(sex)) or {}
    out = {"top": defaults.get("top"), "bottom": defaults.get("bottom"), "shoes": defaults.get("shoes"),
           "outfit": None, "cloak": None, "head": None, "held": None, "jewellery": [], "accessories": [],
           "palette": None}
    for pid in entry.get("pieces") or []:
        slot = (items().get(pid) or {}).get("slot")
        if slot == "jewellery":
            out["jewellery"].append(pid)
        elif slot in ("outfit", "cloak", "head", "held"):
            out[slot] = pid
    return out


def _set_owned(session, set_id, owned):
    entry = sets().get(set_id)
    if entry is None:
        return set_id in owned
    if set_id == starter_set(getattr(session, "gender", "")):
        return True
    pieces = [p for p in entry.get("pieces") or [] if (items().get(p) or {}).get("slot") == "outfit"]
    return all((items().get(p) or {}).get("starter") or p in owned for p in pieces)


def clean_v2(session, appearance, owned):
    """New canonical block {set, skin_tone, hair_colour, head, cloak, jewellery} -> saved look.

    Overlays blocked by painted flags are stripped (not refused) and reported in look['_notes'].
    """
    if not isinstance(appearance, dict):
        return None, "Invalid appearance data."
    cat = catalogue()
    table = items()
    sex = _sex(getattr(session, "gender", ""))
    set_id = set_of(appearance) or starter_set(sex)
    entry = sets().get(set_id)
    coll = collection_entry(set_id) if entry is None else None
    if entry is None and coll is None:
        return None, "That set is not in the catalogue."
    if (entry or coll).get("sex") != sex:
        return None, "That isn't cut for you."
    if coll is not None:
        if not collection_live(coll):
            return None, "That design is coming soon."
        if set_id not in owned:
            return None, "Buy that design first."
    elif not _set_owned(session, set_id, owned):
        return None, "You do not own that set."
    # Set regalia the player didn't ask for are stripped below so the rest of the set still wears;
    # regalia the player explicitly asks to wear without the title are refused (REGALIA_REFUSED).
    tone = appearance.get("skin_tone")
    if tone not in tone_ids():
        tone = (cat.get("skin_aliases") or {}).get(appearance.get("skin")) if tone is None else tone
        if tone not in tone_ids():
            return None, "That skin tone is not in the catalogue."
    hair_colour = appearance.get("hair_colour")
    if hair_colour not in hair_swatches():
        return None, "That hair colour is not in the catalogue."
    look = {"set": set_id, "skin": "skin_base" if "skin_base" in table else appearance.get("skin"),
            "skin_tone": tone, "hair": appearance.get("hair"), "hair_colour": hair_colour,
            "appearance_version": APPEARANCE_VERSION}
    look.update(set_render(set_id, sex) if entry else set_render(starter_set(sex), sex))
    if coll is not None:
        look["outfit"] = None
    notes = []
    # Drop set regalia the player cannot hold yet (crown etc.); coat/cloak still wear.
    for slot in ("head", "cloak", "held"):
        pid = look.get(slot)
        if pid and not regalia_ok(session, table.get(pid)):
            notes.append(f"{(table.get(pid) or {}).get('name') or 'Regalia'} needs the matching title")
            look[slot] = None
    look["jewellery"] = [j for j in look.get("jewellery") or [] if regalia_ok(session, table.get(j))]

    def overlay(item_id, slot):
        item = table.get(item_id)
        if not item or item.get("slot") != slot:
            return None, "That look uses an unknown item."
        if not regalia_ok(session, item):
            return None, REGALIA_REFUSED     # asked to wear regalia (set piece or overlay) without the title
        if item.get("set") == set_id:
            return None, None          # the set's own painted piece: already in the look
        if not item.get("overlay"):
            notes.append("Updated for the new outfits")
            return None, None          # legacy layered piece: cleared (§3.6)
        if item.get("sex") and item["sex"] != sex:
            return None, "That isn't cut for you."
        if not item.get("starter") and item_id not in owned:
            return None, f"You do not own that {'headwear' if slot == 'head' else slot}."
        why = overlay_blocked(item, set_id)
        if why:
            notes.append(why)
            return None, None
        return item_id, None

    for slot in ("head", "cloak"):
        if appearance.get(slot):
            got, err = overlay(appearance[slot], slot)
            if err:
                return None, err
            if got:
                look[slot] = got
    jmax = int(cat.get("jewellery_max") or 2)
    chosen = []
    for item_id in appearance.get("jewellery") or []:
        got, err = overlay(item_id, "jewellery")
        if err:
            return None, err
        if got and got not in chosen:
            chosen.append(got)
    if len(chosen) > jmax:
        return None, f"Too much jewellery ({jmax} at most)."
    look["jewellery"] = [j for j in look["jewellery"] if j not in chosen] + chosen
    if notes:
        look["_notes"] = sorted(set(notes))
    return look, None


def clean(session, appearance, owned):
    """(look, None) or (None, error). v2 painted-set rules; the old layered validator only if v2 crashes."""
    try:
        look, err = clean_v2(session, appearance, owned)
    except Exception:
        import logging
        logging.getLogger("outfits").exception("clean_v2 failed; legacy fallback")
        return clean_legacy(session, appearance, owned)
    if look is not None:
        look.pop("_notes", None)
    return look, err


def clean_notes(session, appearance, owned):
    """Messages for what clean() stripped (painted crown, legacy pieces)."""
    try:
        look, _err = clean_v2(session, appearance, owned)
    except Exception:
        return []
    return list((look or {}).get("_notes") or [])


def legacy_refund(owned):
    """100% coin refund (base price) for what v2 retires: paid layered pieces (top/bottom/shoes/coat/
    accessory), bought colour palettes ("palette:<set|item>:<pal>") and Fine/Regal upgrades ("<set>@<n>")."""
    table = items()
    lp = catalogue().get("legacy_prices") or {}
    gpal = lp.get("garment_palettes") or {}
    lsets = lp.get("sets") or {}
    total, ids = 0, []
    for item_id in dict.fromkeys(owned or []):
        if not isinstance(item_id, str):
            continue
        price = 0
        if item_id.startswith("palette:"):
            _, owner, pal = (item_id.split(":", 2) + ["", ""])[:3]
            sid = owner if owner in lsets else (table.get(owner) or {}).get("set")
            price = int(gpal.get(pal) or 0) or int((lsets.get(sid) or {}).get("palette_price") or 0)
        elif "@" in item_id:
            sid, _, lvl = item_id.rpartition("@")
            ups = (lsets.get(sid) or {}).get("upgrade_prices") or []
            if lvl.isdigit() and 2 <= int(lvl) <= len(ups) + 1:
                price = int(ups[int(lvl) - 2])
        else:
            item = table.get(item_id)
            if item and item.get("legacy") and not item.get("starter") and int(item.get("price") or 0) > 0 \
                    and item.get("slot") != "skin":
                price = int(item["price"])
        if price > 0:
            total += price
            ids.append(item_id)
    return total, ids


def migrate_v2(look, owned, sex, tier_ok):
    """One-off v2 migration. Returns (new_look, refund_coins, refunded_ids). Idempotent on version 2.

    tier_ok(tier) -> bool is the story unlock check (outfit_noble -> T3 when unlocked, else T1).
    """
    sex = _sex(sex)
    if isinstance(look, dict) and int(look.get("appearance_version") or 0) >= APPEARANCE_VERSION:
        return look, 0, []
    old = dict(look or {})
    order = set_order(sex)
    table = items()
    set_id = set_of(old)
    if set_id and (sets().get(set_id) or {}).get("sex") != sex:
        set_id = None
    if not set_id:
        lmap = catalogue().get("legacy_map") or {}
        rule = lmap.get(old.get("outfit") or "") or lmap.get("_default") or {"tier": 1}
        tier = int(rule.get("tier") or 1)
        if tier > 1 and not tier_ok(tier):
            tier = int(rule.get("fallback_tier") or 1)
        set_id = order[tier - 1] if len(order) >= tier else starter_set(sex)
    tone = old.get("skin_tone")
    if tone not in tone_ids():
        skin_map = (catalogue().get("legacy_map") or {}).get("skin") or {}
        tone = skin_map.get(old.get("skin")) or default_tone()
    new = {"set": set_id, "skin_tone": tone, "hair": old.get("hair"),
           "hair_colour": nearest_swatch(old.get("hair_colour") or old.get("hair_tint") or "dark_brown"),
           "head": None, "cloak": None, "jewellery": [], "appearance_version": APPEARANCE_VERSION}
    for slot in ("head", "cloak"):
        item = table.get(old.get(slot) or "") or {}
        if item.get("overlay"):
            new[slot] = old[slot]
    new["jewellery"] = [j for j in old.get("jewellery") or [] if (table.get(j) or {}).get("overlay")][:2]
    refund, ids = legacy_refund(owned or [])
    new["appearance_legacy"] = {k: v for k, v in old.items() if k != "appearance_legacy"}
    new["appearance_legacy"]["migrated_at"] = int(time.time())
    new.update({k: v for k, v in set_render(set_id, sex).items()})
    return new, refund, ids


def saved_slots(raw):
    """6 named wardrobe slots. Old 3-slot lists (bare looks) keep their order."""
    out = []
    for i in range(SAVED_SLOTS):
        entry = raw[i] if isinstance(raw, list) and i < len(raw) else None
        if isinstance(entry, dict):
            entry = normalise(entry)
            entry.setdefault("name", f"Outfit {i + 1}")
        else:
            entry = None
        out.append(entry)
    return out


# ---- Mae ---------------------------------------------------------------------------------------
def mae_line(session):
    """Tier-aware greeting with the phase 6 address forms."""
    sex = _sex(getattr(session, "gender", ""))
    lady = sex == "female"
    title = getattr(session, "royal_title", None)
    rank = int(getattr(session, "noble_rank", 0) or 0)
    sir = "my lady" if lady else "my lord"
    if title in ("Queen", "King"):
        return (f"Your Majesty! The {'Queen' if lady else 'King'}'s robes are ready, and the crown has its own "
                "velvet box.")
    if title in ("Queen Consort", "Prince Consort"):
        return f"Your Highness. Pale blue and silver, I think — the {title} should outshine the court."
    if rank >= 5:
        return f"Your Grace. Ivory and gold for a {'Duchess' if lady else 'Duke'}; the court notices these things."
    if rank >= 4:
        return f"A {'Countess' if lady else 'Count'} should look the part, {sir}. The crimson has just come in."
    if rank >= 2:
        return f"{'Dame' if lady else 'Sir'}! Purple velvet came in this week, cut for {'a lady' if lady else 'a knight'}."
    if _rep_tier(session) in ("Respected", "Honoured", "Revered"):
        return "Folk speak well of you. The court colours are yours to try, love."
    if _rep_tier(session) in ("Hated", "Distrusted"):
        return "Plain cloth only, I'm afraid. Mend your name and the good bolts come out."
    return "Welcome to Mythos Outfitters. Try anything on — paying is the only part that costs."
