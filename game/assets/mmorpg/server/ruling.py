"""Crownfall phase 8: ruling. Every number lives here; read through functions.

Stored realm settings (tax rates), treasury spending under a daily cap, bounties, public
works, the royal council, Days on the Throne and the old King's later states.
The monarch can never move treasury gold into their own bank: there is no such action.
"""
from __future__ import annotations

import time

DAY = 86400

# key -> (default, min, max, max change per edit or None)
SETTINGS = {
    "sales_tax": (0.05, 0.02, 0.10, 0.02),
    "land_fee_house": (500, 250, 1_000, None),
    "land_fee_plot": (150, 75, 300, None),
    "land_fee_farm": (300, 150, 600, None),
    "land_fee_workshop": (450, 225, 900, None),
}
# Old defaults moved by the balance pass. Rows still at the old default and never edited by a monarch
# are migrated once on start; a value a monarch chose is left alone (and clamped into the new bounds).
MIGRATED_DEFAULTS = {"land_fee_farm": (400, 300), "land_fee_workshop": (600, 450)}
SETTING_COOLDOWN = DAY
REP_TAX_RAISE = -10
REP_TAX_CUT = 10

DAILY_CAP_FRACTION = 0.20
DAILY_CAP_MAX = 250_000
CHANCELLOR_CAP_FRACTION = 0.50

# key -> (name, cost)
PUBLIC_WORKS = {
    "roads": ("Repair the roads", 50_000),
    "feast": ("Feast for the people", 30_000),
    "markets": ("Stock the markets", 40_000),
}
WORK_DAYS = 7
ROADS_APPRENTICE_XP_BONUS = 0.10     # there are no teleport fees, so roads boost apprentice XP
FEAST_REP = 5
MARKETS_EXTRA_DISCOUNT = 0.01

BOUNTY_MIN = 1_000
BOUNTY_MAX = 20_000
BOUNTY_MAX_ACTIVE = 3

# post -> stipend per day
POSTS = {"Chancellor": 2_000, "Marshal": 1_500, "Steward": 1_500, "Royal Herald": 500}
COUNCIL_REP_PER_DAY = 3
HERALD_MAX_CHARS = 120

CONSORT_DISCOUNT = 0.02
CONSORT_WORKER_SLOTS = 1

FREE_KING_COST = 25_000
RECALL_KING_COST = 50_000
COUNSEL_XP = 150
NPC_KING_NAME = "King of Crownfall"

KING_VISIT_LINES = (
    "So you sit my throne. Come speak with me again when you've learned what it costs.",
    "You came back. The walls here are honest, at least. Nobody bows to a prisoner.",
    "Every crown is heavier than it looks. Ask your treasurer.",
)
KING_REIGN_LINES = (
    (7, "A new reign, barely a week old. The people are still deciding whether to love you."),
    (30, "Weeks on the throne now. You'll have learned that every tax has a face."),
    (10**9, "A long reign. Perhaps you understand me better than you'd like."),
)
ADVISOR_TIPS = (
    "Sales tax and land fees fill the treasury; raise them and the people remember.",
    "Standing opens doors: Respected folk pay less, Revered folk pay least.",
    "Apprentices earn while you sleep, but working the craft yourself teaches more.",
    "A farm or workshop with hired hands pays its way, if your bank can cover the wages.",
    "A guild needs twenty for the Royal Challenge, and at least twelve of them real.",
    "The Chamberlain grants rank to those with manners, means and a property to their name.",
    "Bounties and public works come out of the treasury, never out of the monarch's purse.",
)


