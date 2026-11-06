"""Crownfall Arena battles: gladiator champion bosses, renown -> nobility / house deed,
weekly ranked ladder seasons, crowd favour + announcer, gladiator gear drops and
fights against other players' saved rosters.

mercenaries.py calls in here at four points:
  resolve_foe()  - foe ids "boss:<tier>", "rival:<player_id>" (ranked).
  build_units()  - adds the boss unit to a staged match.
  on_tick() / after_tick() - boss abilities, crowd favour, announcer.
  settle()       - renown, reputation, deed, gear, Elo, season rewards.
All numbers live at the top of this file.
"""
from __future__ import annotations

import datetime
import json
import random
import time

# --- Gladiator champions (one per practice tier) ---------------------------------
BOSSES = {
    1: {"id": "varro", "name": "Varro the Net", "title": "Retiarius", "base": "man_at_arms",
        "level_bonus": 10, "hp_mult": 4.0, "gear": "iron", "ability": "net_cast",
        "ability_label": "Net Cast — snares a foe for 3 swings",
        "drop": "retiarius_trident"},
    2: {"id": "brutus", "name": "Brutus Ironhide", "title": "Murmillo", "base": "bulwark",
        "level_bonus": 12, "hp_mult": 4.5, "gear": "steel", "ability": "shield_wall",
        "ability_label": "Shield Wall — braces every 8 ticks",
        "drop": "murmillo_helm"},
    3: {"id": "crixus", "name": "Crixus the Red", "title": "Thraex", "base": "veteran",
        "level_bonus": 14, "hp_mult": 4.5, "gear": "mithril", "ability": "blood_frenzy",
        "ability_label": "Blood Frenzy — swings every tick below half health",
        "drop": "thraex_greaves"},
    4: {"id": "sabina", "name": "Sabina of the Sands", "title": "Dimachaera", "base": "duelist",
        "level_bonus": 14, "hp_mult": 5.0, "gear": "adamant", "ability": "twin_blades",
        "ability_label": "Twin Blades — 35% chance of a second cut",
        "drop": "dimachaerus_sicae"},
    5: {"id": "ignatius", "name": "Ignatius the Lion", "title": "Secutor", "base": "bulwark",
        "level_bonus": 16, "hp_mult": 5.5, "gear": "adamant", "ability": "lions_roar",
        "ability_label": "Lion's Roar — stuns nearby foes every 10 ticks",
        "drop": "lionhide_cuirass"},
    6: {"id": "unbroken", "name": "The Unbroken", "title": "Grand Champion", "base": "mythos_guard",
        "level_bonus": 18, "hp_mult": 6.0, "gear": "mythos", "ability": "second_wind",
        "ability_label": "Second Wind + Sun Sweep — rises once, cleaves all around",
        "drop": "champion_sun_shield"},
}
BOSS_XP_MULT = 1.6
BOSS_COIN_MULT = 2.0
BOSS_FIRST_DROP = 1.0
BOSS_REPEAT_DROP = 0.20

# --- Gladiator gear (registered into content.ITEMS; art_as = worn look) ----------
GLADIATOR_ITEMS = {
    "retiarius_trident": {"name": "Retiarius Trident", "type": "weapon", "equip_slot": "weapon",
                          "att_bonus": 14, "str_bonus": 12, "value": 900, "art_as": "iron_battleaxe"},
    "murmillo_helm": {"name": "Murmillo Helm", "type": "armour", "equip_slot": "helmet",
                      "def_bonus": 16, "value": 1_600, "art_as": "steel_helmet"},
    "thraex_greaves": {"name": "Thraex Greaves", "type": "armour", "equip_slot": "legs",
                       "def_bonus": 24, "value": 3_000, "art_as": "mithril_legs"},
    "dimachaerus_sicae": {"name": "Dimachaerus Sicae", "type": "weapon", "equip_slot": "weapon",
                          "att_bonus": 40, "str_bonus": 36, "value": 6_000, "art_as": "adamant_sword"},
    "lionhide_cuirass": {"name": "Lionhide Cuirass", "type": "armour", "equip_slot": "body",
                         "def_bonus": 44, "value": 9_000, "art_as": "adamant_body"},
    "champion_sun_shield": {"name": "Champion's Sun Shield", "type": "armour", "equip_slot": "shield",
                            "def_bonus": 52, "value": 20_000, "art_as": "adamant_shield"},
}

