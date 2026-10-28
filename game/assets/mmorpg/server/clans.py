"""One guild (stored as "clan") per player. Invites last two minutes and are not saved.

Crownfall phase 5 adds ranks, a coin bank, NPC recruits and Royal Challenge strength.
Player-facing text says Guild; tables, module and ids stay "clan".
"""
from __future__ import annotations

import re
import time

_NAME = re.compile(r"^[A-Za-z0-9 ]{3,20}$")
_INVITES = {}  # player_id -> (clan_id, inviter_id, expires_at)
_INVITE_SECONDS = 120.0

# ---- Phase 5 numbers ---------------------------------------------------------
MAX_PLAYER_MEMBERS = 25
MAX_NPC_RECRUITS = 8
ROYAL_CHALLENGE_MEMBERS = 20
ROYAL_CHALLENGE_MIN_PLAYERS = 12
CHARTER_COST = 10_000
RECRUIT_HIRE_COST = 5_000
RECRUIT_UPKEEP_DAILY = 250
RECRUIT_UPKEEP_TAX = 0.05
UPKEEP_MAX_DAYS = 7
DAY = 86400
REP_CREATE = 10
REP_TUTORIAL = 15
CHARISMA_TUTORIAL_XP = 600
REP_DEPOSIT_PER = 1_000
REP_DEPOSIT_DAILY_CAP = 5
KING_CASTLE_ID = "king"
RECRUIT_ROLES = ("Guard", "Squire", "Steward")
RECRUIT_NAMES = (
    "Alden", "Brina", "Cole", "Dara", "Edric", "Fenna", "Garret", "Hale",
    "Isolde", "Jory", "Kestrel", "Lorne", "Maren", "Nils", "Odette", "Piers",
)
RANKS = ("Leader", "Officer", "Member", "Recruit")   # highest first
# rank -> (invite, kick ranks, promote-to ranks, withdraw/day (None = unlimited), hire)
PERMS = {
    "Leader": (True, ("Officer", "Member", "Recruit"), ("Officer", "Member", "Recruit"), None, True),
    "Officer": (True, ("Member", "Recruit"), ("Member",), 50_000, True),
    "Member": (False, (), (), 5_000, False),
    "Recruit": (False, (), (), 0, False),
}
_CONN = None   # tests set this to an in-memory sqlite connection


def max_player_members():
    return MAX_PLAYER_MEMBERS


def can_invite(rank):
    return PERMS.get(rank, PERMS["Recruit"])[0]


def can_kick(rank, target_rank):
    return target_rank in PERMS.get(rank, PERMS["Recruit"])[1]


def can_set_rank(rank, target_rank, new_rank):
    p = PERMS.get(rank, PERMS["Recruit"])
    return target_rank in p[1] and new_rank in p[2] and new_rank != target_rank


def withdraw_cap(rank):
    return PERMS.get(rank, PERMS["Recruit"])[3]


def can_hire(rank):
    return PERMS.get(rank, PERMS["Recruit"])[4]


