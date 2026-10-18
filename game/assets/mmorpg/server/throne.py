"""Crownfall phase 7: the two paths to the throne, marriage and consorts.

Every number lives here. The core is synchronous and conn-based so it can be unit tested;
server.py wires it to NPC dialogue, the tick loop and broadcasts.
Losing anything never takes gold. Losing the throne clears only royal_title.
"""
from __future__ import annotations

import time

import royal_treasury

HOUR = 3600
DAY = 86400
WEEK = 7 * DAY

# Crown Challenge
CROWN_MIN_COMBAT = 100
CROWN_FEE = 150_000
SCHEDULE_MIN_HOURS = 12
SCHEDULE_MAX_HOURS = 48
CROWN_WINDOW = 30 * 60
HOLD_SECONDS = 5 * 60
LOSS_COOLDOWN = WEEK
WARN_BEFORE = HOUR
# Single castle challenge
CASTLE_FEE = 10_000            # floor; the fee is CASTLE_FEE_RATE of the deed
CASTLE_FEE_RATE = 0.01
CASTLE_CHALLENGE_COOLDOWN = WEEK   # per castle, from the last challenge's start
CASTLE_WINDOW = 20 * 60
CASTLE_GUARDS = 2
KING_CASTLE_ID = "king"
# Throne room (castle_realm plane king_f1) and the hold area around the throne
THRONE_PLANE = "king_f1"
THRONE_AREA = (17, 24, 36, 30)          # x0, y0, x1, y1 inclusive
THRONE_GUARD_SPOTS = ((22, 27), (24, 27), (28, 27), (30, 27))
CAPTAIN_SPOT = (26, 27)
GUARD_MONSTER = "knight"
CAPTAIN_HP_MULT = 2
PRISON_PLANE = "king_barracks_f1"
PRISON_SPOT = (10, 3)
# Courtier's Path
COURTIER_MIN_RANK = 3
COURTIER_MIN_ETIQUETTE = 55
COURTIER_MIN_CHARISMA = 55
COURTIER_TIER = "Revered"
FAVOUR_MAX = 1000
FAVOUR_TASK = 20
TASKS_PER_DAY = 3
FAVOUR_BALL = 100
BALL_WEEKDAY = 5            # Saturday (time.localtime().tm_wday)
BALL_HOUR = 20
BALL_SECONDS = HOUR
FAVOUR_PENALTY = -50
PENALTY_TIERS = ("Hated", "Distrusted", "Neutral")
ACCLAIM_FEE = 100_000
ACCLAIM_FAIL_FAVOUR = 500
ACCLAIM_FAIL_COOLDOWN = WEEK
# Court tasks: option id -> (label, accepted item ids)
COURT_TASKS = {
    "court_fish": ("Bring a cooked fish", ("cooked_shrimp", "cooked_trout", "cooked_lobster", "cooked_salmon")),
    "court_bar": ("Bring a metal bar", ("bronze_bar", "iron_bar", "steel_bar", "mithril_bar")),
    "court_gem": ("Bring a cut gem", ("jade", "topaz", "sapphire", "emerald", "ruby", "diamond")),
}
# Marriage
MARRIAGE_FEE = 10_000       # split equally
PROPOSAL_SECONDS = 60
DIVORCE_COOLDOWN = WEEK
REP_MARRIAGE = 10

HERALD_OPTIONS = [
    {"id": "crown_check", "label": "Crown Challenge"},
    {"id": "castle_check", "label": "Castle Challenge"},
    {"id": "throne_list", "label": "Current challenges"},
]
CELIA_OPTIONS = [
    {"id": "court_status", "label": "Court Favour"},
    {"id": "court_fish", "label": "Bring a cooked fish"},
    {"id": "court_bar", "label": "Bring a metal bar"},
    {"id": "court_gem", "label": "Bring a cut gem"},
    {"id": "acclaim_check", "label": "Petition for Court Acclaim"},
]
CHAPLAIN_OPTIONS = [
    {"id": "wed_propose", "label": "Propose"},
    {"id": "wed_accept", "label": "Accept proposal"},
    {"id": "wed_divorce", "label": "Divorce"},
    {"id": "wed_status", "label": "Status"},
]
HOUR_CHOICES = (12, 24, 36, 48)
DYNAMIC_PREFIXES = ("crown_h", "castle_h", "acclaim_h")

_PROPOSALS = {}   # target player_id -> (proposer_id, expires_at)
_titles_hook = None


def set_titles_hook(fn):
    global _titles_hook
    _titles_hook = fn