# ---- schema ---------------------------------------------------------------------
def ensure_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS realm_settings (key TEXT PRIMARY KEY, value REAL, changed_at REAL, "
                 "changed_by INTEGER)")
    for key, (default, *_r) in SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO realm_settings (key, value, changed_at, changed_by) VALUES (?, ?, NULL, NULL)",
                     (key, default))
    for key, (old, new) in MIGRATED_DEFAULTS.items():
        conn.execute("UPDATE realm_settings SET value = ? WHERE key = ? AND value = ? AND changed_at IS NULL",
                     (new, key, old))
        _d, lo, hi, _step = SETTINGS[key]
        conn.execute("UPDATE realm_settings SET value = MAX(?, MIN(?, value)) WHERE key = ?", (lo, hi, key))
    for key, (old, new) in MIGRATED_DEFAULTS.items():
        conn.execute("UPDATE realm_settings SET value = ? WHERE key = ? AND value = ? AND changed_at IS NULL",
                     (new, key, old))
        _d, lo, hi, _step = SETTINGS[key]
        conn.execute("UPDATE realm_settings SET value = MAX(?, MIN(?, value)) WHERE key = ?", (lo, hi, key))
    for key, (old, new) in MIGRATED_DEFAULTS.items():
        conn.execute("UPDATE realm_settings SET value = ? WHERE key = ? AND value = ? AND changed_at IS NULL",
                     (new, key, old))
        _d, lo, hi, _step = SETTINGS[key]
        conn.execute("UPDATE realm_settings SET value = MAX(?, MIN(?, value)) WHERE key = ?", (lo, hi, key))
    for key, (old, new) in MIGRATED_DEFAULTS.items():
        conn.execute("UPDATE realm_settings SET value = ? WHERE key = ? AND value = ? AND changed_at IS NULL",
                     (new, key, old))
        _d, lo, hi, _step = SETTINGS[key]
        conn.execute("UPDATE realm_settings SET value = MAX(?, MIN(?, value)) WHERE key = ?", (lo, hi, key))
    for key, (old, new) in MIGRATED_DEFAULTS.items():
        conn.execute("UPDATE realm_settings SET value = ? WHERE key = ? AND value = ? AND changed_at IS NULL",
                     (new, key, old))
        _d, lo, hi, _step = SETTINGS[key]
        conn.execute("UPDATE realm_settings SET value = MAX(?, MIN(?, value)) WHERE key = ?", (lo, hi, key))
    conn.execute("CREATE TABLE IF NOT EXISTS royal_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
                 "actor_id INTEGER, post TEXT, action TEXT, amount INTEGER, detail TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS council (post TEXT PRIMARY KEY, player_id INTEGER, appointed_at REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS bounties (id INTEGER PRIMARY KEY AUTOINCREMENT, monster_type TEXT, "
                 "amount INTEGER, posted_by INTEGER, posted_at REAL, status TEXT, winner_id INTEGER NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS public_works (key TEXT PRIMARY KEY, funded_at REAL, expires_at REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS treasury_daily (day TEXT PRIMARY KEY, start_balance INTEGER, "
                 "spent INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS reigns (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER NULL, "
                 "name TEXT, title TEXT, path TEXT, guild_name TEXT NULL, started_at REAL, ended_at REAL NULL, "
                 "days INTEGER DEFAULT 0, end_reason TEXT NULL)")
    if conn.execute("SELECT COUNT(*) FROM reigns").fetchone()[0] == 0:
        since = time.time()
        try:
            row = conn.execute("SELECT since, monarch_kind FROM throne WHERE id = 1").fetchone()
            if row and row[1] == "npc" and row[0]:
                since = float(row[0])
        except Exception:
            pass
        conn.execute("INSERT INTO reigns (player_id, name, title, path, started_at) VALUES (NULL, ?, 'King', "
                     "'inheritance', ?)", (NPC_KING_NAME, since))
    conn.commit()
    import royal_treasury
    royal_treasury.bind_settings(conn)


def _news(conn, text, now=None, kind="decree"):
    try:
        import politics
        politics.news(conn, kind, text, now)
    except Exception:
        pass


def _day(now):
    return time.strftime("%Y-%m-%d", time.localtime(now))