def ensure_tables(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clans ("
        "clan_id INTEGER PRIMARY KEY,"
        "name TEXT UNIQUE COLLATE NOCASE,"
        "leader_id INTEGER,"
        "created_at REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clan_members ("
        "player_id INTEGER PRIMARY KEY,"
        "clan_id INTEGER,"
        "joined_at REAL)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clans)")}
    for col, decl in (("bank_coins", "INTEGER DEFAULT 0"), ("charter_paid", "INTEGER DEFAULT 0"),
                      ("challenge_castle_id", "TEXT NULL")):
        if col not in cols:
            conn.execute(f"ALTER TABLE clans ADD COLUMN {col} {decl}")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clan_members)")}
    if "rank" not in cols:
        conn.execute("ALTER TABLE clan_members ADD COLUMN rank TEXT DEFAULT 'Member'")
        conn.execute(
            "UPDATE clan_members SET rank = 'Leader' WHERE player_id IN (SELECT leader_id FROM clans "
            "WHERE clans.clan_id = clan_members.clan_id)"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clan_recruits (id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER, "
        "name TEXT, role TEXT, hired_at REAL, upkeep_paid_through REAL, active INTEGER DEFAULT 1)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clan_bank_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "clan_id INTEGER, player_id INTEGER, action TEXT, amount INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clan_withdraw_daily (player_id INTEGER, day TEXT, amount INTEGER, "
        "PRIMARY KEY(player_id, day))"
    )
    conn.commit()


def _db():
    if _CONN is not None:
        return _CONN
    from server import WORLD
    return WORLD.db.conn


def clan_of(player_id):
    if not player_id:
        return None
    row = _db().execute(
        "SELECT clan_id FROM clan_members WHERE player_id = ?", (int(player_id),),
    ).fetchone()
    return int(row[0]) if row else None


def member_count(clan_id):
    if not clan_id:
        return 0
    row = _db().execute(
        "SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (int(clan_id),),
    ).fetchone()
    return int(row[0] if row else 0)


def members(clan_id):
    if not clan_id:
        return []
    rows = _db().execute(
        "SELECT m.player_id, p.char_name, m.joined_at, c.leader_id, m.rank "
        "FROM clan_members m "
        "JOIN players p ON p.id = m.player_id "
        "JOIN clans c ON c.clan_id = m.clan_id "
        "WHERE m.clan_id = ? ORDER BY m.joined_at, m.player_id",
        (int(clan_id),),
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "name": row[1],
            "joined_at": row[2],
            "leader": int(row[0]) == int(row[3]),
            "rank": "Leader" if int(row[0]) == int(row[3]) else (row[4] or "Member"),
        }
        for row in rows
    ]


def _clan_row(clan_id):
    return _db().execute(
        "SELECT clan_id, name, leader_id FROM clans WHERE clan_id = ?", (int(clan_id),),
    ).fetchone()


def _member_totals(clan_id):
    """Per-member total level + XP for the guild board (sorted best first)."""
    import combat
    from content import XP_SKILLS
    people = members(clan_id)
    if not people:
        return [], 0, 0
    cols = {r[1] for r in _db().execute("PRAGMA table_info(players)")}
    xp_cols = [f"{s}_xp" for s in XP_SKILLS if f"{s}_xp" in cols]
    if not xp_cols:
        rows = [{"name": p["name"], "rank": p["rank"], "total_level": 0, "total_xp": 0} for p in people]
        return rows, 0, 0
    select = ", ".join(["id", "char_name"] + xp_cols)
    by_id = {
        int(r[0]): r for r in _db().execute(
            f"SELECT {select} FROM players WHERE id IN ({','.join('?' * len(people))})",
            tuple(int(p["id"]) for p in people),
        ).fetchall()
    }
    board = []
    guild_xp = 0
    guild_levels = 0
    for p in people:
        row = by_id.get(int(p["id"]))
        total_xp = 0
        total_level = 0
        if row:
            # row: id, char_name, skill_xp...
            for i, _col in enumerate(xp_cols):
                xp = int(row[2 + i] or 0)
                total_xp += xp
                total_level += combat.level_from_xp(xp)
        board.append({
            "name": p["name"],
            "rank": p["rank"],
            "total_level": total_level,
            "total_xp": total_xp,
        })
        guild_xp += total_xp
        guild_levels += total_level
    board.sort(key=lambda e: (-e["total_level"], -e["total_xp"], e["name"]))
    return board, guild_levels, guild_xp


def public(clan_id):
    row = _clan_row(clan_id) if clan_id else None
    people = members(clan_id) if row else []
    leader = next((p["name"] for p in people if p["leader"]), "")
    info = {
        "name": row[1] if row else "",
        "leader": leader,
        "members": [f"{p['name']} ({p['rank']})" for p in people],
        "ranks": {p["name"]: p["rank"] for p in people},
        "count": len(people),
        "max_members": MAX_PLAYER_MEMBERS,
        "board": [],
        "guild_total_level": 0,
        "guild_total_xp": 0,
    }
    if row:
        players, active, counted, eligible = royal_challenge_strength(clan_id)
        board, g_lvl, g_xp = _member_totals(clan_id)
        info.update({
            "bank_coins": bank_balance(clan_id),
            "recruits": recruit_count(clan_id),
            "recruits_active": active,
            "max_recruits": recruit_cap(clan_id),
            "challenge": strength_line(clan_id),
            "challenge_eligible": eligible,
            "board": board,
            "guild_total_level": g_lvl,
            "guild_total_xp": g_xp,
        })
    return info


def _player_named(name):
    return _db().execute(
        "SELECT id, char_name FROM players WHERE char_name = ? COLLATE NOCASE",
        (name.strip(),),
    ).fetchone()


def _clean_invites():
    now = time.time()
    dead = [pid for pid, (_c, _i, exp) in _INVITES.items() if exp <= now]
    for pid in dead:
        _INVITES.pop(pid, None)


def pending_invite(player_id):
    """Open invite for the Guild panel, or None."""
    _clean_invites()
    pending = _INVITES.get(int(player_id))
    if not pending:
        return None
    clan_id, inviter_id, exp = pending
    row = _clan_row(clan_id)
    if not row:
        return None
    inviter = _db().execute(
        "SELECT char_name FROM players WHERE id = ?", (int(inviter_id),),
    ).fetchone()
    return {
        "clan_id": int(clan_id),
        "name": row[1],
        "from": (inviter[0] if inviter else "Someone"),
        "expires_in": max(0, int(exp - time.time())),
    }


def _info_for(session):
    """CLAN_INFO payload for one player (guild + optional pending invite)."""
    clan_id = clan_of(session.player_id)
    info = dict(public(clan_id))
    info["rank"] = rank_of(session.player_id) or ""
    invite = pending_invite(session.player_id)
    if invite:
        info["invite"] = invite
    return info


async def _push(clan_id):
    """Push CLAN_INFO to every online member. Never raise into command handlers."""
    from server import WORLD, send
    if not clan_id:
        return
    try:
        cid = int(clan_id)
    except (TypeError, ValueError):
        return
    for session in list(WORLD.sessions.values()):
        try:
            if clan_of(session.player_id) == cid:
                await send(session.ws, "CLAN_INFO", **_info_for(session))
        except Exception:
            pass


async def _notify(session):
    """CLAN_INFO for one player (create / deposit / invite target)."""
    from server import send
    try:
        await send(session.ws, "CLAN_INFO", **_info_for(session))
    except Exception:
        pass


async def _say(session, text):
    from server import send
    await send(session.ws, "CHAT_MSG", **{"from": "Guild", "text": text, "channel": "guild"})


async def on_login(session):
    from server import send
    clan_id = clan_of(session.player_id)
    if clan_id:
        settle_upkeep(_db(), clan_id)
    await send(session.ws, "CLAN_INFO", **_info_for(session))


async def tick_upkeep():
    """500-tick loop: settle recruit upkeep for guilds with someone online."""
    from server import WORLD
    seen = set()
    for session in list(WORLD.sessions.values()):
        cid = clan_of(session.player_id)
        if cid and cid not in seen:
            seen.add(cid)
            settle_upkeep(_db(), cid)


# ---- Phase 5 core (sync, conn-based, unit-testable) ----------------------------
def _today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() if now is None else now))


