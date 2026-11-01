"""The Resting Ox tavern package (TAVERN spec, 31 Oct 2026).

Rules + data; server/resting_ox_inn.py routes BAR_* messages here.
Built: menu + buffs + tipsy + daily special (s1), Bram dialogue, rumours, patrons (s2), tables (s3),
notice board / requests / proclamations (s4), bard queue (s6), trophy wall (s7), status tiers (s8).
Deferred: brawls (s5), Crown Dice / arm-wrestling, recorded songs (production).
Level bands are scaled to the real CL range (CL passes 236): 40 / 100 / 160 instead of 20 / 50 / 80.
"""
from __future__ import annotations

import json
import random
import re
import time

RESET_HOUR_UTC = 6


def day_key(now=None):
    t = (time.time() if now is None else now) - RESET_HOUR_UTC * 3600
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def week_key(now=None):
    t = (time.time() if now is None else now) - RESET_HOUR_UTC * 3600
    return time.strftime("%Y-W%W", time.gmtime(t))


VISIT_GAP_S = 600
TIPSY_S = 120
BUFF_S = 600
TOAST_BUFF_S = 300
TOAST_WINDOW_S = 5
TOAST_COOLDOWN_S = 600

# CL bands (spec 20/50/80 scaled to a ~240 CL game)
CL_T1, CL_T2, CL_T3 = 40, 100, 160

DRINKS = {
    "village_ale":   {"name": "Village Ale", "price": 5, "xp_pct": 2, "house": True, "basic": True},
    "honeyed_mead":  {"name": "Honeyed Mead", "price": 8, "xp_pct": 5, "house": True},
    "dwarven_stout": {"name": "Dwarven Stout", "price": 15, "hp_pct": 5, "tipsy": True, "house": True},
    "spiced_cider":  {"name": "Spiced Cider", "price": 6, "regen": 1, "house": True, "basic": True},
    "ox_reserve":    {"name": "Ox Reserve", "price": 40, "xp_pct": 6, "hp_pct": 3, "tipsy": True, "reserve": True},
    "water":         {"name": "Water", "price": 0, "free_item": True},
}
FOOD = {
    "rabbit_stew":  {"name": "Rabbit Stew", "price": 10, "heal": 8, "regen": 1},
    "bread_cheese": {"name": "Bread & Cheese", "price": 7, "heal": 6},
    "roast_shrimp": {"name": "Roast Shrimp", "price": 6, "heal": 3},
}
SPECIAL_ORDER = ("honeyed_mead", "spiced_cider", "dwarven_stout", "village_ale", "rabbit_stew")
SPECIAL_DISCOUNT = 1
SPECIAL_BONUS = 1

ECONOMY_NOTES = [
    "Rabbit Stew heals 8 (spec 30): the best cooked food (swordfish, 85c) heals 14.",
    "Bread & Cheese 7c (spec 4c): the General Store's bread is 6c and heals 5.",
    "Bram's Newcomer line quotes ale 5c / stew 10c to match the menu (spec line said 2c / 3c).",
    "Village Ale 5c (old bar sold it at 2c); free drinks now come from status tiers.",
    "Gather jobs pay 1.3x the items' value (spec 60c for 20 iron ore was under the ore's 140c).",
    "Bounties pay 1.25x the average coin drop of the targets, drawn from monsters near your CL.",
    "Elite bounty 300c x band multiplier (450c at CL 100+, 600c at CL 160+).",
    "Ox Reserve (no spec price) is 40c.",
    "Kept as spec: mead 8c, stout 15c, cider 6c, shrimp 6c, rumour tip 5c, bard 5c/25c, ballads 50c/25c, "
    "Cellar Rats 40c + bread, post fee 10c, escrow cap 5,000c.",
    "CL bands scaled to the real range: 40 / 100 / 160 (spec 20 / 50 / 80).",
]

BRAM = {"name": "Bram", "title": "Innkeeper of the Crossroads"}
GREET_FIRST = "Evening, traveller. Fire's warm and the ale's fresh. What can I get you?"
GREET_BACK = "Back again? Your usual stool's free."
DRINKS_LINE = "Ale, mead, or something stronger? Today it's {special}, a copper off."
SERVE_LINE = "There you are. Mind the foam."
FOOD_LINE = "Stew's been on since dawn. Bread's from this morning."
LEAVE_LINE = "Safe roads. Door's always open."
BROKE_LINE = "That's {price} coins, friend. Come back when your purse is heavier."
ABOUT = {
    "arena": "Fights every day. Start with the squires, not the King. Trust me.",
    "king": "Rules from Stonehaven. Fair, mostly. Taxes say otherwise.",
    "guilds": "Every trade has one. Ask around the square; they're always hiring hands.",
    "place": "Forty years my family's poured here. The beams are older than the kingdom.",
}
RUMOURS = [
    {"text": "Rats in the sewer have been bolder lately. Someone said there's a whole nest under the bank.", "hook": "sewer"},
    {"text": "The arena's taking new houses. Win a few bouts and the nobles start learning your name.", "hook": "arena"},
    {"text": "The estate agent up north has a cottage on King's Row going cheap. Probably haunted. Probably.", "hook": "housing"},
    {"text": "A drover swears he saw lights moving in the Stonehaven tunnels. Wenna won't say if he's wrong.", "hook": "lore"},
    {"text": "Mae at the Outfitters has new cloth in. Folk say a good coat opens doors at court.", "hook": "outfit"},
    {"text": "The Barracks are paying for squads that can hold a line. Bring ten and they'll notice.", "hook": "arena"},
    {"text": "Somebody's been posting bounties on the board by the door. Easy coin if you've a sword.", "hook": "board"},
]
RUMOUR_TIP = 5

PATRONS = {
    "wenna": {"name": "Old Wenna", "role": "retired miner", "view": "left",
              "open": "You've the look of someone who's walked far. Sit, it's free.",
              "choices": [("Where did you walk from?", "Stonehaven, once. Mined under it for thirty years. "
                           "The tunnels go further than the King thinks.", None),
                          ("Any advice?", "Iron before steel. Everyone wants to skip ahead. Everyone ends up broke.", None),
                          ("[Leave her be]", None, None)]},
    "tobin": {"name": "Tobin", "role": "nervous apprentice", "view": "right",
              "open": "Don't suppose you're any good with rats?",
              "choices": [("Depends on the rats.", "Big ones. In the bank cellar. Clear five and I'll owe you.", "cellar_rats"),
                          ("Not today.", "Right. Course. Sorry.", None)]},
    "sable": {"name": "Sable", "role": "off-duty arena fighter", "view": "left",
              "open": "Fought Brutus Ironhide last week. Nearly lost a tooth. Worth it.",
              "choices": [("How did you beat him?", "Didn't. Watch his shield; he braces every few swings. Hit between.", None),
                          ("Any openings for a fighter?", "Talk to the Barracks. Bring a squad worth looking at.", None),
                          ("Good luck with the teeth.", "Funny. Buy me a drink and I'll tell you about Crixus.", "buy_sable")]},
}
PATRONS["hale"] = {
    "name": "Hale", "role": "ranger of the north road", "view": "right",
    "open": "You're sitting where I can see the door. Sit somewhere else, or keep quiet.",
    "choices": [("Where have you come from?", "The Mire, then the old north road. Wolves are running in packs again, "
                 "and something bigger is driving them.", None),
                ("What's driving them?", "Ask the miners. Whatever woke under Stonehaven, the beasts smelled it first.", None),
                ("Any advice for the road?", "Light no fire you can't see past. Carry more bread than you think.", None),
                ("[Leave him be]", None, None)]}
SABLE_CRIXUS = ("Crixus fights like he's late for supper: all rush. Let him come, sidestep the third swing, "
                "and he's open for a breath.")
CELLAR_RATS = {"need": 5, "coins": 40, "item": "bread", "monsters": ("giant_rat",)}