# --- Renown -> standing / nobility / house -----------------------------------------
RENOWN_WIN_PER_TIER = 2
RENOWN_BOSS_FIRST = 25          # x tier
RENOWN_BOSS_REPEAT = 4          # x tier
RENOWN_RANKED_WIN = 6
RENOWN_CROWD_BONUS = 5          # crowd favour >= CROWD_ADORED at the end of a win
RENOWN_TO_REPUTATION = 1.0      # 1 renown = 1 standing point (feeds nobility "Standing")
RENOWN_TITLES = ((1000, "Legend of the Sands"), (500, "Champion of Crownfall"),
                 (200, "Primus Palus"), (50, "Veteranus"), (0, "Tiro"))
DEED_LEASE_WEEKS = 4
DEED_FALLBACK_BANK = 250_000    # already own a home -> paid in gold instead

# --- Ranked ladder -------------------------------------------------------------------
RANK_SOFT_RESET = 0.5           # new season rating = 1000 + (old - 1000) * 0.5
SEASON_REWARDS = ((1600, 60_000, 60, "Gold"), (1400, 25_000, 30, "Silver"),
                  (1200, 10_000, 15, "Bronze"), (0, 2_000, 5, "Iron"))
RIVAL_LIST = 5

# --- Crowd ----------------------------------------------------------------------------
CROWD_START = 50
CROWD_ADORED = 80
CROWD_KILL = 7
CROWD_LOSS = -6
CROWD_FIRST_BLOOD = 10
CROWD_COMEBACK = 12
CROWD_BOSS_HIT = -2
CROWD_PURSE_MAX = 0.5            # +50% purse at 100 favour

ANNOUNCER = {
    "start": ["The gates rise! {foe} enters the sand!", "Crownfall roars for blood — {foe} awaits!"],
    "boss": ["Behold {boss}, {title} of the pit!", "Kneel, commoners! {boss} walks the sand!"],
    "first_blood": ["First blood to {side}!", "The sand drinks first from {victim}!"],
    "kill": ["{killer} cuts down {victim}!", "{victim} falls to {killer}!"],
    "comeback": ["Against the odds — the crowd is on its feet!"],
    "boss_ability": ["{boss}: {ability}!"],
    "boss_down": ["{boss} has fallen! The arena erupts!"],
    "adored": ["The crowd chants your house's name!"],
    "jeered": ["Boos rain down from the stands!"],
}


def install_items():
    try:
        from content import ITEMS
    except Exception:
        return
    for iid, d in GLADIATOR_ITEMS.items():
        if iid not in ITEMS:
            ITEMS[iid] = dict(d, stackable=False, tradeable=True, sellable=True, bankable=True,
                              desc="Gladiator spoils from the Crownfall Arena.")


install_items()


def ensure_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS arena_renown (player_id INTEGER PRIMARY KEY,"
        " renown INTEGER NOT NULL DEFAULT 0, champions TEXT NOT NULL DEFAULT '[]',"
        " deed_granted INTEGER NOT NULL DEFAULT 0)")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(arena_ladder)")}
    if cols and "season" not in cols:
        conn.execute("ALTER TABLE arena_ladder ADD COLUMN season TEXT NOT NULL DEFAULT ''")
    if cols and "peak" not in cols:
        conn.execute("ALTER TABLE arena_ladder ADD COLUMN peak INTEGER NOT NULL DEFAULT 1000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS arena_season_history (player_id INTEGER, season TEXT,"
        " rating INTEGER, wins INTEGER, losses INTEGER, reward_coins INTEGER, reward_renown INTEGER,"
        " band TEXT, paid INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(player_id, season))")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS arena_saved_roster (player_id INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL, army_json TEXT NOT NULL, roster_cl INTEGER NOT NULL DEFAULT 0,"
        " saved_at REAL NOT NULL)")
    conn.commit()