def rank_of(player_id):
    if not player_id:
        return None
    row = _db().execute(
        "SELECT m.rank, c.leader_id FROM clan_members m JOIN clans c ON c.clan_id = m.clan_id "
        "WHERE m.player_id = ?", (int(player_id),),
    ).fetchone()
    if not row:
        return None
    return "Leader" if int(row[1]) == int(player_id) else (row[0] or "Member")


def bank_balance(clan_id):
    row = _db().execute("SELECT bank_coins FROM clans WHERE clan_id = ?", (int(clan_id),)).fetchone()
    return int(row[0] or 0) if row else 0


def _log(clan_id, player_id, action, amount, now=None):
    _db().execute(
        "INSERT INTO clan_bank_log (ts, clan_id, player_id, action, amount) VALUES (?, ?, ?, ?, ?)",
        (time.time() if now is None else now, int(clan_id), player_id, action, int(amount)),
    )


def _bank_move(clan_id, delta):
    """Atomic guild bank change that can never go below 0. True if applied."""
    cur = _db().execute(
        "UPDATE clans SET bank_coins = COALESCE(bank_coins, 0) + ? WHERE clan_id = ? "
        "AND COALESCE(bank_coins, 0) + ? >= 0", (int(delta), int(clan_id), int(delta)),
    )
    return cur.rowcount == 1


