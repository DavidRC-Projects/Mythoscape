"""Crownfall phase 4: plots, farms and workshops. Every number lives here.

Bought and upgraded from the bank (never negative, never taxed). Daily land fee per
kind through the Phase 2 land-fee maths. NPC workers earn passive income.
"""
from __future__ import annotations

import time

import apprentice
import royal_treasury

# kind -> (name, price, worker slots, upgrade-from-plot cost). Land fees are stored realm
# settings (ruling.SETTINGS land_fee_<kind>), read through royal_treasury.land_fee_daily(kind).
KINDS = {
    "plot": ("Plot", 25_000, 0, None),
    "farm": ("Farm", 120_000, 2, 95_000),
    "workshop": ("Workshop", 200_000, 3, 175_000),
}
WORKER_HIRE_FEE = 2_000
WORKER_WAGE = 30
WORKER_VALUE = 110
SHIFT_SECONDS = apprentice.SHIFT_SECONDS
WORKER_DAILY_CAP = 8
BACKLOG_DAYS = 3
# property kind -> apprentice workplace for players working there
WORKPLACE_FOR = {"farm": "farm", "workshop": "workshop"}

# Four plot sites on the grass between the office and the King's Row lanes.
SITES = {
    "kings_row_plot_1": (15, 99),
    "kings_row_plot_2": (20, 99),
    "kings_row_plot_3": (15, 104),
    "kings_row_plot_4": (20, 104),
}

OFFICE_OPTIONS = [
    {"id": "prop_buy", "label": "Buy plot"},
    {"id": "prop_farm", "label": "Upgrade to farm"},
    {"id": "prop_workshop", "label": "Upgrade to workshop"},
    {"id": "prop_hire", "label": "Hire worker"},
    {"id": "prop_dismiss", "label": "Dismiss worker"},
    {"id": "prop_mine", "label": "My property"},
    {"id": "prop_work", "label": "Work at a player's property"},
]


def kind_name(kind):
    return KINDS[kind][0]


def price(kind):
    return KINDS[kind][1]


def land_fee(kind):
    return royal_treasury.land_fee_daily(kind)


def slots(kind, owner_id=None, conn=None):
    """Base worker slots, plus the owner's noble-rank bonus when owner and conn are given."""
    base = KINDS[kind][2]
    if base and owner_id is not None and conn is not None:
        import nobility
        import ruling
        base += nobility.extra_worker_slots(nobility.rank_of(conn, owner_id))
        try:
            row = conn.execute("SELECT royal_title FROM players WHERE id = ?", (owner_id,)).fetchone()
        except Exception:
            row = None
        if row and ruling.is_consort(row[0]):
            base += ruling.CONSORT_WORKER_SLOTS
    return base


def upgrade_cost(kind):
    return KINDS[kind][3]


def income_tax(amount):
    """Income tax follows the stored sales tax (rounded down)."""
    return int(max(0, int(amount)) * royal_treasury.sales_tax_rate())


def ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, kind TEXT, site_key TEXT UNIQUE,
            bought_at REAL, land_fee_paid_through REAL, last_income_settled REAL)"""
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(properties)")}
    if "last_income" not in cols:
        conn.execute("ALTER TABLE properties ADD COLUMN last_income INTEGER NOT NULL DEFAULT 0")
    if "unpaid_shifts" not in cols:
        conn.execute("ALTER TABLE properties ADD COLUMN unpaid_shifts INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS property_workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, property_id INTEGER, worker_kind TEXT, hired_at REAL)"""
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(property_workers)")}
    if "last_settled" not in cols:
        conn.execute("ALTER TABLE property_workers ADD COLUMN last_settled REAL")
    conn.commit()


def stamp(grid, wm):
    """A small path square around each plot sign, on grass only."""
    for x, y in SITES.values():
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < len(grid) and 0 <= xx < len(grid[0]) and grid[yy][xx] == wm.GRASS:
                    grid[yy][xx] = wm.PATH


