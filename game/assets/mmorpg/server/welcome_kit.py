"""Warden Tamsin's welcome: the Recruit's Bronze kit, the tutorial talk and the first-login trail (17 Oct 2026).

Everything that decides who gets what lives here and in the DB, never in the client:
- One claim per account. ``welcome_kit.claimed_at`` is set by a conditional UPDATE, so a double click, two
  requests in one tick or a second client can't claim twice.
- The claim, every item placed (bag first, then bank) and anything still owed commit in one transaction
  (``one_transaction``). A crash or a disconnect leaves either the whole grant or none of it.
- Veterans who already own a real weapon and armour aren't offered the kit. Anyone who lacks either can claim it once.
- Kit pieces are account-bound (no trade, no drop, no shop buys them, worth 1 coin), so new accounts can't farm them.
- A player with nothing at all to hold in the weapon slot can ask for one free Recruit's sword per hour, so
  nobody is ever locked out of combat.
"""
import contextlib
import copy
import json
import time

GUIDE_ID = "warden_tamsin"
GUIDE_NAME = "Warden Tamsin"
KIT = (("recruit_bronze_helmet", "helmet"), ("recruit_bronze_body", "body"),
       ("recruit_bronze_legs", "legs"), ("recruit_bronze_sword", "weapon"))
KIT_IDS = tuple(item_id for item_id, _slot in KIT)
KIT_BASE = {"recruit_bronze_helmet": "bronze_helmet", "recruit_bronze_body": "bronze_body",
            "recruit_bronze_legs": "bronze_legs", "recruit_bronze_sword": "bronze_sword"}
SWORD = "recruit_bronze_sword"
ARMOUR_SLOTS = ("helmet", "body", "legs")
SWORD_COOLDOWN_S = 3600

OPT_WEAR, OPT_TAKE, OPT_COLLECT, OPT_EQUIP = "kit_wear", "kit_take", "kit_collect", "kit_equip"
OPT_SWORD, OPT_REMIND, OPT_SKIP = "kit_sword", "remind", "skip"

# First talk: short, idiot-proof controls + kit. Long systems wait for Remind / later NPCs.
FIRST_VISIT = (
    ("Walk: click the ground, or use arrow keys / number pad.",
     "Zoom: mouse wheel over the map (or - and =)."),
    ("Travel: press M, pick a place — you still walk there.",
     "Minimap shows the way. H = every control."),
    ("Take the Recruit's Bronze kit below — prefer \"Take the kit and put it on\".",
     "Axe, pickaxe and net are already on — click trees, rocks or fish spots. Sword is for fighting."),
)

# Remind me: a bit more, still short. Bank / reputation / outfits live here, not the first dump.
TOUR = (
    ("Walking: click the ground to walk there, or use arrow keys / number pad one tile at a time.",
     "Zoom: mouse wheel over the map, or - and =. Travel: press M. World map: right-click the minimap. H = all controls."),
    ("Fighting: you need a sword or axe in your hand. Click a monster to attack, or press Space for the nearest "
     "one.",
     "Nameplates: green = easy, yellow = even, orange = risky, red = leave alone. "
     "Empty-handed? Run. Innkeeper Sarah (south of Miriam) shows you how to eat food."),
    ("Tools: axe, pickaxe and net start equipped — Equipment (E) or the Gathering tab. "
     "Keep your sword on; gathering plays the right tool when you click the resource.",
     "After Miriam's rats, the Crypt behind the bank (The Depths) is your first dungeon. "
     "Tidehollow by the harbour is later."),
    ("Skills: Tab. Bank: B near a booth. Outfits (Mae) swap off armour into your bag — nothing is lost.",
     "Where next: Elder Miriam NW cottage, then Lira by the well and Elena to the east. "
     "Come back any time for this reminder."),
)


class Rollback(Exception):
    """Raise inside one_transaction to undo every write (DB and in-memory)."""


class _HoldCommits:
    """Stand-in connection: helpers that call commit() don't end our transaction early."""

    def __init__(self, conn):
        self._conn = conn

    def commit(self):
        return None

    def __getattr__(self, name):
        return getattr(self._conn, name)


@contextlib.contextmanager
def one_transaction(db, session):
    """Every write inside commits together or not at all. The session's bag, bank and gear roll back too."""
    real = db.conn
    snapshot = copy.deepcopy((session.inventory, session.bank, session.equipment))
    real.commit()                                    # start from a clean slate
    db.conn = _HoldCommits(real)
    try:
        yield real
        real.commit()
    except BaseException:
        real.rollback()
        session.inventory, session.bank, session.equipment = snapshot
        raise
    finally:
        db.conn = real


_READY = set()


def ensure_schema(conn):
    if id(conn) in _READY:
        return
    conn.execute(
        "CREATE TABLE IF NOT EXISTS welcome_kit ("
        "player_id INTEGER PRIMARY KEY,"
        "claimed_at REAL,"
        "skipped INTEGER NOT NULL DEFAULT 0,"
        "owed TEXT NOT NULL DEFAULT '[]',"
        "sword_at REAL NOT NULL DEFAULT 0)"
    )
    conn.commit()
    _READY.add(id(conn))


