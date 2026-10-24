"""Crownfall phase 9: living politics - kingdom mood, noble houses, court events and news.

Every number lives here. Mood and house stances belong to the kingdom (realm_settings / houses),
so they survive a change of throne. Event costs go through ruling.spend() (or the same cap and
spendable checks for the NPC King), so the treasury never goes below 0.
"""
import random
import time

DAY = 86400
HOUR = 3600

# ---- mood -------------------------------------------------------------------------------------
MOOD_START = 60
MOOD_MIN, MOOD_MAX = 0, 100
BANDS = (("Revolt", 0, 14), ("Unrest", 15, 34), ("Calm", 35, 64), ("Content", 65, 84), ("Prosperous", 85, 100))
TAX_PIVOT_PCT = 5
TAX_DRIFT_PER_PCT = 1.0
FEE_DRIFT = 5            # -1 * (ratio - 1) * 5: double fees = -5, half = +2.5
FEE_DRIFT_MULT = 1
WORK_DRIFT = 1
BOUNTY_DRIFT = 1
BOUNTY_DRIFT_MAX = 3
BATTLE_DRIFT = -3
PEACE_DRIFT = 0.5
PULL_TARGET = 50
PULL_RATE = 0.15
HOUSE_BACK_DRIFT = 1
HOUSE_OPPOSE_DRIFT = -1

CROWN_DISCOUNT = {"Revolt": 0.50, "Unrest": 0.25}
OPPOSE_CROWN_DISCOUNT = 0.10
CROWN_DISCOUNT_CAP = 0.50
SHIFT_INCOME_MULT = {"Content": 1.05, "Prosperous": 1.10}
SALES_TAX_RAISE_MULT = {"Content": 1.05, "Prosperous": 1.05}
RESTOCK_MULT = {"Revolt": 0.5}           # no shop restock system exists yet; read by restock_mult()
PROSPERITY_RATE = 0.01
PROSPERITY_MAX = 10_000
RAID_EVERY_DAYS = {"Revolt": 1, "Unrest": 2}
PROTEST_BANDS = ("Revolt", "Unrest")

# ---- houses -----------------------------------------------------------------------------------
HOUSES = {
    "valcrest": "House Valcrest",
    "thornmere": "House Thornmere",
    "ironhold": "House Ironhold",
    "commons": "The Commons",
}
HOUSE_BLURB = {
    "valcrest": "The old nobility. They want low land fees and the old King treated with honour.",
    "thornmere": "The merchant houses. They want a low sales tax and well-stocked markets.",
    "ironhold": "The military. They want bounties paid and the throne defended.",
    "commons": "The people's guild. They want a happy kingdom and public works.",
}
STANCE_MIN, STANCE_MAX = -100, 100
STANCE_DAILY = 5
BACKING_AT = 40
OPPOSING_AT = -40
PLEDGE_COOLDOWN = 7 * DAY
ERRAND_FAVOUR = 10
ERRAND_REP = 2
ERRAND_CHARISMA = 100        # once a day, with the errand
ERRAND_CHARISMA = 100        # once a day, with the errand
ERRAND_CHARISMA = 100        # once a day, with the errand
ERRAND_CHARISMA = 100        # once a day, with the errand
ERRAND_CHARISMA = 100        # once a day, with the errand
ERRAND_COINS = 200
FAVOUR_MAX = 500
SUPPORT_STEP = 1
# Errand: hand the envoy a few common items (existing items only)
ERRANDS = {
    "valcrest": ("bread", 3, "three loaves of bread for the old household"),
    "thornmere": ("bronze_bar", 2, "two bronze bars for the merchants' scales"),
    "ironhold": ("bones", 5, "five bones from the field, proof of a patrol"),
    "commons": ("logs", 5, "five logs for the people's hearths"),
}
# favour -> suffix format
TITLE_TIERS = ((500, "Champion of {h}"), (250, "Sworn of {h}"), (100, "of {h}"))

# ---- court events -----------------------------------------------------------------------------
EVENT_CHANCE = 0.60
NO_REPEAT = 3
CHANCELLOR_AFTER = 12 * HOUR
AUTO_IGNORE_AFTER = 24 * HOUR
IRONHOLD_BOUNTY_DAYS = 2
IRONHOLD_FAIL = -10
RAID_TYPES = ("goblin",)
EVENT_BOUNTY = 10_000