# ---- schema & state ---------------------------------------------------------
def ensure_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS throne (id INTEGER PRIMARY KEY CHECK (id = 1), monarch_kind TEXT DEFAULT 'npc', "
        "monarch_player_id INTEGER NULL, since REAL, path TEXT NULL, old_king_state TEXT DEFAULT 'reigning')"
    )
    conn.execute("INSERT OR IGNORE INTO throne (id, monarch_kind, since, old_king_state) VALUES (1, 'npc', ?, 'reigning')",
                 (time.time(),))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS challenges (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, challenger_id INTEGER, "
        "clan_id INTEGER NULL, castle_id TEXT, scheduled_at REAL, status TEXT, created_at REAL, resolved_at REAL NULL, "
        "result TEXT NULL)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(challenges)")}
    if "warned" not in cols:
        conn.execute("ALTER TABLE challenges ADD COLUMN warned INTEGER DEFAULT 0")
    if "started_at" not in cols:
        conn.execute("ALTER TABLE challenges ADD COLUMN started_at REAL NULL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS court_favour (player_id INTEGER PRIMARY KEY, favour INTEGER DEFAULT 0, "
        "tasks_day TEXT, tasks_done INTEGER DEFAULT 0, last_ball_week TEXT, cooldown_until REAL NULL)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(court_favour)")}
    if "penalty_day" not in cols:
        conn.execute("ALTER TABLE court_favour ADD COLUMN penalty_day TEXT NULL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS marriages (id INTEGER PRIMARY KEY AUTOINCREMENT, a_id INTEGER, b_id INTEGER, "
        "married_at REAL, divorced_at REAL NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS throne_cooldowns (player_id INTEGER, kind TEXT, until REAL, "
        "PRIMARY KEY(player_id, kind))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS throne_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, event TEXT, "
        "player_id INTEGER NULL, detail TEXT)"
    )
    conn.commit()


def state(conn):
    row = conn.execute(
        "SELECT monarch_kind, monarch_player_id, since, path, old_king_state FROM throne WHERE id = 1").fetchone()
    return dict(zip(("monarch_kind", "monarch_player_id", "since", "path", "old_king_state"), row))


def log(conn, event, player_id=None, detail="", now=None):
    conn.execute("INSERT INTO throne_log (ts, event, player_id, detail) VALUES (?, ?, ?, ?)",
                 (time.time() if now is None else now, event, player_id, detail))


def _cooldown(conn, pid, kind, now):
    row = conn.execute("SELECT until FROM throne_cooldowns WHERE player_id = ? AND kind = ?", (pid, kind)).fetchone()
    return max(0.0, float(row[0]) - now) if row else 0.0


def _set_cooldown(conn, pid, kind, until):
    conn.execute("INSERT OR REPLACE INTO throne_cooldowns (player_id, kind, until) VALUES (?, ?, ?)",
                 (pid, kind, until))


def _player_field(conn, pid, col, default=None):
    try:
        row = conn.execute(f"SELECT {col} FROM players WHERE id = ?", (pid,)).fetchone()
        return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def _gender(conn, pid):
    g = _player_field(conn, pid, "gender", None)
    if g is None and _titles_hook:
        g = getattr(_titles_hook, "gender_of", lambda _p: None)(pid)
    return "female" if str(g or "").lower() == "female" else "male"


def _bank(conn, pid):
    import apprentice
    return apprentice.bank_get(conn, pid)


def _bank_add(conn, pid, delta):
    import apprentice
    return apprentice.bank_add(conn, pid, delta)


# ---- titles -------------------------------------------------------------------
def spouse_of(conn, pid):
    row = conn.execute(
        "SELECT a_id, b_id FROM marriages WHERE divorced_at IS NULL AND (a_id = ? OR b_id = ?)", (pid, pid)).fetchone()
    if not row:
        return None
    return row[1] if int(row[0]) == int(pid) else row[0]


def apply_titles(conn):
    """royal_title for monarch and consort; cleared for everyone else. Never touches noble_rank."""
    st = state(conn)
    want = {}
    mon = st["monarch_player_id"] if st["monarch_kind"] == "player" else None
    if mon:
        want[int(mon)] = "Queen" if _gender(conn, mon) == "female" else "King"
        sp = spouse_of(conn, mon)
        if sp:
            want[int(sp)] = "Queen Consort" if _gender(conn, sp) == "female" else "Prince Consort"
    conn.execute("UPDATE players SET royal_title = NULL WHERE royal_title IS NOT NULL")
    for pid, title in want.items():
        conn.execute("UPDATE players SET royal_title = ? WHERE id = ?", (title, pid))
    conn.commit()
    if _titles_hook:
        _titles_hook(want)
    return want