def audit(conn, actor, post, action, amount, detail="", now=None):
    conn.execute("INSERT INTO royal_audit (ts, actor_id, post, action, amount, detail) VALUES (?, ?, ?, ?, ?, ?)",
                 (time.time() if now is None else now, actor, post, action, int(amount), detail))


# ---- settings ------------------------------------------------------------------------
def get_setting(conn, key):
    try:
        row = conn.execute("SELECT value FROM realm_settings WHERE key = ?", (key,)).fetchone()
    except Exception:
        row = None
    return SETTINGS[key][0] if row is None or row[0] is None else row[0]


def pending_setting(conn, key):
    row = conn.execute("SELECT value, changed_at FROM realm_settings WHERE key = ?", ("pending:" + key,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def role(conn, player_id):
    """'Monarch', a council post name, or None."""
    try:
        row = conn.execute("SELECT monarch_kind, monarch_player_id FROM throne WHERE id = 1").fetchone()
    except Exception:
        row = None
    if row and row[0] == "player" and row[1] is not None and int(row[1]) == int(player_id):
        return "Monarch"
    p = conn.execute("SELECT post FROM council WHERE player_id = ?", (player_id,)).fetchone()
    return p[0] if p else None


def set_tax(conn, actor, key, value, now=None):
    """Queue a rate change for the next daily tick. Returns (ok, message)."""
    now = time.time() if now is None else float(now)
    r = role(conn, actor)
    if key not in SETTINGS:
        return False, "Unknown setting."
    if r != "Monarch" and not (r == "Steward" and key.startswith("land_fee_")):
        return False, "You have no authority over that."
    default, lo, hi, step = SETTINGS[key]
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False, "Not a number."
    if key == "sales_tax" and value > 1:
        value = value / 100.0
    if not (lo - 1e-9 <= value <= hi + 1e-9):
        return False, f"Out of bounds ({_fmt(key, lo)}–{_fmt(key, hi)})."
    cur = float(get_setting(conn, key))
    if step is not None and abs(value - cur) > step + 1e-9:
        return False, f"At most {_fmt(key, step)} per change."
    row = conn.execute("SELECT changed_at FROM realm_settings WHERE key = ?", (key,)).fetchone()
    pend = pending_setting(conn, key)
    last = max([float(x) for x in (row[0] if row else None, pend[1]) if x is not None] or [0.0])
    if now - last < SETTING_COOLDOWN:
        return False, "That rate was changed in the last 24 hours."
    if abs(value - cur) < 1e-9:
        return False, "That is already the rate."
    conn.execute("INSERT OR REPLACE INTO realm_settings (key, value, changed_at, changed_by) VALUES (?, ?, ?, ?)",
                 ("pending:" + key, value, now, actor))
    audit(conn, actor, r, "set_tax", 0, f"{key} {cur} -> {value}", now)
    conn.commit()
    return True, value


def _fmt(key, v):
    return f"{round(float(v) * 100)}%" if key == "sales_tax" else f"{int(v):,}"


def setting_label(key):
    return {"sales_tax": "the sales tax", "land_fee_house": "the house land fee", "land_fee_plot": "the plot land fee",
            "land_fee_farm": "the farm land fee", "land_fee_workshop": "the workshop land fee"}[key]


def apply_pending(conn, now):
    """Daily tick: pending rates take effect. Returns [(key, old, new, actor)]."""
    out = []
    for key in SETTINGS:
        val, ts = pending_setting(conn, "" + key)
        if val is None:
            continue
        old = float(get_setting(conn, key))
        actor = conn.execute("SELECT changed_by FROM realm_settings WHERE key = ?", ("pending:" + key,)).fetchone()[0]
        conn.execute("UPDATE realm_settings SET value = ?, changed_at = ?, changed_by = ? WHERE key = ?",
                     (val, ts, actor, key))
        conn.execute("DELETE FROM realm_settings WHERE key = ?", ("pending:" + key,))
        out.append((key, old, float(val), actor))
    conn.commit()
    return out


# ---- treasury spending -------------------------------------------------------------------
def reserved(conn):
    return int(conn.execute("SELECT COALESCE(SUM(amount), 0) FROM bounties WHERE status = 'active'").fetchone()[0])


def _snapshot(conn, now):
    import royal_treasury
    day = _day(now)
    conn.execute("INSERT OR IGNORE INTO treasury_daily (day, start_balance, spent) VALUES (?, ?, 0)",
                 (day, royal_treasury.balance(conn)))
    row = conn.execute("SELECT start_balance, spent FROM treasury_daily WHERE day = ?", (day,)).fetchone()
    return int(row[0]), int(row[1])


def daily_cap(conn, now=None):
    now = time.time() if now is None else now
    start, _spent = _snapshot(conn, now)
    return min(int(start * DAILY_CAP_FRACTION), DAILY_CAP_MAX)


def spent_today(conn, now=None):
    return _snapshot(conn, time.time() if now is None else now)[1]


def spendable(conn):
    import royal_treasury
    return max(0, royal_treasury.balance(conn) - reserved(conn))


def can_spend(conn, actor, post, amount, kind, now=None):
    now = time.time() if now is None else now
    r = role(conn, actor)
    allowed = {"work": ("Monarch", "Chancellor"), "bounty": ("Monarch", "Marshal"),
               "king": ("Monarch",), "event": ("Monarch", "Chancellor")}.get(kind, ())
    if r not in allowed:
        return False, "You have no authority to spend on that."
    amount = int(amount)
    cap = daily_cap(conn, now)
    if spent_today(conn, now) + amount > cap:
        return False, f"That passes today's spending cap ({cap:,})."
    if r == "Chancellor":
        mine = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM royal_audit WHERE actor_id = ? AND post = "
                            "'Chancellor' AND ts >= ? AND action LIKE 'spend:%'", (actor, now - (now % DAY))).fetchone()[0]
        if int(mine) + amount > int(cap * CHANCELLOR_CAP_FRACTION):
            return False, "The Chancellor may spend at most half of today's cap."
    if amount > spendable(conn):
        return False, "The treasury can't cover that."
    return True, r


def spend(conn, actor, kind, amount, detail, now=None, reserve_only=False):
    """Atomic spend: treasury debit + ledger + audit + daily total. Returns (ok, message)."""
    import royal_treasury
    now = time.time() if now is None else now
    ok, r = can_spend(conn, actor, None, amount, kind, now)
    if not ok:
        return False, r
    if not reserve_only and not royal_treasury.debit(conn, f"spend_{kind}", actor, amount):
        return False, "The treasury can't cover that."
    conn.execute("UPDATE treasury_daily SET spent = spent + ? WHERE day = ?", (int(amount), _day(now)))
    audit(conn, actor, r, f"spend:{kind}", amount, detail, now)
    conn.commit()
    return True, r


def fund_work(conn, actor, key, now=None):
    now = time.time() if now is None else now
    if key not in PUBLIC_WORKS:
        return False, "Unknown work."
    if work_active(conn, key, now):
        return False, "That work is still in effect."
    name, cost = PUBLIC_WORKS[key]
    ok, msg = spend(conn, actor, "work", cost, key, now)
    if not ok:
        return False, msg
    conn.execute("INSERT OR REPLACE INTO public_works (key, funded_at, expires_at) VALUES (?, ?, ?)",
                 (key, now, now + WORK_DAYS * DAY))
    conn.commit()
    _news(conn, f"By royal decree: {name.lower()} ({cost:,}), for {WORK_DAYS} days.", now)
    return True, f"{name} funded ({cost:,}) for {WORK_DAYS} days."


def work_active(conn, key, now=None):
    now = time.time() if now is None else now
    try:
        row = conn.execute("SELECT expires_at FROM public_works WHERE key = ?", (key,)).fetchone()
    except Exception:
        return False
    return bool(row and row[0] and float(row[0]) > now)


def post_bounty(conn, actor, monster_type, amount, monsters, now=None):
    now = time.time() if now is None else now
    if monster_type not in monsters:
        return False, "No such creature."
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return False, "Not a number."
    if not BOUNTY_MIN <= amount <= BOUNTY_MAX:
        return False, f"Bounties are {BOUNTY_MIN:,}–{BOUNTY_MAX:,}."
    if conn.execute("SELECT COUNT(*) FROM bounties WHERE status = 'active'").fetchone()[0] >= BOUNTY_MAX_ACTIVE:
        return False, f"At most {BOUNTY_MAX_ACTIVE} bounties at once."
    ok, msg = spend(conn, actor, "bounty", amount, monster_type, now, reserve_only=True)
    if not ok:
        return False, msg
    conn.execute("INSERT INTO bounties (monster_type, amount, posted_by, posted_at, status) VALUES (?, ?, ?, ?, 'active')",
                 (monster_type, amount, actor, now))
    conn.commit()
    _news(conn, f"By royal decree, a bounty of {amount:,} is posted on the {monster_type.replace('_', ' ')}.", now)
    return True, f"Bounty posted: {amount:,} for a {monster_type.replace('_', ' ')}."


def cancel_bounty(conn, actor, bounty_id, now=None):
    r = role(conn, actor)
    if r not in ("Monarch", "Marshal"):
        return False, "You have no authority over bounties."
    cur = conn.execute("UPDATE bounties SET status = 'cancelled' WHERE id = ? AND status = 'active'", (int(bounty_id),))
    audit(conn, actor, r, "cancel_bounty", 0, str(bounty_id), now)
    conn.commit()
    return (True, "Bounty cancelled.") if cur.rowcount else (False, "No such active bounty.")


def claim_bounty(conn, monster_type, killer_id, now=None):
    """First kill pays the reserved amount into the killer's bank. Returns amount or 0."""
    import apprentice
    import royal_treasury
    try:
        row = conn.execute("SELECT id, amount FROM bounties WHERE status = 'active' AND monster_type = ? "
                           "ORDER BY id LIMIT 1", (monster_type,)).fetchone()
    except Exception:
        return 0
    if not row:
        return 0
    bid, amount = row
    cur = conn.execute("UPDATE bounties SET status = 'claimed', winner_id = ? WHERE id = ? AND status = 'active'",
                       (killer_id, bid))
    if cur.rowcount != 1 or not royal_treasury.debit(conn, "bounty_paid", killer_id, amount):
        conn.rollback()
        return 0
    apprentice.bank_add(conn, killer_id, amount)
    audit(conn, killer_id, None, "bounty_paid", amount, monster_type, now)
    conn.commit()
    return int(amount)


# ---- council -------------------------------------------------------------------------------
def appoint(conn, actor, post, player_id, now=None):
    now = time.time() if now is None else now
    if role(conn, actor) != "Monarch":
        return False, "Only the monarch appoints the council."
    if post not in POSTS:
        return False, "Posts: " + ", ".join(POSTS) + "."
    if int(player_id) == int(actor):
        return False, "The monarch can't hold a council post."
    rank = conn.execute("SELECT noble_rank FROM players WHERE id = ?", (player_id,)).fetchone()
    if not rank or int(rank[0] or 0) < 1:
        return False, "Council members must hold a noble rank."
    if conn.execute("SELECT post FROM council WHERE player_id = ? AND post != ?", (player_id, post)).fetchone():
        return False, "They already hold another post."
    conn.execute("INSERT OR REPLACE INTO council (post, player_id, appointed_at) VALUES (?, ?, ?)",
                 (post, player_id, now))
    audit(conn, actor, "Monarch", "appoint", 0, f"{post}:{player_id}", now)
    conn.commit()
    return True, f"Appointed {post}."


def dismiss(conn, actor, post, now=None):
    if role(conn, actor) != "Monarch":
        return False, "Only the monarch dismisses the council."
    cur = conn.execute("DELETE FROM council WHERE post = ?", (post,))
    audit(conn, actor, "Monarch", "dismiss", 0, post, now)
    conn.commit()
    return (True, f"{post} dismissed.") if cur.rowcount else (False, "That post is empty.")


def herald_announce(conn, actor, text, now=None):
    import reputation
    now = time.time() if now is None else now
    if role(conn, actor) != "Royal Herald":
        return False, "Only the Royal Herald may proclaim."
    text = " ".join((text or "").split())[:HERALD_MAX_CHARS]
    if not text:
        return False, "Say something."
    if reputation.daily_take(conn, actor, "herald_announce", 1, 1, now) != 1:
        return False, "One proclamation a day."
    audit(conn, actor, "Royal Herald", "announce", 0, text, now)
    conn.commit()
    return True, text


def pay_stipends(conn, now=None):
    """Daily: stipends from the treasury, skipped (not owed) when short. Not counted in the cap."""
    import apprentice
    import reputation
    import royal_treasury
    now = time.time() if now is None else now
    paid, skipped = [], []
    for post, pid in conn.execute("SELECT post, player_id FROM council").fetchall():
        amt = POSTS.get(post, 0)
        if amt and royal_treasury.debit(conn, "council_stipend", pid, amt):
            apprentice.bank_add(conn, pid, amt)
            audit(conn, None, post, "stipend", amt, str(pid), now)
            paid.append((post, pid, amt))
        else:
            skipped.append((post, pid))
        got = reputation.daily_take(conn, pid, "council_rep", COUNCIL_REP_PER_DAY, COUNCIL_REP_PER_DAY, now)
        if got:
            conn.execute("UPDATE players SET reputation = MAX(-1000, MIN(1000, COALESCE(reputation, 0) + ?)) "
                         "WHERE id = ?", (got, pid))
    conn.commit()
    return paid, skipped


# ---- reigns ---------------------------------------------------------------------------------------
def current_reign(conn):
    row = conn.execute("SELECT id, player_id, name, title, path, guild_name, started_at, days FROM reigns "
                       "WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return dict(zip(("id", "player_id", "name", "title", "path", "guild_name", "started_at", "days"), row))


def update_days(conn, now=None):
    now = time.time() if now is None else now
    r = current_reign(conn)
    if r:
        conn.execute("UPDATE reigns SET days = ? WHERE id = ?", (int((now - float(r["started_at"])) // DAY), r["id"]))
        conn.commit()


def on_throne_change(conn, player_id, name, title, path, guild_name, now=None, reason="overthrown"):
    """Close the current reign, open a new one, clear the council. Rates, bounties and works stay."""
    now = time.time() if now is None else now
    r = current_reign(conn)
    if r:
        conn.execute("UPDATE reigns SET ended_at = ?, days = ?, end_reason = ? WHERE id = ?",
                     (now, int((now - float(r["started_at"])) // DAY), reason, r["id"]))
    conn.execute("INSERT INTO reigns (player_id, name, title, path, guild_name, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (player_id, name, title, path, guild_name, now))
    conn.execute("DELETE FROM council")
    conn.commit()
    try:
        import politics
        politics.news(conn, "reign", f"A new reign begins: {title} {name}.", now)
    except Exception:
        pass


def reign_lines(conn, now=None):
    now = time.time() if now is None else now
    cur = current_reign(conn)
    lines = []
    if cur:
        live = int((now - float(cur["started_at"])) // DAY)
        lines.append(f"Now: {cur['title']} {cur['name']} · {live} days ({cur['path']})")
    top = conn.execute("SELECT title, name, days FROM reigns WHERE ended_at IS NOT NULL ORDER BY days DESC, id "
                       "LIMIT 10").fetchall()
    if top:
        lines.append("Longest: " + " · ".join(f"{t} {n} {d}d" for t, n, d in top))
    last = conn.execute("SELECT title, name, days, end_reason FROM reigns WHERE ended_at IS NOT NULL ORDER BY id DESC "
                        "LIMIT 5").fetchall()
    if last:
        lines.append("Recent: " + " · ".join(f"{t} {n} {d}d ({e})" for t, n, d, e in last))
    return lines


# ---- the old King ---------------------------------------------------------------------------------------
def free_king(conn, actor, now=None):
    return _king_to_freed(conn, actor, "imprisoned", FREE_KING_COST, now)


def recall_king(conn, actor, now=None):
    return _king_to_freed(conn, actor, "exiled", RECALL_KING_COST, now)


def _king_to_freed(conn, actor, need, cost, now):
    st = conn.execute("SELECT old_king_state FROM throne WHERE id = 1").fetchone()
    if not st or st[0] != need:
        return False, f"The old King is not {need}."
    ok, msg = spend(conn, actor, "king", cost, f"old king {need}->freed", now)
    if not ok:
        return False, msg
    conn.execute("UPDATE throne SET old_king_state = 'freed' WHERE id = 1")
    conn.commit()
    _news(conn, "By royal decree, the old King is set free.", now)
    return True, "The old King is free, and will serve as Royal Advisor."


def king_visit_line(conn, player_id, now=None):
    key = f"king_visits:{player_id}"
    row = conn.execute("SELECT value FROM realm_settings WHERE key = ?", (key,)).fetchone()
    n = int(row[0]) if row else 0
    conn.execute("INSERT OR REPLACE INTO realm_settings (key, value, changed_at) VALUES (?, ?, ?)",
                 (key, n + 1, time.time() if now is None else now))
    conn.commit()
    lines = [KING_VISIT_LINES[n % len(KING_VISIT_LINES)]]
    cur = current_reign(conn)
    if cur and cur["player_id"] is not None:
        days = int(((time.time() if now is None else now) - float(cur["started_at"])) // DAY)
        lines.append(next(text for limit, text in KING_REIGN_LINES if days < limit))
    return lines


def counsel(conn, player_id, now=None):
    import reputation
    return reputation.daily_take(conn, player_id, "aldous_counsel", COUNSEL_XP, COUNSEL_XP, now)


# ---- consort ---------------------------------------------------------------------------------------------
def is_consort(royal_title):
    return bool(royal_title) and str(royal_title).endswith("Consort")


def consort_discount(royal_title):
    return CONSORT_DISCOUNT if is_consort(royal_title) else 0.0


def state_payload(conn, actor, now=None, monsters=None):
    import royal_treasury
    now = time.time() if now is None else now
    r = role(conn, actor)
    st = conn.execute("SELECT old_king_state FROM throne WHERE id = 1").fetchone()
    settings = {}
    for key, (d, lo, hi, step) in SETTINGS.items():
        pend, ts = pending_setting(conn, key)
        row = conn.execute("SELECT changed_at FROM realm_settings WHERE key = ?", (key,)).fetchone()
        last = max([float(x) for x in (row[0] if row else None, ts) if x is not None] or [0.0])
        settings[key] = {"value": get_setting(conn, key), "min": lo, "max": hi, "step": step, "pending": pend,
                         "cooldown": max(0, int(SETTING_COOLDOWN - (now - last))), "label": setting_label(key)}
    return {
        "role": r,
        "balance": royal_treasury.balance(conn),
        "spent": spent_today(conn, now),
        "cap": daily_cap(conn, now),
        "reserved": reserved(conn),
        "settings": settings,
        "works": {k: {"name": n, "cost": c, "active": work_active(conn, k, now)} for k, (n, c) in PUBLIC_WORKS.items()},
        "bounties": [dict(zip(("id", "monster", "amount"), b)) for b in conn.execute(
            "SELECT id, monster_type, amount FROM bounties WHERE status = 'active' ORDER BY id")],
        "council": {p: pid for p, pid in conn.execute("SELECT post, player_id FROM council")},
        "audit": [list(a) for a in conn.execute(
            "SELECT ts, post, action, amount, detail FROM royal_audit ORDER BY id DESC LIMIT 20")],
        "old_king": st[0] if st else "reigning",
    }