# choice fields: id, label, cost, mood, houses{key:delta}, rep (monarch), tax_cut, free_king,
# bounty, raid (days from now), ironhold_check
EVENTS = [
    {"key": "flood", "title": "Flooded farms",
     "text": "The river has burst its banks and the farms are under water.",
     "choices": [{"id": "relief", "label": "Send relief", "cost": 20_000, "mood": 5, "houses": {"commons": 10}},
                 {"id": "ignore", "label": "Ignore", "mood": -5, "houses": {"commons": -10}}]},
    {"key": "tax_break", "title": "Merchant guild asks for a tax break",
     "text": "House Thornmere asks for one point off the sales tax.",
     "choices": [{"id": "grant", "label": "Grant (-1 point sales tax)", "tax_cut": 0.01, "houses": {"thornmere": 15}},
                 {"id": "refuse", "label": "Refuse", "houses": {"thornmere": -10}},
                 {"id": "ignore", "label": "Ignore", "houses": {"thornmere": -5}}]},
    {"key": "valcrest_release", "title": "Valcrest demands the old King's release",
     "text": "House Valcrest demands the old King be set free.",
     "choices": [{"id": "free", "label": "Free him", "free_king": True, "mood": 3, "houses": {"valcrest": 25}},
                 {"id": "refuse", "label": "Refuse", "houses": {"valcrest": -15}},
                 {"id": "ignore", "label": "Ignore", "houses": {"valcrest": -10}}]},
    {"key": "bandits", "title": "Bandits on the King's Road",
     "text": "Raiders are robbing travellers on the King's Road.",
     "choices": [{"id": "bounty", "label": "Post a 10,000 bounty", "bounty": EVENT_BOUNTY, "houses": {"ironhold": 10}},
                 {"id": "guards", "label": "Hire guards", "cost": 15_000, "mood": 3, "houses": {"ironhold": 5}},
                 {"id": "ignore", "label": "Ignore", "raid": 1, "mood": -3}]},
    {"key": "harvest", "title": "Harvest festival",
     "text": "The villages ask the Crown to fund a harvest festival.",
     "choices": [{"id": "fund", "label": "Fund it", "cost": 25_000, "mood": 8, "houses": {"commons": 10}, "rep": 5},
                 {"id": "ignore", "label": "Ignore"}]},
    {"key": "pardon", "title": "A noble petitions for a royal pardon",
     "text": "A Valcrest cousin, jailed for brawling, begs a royal pardon.",
     "choices": [{"id": "pardon", "label": "Pardon", "mood": -3, "houses": {"valcrest": 10, "ironhold": -10}},
                 {"id": "refuse", "label": "Refuse", "houses": {"ironhold": 5}},
                 {"id": "ignore", "label": "Ignore"}]},
    {"key": "plague", "title": "Plague rumours",
     "text": "Whispers of plague spread through the lower town.",
     "choices": [{"id": "healers", "label": "Hire healers", "cost": 30_000, "mood": 4},
                 {"id": "ignore", "label": "Ignore", "mood": -6, "houses": {"commons": -10}}]},
    {"key": "ironhold_bounties", "title": "Ironhold wants more bounties",
     "text": "House Ironhold wants a bounty posted within two days.",
     "choices": [{"id": "accept", "label": "Accept", "houses": {"ironhold": 10}, "ironhold_check": True},
                 {"id": "refuse", "label": "Refuse", "houses": {"ironhold": -10}}]},
]
EVENT_BY_KEY = {e["key"]: e for e in EVENTS}

# ---- news, raids, live NPCs -------------------------------------------------------------------
NEWS_KEEP = 100
NEWS_BOARD_LINES = 10
NEWS_CMD_LINES = 5
CRIER_EVERY = 600
CRIER_RANGE = 15
RAID_MINUTES = 30
RAID_SIZE = (4, 6)
RAID_REP = 1
RAID_REP_DAILY_MAX = 5
RAID_POINTS = {"north_road": (60, 40), "east_road": (100, 60), "south_road": (40, 80)}
PROTESTER_SPOTS = ((128, 61), (128, 63), (128, 65))
PROTESTER_NAMES = ("Angry Farmer", "Angry Tanner", "Angry Weaver")
CRIERS = ({"id": "crier_square", "name": "Town Crier Hob", "x": 131, "y": 64},
          {"id": "crier_village", "name": "Town Crier Nell", "x": 25, "y": 19})
# Starter-village board only — wayfinder signposts were removed from the overworld.
BOARDS = ({"id": "notice_board_village", "x": 27, "y": 19},)


def _follow_castle():
    """Protesters and the castle crier stand in the keep's bailey (pack space)."""
    global PROTESTER_SPOTS
    try:
        import castle_v2
        if not castle_v2.active():
            return
    except Exception:
        return
    PROTESTER_SPOTS = tuple(castle_v2.w(px, py) for px, py in ((111, 48), (112, 49), (110, 50)))
    for item in CRIERS + BOARDS:
        if item["id"] == "crier_square":
            item["x"], item["y"] = castle_v2.w(115, 50)


_follow_castle()