def _crown(conn, pid, path, old_state, now):
    st = state(conn)
    conn.execute(
        "UPDATE throne SET monarch_kind = 'player', monarch_player_id = ?, since = ?, path = ?, "
        "old_king_state = CASE WHEN monarch_kind = 'npc' THEN ? ELSE old_king_state END WHERE id = 1",
        (pid, now, path, old_state),
    )
    log(conn, "crowned", pid, f"{path}; previous {st['monarch_kind']}:{st['monarch_player_id']}", now)
    conn.commit()
    titles = apply_titles(conn)
    try:
        import ruling
        gname = conn.execute("SELECT c.name FROM clan_members m JOIN clans c ON c.clan_id = m.clan_id "
                             "WHERE m.player_id = ?", (pid,)).fetchone()
        ruling.on_throne_change(conn, pid, _player_field(conn, pid, "char_name", f"#{pid}"),
                                titles.get(int(pid), "King"), path, gname[0] if gname else None, now,
                                reason="overthrown" if path == "conquest" else "acclaimed")
    except Exception:
        conn.rollback()   # ruling tables missing (unit tests of phase 7 alone)
    return titles


# ---- eligibility --------------------------------------------------------------
def _castle_owned_by(conn, pid):
    try:
        rows = conn.execute("SELECT castle_id FROM castle_ownership WHERE owner_account_id = ?", (pid,)).fetchall()
    except Exception:
        return []
    return [r[0] for r in rows if r[0] != KING_CASTLE_ID]


def crown_eligible(session, conn, quest_ids=None):
    import clans
    missing = []
    if int(session.combat_level()) < CROWN_MIN_COMBAT:
        missing.append(f"Combat level {CROWN_MIN_COMBAT}")
    if not _castle_owned_by(conn, session.player_id):
        missing.append("Own a castle (not the King's)")
    if quest_ids is None:
        from content import QUESTS
        quest_ids = list(QUESTS)
    done = {q for q, p in (getattr(session, "quests", {}) or {}).items() if (p or {}).get("status") == "complete"}
    left = [q for q in quest_ids if q not in done]
    if left:
        missing.append(f"Complete every quest ({len(quest_ids) - len(left)}/{len(quest_ids)})")
    cid = clans.clan_of(session.player_id)
    if not cid or clans.rank_of(session.player_id) != "Leader":
        missing.append("Lead a guild")
    elif not clans.royal_challenge_strength(cid)[3]:
        missing.append(clans.strength_line(cid))
    return not missing, missing


def courtier_eligible(session, conn=None):
    """Female characters only; men get (False, []) and never see the path."""
    import reputation
    if str(getattr(session, "gender", "")).lower() != "female":
        return False, []
    missing = []

    def lvl(sk):
        try:
            return int(session.level(sk)) if sk in session.xp else 1
        except Exception:
            return 1
    if int(getattr(session, "noble_rank", 0) or 0) < COURTIER_MIN_RANK:
        missing.append("Baroness rank or higher")
    if lvl("etiquette") < COURTIER_MIN_ETIQUETTE:
        missing.append(f"Etiquette {COURTIER_MIN_ETIQUETTE}")
    if lvl("charisma") < COURTIER_MIN_CHARISMA:
        missing.append(f"Charisma {COURTIER_MIN_CHARISMA}")
    if reputation.tier(getattr(session, "reputation", 0)) != COURTIER_TIER:
        missing.append(f"{COURTIER_TIER} standing")
    return not missing, missing


# ---- scheduling -----------------------------------------------------------------
def scheduled(conn, kinds=("crown", "acclaim", "castle")):
    q = ("SELECT id, kind, challenger_id, clan_id, castle_id, scheduled_at, status, warned, started_at "
         "FROM challenges WHERE status IN ('scheduled', 'active') AND kind IN (%s) ORDER BY scheduled_at"
         % ",".join("?" * len(kinds)))
    keys = ("id", "kind", "challenger_id", "clan_id", "castle_id", "scheduled_at", "status", "warned", "started_at")
    return [dict(zip(keys, r)) for r in conn.execute(q, kinds)]


def _check_hours(hours):
    try:
        h = int(hours)
    except (TypeError, ValueError):
        return None
    if h != float(hours) or not SCHEDULE_MIN_HOURS <= h <= SCHEDULE_MAX_HOURS:
        return None
    return h


