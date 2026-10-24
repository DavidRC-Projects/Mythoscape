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

TOOLS_STEP = (
    "Tools: your hatchet, pickaxe and fishing net are in your bag. Click one to equip it. It moves into the "
    "tool slot on your Equipment screen and leaves your bag.",
    "You chop, mine or fish with the tool you have equipped, so swap to the right one first: "
    "hatchet for trees, pickaxe for rocks, net or rod for fishing spots.",
)

TOUR = (
    ("Walking: click the ground and you'll walk there. The arrow keys move you one tile at a time.",
     "Zoom with the mouse wheel over the map, or with - and =. The minimap shows where you are. "
     "Right-click it to open the world map. M opens Travel. H lists every control."),
    ("Fighting: you need a sword or axe in your hand. Click a monster to attack, or press Space for the nearest "
     "one. R eats food.",
     "Nameplates are coloured against your level: green you'll win, yellow it's even, orange it's risky, "
     "red you should leave alone.",
     "Armour helps but isn't required. Without a sword or axe you can't fight at all, so if something "
     "attacks you empty-handed, run."),
    ("Dungeons: the gate opens for anyone with a sword or axe equipped. Armour is up to you.",),
    ("Outfits and armour don't mix. Put on any armour piece and your outfit comes off.",
     "Put on an outfit from Mae and your armour goes to your bag, or the bank if your bag is full. "
     "Nothing is ever lost. Your sword or axe stays in your hand either way."),
    TOOLS_STEP,
    ("Skills: chop, mine, fish, cook, smith, fletch and more. Each one levels up as you use it. "
     "Press Tab to see them all.",
     "Gareth's smithy, far to the north-east, sells bronze to mithril and buys ore. "
     "Elena, to the east, teaches archery."),
    ("The bank: press B near a booth. Your purse holds 65,000 coins, so keep the rest in the vault. "
     "Land fees are taken from the bank first.",),
    ("Reputation: honest work, quests and paying your dues all raise it. Shops treat you better as it grows, "
     "and it opens noble ranks with the Chamberlain.",
     "A high-ranking noble with a guild behind them can challenge for a castle, and one day the Crown itself. "
     "That's the road to the throne."),
    ("Where next: Elder Miriam, in the north-west cottage, has a rat problem. It's a good first fight in your new kit.",
     "Come back any time and I'll go over all of this again."),
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


def public_state(st, guide):
    """What the client gets: only enough to draw the trail. The server re-checks everything on each request."""
    g = guide or {}
    return {"show_path": bool(st["show_path"]), "claimed": bool(st["claimed"]), "owed": len(st["owed"]),
            "skipped": bool(st["skipped"]),
            "guide": {"id": GUIDE_ID, "name": GUIDE_NAME, "x": g.get("x"), "y": g.get("y")}}


def public_state_after_claim(st, guide):
    """State right after the kit is claimed: the trail is off, but stage 2 (Miriam's quest) can begin.

    The client uses show_path + claimed to run stage 2 while no quest is underway, so a fresh WELCOME_STATE
    must arrive after the claim — the client can't derive it from QUEST_LOG alone.
    """
    state = public_state(st, guide)
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
        return [f"Well met, {name}! I'm Warden Tamsin. I get new arrivals ready for Crownfall.",
                "I've a Recruit's Bronze kit with your name on it: helmet, chest plate, leg armour and a sword. "
                "Click Next to hear how things work, or just take the kit."]
    if st["owed"]:
        return ["I'm still holding part of your kit. Make some room in your bag and I'll hand it over."]
    if st["sword_offer"]:
        return ["No weapon at all? That won't do. You can't fight empty-handed.",
                "Gareth's smithy sells bronze, or you can smith your own at the anvil. "
                "I can spare one Recruit's sword to tide you over."]
    if st["claimed"]:
        return [f"Good to see you, {name}. Lost your kit? I can only hand it out once, but Gareth's smithy "
                "sells bronze, and you can smith your own at the anvil."]
    return [f"Good to see you, {name}. You look well equipped already. The kit's for those starting out.",
            "Ask me anything you like, though."]


def pages(st, name, tour=False, note=None):
    """Paged dialogue: a short first page, then the tour when asked (or on a first, unclaimed visit)."""
    first = list(note) if note else greeting(st, name)
    out = [first]
    if tour or (note is None and st["can_claim"]):
        out += [list(p) for p in TOUR]
    return out