# --- Renown ------------------------------------------------------------------------
def renown_row(conn, pid):
    row = conn.execute("SELECT renown, champions, deed_granted FROM arena_renown WHERE player_id=?",
                       (int(pid),)).fetchone()
    if not row:
        return {"renown": 0, "champions": [], "deed_granted": False}
    return {"renown": int(row[0]), "champions": json.loads(row[1] or "[]"), "deed_granted": bool(row[2])}


def _save_renown(conn, pid, r):
    conn.execute("INSERT OR REPLACE INTO arena_renown (player_id, renown, champions, deed_granted)"
                 " VALUES (?,?,?,?)", (int(pid), int(r["renown"]), json.dumps(sorted(r["champions"])),
                                        1 if r["deed_granted"] else 0))
    conn.commit()


def renown_title(renown):
    for low, name in RENOWN_TITLES:
        if renown >= low:
            return name
    return "Tiro"


def add_renown(conn, session, amount, source="arena"):
    amount = int(amount)
    if amount <= 0:
        return None
    r = renown_row(conn, session.player_id)
    r["renown"] += amount
    _save_renown(conn, session.player_id, r)
    new_tier = None
    try:
        import reputation
        new_tier = reputation.adjust(conn, session, source, int(amount * RENOWN_TO_REPUTATION))
    except Exception:
        pass
    return new_tier


def grant_champion_deed(conn, session):
    """Top-tier champion: a King's Row house deed (lease prepaid) plus a noble house banner."""
    r = renown_row(conn, session.player_id)
    if r["deed_granted"]:
        return None
    r["deed_granted"] = True
    _save_renown(conn, session.player_id, r)
    out = {"kind": None}
    try:
        import player_houses
        player_houses.ensure_schema(conn)
        if not player_houses.has_house(conn, session.player_id):
            nm = getattr(session, "char_name", None) or getattr(session, "username", None) or "the Sands"
            player_houses.create_house(conn, session.player_id, f"House {nm}")
            out["noble_house"] = f"House {nm}"
    except Exception:
        pass
    try:
        import housing
        housing.ensure_schema(conn)
        if housing.owned_house_key(conn, session.player_id):
            raise LookupError("owns")
        vacant = [h for h in housing.lots(conn) if h["vacant"]]
        if not vacant:
            raise LookupError("none")
        pick = min(vacant, key=lambda h: h["price"])
        now = time.time()
        conn.execute(
            "INSERT INTO housing_deeds (house_key, owner_id, owner_name, deed_issued_at,"
            " lease_paid_through, grace_until) VALUES (?,?,?,?,?,NULL)",
            (pick["key"], session.player_id, getattr(session, "char_name", "Champion"), now,
             now + DEED_LEASE_WEEKS * 7 * 86400))
        conn.commit()
        out.update(kind="deed", house_key=pick["key"], house_name=pick["name"])
        world = getattr(housing, "_WORLD", None)
        if world is not None:
            housing.install_items()
            house = housing.house_by_key(pick["key"])
            try:
                world.add_item_to_inventory(session, housing._deed_id(house), 1)
            except Exception:
                pass
    except Exception:
        session.bank_coins = int(getattr(session, "bank_coins", 0) or 0) + DEED_FALLBACK_BANK
        try:
            conn.execute("UPDATE players SET bank_coins=? WHERE id=?", (session.bank_coins, session.player_id))
            conn.commit()
        except Exception:
            pass
        out.update(kind="gold", bank=DEED_FALLBACK_BANK)
    return out


