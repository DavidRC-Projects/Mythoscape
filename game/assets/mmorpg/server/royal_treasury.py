"""Royal treasury: every Crownfall tax rate lives here, plus the treasury balance.

Rates are stored in realm_settings (server/ruling.py holds the defaults and bounds);
read them through these functions.
"""
from __future__ import annotations

import math
import time

_SETTINGS_CONN = None
DAY_SECONDS = 86400
LAND_FEE_MAX_DAYS = 7     # long absences are capped, unpaid days are forgiven

SOURCES = ("sales_tax_buy", "sales_tax_sell", "land_fee", "house_lease", "castle_upkeep")


def ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS royal_treasury (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance INTEGER NOT NULL DEFAULT 0,
            updated_at REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS treasury_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            source TEXT,
            player_id INTEGER,
            amount INTEGER
        )"""
    )
    conn.execute("INSERT OR IGNORE INTO royal_treasury (id, balance, updated_at) VALUES (1, 0, ?)", (time.time(),))
    conn.commit()


def bind_settings(conn):
    """Point rate lookups at the live database (ruling.ensure_schema calls this)."""
    global _SETTINGS_CONN
    _SETTINGS_CONN = conn


def _setting(key):
    import ruling
    if _SETTINGS_CONN is None:
        return ruling.SETTINGS[key][0]
    return ruling.get_setting(_SETTINGS_CONN, key)


def sales_tax_rate():
    return float(_setting("sales_tax"))


def land_fee_daily(kind="house"):
    return int(_setting(f"land_fee_{kind}"))


def debit(conn, source, player_id, amount):
    """Atomic treasury spend: never below 0. Ledger row has a negative amount. True if paid."""
    amount = int(amount or 0)
    if amount <= 0:
        return False
    now = time.time()
    cur = conn.execute("UPDATE royal_treasury SET balance = balance - ?, updated_at = ? WHERE id = 1 AND balance >= ?",
                       (amount, now, amount))
    if cur.rowcount != 1:
        return False
    conn.execute("INSERT INTO treasury_ledger (ts, source, player_id, amount) VALUES (?, ?, ?, ?)",
                 (now, source, player_id, -amount))
    conn.commit()
    return True


def buy_tax(cost):
    """Tax added on top of a purchase: ceil(rate * cost), at least 1 when cost > 0."""
    cost = int(cost)
    if cost <= 0:
        return 0
    return max(1, int(math.ceil(cost * sales_tax_rate() - 1e-9)))


def sell_tax(value):
    """Tax taken from a sale: floor(rate * value)."""
    value = int(value)
    if value <= 0:
        return 0
    return int(math.floor(value * sales_tax_rate() + 1e-9))


def credit(conn, source, player_id, amount):
    amount = int(amount or 0)
    if amount <= 0:
        return
    if str(source).startswith("sales_tax"):
        try:
            import politics
            amount = int(round(amount * politics.sales_tax_mult(conn)))
        except Exception:
            pass
    now = time.time()
    with conn:
        conn.execute("INSERT OR IGNORE INTO royal_treasury (id, balance, updated_at) VALUES (1, 0, ?)", (now,))
        conn.execute("UPDATE royal_treasury SET balance = balance + ?, updated_at = ? WHERE id = 1", (amount, now))
        conn.execute(
            "INSERT INTO treasury_ledger (ts, source, player_id, amount) VALUES (?, ?, ?, ?)",
            (now, source, player_id, amount),
        )


def balance(conn):
    row = conn.execute("SELECT balance FROM royal_treasury WHERE id = 1").fetchone()
    return int(row[0]) if row else 0


def land_fee_due(paid_through, now, purse, bank, fee=None):
    """Pure land-fee maths for one house.

    Returns (days_paid, days_passed, new_paid_through, purse, bank). Each passed
    day (capped at LAND_FEE_MAX_DAYS for charging) is charged in full from bank
    then purse only if the player can cover the whole fee; unpaid days are
    forgiven. paid_through always moves forward by every whole day passed.
    """
    fee = land_fee_daily() if fee is None else int(fee)
    days = int((float(now) - float(paid_through)) // DAY_SECONDS)
    if days <= 0:
        return 0, 0, float(paid_through), int(purse), int(bank)
    purse, bank = int(purse), int(bank)
    paid = 0
    for _ in range(min(days, LAND_FEE_MAX_DAYS)):
        if purse + bank < fee:
            break
        from_bank = min(bank, fee)
        bank -= from_bank
        purse -= fee - from_bank
        paid += 1
    return paid, days, float(paid_through) + days * DAY_SECONDS, purse, bank