# Spread around Stonehaven (east ward after the massif slid west).
ENVOYS = ({"id": "envoy_valcrest", "house": "valcrest", "name": "Lady Ismay, Valcrest Envoy", "x": 152, "y": 64},
          {"id": "envoy_thornmere", "house": "thornmere", "name": "Master Corvin, Thornmere Envoy", "x": 116, "y": 76},
          {"id": "envoy_ironhold", "house": "ironhold", "name": "Captain Brand, Ironhold Envoy", "x": 140, "y": 98},
          {"id": "envoy_commons", "house": "commons", "name": "Goodwife Tansy, Commons Envoy", "x": 122, "y": 74})
ENVOY_OPTIONS = [
    {"id": "house_pledge", "label": "Pledge to this house"},
    {"id": "house_errand", "label": "Daily errand"},
    {"id": "house_support", "label": "Support the Crown"},
    {"id": "house_oppose", "label": "Oppose the Crown"},
    {"id": "house_standing", "label": "House standing"},
]


def _conn_default(conn):
    if conn is not None:
        return conn
    import royal_treasury
    return royal_treasury._SETTINGS_CONN


def _now(now):
    return time.time() if now is None else float(now)


def _day(now):
    return time.strftime("%Y-%m-%d", time.localtime(now))


def _get(conn, key, default=None):
    try:
        row = conn.execute("SELECT value FROM realm_settings WHERE key = ?", (key,)).fetchone()
    except Exception:
        return default
    return default if row is None or row[0] is None else row[0]


def _put(conn, key, value, now=None):
    conn.execute("INSERT OR REPLACE INTO realm_settings (key, value, changed_at) VALUES (?, ?, ?)",
                 (key, value, _now(now)))


# ---- schema -----------------------------------------------------------------------------------
def ensure_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS realm_settings (key TEXT PRIMARY KEY, value REAL, changed_at REAL, "
                 "changed_by INTEGER)")
    conn.execute("INSERT OR IGNORE INTO realm_settings (key, value) VALUES ('mood', ?)", (MOOD_START,))
    conn.execute("CREATE TABLE IF NOT EXISTS houses (key TEXT PRIMARY KEY, name TEXT, stance INTEGER DEFAULT 0)")
    for k, n in HOUSES.items():
        conn.execute("INSERT OR IGNORE INTO houses (key, name, stance) VALUES (?, ?, 0)", (k, n))
    conn.execute("CREATE TABLE IF NOT EXISTS house_pledges (player_id INTEGER PRIMARY KEY, house_key TEXT, "
                 "favour INTEGER DEFAULT 0, pledged_at REAL, errand_day TEXT, support_day TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS court_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT, "
                 "opened_at REAL, resolved_at REAL NULL, choice TEXT NULL, resolved_by INTEGER NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS politics_news (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
                 "kind TEXT, text TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS raids (id INTEGER PRIMARY KEY AUTOINCREMENT, spawn_point TEXT, "
                 "started_at REAL, ends_at REAL, status TEXT)")
    conn.commit()


# ---- news -------------------------------------------------------------------------------------
def news(conn, kind, text, now=None):
    try:
        conn.execute("SELECT 1 FROM politics_news LIMIT 1")
    except Exception:
        return
    conn.execute("INSERT INTO politics_news (ts, kind, text) VALUES (?, ?, ?)", (_now(now), kind, str(text)[:200]))
    conn.execute("DELETE FROM politics_news WHERE id NOT IN (SELECT id FROM politics_news ORDER BY id DESC LIMIT ?)",
                 (NEWS_KEEP,))
    conn.commit()


def latest_news(conn, n=NEWS_CMD_LINES):
    rows = conn.execute("SELECT ts, text FROM politics_news ORDER BY id DESC LIMIT ?", (int(n),)).fetchall()
    return [f"[{time.strftime('%d %b %H:%M', time.localtime(ts))}] {t}" for ts, t in rows]


# ---- mood -------------------------------------------------------------------------------------
def mood(conn=None):
    conn = _conn_default(conn)
    if conn is None:
        return MOOD_START
    return float(_get(conn, "mood", MOOD_START))


def band_of(value):
    v = int(round(float(value)))
    for name, lo, hi in BANDS:
        if lo <= v <= hi:
            return name
    return "Revolt" if v < 0 else "Prosperous"


def mood_band(conn=None):
    return band_of(mood(conn))


def set_mood(conn, value, now=None):
    v = max(MOOD_MIN, min(MOOD_MAX, float(value)))
    _put(conn, "mood", v, now)
    conn.commit()
    return v


def adjust_mood(conn, delta, now=None):
    before = mood_band(conn)
    v = set_mood(conn, mood(conn) + float(delta), now)
    after = band_of(v)
    if after != before:
        news(conn, "mood", f"The kingdom's mood turns: {before} to {after} ({int(round(v))}).", now)
    return v


def shift_income_mult(conn=None):
    try:
        return SHIFT_INCOME_MULT.get(mood_band(conn), 1.0)
    except Exception:
        return 1.0


def sales_tax_mult(conn=None):
    try:
        return SALES_TAX_RAISE_MULT.get(mood_band(conn), 1.0)
    except Exception:
        return 1.0