# --- Seasons -----------------------------------------------------------------------
def season_key(now=None):
    d = datetime.datetime.utcfromtimestamp(time.time() if now is None else now)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def season_ends(now=None):
    d = datetime.datetime.utcfromtimestamp(time.time() if now is None else now)
    monday = (d - datetime.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return (monday + datetime.timedelta(days=7) - datetime.datetime(1970, 1, 1)).total_seconds()


def season_band(rating):
    for low, coins, renown, band in SEASON_REWARDS:
        if rating >= low:
            return low, coins, renown, band
    return SEASON_REWARDS[-1]


def ladder(conn, pid, now=None):
    """Ladder row for this week; rolls the season over (soft reset + reward owed) when stale."""
    import mercenaries as merc
    merc.ladder_row(conn, pid)
    cur = season_key(now)
    row = conn.execute("SELECT rating, wins, losses, season, peak FROM arena_ladder WHERE player_id=?",
                       (int(pid),)).fetchone()
    rating, wins, losses, season, peak = int(row[0]), int(row[1]), int(row[2]), row[3] or "", int(row[4])
    if season != cur:
        if season and (wins + losses) > 0:
            _, coins, renown, band = season_band(rating)
            conn.execute("INSERT OR IGNORE INTO arena_season_history VALUES (?,?,?,?,?,?,?,?,0)",
                         (int(pid), season, rating, wins, losses, coins, renown, band))
        rating = int(round(merc.ELO_START + (rating - merc.ELO_START) * RANK_SOFT_RESET))
        wins = losses = 0
        conn.execute("UPDATE arena_ladder SET rating=?, wins=0, losses=0, season=?, peak=? WHERE player_id=?",
                     (rating, cur, rating, int(pid)))
        conn.commit()
        peak = rating
    return {"rating": rating, "wins": wins, "losses": losses, "season": cur, "peak": peak,
            "band": season_band(rating)[3], "ends_at": season_ends(now)}


def pay_season_rewards(conn, session):
    rows = conn.execute("SELECT season, reward_coins, reward_renown, band, rating FROM arena_season_history"
                        " WHERE player_id=? AND paid=0", (session.player_id,)).fetchall()
    paid = []
    for season, coins, renown, band, rating in rows:
        session.bank_coins = int(getattr(session, "bank_coins", 0) or 0) + int(coins)
        try:
            conn.execute("UPDATE players SET bank_coins=? WHERE id=?", (session.bank_coins, session.player_id))
        except Exception:
            pass
        conn.execute("UPDATE arena_season_history SET paid=1 WHERE player_id=? AND season=?",
                     (session.player_id, season))
        conn.commit()
        add_renown(conn, session, renown, "arena_season")
        paid.append({"season": season, "coins": int(coins), "renown": int(renown), "band": band,
                     "rating": int(rating)})
    return paid


def leaderboard(conn, limit=10):
    cur = season_key()
    rows = conn.execute(
        "SELECT l.player_id, l.rating, l.wins, l.losses, COALESCE(s.name, 'Commander ' || l.player_id)"
        " FROM arena_ladder l LEFT JOIN arena_saved_roster s ON s.player_id = l.player_id"
        " WHERE l.season = ? AND (l.wins + l.losses) > 0 ORDER BY l.rating DESC LIMIT ?",
        (cur, int(limit))).fetchall()
    return [{"rank": i + 1, "player_id": int(r[0]), "rating": int(r[1]), "wins": int(r[2]),
             "losses": int(r[3]), "name": r[4]} for i, r in enumerate(rows)]


# --- Saved rosters / rivals ------------------------------------------------------
def save_roster(conn, session):
    import mercenaries as merc
    placed = merc.battle_slots(conn, session.player_id)   # saved formation (owned soldiers only)
    if not placed:
        return
    army = []
    for r, slot in placed:
        f = merc._fighter_from_row(r)
        army.append({"template_id": r["template_id"], "name": f["name"], "levels": f["levels"],
                     "gear_tier": f["gear_tier"], "ability": f["ability"], "slot": int(slot)})
    cl = merc.roster_total_cl(merc.roster_public(conn, session.player_id))
    name = getattr(session, "char_name", None) or getattr(session, "username", None) or f"Commander {session.player_id}"
    conn.execute("INSERT OR REPLACE INTO arena_saved_roster VALUES (?,?,?,?,?)",
                 (session.player_id, str(name), json.dumps(army), int(cl), time.time()))
    conn.commit()


def rivals(conn, pid, limit=RIVAL_LIST):
    me = ladder(conn, pid)["rating"]
    rows = conn.execute("SELECT s.player_id, s.name, s.roster_cl, s.army_json, COALESCE(l.rating, 1000)"
                        " FROM arena_saved_roster s LEFT JOIN arena_ladder l ON l.player_id = s.player_id"
                        " WHERE s.player_id != ?", (int(pid),)).fetchall()
    out = []
    for r in rows:
        import mercenaries as merc
        pred = merc.predicted_elo(me, int(r[4]))
        out.append({"id": f"rival:{int(r[0])}", "player_id": int(r[0]), "name": r[1],
                    "roster_cl": int(r[2]), "soldiers": len(json.loads(r[3] or "[]")),
                    "rating": int(r[4]), "elo_win": pred["win"], "elo_loss": pred["loss"]})
    out.sort(key=lambda x: abs(x["rating"] - me))
    return out[:limit]


# --- Foe resolution ------------------------------------------------------------------
def resolve_foe(conn, session, foe_id):
    """(entry | None, error | None) for boss/rival ids; (None, None) for plain practice ids."""
    import mercenaries as merc
    fid = str(foe_id or "")
    if fid.startswith("boss:"):
        try:
            tier = int(fid.split(":", 1)[1])
        except ValueError:
            return None, "Unknown champion."
        boss = BOSSES.get(tier)
        base = next((e for e in merc.PRACTICE_TIERS if int(e["tier"]) == tier), None)
        if not boss or not base:
            return None, "Unknown champion."
        if merc.practice_highest(conn, session.player_id) < tier:
            return None, f"Beat {base['name']} first to call out {boss['name']}."
        army = merc._normalize_army(base["army"])[:merc.PRACTICE_ARMY_SIZE - 1]
        return {
            "id": fid, "name": f"{boss['name']}, {boss['title']}", "tier": tier, "boss": boss,
            "recommend_cl": int(base["recommend_cl"] * 1.25),
            "command_xp_win": int(base["command_xp_win"] * BOSS_XP_MULT),
            "command_xp_loss": base["command_xp_loss"],
            "coin_win": int(base["coin_win"] * BOSS_COIN_MULT), "army": army,
        }, None
    if fid.startswith("rival:"):
        try:
            rid = int(fid.split(":", 1)[1])
        except ValueError:
            return None, "Unknown rival."
        if rid == int(session.player_id):
            return None, "You cannot fight your own banner."
        row = conn.execute("SELECT name, army_json, roster_cl FROM arena_saved_roster WHERE player_id=?",
                           (rid,)).fetchone()
        if not row:
            return None, "That commander has no saved roster."
        rating = ladder(conn, rid)["rating"]
        tier = max(1, min(6, int(row[2]) // 120 + 1))
        return {
            "id": fid, "name": f"{row[0]}'s company", "tier": tier, "rival_id": rid, "ranked": True,
            "rival_rating": rating, "rival_army": json.loads(row[1] or "[]"),
            "recommend_cl": int(row[2]), "command_xp_win": 60 + tier * 40, "command_xp_loss": 20 + tier * 8,
            "coin_win": 100 * tier, "army": [],
        }, None
    return None, None


def refresh_saved_roster(conn, session):
    """Formation changed: re-snapshot the ladder army, but only for commanders who already
    have one (saving a formation must not enlist anyone on the ladder)."""
    ensure_schema(conn)
    if conn.execute("SELECT 1 FROM arena_saved_roster WHERE player_id=?", (session.player_id,)).fetchone():
        save_roster(conn, session)


def build_foe_fighters(entry):
    """Fighters for a rival army (saved levels/gear), or None for template armies."""
    if not entry.get("rival_army"):
        return None
    import mercenaries as merc
    out = []
    for s in entry["rival_army"][:merc.ROSTER_MAX]:
        lv = dict(s["levels"])
        hp = max(1, int(lv["hitpoints"]))
        ab = s.get("ability")
        out.append({"name": s["name"], "levels": lv, "gear_tier": s["gear_tier"], "ability": ab,
                    "hp": hp, "max_hp": hp, "first_strike": ab == "first_strike",
                    "guard_left": 1 if ab == "guard" else 0, "medic_left": 1 if ab == "field_dress" else 0,
                    "side": "foe", "template_id": s["template_id"],
                    **({"slot": int(s["slot"])} if isinstance(s.get("slot"), int) else {})})
    return out


def boss_unit(entry, xy):
    import mercenaries as merc
    b = entry["boss"]
    base = next(e for e in merc.PRACTICE_TIERS if int(e["tier"]) == int(entry["tier"]))
    top_lv = max(int(lv) for _, _, lv in merc._normalize_army(base["army"]))
    f = merc._fighter_from_snap(b["base"], b["gear"], top_lv + b["level_bonus"])
    f["max_hp"] = f["hp"] = int(f["hp"] * b["hp_mult"])
    f["name"] = b["name"]
    f["ability"] = {"blood_frenzy": "bloodlust", "second_wind": "mythos_aegis"}.get(b["ability"], f["ability"])
    u = merc._unit_from_fighter(f, "foe", xy, f"gladiator_{b['id']}")
    u.update(boss=True, boss_id=b["id"], boss_ability=b["ability"], ability_label=b["ability_label"],
             rank="front", file=2, held_reserve=False, boss_cd=4, second_wind_used=False)
    return u


# --- Ticks: boss abilities + crowd -------------------------------------------------
def _say(match, key, **kw):
    line = random.choice(ANNOUNCER[key]).format(**kw)
    match.setdefault("announce", []).append({"tick": int(match.get("tick") or 0), "text": line})
    del match["announce"][:-6]
    import mercenaries as merc
    merc._push_log(match, "Announcer: " + line)
    return line


def _favour(match, delta):
    match["crowd"] = max(0, min(100, int(match.get("crowd", CROWD_START)) + int(delta)))


def on_start(match):
    match["crowd"] = CROWD_START
    match["announce"] = []
    _say(match, "start", foe=match.get("foe_name"))
    boss = next((u for u in match["units"] if u.get("boss")), None)
    if boss:
        b = BOSSES[int(match["tier"])]
        _say(match, "boss", boss=b["name"], title=b["title"])


def on_tick(match, events):
    """Before units act: boss abilities. Stunned units skip via unit['stun']."""
    import mercenaries as merc
    boss = next((u for u in match["units"] if u.get("boss") and u["alive"] and u["hp"] > 0), None)
    if not boss:
        return
    ab = boss["boss_ability"]
    foes = [u for u in match["units"] if u["side"] != boss["side"] and u["alive"] and u["hp"] > 0
            and not u.get("held_reserve")]
    boss["boss_cd"] = int(boss.get("boss_cd") or 0) - 1
    fired = None
    if ab == "net_cast" and boss["boss_cd"] <= 0 and foes:
        t = min(foes, key=lambda f: merc._chebyshev(boss["x"], boss["y"], f["x"], f["y"]))
        t["stun"] = 3
        boss["boss_cd"] = 6
        fired = f"Net Cast snares {t['name']}"
    elif ab == "shield_wall" and boss["boss_cd"] <= 0:
        boss["guard_left"] = 2
        boss["boss_cd"] = 8
        fired = "Shield Wall"
    elif ab == "blood_frenzy" and boss["hp"] * 2 < boss["max_hp"]:
        boss["attack_cd"] = 0
        if not boss.get("frenzy_said"):
            boss["frenzy_said"] = True
            fired = "Blood Frenzy"
    elif ab == "twin_blades" and foes and random.random() < 0.35:
        near = [f for f in foes if merc._chebyshev(boss["x"], boss["y"], f["x"], f["y"]) <= merc.MATCH_MELEE_RANGE]
        if near:
            t = random.choice(near)
            dmg = merc._apply_hit(boss, t)
            events.append(merc._hit_event(boss, t, dmg))
            _kill_check(match, boss, t, events)
    elif ab == "lions_roar" and boss["boss_cd"] <= 0 and foes:
        hit = [f for f in foes if merc._chebyshev(boss["x"], boss["y"], f["x"], f["y"]) <= 3]
        for f in hit:
            f["stun"] = 2
        boss["boss_cd"] = 10
        if hit:
            fired = f"Lion's Roar stuns {len(hit)}"
    elif ab == "second_wind":
        if not boss["second_wind_used"] and boss["hp"] * 10 <= boss["max_hp"] * 4:
            boss["second_wind_used"] = True
            boss["hp"] = int(boss["max_hp"] * 0.75)
            fired = "Second Wind"
        elif boss["boss_cd"] <= 0:
            near = [f for f in foes if merc._chebyshev(boss["x"], boss["y"], f["x"], f["y"]) <= merc.MATCH_MELEE_RANGE]
            boss["boss_cd"] = 5
            for t in near:
                dmg = max(1, merc._apply_hit(boss, t) // 2)
                events.append(merc._hit_event(boss, t, dmg))
                _kill_check(match, boss, t, events)
            if near:
                fired = f"Sun Sweep hits {len(near)}"
    if fired:
        boss["attacking"] = 1.0
        _favour(match, CROWD_BOSS_HIT)
        _say(match, "boss_ability", boss=boss["name"], ability=fired)
        events.append({"type": "ARENA_BOSS_ABILITY", "unit_id": boss["id"], "text": fired})


def _kill_check(match, attacker, target, events):
    import mercenaries as merc
    if target["hp"] <= 0 and target["alive"]:
        target["alive"] = False
        events.append({"type": "DEATH", "entity_id": target["id"], "entity_kind": "arena"})
        merc._release_reserves(match, events)


def after_tick(match, events, dead_before):
    """Crowd favour + announcer from deaths this tick (ids dead before the tick are skipped)."""
    units = {u["id"]: u for u in match["units"]}
    for u in match["units"]:
        if u["id"] in dead_before or (u["alive"] and u["hp"] > 0):
            continue
        dead_before.add(u["id"])
        killer = next((units.get(a["id"]) for a in match["units"]
                       if a.get("target_id") == u["id"] and a["side"] != u["side"]), None)
        mine = u["side"] == "you"
        if not match.get("first_blood"):
            match["first_blood"] = True
            _favour(match, -CROWD_FIRST_BLOOD if mine else CROWD_FIRST_BLOOD)
            _say(match, "first_blood", side="the challenger" if not mine else match.get("foe_name"),
                 victim=u["name"])
        else:
            _favour(match, CROWD_LOSS if mine else CROWD_KILL)
            if u.get("boss"):
                _say(match, "boss_down", boss=u["name"])
                _favour(match, 15)
            elif killer and random.random() < 0.5:
                _say(match, "kill", killer=killer["name"], victim=u["name"])
        if not mine:
            you = sum(1 for x in match["units"] if x["side"] == "you" and x["alive"] and x["hp"] > 0)
            foe = sum(1 for x in match["units"] if x["side"] == "foe" and x["alive"] and x["hp"] > 0)
            if you < foe and not match.get("comeback_said"):
                match["comeback_said"] = True
                _favour(match, CROWD_COMEBACK)
                _say(match, "comeback")
    c = int(match.get("crowd", CROWD_START))
    mood = "adored" if c >= CROWD_ADORED else ("jeered" if c <= 20 else None)
    if mood and match.get("_mood") != mood:
        match["_mood"] = mood
        _say(match, mood)


def hud_extra(match):
    boss = next((u for u in match["units"] if u.get("boss")), None)
    out = {"crowd": int(match.get("crowd", CROWD_START)),
           "announce": [a["text"] for a in (match.get("announce") or [])][-3:],
           "ranked": bool((match.get("entry") or {}).get("ranked"))}
    if boss:
        out["boss"] = {"name": boss["name"], "title": BOSSES[int(match["tier"])]["title"],
                       "hp": max(0, boss["hp"]), "max_hp": boss["max_hp"],
                       "ability": boss.get("ability_label"), "id": boss["id"]}
    return out


# --- Settle ----------------------------------------------------------------------
def settle(conn, session, match, summary):
    """Extra rewards after a finished match. Mutates summary; returns a text suffix."""
    entry = match.get("entry") or {}
    won = bool(summary.get("won"))
    tier = int(match.get("tier") or 1)
    bits = []
    renown = 0
    crowd = int(match.get("crowd", CROWD_START))
    summary["crowd"] = crowd
    if won:
        renown += RENOWN_WIN_PER_TIER * tier
        purse = int(int(summary.get("coins") or 0) * CROWD_PURSE_MAX * max(0, crowd - 50) / 50.0)
        if purse:
            from content import MAX_PURSE_COINS
            session.coins = min(int(session.coins) + purse, MAX_PURSE_COINS)
            summary["crowd_purse"] = purse
            bits.append(f"crowd purse +{purse:,}")
        if crowd >= CROWD_ADORED:
            renown += RENOWN_CROWD_BONUS
    boss = entry.get("boss")
    if boss and won:
        r = renown_row(conn, session.player_id)
        first = boss["id"] not in r["champions"]
        if first:
            r["champions"].append(boss["id"])
            _save_renown(conn, session.player_id, r)
        renown += (RENOWN_BOSS_FIRST if first else RENOWN_BOSS_REPEAT) * tier
        summary["boss_first_clear"] = first
        if random.random() < (BOSS_FIRST_DROP if first else BOSS_REPEAT_DROP):
            drop = boss["drop"]
            given = True
            try:
                import housing
                world = getattr(housing, "_WORLD", None)
                if world is not None:
                    given = bool(world.add_item_to_inventory(session, drop, 1))
            except Exception:
                pass
            summary["gear_drop"] = {"item_id": drop, "name": GLADIATOR_ITEMS[drop]["name"], "given": given}
            bits.append(f"{GLADIATOR_ITEMS[drop]['name']}!" + ("" if given else " (pack full — lost)"))
        if tier == 6 and first:
            deed = grant_champion_deed(conn, session)
            if deed:
                summary["deed"] = deed
                if deed.get("kind") == "deed":
                    bits.append(f"Deed to {deed['house_name']}!")
                elif deed.get("kind") == "gold":
                    bits.append(f"Champion's purse {deed['bank']:,} to bank")
    if entry.get("ranked"):
        me = ladder(conn, session.player_id)
        d = __import__("mercenaries").elo_delta(me["rating"], int(entry["rival_rating"]), won)
        new = me["rating"] + d
        conn.execute("UPDATE arena_ladder SET rating=?, wins=wins+?, losses=losses+?, peak=MAX(peak, ?)"
                     " WHERE player_id=?", (new, 1 if won else 0, 0 if won else 1, new, session.player_id))
        conn.commit()
        summary["elo"] = {"before": me["rating"], "after": new, "delta": d}
        bits.append(f"Elo {me['rating']}→{new} ({d:+d})")
        if won:
            renown += RENOWN_RANKED_WIN
    try:
        save_roster(conn, session)
    except Exception:
        pass
    if renown:
        tier_change = add_renown(conn, session, renown)
        summary["renown_gain"] = renown
        bits.append(f"+{renown} renown")
        if tier_change:
            bits.append(f"standing now {tier_change}")
    rr = renown_row(conn, session.player_id)
    summary["renown"] = rr["renown"]
    summary["renown_title"] = renown_title(rr["renown"])
    return (" · " + " · ".join(bits)) if bits else ""


def payload(conn, session):
    rr = renown_row(conn, session.player_id)
    paid = pay_season_rewards(conn, session)
    lad = ladder(conn, session.player_id)
    import mercenaries as merc
    highest = merc.practice_highest(conn, session.player_id)
    bosses = []
    for tier, b in BOSSES.items():
        entry, _ = resolve_foe(conn, session, f"boss:{tier}") if highest >= tier else (None, None)
        bosses.append({"id": f"boss:{tier}", "tier": tier, "name": b["name"], "title": b["title"],
                       "boss_id": b["id"], "ability": b["ability_label"], "unlocked": highest >= tier,
                       "beaten": b["id"] in rr["champions"], "drop": GLADIATOR_ITEMS[b["drop"]]["name"],
                       "drop_id": b["drop"],
                       "coin_win": (entry or {}).get("coin_win", 0),
                       "recommend_cl": (entry or {}).get("recommend_cl", 0)})
    return {"renown": rr["renown"], "renown_title": renown_title(rr["renown"]),
            "champions": rr["champions"], "deed_granted": rr["deed_granted"],
            "bosses": bosses, "ladder": lad, "leaderboard": leaderboard(conn),
            "rivals": rivals(conn, session.player_id), "season_paid": paid}
