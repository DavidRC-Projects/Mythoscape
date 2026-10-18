"""Crownfall reputation (standing) and social-skill tuning. All numbers live here."""
from __future__ import annotations

import time

REP_MIN, REP_MAX = -1000, 1000
TIERS = (  # (name, lowest score), highest first
    ("Revered", 800), ("Honoured", 400), ("Respected", 100),
    ("Neutral", -99), ("Distrusted", -499), ("Hated", REP_MIN),
)
REP_QUEST = 25
REP_TAX = 1
REP_TAX_DAILY_CAP = 10
REP_LAND_FEE_PAID = 3
REP_LAND_FEE_MISSED = -5
REP_WEEKLY_PAID = 10
REP_LEASE_MISSED = -25
REP_CRIME = -50
REP_HELP = 5

PRICE_MULT = {"Hated": 1.10, "Distrusted": 1.05, "Neutral": 1.0, "Respected": 0.98, "Honoured": 0.96, "Revered": 0.95}
SELL_MULT = {"Hated": 0.90, "Distrusted": 0.95, "Neutral": 1.0, "Respected": 1.02, "Honoured": 1.04, "Revered": 1.05}

CHARISMA_QUEST_XP = 300
CHARISMA_TALK_XP = 40
ETIQUETTE_FEE_XP = 300           # per land-fee day paid, each property (inside the daily cap)
ETIQUETTE_TAX_XP = 150           # per counted taxed trade (inside the daily cap)
MIN_TAX_FOR_STANDING = 5         # a trade counts for rep/Etiquette only if its tax is at least this
ETIQUETTE_FEE_DAILY_CAP = 2_500
ETIQUETTE_WEEKLY_XP = 1_500

GREETINGS = {
    "Hated": "Guards! ...No? Then be quick.",
    "Distrusted": "I've heard things about you.",
    "Respected": "Good to see you, friend.",
    "Honoured": "An honour, truly.",
    "Revered": "The whole kingdom speaks well of you.",
}


def ensure_schema(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)")}
    for col in ("reputation", "charisma_xp", "etiquette_xp"):
        if cols and col not in cols:
            conn.execute(f"ALTER TABLE players ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rep_town (player_id INTEGER, town TEXT, score INTEGER DEFAULT 0, "
        "PRIMARY KEY(player_id, town))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rep_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "player_id INTEGER, source TEXT, delta INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS social_daily (player_id INTEGER, day TEXT, key TEXT, value INTEGER, "
        "PRIMARY KEY(player_id, day, key))"
    )
    conn.commit()


def tier(score):
    score = int(score or 0)
    for name, low in TIERS:
        if score >= low:
            return name
    return "Hated"


def clamp(score):
    return max(REP_MIN, min(REP_MAX, int(score)))


def adjust(conn, session, source, delta, town=None):
    """Change standing (clamped), save and log. Returns the new tier name if it changed, else None."""
    delta = int(delta or 0)
    if not delta:
        return None
    before = int(getattr(session, "reputation", 0) or 0)
    after = clamp(before + delta)
    session.reputation = after
    conn.execute("UPDATE players SET reputation = ? WHERE id = ?", (after, session.player_id))
    conn.execute(
        "INSERT INTO rep_log (ts, player_id, source, delta) VALUES (?, ?, ?, ?)",
        (time.time(), session.player_id, source, after - before),
    )
    if town:
        conn.execute(
            "INSERT INTO rep_town (player_id, town, score) VALUES (?, ?, ?) "
            "ON CONFLICT(player_id, town) DO UPDATE SET score = MAX(?, MIN(?, score + ?))",
            (session.player_id, town, clamp(delta), REP_MIN, REP_MAX, delta),
        )
    conn.commit()
    new_tier = tier(after)
    return new_tier if new_tier != tier(before) else None


def price_mult(score):
    return PRICE_MULT[tier(score)]


def sell_mult(score):
    return SELL_MULT[tier(score)]


MAX_TOTAL_DISCOUNT = 0.10   # standing × noble rank never beats −10%


def buy_price(base, score, noble_discount=0.0):
    base = int(base)
    if base <= 0:
        return 0
    mult = max(1.0 - MAX_TOTAL_DISCOUNT, price_mult(score) * (1.0 - float(noble_discount or 0)))
    return max(1, int(round(base * mult)))


def sell_value(base, score):
    base = int(base)
    if base <= 0:
        return 0
    return max(1, int(round(base * sell_mult(score))))


def greeting(score):
    return GREETINGS.get(tier(score))


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() if now is None else now))


def daily_take(conn, player_id, key, amount, cap, now=None):
    """How much of `amount` is still allowed today under `cap`; records it."""
    day = today(now)
    row = conn.execute(
        "SELECT value FROM social_daily WHERE player_id = ? AND day = ? AND key = ?", (player_id, day, key),
    ).fetchone()
    used = int(row[0]) if row else 0
    take = max(0, min(int(amount), int(cap) - used))
    if take:
        conn.execute(
            "INSERT INTO social_daily (player_id, day, key, value) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(player_id, day, key) DO UPDATE SET value = value + ?",
            (player_id, day, key, take, take),
        )
        conn.commit()
    return take


def first_talk_today(conn, player_id, npc_id, now=None):
    return daily_take(conn, player_id, f"talk:{npc_id}", 1, 1, now) == 1


async def social_event(world, send, session, source, rep=0, xp=None, rep_cap_key=None, rep_cap=None,
                       xp_cap_key=None, xp_cap=None):
    """One place for every standing / social-XP hook.

    rep: standing delta (optionally capped per day by rep_cap_key/rep_cap).
    xp: {"charisma": n, "etiquette": n} (optionally capped per day by xp_cap_key/xp_cap).
    Sends the Herald message on a tier change.
    """
    conn = world.db.conn
    if rep and rep_cap_key and rep > 0:
        rep = daily_take(conn, session.player_id, rep_cap_key, rep, rep_cap)
    for skill, amount in (xp or {}).items():
        if xp_cap_key:
            amount = daily_take(conn, session.player_id, f"{xp_cap_key}:{skill}", amount, xp_cap)
        if amount > 0:
            world.grant_xp(session, skill, amount)
    if rep:
        new_tier = adjust(conn, session, source, rep)
        if new_tier:
            await send(session.ws, "CHAT_MSG", **{
                "from": "Herald", "text": f"Your standing in Crownfall is now {new_tier}.",
            })
