"""Crownfall phase 4: apprenticeships. Every number lives here; read them through functions.

A shift is one real hour while signed on with a master, online or offline. Shifts are
settled on login, on "Collect wages" and every 500 ticks for online players.
"""
from __future__ import annotations

import time

import royal_treasury

SHIFT_SECONDS = 3600
DAILY_SHIFT_CAP = 8
BACKLOG_DAYS = 3
BACKLOG_SHIFT_CAP = DAILY_SHIFT_CAP * BACKLOG_DAYS   # 24
RESIGN_COOLDOWN = 3600
XP_LEVEL_SCALE_MAX = 2.0
REP_PER_SHIFT = 1
REP_SHIFT_DAILY_CAP = 5
ETIQUETTE_PER_SHIFT = 40

# workplace -> (display name, skill, wage, base xp, min level)
WORKPLACES = {
    "farm": ("Farm", "cooking", 40, 60, 1),
    "workshop": ("Workshop", "fletching", 50, 75, 1),
    "smithy": ("Smithy", "smithing", 60, 90, 1),
}

# master NPC id -> workplace
MASTERS = {
    "master_hollis": "farm",
    "master_wren": "workshop",
    "master_doran": "smithy",
}

MASTER_OPTIONS = [
    {"id": "app_sign", "label": "Sign on as apprentice"},
    {"id": "app_collect", "label": "Collect wages"},
    {"id": "app_leave", "label": "Leave apprenticeship"},
    {"id": "app_info", "label": "What do I earn?"},
]


def workplace(key):
    return WORKPLACES.get(key)


def wage(key):
    return WORKPLACES[key][2]


def skill(key):
    return WORKPLACES[key][1]


def shift_xp(key, level):
    base = WORKPLACES[key][3]
    return int(base * min(XP_LEVEL_SCALE_MAX, 1 + int(level) / 100))


def wage_tax(amount):
    return int(int(amount) * royal_treasury.sales_tax_rate())


def info_lines(key):
    name, sk, w, xp, lvl = WORKPLACES[key]
    return [
        f"{name} apprentice: {w} coins a shift (5% wage tax to the Crown), {xp} {sk.title()} XP a shift.",
        f"One shift is an hour, online or offline. At most {DAILY_SHIFT_CAP} shifts a day, "
        f"and up to {BACKLOG_DAYS} days of shifts wait for you.",
        "Wages go to your bank. Working the craft yourself always teaches more.",
    ]


def ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS apprentice_contracts (
            player_id INTEGER PRIMARY KEY, master_id TEXT, workplace TEXT,
            property_id INTEGER NULL, started_at REAL, last_settled REAL, left_at REAL NULL)"""
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(apprentice_contracts)")}
    if "last_wages" not in cols:
        conn.execute("ALTER TABLE apprentice_contracts ADD COLUMN last_wages INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS apprentice_daily (
            player_id INTEGER, day TEXT, shifts INTEGER, PRIMARY KEY(player_id, day))"""
    )
    conn.commit()


# ---- bank helpers (shared with property.py) --------------------------------
_bank_hook = None   # fn(player_id, new_bank) -> keeps a live session in step


def set_bank_hook(fn):
    global _bank_hook
    _bank_hook = fn


def bank_get(conn, player_id):
    row = conn.execute("SELECT bank_coins FROM players WHERE id = ?", (player_id,)).fetchone()
    return int(row[0] or 0) if row else 0


def bank_set(conn, player_id, value):
    try:
        from content import MAX_BANK_COINS
    except Exception:
        MAX_BANK_COINS = 2 ** 62
    value = max(0, min(int(MAX_BANK_COINS), int(value)))
    conn.execute("UPDATE players SET bank_coins = ? WHERE id = ?", (value, player_id))
    conn.commit()
    if _bank_hook:
        _bank_hook(player_id, value)
    return value


def bank_add(conn, player_id, delta):
    return bank_set(conn, player_id, bank_get(conn, player_id) + int(delta))


# ---- contracts --------------------------------------------------------------
def contract(conn, player_id):
    row = conn.execute(
        "SELECT master_id, workplace, property_id, started_at, last_settled, left_at, last_wages "
        "FROM apprentice_contracts WHERE player_id = ?", (player_id,),
    ).fetchone()
    if row is None:
        return None
    keys = ("master_id", "workplace", "property_id", "started_at", "last_settled", "left_at", "last_wages")
    return dict(zip(keys, row))


def active(conn, player_id):
    c = contract(conn, player_id)
    return c if c and c["master_id"] else None