TIER_NAMES = {"T0": "Newcomer", "T1": "Known face", "T2": "Respected", "T3": "Renowned", "T4": "The Crown"}
FREE_PER_VISIT = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 99}
FREE_DAILY_CAP = {"T0": 0, "T1": 2, "T2": 4, "T3": 6, "T4": 99}
KINGS_GUILD_DAILY = 3
GUILD_BEFORE_REIGN_S = 48 * 3600
GUILD_MEMBER_S = 72 * 3600
ROUNDS_FOR_REP = 20
TIER_LINES = {
    "T0": ["Evening. Ale's five coins, stew's ten. Wipe your boots.",
           "New to the road? Keep your purse close in here.",
           "Sit where you like. Not that stool. That's Wenna's."],
    "T1": ["There you are. Your usual? First one's on me tonight.",
           "Heard you've been clearing the sewers. Rats are fewer. Have a cider for it.",
           "You're getting a name around here. Mind it doesn't get you into trouble."],
    "T2": ["Sit. I've been saving the good cask for someone who'd notice it.",
           "You've the look of someone who's seen real fighting. Your first two are on the house.",
           "People talk about you when you're not here. Mostly good.",
           "If anyone in here gives you grief, you tell me."],
    "T3": ["Clear the end of the bar. Pour from the Reserve, the dark one.",
           "Not often someone of your standing drinks with the likes of us. It's an honour. "
           "Your coin's no good tonight, up to a point.",
           "Champion of the Sands under my roof. I'll be telling that one for years."],
}
T3_CHAMPION_LINE = 2
CROWN_LINES = [
    ("Your Grace. Put your purse away. No crowned head pays in my house, not while I'm standing behind this bar.", ()),
    ("{days_reigned} days on the throne. Most don't see a fortnight. You took it off {previous_king} and "
     "you've held it against {throne_defences} who came for it.", ("days_reigned", "previous_king", "throne_defences")),
    ("Tax at {tax_rate} percent. The traders grumble, but the roads are safer than they've been in years. "
     "I'll say that to anyone who asks.", ("tax_rate",)),
]
CROWN_TAX_EASED = "You eased the tax this week. The drovers drank to you last night. Didn't hear a word against you."
CROWN_NO_DEFENCES = "Early days, Your Grace. Hold it a month and they'll sing about you in here."
CROWN_LEAVE = "Long may you reign. And if it ends, there'll still be a seat here."
KINGS_GUILD_LINE = "Crown's colours. Welcome."
PREMIUM_OUTFIT_TIER = 4

JOB_SLOTS = {"gather": 3, "bounty": 2, "elite": 1}
JOB_HOLD = 3
JOB_DAILY = 6
GATHER_POOL = [("iron_ore", 20), ("logs", 30), ("oak_logs", 20), ("copper_ore", 25), ("tin_ore", 25),
               ("coal", 15), ("raw_trout", 15), ("willow_logs", 15), ("big_bones", 20), ("mithril_ore", 10)]
GATHER_MULT = 1.3
BOUNTY_MULT = 1.25
BOUNTY_BANDS = [
    (39, ["sewer_rat", "village_rat", "sewer_spider", "giant_rat", "goblin"]),
    (99, ["goblin", "skeleton", "giant", "big_skeleton"]),
    (159, ["giant", "wolf", "spider", "knight", "shade"]),
    (10 ** 6, ["crypt_ghoul", "magma_knight", "void_imp", "knight"]),
]
ELITE_POOL = ["barrow_knight", "sir_aldric", "ossuary_keeper", "gallery_warden", "morvath"]
ELITE_COINS = 300
ELITE_MIN_CL = 60
BOUNTY_XP = 25
TROPHY_TOKEN = "ox_trophy_token"
POST_FEE = 10
POST_LIMIT, POST_LIMIT_SUB = 2, 4
POST_LIFE_S = 48 * 3600
ESCROW_MAX = 5000
POST_TEXT_MAX = 80
REPORTS_TO_HIDE = 3
REMOVALS_BAN = 3
BAN_S = 7 * 86400
POST_TYPES = {
    "wanted": "WANTED: {item} x{qty} - paying {coin}",
    "selling": "SELLING: {item} x{qty} - asking {coin}",
    "guild": "{guild} is recruiting - ask {contact}",
    "lfg": "Looking for {what} - {when}",
    "spar": "Arena sparring wanted - {style}",
}
PROCLAIM_TEMPLATES = {
    "tax": "By royal decree, the sales tax is now {value} percent.",
    "bounty": "A royal bounty is set on every {value} slain.",
    "celebration": "Drinks are half-price at the Resting Ox tonight, paid from the treasury.",
    "summons": "The Crown summons the guilds of the realm to {value}.",
}
PROCLAIM_TEXT_MAX = 120
PROCLAIM_EVERY_S = 86400
_BAD_WORDS = ("fuck", "shit", "cunt", "nigg", "fag", "bitch", "whore", "rape")
_URL = re.compile(r"(https?://|www\.|\.(com|net|org|gg|io|co|uk)\b)", re.I)

SONGS = [
    {"id": "long_winter_road", "title": "The Long Winter Road", "mood": "sombre", "secs": 96},
    {"id": "iron_before_steel", "title": "Iron Before Steel", "mood": "rowdy drinking song", "secs": 78},
    {"id": "ox_and_crown", "title": "The Ox and the Crown", "mood": "tavern anthem", "secs": 104},
    {"id": "ashes_of_stonehaven", "title": "Ashes of Stonehaven", "mood": "lament", "secs": 112},
    {"id": "blades_in_the_sand", "title": "Blades in the Sand", "mood": "arena", "secs": 88},
    {"id": "rat_king", "title": "The Rat King of the Sewers", "mood": "comic", "secs": 70},
    {"id": "wolves_at_the_gate", "title": "Wolves at the Gate", "mood": "battle", "secs": 92},
    {"id": "toast_to_the_fallen", "title": "A Toast to the Fallen", "mood": "toast", "secs": 84},
    {"id": "silver_lady", "title": "The Silver Lady", "mood": "about Seraphine", "secs": 100},
    {"id": "lute_only", "title": "Lute only, no words", "mood": "calm", "secs": 120},
]
BALLADS = {
    "ballad_crown": {"title": "Ballad of the Crown", "price": 50, "secs": 150, "slot": ("the King", "the Queen")},
    "champion_sands": {"title": "Champion of the Sands", "price": 25, "secs": 140, "slot": ("the Champion", "the Champion")},
    "slayers_song": {"title": "The Slayer's Song", "price": 25, "secs": 140, "slot": ("the Slayer", "the Slayer")},
}
BARD_TIP, BARD_JUMP = 5, 25
BARD_QUEUE_MAX = 8
SONG_AUDIO_READY = False   # recordings are a production task; queue/subtitles run without audio

TABLE_COUNT = 3
TABLE_SEATS = 4

_BARD = {"queue": [], "now": None}
_TABLES = {}


def _srv():
    import server
    return server


def ensure_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS tavern_players (player_id INTEGER PRIMARY KEY, data TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tavern_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, "
        "player_id INTEGER, poster TEXT, guild_id INTEGER, body TEXT, note TEXT, escrow INTEGER DEFAULT 0, "
        "created REAL, expires REAL, renewed INTEGER DEFAULT 0, reports TEXT DEFAULT '[]', "
        "hidden INTEGER DEFAULT 0, status TEXT DEFAULT 'open')")
    conn.execute("CREATE TABLE IF NOT EXISTS tavern_proclamation (id INTEGER PRIMARY KEY, monarch_pid INTEGER, "
                 "template TEXT, body TEXT, note TEXT, posted REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS tavern_kills (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
                 "monster TEXT, player_id INTEGER, killer TEXT, first INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS tavern_removals (player_id INTEGER, ts REAL)")
    conn.commit()


def load(conn, pid):
    ensure_schema(conn)
    row = conn.execute("SELECT data FROM tavern_players WHERE player_id = ?", (int(pid),)).fetchone()
    try:
        d = json.loads(row[0]) if row else {}
    except ValueError:
        d = {}
    for k, v in (("visits", 0), ("rounds", 0), ("quests", {}), ("jobs", []), ("last_lines", {})):
        d.setdefault(k, v)
    return d


def save(conn, pid, d):
    conn.execute("INSERT OR REPLACE INTO tavern_players (player_id, data) VALUES (?, ?)", (int(pid), json.dumps(d)))
    conn.commit()


def _daily(d, now=None):
    k = day_key(now)
    if d.get("day") != k:
        d.update(day=k, free_today=0, guild_free_today=0, rumour_free_used=False, rumours_seen=0,
                 rumour_drinks_used=0, jobs_done_today=0, ballad_self=[])
    return d


def combat_level(session):
    try:
        return int(session.combat_level())
    except Exception:
        return int(getattr(session, "cl", 1) or 1)


def cl_band_mult(cl):
    return 1.0 if cl < CL_T2 else 1.5 if cl < CL_T3 else 2.0