def schedule_crown(session, conn, hours, now=None, quest_ids=None):
    import clans
    now = time.time() if now is None else float(now)
    h = _check_hours(hours)
    if h is None:
        return False, f"Pick a start {SCHEDULE_MIN_HOURS}–{SCHEDULE_MAX_HOURS} whole hours from now."
    if scheduled(conn, ("crown", "acclaim")):
        return False, "A challenge for the throne is already scheduled."
    if _cooldown(conn, session.player_id, "crown", now) > 0:
        return False, "You lost a Crown Challenge this week. Wait out your cooldown."
    st = state(conn)
    if st["monarch_kind"] == "player" and int(st["monarch_player_id"]) == int(session.player_id):
        return False, "You already wear the crown."
    ok, missing = crown_eligible(session, conn, quest_ids)
    if not ok:
        return False, "Not yet: " + "; ".join(missing)
    import politics
    fee = politics.crown_fee(conn, CROWN_FEE)
    if _bank(conn, session.player_id) < fee:
        return False, f"The challenge fee is {fee:,} from your bank."
    session.bank_coins = _bank_add(conn, session.player_id, -fee)
    royal_treasury.credit(conn, "crown_challenge", session.player_id, fee)
    politics.news(conn, "throne", f"{session.char_name} has called a Crown Challenge, {h} hours from now.", now)
    cid = clans.clan_of(session.player_id)
    conn.execute(
        "INSERT INTO challenges (kind, challenger_id, clan_id, castle_id, scheduled_at, status, created_at) "
        "VALUES ('crown', ?, ?, ?, ?, 'scheduled', ?)",
        (session.player_id, cid, KING_CASTLE_ID, now + h * HOUR, now),
    )
    log(conn, "crown_scheduled", session.player_id, f"{h}h", now)
    conn.commit()
    return True, h


def castle_fee(castle_id):
    """1% of the castle's deed price (never below CASTLE_FEE)."""
    try:
        import castle_owners
        deed = int((castle_owners.castle_row(castle_id) or {}).get("deed_price") or 0)
    except Exception:
        deed = 0
    return max(CASTLE_FEE, int(round(deed * CASTLE_FEE_RATE)))


def castle_cooldown(conn, castle_id, now):
    """Seconds until this castle may be challenged again (0 = free)."""
    row = conn.execute("SELECT MAX(scheduled_at) FROM challenges WHERE kind = 'castle' AND castle_id = ?",
                       (castle_id,)).fetchone()
    last = float(row[0]) if row and row[0] is not None else None
    return 0.0 if last is None else max(0.0, last + CASTLE_CHALLENGE_COOLDOWN - float(now))


def castle_fee(castle_id):
    """1% of the castle's deed price (never below CASTLE_FEE)."""
    try:
        import castle_owners
        deed = int((castle_owners.castle_row(castle_id) or {}).get("deed_price") or 0)
    except Exception:
        deed = 0
    return max(CASTLE_FEE, int(round(deed * CASTLE_FEE_RATE)))


def castle_cooldown(conn, castle_id, now):
    """Seconds until this castle may be challenged again (0 = free)."""
    row = conn.execute("SELECT MAX(scheduled_at) FROM challenges WHERE kind = 'castle' AND castle_id = ?",
                       (castle_id,)).fetchone()
    last = float(row[0]) if row and row[0] is not None else None
    return 0.0 if last is None else max(0.0, last + CASTLE_CHALLENGE_COOLDOWN - float(now))


def castle_fee(castle_id):
    """1% of the castle's deed price (never below CASTLE_FEE)."""
    try:
        import castle_owners
        deed = int((castle_owners.castle_row(castle_id) or {}).get("deed_price") or 0)
    except Exception:
        deed = 0
    return max(CASTLE_FEE, int(round(deed * CASTLE_FEE_RATE)))


def castle_cooldown(conn, castle_id, now):
    """Seconds until this castle may be challenged again (0 = free)."""
    row = conn.execute("SELECT MAX(scheduled_at) FROM challenges WHERE kind = 'castle' AND castle_id = ?",
                       (castle_id,)).fetchone()
    last = float(row[0]) if row and row[0] is not None else None
    return 0.0 if last is None else max(0.0, last + CASTLE_CHALLENGE_COOLDOWN - float(now))


def castle_fee(castle_id):
    """1% of the castle's deed price (never below CASTLE_FEE)."""
    try:
        import castle_owners
        deed = int((castle_owners.castle_row(castle_id) or {}).get("deed_price") or 0)
    except Exception:
        deed = 0
    return max(CASTLE_FEE, int(round(deed * CASTLE_FEE_RATE)))


def castle_cooldown(conn, castle_id, now):
    """Seconds until this castle may be challenged again (0 = free)."""
    row = conn.execute("SELECT MAX(scheduled_at) FROM challenges WHERE kind = 'castle' AND castle_id = ?",
                       (castle_id,)).fetchone()
    last = float(row[0]) if row and row[0] is not None else None
    return 0.0 if last is None else max(0.0, last + CASTLE_CHALLENGE_COOLDOWN - float(now))


