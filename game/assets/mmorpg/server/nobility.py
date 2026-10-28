"""Crownfall phase 6: noble ranks. Every number lives here; read them through functions.

Noble rank (players.noble_rank) is separate from royal titles (players.royal_title, phase 7).
Rank never goes down.
"""
from __future__ import annotations

import time

import reputation
import royal_treasury

# rank -> (male, female)
NAMES = {
    0: ("Commoner", "Commoner"),
    1: ("Squire", "Gentlewoman"),
    2: ("Knight", "Dame"),
    3: ("Baron", "Baroness"),
    4: ("Count", "Countess"),
    5: ("Duke", "Duchess"),
}
# Prefix used before a name; Knight is "Sir" for men.
PREFIX = {
    1: ("Squire", "Gentlewoman"),
    2: ("Sir", "Dame"),
    3: ("Baron", "Baroness"),
    4: ("Count", "Countess"),
    5: ("Duke", "Duchess"),
}
MAX_RANK = 5
# rank -> (rep tier, etiquette, charisma, combat, property need, fee)
#   property need: None | "any" (house or any property) | "estate" (farm/workshop)
#   | "estate+house" | "estate+house+guild"
REQUIREMENTS = {
    1: ("Respected", 10, 5, 20, None, 5_000),
    2: ("Respected", 20, 15, 50, "any", 25_000),
    3: ("Honoured", 35, 30, 70, "estate", 100_000),
    4: ("Honoured", 50, 45, 85, "estate+house", 300_000),
    5: ("Revered", 65, 55, 100, "estate+house+guild", 1_000_000),
}
DUKE_GUILD_MIN_PLAYERS = 10
REFUSAL_COOLDOWN = 24 * 3600
# rank -> (shop discount, extra worker slots, extra guild recruit cap)
PERKS = {
    0: (0.00, 0, 0),
    1: (0.01, 0, 0),
    2: (0.02, 0, 0),
    3: (0.03, 1, 0),
    4: (0.04, 1, 1),
    5: (0.05, 2, 2),
}
MAX_TOTAL_DISCOUNT = 0.10
REP_PROMOTION = 10
ETIQUETTE_PROMOTION_XP = 2_000
BROADCAST_FROM_RANK = 4
# NPC address forms: rank -> (to a man, to a woman). Knight and above.
ADDRESS = {
    2: ("Sir.", "My lady."),
    3: ("My lord.", "My lady."),
    4: ("My lord.", "My lady."),
    5: ("Your Grace.", "Your Grace."),
}
PROPERTY_TEXT = {
    "any": "a house or any property",
    "estate": "a farm or workshop",
    "estate+house": "a farm or workshop and a house",
    "estate+house+guild": f"a farm or workshop, a house, and Leader/Officer of a {DUKE_GUILD_MIN_PLAYERS}+ player guild",
}


def _g(gender):
    return 1 if str(gender or "").lower() == "female" else 0


def rank_name(rank, gender):
    return NAMES.get(int(rank or 0), NAMES[0])[_g(gender)]


def prefix(rank, gender):
    p = PREFIX.get(int(rank or 0))
    return p[_g(gender)] if p else ""


def requirements(rank):
    return REQUIREMENTS.get(int(rank))


def fee(rank):
    return REQUIREMENTS[int(rank)][5]


def shop_discount(rank):
    return PERKS.get(int(rank or 0), PERKS[0])[0]


def extra_worker_slots(rank):
    return PERKS.get(int(rank or 0), PERKS[0])[1]


def extra_recruit_cap(rank):
    return PERKS.get(int(rank or 0), PERKS[0])[2]


def address(rank, gender):
    a = ADDRESS.get(int(rank or 0))
    return a[_g(gender)] if a else None


def title_prefix(rank, gender, royal_title=None):
    """Royal title wins over the noble one (Queen Elsa, not Queen Duchess Elsa)."""
    return royal_title or prefix(rank, gender)


def display_name(session):
    p = title_prefix(getattr(session, "noble_rank", 0), getattr(session, "gender", "male"),
                     getattr(session, "royal_title", None))
    name = getattr(session, "char_name", "") or ""
    full = f"{p} {name}" if p else name
    suf = getattr(session, "house_suffix", "") or ""
    if suf:
        full = f"{full} {suf}" if suf.startswith("of ") else f"{full}, {suf}"
    return full


def ensure_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
    if "noble_rank" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN noble_rank INTEGER DEFAULT 0")
    if "royal_title" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN royal_title TEXT NULL")
    if "last_petition_refused" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN last_petition_refused REAL NULL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS noble_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "player_id INTEGER, from_rank INTEGER, to_rank INTEGER, fee INTEGER)"
    )
    conn.commit()


def rank_of(conn, player_id):
    try:
        row = conn.execute("SELECT noble_rank FROM players WHERE id = ?", (int(player_id),)).fetchone()
    except Exception:
        return 0
    return int(row[0] or 0) if row else 0


def _owns_house(conn, pid):
    try:
        return conn.execute("SELECT 1 FROM housing_deeds WHERE owner_id = ?", (pid,)).fetchone() is not None
    except Exception:
        return False


def _owns(conn, pid, kinds):
    try:
        q = "SELECT 1 FROM properties WHERE owner_id = ? AND kind IN (%s)" % ",".join("?" * len(kinds))
        return conn.execute(q, (pid, *kinds)).fetchone() is not None
    except Exception:
        return False