def sign_on(conn, player_id, master_id, wp, property_id=None, now=None):
    """Returns (ok, message)."""
    now = time.time() if now is None else float(now)
    c = contract(conn, player_id)
    if c and c["master_id"]:
        return False, f"You already work at the {WORKPLACES[c['workplace']][0]}. Leave first."
    if c and c["left_at"] and now - float(c["left_at"]) < RESIGN_COOLDOWN:
        mins = int((RESIGN_COOLDOWN - (now - float(c["left_at"]))) // 60) + 1
        return False, f"You only just left a master. Come back in {mins} minutes."
    conn.execute(
        "INSERT INTO apprentice_contracts (player_id, master_id, workplace, property_id, started_at, last_settled, left_at) "
        "VALUES (?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(player_id) DO UPDATE SET master_id = excluded.master_id, "
        "workplace = excluded.workplace, property_id = excluded.property_id, started_at = excluded.started_at, "
        "last_settled = excluded.last_settled, left_at = NULL",
        (player_id, master_id, wp, property_id, now, now),
    )
    conn.commit()
    return True, f"You sign on at the {WORKPLACES[wp][0]}. Each hour you are signed on is a paid shift."


def leave(conn, player_id, now=None):
    now = time.time() if now is None else float(now)
    if not active(conn, player_id):
        return False, "You are not apprenticed to anyone."
    conn.execute(
        "UPDATE apprentice_contracts SET master_id = NULL, property_id = NULL, left_at = ? WHERE player_id = ?",
        (now, player_id),
    )
    conn.commit()
    return True, "You leave your apprenticeship. You can sign on again in an hour."


def shifts_today(conn, player_id, now=None):
    import reputation
    row = conn.execute(
        "SELECT shifts FROM apprentice_daily WHERE player_id = ? AND day = ?",
        (player_id, reputation.today(now)),
    ).fetchone()
    return int(row[0]) if row else 0


def due_slots(last_settled, now, used_by_day):
    """Pure: which hour slots are paid. Returns (paid_days list, new_last_settled).

    Whole hours since last_settled; only the last BACKLOG_DAYS count; each real day
    pays at most DAILY_SHIFT_CAP (counting shifts already paid that day); the total
    never exceeds BACKLOG_SHIFT_CAP. Dropped hours are simply gone (never debt).
    """
    import reputation
    hours = int((float(now) - float(last_settled)) // SHIFT_SECONDS)
    if hours <= 0:
        return [], float(last_settled)
    used = dict(used_by_day)
    paid = []
    earliest = float(now) - BACKLOG_DAYS * 86400
    for i in range(hours):
        end = float(last_settled) + (i + 1) * SHIFT_SECONDS
        if end <= earliest:
            continue
        day = reputation.today(end)
        if used.get(day, 0) >= DAILY_SHIFT_CAP or len(paid) >= BACKLOG_SHIFT_CAP:
            continue
        used[day] = used.get(day, 0) + 1
        paid.append(day)
    return paid, float(last_settled) + hours * SHIFT_SECONDS


def settle(conn, session, now=None, grant_xp=None):
    """Settle shifts for a live session. Returns a result dict or None.

    grant_xp(session, skill, amount) applies XP (World.grant_xp in the server).
    """
    import property as _property
    now = time.time() if now is None else float(now)
    pid = session.player_id
    c = active(conn, pid)
    if not c:
        return None
    wp = c["workplace"]
    days_used = {r[0]: int(r[1]) for r in conn.execute(
        "SELECT day, shifts FROM apprentice_daily WHERE player_id = ?", (pid,))}
    slots, new_last = due_slots(c["last_settled"] or now, now, days_used)
    if new_last == float(c["last_settled"] or now):
        return None
    owner = None
    if c["property_id"]:
        owner = _property.owner_of(conn, c["property_id"])
        if owner is None or owner == pid:   # property gone: fall back to a plain NPC master
            owner = None
    paid_slots = []
    skipped = 0
    w = wage(wp)
    if owner is None:
        import politics
        w = int(w * politics.shift_income_mult(conn))
    for day in slots:
        if owner is not None:
            if bank_get(conn, owner) < w:
                skipped += 1
                continue
            bank_add(conn, owner, -w)
            _property.credit_owner(conn, owner, _property.WORKER_VALUE - w)
        paid_slots.append(day)
    for day in paid_slots:
        conn.execute(
            "INSERT INTO apprentice_daily (player_id, day, shifts) VALUES (?, ?, 1) "
            "ON CONFLICT(player_id, day) DO UPDATE SET shifts = shifts + 1", (pid, day))
    if skipped and owner is not None:
        _property.note_unpaid(conn, c["property_id"], skipped)
    n = len(paid_slots)
    gross = n * w
    tax = wage_tax(gross)
    net = gross - tax
    if net:
        session.bank_coins = bank_add(conn, pid, net)
    if tax:
        royal_treasury.credit(conn, "wage_tax", pid, tax)
    sk = skill(wp)
    xp = 0
    lvl = session.level(sk) if sk in session.xp else 1   # level when the settle starts
    import ruling
    roads = ruling.ROADS_APPRENTICE_XP_BONUS if ruling.work_active(conn, "roads", now) else 0.0
    for _ in range(n):
        amt = int(shift_xp(wp, lvl) * (1 + roads))
        xp += amt
        if grant_xp:
            grant_xp(session, sk, amt)
        elif sk in session.xp:
            session.xp[sk] += amt
    conn.execute("UPDATE apprentice_contracts SET last_settled = ?, last_wages = ? WHERE player_id = ?",
                 (new_last, net if n else c["last_wages"], pid))
    conn.commit()
    return {"shifts": n, "coins": net, "tax": tax, "xp": xp, "skill": sk, "workplace": wp,
            "skipped": skipped}


def message(result):
    from content import SKILL_DISPLAY_NAMES
    name = WORKPLACES[result["workplace"]][0]
    sk = SKILL_DISPLAY_NAMES.get(result["skill"], result["skill"].title())
    return (f"You worked {result['shifts']} shifts at the {name}: "
            f"+{result['coins']} coins, +{result['xp']} {sk} XP.")


def status(conn, player_id, now=None):
    c = active(conn, player_id)
    if not c:
        return None
    return {"workplace": WORKPLACES[c["workplace"]][0], "today": shifts_today(conn, player_id, now),
            "cap": DAILY_SHIFT_CAP, "last_wages": int(c["last_wages"] or 0),
            "at_player_property": bool(c["property_id"])}