def restock_mult(conn=None):
    try:
        return RESTOCK_MULT.get(mood_band(conn), 1.0)
    except Exception:
        return 1.0


def crown_discount(conn):
    d = CROWN_DISCOUNT.get(mood_band(conn), 0.0)
    d += OPPOSE_CROWN_DISCOUNT * sum(1 for _k, s in stances(conn).items() if s <= OPPOSING_AT)
    return min(CROWN_DISCOUNT_CAP, d)


def crown_fee(conn, base):
    return int(round(int(base) * (1 - crown_discount(conn))))


# ---- houses -----------------------------------------------------------------------------------
def stances(conn):
    try:
        rows = conn.execute("SELECT key, stance FROM houses").fetchall()
    except Exception:          # schema not set up (older test databases)
        return {}
    return {k: int(s) for k, s in rows}


def stance_band(s):
    return "Backing" if s >= BACKING_AT else "Opposing" if s <= OPPOSING_AT else "Neutral"


def adjust_stance(conn, key, delta, now=None):
    if key not in HOUSES or not delta:
        return
    old = stances(conn).get(key, 0)
    new = max(STANCE_MIN, min(STANCE_MAX, old + int(delta)))
    conn.execute("UPDATE houses SET stance = ? WHERE key = ?", (new, key))
    conn.commit()
    if stance_band(new) != stance_band(old):
        news(conn, "house", f"{HOUSES[key]} is now {stance_band(new)} the Crown ({new:+d}).", now)


def _bounties_today(conn, now):
    return int(_get(conn, f"politics:bounties:{_day(now)}", 0) or 0)


def note_bounty_paid(conn, now=None):
    now = _now(now)
    _put(conn, f"politics:bounties:{_day(now)}", _bounties_today(conn, now) + 1, now)
    conn.commit()


def _battles_today(conn, now):
    """Crown Challenge battles in the last day: (count, defended)."""
    try:
        rows = conn.execute("SELECT result FROM challenges WHERE kind IN ('crown', 'acclaim') AND status = 'done' "
                            "AND resolved_at > ? AND resolved_at <= ?", (now - DAY, now)).fetchall()
    except Exception:
        return 0, False
    return len(rows), any(r[0] == "loss" for r in rows)


def _fee_ratio(conn):
    import ruling
    keys = [k for k in ruling.SETTINGS if k.startswith("land_fee_")]
    return sum(float(ruling.get_setting(conn, k)) / ruling.SETTINGS[k][0] for k in keys) / len(keys)


def _active_works(conn, now):
    import ruling
    return [k for k in ruling.PUBLIC_WORKS if ruling.work_active(conn, k, now)]


def _old_king_state(conn):
    try:
        row = conn.execute("SELECT old_king_state FROM throne WHERE id = 1").fetchone()
    except Exception:
        return "reigning"
    return row[0] if row and row[0] else "reigning"


def drift(conn, now=None, unpaid_stipends=0):
    """[(label, value)] for the coming daily tick."""
    import ruling
    now = _now(now)
    m = mood(conn)
    rate = float(ruling.get_setting(conn, "sales_tax")) * 100
    out = [("Sales tax", (TAX_PIVOT_PCT - rate) * TAX_DRIFT_PER_PCT),
           ("Land fees", -FEE_DRIFT_MULT * (_fee_ratio(conn) - 1) * FEE_DRIFT)]
    works = _active_works(conn, now)
    if works:
        out.append(("Public works", WORK_DRIFT * len(works)))
    b = min(BOUNTY_DRIFT_MAX, BOUNTY_DRIFT * _bounties_today(conn, now))
    if b:
        out.append(("Bounties paid", b))
    battles, _def = _battles_today(conn, now)
    if battles:
        out.append(("Crown Challenge", BATTLE_DRIFT))
    elif not unpaid_stipends:
        out.append(("Peaceful day", PEACE_DRIFT))
    st = stances(conn)
    back = sum(1 for s in st.values() if s >= BACKING_AT)
    opp = sum(1 for s in st.values() if s <= OPPOSING_AT)
    if back:
        out.append(("Houses backing", HOUSE_BACK_DRIFT * back))
    if opp:
        out.append(("Houses opposing", HOUSE_OPPOSE_DRIFT * opp))
    out.append(("Pull to the middle", (PULL_TARGET - m) * PULL_RATE))
    return [(k, round(v, 2)) for k, v in out if abs(v) > 1e-9]