def pay(session, cost):
    if int(cost) <= 0:
        return True, ""
    import mercenaries
    ok, err, _p, _b = mercenaries.spend_coins(session, int(cost))
    return ok, err


def credit(session, qty):
    try:
        _g, left = _srv().WORLD.add_coins(session, int(qty))
        if left:
            session.bank_coins = int(getattr(session, "bank_coins", 0) or 0) + int(left)
    except Exception:
        session.coins = int(getattr(session, "coins", 0) or 0) + int(qty)


def _name_of(conn, pid):
    try:
        live = _srv().WORLD.sessions.get(int(pid))
        if live:
            return live.char_name
    except Exception:
        pass
    try:
        row = conn.execute("SELECT char_name FROM players WHERE id = ?", (int(pid),)).fetchone()
        return row[0] if row and row[0] else f"#{pid}"
    except Exception:
        return f"#{pid}"


def clean_text(text, limit, conn=None, block_names=False):
    """Length cap, no links, no slurs; proclamations may not name players."""
    t = " ".join(str(text or "").split())[:limit]
    if not t:
        return True, ""
    low = t.lower()
    if _URL.search(t):
        return False, "Links aren't allowed on the board."
    if any(w in low for w in _BAD_WORDS):
        return False, "Keep it civil; that wording isn't allowed."
    if block_names and conn is not None:
        try:
            names = [r[0].lower() for r in conn.execute(
                "SELECT char_name FROM players WHERE char_name IS NOT NULL AND length(char_name) >= 3")]
        except Exception:
            names = []
        words = set(re.findall(r"[a-z0-9_']+", low))
        if any(n in words or (" " in n and n in low) for n in names):
            return False, "Proclamations may not name players."
    return True, t