def _guild_ok(conn, pid):
    try:
        row = conn.execute(
            "SELECT m.clan_id, m.rank, c.leader_id FROM clan_members m JOIN clans c ON c.clan_id = m.clan_id "
            "WHERE m.player_id = ?", (pid,)).fetchone()
        if not row:
            return False
        rank = "Leader" if int(row[2]) == pid else row[1]
        if rank not in ("Leader", "Officer"):
            return False
        n = conn.execute("SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (row[0],)).fetchone()[0]
        return int(n) >= DUKE_GUILD_MIN_PLAYERS
    except Exception:
        return False


def property_ok(conn, pid, need):
    if not need:
        return True
    estate = _owns(conn, pid, ("farm", "workshop"))
    house = _owns_house(conn, pid)
    if need == "any":
        return house or _owns(conn, pid, ("plot", "farm", "workshop"))
    if need == "estate":
        return estate
    if need == "estate+house":
        return estate and house
    return estate and house and _guild_ok(conn, pid)


def _lvl(session, skill):
    try:
        return int(session.level(skill)) if skill in session.xp else 1
    except Exception:
        return 1


def check_rows(session, conn):
    """[(label, ok)] for the next rank, or [] when already at the top."""
    nxt = int(getattr(session, "noble_rank", 0) or 0) + 1
    req = requirements(nxt)
    if not req:
        return []
    tier, et, ch, cb, need, cost = req
    order = [t for t, _ in reversed(reputation.TIERS)]
    have_tier = reputation.tier(getattr(session, "reputation", 0))
    rows = [
        (f"Standing {tier}+", order.index(have_tier) >= order.index(tier)),
        (f"Etiquette {et}", _lvl(session, "etiquette") >= et),
        (f"Charisma {ch}", _lvl(session, "charisma") >= ch),
        (f"Combat {cb}", int(session.combat_level()) >= cb),
    ]
    if need:
        rows.append((PROPERTY_TEXT[need].capitalize(), property_ok(conn, session.player_id, need)))
    rows.append((f"Patent fee {cost:,} (bank)", int(getattr(session, "bank_coins", 0)) >= cost))
    return rows


def check(session, conn):
    rows = check_rows(session, conn)
    if not rows:
        return False, ["You hold the highest rank."]
    missing = [label for label, ok in rows if not ok]
    return not missing, missing


def cooldown_left(conn, player_id, now=None):
    now = time.time() if now is None else float(now)
    row = conn.execute("SELECT last_petition_refused FROM players WHERE id = ?", (int(player_id),)).fetchone()
    if not row or row[0] is None:
        return 0
    return max(0, REFUSAL_COOLDOWN - (now - float(row[0])))


def petition(session, conn, now=None):
    """Returns (ok, message, old_rank). Never takes the bank below 0."""
    import apprentice
    now = time.time() if now is None else float(now)
    pid = session.player_id
    old = int(getattr(session, "noble_rank", 0) or 0)
    left = cooldown_left(conn, pid, now)
    if left > 0:
        return False, f"The Chamberlain will hear you again in {int(left // 3600) + 1} hours.", old
    if old >= MAX_RANK:
        return False, "You hold the highest rank.", old
    ok, missing = check(session, conn)
    nxt = old + 1
    if not ok:
        conn.execute("UPDATE players SET last_petition_refused = ? WHERE id = ?", (now, pid))
        conn.commit()
        return False, "Petition refused. Missing: " + "; ".join(missing) + ". Try again in 24 hours.", old
    cost = fee(nxt)
    if apprentice.bank_get(conn, pid) < cost:
        conn.execute("UPDATE players SET last_petition_refused = ? WHERE id = ?", (now, pid))
        conn.commit()
        return False, f"Your bank can't cover the {cost:,} patent fee.", old
    session.bank_coins = apprentice.bank_add(conn, pid, -cost)
    royal_treasury.credit(conn, "noble_patent", pid, cost)
    conn.execute("UPDATE players SET noble_rank = ? WHERE id = ?", (nxt, pid))
    conn.execute("INSERT INTO noble_log (ts, player_id, from_rank, to_rank, fee) VALUES (?, ?, ?, ?, ?)",
                 (now, pid, old, nxt, cost))
    conn.commit()
    session.noble_rank = nxt
    return True, f"Patent granted: you are now {rank_name(nxt, session.gender)}.", old


def perks_lines():
    out = []
    for r in range(1, MAX_RANK + 1):
        d, w, c = PERKS[r]
        bits = [f"{int(d * 100)}% off in shops"]
        if w:
            bits.append(f"+{w} property worker slot{'s' if w > 1 else ''}")
        if c:
            bits.append(f"+{c} guild recruit cap")
        out.append(f"{NAMES[r][0]}/{NAMES[r][1]}: " + ", ".join(bits) + f". Fee {fee(r):,}.")
    return out


CHAMBERLAIN_OPTIONS = [
    {"id": "noble_petition", "label": "Petition for rank"},
    {"id": "noble_perks", "label": "What do ranks grant?"},
    {"id": "social_explain", "label": "Charisma & Etiquette?"},
    {"id": "tribute_menu", "label": "Offer tribute to the Crown"},
    {"id": "noble_leave", "label": "Leave"},
]

SOCIAL_EXPLAIN_LINES = [
    "Charisma grows when you talk to folk (once a day each) and finish quests. Persuade options and noble ranks need it.",
    "Etiquette grows when you pay land fees, make taxed trades, work as an apprentice — or offer tribute to the Crown.",
    "Standing (Reputation) is separate: honest work and quests raise it; shops treat you better and ranks require a tier.",
    "Tribute: costly gold or gems for a little Court Favour plus Charisma and Etiquette XP — never a cheap shortcut. Ask me to Offer tribute when you can afford it.",
]