def record(conn, player_id):
    ensure_schema(conn)
    row = conn.execute("SELECT claimed_at, skipped, owed, sword_at FROM welcome_kit WHERE player_id = ?",
                       (player_id,)).fetchone()
    if row is None:
        return {"claimed_at": None, "skipped": False, "owed": [], "sword_at": 0.0}
    try:
        owed = [i for i in json.loads(row[2] or "[]") if i in KIT_IDS]
    except (TypeError, ValueError):
        owed = []
    return {"claimed_at": row[0], "skipped": bool(row[1]), "owed": owed, "sword_at": float(row[3] or 0)}


def _ensure_row(conn, player_id):
    ensure_schema(conn)
    conn.execute("INSERT OR IGNORE INTO welcome_kit (player_id) VALUES (?)", (player_id,))


def take_claim(conn, player_id, now=None):
    """The one gate. True for exactly one caller per account, ever. No commit (caller's transaction)."""
    _ensure_row(conn, player_id)
    cur = conn.execute("UPDATE welcome_kit SET claimed_at = ? WHERE player_id = ? AND claimed_at IS NULL",
                       (float(now or time.time()), player_id))
    return cur.rowcount == 1


def set_owed(conn, player_id, owed):
    _ensure_row(conn, player_id)
    conn.execute("UPDATE welcome_kit SET owed = ? WHERE player_id = ?", (json.dumps(list(owed)), player_id))


def take_sword(conn, player_id, now=None):
    """Free replacement sword: True and stamps the time when the cooldown is over. No commit."""
    now = float(now or time.time())
    _ensure_row(conn, player_id)
    cur = conn.execute("UPDATE welcome_kit SET sword_at = ? WHERE player_id = ? AND sword_at <= ?",
                       (now, player_id, now - SWORD_COOLDOWN_S))
    return cur.rowcount == 1


def set_skipped(conn, player_id, skipped=True):
    _ensure_row(conn, player_id)
    conn.execute("UPDATE welcome_kit SET skipped = ? WHERE player_id = ?", (1 if skipped else 0, player_id))
    conn.commit()


def reset(conn, player_id):
    """Dev only (::welcome reset)."""
    ensure_schema(conn)
    conn.execute("DELETE FROM welcome_kit WHERE player_id = ?", (player_id,))
    conn.commit()


# ---- what the player owns ---------------------------------------------------------------------------------
def _owned_ids(session):
    for item_id in (getattr(session, "equipment", None) or {}).values():
        if item_id:
            yield item_id
    for store in (getattr(session, "inventory", None) or {}, getattr(session, "bank", None) or {}):
        for entry in store.values():
            if entry and entry.get("item_id"):
                yield entry["item_id"]


def has_weapon_slot_item(session, items):
    """Owns something to fight with: a sword or axe (gear_rules). Gathering tools and bows don't count."""
    import gear_rules
    return any(gear_rules.weapon_kind(i, items) in gear_rules.FIGHT_KINDS for i in _owned_ids(session))


def geared(session, items):
    """A veteran: owns a real weapon and at least one armour piece (helmet, chest or legs)."""
    ids = list(_owned_ids(session))
    weapon = any((items.get(i) or {}).get("type") == "weapon" for i in ids)
    armour = any((items.get(i) or {}).get("equip_slot") in ARMOUR_SLOTS for i in ids)
    return weapon and armour


def equippable_kit(session, items):
    """Kit pieces in the bag whose slot is empty or only holds a tool."""
    out = []
    bag = {e["item_id"] for e in (session.inventory or {}).values() if e}
    for item_id, slot in KIT:
        cur = (session.equipment or {}).get(slot)
        if item_id in bag and (not cur or (items.get(cur) or {}).get("type") == "tool"):
            out.append((item_id, slot))
    return out


def status(conn, session, items, now=None):
    now = float(now or time.time())
    rec = record(conn, session.player_id)
    claimed = rec["claimed_at"] is not None
    vet = geared(session, items)
    can_claim = not claimed and not vet
    no_weapon = not has_weapon_slot_item(session, items)
    sword_wait = max(0, int(rec["sword_at"] + SWORD_COOLDOWN_S - now))
    return {
        "claimed": claimed, "skipped": rec["skipped"], "owed": rec["owed"], "veteran": vet,
        "can_claim": can_claim,
        "show_path": can_claim and not rec["skipped"],
        "equippable": [i for i, _s in equippable_kit(session, items)],
        "sword_offer": no_weapon and not can_claim and not rec["owed"],
        "sword_wait": sword_wait,
    }