# ---- queries ----------------------------------------------------------------
def owned(conn, owner_id):
    row = conn.execute(
        "SELECT id, kind, site_key, land_fee_paid_through, last_income, unpaid_shifts "
        "FROM properties WHERE owner_id = ?", (owner_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(("id", "kind", "site_key", "land_fee_paid_through", "last_income", "unpaid_shifts"), row))


def owner_of(conn, property_id):
    row = conn.execute("SELECT owner_id FROM properties WHERE id = ?", (property_id,)).fetchone()
    return int(row[0]) if row else None


def npc_workers(conn, property_id):
    return conn.execute(
        "SELECT id, hired_at, last_settled FROM property_workers WHERE property_id = ? AND worker_kind = 'npc' "
        "ORDER BY id", (property_id,),
    ).fetchall()


def player_workers(conn, property_id):
    return conn.execute(
        "SELECT COUNT(*) FROM apprentice_contracts WHERE property_id = ? AND master_id IS NOT NULL", (property_id,),
    ).fetchone()[0]


def used_slots(conn, property_id):
    return len(npc_workers(conn, property_id)) + int(player_workers(conn, property_id))


def credit_owner(conn, owner_id, amount):
    """Owner income from a worker shift, minus 5% property_income_tax. Returns net."""
    tax = income_tax(amount)
    net = int(amount) - tax
    if net:
        apprentice.bank_add(conn, owner_id, net)
    if tax:
        royal_treasury.credit(conn, "property_income_tax", owner_id, tax)
    return net


def note_unpaid(conn, property_id, n):
    conn.execute("UPDATE properties SET unpaid_shifts = unpaid_shifts + ? WHERE id = ?", (int(n), property_id))
    conn.commit()


# ---- actions (all return (ok, message)) -------------------------------------
def buy_plot(conn, owner_id, now=None):
    now = time.time() if now is None else float(now)
    if owned(conn, owner_id):
        return False, "You already own a property. One each for now."
    taken = {r[0] for r in conn.execute("SELECT site_key FROM properties")}
    free = [k for k in SITES if k not in taken]
    if not free:
        return False, "Every plot on King's Row is sold."
    cost = price("plot")
    if apprentice.bank_get(conn, owner_id) < cost:
        return False, f"A plot costs {cost:,} gold from your bank."
    apprentice.bank_add(conn, owner_id, -cost)
    conn.execute(
        "INSERT INTO properties (owner_id, kind, site_key, bought_at, land_fee_paid_through, last_income_settled) "
        "VALUES (?, 'plot', ?, ?, ?, ?)", (owner_id, free[0], now, now, now),
    )
    conn.commit()
    return True, f"You buy {free[0].replace('_', ' ').title()} for {cost:,} gold. Daily land fee: {land_fee('plot')}."


def upgrade(conn, owner_id, kind):
    p = owned(conn, owner_id)
    if not p:
        return False, "You need a plot first."
    if p["kind"] != "plot":
        return False, f"Your {kind_name(p['kind']).lower()} is already built."
    cost = upgrade_cost(kind)
    if apprentice.bank_get(conn, owner_id) < cost:
        return False, f"Building a {kind_name(kind).lower()} costs {cost:,} gold from your bank."
    apprentice.bank_add(conn, owner_id, -cost)
    conn.execute("UPDATE properties SET kind = ? WHERE id = ?", (kind, p["id"]))
    conn.commit()
    return True, (f"Your plot is now a {kind_name(kind).lower()} ({cost:,} gold). "
                  f"Land fee {land_fee(kind)} a day, {slots(kind)} worker slots.")


def hire(conn, owner_id, now=None):
    now = time.time() if now is None else float(now)
    p = owned(conn, owner_id)
    if not p or slots(p["kind"]) == 0:
        return False, "Only a farm or workshop can take workers."
    if used_slots(conn, p["id"]) >= slots(p["kind"], owner_id, conn):
        return False, "Every worker slot is full."
    if apprentice.bank_get(conn, owner_id) < WORKER_HIRE_FEE:
        return False, f"Hiring costs {WORKER_HIRE_FEE:,} gold from your bank."
    apprentice.bank_add(conn, owner_id, -WORKER_HIRE_FEE)
    conn.execute(
        "INSERT INTO property_workers (property_id, worker_kind, hired_at, last_settled) VALUES (?, 'npc', ?, ?)",
        (p["id"], now, now),
    )
    conn.commit()
    return True, (f"A worker joins your {kind_name(p['kind']).lower()} ({WORKER_HIRE_FEE:,} gold). "
                  f"They take {WORKER_WAGE} a shift and make {WORKER_VALUE}.")


def dismiss(conn, owner_id):
    p = owned(conn, owner_id)
    rows = npc_workers(conn, p["id"]) if p else []
    if not rows:
        return False, "You have no hired workers."
    conn.execute("DELETE FROM property_workers WHERE id = ?", (rows[-1][0],))
    conn.commit()
    return True, "You let a worker go."


def find_workplace(conn, player_id):
    """A farm or workshop owned by someone else with a free slot."""
    for pid_, owner, kind in conn.execute(
            "SELECT id, owner_id, kind FROM properties WHERE kind IN ('farm', 'workshop') ORDER BY id"):
        if owner != player_id and used_slots(conn, pid_) < slots(kind, owner, conn):
            return pid_, owner, kind
    return None


# ---- settlement ---------------------------------------------------------------
def settle_income(conn, owner_id, now=None):
    """NPC worker shifts. Returns dict or None. Wages first, value and tax after."""
    import reputation
    now = time.time() if now is None else float(now)
    p = owned(conn, owner_id)
    if not p:
        return None
    workers = npc_workers(conn, p["id"])
    shifts = 0
    skipped = 0
    for wid, hired_at, last in workers:
        last = float(last or hired_at or now)
        used = {}
        key = f"prop_worker:{wid}"
        slots_, new_last = apprentice.due_slots(last, now, used)
        conn.execute("UPDATE property_workers SET last_settled = ? WHERE id = ?", (new_last, wid))
        for day in slots_:
            if reputation.daily_take(conn, owner_id, key, 1, WORKER_DAILY_CAP, now=_noon(day)) != 1:
                continue
            if apprentice.bank_get(conn, owner_id) < WORKER_WAGE:
                skipped += 1
                continue
            apprentice.bank_add(conn, owner_id, -WORKER_WAGE)
            shifts += 1
    conn.commit()
    unpaid = int(p["unpaid_shifts"] or 0)
    if shifts == 0 and skipped == 0 and unpaid == 0:
        return None
    import politics
    value = int(shifts * WORKER_VALUE * politics.shift_income_mult(conn))
    gross = value - shifts * WORKER_WAGE
    tax = income_tax(gross)
    net = gross - tax
    if value:
        apprentice.bank_add(conn, owner_id, value - tax)
    if tax:
        royal_treasury.credit(conn, "property_income_tax", owner_id, tax)
    conn.execute("UPDATE properties SET last_income_settled = ?, last_income = ?, unpaid_shifts = 0 WHERE id = ?",
                 (now, net if shifts else p["last_income"], p["id"]))
    conn.commit()
    return {"kind": p["kind"], "net": net, "shifts": shifts, "tax": tax, "skipped": skipped + unpaid}


def _noon(day):
    return time.mktime(time.strptime(day + " 12", "%Y-%m-%d %H"))


def income_message(r):
    return f"Your {kind_name(r['kind']).lower()} earned {r['net']} coins ({r['shifts']} shifts, {r['tax']} to the Crown)."


def settle_land_fee_rows(conn, owner_id, purse, bank, now=None):
    """Phase 2 land-fee maths per property kind. Returns (purse, bank, [(kind, paid, days)])."""
    now = time.time() if now is None else float(now)
    out = []
    p = owned(conn, owner_id)
    if not p:
        return purse, bank, out
    through = p["land_fee_paid_through"]
    if through is None:
        conn.execute("UPDATE properties SET land_fee_paid_through = ? WHERE id = ?", (now, p["id"]))
        conn.commit()
        return purse, bank, out
    fee = land_fee(p["kind"])
    paid, days, new_through, purse, bank = royal_treasury.land_fee_due(through, now, purse, bank, fee=fee)
    if days > 0:
        conn.execute("UPDATE properties SET land_fee_paid_through = ? WHERE id = ?", (new_through, p["id"]))
        if paid:
            royal_treasury.credit(conn, "land_fee", owner_id, paid * fee)
        out.append((p["kind"], paid, days))
    conn.commit()
    return purse, bank, out


def status(conn, owner_id):
    p = owned(conn, owner_id)
    if not p:
        return None
    return {"kind": kind_name(p["kind"]), "workers": used_slots(conn, p["id"]),
            "slots": slots(p["kind"], owner_id, conn),
            "fee": land_fee(p["kind"]), "last_income": int(p["last_income"] or 0),
            "site": p["site_key"]}


def describe(conn, owner_id):
    s = status(conn, owner_id)
    if not s:
        return ["You own no plot, farm or workshop. A plot costs 25,000 gold."]
    return [f"{s['kind']} at {s['site'].replace('_', ' ').title()}.",
            f"Workers {s['workers']}/{s['slots']} · land fee {s['fee']} a day · last income {s['last_income']}."]