def throne_info(conn):
    try:
        import throne
        st = throne.state(conn)
    except Exception:
        return {}
    pid = st.get("monarch_player_id") if st.get("monarch_kind") == "player" else None
    info = {"kind": st.get("monarch_kind"), "pid": int(pid) if pid else None, "since": float(st.get("since") or 0)}
    if not pid:
        return info
    info["name"] = _name_of(conn, pid)
    info["days_reigned"] = max(0, int((time.time() - info["since"]) // 86400)) if info["since"] else None
    try:
        row = conn.execute("SELECT detail FROM throne_log WHERE event = 'crowned' AND player_id = ? "
                           "ORDER BY ts DESC LIMIT 1", (pid,)).fetchone()
        m = re.search(r"previous (\w+):(\w+)", row[0] if row and row[0] else "")
        if m:
            info["previous_king"] = (_name_of(conn, int(m.group(2))) if m.group(1) == "player" and
                                     m.group(2).isdigit() else "the old King")
        n = conn.execute("SELECT COUNT(*) FROM throne_log WHERE ts >= ? AND event LIKE '%defend%'",
                         (info["since"],)).fetchone()
        info["throne_defences"] = int(n[0]) if n else 0
        tax = conn.execute("SELECT COUNT(*) FROM throne_log WHERE ts >= ? AND player_id = ? AND "
                           "event LIKE '%tax_lower%'", (time.time() - 7 * 86400, pid)).fetchone()
        info["tax_eased"] = bool(tax and tax[0])
    except Exception:
        pass
    try:
        import royal_treasury
        rate = round(royal_treasury.sales_tax_rate() * 100, 1)
        info["tax_rate"] = int(rate) if float(rate).is_integer() else rate
    except Exception:
        pass
    try:
        import clans
        info["guild_id"] = clans.clan_of(pid)
    except Exception:
        info["guild_id"] = None
    return info


def _guild_join_ts(conn, pid):
    try:
        row = conn.execute("SELECT clan_id, joined_at FROM clan_members WHERE player_id = ?", (int(pid),)).fetchone()
        return (int(row[0]), float(row[1] or 0)) if row else (None, 0.0)
    except Exception:
        return None, 0.0


def kings_guild_member(conn, session, throne=None, now=None):
    now = time.time() if now is None else now
    th = throne if throne is not None else throne_info(conn)
    if not th.get("pid") or int(th["pid"]) == int(session.player_id) or not th.get("guild_id"):
        return False
    gid, joined = _guild_join_ts(conn, session.player_id)
    if gid != th["guild_id"] or not joined:
        return False
    return joined <= th.get("since", now) - GUILD_BEFORE_REIGN_S or now - joined >= GUILD_MEMBER_S


def outfit_tier(session):
    try:
        import outfits
        look = session.appearance_state() or {}
        table = outfits.items()
        item = table.get(look.get("outfit") or "") or table.get(look.get("top") or "") or {}
    except Exception:
        return "free"
    if item.get("outfit_tier") in ("free", "advanced", "premium"):
        return item["outfit_tier"]
    if int(item.get("tier") or 0) >= PREMIUM_OUTFIT_TIER:
        return "premium"
    if not item or item.get("starter") or int(item.get("price") or 0) == 0:
        return "free"
    return "advanced"


def arena_champion(conn, pid):
    try:
        import arena_battles
        top = arena_battles.leaderboard(conn, 1)
        return bool(top) and int(top[0]["player_id"]) == int(pid)
    except Exception:
        return False


def status_tier(session, conn, throne=None):
    th = throne if throne is not None else throne_info(conn)
    if th.get("pid") and int(th["pid"]) == int(session.player_id):
        return "T4"
    cl = combat_level(session)
    ot = outfit_tier(session)
    if cl >= CL_T3 or ot == "premium" or arena_champion(conn, session.player_id):
        return "T3"
    if cl >= CL_T2:
        return "T2"
    if cl >= CL_T1 or ot == "advanced":
        return "T1"
    return "T0"


def _rotate(d, key, n):
    last = d["last_lines"].get(key, -1)
    i = random.randrange(n)
    if n > 1 and i == last:
        i = (i + 1) % n
    d["last_lines"][key] = i
    return i


def crown_line(d, th):
    pool = [text.format(**{k: th.get(k) for k in needs}) for text, needs in CROWN_LINES
            if all(th.get(k) not in (None, "") for k in needs)]
    if th.get("tax_eased"):
        pool.append(CROWN_TAX_EASED)
    if th.get("throne_defences") == 0:
        pool.append(CROWN_NO_DEFENCES)
    return pool[_rotate(d, "T4", len(pool))]


def greeting(session, conn, d, tier, th, kings_guild=False):
    if tier == "T4":
        line = crown_line(d, th)
    elif d.get("visits", 0) <= 1 and tier == "T0":
        line = GREET_FIRST
    else:
        lines = list(TIER_LINES[tier])
        if tier == "T3" and not arena_champion(conn, session.player_id):
            lines.pop(T3_CHAMPION_LINE)
        line = lines[_rotate(d, tier, len(lines))]
    return f"{line} {KINGS_GUILD_LINE}" if kings_guild else line


def _own_allowance(d, tier):
    rep = 1 if tier in ("T1", "T2", "T3") and int(d.get("rounds", 0)) >= ROUNDS_FOR_REP else 0
    return FREE_PER_VISIT[tier] + rep, FREE_DAILY_CAP[tier] + rep


def free_left(d, tier, kings_guild):
    if tier == "T4":
        return 99
    per_visit, cap = _own_allowance(d, tier)
    own = max(0, min(per_visit - int(d.get("visit_free", 0)), cap - int(d.get("free_today", 0))))
    guild = max(0, KINGS_GUILD_DAILY - int(d.get("guild_free_today", 0))) if kings_guild else 0
    return own + guild


def drink_free_ok(tier, drink_id):
    dr = DRINKS[drink_id]
    if tier in ("T3", "T4"):
        return True
    if tier == "T1":
        return dr.get("basic", False)
    if tier == "T2":
        return dr.get("house", False)
    return False


def special_today(now=None):
    return SPECIAL_ORDER[sum(map(ord, day_key(now))) % len(SPECIAL_ORDER)]


def describe(iid, special=False):
    it = DRINKS.get(iid) or FOOD.get(iid) or {}
    b = SPECIAL_BONUS if special else 0
    bits = []
    if it.get("xp_pct"):
        bits.append(f"+{it['xp_pct'] + b}% XP, 10 min")
    if it.get("hp_pct"):
        bits.append(f"+{it['hp_pct'] + b}% max HP, 10 min")
    if it.get("heal"):
        bits.append(f"heals {it['heal']} HP")
    if it.get("regen"):
        bits.append("+regen out of combat")
    if it.get("tipsy"):
        bits.append("tipsy")
    return ", ".join(bits) or "no buff"


def menu(tier, now=None):
    sp = special_today(now)
    out = []
    for kind, table in (("drink", DRINKS), ("food", FOOD)):
        for iid, it in table.items():
            if it.get("reserve") and tier not in ("T3", "T4"):
                continue
            price = max(0, it["price"] - SPECIAL_DISCOUNT) if iid == sp else it["price"]
            out.append({"id": iid, "kind": kind, "name": it["name"], "price": price, "special": iid == sp,
                        "desc": describe(iid, special=iid == sp)})
    return out


def apply_drink(session, iid, special=False, now=None):
    now = time.time() if now is None else now
    it = DRINKS[iid]
    if it.get("free_item"):
        return
    b = SPECIAL_BONUS if special else 0
    session.tavern_buff = {"id": iid, "name": it["name"], "until": now + BUFF_S,
                           "xp_pct": it["xp_pct"] + b if it.get("xp_pct") else 0,
                           "hp_pct": it["hp_pct"] + b if it.get("hp_pct") else 0,
                           "regen": int(it.get("regen", 0))}
    if it.get("tipsy"):
        session.tipsy_until = now + TIPSY_S


def apply_food(session, iid, now=None):
    now = time.time() if now is None else now
    it = FOOD[iid]
    try:
        session.hp = min(session.max_hp(), int(session.hp) + int(it.get("heal", 0)))
    except Exception:
        pass
    if it.get("regen"):
        session.tavern_food_regen_until = now + BUFF_S


def _buff(session, now=None):
    b = getattr(session, "tavern_buff", None)
    if not b:
        return None
    if (time.time() if now is None else now) >= b["until"]:
        session.tavern_buff = None
        return None
    return b


def xp_mult(session, skill=None, now=None):
    now = time.time() if now is None else now
    m = 1.0
    b = _buff(session, now)
    if b and b.get("xp_pct"):
        m += b["xp_pct"] / 100.0
    if float(getattr(session, "toast_until", 0) or 0) > now:
        m += 0.01
    return m


def hp_bonus(session, base, now=None):
    b = _buff(session, now)
    return int(base * b["hp_pct"] / 100.0) if b and b.get("hp_pct") else 0


def regen_amount(session, now=None):
    now = time.time() if now is None else now
    if getattr(session, "in_combat_with", None):
        return 0
    b = _buff(session, now)
    n = int(b.get("regen", 0)) if b else 0
    if float(getattr(session, "tavern_food_regen_until", 0) or 0) > now:
        n = max(n, 1)
    return n


def buffs_payload(session, now=None):
    now = time.time() if now is None else now
    b = _buff(session, now)
    drink = None
    if b:
        drink = {k: b[k] for k in ("id", "name", "xp_pct", "hp_pct", "regen")}
        drink["left"] = int(b["until"] - now)
    return {"drink": drink,
            "tipsy_left": max(0, int(float(getattr(session, "tipsy_until", 0) or 0) - now)),
            "toast_left": max(0, int(float(getattr(session, "toast_until", 0) or 0) - now))}


def _ctx(session, conn, now):
    d = _daily(load(conn, session.player_id), now)
    th = throne_info(conn)
    tier = status_tier(session, conn, th)
    kg = kings_guild_member(conn, session, th, now) if tier != "T4" else False
    return d, th, tier, kg


def enter(session, conn, now=None):
    now = time.time() if now is None else now
    d, th, tier, kg = _ctx(session, conn, now)
    if now - float(d.get("left_at", 0) or 0) >= VISIT_GAP_S or not d.get("visits"):
        d["visits"] = int(d.get("visits", 0)) + 1
        d.update(visit_free=0, visit_drinks=0, rumour_drinks_used=0)
    line = greeting(session, conn, d, tier, th, kg)
    if tier == "T0" and d["visits"] > 1 and d["last_lines"].get("back") != d["visits"] and random.random() < 0.34:
        d["last_lines"]["back"] = d["visits"]
        line = GREET_BACK
    intro = not d.get("intro_seen")
    save(conn, session.player_id, d)
    sp = special_today(now)
    return {"tier": tier, "tier_name": TIER_NAMES[tier], "kings_guild": kg, "line": line, "intro": intro,
            "free_left": free_left(d, tier, kg), "special": sp,
            "special_name": (DRINKS.get(sp) or FOOD.get(sp))["name"], "menu": menu(tier, now),
            "quests": d["quests"], "about": list(ABOUT), "look": _look_of(session)}


def mark_intro_seen(conn, pid):
    d = load(conn, pid)
    d["intro_seen"] = True
    save(conn, pid, d)


def leave(session, conn, now=None):
    now = time.time() if now is None else now
    d = load(conn, session.player_id)
    d["left_at"] = now
    save(conn, session.player_id, d)
    return CROWN_LEAVE if status_tier(session, conn) == "T4" else LEAVE_LINE


def buy(session, conn, iid, now=None):
    """Returns (ok, line, info)."""
    now = time.time() if now is None else now
    d, th, tier, kg = _ctx(session, conn, now)
    it = DRINKS.get(iid) or FOOD.get(iid)
    if not it:
        return False, "We don't pour that here.", {}
    if it.get("reserve") and tier not in ("T3", "T4"):
        return False, "The Reserve's for regulars of some standing. Maybe one day.", {}
    sp = special_today(now) == iid
    price = max(0, it["price"] - (SPECIAL_DISCOUNT if sp else 0))
    free = False
    if iid in DRINKS and price > 0 and free_left(d, tier, kg) > 0:
        per_visit, cap = _own_allowance(d, tier)
        own_ok = tier == "T4" or (int(d.get("visit_free", 0)) < per_visit and int(d.get("free_today", 0)) < cap)
        if own_ok and drink_free_ok(tier, iid):
            free = True
            d["visit_free"] = int(d.get("visit_free", 0)) + 1
            d["free_today"] = int(d.get("free_today", 0)) + 1
        elif kg and int(d.get("guild_free_today", 0)) < KINGS_GUILD_DAILY:
            free = True
            d["guild_free_today"] = int(d.get("guild_free_today", 0)) + 1
        if free:
            price = 0
    if price:
        ok, _e = pay(session, price)
        if not ok:
            return False, BROKE_LINE.format(price=price), {}
    if iid in DRINKS:
        apply_drink(session, iid, special=sp, now=now)
        if not it.get("free_item"):
            d["visit_drinks"] = int(d.get("visit_drinks", 0)) + 1
    else:
        apply_food(session, iid, now)
    save(conn, session.player_id, d)
    if free:
        line = "Your Grace. No coin." if tier == "T4" else "On the house."
    elif iid in FOOD:
        line = "Hot from the pot. Mind your fingers."
    elif it.get("free_item"):
        line = "Water it is. Plenty of that."
    else:
        line = SERVE_LINE
    return True, line, {"price": price, "free": free, "item": iid, "name": it["name"],
                        "free_left": free_left(d, tier, kg), "drink": iid in DRINKS and not it.get("free_item"),
                        "tipsy": bool(it.get("tipsy"))}


def rumour(session, conn, tip=False, now=None):
    """1 free a day; more for a 5c tip or after a drink this visit. Returns (ok, text, hook, paid)."""
    now = time.time() if now is None else now
    d = _daily(load(conn, session.player_id), now)
    paid = 0
    if d.get("rumour_free_used"):
        if tip:
            ok, _e = pay(session, RUMOUR_TIP)
            if not ok:
                return False, "A rumour's worth a tip, and your purse is empty.", None, 0
            paid = RUMOUR_TIP
        elif int(d.get("visit_drinks", 0)) > int(d.get("rumour_drinks_used", 0)):
            d["rumour_drinks_used"] = int(d.get("rumour_drinks_used", 0)) + 1
        else:
            return False, "That's all I've got for free today. A tip or a drink loosens my tongue.", None, 0
    else:
        d["rumour_free_used"] = True
    base = sum(map(ord, day_key(now))) % len(RUMOURS)
    n = int(d.get("rumours_seen", 0))
    d["rumours_seen"] = n + 1
    r = RUMOURS[(base + n) % len(RUMOURS)]
    save(conn, session.player_id, d)
    return True, r["text"], r["hook"], paid


def patron_talk(session, conn, patron, choice=None):
    p = PATRONS.get(patron)
    if not p:
        return False, "Nobody there.", {}
    d = load(conn, session.player_id)
    q = d["quests"].get("cellar_rats") or {}
    if choice is None:
        labels = [c[0] for c in p["choices"]]
        line = p["open"]
        if patron == "tobin" and q.get("state") == "active":
            line = f"How are the rats? {q.get('count', 0)} of {CELLAR_RATS['need']} so far."
            labels = ["Still working on it."]
        elif patron == "tobin" and q.get("state") == "done":
            line = "The cellar's quiet. You've no idea how grateful I am."
            labels = ["Glad to help."]
        return True, line, {"speaker": p["name"], "choices": labels}
    i = int(choice)
    if patron == "tobin" and q.get("state") in ("active", "done"):
        return True, ("Right. Thanks." if q.get("state") == "done" else "Five rats. You've got this."), \
            {"speaker": p["name"], "close": True}
    if not 0 <= i < len(p["choices"]):
        return False, "", {}
    _label, reply, effect = p["choices"][i]
    info = {"speaker": p["name"], "close": True}
    if effect == "cellar_rats" and not q:
        d["quests"]["cellar_rats"] = {"state": "active", "count": 0}
        info["quest"] = "Cellar Rats"
        reply += f" (Quest: Cellar Rats. Clear {CELLAR_RATS['need']} rats: {CELLAR_RATS['coins']}c + bread.)"
    elif effect == "buy_sable":
        info["offer"] = {"kind": "sable_drink", "price": DRINKS["village_ale"]["price"]}
    save(conn, session.player_id, d)
    return True, reply or "", info


def buy_sable_drink(session, conn):
    price = DRINKS["village_ale"]["price"]
    ok, _e = pay(session, price)
    if not ok:
        return False, "Sable laughs. 'With what, your good looks?'", 0
    return True, SABLE_CRIXUS, price


def _monster_defs():
    try:
        from content import MONSTERS
        return MONSTERS
    except Exception:
        return {}


def _item_defs():
    try:
        from content import ITEMS
        return ITEMS
    except Exception:
        return {}


def is_great_kill(mtype, mdef):
    return bool(mdef.get("boss")) or mtype in ELITE_POOL


def on_kill(session, conn, monster_type, monsters=None, now=None):
    now = time.time() if now is None else now
    mdef = (monsters or _monster_defs()).get(monster_type) or {}
    as_type = mdef.get("quest_as") or monster_type
    d = _daily(load(conn, session.player_id), now)
    out, changed = [], False
    q = d["quests"].get("cellar_rats")
    if q and q.get("state") == "active" and as_type in CELLAR_RATS["monsters"]:
        q["count"] = int(q.get("count", 0)) + 1
        changed = True
        if q["count"] >= CELLAR_RATS["need"]:
            q["state"] = "done"
            credit(session, CELLAR_RATS["coins"])
            try:
                _srv().WORLD.add_item_to_inventory(session, CELLAR_RATS["item"], 1)
            except Exception:
                pass
            out.append(f"Cellar Rats complete: Tobin pays {CELLAR_RATS['coins']} coins and a loaf of bread.")
        else:
            out.append(f"Cellar Rats: {q['count']}/{CELLAR_RATS['need']}")
    for j in d["jobs"]:
        if j.get("kind") in ("bounty", "elite") and j.get("target") in (monster_type, as_type) \
                and int(j.get("have", 0)) < int(j["qty"]):
            j["have"] = int(j.get("have", 0)) + 1
            changed = True
            out.append(f"Board job '{j['title']}': {j['have']}/{j['qty']}")
    if changed:
        save(conn, session.player_id, d)
    if is_great_kill(monster_type, mdef):
        ensure_schema(conn)
        first = conn.execute("SELECT COUNT(*) FROM tavern_kills WHERE monster = ?", (monster_type,)).fetchone()[0] == 0
        conn.execute("INSERT INTO tavern_kills (ts, monster, player_id, killer, first) VALUES (?, ?, ?, ?, ?)",
                     (now, monster_type, session.player_id, getattr(session, "char_name", "?"), int(first)))
        conn.commit()
    return out


def _avg_coin(mdef):
    for drop in mdef.get("drops") or []:
        if drop[0] == "coins":
            lo, hi = drop[2]
            return (lo + hi) / 2.0 * float(drop[1])
    return 4.0


def _round10(x, floor=10):
    return max(floor, int(round(x / 10.0)) * 10)


def board_jobs(now=None):
    """Today's 6 NPC posts; targets and rewards resolve per player's CL in jobs_for."""
    rng = random.Random("ox-board-" + day_key(now))
    items = _item_defs()
    jobs = []
    gather = [g for g in GATHER_POOL if g[0] in items]
    for i, (iid, qty) in enumerate(rng.sample(gather, min(JOB_SLOTS["gather"], len(gather)))):
        jobs.append({"id": f"g{i}:{iid}", "kind": "gather", "item": iid, "qty": qty,
                     "coins": _round10(qty * int(items[iid].get("value", 1)) * GATHER_MULT, 20),
                     "title": f"Bring {qty} {items[iid]['name'].lower()}"})
    for i in range(JOB_SLOTS["bounty"]):
        jobs.append({"id": f"b{i}", "kind": "bounty", "pick": rng.random(), "qty": 10})
    jobs.append({"id": "e0", "kind": "elite", "pick": rng.random(), "qty": 1, "coins": ELITE_COINS,
                 "min_cl": ELITE_MIN_CL})
    return jobs


def jobs_for(session, now=None):
    cl = combat_level(session)
    mult = cl_band_mult(cl)
    mons = _monster_defs()
    out, picked = [], set()
    for j in board_jobs(now):
        j = dict(j)
        if j["kind"] == "bounty":
            pool = next(p for top, p in BOUNTY_BANDS if cl <= top)
            pool = [m for m in pool if m in mons] or ["sewer_rat"]
            k = int(j.pop("pick") * len(pool)) % len(pool)
            if pool[k] in picked and len(pool) > 1:
                k = (k + 1) % len(pool)
            m = pool[k]
            picked.add(m)
            j["target"] = m
            j["coins"] = _round10(j["qty"] * _avg_coin(mons.get(m, {})) * BOUNTY_MULT, 50)
            j["xp"] = BOUNTY_XP * {1.0: 1, 1.5: 2, 2.0: 3}[mult]
            j["title"] = f"Slay {j['qty']} {mons.get(m, {}).get('name', m).lower()}s"
            j["id"] = f"{j['id']}:{m}"
        elif j["kind"] == "elite":
            pool = sorted((m for m in ELITE_POOL if m in mons), key=lambda m: mons[m].get("level", 0))
            if not pool:
                continue
            fit = [m for m in pool if mons[m].get("level", 0) <= cl + 30] or pool[:1]
            cands = fit[-2:]
            m = cands[int(j.pop("pick") * len(cands)) % len(cands)]
            j["target"] = m
            j["title"] = f"Elite bounty: {mons[m]['name']}"
            j["id"] = f"e0:{m}"
        j["reward"] = int(j["coins"] * mult)
        out.append(j)
    return out


def board_state(session, conn, now=None):
    now = time.time() if now is None else now
    d = _daily(load(conn, session.player_id), now)
    held = {j["id"]: j for j in d["jobs"]}
    today = jobs_for(session, now)
    for j in today:
        j["held"] = j["id"] in held
        if j["held"]:
            j["have"] = held[j["id"]].get("have", 0)
    return {"jobs": today, "held": list(held.values()), "done_today": d.get("jobs_done_today", 0),
            "hold_max": JOB_HOLD, "daily_max": JOB_DAILY, "requests": list_posts(conn, now),
            "arena": arena_posters(conn), "royal": proclamation(conn), "post_fee": POST_FEE,
            "templates": POST_TYPES, "proclaim_templates": PROCLAIM_TEMPLATES,
            "is_monarch": bool(throne_info(conn).get("pid") == session.player_id), "me": session.player_id}


def accept_job(session, conn, job_id, now=None):
    d = _daily(load(conn, session.player_id), now)
    if any(j["id"] == job_id for j in d["jobs"]):
        return False, "You already hold that job."
    if len(d["jobs"]) >= JOB_HOLD:
        return False, f"You can hold {JOB_HOLD} board jobs at once."
    if int(d.get("jobs_done_today", 0)) >= JOB_DAILY:
        return False, f"You've finished {JOB_DAILY} board jobs today. New ones go up at 06:00."
    job = next((j for j in jobs_for(session, now) if j["id"] == job_id), None)
    if not job:
        return False, "That notice has been taken down."
    if job.get("min_cl") and combat_level(session) < job["min_cl"]:
        return False, f"That one needs combat level {job['min_cl']}."
    job["have"] = 0
    d["jobs"].append(job)
    save(conn, session.player_id, d)
    return True, f"Accepted: {job['title']}."


def drop_job(session, conn, job_id):
    d = load(conn, session.player_id)
    d["jobs"] = [j for j in d["jobs"] if j["id"] != job_id]
    save(conn, session.player_id, d)
    return True, "Notice pinned back on the board."


def turn_in_job(session, conn, job_id, now=None):
    d = _daily(load(conn, session.player_id), now)
    job = next((j for j in d["jobs"] if j["id"] == job_id), None)
    if not job:
        return False, "You don't hold that job.", 0
    if int(d.get("jobs_done_today", 0)) >= JOB_DAILY:
        return False, f"You've finished {JOB_DAILY} board jobs today.", 0
    W = _srv().WORLD
    if job["kind"] == "gather":
        have = W.count_item(session, job["item"])
        if have < job["qty"]:
            return False, f"You have {have}/{job['qty']}.", 0
        W.remove_item_qty(session, job["item"], job["qty"])
    elif int(job.get("have", 0)) < int(job["qty"]):
        return False, f"Progress {job.get('have', 0)}/{job['qty']}.", 0
    credit(session, job["reward"])
    for sk in ("attack", "strength", "defence") if job.get("xp") else ():
        try:
            W.grant_xp(session, sk, int(job["xp"]))
        except Exception:
            pass
    if job["kind"] == "elite":
        try:
            W.add_item_to_inventory(session, TROPHY_TOKEN, 1)
        except Exception:
            pass
    d["jobs"] = [j for j in d["jobs"] if j["id"] != job_id]
    d["jobs_done_today"] = int(d.get("jobs_done_today", 0)) + 1
    save(conn, session.player_id, d)
    return True, f"Job done: {job['title']}. +{job['reward']:,} coins.", job["reward"]


def install_items():
    _item_defs().setdefault(TROPHY_TOKEN, {
        "name": "Ox Trophy Token", "type": "misc", "stackable": True, "value": 1, "equip_slot": None,
        "desc": "Proof of an elite bounty from the Resting Ox board. A keepsake."})


install_items()


def _banned(conn, pid, now):
    n = conn.execute("SELECT COUNT(*) FROM tavern_removals WHERE player_id = ? AND ts >= ?",
                     (int(pid), now - BAN_S)).fetchone()[0]
    return n >= REMOVALS_BAN


def create_post(session, conn, kind, fields, note="", escrow=0, now=None):
    now = time.time() if now is None else now
    ensure_schema(conn)
    if kind not in POST_TYPES:
        return False, "Pick a notice type.", None
    if _banned(conn, session.player_id, now):
        return False, "Your posting rights are paused for a week after removed notices.", None
    gid = None
    if kind == "guild":
        try:
            import clans
            gid, rank = clans.clan_of(session.player_id), clans.rank_of(session.player_id)
        except Exception:
            gid, rank = None, None
        if not gid or str(rank).lower() not in ("leader", "officer", "deputy", "general"):
            return False, "Only a guild's leader or officers can post recruitment.", None
        if conn.execute("SELECT COUNT(*) FROM tavern_posts WHERE guild_id = ? AND status = 'open' AND expires > ?",
                        (gid, now)).fetchone()[0]:
            return False, "Your guild already has a recruitment notice up.", None
    else:
        cap = POST_LIMIT_SUB if getattr(session, "subscriber", False) else POST_LIMIT
        active = conn.execute("SELECT COUNT(*) FROM tavern_posts WHERE player_id = ? AND kind != 'guild' AND "
                              "status = 'open' AND expires > ?", (session.player_id, now)).fetchone()[0]
        if active >= cap:
            return False, f"You can keep {cap} notices up at once.", None
    safe = {}
    for k in re.findall(r"{(\w+)}", POST_TYPES[kind]):
        ok, t = clean_text((fields or {}).get(k, ""), 24)
        if not ok:
            return False, t, None
        if not t:
            return False, "Fill in every field of the notice.", None
        safe[k] = t
    body = POST_TYPES[kind].format(**safe)
    ok, note = clean_text(note, POST_TEXT_MAX)
    if not ok:
        return False, note, None
    escrow = max(0, min(ESCROW_MAX, int(escrow or 0)))
    ok, _e = pay(session, POST_FEE + escrow)
    if not ok:
        return False, f"Posting costs {POST_FEE}c" + (f" plus the {escrow:,}c reward" if escrow else "") + ".", None
    cur = conn.execute(
        "INSERT INTO tavern_posts (kind, player_id, poster, guild_id, body, note, escrow, created, expires) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, session.player_id, getattr(session, "char_name", "?"), gid, body, note, escrow, now, now + POST_LIFE_S))
    conn.commit()
    return True, "Notice pinned to the board.", cur.lastrowid


def list_posts(conn, now=None):
    now = time.time() if now is None else now
    ensure_schema(conn)
    rows = conn.execute("SELECT id, kind, player_id, poster, body, note, escrow, expires, renewed FROM tavern_posts "
                        "WHERE status = 'open' AND hidden = 0 AND expires > ? ORDER BY created DESC LIMIT 40",
                        (now,)).fetchall()
    return [{"id": r[0], "kind": r[1], "player_id": r[2], "poster": r[3], "body": r[4], "note": r[5],
             "escrow": r[6], "hours_left": max(0, int((r[7] - now) // 3600)), "renewed": bool(r[8])} for r in rows]


def _own_post(conn, session, post_id):
    row = conn.execute("SELECT player_id, escrow, status, renewed FROM tavern_posts WHERE id = ?",
                       (int(post_id),)).fetchone()
    return row if row and int(row[0]) == int(session.player_id) and row[2] == "open" else None


def cancel_post(session, conn, post_id):
    row = _own_post(conn, session, post_id)
    if not row:
        return False, "That isn't your notice."
    conn.execute("UPDATE tavern_posts SET status = 'cancelled' WHERE id = ?", (int(post_id),))
    conn.commit()
    if row[1]:
        credit(session, int(row[1]))
        return True, f"Notice taken down. Your {int(row[1]):,}c reward is returned (the {POST_FEE}c fee is kept)."
    return True, "Notice taken down."


def renew_post(session, conn, post_id, now=None):
    now = time.time() if now is None else now
    row = _own_post(conn, session, post_id)
    if not row:
        return False, "That isn't your notice."
    if row[3]:
        return False, "A notice can be renewed once."
    conn.execute("UPDATE tavern_posts SET renewed = 1, expires = ? WHERE id = ?", (now + POST_LIFE_S, int(post_id)))
    conn.commit()
    return True, "Renewed for another 48 hours, free."


def report_post(session, conn, post_id):
    row = conn.execute("SELECT reports, player_id FROM tavern_posts WHERE id = ?", (int(post_id),)).fetchone()
    if not row:
        return False, "Gone already."
    if int(row[1]) == int(session.player_id):
        return False, "You can't report your own notice."
    reps = set(json.loads(row[0] or "[]"))
    reps.add(int(session.player_id))
    hidden = len(reps) >= REPORTS_TO_HIDE
    conn.execute("UPDATE tavern_posts SET reports = ?, hidden = ? WHERE id = ?",
                 (json.dumps(sorted(reps)), int(hidden), int(post_id)))
    conn.commit()
    return True, "Reported. Thank you." + (" The notice is hidden pending review." if hidden else "")


def remove_post_by_mod(conn, post_id, now=None):
    now = time.time() if now is None else now
    row = conn.execute("SELECT player_id FROM tavern_posts WHERE id = ?", (int(post_id),)).fetchone()
    if not row:
        return False
    conn.execute("UPDATE tavern_posts SET status = 'removed' WHERE id = ?", (int(post_id),))
    conn.execute("INSERT INTO tavern_removals (player_id, ts) VALUES (?, ?)", (int(row[0]), now))
    conn.commit()
    return True


def arena_posters(conn):
    out = []
    try:
        import arena_battles
        for r in arena_battles.leaderboard(conn, 3):
            out.append({"title": f"Champion #{r.get('rank', len(out) + 1)}: {r['name']}",
                        "body": f"{r.get('wins', 0)} wins, {r.get('losses', 0)} losses"})
    except Exception:
        pass
    out.append({"title": "Daily bouts", "body": "Squires to the King: fights every day at the Arena.", "open": "arena"})
    return out


def proclamation(conn):
    ensure_schema(conn)
    th = throne_info(conn)
    row = conn.execute("SELECT monarch_pid, template, body, note, posted FROM tavern_proclamation WHERE id = 1").fetchone()
    if not row:
        return None
    if not th.get("pid") or int(row[0]) != int(th["pid"]):
        conn.execute("DELETE FROM tavern_proclamation WHERE id = 1")
        conn.commit()
        return None
    return {"by": th.get("name"), "body": row[2], "note": row[3], "date": time.strftime("%d %b %Y", time.gmtime(row[4]))}


def proclaim(session, conn, template, value="", note="", now=None):
    now = time.time() if now is None else now
    ensure_schema(conn)
    th = throne_info(conn)
    if not th.get("pid") or int(th["pid"]) != int(session.player_id):
        return False, "Only the reigning monarch may post a proclamation."
    if template not in PROCLAIM_TEMPLATES:
        return False, "Pick a proclamation."
    row = conn.execute("SELECT posted, monarch_pid FROM tavern_proclamation WHERE id = 1").fetchone()
    if row and int(row[1]) == int(session.player_id) and now - float(row[0]) < PROCLAIM_EVERY_S:
        return False, "A proclamation can be changed once every 24 hours."
    if template == "bounty":
        mons = _monster_defs()
        v = str(value or "").strip().lower()
        hit = next((k for k, m in mons.items() if k == v.replace(" ", "_") or m.get("name", "").lower() == v), None)
        if not hit:
            return False, "Bounties may only name a monster species or a named boss."
        value = mons[hit]["name"]
    elif template == "tax":
        try:
            value = str(max(0, min(50, int(float(value)))))
        except (TypeError, ValueError):
            return False, "Give the new tax as a number."
    if "{value}" in PROCLAIM_TEMPLATES[template]:
        ok, value = clean_text(value, 24, conn, block_names=template != "bounty")
        if not ok:
            return False, value
        if not value:
            return False, "Fill in the proclamation."
    ok, note = clean_text(note, PROCLAIM_TEXT_MAX, conn, block_names=True)
    if not ok:
        return False, note
    body = PROCLAIM_TEMPLATES[template].format(value=value)
    conn.execute("INSERT OR REPLACE INTO tavern_proclamation (id, monarch_pid, template, body, note, posted) "
                 "VALUES (1, ?, ?, ?, ?, ?)", (session.player_id, template, body, note, now))
    conn.commit()
    return True, "Proclamation pinned under the royal seal."


def _guild_name(conn, gid):
    if not gid:
        return None
    try:
        row = conn.execute("SELECT name FROM clans WHERE clan_id = ?", (int(gid),)).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _look_of(s):
    try:
        return {"sex": getattr(s, "gender", "male"), "appearance": s.appearance_state(),
                "equipment": dict(getattr(s, "equipment", {}) or {})}
    except Exception:
        return None


def trophies(conn, now=None):
    ensure_schema(conn)
    th = throne_info(conn)
    if th.get("pid"):
        crown = {"player_id": th["pid"], "name": th.get("name"), "days": th.get("days_reigned"),
                 "guild": _guild_name(conn, th.get("guild_id"))}
        try:
            live = _srv().WORLD.sessions.get(int(th["pid"]))
        except Exception:
            live = None
        if live is not None:
            crown["look"] = _look_of(live)
    else:
        crown = {"name": "King Aldric", "days": None, "npc": True, "guild": "The old line"}
    try:
        import arena_battles
        champs = arena_battles.leaderboard(conn, 3)
    except Exception:
        champs = []
    mons = _monster_defs()
    kills = [{"monster": r[0], "name": (mons.get(r[0]) or {}).get("name", r[0]), "killer": r[1],
              "date": time.strftime("%d %b", time.gmtime(r[2])), "first": bool(r[3])}
             for r in conn.execute("SELECT monster, killer, ts, first FROM tavern_kills ORDER BY ts DESC LIMIT 3")]
    try:
        rows = conn.execute("SELECT c.clan_id, c.name, COUNT(m.player_id) FROM clans c LEFT JOIN clan_members m "
                            "ON m.clan_id = c.clan_id GROUP BY c.clan_id ORDER BY COUNT(m.player_id) DESC "
                            "LIMIT 3").fetchall()
        guilds = [{"name": r[1], "members": int(r[2]), "throne": th.get("guild_id") == r[0]} for r in rows]
    except Exception:
        guilds = []
    return {"crown": crown, "champions": champs, "kills": kills, "guilds": guilds,
            "throne_guild": _guild_name(conn, th.get("guild_id")),
            "legends": {"note": "Brawls and Crown Dice open soon."}, "week": week_key(now)}


def _bard_tick(now=None):
    now = time.time() if now is None else now
    cur = _BARD["now"]
    if cur and now >= cur["start"] + cur["secs"]:
        _BARD["now"] = cur = None
    if (cur is None or cur.get("ambient")) and _BARD["queue"]:
        nxt = _BARD["queue"].pop(0)
        nxt["start"] = now
        _BARD["now"] = cur = nxt
    if cur is None:
        song = random.choice(SONGS)
        _BARD["now"] = cur = {"song": song["id"], "title": song["title"], "secs": song["secs"], "start": now,
                              "by": None, "ambient": True}
    return cur


def bard_state(now=None):
    now = time.time() if now is None else now
    cur = _bard_tick(now)
    shown = {k: v for k, v in cur.items() if k != "by_id"}
    shown["elapsed"] = round(now - cur["start"], 1)
    return {"now": shown, "queue": [{k: v for k, v in q.items() if k != "by_id"} for q in _BARD["queue"]],
            "songs": SONGS, "ballads": [{"id": k, "title": v["title"], "price": v["price"]} for k, v in BALLADS.items()],
            "tip": BARD_TIP, "jump": BARD_JUMP, "audio_ready": SONG_AUDIO_READY, "max": BARD_QUEUE_MAX}


def _gender(conn, pid):
    try:
        import throne
        return throne._gender(conn, pid)
    except Exception:
        return "male"


def ballad_subject(conn, ballad):
    th = throne_info(conn)
    if ballad == "ballad_crown":
        if not th.get("pid"):
            return None
        sex = _gender(conn, th["pid"])
        days = th.get("days_reigned")
        sub = f"{'Queen' if sex == 'female' else 'King'} {th['name']}" + (f", {days} days" if days is not None else "")
        if th.get("previous_king"):
            sub += f", who took the crown from {th['previous_king']}"
        return {"pid": th["pid"], "subtitle": sub, "sex": sex}
    if ballad == "champion_sands":
        try:
            import arena_battles
            top = arena_battles.leaderboard(conn, 1)
        except Exception:
            top = []
        if not top:
            return None
        return {"pid": top[0]["player_id"], "subtitle": f"{top[0]['name']}, {top[0]['wins']} wins",
                "sex": _gender(conn, top[0]["player_id"])}
    if ballad == "slayers_song":
        ensure_schema(conn)
        row = conn.execute("SELECT monster, player_id, killer FROM tavern_kills WHERE first = 1 ORDER BY ts DESC "
                           "LIMIT 1").fetchone()
        if not row:
            return None
        name = (_monster_defs().get(row[0]) or {}).get("name", row[0])
        return {"pid": row[1], "subtitle": f"{row[2]}, slayer of {name}", "sex": _gender(conn, row[1])}
    return None


def bard_request(session, conn, song_id, jump=False, now=None):
    now = time.time() if now is None else now
    _bard_tick(now)
    q = _BARD["queue"]
    playing = _BARD["now"] or {}
    if any(r.get("by_id") == session.player_id for r in q) or playing.get("by_id") == session.player_id:
        return False, "One request at a time. Elric's got yours."
    if len(q) >= BARD_QUEUE_MAX:
        return False, "The queue's full. Give him a few songs."
    if jump and any(r.get("jumped") for r in q):
        return False, "Someone's already jumped the queue. Wait your turn."
    self_ballad, d = False, None
    if song_id in BALLADS:
        b = BALLADS[song_id]
        subj = ballad_subject(conn, song_id)
        if not subj:
            return False, "There's nobody to sing that about yet."
        price = b["price"] + (BARD_JUMP - BARD_TIP if jump else 0)
        entry = {"song": song_id, "title": b["title"], "secs": b["secs"],
                 "slot": b["slot"][1 if subj.get("sex") == "female" else 0], "subtitle": subj["subtitle"]}
        if int(subj["pid"]) == int(session.player_id):
            self_ballad = True
            d = _daily(load(conn, session.player_id), now)
            if song_id in d.get("ballad_self", []):
                return False, "Once a day for your own ballad. Modesty, friend."
    else:
        song = next((s for s in SONGS if s["id"] == song_id), None)
        if not song:
            return False, "Elric doesn't know that one."
        price = BARD_JUMP if jump else BARD_TIP
        entry = {"song": song_id, "title": song["title"], "secs": song["secs"]}
    ok, _e = pay(session, price)
    if not ok:
        return False, f"Elric plays for {price} coins."
    if self_ballad:
        d.setdefault("ballad_self", []).append(song_id)
        save(conn, session.player_id, d)
    entry.update(by=getattr(session, "char_name", "?"), by_id=session.player_id, jumped=bool(jump), price=price)
    if jump and q:
        q.insert(len(q) - 1, entry)
    else:
        q.append(entry)
    pos = q.index(entry)
    return True, (f"Elric nods. '{entry['title']}' is next." if pos == 0 else
                  f"Elric nods. '{entry['title']}' after {pos} more.")


def _table(tid):
    tid = int(tid)
    if tid not in _TABLES:
        _TABLES[tid] = {"id": tid, "seats": [None] * TABLE_SEATS, "locked": False, "owner": None,
                        "queue": [], "toast": None, "toast_cd": 0.0, "chat": []}
    return _TABLES[tid]


def tables_state():
    out = []
    for tid in range(1, TABLE_COUNT + 1):
        t = _table(tid)
        out.append({"id": tid, "taken": sum(1 for s in t["seats"] if s), "seats": TABLE_SEATS, "locked": t["locked"],
                    "names": [getattr(s, "char_name", "?") for s in t["seats"] if s]})
    return out


def table_of(session):
    for t in _TABLES.values():
        for i, s in enumerate(t["seats"]):
            if s is not None and s is session:
                return t, i
    return None, None


def _may_sit(t, session):
    if not t["locked"] or t["owner"] is None:
        return True
    owner = next((s for s in t["seats"] if s is not None and s.player_id == t["owner"]), None)
    if owner is None:
        return True
    try:
        import clans
        g1, g2 = clans.clan_of(owner.player_id), clans.clan_of(session.player_id)
        if g1 and g1 == g2:
            return True
    except Exception:
        pass
    party = getattr(owner, "party_ids", None) or set()
    friends = {str(f).lower() for f in (getattr(owner, "friends", None) or [])}
    return (session.player_id in party or str(session.player_id) in friends or
            getattr(session, "char_name", "").lower() in friends)


def sit(session, tid):
    if not 1 <= int(tid) <= TABLE_COUNT:
        return False, "No such table.", None
    t = _table(tid)
    cur, _i = table_of(session)
    if cur is t:
        return True, "You're already seated here.", t
    if not _may_sit(t, session):
        return False, "That table's kept for the party and friends.", t
    if None not in t["seats"]:
        free = next((x for x in range(1, TABLE_COUNT + 1)
                     if None in _table(x)["seats"] and _may_sit(_table(x), session)), None)
        hint = f" Table {free} has a seat." if free else " Every table's full; a bar stool is always free."
        return False, f"Table full ({TABLE_SEATS}/{TABLE_SEATS}).{hint}", t
    if cur is not None:
        stand(session)
    t["seats"][t["seats"].index(None)] = session
    if t["owner"] is None:
        t["owner"] = session.player_id
    if session.player_id in t["queue"]:
        t["queue"].remove(session.player_id)
    return True, f"You take a seat at table {t['id']}.", t


def stand(session):
    t, i = table_of(session)
    if t is None:
        return None
    t["seats"][i] = None
    if t["toast"]:
        t["toast"]["joined"].discard(session.player_id)
    if t["owner"] == session.player_id:
        nxt = next((s for s in t["seats"] if s is not None), None)
        t["owner"] = nxt.player_id if nxt else None
        if nxt is None:
            t["locked"] = False
    return t


def join_queue(session, tid):
    t = _table(tid)
    if session.player_id not in t["queue"]:
        t["queue"].append(session.player_id)
    return t


def set_lock(session, locked):
    t, _i = table_of(session)
    if t is None:
        return False, "Sit down first.", None
    if t["owner"] != session.player_id:
        return False, "Only whoever claimed the table can lock it.", t
    t["locked"] = bool(locked)
    return True, ("Table locked to party and friends." if locked else "Table open to anyone."), t


def table_payload(t, now=None):
    now = time.time() if now is None else now
    seats = [None if s is None else {"seat": i, "id": s.player_id, "name": getattr(s, "char_name", "?"),
                                     "cl": combat_level(s), "look": _look_of(s)}
             for i, s in enumerate(t["seats"])]
    toast = t.get("toast")
    return {"id": t["id"], "seats": seats, "locked": t["locked"], "owner": t["owner"],
            "taken": sum(1 for s in t["seats"] if s), "max": TABLE_SEATS, "chat": t["chat"][-6:],
            "toast": {"by": toast["by"], "left": max(0.0, round(toast["until"] - now, 1)),
                      "joined": sorted(toast["joined"])} if toast else None,
            "toast_cd": max(0, int(t["toast_cd"] - now))}


def table_chat(session, text):
    t, _i = table_of(session)
    if t is None:
        return False, "Sit at a table to use table chat.", None
    ok, clean = clean_text(text, 120)
    if not ok or not clean:
        return False, clean or "Say something.", t
    t["chat"].append({"from": getattr(session, "char_name", "?"), "text": clean})
    t["chat"] = t["chat"][-30:]
    return True, clean, t


def toast_start(session, now=None):
    now = time.time() if now is None else now
    t, _i = table_of(session)
    if t is None:
        return False, "Sit at a table to raise a toast.", None
    if t["toast"]:
        return False, "A toast is already raised.", t
    if now < t["toast_cd"]:
        return False, f"Glasses are still wet. Toast again in {int(t['toast_cd'] - now)}s.", t
    t["toast"] = {"by": getattr(session, "char_name", "?"), "until": now + TOAST_WINDOW_S,
                  "joined": {session.player_id}}
    return True, "You raise your tankard.", t


def toast_join(session, now=None):
    now = time.time() if now is None else now
    t, _i = table_of(session)
    if t is None or not t["toast"] or now > t["toast"]["until"]:
        return False, "Too late for that toast.", t
    t["toast"]["joined"].add(session.player_id)
    return True, "Clink!", t


def toast_resolve(t, now=None):
    """After the 5s window: 2+ joiners each get +1% XP for 5 min, then a 10 min cooldown. None = still open."""
    now = time.time() if now is None else now
    toast = t.get("toast")
    if not toast or now < toast["until"]:
        return None
    t["toast"] = None
    joined = [s for s in t["seats"] if s is not None and s.player_id in toast["joined"]]
    if len(joined) >= 2:
        for s in joined:
            s.toast_until = now + TOAST_BUFF_S
        t["toast_cd"] = now + TOAST_COOLDOWN_S
        return joined
    return []


def pending_toasts(now=None):
    return [t for t in _TABLES.values() if t.get("toast")]


def order_round(session, conn, now=None):
    t, _i = table_of(session)
    if t is None:
        return False, "Sit at a table to order a round.", None
    seated = [s for s in t["seats"] if s is not None]
    price = DRINKS["village_ale"]["price"] * len(seated)
    ok, _e = pay(session, price)
    if not ok:
        return False, f"A round for {len(seated)} is {price} coins.", t
    for s in seated:
        apply_drink(s, "village_ale", now=now)
    d = load(conn, session.player_id)
    d["rounds"] = int(d.get("rounds", 0)) + 1
    save(conn, session.player_id, d)
    t["chat"].append({"from": "Bram", "text": f"A round from {getattr(session, 'char_name', 'a friend')}!"})
    return True, f"You buy a round of ale for the table (-{price}c).", t


def drop_session(session):
    """Player left the tavern / disconnected: free their seat and bard request."""
    stand(session)
    _BARD["queue"][:] = [q for q in _BARD["queue"] if q.get("by_id") != session.player_id]


def reset_live_state():
    _BARD["queue"].clear()
    _BARD["now"] = None
    _TABLES.clear()