def create_core(player_id, name, now=None):
    """Returns (ok, message, clan_id). Charges CHARTER_COST from the player's bank."""
    import apprentice
    import royal_treasury
    conn = _db()
    now = time.time() if now is None else now
    name = " ".join((name or "").split())
    if not _NAME.match(name):
        return False, "Guild names are 3–20 letters, digits, and spaces.", None
    if clan_of(player_id):
        return False, "You are already in a guild. /guild leave first.", None
    if conn.execute("SELECT 1 FROM clans WHERE name = ? COLLATE NOCASE", (name,)).fetchone():
        return False, "That guild name is already taken.", None
    if apprentice.bank_get(conn, player_id) < CHARTER_COST:
        return False, f"A guild charter costs {CHARTER_COST:,} coins from your bank.", None
    try:
        cur = conn.execute(
            "INSERT INTO clans (name, leader_id, created_at, bank_coins, charter_paid) VALUES (?, ?, ?, 0, 1)",
            (name, int(player_id), now),
        )
        clan_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO clan_members (player_id, clan_id, joined_at, rank) VALUES (?, ?, ?, 'Leader')",
            (int(player_id), clan_id, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        return False, "That guild name is already taken.", None
    apprentice.bank_add(conn, player_id, -CHARTER_COST)
    royal_treasury.credit(conn, "guild_charter", player_id, CHARTER_COST)
    return True, f"You founded the guild {name} ({CHARTER_COST:,} coins to the Crown).", clan_id


def join_core(player_id, clan_id, now=None):
    if member_count(clan_id) >= MAX_PLAYER_MEMBERS:
        return False
    _db().execute(
        "INSERT OR REPLACE INTO clan_members (player_id, clan_id, joined_at, rank) VALUES (?, ?, ?, 'Recruit')",
        (int(player_id), int(clan_id), time.time() if now is None else now),
    )
    _db().commit()
    return True


def kick_core(actor_id, target_id):
    cid = clan_of(actor_id)
    if not cid or clan_of(target_id) != cid:
        return False, "They are not in your guild."
    if int(actor_id) == int(target_id):
        return False, "Use /guild leave to step down."
    if not can_kick(rank_of(actor_id), rank_of(target_id)):
        return False, "Your rank can't kick them."
    _db().execute("DELETE FROM clan_members WHERE player_id = ?", (int(target_id),))
    _db().commit()
    return True, "Kicked."


def set_rank_core(actor_id, target_id, new_rank):
    cid = clan_of(actor_id)
    if not cid or clan_of(target_id) != cid:
        return False, "They are not in your guild."
    if new_rank not in RANKS or new_rank == "Leader":
        return False, "Use /guild leader <player> to pass on leadership."
    old = rank_of(target_id)
    if not can_set_rank(rank_of(actor_id), old, new_rank):
        return False, "Your rank can't do that."
    _db().execute("UPDATE clan_members SET rank = ? WHERE player_id = ?", (new_rank, int(target_id)))
    _db().commit()
    return True, f"Now {new_rank}."


def _step(rank, up):
    i = RANKS.index(rank)
    i = i - 1 if up else i + 1
    return RANKS[max(1, min(len(RANKS) - 1, i))]


def leader_core(actor_id, target_id):
    cid = clan_of(actor_id)
    if rank_of(actor_id) != "Leader":
        return False, "Only the Leader can pass on leadership."
    if not cid or clan_of(target_id) != cid or int(target_id) == int(actor_id):
        return False, "They are not in your guild."
    conn = _db()
    conn.execute("UPDATE clans SET leader_id = ? WHERE clan_id = ?", (int(target_id), cid))
    conn.execute("UPDATE clan_members SET rank = 'Leader' WHERE player_id = ?", (int(target_id),))
    conn.execute("UPDATE clan_members SET rank = 'Officer' WHERE player_id = ?", (int(actor_id),))
    conn.commit()
    return True, "Leadership passed on."


def leave_core(player_id):
    """Returns (clan_id, disbanded). Leader succession: longest Officer, then Member, then anyone."""
    cid = clan_of(player_id)
    if not cid:
        return None, False
    conn = _db()
    was_leader = rank_of(player_id) == "Leader"
    conn.execute("DELETE FROM clan_members WHERE player_id = ?", (int(player_id),))
    left = members(cid)
    if not left:
        conn.execute("DELETE FROM clans WHERE clan_id = ?", (cid,))
        conn.execute("DELETE FROM clan_recruits WHERE clan_id = ?", (cid,))
        conn.commit()
        return cid, True
    if was_leader:
        nxt = None
        for want in ("Officer", "Member"):
            nxt = next((m for m in left if m["rank"] == want), None)
            if nxt:
                break
        nxt = nxt or left[0]
        conn.execute("UPDATE clans SET leader_id = ? WHERE clan_id = ?", (nxt["id"], cid))
        conn.execute("UPDATE clan_members SET rank = 'Leader' WHERE player_id = ?", (nxt["id"],))
    conn.commit()
    return cid, False


def deposit_core(player_id, amount, now=None):
    import apprentice
    conn = _db()
    cid = clan_of(player_id)
    amount = int(amount)
    if not cid:
        return False, "You are not in a guild."
    if amount <= 0:
        return False, "Deposit a positive amount."
    if apprentice.bank_get(conn, player_id) < amount:
        return False, "Your bank doesn't hold that much."
    apprentice.bank_add(conn, player_id, -amount)
    _bank_move(cid, amount)
    _log(cid, player_id, "deposit", amount, now)
    conn.commit()
    return True, f"Deposited {amount:,} coins. Guild bank: {bank_balance(cid):,}."


def withdraw_core(player_id, amount, now=None):
    import apprentice
    conn = _db()
    cid = clan_of(player_id)
    amount = int(amount)
    if not cid:
        return False, "You are not in a guild."
    if amount <= 0:
        return False, "Withdraw a positive amount."
    cap = withdraw_cap(rank_of(player_id))
    day = _today(now)
    row = conn.execute("SELECT amount FROM clan_withdraw_daily WHERE player_id = ? AND day = ?",
                       (int(player_id), day)).fetchone()
    used = int(row[0]) if row else 0
    if cap is not None and used + amount > cap:
        return False, f"Your rank may withdraw {cap:,} a day ({max(0, cap - used):,} left today)."
    if not _bank_move(cid, -amount):
        return False, "The guild bank doesn't hold that much."
    apprentice.bank_add(conn, player_id, amount)
    conn.execute(
        "INSERT INTO clan_withdraw_daily (player_id, day, amount) VALUES (?, ?, ?) "
        "ON CONFLICT(player_id, day) DO UPDATE SET amount = amount + ?", (int(player_id), day, amount, amount))
    _log(cid, player_id, "withdraw", amount, now)
    conn.commit()
    return True, f"Withdrew {amount:,} coins to your bank. Guild bank: {bank_balance(cid):,}."


RECRUIT_CAP_HARD_MAX = 10


def recruit_cap(clan_id):
    """MAX_NPC_RECRUITS plus the best Leader/Officer noble bonus, at most 10."""
    import nobility
    best = 0
    for m in members(clan_id):
        if m["rank"] in ("Leader", "Officer"):
            best = max(best, nobility.extra_recruit_cap(nobility.rank_of(_db(), m["id"])))
    return min(RECRUIT_CAP_HARD_MAX, MAX_NPC_RECRUITS + best)


def recruit_count(clan_id, active_only=False):
    q = "SELECT COUNT(*) FROM clan_recruits WHERE clan_id = ?" + (" AND active = 1" if active_only else "")
    return int(_db().execute(q, (int(clan_id),)).fetchone()[0])


def recruits(clan_id):
    return _db().execute(
        "SELECT id, name, role, active FROM clan_recruits WHERE clan_id = ? ORDER BY id", (int(clan_id),),
    ).fetchall()


def hire_core(player_id, role, now=None):
    now = time.time() if now is None else now
    cid = clan_of(player_id)
    if not cid:
        return False, "You are not in a guild."
    if not can_hire(rank_of(player_id)):
        return False, "Only the Leader or an Officer can hire recruits."
    role = (role or "").strip().title()
    if role not in RECRUIT_ROLES:
        return False, "Roles: " + ", ".join(RECRUIT_ROLES) + "."
    n = recruit_count(cid)
    cap = recruit_cap(cid)
    if n >= cap:
        return False, f"Your guild already has {cap} recruits."
    if not _bank_move(cid, -RECRUIT_HIRE_COST):
        return False, f"Hiring costs {RECRUIT_HIRE_COST:,} from the guild bank."
    used = {r[0] for r in _db().execute("SELECT name FROM clan_recruits WHERE clan_id = ?", (cid,))}
    name = next((x for x in RECRUIT_NAMES if x not in used), f"Recruit {n + 1}")
    _db().execute(
        "INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
        "VALUES (?, ?, ?, ?, ?, 1)", (cid, name, role, now, now),
    )
    _log(cid, player_id, "hire", -RECRUIT_HIRE_COST, now)
    _db().commit()
    return True, f"{name} the {role} joins the guild ({RECRUIT_HIRE_COST:,}, then {RECRUIT_UPKEEP_DAILY}/day)."


def dismiss_core(player_id, recruit_id):
    cid = clan_of(player_id)
    if not cid or not can_hire(rank_of(player_id)):
        return False, "Only the Leader or an Officer can dismiss recruits."
    cur = _db().execute("DELETE FROM clan_recruits WHERE id = ? AND clan_id = ?", (int(recruit_id), cid))
    _db().commit()
    return (True, "Recruit dismissed.") if cur.rowcount else (False, "No recruit with that id.")


def settle_upkeep(conn, clan_id, now=None):
    """Daily recruit upkeep. Returns (days_paid, days_skipped). Never negative, no debt."""
    import royal_treasury
    global _CONN
    prev = _CONN
    _CONN = conn
    try:
        now = time.time() if now is None else float(now)
        paid = skipped = 0
        for rid, through in conn.execute(
                "SELECT id, upkeep_paid_through FROM clan_recruits WHERE clan_id = ? ORDER BY id",
                (int(clan_id),)).fetchall():
            through = float(through or now)
            days = int((now - through) // DAY)
            if days <= 0:
                continue
            active = None
            for _ in range(min(days, UPKEEP_MAX_DAYS)):
                if _bank_move(clan_id, -RECRUIT_UPKEEP_DAILY):
                    tax = int(RECRUIT_UPKEEP_DAILY * RECRUIT_UPKEEP_TAX)
                    royal_treasury.credit(conn, "recruit_upkeep_tax", None, tax)
                    _log(clan_id, None, "upkeep", -RECRUIT_UPKEEP_DAILY, now)
                    paid += 1
                    active = 1
                else:
                    skipped += 1
                    active = 0
            conn.execute("UPDATE clan_recruits SET upkeep_paid_through = ?, active = ? WHERE id = ?",
                         (through + days * DAY, active, rid))
        conn.commit()
        return paid, skipped
    finally:
        _CONN = prev


def royal_challenge_strength(clan_id):
    players = member_count(clan_id)
    active = recruit_count(clan_id, active_only=True)
    counted = players + min(active, MAX_NPC_RECRUITS)
    return players, active, counted, players >= ROYAL_CHALLENGE_MIN_PLAYERS and counted >= ROYAL_CHALLENGE_MEMBERS


def strength_line(clan_id):
    players, active, counted, ok = royal_challenge_strength(clan_id)
    rec = min(active, MAX_NPC_RECRUITS)
    return (f"Royal Challenge: {players} players + {rec} recruits = {min(counted, 99)}/{ROYAL_CHALLENGE_MEMBERS} "
            + ("✓" if ok else f"✗ (needs {ROYAL_CHALLENGE_MIN_PLAYERS}+ players)"))


def can_challenge_castle(clan_id, castle_id, owned_castles=None, all_castles=None):
    """Data hook only. King's Castle waits for the phase 7 throne rules."""
    if castle_id == KING_CASTLE_ID:
        try:
            import throne
            return bool(throne.can_challenge_king(clan_id))
        except ImportError:
            return False
    if owned_castles is None or all_castles is None:
        try:
            import castle_owners
            all_castles = [c for c in castle_owners.load()["castles"] if c != KING_CASTLE_ID]
            owned_castles = list(castle_owners.owners(_db()).keys())
        except Exception:
            return False
    others = [c for c in all_castles if c != KING_CASTLE_ID]
    return castle_id in others and all(c in owned_castles for c in others)


def set_challenge(clan_id, castle_id, **kw):
    if not can_challenge_castle(clan_id, castle_id, **kw):
        return False
    _db().execute("UPDATE clans SET challenge_castle_id = ? WHERE clan_id = ?", (castle_id, int(clan_id)))
    _db().commit()
    return True


# ---- chat commands ------------------------------------------------------------
_HELP = ("Guild: /guild create <name> (10,000) · invite <p> · accept · decline · leave · kick <p> · list · "
         "promote <p> · demote <p> · leader <p> · bank · deposit <n> · withdraw <n> · "
         "recruits · hire <Guard|Squire|Steward> · dismiss <id> · challenge [castle] · help")


async def _refresh(session):
    from server import send
    await send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def handle_command(session, text):
    _clean_invites()
    parts = text.split()
    cmd = parts[1].lower() if len(parts) > 1 else ""
    rest = text.split(None, 2)
    arg = rest[2].strip() if len(rest) > 2 else ""
    if cmd == "create":
        await create(session, arg)
    elif cmd == "invite":
        await invite(session, arg)
    elif cmd == "accept":
        await accept(session)
    elif cmd == "decline":
        await decline(session)
    elif cmd == "leave":
        await leave(session)
    elif cmd == "kick":
        await kick(session, arg)
    elif cmd == "list":
        await _list(session)
    elif cmd in ("promote", "demote"):
        target = _player_named(arg) if arg else None
        if not target:
            await _say(session, f"No one named {arg} is known here.")
            return
        old = rank_of(target[0]) or "Member"
        ok, msg = set_rank_core(session.player_id, target[0], _step(old, cmd == "promote"))
        await _say(session, f"{target[1]}: {msg}" if ok else msg)
        if ok:
            await _push(clan_of(session.player_id))
    elif cmd == "leader":
        target = _player_named(arg) if arg else None
        ok, msg = leader_core(session.player_id, target[0]) if target else (False, "Who?")
        await _say(session, msg)
        if ok:
            await _push(clan_of(session.player_id))
    elif cmd == "bank":
        cid = clan_of(session.player_id)
        await _say(session, f"Guild bank: {bank_balance(cid):,} coins." if cid else "You are not in a guild.")
    elif cmd in ("deposit", "withdraw"):
        try:
            n = int(arg.replace(",", ""))
        except ValueError:
            await _say(session, f"/guild {cmd} <amount>")
            return
        fn = deposit_core if cmd == "deposit" else withdraw_core
        ok, msg = fn(session.player_id, n)
        await _say(session, msg)
        if ok:
            # Bank figure on the Guild panel comes from CLAN_INFO / PLAYER_UPDATE.
            await _refresh(session)
            await _notify(session)
            await _push(clan_of(session.player_id))
            if cmd == "deposit":
                try:
                    from server import social_event
                    import server
                    await social_event(session, "guild_deposit", rep=n // REP_DEPOSIT_PER,
                                       rep_cap_key="rep_guild_deposit", rep_cap=REP_DEPOSIT_DAILY_CAP)
                    await server.guild_tutorial_event(session, "deposit")
                except Exception:
                    pass
    elif cmd == "recruits":
        cid = clan_of(session.player_id)
        if not cid:
            await _say(session, "You are not in a guild.")
            return
        rows = recruits(cid)
        listing = ", ".join(f"#{r[0]} {r[1]} ({r[2]}{'' if r[3] else ', inactive'})" for r in rows) or "none"
        await _say(session, f"Recruits {recruit_count(cid, True)}/{MAX_NPC_RECRUITS} active: {listing}")
    elif cmd == "hire":
        ok, msg = hire_core(session.player_id, arg)
        await _say(session, msg)
        if ok:
            await _push(clan_of(session.player_id))
    elif cmd == "dismiss":
        try:
            ok, msg = dismiss_core(session.player_id, int(arg.lstrip("#")))
        except ValueError:
            ok, msg = False, "/guild dismiss <id>"
        await _say(session, msg)
        if ok:
            await _push(clan_of(session.player_id))
    elif cmd == "challenge":
        cid = clan_of(session.player_id)
        if not cid:
            await _say(session, "You are not in a guild.")
            return
        await _say(session, strength_line(cid))
        if arg:
            if rank_of(session.player_id) != "Leader":
                await _say(session, "Only the Leader can name a castle to challenge.")
            elif set_challenge(cid, arg.lower()):
                await _say(session, f"Your guild has declared a challenge for {arg}. (Sieges come later.)")
            else:
                await _say(session, "You can't challenge that castle yet. The King's Castle needs the throne "
                                    "rules; other castles only once every castle is owned.")
        else:
            row = _db().execute("SELECT challenge_castle_id FROM clans WHERE clan_id = ?", (cid,)).fetchone()
            await _say(session, f"Castle challenge: {row[0] or 'none declared'}.")
    else:
        await _say(session, _HELP)


async def create(session, name):
    ok, msg, clan_id = create_core(session.player_id, name)
    await _say(session, msg)
    if not ok:
        return
    # Notify before refresh/social so the panel never stays on "Create guild".
    await _notify(session)
    try:
        await _refresh(session)
    except Exception:
        pass
    await _push(clan_id)
    try:
        from server import social_event
        import server
        await social_event(session, "guild_create", rep=REP_CREATE)
        await server.guild_tutorial_event(session, "guild")
    except Exception:
        pass


async def invite(session, target_name):
    clan_id = clan_of(session.player_id)
    row = _clan_row(clan_id) if clan_id else None
    if not row or not can_invite(rank_of(session.player_id)):
        await _say(session, "Only the Leader or an Officer can invite.")
        return
    if member_count(clan_id) >= MAX_PLAYER_MEMBERS:
        await _say(session, f"The guild is already at {MAX_PLAYER_MEMBERS} members.")
        return
    target = _player_named(target_name)
    if not target:
        await _say(session, f"No one named {target_name} is known here.")
        return
    if clan_of(target[0]):
        await _say(session, f"{target[1]} is already in a guild.")
        return
    _INVITES[int(target[0])] = (int(clan_id), int(session.player_id), time.time() + _INVITE_SECONDS)
    await _say(session, f"Invited {target[1]}. They have two minutes to Accept in Guild.")
    from server import WORLD, send
    other = WORLD.sessions.get(int(target[0]))
    if other:
        await send(other.ws, "CHAT_MSG", **{
            "from": "Guild",
            "text": f"{session.char_name} invited you to {row[1]}. Open Guild to Accept.",
        })
        await send(other.ws, "CLAN_INFO", **_info_for(other))


async def accept(session):
    from server import send
    _clean_invites()
    pending = _INVITES.get(int(session.player_id))
    if not pending:
        await _say(session, "You have no guild invite.")
        await _notify(session)  # clear a stuck invite banner if already joined
        return
    if clan_of(session.player_id):
        _INVITES.pop(int(session.player_id), None)
        await _say(session, "You are already in a guild.")
        await _notify(session)
        return
    clan_id, _inviter, _exp = pending
    _INVITES.pop(int(session.player_id), None)
    if not join_core(session.player_id, clan_id):
        await _say(session, "That guild is full.")
        await _notify(session)
        return
    await _say(session, "You joined the guild as a Recruit.")
    # Notify first so the panel never stays on Create/Invite if refresh fails.
    await _notify(session)
    try:
        await _refresh(session)
    except Exception:
        pass
    await _push(clan_id)
    try:
        import server
        await server.guild_tutorial_event(session, "guild")
    except Exception:
        pass


async def decline(session):
    _clean_invites()
    pending = _INVITES.pop(int(session.player_id), None)
    if not pending:
        await _say(session, "You have no guild invite.")
        await _notify(session)  # resync panel (e.g. already joined, banner stuck)
        return
    await _say(session, "You declined the guild invite.")
    await _notify(session)


async def leave(session):
    from server import send
    clan_id, disbanded = leave_core(session.player_id)
    if not clan_id:
        await _say(session, "You are not in a guild.")
        return
    await send(session.ws, "CLAN_INFO", **_info_for(session))
    if disbanded:
        await _say(session, "You left, and the guild disbanded.")
        return
    await _say(session, "You left the guild.")
    await _push(clan_id)


async def kick(session, target_name):
    clan_id = clan_of(session.player_id)
    target = _player_named(target_name)
    if not clan_id or not target:
        await _say(session, f"{target_name} is not in your guild.")
        return
    ok, msg = kick_core(session.player_id, target[0])
    if not ok:
        await _say(session, msg)
        return
    await _say(session, f"Kicked {target[1]}.")
    from server import WORLD, send
    other = WORLD.sessions.get(int(target[0]))
    if other:
        await send(other.ws, "CLAN_INFO", **_info_for(other))
        await send(other.ws, "CHAT_MSG", **{"from": "Guild", "text": "You were kicked from the guild."})
    await _push(clan_id)


async def _list(session):
    clan_id = clan_of(session.player_id)
    info = public(clan_id)
    if not info["name"]:
        await _say(session, "You are not in a guild. /guild create <name>")
        return
    names = ", ".join(info["members"])
    await _say(session, f"{info['name']} — leader {info['leader']} — {info['count']}/{MAX_PLAYER_MEMBERS} "
                        f"members. Bank {info['bank_coins']:,}. Recruits {info['recruits_active']}/"
                        f"{MAX_NPC_RECRUITS}. {names}")
    await _say(session, info["challenge"])