def _house_drift(conn, now):
    import ruling
    rate = float(ruling.get_setting(conn, "sales_tax"))
    default_rate = ruling.SETTINGS["sales_tax"][0]
    fee = _fee_ratio(conn)
    battles, defended = _battles_today(conn, now)
    m = mood(conn)
    works = _active_works(conn, now)
    score = {
        "valcrest": (fee < 0.999) - (fee > 1.001) - (_old_king_state(conn) in ("imprisoned", "exiled")),
        "thornmere": (rate < default_rate - 1e-9) - (rate > default_rate + 1e-9) + ("markets" in works),
        "ironhold": (_bounties_today(conn, now) > 0) + (1 if defended else 0) - (1 if battles and not defended else 0),
        "commons": (m >= 65) - (m <= 34) + (1 if works else 0),
    }
    for k, s in score.items():
        if s:
            adjust_stance(conn, k, STANCE_DAILY if s > 0 else -STANCE_DAILY, now)


def daily_mood_tick(conn, now=None, unpaid_stipends=0, rng=None):
    """Once per daily tick: drift, clamp, band news, band effects, house drift, Ironhold check, event roll."""
    import royal_treasury
    import ruling
    now = _now(now)
    parts = drift(conn, now, unpaid_stipends)
    before = mood_band(conn)
    v = set_mood(conn, mood(conn) + sum(p for _l, p in parts), now)
    band = band_of(v)
    _put(conn, "politics:last_drift", sum(p for _l, p in parts), now)
    if band != before:
        news(conn, "mood", f"The kingdom's mood turns: {before} to {band} ({int(round(v))}).", now)
    if band == "Prosperous":
        grant = min(PROSPERITY_MAX, int(royal_treasury.balance(conn) * PROSPERITY_RATE))
        if grant > 0:
            royal_treasury.credit(conn, "prosperity", None, grant)
            ruling.audit(conn, None, "Kingdom", "prosperity", grant, "daily prosperity grant", now)
            conn.commit()
            news(conn, "treasury", f"A prosperous kingdom: the treasury gains {grant:,} coins.", now)
    every = RAID_EVERY_DAYS.get(band)
    if every:
        last = float(_get(conn, "politics:last_raid", 0) or 0)
        if now - last >= every * DAY - HOUR:
            schedule_raid(conn, now, rng=rng)
    _house_drift(conn, now)
    due = float(_get(conn, "politics:ironhold_due", 0) or 0)
    if due and now >= due:
        since = due - IRONHOLD_BOUNTY_DAYS * DAY
        n = conn.execute("SELECT COUNT(*) FROM bounties WHERE posted_at >= ?", (since,)).fetchone()[0]
        if not n:
            adjust_stance(conn, "ironhold", IRONHOLD_FAIL, now)
            news(conn, "house", "No bounty was posted as promised. House Ironhold is displeased.", now)
        _put(conn, "politics:ironhold_due", 0, now)
    conn.commit()
    ev = roll_event(conn, now, rng)
    return v, band, parts, ev


# ---- raids ------------------------------------------------------------------------------------
def schedule_raid(conn, now=None, delay=0, rng=None):
    now = _now(now)
    rng = rng or random
    if conn.execute("SELECT COUNT(*) FROM raids WHERE status IN ('pending', 'active')").fetchone()[0]:
        return None
    point = rng.choice(sorted(RAID_POINTS))
    start = now + delay
    cur = conn.execute("INSERT INTO raids (spawn_point, started_at, ends_at, status) VALUES (?, ?, ?, 'pending')",
                       (point, start, start + RAID_MINUTES * 60))
    _put(conn, "politics:last_raid", now, now)
    conn.commit()
    return cur.lastrowid


def raid_size(raid_id):
    lo, hi = RAID_SIZE
    return lo + int(raid_id) % (hi - lo + 1)


def open_raids(conn):
    return conn.execute("SELECT id, spawn_point, started_at, ends_at, status FROM raids WHERE status IN "
                        "('pending', 'active') ORDER BY id").fetchall()


def wants_protesters(conn):
    return mood_band(conn) in PROTEST_BANDS


def protest_cause(conn):
    """The biggest negative drift factor, as a placard line."""
    worst = min(drift(conn), key=lambda p: p[1], default=("", 0))
    return {"Sales tax": "The sales tax bleeds us dry!",
            "Land fees": "Land fees are robbery!",
            "Crown Challenge": "Enough blood for the throne!",
            "Houses opposing": "The great houses have turned on the Crown!"}.get(
        worst[0], "Bread, not crowns!")


# ---- pledges ----------------------------------------------------------------------------------
def pledge_of(conn, pid):
    row = conn.execute("SELECT house_key, favour, pledged_at, errand_day, support_day FROM house_pledges "
                       "WHERE player_id = ?", (pid,)).fetchone()
    return dict(zip(("house", "favour", "pledged_at", "errand_day", "support_day"), row)) if row else None