def castle_fee(castle_id):
    """1% of the castle's deed price (never below CASTLE_FEE)."""
    try:
        import castle_owners
        deed = int((castle_owners.castle_row(castle_id) or {}).get("deed_price") or 0)
    except Exception:
        deed = 0
    return max(CASTLE_FEE, int(round(deed * CASTLE_FEE_RATE)))


def castle_cooldown(conn, castle_id, now):
    """Seconds until this castle may be challenged again (0 = free)."""
    row = conn.execute("SELECT MAX(scheduled_at) FROM challenges WHERE kind = 'castle' AND castle_id = ?",
                       (castle_id,)).fetchone()
    last = float(row[0]) if row and row[0] is not None else None
    return 0.0 if last is None else max(0.0, last + CASTLE_CHALLENGE_COOLDOWN - float(now))


def schedule_castle(session, conn, hours, now=None, owned_castles=None, all_castles=None):
    import clans
    now = time.time() if now is None else float(now)
    h = _check_hours(hours)
    if h is None:
        return False, f"Pick a start {SCHEDULE_MIN_HOURS}–{SCHEDULE_MAX_HOURS} whole hours from now."
    cid = clans.clan_of(session.player_id)
    if not cid or clans.rank_of(session.player_id) != "Leader":
        return False, "Only a guild Leader can challenge for a castle."
    row = conn.execute("SELECT challenge_castle_id FROM clans WHERE clan_id = ?", (cid,)).fetchone()
    castle = row[0] if row else None
    if not castle:
        return False, "Declare a castle first with /guild challenge <castle>."
    if castle == KING_CASTLE_ID or not clans.can_challenge_castle(cid, castle, owned_castles, all_castles):
        return False, "That castle can't be challenged (every non-King castle must be owned)."
    if any(c["castle_id"] == castle for c in scheduled(conn, ("castle",))):
        return False, "A challenge for that castle is already scheduled."
    wait = castle_cooldown(conn, castle, now)
    if wait > 0:
        days = max(1, int(-(-wait // DAY)))
        return False, f"That castle was challenged this week. It can be challenged again in {days} day{'s' if days != 1 else ''}."
    fee = castle_fee(castle)
    if _bank(conn, session.player_id) < fee:
        return False, f"The castle challenge fee is {fee:,} from your bank (1% of the deed)."
    session.bank_coins = _bank_add(conn, session.player_id, -fee)
    royal_treasury.credit(conn, "castle_challenge", session.player_id, fee)
    conn.execute(
        "INSERT INTO challenges (kind, challenger_id, clan_id, castle_id, scheduled_at, status, created_at) "
        "VALUES ('castle', ?, ?, ?, ?, 'scheduled', ?)",
        (session.player_id, cid, castle, now + h * HOUR, now),
    )
    conn.commit()
    return True, h


def schedule_acclaim(session, conn, hours, now=None):
    now = time.time() if now is None else float(now)
    ok, missing = courtier_eligible(session, conn)
    if not ok:
        return False, ("Not yet: " + "; ".join(missing)) if missing else "The court does not receive you."
    h = _check_hours(hours)
    if h is None:
        return False, f"Pick a time {SCHEDULE_MIN_HOURS}–{SCHEDULE_MAX_HOURS} whole hours from now."
    fav = favour_row(conn, session.player_id)
    if fav["favour"] < FAVOUR_MAX:
        return False, f"You need {FAVOUR_MAX} Court Favour (you have {fav['favour']})."
    if fav["cooldown_until"] and float(fav["cooldown_until"]) > now:
        return False, "The court will not hear you again this week."
    if scheduled(conn, ("crown", "acclaim")):
        return False, "A challenge for the throne is already scheduled."
    if _bank(conn, session.player_id) < ACCLAIM_FEE:
        return False, f"The Acclaim costs {ACCLAIM_FEE:,} from your bank."
    session.bank_coins = _bank_add(conn, session.player_id, -ACCLAIM_FEE)
    royal_treasury.credit(conn, "court_acclaim", session.player_id, ACCLAIM_FEE)
    conn.execute(
        "INSERT INTO challenges (kind, challenger_id, clan_id, castle_id, scheduled_at, status, created_at) "
        "VALUES ('acclaim', ?, NULL, ?, ?, 'scheduled', ?)",
        (session.player_id, KING_CASTLE_ID, now + h * HOUR, now),
    )
    conn.commit()
    return True, h


# ---- battles --------------------------------------------------------------------
def window_for(kind):
    return CROWN_WINDOW if kind == "crown" else CASTLE_WINDOW


def new_battle(challenge, now):
    return {"id": challenge["id"], "kind": challenge["kind"], "start": float(now),
            "end": float(now) + window_for(challenge["kind"]), "hold": 0.0, "last": float(now)}


def step_battle(b, now, captain_dead, challengers, defenders):
    """Pure per-check update. Returns None (ongoing), 'win' or 'loss'."""
    dt = max(0.0, float(now) - b["last"])
    b["last"] = float(now)
    if captain_dead and challengers > defenders:
        b["hold"] += dt
    else:
        b["hold"] = 0.0
    if b["hold"] >= HOLD_SECONDS:
        return "win"
    if now >= b["end"]:
        return "loss"
    return None


def start(conn, challenge_id, now):
    conn.execute("UPDATE challenges SET status = 'active', started_at = ? WHERE id = ?", (now, challenge_id))
    conn.commit()


def _finish(conn, challenge_id, result, now):
    conn.execute("UPDATE challenges SET status = 'done', resolved_at = ?, result = ? WHERE id = ?",
                 (now, result, challenge_id))
    conn.commit()
    try:
        import politics
        row = conn.execute("SELECT kind FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
        kind = {"crown": "Crown Challenge", "acclaim": "Acclamation", "castle": "castle challenge"}.get(
            row[0] if row else "", "challenge")
        politics.news(conn, "throne", f"The {kind} ends: the challenger {'wins' if result == 'win' else 'falls'}.", now)
    except Exception:
        pass


def remove_castle_deed(conn, pid, castle_id):
    conn.execute("DELETE FROM castle_ownership WHERE castle_id = ? AND owner_account_id = ?", (castle_id, pid))
    conn.commit()


def resolve_crown(conn, challenge, result, now):
    """Apply a Crown Challenge outcome. Returns a dict describing it."""
    pid = int(challenge["challenger_id"])
    _finish(conn, challenge["id"], result, now)
    if result == "win":
        titles = _crown(conn, pid, "conquest", "imprisoned", now)
        return {"result": "win", "titles": titles}
    lost = _castle_owned_by(conn, pid)
    for castle in lost[:1]:
        remove_castle_deed(conn, pid, castle)
    _set_cooldown(conn, pid, "crown", now + LOSS_COOLDOWN)
    log(conn, "crown_lost", pid, ",".join(lost[:1]), now)
    conn.commit()
    return {"result": "loss", "castle_lost": lost[0] if lost else None}


def resolve_castle(conn, challenge, result, now, name=None):
    pid = int(challenge["challenger_id"])
    castle = challenge["castle_id"]
    _finish(conn, challenge["id"], result, now)
    if result == "win":
        conn.execute("UPDATE castle_ownership SET owner_account_id = ?, owner_display_name = ?, purchased_at = ? "
                     "WHERE castle_id = ?", (pid, name or "Owner", now, castle))
        log(conn, "castle_won", pid, castle, now)
        conn.commit()
    return {"result": result, "castle": castle}


ACCLAIM_TIE_MOOD = 50            # a tie wins while the kingdom mood is below this...
ACCLAIM_TIE_HOUSES = 2           # ...or while at least this many great houses oppose the Crown


def acclaim_tie_break(conn):
    """Reputation saturates at 1000, so a tie goes to the challenger when the realm has turned."""
    try:
        import politics
        if politics.mood(conn) < ACCLAIM_TIE_MOOD:
            return True
        return sum(1 for s in politics.stances(conn).values() if s <= politics.OPPOSING_AT) >= ACCLAIM_TIE_HOUSES
    except Exception:
        return False


ACCLAIM_TIE_MOOD = 50            # a tie wins while the kingdom mood is below this...
ACCLAIM_TIE_HOUSES = 2           # ...or while at least this many great houses oppose the Crown


def acclaim_tie_break(conn):
    """Reputation saturates at 1000, so a tie goes to the challenger when the realm has turned."""
    try:
        import politics
        if politics.mood(conn) < ACCLAIM_TIE_MOOD:
            return True
        return sum(1 for s in politics.stances(conn).values() if s <= politics.OPPOSING_AT) >= ACCLAIM_TIE_HOUSES
    except Exception:
        return False


ACCLAIM_TIE_MOOD = 50            # a tie wins while the kingdom mood is below this...
ACCLAIM_TIE_HOUSES = 2           # ...or while at least this many great houses oppose the Crown


def acclaim_tie_break(conn):
    """Reputation saturates at 1000, so a tie goes to the challenger when the realm has turned."""
    try:
        import politics
        if politics.mood(conn) < ACCLAIM_TIE_MOOD:
            return True
        return sum(1 for s in politics.stances(conn).values() if s <= politics.OPPOSING_AT) >= ACCLAIM_TIE_HOUSES
    except Exception:
        return False


ACCLAIM_TIE_MOOD = 50            # a tie wins while the kingdom mood is below this...
ACCLAIM_TIE_HOUSES = 2           # ...or while at least this many great houses oppose the Crown


def acclaim_tie_break(conn):
    """Reputation saturates at 1000, so a tie goes to the challenger when the realm has turned."""
    try:
        import politics
        if politics.mood(conn) < ACCLAIM_TIE_MOOD:
            return True
        return sum(1 for s in politics.stances(conn).values() if s <= politics.OPPOSING_AT) >= ACCLAIM_TIE_HOUSES
    except Exception:
        return False


ACCLAIM_TIE_MOOD = 50            # a tie wins while the kingdom mood is below this...
ACCLAIM_TIE_HOUSES = 2           # ...or while at least this many great houses oppose the Crown


def acclaim_tie_break(conn):
    """Reputation saturates at 1000, so a tie goes to the challenger when the realm has turned."""
    try:
        import politics
        if politics.mood(conn) < ACCLAIM_TIE_MOOD:
            return True
        return sum(1 for s in politics.stances(conn).values() if s <= politics.OPPOSING_AT) >= ACCLAIM_TIE_HOUSES
    except Exception:
        return False


def resolve_acclaim(conn, challenge, now):
    pid = int(challenge["challenger_id"])
    st = state(conn)
    if st["monarch_kind"] == "npc":
        ok = True
    else:
        mine = int(_player_field(conn, pid, "reputation", 0) or 0)
        theirs = int(_player_field(conn, st["monarch_player_id"], "reputation", 0) or 0)
        ok = mine > theirs or (mine >= theirs and acclaim_tie_break(conn)) or (mine >= theirs and acclaim_tie_break(conn)) or (mine >= theirs and acclaim_tie_break(conn)) or (mine >= theirs and acclaim_tie_break(conn)) or (mine >= theirs and acclaim_tie_break(conn))
    _finish(conn, challenge["id"], "win" if ok else "loss", now)
    if ok:
        titles = _crown(conn, pid, "courtier", "exiled", now)
        return {"result": "win", "titles": titles}
    favour_row(conn, pid)
    conn.execute("UPDATE court_favour SET favour = ?, cooldown_until = ? WHERE player_id = ?",
                 (ACCLAIM_FAIL_FAVOUR, now + ACCLAIM_FAIL_COOLDOWN, pid))
    conn.commit()
    return {"result": "loss"}


# ---- Court Favour ----------------------------------------------------------------
def _day(now):
    return time.strftime("%Y-%m-%d", time.localtime(now))


def _week(now):
    return time.strftime("%G-W%V", time.localtime(now))


def favour_row(conn, pid):
    conn.execute("INSERT OR IGNORE INTO court_favour (player_id, favour, tasks_done) VALUES (?, 0, 0)", (pid,))
    row = conn.execute("SELECT favour, tasks_day, tasks_done, last_ball_week, cooldown_until, penalty_day "
                       "FROM court_favour WHERE player_id = ?", (pid,)).fetchone()
    return dict(zip(("favour", "tasks_day", "tasks_done", "last_ball_week", "cooldown_until", "penalty_day"), row))


def add_favour(conn, pid, delta):
    f = favour_row(conn, pid)["favour"]
    new = max(0, min(FAVOUR_MAX, int(f) + int(delta)))
    conn.execute("UPDATE court_favour SET favour = ? WHERE player_id = ?", (new, pid))
    conn.commit()
    return new


def court_task(conn, pid, now=None):
    """One daily task. Returns gained favour (0 when today's 3 are done)."""
    now = time.time() if now is None else now
    f = favour_row(conn, pid)
    day = _day(now)
    done = int(f["tasks_done"] or 0) if f["tasks_day"] == day else 0
    if done >= TASKS_PER_DAY:
        return 0
    conn.execute("UPDATE court_favour SET tasks_day = ?, tasks_done = ? WHERE player_id = ?", (day, done + 1, pid))
    before = f["favour"]
    return add_favour(conn, pid, FAVOUR_TASK) - before


def ball_open(now):
    lt = time.localtime(now)
    start_ = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, BALL_HOUR, 0, 0, 0, 0, -1))
    return lt.tm_wday == BALL_WEEKDAY and start_ <= now < start_ + BALL_SECONDS


def ball_attend(conn, pid, now=None):
    now = time.time() if now is None else now
    if not ball_open(now):
        return 0
    f = favour_row(conn, pid)
    wk = _week(now)
    if f["last_ball_week"] == wk:
        return 0
    conn.execute("UPDATE court_favour SET last_ball_week = ? WHERE player_id = ?", (wk, pid))
    before = f["favour"]
    return add_favour(conn, pid, FAVOUR_BALL) - before


def standing_penalty(conn, session, now=None):
    """−50 once a day while a courtier's standing is Neutral or worse."""
    import reputation
    now = time.time() if now is None else now
    if str(getattr(session, "gender", "")).lower() != "female":
        return 0
    row = conn.execute("SELECT penalty_day FROM court_favour WHERE player_id = ?", (session.player_id,)).fetchone()
    if row is None or reputation.tier(getattr(session, "reputation", 0)) not in PENALTY_TIERS:
        return 0
    if row[0] == _day(now):
        return 0
    conn.execute("UPDATE court_favour SET penalty_day = ? WHERE player_id = ?", (_day(now), session.player_id))
    before = favour_row(conn, session.player_id)["favour"]
    return add_favour(conn, session.player_id, FAVOUR_PENALTY) - before


# ---- marriage ------------------------------------------------------------------------
def propose(a_id, b_id, now=None):
    now = time.time() if now is None else now
    _PROPOSALS[int(b_id)] = (int(a_id), now + PROPOSAL_SECONDS)


def pending_proposal(b_id, now=None):
    now = time.time() if now is None else now
    p = _PROPOSALS.get(int(b_id))
    if not p or p[1] < now:
        _PROPOSALS.pop(int(b_id), None)
        return None
    return p[0]


def marry(conn, a_id, b_id, now=None):
    """Returns (ok, message). Charges 5,000 to each bank."""
    now = time.time() if now is None else now
    half = MARRIAGE_FEE // 2
    for pid in (a_id, b_id):
        if spouse_of(conn, pid):
            return False, "One of you is already married."
        if _cooldown(conn, pid, "marriage", now) > 0:
            return False, "One of you divorced this week. The Chaplain asks you to wait."
    if int(a_id) == int(b_id):
        return False, "You cannot marry yourself."
    if _bank(conn, a_id) < half or _bank(conn, b_id) < half:
        return False, f"Each of you needs {half:,} in the bank for the ceremony."
    _bank_add(conn, a_id, -half)
    _bank_add(conn, b_id, -half)
    royal_treasury.credit(conn, "marriage_fee", a_id, half)
    royal_treasury.credit(conn, "marriage_fee", b_id, half)
    conn.execute("INSERT INTO marriages (a_id, b_id, married_at) VALUES (?, ?, ?)", (a_id, b_id, now))
    conn.commit()
    _PROPOSALS.pop(int(b_id), None)
    apply_titles(conn)
    return True, "You are wed."


def divorce(conn, pid, now=None):
    now = time.time() if now is None else now
    sp = spouse_of(conn, pid)
    if not sp:
        return False, "You are not married."
    conn.execute("UPDATE marriages SET divorced_at = ? WHERE divorced_at IS NULL AND (a_id = ? OR b_id = ?)",
                 (now, pid, pid))
    for p in (pid, sp):
        _set_cooldown(conn, p, "marriage", now + DIVORCE_COOLDOWN)
    conn.commit()
    apply_titles(conn)
    return True, "The marriage is dissolved."


# ---- reboot ------------------------------------------------------------------------------
def reload(conn, now=None):
    """Active challenges restart their window from the reboot time. Returns battles dict."""
    now = time.time() if now is None else now
    battles = {}
    for c in scheduled(conn):
        if c["status"] == "active":
            start(conn, c["id"], now)
            battles[c["id"]] = new_battle(c, now)
    return battles


def summary_lines(conn, name_of=lambda pid: f"#{pid}"):
    st = state(conn)
    mon = "the NPC King" if st["monarch_kind"] == "npc" else name_of(st["monarch_player_id"])
    lines = [f"Monarch: {mon} · path {st['path'] or 'inheritance'} · old King: {st['old_king_state']}"]
    nxt = scheduled(conn)
    if nxt:
        for c in nxt[:3]:
            when = max(0, int((c["scheduled_at"] - time.time()) // 60))
            lines.append(f"{c['kind'].title()} by {name_of(c['challenger_id'])} at {c['castle_id']}: "
                         + ("under way" if c["status"] == "active" else f"in {when // 60}h {when % 60}m"))
    else:
        lines.append("No challenges scheduled.")
    return lines


def can_challenge_king(clan_id):
    """The King's Castle is never a castle challenge; the throne goes through the Crown Challenge."""
    return False


# Castle id -> plane used as its keep for a single castle challenge
CASTLE_KEEP_PLANE = {"gothic": "gothic_f1", "white_rose": "rose_f1", "sky_anchor": "sky_f1"}