def public_state(st, guide, coaches=None):
    """What the client gets: only enough to draw the trail. The server re-checks everything on each request."""
    g = guide or {}
    seen = set(coaches or ())
    return {"show_path": bool(st["show_path"]), "claimed": bool(st["claimed"]), "owed": len(st["owed"]),
            "skipped": bool(st["skipped"]),
            # Spine after kit: Sarah (eat) → Miriam. Client stages the trail from this.
            "eat_done": COACH_EAT in seen,
            "guide": {"id": GUIDE_ID, "name": GUIDE_NAME, "x": g.get("x"), "y": g.get("y")}}


def public_state_after_claim(st, guide, coaches=None):
    """State right after the kit is claimed: trail stays on for Sarah → Miriam.

    The client uses show_path + claimed (+ eat_done) while no quest is underway.
    """
    state = public_state(st, guide, coaches=coaches)
    state["claimed"] = True
    state["show_path"] = True
    return state


def options(st):
    opts = []
    if st["can_claim"]:
        opts += [{"id": OPT_WEAR, "label": "Take the kit and put it on"},
                 {"id": OPT_TAKE, "label": "Just take the kit"}]
    if st["owed"]:
        opts.append({"id": OPT_COLLECT, "label": f"Collect the rest of my kit ({len(st['owed'])})"})
    if st["equippable"]:
        opts.append({"id": OPT_EQUIP, "label": "Equip it for me"})
    if st["sword_offer"]:
        if st["sword_wait"] > 0:
            mins = max(1, (st["sword_wait"] + 59) // 60)
            opts.append({"id": OPT_SWORD, "label": "I've lost my sword", "ok": False,
                         "why": f"Tamsin: I gave you one not long ago. Try again in {mins} min, "
                                "or buy one from Gareth's smithy."})
        else:
            opts.append({"id": OPT_SWORD, "label": "I've lost my sword"})
    opts.append({"id": OPT_REMIND, "label": "Remind me how things work"})
    if st["show_path"]:
        opts.append({"id": OPT_SKIP, "label": "Skip the tutorial"})
    return opts


def allowed(st):
    return {o["id"] for o in options(st) if o.get("ok", True)}


def greeting(st, name):
    if st["can_claim"]:
        return [f"Well met, {name}! I'm Warden Tamsin.",
                "Click Next for walk, zoom and Travel — then take your Bronze kit."]
    if st["owed"]:
        return ["Still holding part of your kit. Free bag space and talk again."]
    if st["sword_offer"]:
        return ["Empty-handed? Gareth sells bronze, or take one spare sword from me."]
    if st["claimed"]:
        return [f"Good to see you, {name}. Kit's one-time — Gareth sells bronze if you need more."]
    return [f"Good to see you, {name}. You're set. Pick Remind me if you want a refresher."]


def pages(st, name, tour=False, note=None):
    """Paged dialogue: greeting, then first-visit controls (or Remind tour). Notes stay single-page."""
    first = list(note) if note else greeting(st, name)
    out = [first]
    if note is not None:
        return out
    if tour:
        out += [list(p) for p in TOUR]
    elif st["can_claim"]:
        out += [list(p) for p in FIRST_VISIT]
    return out


# ---- UI coaches (one tip per NPC beat; persisted so reconnects don't re-spam) -------------------------------
COACH_EQUIP = "equip_gear_v2"  # sidebar Equipment + unequip/equip; waits for dialogue close
COACH_QUEST_ACCEPT = "quest_accept"
COACH_INVENTORY = "inventory"
COACH_INV_FILTERS = "inv_filters"  # bag filter chips (Quest / Weapon / Armour…) on first quest
COACH_SKILLS = "skills"
COACH_EAT = "eat_hp"  # why food/potions matter + Eat/R pointer
COACH_AUTO_PICKUP = "auto_pickup_coins_bones"  # Coins+bones toggle (off by default)
COACH_FIRST_FIGHT = "first_fight"  # first attack: click/Space + R
COACH_FIRST_KILL = "first_kill"    # first quest kill — confidence beat
COACH_DEATH = "first_death"        # post-death recovery once


def ensure_coaches_col(conn):
    ensure_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(welcome_kit)").fetchall()}
    if "coaches_seen" not in cols:
        conn.execute("ALTER TABLE welcome_kit ADD COLUMN coaches_seen TEXT NOT NULL DEFAULT '[]'")
        conn.commit()


def coaches_seen(conn, player_id):
    ensure_coaches_col(conn)
    row = conn.execute("SELECT coaches_seen FROM welcome_kit WHERE player_id = ?", (player_id,)).fetchone()
    if not row:
        return set()
    try:
        return set(json.loads(row[0] or "[]"))
    except (TypeError, ValueError):
        return set()


def mark_coach_seen(conn, player_id, coach_id):
    ensure_coaches_col(conn)
    _ensure_row(conn, player_id)
    seen = coaches_seen(conn, player_id)
    if coach_id in seen:
        return False
    seen.add(coach_id)
    conn.execute("UPDATE welcome_kit SET coaches_seen = ? WHERE player_id = ?",
                 (json.dumps(sorted(seen)), player_id))
    conn.commit()
    return True