def pledge(conn, pid, house, now=None):
    now = _now(now)
    if house not in HOUSES:
        return False, "No such house."
    p = pledge_of(conn, pid)
    if p and p["house"] == house:
        return False, f"You are already pledged to {HOUSES[house]}."
    if p and now - float(p["pledged_at"] or 0) < PLEDGE_COOLDOWN:
        days = int((PLEDGE_COOLDOWN - (now - float(p["pledged_at"]))) // DAY) + 1
        return False, f"You pledged to {HOUSES[p['house']]} too recently. Wait {days} more day(s)."
    conn.execute("INSERT OR REPLACE INTO house_pledges (player_id, house_key, favour, pledged_at, errand_day, "
                 "support_day) VALUES (?, ?, 0, ?, NULL, NULL)", (pid, house, now))
    conn.commit()
    return True, f"You pledge yourself to {HOUSES[house]}."


def errand_done(conn, pid, house, now=None):
    """Pays the house reward once a day. Call after the items were handed over. -> (ok, msg)."""
    import apprentice
    import reputation
    now = _now(now)
    p = pledge_of(conn, pid)
    if not p or p["house"] != house:
        return False, f"Only those pledged to {HOUSES.get(house, 'this house')} run its errands."
    if p["errand_day"] == _day(now):
        return False, "You've already run today's errand. Come back tomorrow."
    fav = min(FAVOUR_MAX, int(p["favour"] or 0) + ERRAND_FAVOUR)
    conn.execute("UPDATE house_pledges SET favour = ?, errand_day = ? WHERE player_id = ?", (fav, _day(now), pid))
    apprentice.bank_add(conn, pid, ERRAND_COINS)
    got = reputation.daily_take(conn, pid, "house_errand", ERRAND_REP, ERRAND_REP, now)
    if got:
        conn.execute("UPDATE players SET reputation = MAX(-1000, MIN(1000, COALESCE(reputation, 0) + ?)) "
                     "WHERE id = ?", (got, pid))
    conn.commit()
    return True, f"The house thanks you: {ERRAND_COINS} coins to your bank, +{ERRAND_FAVOUR} favour ({fav})."


def can_errand(conn, pid, house, now=None):
    p = pledge_of(conn, pid)
    if not p or p["house"] != house:
        return False, f"Only those pledged to {HOUSES.get(house, 'this house')} run its errands."
    if p["errand_day"] == _day(_now(now)):
        return False, "You've already run today's errand. Come back tomorrow."
    return True, ""


def support(conn, pid, direction, now=None):
    now = _now(now)
    p = pledge_of(conn, pid)
    if not p:
        return False, "Pledge to a house first."
    if p["support_day"] == _day(now):
        return False, "You've already spoken for your house today."
    step = SUPPORT_STEP if direction == "support" else -SUPPORT_STEP
    conn.execute("UPDATE house_pledges SET support_day = ? WHERE player_id = ?", (_day(now), pid))
    adjust_stance(conn, p["house"], step, now)
    conn.commit()
    verb = "speak for" if step > 0 else "speak against"
    return True, f"You {verb} the Crown in {HOUSES[p['house']]}'s halls ({stances(conn)[p['house']]:+d})."


def title_suffix(conn, pid):
    try:
        p = pledge_of(conn, pid)
    except Exception:
        return ""
    if not p:
        return ""
    fav = int(p["favour"] or 0)
    h = HOUSES[p["house"]]
    h = "the Commons" if p["house"] == "commons" else h
    for need, fmt in TITLE_TIERS:
        if fav >= need:
            return fmt.format(h=h)
    return ""


def house_lines(conn, pid=None):
    st = stances(conn)
    lines = [f"{HOUSES[k]}: {stance_band(st[k])} ({st[k]:+d})" for k in HOUSES]
    p = pledge_of(conn, pid) if pid is not None else None
    if p:
        lines.append(f"You are pledged to {HOUSES[p['house']]}, favour {p['favour']}/{FAVOUR_MAX}.")
    elif pid is not None:
        lines.append("You are not pledged to any house. Speak with an envoy in the castle courtyard.")
    return lines


# ---- court events -----------------------------------------------------------------------------
def open_event(conn):
    row = conn.execute("SELECT id, event_key, opened_at FROM court_events WHERE resolved_at IS NULL "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    return {"id": row[0], "key": row[1], "opened_at": float(row[2])} if row else None


def _eligible_events(conn):
    recent = [r[0] for r in conn.execute("SELECT event_key FROM court_events ORDER BY id DESC LIMIT ?",
                                         (NO_REPEAT,)).fetchall()]
    ks = _old_king_state(conn)
    out = []
    for e in EVENTS:
        if e["key"] in recent:
            continue
        if e["key"] == "valcrest_release" and ks not in ("imprisoned", "exiled"):
            continue
        out.append(e)
    return out


def roll_event(conn, now=None, rng=None, force=False):
    now = _now(now)
    rng = rng or random
    if open_event(conn):
        return None
    if not force and rng.random() >= EVENT_CHANCE:
        return None
    pool = _eligible_events(conn)
    if not pool:
        return None
    e = rng.choice(pool)
    cur = conn.execute("INSERT INTO court_events (event_key, opened_at) VALUES (?, ?)", (e["key"], now))
    conn.commit()
    news(conn, "court", f"Court: {e['title']}. {e['text']}", now)
    return cur.lastrowid


def _choice(ev_key, choice_id):
    for c in EVENT_BY_KEY[ev_key]["choices"]:
        if c["id"] == choice_id:
            return c
    return None


def _ignore_choice(ev_key):
    ch = EVENT_BY_KEY[ev_key]["choices"]
    return next((c for c in ch if c["id"] == "ignore"), ch[-1])


def _choice_cost(conn, c):
    import ruling
    if c.get("free_king"):
        return ruling.RECALL_KING_COST if _old_king_state(conn) == "exiled" else ruling.FREE_KING_COST
    return int(c.get("cost", 0) or 0)


def _npc_can_pay(conn, amount, now):
    import ruling
    if amount <= 0:
        return True, ""
    if ruling.spent_today(conn, now) + amount > ruling.daily_cap(conn, now):
        return False, "That passes today's spending cap."
    if amount > ruling.spendable(conn):
        return False, "The treasury can't cover that."
    return True, ""


def choice_ok(conn, actor, ev_key, choice_id, now=None, npc=False):
    """(ok, reason) - affordability and bounds, without changing anything."""
    import ruling
    now = _now(now)
    c = _choice(ev_key, choice_id)
    if c is None:
        return False, "No such choice."
    cost = _choice_cost(conn, c)
    if c.get("tax_cut"):
        if float(ruling.get_setting(conn, "sales_tax")) - c["tax_cut"] < ruling.SETTINGS["sales_tax"][1] - 1e-9:
            return False, "The sales tax is already at its lowest."
    if c.get("free_king"):
        if npc:
            return False, "Only a monarch can free the old King."
        if _old_king_state(conn) not in ("imprisoned", "exiled"):
            return False, "The old King is already free."
        if ruling.role(conn, actor) != "Monarch":
            return False, "Only the monarch can free the old King."
    if c.get("bounty"):
        if npc:
            return False, "The NPC King posts no bounties."
        if ruling.role(conn, actor) not in ("Monarch", "Marshal"):
            return False, "Only the monarch can post that bounty."
        cost = c["bounty"]
    if cost:
        if npc:
            return _npc_can_pay(conn, cost, now)
        ok, why = ruling.can_spend(conn, actor, None, cost, "event", now)
        if not ok:
            return False, why
    return True, ""


def can_resolve(conn, actor, ev, now=None):
    import ruling
    now = _now(now)
    r = ruling.role(conn, actor)
    if r == "Monarch":
        return True, ""
    if r == "Chancellor":
        if now - ev["opened_at"] >= CHANCELLOR_AFTER:
            return True, ""
        return False, "The Chancellor may decide only after the monarch has had 12 hours."
    return False, "Only the monarch (or the Chancellor after 12 hours) decides court matters."


def _apply(conn, actor, ev, c, now, npc=False, monsters=None):
    import ruling
    cost = _choice_cost(conn, c)
    detail = f"court:{ev['key']}:{c['id']}"
    if c.get("free_king"):
        fn = ruling.recall_king if _old_king_state(conn) == "exiled" else ruling.free_king
        ok, msg = fn(conn, actor, now)
        if not ok:
            return False, msg
    elif c.get("bounty"):
        ok, msg = ruling.post_bounty(conn, actor, RAID_TYPES[0], c["bounty"], monsters or {RAID_TYPES[0]: {}}, now)
        if not ok:
            return False, msg
    elif cost:
        if npc:
            import royal_treasury
            ok, why = _npc_can_pay(conn, cost, now)
            if not ok or not royal_treasury.debit(conn, "spend_event", None, cost):
                return False, why or "The treasury can't cover that."
            conn.execute("UPDATE treasury_daily SET spent = spent + ? WHERE day = ?", (cost, ruling._day(now)))
            ruling.audit(conn, None, "NPC King", "spend:event", cost, detail, now)
        else:
            ok, msg = ruling.spend(conn, actor, "event", cost, detail, now)
            if not ok:
                return False, msg
    if c.get("tax_cut"):
        cur = float(ruling.get_setting(conn, "sales_tax"))
        new = round(max(ruling.SETTINGS["sales_tax"][1], cur - c["tax_cut"]), 4)
        conn.execute("UPDATE realm_settings SET value = ?, changed_at = ?, changed_by = ? WHERE key = 'sales_tax'",
                     (new, now, actor))
        news(conn, "decree", f"By royal decree, the sales tax is now {new * 100:.0f}%.", now)
    if c.get("mood"):
        adjust_mood(conn, c["mood"], now)
    for k, d in (c.get("houses") or {}).items():
        adjust_stance(conn, k, d, now)
    if c.get("rep"):
        row = conn.execute("SELECT monarch_kind, monarch_player_id FROM throne WHERE id = 1").fetchone()
        if row and row[0] == "player" and row[1] is not None:
            conn.execute("UPDATE players SET reputation = MAX(-1000, MIN(1000, COALESCE(reputation, 0) + ?)) "
                         "WHERE id = ?", (int(c["rep"]), row[1]))
    if c.get("raid"):
        schedule_raid(conn, now, delay=int(c["raid"]) * DAY)
    if c.get("ironhold_check"):
        _put(conn, "politics:ironhold_due", now + IRONHOLD_BOUNTY_DAYS * DAY, now)
    conn.execute("UPDATE court_events SET resolved_at = ?, choice = ?, resolved_by = ? WHERE id = ?",
                 (now, c["id"], actor, ev["id"]))
    post = "NPC King" if npc else ("Court" if actor is None else (ruling.role(conn, actor) or "Court"))
    ruling.audit(conn, actor, post, "court_event", cost if not c.get("bounty") else c["bounty"], detail, now)
    conn.commit()
    who = {"NPC King": "The King", "Court": "With no answer from the throne, the court"}.get(post, f"The {post}")
    news(conn, "court", f"{who} answers '{EVENT_BY_KEY[ev['key']]['title']}': {c['label']}.", now)
    return True, f"{EVENT_BY_KEY[ev['key']]['title']}: {c['label']}."


def resolve(conn, actor, choice_id, now=None, monsters=None):
    now = _now(now)
    ev = open_event(conn)
    if not ev:
        return False, "There is no open court matter."
    ok, why = can_resolve(conn, actor, ev, now)
    if not ok:
        return False, why
    ok, why = choice_ok(conn, actor, ev["key"], choice_id, now)
    if not ok:
        return False, why
    return _apply(conn, actor, ev, _choice(ev["key"], choice_id), now, monsters=monsters)


def npc_king_reigns(conn):
    try:
        row = conn.execute("SELECT monarch_kind FROM throne WHERE id = 1").fetchone()
    except Exception:
        return True
    return not row or row[0] != "player"


def tick_events(conn, now=None, monsters=None):
    """NPC King answers at once; anyone else's matter falls to 'ignore' after 24 hours."""
    now = _now(now)
    ev = open_event(conn)
    if not ev:
        return None
    if npc_king_reigns(conn):
        for c in EVENT_BY_KEY[ev["key"]]["choices"]:
            if c["id"] == "ignore":
                continue
            if choice_ok(conn, None, ev["key"], c["id"], now, npc=True)[0]:
                return _apply(conn, None, ev, c, now, npc=True, monsters=monsters)
        return _apply(conn, None, ev, _ignore_choice(ev["key"]), now, npc=True, monsters=monsters)
    if now - ev["opened_at"] >= AUTO_IGNORE_AFTER:
        return _apply(conn, None, ev, _ignore_choice(ev["key"]), now, monsters=monsters)
    return None


def event_payload(conn, actor, now=None):
    now = _now(now)
    ev = open_event(conn)
    if not ev:
        return None
    e = EVENT_BY_KEY[ev["key"]]
    can, why = can_resolve(conn, actor, ev, now)
    choices = []
    for c in e["choices"]:
        ok, reason = choice_ok(conn, actor, ev["key"], c["id"], now) if can else (False, why)
        cost = _choice_cost(conn, c) or c.get("bounty", 0)
        choices.append({"id": c["id"], "label": c["label"] + (f" ({cost:,})" if cost else ""),
                        "ok": bool(ok), "why": reason})
    left = max(0, int((ev["opened_at"] + AUTO_IGNORE_AFTER - now) // 60))
    return {"id": ev["id"], "key": ev["key"], "title": e["title"], "text": e["text"], "choices": choices,
            "can_decide": bool(can), "why": why, "minutes_left": left}


# ---- UI ---------------------------------------------------------------------------------------
def state_payload(conn, pid, now=None):
    import ruling
    now = _now(now)
    m = mood(conn)
    parts = sorted(drift(conn, now), key=lambda p: -abs(p[1]))[:3]
    st = stances(conn)
    p = pledge_of(conn, pid)
    role = ruling.role(conn, pid)
    return {
        "mood": int(round(m)), "band": band_of(m),
        "drift": [{"label": k, "value": v} for k, v in parts],
        "houses": [{"key": k, "name": HOUSES[k], "stance": st[k], "band": stance_band(st[k])} for k in HOUSES],
        "pledge": ({"house": HOUSES[p["house"]], "favour": int(p["favour"] or 0)} if p else None),
        "event": event_payload(conn, pid, now) if role in ("Monarch", "Chancellor") or
        role in ruling.POSTS else None,
    }


def hud_line(conn):
    m = mood(conn)
    return f"Kingdom: {band_of(m)} ({int(round(m))})"
