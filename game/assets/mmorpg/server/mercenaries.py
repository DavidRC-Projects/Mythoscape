"""Castle Realm mercenary barracks, practice board, and Command unlocks.

Players field up to 10 AI soldiers. Practice vs NPC houses grants Command XP
(no Elo). Mythos soldiers unlock at Command 80. Soldier visuals use player_hd
armour tiers keyed by gear_tier.
"""
from __future__ import annotations

import math
import random
import time

import combat
from content import ITEMS

ROSTER_MAX = 10
ELO_START = 1000
ELO_K = 32

# Gear kits sold by the quartermaster (coins). Mythos kit needs Command 80.
GEAR_KITS = {
    "bronze": {"label": "Bronze kit", "cost": 250, "command_req": 1},
    "iron": {"label": "Iron kit", "cost": 900, "command_req": 1},
    "steel": {"label": "Steel kit", "cost": 2_500, "command_req": 10},
    "mithril": {"label": "Mithril kit", "cost": 8_000, "command_req": 40},
    "adamant": {"label": "Adamant kit", "cost": 22_000, "command_req": 50},
    "mythos": {"label": "Mythos kit", "cost": 120_000, "command_req": 80},
}

# Matching plate set for combat bonuses + player_hd armour_*_bh_hd art.
TIER_EQUIP = {
    "bronze": {
        "weapon": "bronze_sword", "shield": "bronze_shield",
        "helmet": "bronze_helmet", "body": "bronze_body", "legs": "bronze_legs",
    },
    "iron": {
        "weapon": "iron_sword", "shield": "iron_shield",
        "helmet": "iron_helmet", "body": "iron_body", "legs": "iron_legs",
    },
    "steel": {
        "weapon": "steel_longsword", "shield": "steel_shield",
        "helmet": "steel_helmet", "body": "steel_body", "legs": "steel_legs",
    },
    "mithril": {
        "weapon": "mithril_sword", "shield": "mithril_shield",
        "helmet": "mithril_helmet", "body": "mithril_body", "legs": "mithril_legs",
    },
    "adamant": {
        "weapon": "adamant_sword", "shield": "adamant_shield",
        "helmet": "adamant_helmet", "body": "adamant_body", "legs": "adamant_legs",
    },
    "mythos": {
        "weapon": "mythos_longsword", "shield": "mythos_shield",
        "helmet": "mythos_helmet", "body": "mythos_body", "legs": "mythos_legs",
    },
}

# Template catalogue. command_req gates recruit. train_speed multiplies Training Centre XP.
TEMPLATES = {
    "levy": {
        "name": "Levy", "role": "fodder", "cost": 80,
        "attack": 5, "strength": 5, "defence": 5, "hitpoints": 10,
        "train_speed": 1.15, "ability": None, "command_req": 1,
        "default_gear": "bronze", "blurb": "Cheap bodies. Train fast.",
    },
    "man_at_arms": {
        "name": "Man-at-arms", "role": "line", "cost": 280,
        "attack": 12, "strength": 12, "defence": 12, "hitpoints": 18,
        "train_speed": 1.0, "ability": None, "command_req": 1,
        "default_gear": "bronze", "blurb": "Reliable front-line soldier.",
    },
    "veteran": {
        "name": "Veteran", "role": "line", "cost": 900,
        "attack": 28, "strength": 28, "defence": 26, "hitpoints": 40,
        "train_speed": 0.85, "ability": None, "command_req": 10,
        "default_gear": "iron", "blurb": "Hardened fighter. Slower to train.",
    },
    "skirmisher": {
        "name": "Skirmisher", "role": "flank", "cost": 1_100,
        "attack": 32, "strength": 24, "defence": 18, "hitpoints": 28,
        "train_speed": 1.0, "ability": "first_strike", "command_req": 10,
        "default_gear": "iron", "blurb": "First Strike — opens with a free hit.",
    },
    "bulwark": {
        "name": "Bulwark", "role": "tank", "cost": 1_800,
        "attack": 22, "strength": 22, "defence": 40, "hitpoints": 55,
        "train_speed": 0.9, "ability": "guard", "command_req": 20,
        "default_gear": "steel", "blurb": "Guard — soaks the first big hits.",
    },
    "zealot": {
        "name": "Zealot", "role": "glass", "cost": 1_900,
        "attack": 38, "strength": 40, "defence": 16, "hitpoints": 30,
        "train_speed": 0.95, "ability": "bloodlust", "command_req": 20,
        "default_gear": "steel", "blurb": "Bloodlust — hits harder below half HP.",
    },
    "duelist": {
        "name": "Duelist", "role": "elite", "cost": 3_500,
        "attack": 48, "strength": 42, "defence": 36, "hitpoints": 48,
        "train_speed": 0.8, "ability": "riposte", "command_req": 30,
        "default_gear": "mithril", "blurb": "Riposte — returns a cut after being hit.",
    },
    "medic": {
        "name": "Medic", "role": "support", "cost": 4_200,
        "attack": 18, "strength": 16, "defence": 28, "hitpoints": 42,
        "train_speed": 0.85, "ability": "field_dress", "command_req": 40,
        "default_gear": "mithril", "blurb": "Field Dress — heals an ally once per fight. Max 1.",
        "max_per_roster": 1,
    },
    "mythos_guard": {
        "name": "Mythos Guard", "role": "elite", "cost": 85_000,
        "attack": 72, "strength": 70, "defence": 68, "hitpoints": 90,
        "train_speed": 0.7, "ability": "mythos_aegis", "command_req": 80,
        "default_gear": "mythos", "blurb": "Crownsteel elite. Needs Command 80.",
    },
}

ABILITY_LABELS = {
    None: "—",
    "first_strike": "First Strike",
    "guard": "Guard",
    "bloodlust": "Bloodlust",
    "riposte": "Riposte",
    "field_dress": "Field Dress",
    "mythos_aegis": "Mythos Aegis",
}

# Promote in place — keeps name, battle/train XP, and kit. Cost = next recruit
# price minus current template price (floor 50c). Specialists fold into the line.
UPGRADE_NEXT = {
    "levy": "man_at_arms",
    "man_at_arms": "veteran",
    "veteran": "duelist",
    "duelist": "mythos_guard",
    "skirmisher": "duelist",
    "bulwark": "mythos_guard",
    "zealot": "duelist",
    # medic stays unique (max 1) — no promote path
}

GEAR_TIER_RANK = {
    "bronze": 0, "iron": 1, "steel": 2, "mithril": 3, "adamant": 4, "mythos": 5,
}

# Practice board — graded NPC houses. Every house fields exactly 10 soldiers
# (5 front / 5 rear when lined up). Beating a tier unlocks the next.
PRACTICE_ARMY_SIZE = 10
DAILY_FIGHT_CAP = 10

PRACTICE_TIERS = [
    {
        "id": "squire_alden", "name": "Squire Alden", "tier": 1,
        "recommend_cl": 70, "command_xp_win": 40, "command_xp_loss": 12, "coin_win": 40,
        "army": [("levy", "bronze", 5)] * 8 + [("man_at_arms", "bronze", 8)] * 2,
    },
    {
        "id": "dame_rowan", "name": "Dame Rowan", "tier": 2,
        "recommend_cl": 120, "command_xp_win": 90, "command_xp_loss": 25, "coin_win": 120,
        "army": [("man_at_arms", "iron", 12)] * 8 + [("skirmisher", "iron", 14)] * 2,
    },
    {
        "id": "lord_halwick", "name": "Lord Halwick", "tier": 3,
        "recommend_cl": 200, "command_xp_win": 180, "command_xp_loss": 45, "coin_win": 350,
        "army": (
            [("man_at_arms", "steel", 20)] * 4
            + [("veteran", "steel", 28)] * 4
            + [("skirmisher", "steel", 28)] * 2
        ),
    },
    {
        "id": "countess_veyra", "name": "Countess Veyra", "tier": 4,
        "recommend_cl": 340, "command_xp_win": 320, "command_xp_loss": 80, "coin_win": 900,
        "army": (
            [("veteran", "mithril", 40)] * 5
            + [("duelist", "mithril", 45)] * 3
            + [("medic", "mithril", 40)] * 1
            + [("bulwark", "mithril", 42)] * 1
        ),
    },
    {
        "id": "duke_ironwood", "name": "Duke Ironwood", "tier": 5,
        "recommend_cl": 500, "command_xp_win": 480, "command_xp_loss": 120, "coin_win": 2_200,
        "army": [("duelist", "adamant", 55)] * 5 + [("bulwark", "adamant", 55)] * 4 + [("medic", "adamant", 50)] * 1,
    },
    {
        "id": "king_crownfall", "name": "King of Crownfall", "tier": 6,
        "recommend_cl": 720, "command_xp_win": 750, "command_xp_loss": 180, "coin_win": 6_000,
        "army": [("mythos_guard", "mythos", 70)] * 8 + [("medic", "mythos", 60)] * 2,
    },
]

MARSHAL_OPTIONS = [
    {"id": "barracks_open", "label": "Open barracks"},
    {"id": "practice_board", "label": "Practice board"},
    {"id": "command_info", "label": "What is Command?"},
]

QUARTERMASTER_OPTIONS = [
    {"id": "barracks_open", "label": "Outfit my soldiers"},
    {"id": "kit_prices", "label": "Kit prices"},
]

COMMAND_UNLOCK_ROWS = [
    (1, "Recruit Levy and Man-at-arms"),
    (10, "Recruit Veteran and Skirmisher; order cooldown −10%"),
    (20, "Recruit Bulwark and Zealot; train efficiency +10%"),
    (30, "Recruit Duelist; daily upkeep −10%"),
    (40, "Recruit Medic; mithril kits"),
    (50, "Adamant kits"),
    (60, "Smelt Mythos ore (also needs Smithing 60)"),
    (70, "Practice Duke/King ore drop weight bump"),
    (80, "Recruit Mythos Guard; Mythos kits; smith Mythos gear (Smithing 70+)"),
    (99, "Title: Warlord"),
]


def ensure_schema(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "command_xp" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN command_xp INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS mercenary_roster ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "player_id INTEGER NOT NULL,"
        "template_id TEXT NOT NULL,"
        "name TEXT NOT NULL,"
        "attack_xp INTEGER NOT NULL,"
        "strength_xp INTEGER NOT NULL,"
        "defence_xp INTEGER NOT NULL,"
        "hitpoints_xp INTEGER NOT NULL,"
        "gear_tier TEXT NOT NULL DEFAULT 'bronze',"
        "created_at REAL NOT NULL,"
        "FOREIGN KEY(player_id) REFERENCES players(id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS arena_ladder ("
        "player_id INTEGER PRIMARY KEY,"
        "rating INTEGER NOT NULL DEFAULT 1000,"
        "wins INTEGER NOT NULL DEFAULT 0,"
        "losses INTEGER NOT NULL DEFAULT 0,"
        "FOREIGN KEY(player_id) REFERENCES players(id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS practice_progress ("
        "player_id INTEGER PRIMARY KEY,"
        "highest_tier INTEGER NOT NULL DEFAULT 0,"
        "fights_today INTEGER NOT NULL DEFAULT 0,"
        "fights_day TEXT NOT NULL DEFAULT '',"
        "FOREIGN KEY(player_id) REFERENCES players(id))"
    )
    # Migrate older DBs that only had highest_tier.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(practice_progress)").fetchall()}
    if "fights_today" not in cols:
        conn.execute(
            "ALTER TABLE practice_progress ADD COLUMN fights_today INTEGER NOT NULL DEFAULT 0"
        )
    if "fights_day" not in cols:
        conn.execute(
            "ALTER TABLE practice_progress ADD COLUMN fights_day TEXT NOT NULL DEFAULT ''"
        )
    roster_cols = {row[1] for row in conn.execute("PRAGMA table_info(mercenary_roster)").fetchall()}
    if "train_day" not in roster_cols:
        conn.execute(
            "ALTER TABLE mercenary_roster ADD COLUMN train_day TEXT NOT NULL DEFAULT ''"
        )
    if "trains_today" not in roster_cols:
        conn.execute(
            "ALTER TABLE mercenary_roster ADD COLUMN trains_today INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def _today_key() -> str:
    return time.strftime("%Y-%m-%d")


DAILY_TRAIN_CAP = 10


def soldier_trains_today(row) -> dict:
    """Per-soldier daily train slots (each train = +1 level in one skill)."""
    day = _today_key()
    try:
        used = int(row["trains_today"] or 0) if (row["train_day"] or "") == day else 0
    except (IndexError, KeyError, TypeError):
        used = 0
    return {
        "used": used,
        "cap": DAILY_TRAIN_CAP,
        "remaining": max(0, DAILY_TRAIN_CAP - used),
        "day": day,
    }


def daily_fights(conn, player_id: int) -> dict:
    """Return {used, cap, remaining, day} with midnight reset."""
    day = _today_key()
    row = conn.execute(
        "SELECT fights_today, fights_day FROM practice_progress WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    if not row:
        return {"used": 0, "cap": DAILY_FIGHT_CAP, "remaining": DAILY_FIGHT_CAP, "day": day}
    used = int(row[0] or 0) if (row[1] or "") == day else 0
    return {
        "used": used,
        "cap": DAILY_FIGHT_CAP,
        "remaining": max(0, DAILY_FIGHT_CAP - used),
        "day": day,
    }


def consume_daily_fight(conn, player_id: int) -> tuple[bool, str, dict]:
    """Spend one of today's fight slots. Returns (ok, message, daily info)."""
    info = daily_fights(conn, player_id)
    if info["remaining"] <= 0:
        return False, f"You have used all {DAILY_FIGHT_CAP} arena fights for today. Return tomorrow.", info
    day = info["day"]
    used = info["used"] + 1
    conn.execute(
        "INSERT INTO practice_progress (player_id, highest_tier, fights_today, fights_day) "
        "VALUES (?, 0, ?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET fights_today = ?, fights_day = ?",
        (player_id, used, day, used, day),
    )
    conn.commit()
    info = daily_fights(conn, player_id)
    return True, "", info


def command_level(session) -> int:
    return int(session.level("command")) if "command" in session.xp else 1


def unlocks_for(level: int) -> list[dict]:
    rows = []
    for req, text in COMMAND_UNLOCK_ROWS:
        rows.append({"level": req, "text": text, "unlocked": int(level) >= req})
    return rows


def next_unlock(level: int) -> dict | None:
    for req, text in COMMAND_UNLOCK_ROWS:
        if int(level) < req:
            return {"level": req, "text": text}
    return None


def soldier_levels(row) -> dict:
    return {
        "attack": combat.level_from_xp(int(row["attack_xp"])),
        "strength": combat.level_from_xp(int(row["strength_xp"])),
        "defence": combat.level_from_xp(int(row["defence_xp"])),
        "hitpoints": combat.level_from_xp(int(row["hitpoints_xp"])),
    }


def soldier_combat_level(levels: dict) -> int:
    return combat.combat_level(
        levels["attack"], levels["strength"], levels["defence"],
        levels["hitpoints"], 1,
    )


def equip_bonuses(gear_tier: str) -> dict:
    eq = TIER_EQUIP.get(gear_tier) or TIER_EQUIP["bronze"]
    att = str_ = deff = 0
    for item_id in eq.values():
        item = ITEMS.get(item_id) or {}
        att += int(item.get("att_bonus") or 0)
        str_ += int(item.get("str_bonus") or 0)
        deff += int(item.get("def_bonus") or 0)
    return {"attack_bonus": att, "strength_bonus": str_, "defence_bonus": deff}


def fight_stats(levels: dict, gear_tier: str, ability: str | None = None, hp_ratio: float = 1.0) -> dict:
    bonus = equip_bonuses(gear_tier)
    att = levels["attack"]
    strength = levels["strength"]
    defence = levels["defence"]
    if ability == "bloodlust" and hp_ratio < 0.5:
        strength = int(strength * 1.25)
        bonus["strength_bonus"] = int(bonus["strength_bonus"] * 1.15)
    if ability == "mythos_aegis":
        defence = int(defence * 1.1)
        bonus["defence_bonus"] = int(bonus["defence_bonus"] * 1.1)
    return {
        "attack": att,
        "strength": strength,
        "defence": defence,
        "attack_bonus": bonus["attack_bonus"],
        "strength_bonus": bonus["strength_bonus"],
        "defence_bonus": bonus["defence_bonus"],
    }


def upgrade_info(row, cmd_lvl: int) -> dict | None:
    """Next template + cost for an in-place promote, or None if maxed/locked."""
    cur_id = row["template_id"]
    nxt_id = UPGRADE_NEXT.get(cur_id)
    if not nxt_id:
        return None
    cur = TEMPLATES.get(cur_id) or TEMPLATES["levy"]
    nxt = TEMPLATES.get(nxt_id)
    if not nxt:
        return None
    cost = max(50, int(nxt["cost"]) - int(cur["cost"]))
    locked = cmd_lvl < int(nxt["command_req"])
    return {
        "to_id": nxt_id,
        "to_name": nxt["name"],
        "cost": cost,
        "command_req": int(nxt["command_req"]),
        "locked": locked,
        "ability_label": ABILITY_LABELS.get(nxt.get("ability"), "—"),
        "blurb": nxt.get("blurb") or "",
    }


def soldier_public(row, session=None) -> dict:
    tmpl = TEMPLATES.get(row["template_id"]) or TEMPLATES["levy"]
    levels = soldier_levels(row)
    cl = soldier_combat_level(levels)
    gear = row["gear_tier"] if row["gear_tier"] in TIER_EQUIP else "bronze"
    daily = soldier_trains_today(row)
    # Preview cost for Attack next level (UI shows ~cost; actual varies by skill).
    if session is not None:
        train_cost = train_cost_for_row(session, row, "attack")
        cmd = command_level(session)
    else:
        need = max(1, combat.xp_to_next_level(int(row["attack_xp"])))
        speed = max(0.5, float(tmpl["train_speed"]))
        train_cost = max(1, int(math.ceil(need * TRAIN_COIN_PER_XP / speed)))
        cmd = 1
    up = upgrade_info(row, cmd)
    return {
        "id": int(row["id"]),
        "template_id": row["template_id"],
        "template_name": tmpl["name"],
        "name": row["name"],
        "role": tmpl["role"],
        "ability": tmpl.get("ability"),
        "ability_label": ABILITY_LABELS.get(tmpl.get("ability"), "—"),
        "levels": levels,
        "combat_level": cl,
        "gear_tier": gear,
        "equipment": dict(TIER_EQUIP[gear]),
        "train_speed": float(tmpl["train_speed"]),
        "train_cost": train_cost,
        "trains_today": daily,
        "blurb": tmpl.get("blurb") or "",
        "upgrade": up,
    }


def roster_rows(conn, player_id: int):
    return conn.execute(
        "SELECT * FROM mercenary_roster WHERE player_id = ? ORDER BY id",
        (player_id,),
    ).fetchall()


def roster_public(conn, player_id: int, session=None) -> list[dict]:
    return [soldier_public(r, session=session) for r in roster_rows(conn, player_id)]


def roster_total_cl(soldiers: list[dict]) -> int:
    return sum(int(s["combat_level"]) for s in soldiers)


def practice_highest(conn, player_id: int) -> int:
    row = conn.execute(
        "SELECT highest_tier FROM practice_progress WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def set_practice_highest(conn, player_id: int, tier: int):
    cur = practice_highest(conn, player_id)
    if tier <= cur:
        return
    conn.execute(
        "INSERT INTO practice_progress (player_id, highest_tier) VALUES (?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET highest_tier = excluded.highest_tier",
        (player_id, tier),
    )
    conn.commit()


def ladder_row(conn, player_id: int) -> dict:
    row = conn.execute(
        "SELECT rating, wins, losses FROM arena_ladder WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO arena_ladder (player_id, rating) VALUES (?, ?)",
            (player_id, ELO_START),
        )
        conn.commit()
        return {"rating": ELO_START, "wins": 0, "losses": 0}
    return {"rating": int(row[0]), "wins": int(row[1]), "losses": int(row[2])}


def elo_delta(rating_self: int, rating_opp: int, won: bool) -> int:
    expected = 1.0 / (1.0 + 10 ** ((rating_opp - rating_self) / 400.0))
    score = 1.0 if won else 0.0
    return int(round(ELO_K * (score - expected)))


def predicted_elo(rating_self: int, rating_opp: int) -> dict:
    return {
        "win": elo_delta(rating_self, rating_opp, True),
        "loss": elo_delta(rating_self, rating_opp, False),
    }


def recruitable_templates(cmd_lvl: int, roster_rows_list=None) -> list[dict]:
    """Catalogue for the Recruit tab. Includes in-place upgrade offers from roster."""
    from_map = {}
    for cur_id, nxt_id in UPGRADE_NEXT.items():
        from_map.setdefault(nxt_id, []).append(cur_id)
    out = []
    for tid, t in TEMPLATES.items():
        locked = cmd_lvl < int(t["command_req"])
        # Cheapest eligible roster soldier who promotes into this template.
        upgrade_from = None
        if roster_rows_list and not locked:
            best = None
            for row in roster_rows_list:
                if row["template_id"] not in from_map.get(tid, ()):
                    continue
                info = upgrade_info(row, cmd_lvl)
                if not info or info["to_id"] != tid or info["locked"]:
                    continue
                cand = {
                    "soldier_id": int(row["id"]),
                    "soldier_name": row["name"],
                    "from_id": row["template_id"],
                    "from_name": (TEMPLATES.get(row["template_id"]) or {}).get("name") or row["template_id"],
                    "cost": int(info["cost"]),
                }
                if best is None or cand["cost"] < best["cost"]:
                    best = cand
            upgrade_from = best
        out.append({
            "id": tid,
            "name": t["name"],
            "cost": t["cost"],
            "command_req": t["command_req"],
            "locked": locked,
            "ability_label": ABILITY_LABELS.get(t.get("ability"), "—"),
            "combat_level": combat.combat_level(
                t["attack"], t["strength"], t["defence"], t["hitpoints"], 1,
            ),
            "train_speed": t["train_speed"],
            "default_gear": t["default_gear"],
            "blurb": t.get("blurb") or "",
            "equipment": dict(TIER_EQUIP[t["default_gear"]]),
            "max_per_roster": t.get("max_per_roster"),
            "upgrade_from": upgrade_from,
        })
    return out


def kit_catalogue(cmd_lvl: int) -> list[dict]:
    rows = []
    for tier, info in GEAR_KITS.items():
        rows.append({
            "tier": tier,
            "label": info["label"],
            "cost": info["cost"],
            "command_req": info["command_req"],
            "locked": cmd_lvl < int(info["command_req"]),
            "equipment": dict(TIER_EQUIP[tier]),
        })
    return rows


def practice_board(conn, player_id: int, roster_cl: int) -> list[dict]:
    highest = practice_highest(conn, player_id)
    board = []
    for entry in PRACTICE_TIERS:
        tier = int(entry["tier"])
        unlocked = tier <= highest + 1
        army = _normalize_army(entry["army"])
        foe_cl = _snapshot_army_cl(army)
        board.append({
            "id": entry["id"],
            "name": entry["name"],
            "tier": tier,
            "unlocked": unlocked,
            "recommend_cl": entry["recommend_cl"],
            "foe_combat_level": foe_cl,
            "foe_soldiers": len(army),
            "your_combat_level": roster_cl,
            "power_gap": roster_cl - foe_cl,
            "command_xp_win": entry["command_xp_win"],
            "command_xp_loss": entry["command_xp_loss"],
            "coin_win": entry["coin_win"],
            "advice": _power_advice(roster_cl, entry["recommend_cl"]),
        })
    return board


def _power_advice(roster_cl: int, recommend: int) -> str:
    if roster_cl <= 0:
        return "Recruit soldiers first."
    ratio = roster_cl / max(1, recommend)
    if ratio < 0.7:
        return "Outmatched — train or kit up."
    if ratio < 0.95:
        return "Close fight — watch your orders."
    if ratio < 1.2:
        return "Even match."
    return "You should win."


def _snapshot_army_cl(army) -> int:
    total = 0
    for template_id, gear, level in army:
        tmpl = TEMPLATES.get(template_id) or TEMPLATES["levy"]
        lv = max(int(level), tmpl["attack"])
        levels = {
            "attack": lv, "strength": lv, "defence": max(1, lv - 2),
            "hitpoints": max(10, int(lv * 1.2)),
        }
        # Rough gear bump via combat formula bonuses is applied in sim; CL stays level-based.
        total += soldier_combat_level(levels)
    return total


def _xp_for_base_levels(tmpl: dict) -> dict:
    return {
        "attack_xp": combat.xp_for_level(tmpl["attack"]),
        "strength_xp": combat.xp_for_level(tmpl["strength"]),
        "defence_xp": combat.xp_for_level(tmpl["defence"]),
        "hitpoints_xp": combat.xp_for_level(tmpl["hitpoints"]),
    }


TRAIN_SKILLS = ("attack", "strength", "defence", "hitpoints")
# Coins per XP needed for the next level; Command 20+ trains ~10% cheaper via speed.
TRAIN_COIN_PER_XP = 2.5
TRAIN_XP_CHUNK = 50  # legacy; train() now grants +1 level per click

# Given names for recruits — personal name + template type shown in UI.
SOLDIER_FIRST_NAMES = (
    "Aldric", "Bram", "Cedric", "Dara", "Edric", "Faye", "Garrick", "Helena",
    "Ivor", "Jora", "Kael", "Lira", "Merek", "Nessa", "Orin", "Petra",
    "Quinn", "Roran", "Sera", "Torin", "Una", "Vance", "Wynn", "Yara",
    "Zane", "Anwen", "Bryn", "Corin", "Delia", "Ewan", "Fionn", "Gwen",
    "Harlan", "Isla", "Joss", "Kira", "Leif", "Mara", "Nolan", "Oona",
    "Perrin", "Rhea", "Silas", "Tamsin", "Ulric", "Vera", "Wren", "Yorick",
)


def wealth(session) -> int:
    return int(getattr(session, "coins", 0) or 0) + int(getattr(session, "bank_coins", 0) or 0)


def spend_coins(session, cost: int) -> tuple[bool, str, int, int]:
    """Pay from purse first, then bank. Returns (ok, error, purse_spent, bank_spent)."""
    cost = max(0, int(cost))
    if cost <= 0:
        return True, "", 0, 0
    purse = int(getattr(session, "coins", 0) or 0)
    bank = int(getattr(session, "bank_coins", 0) or 0)
    if purse + bank < cost:
        return False, f"Need {cost:,} coins (purse + bank).", 0, 0
    from_purse = min(purse, cost)
    from_bank = cost - from_purse
    session.coins = purse - from_purse
    session.bank_coins = bank - from_bank
    return True, "", from_purse, from_bank


def _spend_note(cost: int, purse_spent: int, bank_spent: int) -> str:
    if bank_spent and purse_spent:
        return f"−{cost:,} ({purse_spent:,} purse + {bank_spent:,} bank)"
    if bank_spent:
        return f"−{cost:,} from bank"
    return f"−{cost:,} coins"


def _train_speed(session, template_id: str) -> float:
    tmpl = TEMPLATES.get(template_id) or TEMPLATES["levy"]
    speed = float(tmpl["train_speed"])
    if command_level(session) >= 20:
        speed *= 1.10
    return max(0.5, speed)


def train_cost_for_row(session, row, skill: str) -> int:
    """Coin cost to raise one skill by exactly one level."""
    col = f"{skill}_xp"
    before_xp = int(row[col])
    before_lvl = combat.level_from_xp(before_xp)
    if before_lvl >= 99:
        return 0
    need = max(1, combat.xp_to_next_level(before_xp))
    speed = _train_speed(session, row["template_id"])
    return max(1, int(math.ceil(need * TRAIN_COIN_PER_XP / speed)))


def train_cost_for(session, template_id: str) -> int:
    """Rough next-level cost from template base levels (catalogue / empty preview)."""
    tmpl = TEMPLATES.get(template_id) or TEMPLATES["levy"]
    fake = {
        "template_id": template_id,
        "attack_xp": combat.xp_for_level(tmpl["attack"]),
        "strength_xp": combat.xp_for_level(tmpl["strength"]),
        "defence_xp": combat.xp_for_level(tmpl["defence"]),
        "hitpoints_xp": combat.xp_for_level(tmpl["hitpoints"]),
    }
    return train_cost_for_row(session, fake, "attack")


def random_soldier_name(conn, player_id: int, template_id: str) -> str:
    """Pick a first name not already used on this roster; fall back with a numeral."""
    used = {
        str(r["name"]).split()[0]
        for r in roster_rows(conn, player_id)
        if r["name"]
    }
    pool = [n for n in SOLDIER_FIRST_NAMES if n not in used]
    if pool:
        return random.choice(pool)
    base = random.choice(SOLDIER_FIRST_NAMES)
    n = 2
    while f"{base} {n}" in {str(r["name"]) for r in roster_rows(conn, player_id)}:
        n += 1
    return f"{base} {n}"


def recruit(conn, session, template_id: str) -> tuple[bool, str, dict | None]:
    tmpl = TEMPLATES.get(template_id)
    if not tmpl:
        return False, "Unknown soldier type.", None
    cmd = command_level(session)
    if cmd < int(tmpl["command_req"]):
        return False, f"Need Command {tmpl['command_req']} to recruit {tmpl['name']}.", None
    rows = roster_rows(conn, session.player_id)
    if len(rows) >= ROSTER_MAX:
        return False, f"Roster full ({ROSTER_MAX}). Dismiss someone first.", None
    cap = tmpl.get("max_per_roster")
    if cap is not None:
        have = sum(1 for r in rows if r["template_id"] == template_id)
        if have >= int(cap):
            return False, f"You may only field {cap} {tmpl['name']}.", None
    cost = int(tmpl["cost"])
    ok, err, purse_spent, bank_spent = spend_coins(session, cost)
    if not ok:
        return False, err, None
    xp = _xp_for_base_levels(tmpl)
    gear = tmpl["default_gear"]
    if gear == "mythos" and cmd < 80:
        gear = "adamant"
    given = random_soldier_name(conn, session.player_id, template_id)
    cur = conn.execute(
        "INSERT INTO mercenary_roster "
        "(player_id, template_id, name, attack_xp, strength_xp, defence_xp, hitpoints_xp, gear_tier, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session.player_id, template_id, given,
            xp["attack_xp"], xp["strength_xp"], xp["defence_xp"], xp["hitpoints_xp"],
            gear, time.time(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM mercenary_roster WHERE id = ?", (cur.lastrowid,)).fetchone()
    return (
        True,
        f"Recruited {given} ({tmpl['name']}) ({_spend_note(cost, purse_spent, bank_spent)}).",
        soldier_public(row),
    )


def dismiss(conn, session, soldier_id: int) -> tuple[bool, str]:
    row = conn.execute(
        "SELECT id, name FROM mercenary_roster WHERE id = ? AND player_id = ?",
        (soldier_id, session.player_id),
    ).fetchone()
    if not row:
        return False, "That soldier is not in your roster."
    # Pull them off the field before deleting the roster row.
    if int(soldier_id) in set(deployed_roster_ids(session)):
        recall_soldiers(session, soldier_id)
    conn.execute("DELETE FROM mercenary_roster WHERE id = ?", (soldier_id,))
    conn.commit()
    return True, f"{row['name']} has been dismissed."


def upgrade(conn, session, soldier_id: int) -> tuple[bool, str, dict | None]:
    """Promote a soldier to the next template. Keeps name, XP, and kit."""
    row = conn.execute(
        "SELECT * FROM mercenary_roster WHERE id = ? AND player_id = ?",
        (soldier_id, session.player_id),
    ).fetchone()
    if not row:
        return False, "That soldier is not in your roster.", None
    cmd = command_level(session)
    info = upgrade_info(row, cmd)
    if not info:
        return False, f"{row['name']} is already at the top of their path.", None
    if info["locked"]:
        return (
            False,
            f"Need Command {info['command_req']} to promote to {info['to_name']}.",
            None,
        )
    nxt = TEMPLATES[info["to_id"]]
    cap = nxt.get("max_per_roster")
    if cap is not None:
        have = sum(
            1 for r in roster_rows(conn, session.player_id)
            if r["template_id"] == info["to_id"] and int(r["id"]) != int(soldier_id)
        )
        if have >= int(cap):
            return False, f"You may only field {cap} {nxt['name']}.", None
    cost = int(info["cost"])
    ok, err, purse_spent, bank_spent = spend_coins(session, cost)
    if not ok:
        return False, err, None
    # Floor each skill XP to the new template base — never lose battle progress.
    base_xp = _xp_for_base_levels(nxt)
    att_xp = max(int(row["attack_xp"]), base_xp["attack_xp"])
    str_xp = max(int(row["strength_xp"]), base_xp["strength_xp"])
    def_xp = max(int(row["defence_xp"]), base_xp["defence_xp"])
    hp_xp = max(int(row["hitpoints_xp"]), base_xp["hitpoints_xp"])
    gear = row["gear_tier"] if row["gear_tier"] in TIER_EQUIP else "bronze"
    default_gear = nxt["default_gear"]
    if default_gear == "mythos" and cmd < 80:
        default_gear = "adamant"
    if GEAR_TIER_RANK.get(default_gear, 0) > GEAR_TIER_RANK.get(gear, 0):
        gear = default_gear
    conn.execute(
        "UPDATE mercenary_roster SET template_id = ?, attack_xp = ?, strength_xp = ?, "
        "defence_xp = ?, hitpoints_xp = ?, gear_tier = ? WHERE id = ?",
        (info["to_id"], att_xp, str_xp, def_xp, hp_xp, gear, soldier_id),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM mercenary_roster WHERE id = ?", (soldier_id,)
    ).fetchone()
    return (
        True,
        f"{row['name']} promoted to {info['to_name']} "
        f"(keeps battle XP · {_spend_note(cost, purse_spent, bank_spent)}).",
        soldier_public(updated, session=session),
    )


def outfit(conn, session, soldier_id: int, tier: str) -> tuple[bool, str]:
    info = GEAR_KITS.get(tier)
    if not info:
        return False, "Unknown kit."
    cmd = command_level(session)
    if cmd < int(info["command_req"]):
        return False, f"Need Command {info['command_req']} for {info['label']}."
    row = conn.execute(
        "SELECT * FROM mercenary_roster WHERE id = ? AND player_id = ?",
        (soldier_id, session.player_id),
    ).fetchone()
    if not row:
        return False, "That soldier is not in your roster."
    if row["gear_tier"] == tier:
        return False, f"{row['name']} already wears {info['label']}."
    cost = int(info["cost"])
    ok, err, purse_spent, bank_spent = spend_coins(session, cost)
    if not ok:
        return False, err
    conn.execute(
        "UPDATE mercenary_roster SET gear_tier = ? WHERE id = ?",
        (tier, soldier_id),
    )
    conn.commit()
    return True, f"{row['name']} fitted with {info['label']} ({_spend_note(cost, purse_spent, bank_spent)})."


def train(conn, session, soldier_id: int, skill: str) -> tuple[bool, str, dict | None]:
    """Raise one combat skill by exactly +1 level. Limited to DAILY_TRAIN_CAP/day."""
    if skill not in TRAIN_SKILLS:
        return False, "Train Attack, Strength, Defence, or Hitpoints.", None
    row = conn.execute(
        "SELECT * FROM mercenary_roster WHERE id = ? AND player_id = ?",
        (soldier_id, session.player_id),
    ).fetchone()
    if not row:
        return False, "That soldier is not in your roster.", None
    daily = soldier_trains_today(row)
    if daily["remaining"] <= 0:
        return (
            False,
            f"{row['name']} has used all {DAILY_TRAIN_CAP} train slots today. Return tomorrow.",
            None,
        )
    col = f"{skill}_xp"
    before_xp = int(row[col])
    before_lvl = combat.level_from_xp(before_xp)
    if before_lvl >= 99:
        return False, f"{row['name']}'s {skill.title()} is already 99.", None
    after_lvl = before_lvl + 1
    after_xp = combat.xp_for_level(after_lvl)
    cost = train_cost_for_row(session, row, skill)
    ok, err, purse_spent, bank_spent = spend_coins(session, cost)
    if not ok:
        return False, err, None
    day = daily["day"]
    used = daily["used"] + 1
    conn.execute(
        f"UPDATE mercenary_roster SET {col} = ?, train_day = ?, trains_today = ? WHERE id = ?",
        (after_xp, day, used, soldier_id),
    )
    conn.commit()
    row2 = conn.execute("SELECT * FROM mercenary_roster WHERE id = ?", (soldier_id,)).fetchone()
    left = DAILY_TRAIN_CAP - used
    msg = (
        f"{row['name']} {skill.title()} {before_lvl}→{after_lvl} "
        f"({_spend_note(cost, purse_spent, bank_spent)}; {left}/{DAILY_TRAIN_CAP} trains left today)"
    )
    return True, msg, soldier_public(row2, session=session)


def outfit_all(conn, session, tier: str) -> tuple[bool, str]:
    """Fit every roster soldier who doesn't already wear this kit."""
    info = GEAR_KITS.get(tier)
    if not info:
        return False, "Unknown kit."
    cmd = command_level(session)
    if cmd < int(info["command_req"]):
        return False, f"Need Command {info['command_req']} for {info['label']}."
    rows = roster_rows(conn, session.player_id)
    targets = [r for r in rows if r["gear_tier"] != tier]
    if not targets:
        return False, f"Every soldier already wears {info['label']}."
    fitted = 0
    spent_purse = spent_bank = 0
    for row in targets:
        cost = int(info["cost"])
        ok, err, p, b = spend_coins(session, cost)
        if not ok:
            if fitted:
                break
            return False, err
        conn.execute(
            "UPDATE mercenary_roster SET gear_tier = ? WHERE id = ?",
            (tier, row["id"]),
        )
        fitted += 1
        spent_purse += p
        spent_bank += b
    conn.commit()
    skipped = len(targets) - fitted
    note = _spend_note(spent_purse + spent_bank, spent_purse, spent_bank)
    msg = f"Fitted {fitted} soldier{'s' if fitted != 1 else ''} with {info['label']} ({note})."
    if skipped:
        msg += f" Stopped early — need more coins for {skipped}."
    return True, msg


def train_all(conn, session, skill: str) -> tuple[bool, str]:
    """+1 level in skill for every soldier who still has a daily train slot."""
    if skill not in TRAIN_SKILLS:
        return False, "Train Attack, Strength, Defence, or Hitpoints."
    rows = roster_rows(conn, session.player_id)
    if not rows:
        return False, "Recruit soldiers first."
    trained = 0
    spent_purse = spent_bank = 0
    blocked = 0
    for row in rows:
        daily = soldier_trains_today(row)
        if daily["remaining"] <= 0:
            blocked += 1
            continue
        col = f"{skill}_xp"
        before_xp = int(row[col])
        before_lvl = combat.level_from_xp(before_xp)
        if before_lvl >= 99:
            continue
        cost = train_cost_for_row(session, row, skill)
        ok, err, p, b = spend_coins(session, cost)
        if not ok:
            if trained:
                break
            return False, err
        after_xp = combat.xp_for_level(before_lvl + 1)
        day = daily["day"]
        used = daily["used"] + 1
        conn.execute(
            f"UPDATE mercenary_roster SET {col} = ?, train_day = ?, trains_today = ? WHERE id = ?",
            (after_xp, day, used, row["id"]),
        )
        trained += 1
        spent_purse += p
        spent_bank += b
    conn.commit()
    if trained == 0:
        if blocked == len(rows):
            return False, f"All soldiers have used their {DAILY_TRAIN_CAP} trains for today."
        return False, f"No one could train {skill.title()} right now."
    note = _spend_note(spent_purse + spent_bank, spent_purse, spent_bank)
    msg = f"Trained {skill.title()} +1 on {trained} soldier{'s' if trained != 1 else ''} ({note})."
    if blocked:
        msg += f" {blocked} already at daily cap."
    return True, msg


def _fighter_from_row(row) -> dict:
    pub = soldier_public(row)
    levels = pub["levels"]
    hp = max(1, levels["hitpoints"])
    return {
        "roster_id": int(row["id"]),
        "name": pub["name"],
        "levels": levels,
        "gear_tier": pub["gear_tier"],
        "ability": pub["ability"],
        "hp": hp,
        "max_hp": hp,
        "first_strike": pub["ability"] == "first_strike",
        "guard_left": 1 if pub["ability"] == "guard" else 0,
        "medic_left": 1 if pub["ability"] == "field_dress" else 0,
        "side": "you",
    }


def _fighter_from_snap(template_id: str, gear: str, level: int) -> dict:
    tmpl = TEMPLATES.get(template_id) or TEMPLATES["levy"]
    lv = max(int(level), 1)
    levels = {
        "attack": lv,
        "strength": lv,
        "defence": max(1, lv - 2),
        "hitpoints": max(10, int(lv * 1.25)),
    }
    hp = levels["hitpoints"]
    return {
        "name": tmpl["name"],
        "levels": levels,
        "gear_tier": gear if gear in TIER_EQUIP else "bronze",
        "ability": tmpl.get("ability"),
        "hp": hp,
        "max_hp": hp,
        "first_strike": tmpl.get("ability") == "first_strike",
        "guard_left": 1 if tmpl.get("ability") == "guard" else 0,
        "medic_left": 1 if tmpl.get("ability") == "field_dress" else 0,
        "side": "foe",
    }


def _alive(team):
    return [f for f in team if f["hp"] > 0]


def _pick_target(foes):
    alive = _alive(foes)
    return min(alive, key=lambda f: f["hp"]) if alive else None


def _apply_hit(attacker, defender):
    ratio = attacker["hp"] / max(1, attacker["max_hp"])
    astat = fight_stats(attacker["levels"], attacker["gear_tier"], attacker["ability"], ratio)
    dstat = fight_stats(defender["levels"], defender["gear_tier"], defender["ability"],
                        defender["hp"] / max(1, defender["max_hp"]))
    if defender.get("guard_left"):
        dstat["defence_bonus"] = int(dstat["defence_bonus"] * 1.5) + 20
        defender["guard_left"] -= 1
    dmg, _ = combat.resolve_hit(astat, dstat)
    if attacker.get("ability") == "riposte" and random.random() < 0.15:
        dmg = int(dmg * 1.2)
    defender["hp"] = max(0, defender["hp"] - dmg)
    if attacker.get("ability") == "riposte" and dmg > 0 and defender["hp"] > 0:
        # Small return cut modeled as attacker taking no damage; applied when defender swings.
        pass
    return dmg


def _try_medic(team):
    medics = [f for f in _alive(team) if f.get("medic_left")]
    if not medics:
        return
    wounded = [f for f in _alive(team) if f["hp"] < f["max_hp"]]
    if not wounded:
        return
    medic = medics[0]
    target = min(wounded, key=lambda f: f["hp"] / f["max_hp"])
    heal = max(4, target["max_hp"] // 4)
    target["hp"] = min(target["max_hp"], target["hp"] + heal)
    medic["medic_left"] = 0


def simulate_battle(your_team, foe_team, max_rounds: int = 200) -> dict:
    """Instant AI-vs-AI resolve for practice (and later PvP snapshot)."""
    you = [dict(f) for f in your_team]
    foe = [dict(f) for f in foe_team]
    # First Strike free hits
    for side, other in ((you, foe), (foe, you)):
        for fighter in side:
            if fighter.get("first_strike") and fighter["hp"] > 0:
                target = _pick_target(other)
                if target:
                    _apply_hit(fighter, target)
                fighter["first_strike"] = False

    rounds = 0
    log = []
    while rounds < max_rounds and _alive(you) and _alive(foe):
        rounds += 1
        if rounds % 4 == 0:
            _try_medic(you)
            _try_medic(foe)
        order = _alive(you) + _alive(foe)
        random.shuffle(order)
        for fighter in order:
            if fighter["hp"] <= 0:
                continue
            enemies = foe if fighter in you or fighter["side"] == "you" else you
            # identity: rebuild side membership each round via side tag
            enemies = foe if fighter["side"] == "you" else you
            target = _pick_target(enemies)
            if not target:
                break
            dmg = _apply_hit(fighter, target)
            if len(log) < 12:
                log.append(f"{fighter['name']} hits {target['name']} for {dmg}")
            if fighter.get("ability") == "riposte" and target["hp"] > 0 and dmg > 0:
                # Light return damage
                retal = max(1, dmg // 5)
                fighter["hp"] = max(0, fighter["hp"] - retal)

    you_hp = sum(f["hp"] for f in you)
    foe_hp = sum(f["hp"] for f in foe)
    if you_hp <= 0 and foe_hp <= 0:
        won = you_hp >= foe_hp
    elif not _alive(foe):
        won = True
    elif not _alive(you):
        won = False
    else:
        won = you_hp >= foe_hp
    return {
        "won": won,
        "rounds": rounds,
        "your_hp_left": you_hp,
        "foe_hp_left": foe_hp,
        "your_alive": len(_alive(you)),
        "foe_alive": len(_alive(foe)),
        "log": log,
    }


# --- Live arena matches (soldiers fight on the sand) --------------------------

# Pit from castle_realm_map.json arena.pit; spectator south of the ring.
ARENA_PIT = (178, 113, 214, 143)
ARENA_CENTER = (196, 128)
ARENA_SPECTATOR = (196, 148)
MATCH_ATTACK_TICKS = 1          # ~0.6s between swings — readable but not sluggish
MATCH_TIMEOUT_TICKS = 180       # ~108s safety cap
_NEXT_UNIT_ID = 900_000


def _next_unit_id() -> int:
    global _NEXT_UNIT_ID
    _NEXT_UNIT_ID += 1
    return _NEXT_UNIT_ID


def arena_coords():
    """Load pit / spectator from the stamped realm map when available."""
    try:
        import castle_realm
        arena = (castle_realm.REALM or {}).get("arena") or {}
        pit = arena.get("pit") or list(ARENA_PIT)
        center = arena.get("center") or list(ARENA_CENTER)
        spec = arena.get("marshal_tile") or list(ARENA_SPECTATOR)
        # Spectator a little south of the marshal so the camera sees the pit.
        spectator = [int(center[0]), int(pit[3]) + 3]
        return {
            "pit": [int(pit[0]), int(pit[1]), int(pit[2]), int(pit[3])],
            "center": [int(center[0]), int(center[1])],
            "spectator": spectator,
        }
    except Exception:
        return {
            "pit": list(ARENA_PIT),
            "center": list(ARENA_CENTER),
            "spectator": list(ARENA_SPECTATOR),
        }


def _line_up(n: int, x0: int, x1: int, y0: int, y1: int, west: bool) -> list[tuple[int, int]]:
    """Line up to 10 soldiers as two ranks of 5: front then rear.

    West (your) army faces east; east (foe) army faces west. Gaps keep
    sprites readable; front ranks start a few tiles from mid so they march in.
    """
    if n <= 0:
        return []
    n = min(int(n), PRACTICE_ARMY_SIZE)
    front_n = min(5, n)
    rear_n = max(0, n - front_n)
    mid_y = (y0 + y1) // 2
    mid_x = (x0 + x1) // 2
    # Room between soldiers so attack anims don't stack on top of each other.
    rank_gap = 4
    file_gap = 3

    def _rank(count: int, x: int, y_nudge: int = 0) -> list[tuple[int, int]]:
        if count <= 0:
            return []
        start_y = mid_y - ((count - 1) * file_gap) // 2 + y_nudge
        out = []
        for i in range(count):
            y = max(y0 + 1, min(y1 - 1, start_y + i * file_gap))
            xx = max(x0 + 1, min(x1 - 1, x))
            out.append((xx, y))
        return out

    if west:
        front_x = mid_x - 6
        rear_x = front_x - rank_gap
    else:
        front_x = mid_x + 6
        rear_x = front_x + rank_gap
    # Same file Y for front/rear so each column reads clearly.
    return _rank(front_n, front_x, 0) + _rank(rear_n, rear_x, 0)


def _unit_from_fighter(fighter: dict, side: str, xy, template_id: str | None = None) -> dict:
    gear = fighter.get("gear_tier") or "bronze"
    levels = fighter["levels"]
    return {
        "id": _next_unit_id(),
        "roster_id": fighter.get("roster_id"),
        "type": "arena_soldier",
        "name": fighter["name"],
        "side": side,
        "template_id": template_id or fighter.get("template_id") or "levy",
        "x": int(xy[0]),
        "y": int(xy[1]),
        "hp": int(fighter["hp"]),
        "max_hp": int(fighter["max_hp"]),
        "alive": True,
        "levels": dict(levels),
        "gear_tier": gear,
        "equipment": dict(TIER_EQUIP.get(gear) or TIER_EQUIP["bronze"]),
        "ability": fighter.get("ability"),
        "ability_label": ABILITY_LABELS.get(fighter.get("ability"), "—"),
        "first_strike": bool(fighter.get("first_strike")),
        "guard_left": int(fighter.get("guard_left") or 0),
        "medic_left": int(fighter.get("medic_left") or 0),
        # Desync swings; rear held until first death (see start_live_practice).
        "attack_cd": random.randint(0, MATCH_ATTACK_TICKS),
        "rank": "front",
        "file": 0,
        "held_reserve": False,
        "facing": "e" if side == "you" else "w",
        "attacking": 0.0,
        "player_art": True,
        "humanoid": True,
        "level": soldier_combat_level(levels),
        "target_id": None,
    }


def unit_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "type": "arena_soldier",
        "name": u["name"],
        "side": u["side"],
        "template_id": u.get("template_id"),
        "x": u["x"],
        "y": u["y"],
        "hp": u["hp"],
        "max_hp": u["max_hp"],
        "alive": u["alive"] and u["hp"] > 0,
        "level": u["level"],
        "gear_tier": u["gear_tier"],
        "equipment": u["equipment"],
        "ability_label": u.get("ability_label") or "—",
        "player_art": True,
        "humanoid": True,
        "facing": u.get("facing") or ("e" if u["side"] == "you" else "w"),
        "attacking": float(u.get("attacking") or 0),
        "arena_soldier": True,
        "field_soldier": bool(u.get("field_soldier")),
        "roster_id": u.get("roster_id"),
        "owner_id": u.get("owner_id"),
    }


def _normalize_army(army) -> list:
    """Every practice foe fields exactly PRACTICE_ARMY_SIZE soldiers."""
    rows = list(army or [])
    if len(rows) > PRACTICE_ARMY_SIZE:
        return rows[:PRACTICE_ARMY_SIZE]
    while len(rows) < PRACTICE_ARMY_SIZE:
        rows.append(rows[-1] if rows else ("levy", "bronze", 5))
    return rows


def validate_practice(conn, session, foe_id: str) -> tuple[bool, str, dict | None]:
    entry = next((e for e in PRACTICE_TIERS if e["id"] == foe_id), None)
    if not entry:
        return False, "Unknown practice opponent.", None
    highest = practice_highest(conn, session.player_id)
    if int(entry["tier"]) > highest + 1:
        return False, "Beat the previous house first.", None
    rows = roster_rows(conn, session.player_id)
    if not rows:
        return False, "Recruit at least one soldier first.", None
    daily = daily_fights(conn, session.player_id)
    if daily["remaining"] <= 0:
        return False, (
            f"You have used all {DAILY_FIGHT_CAP} arena fights for today. Return tomorrow."
        ), None
    existing = getattr(session, "arena_match", None)
    if existing and existing.get("phase") in ("fight", "preview"):
        return False, "A fight is already staged in the arena.", None
    if existing:
        session.arena_match = None
    return True, "", entry


def start_live_practice(conn, session, foe_id: str) -> tuple[bool, str, dict | None]:
    """Stage both armies on the sand in preview; combat starts on begin_live_fight."""
    ok, err, entry = validate_practice(conn, session, foe_id)
    if not ok:
        return False, err, None
    spent, spend_err, daily = consume_daily_fight(conn, session.player_id)
    if not spent:
        return False, spend_err, None
    rows = roster_rows(conn, session.player_id)[:ROSTER_MAX]
    coords = arena_coords()
    x0, y0, x1, y1 = coords["pit"]
    your_fighters = [_fighter_from_row(r) for r in rows]
    for f, r in zip(your_fighters, rows):
        f["template_id"] = r["template_id"]
    foe_fighters = []
    for t, g, lv in _normalize_army(entry["army"]):
        f = _fighter_from_snap(t, g, lv)
        f["template_id"] = t
        foe_fighters.append(f)
    your_spots = _line_up(len(your_fighters), x0, x1, y0, y1, west=True)
    foe_spots = _line_up(len(foe_fighters), x0, x1, y0, y1, west=False)
    units = []
    for i, (f, xy) in enumerate(zip(your_fighters, your_spots)):
        u = _unit_from_fighter(f, "you", xy, f.get("template_id"))
        # Front 5 clash; rear 5 hold until the first soldier falls.
        u["rank"] = "front" if i < 5 else "rear"
        u["file"] = i if i < 5 else i - 5
        u["held_reserve"] = i >= 5
        units.append(u)
    for i, (f, xy) in enumerate(zip(foe_fighters, foe_spots)):
        u = _unit_from_fighter(f, "foe", xy, f.get("template_id"))
        u["rank"] = "front" if i < 5 else "rear"
        u["file"] = i if i < 5 else i - 5
        u["held_reserve"] = i >= 5
        units.append(u)
    match = {
        "foe_id": foe_id,
        "foe_name": entry["name"],
        "tier": int(entry["tier"]),
        "entry": entry,
        "units": units,
        "tick": 0,
        "log": [],
        "phase": "preview",
        "reserves_released": False,
        "roster_cl": roster_total_cl(roster_public(conn, session.player_id)),
        "foe_cl": _snapshot_army_cl(_normalize_army(entry["army"])),
        "spectator": coords["spectator"],
        "pit": coords["pit"],
        "center": coords["center"],
        "daily": daily,
    }
    session.arena_match = match
    left = daily.get("remaining", 0)
    return True, (
        f"Armies ready vs {entry['name']} — press Start Battle when you have the view. "
        f"({left}/{DAILY_FIGHT_CAP} fights left today)"
    ), match


def begin_live_fight(session) -> tuple[bool, str]:
    """Leave preview and start ticking combat."""
    match = getattr(session, "arena_match", None)
    if not match:
        return False, "No arena match staged."
    if match.get("phase") == "fight":
        return False, "The battle has already begun."
    if match.get("phase") != "preview":
        return False, "Cannot start that match."
    match["phase"] = "fight"
    match["tick"] = 0
    match["log"] = list(match.get("log") or [])
    _push_log(match, "Front ranks advance — reserves hold!")
    return True, f"Battle! vs {match.get('foe_name')}"


# Up to this many soldiers may focus the same foe (surround + pile-on).
MATCH_FOCUS_MAX = 3
# Same stand-off as player/monster melee (content.MELEE_STAND_GAP).
try:
    from content import MELEE_STAND_GAP as MATCH_MELEE_RANGE
except Exception:
    MATCH_MELEE_RANGE = 2


def _chebyshev(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))


def _step_toward(ux, uy, tx, ty):
    dx = 0 if tx == ux else (1 if tx > ux else -1)
    dy = 0 if ty == uy else (1 if ty > uy else -1)
    return ux + dx, uy + dy


def _enemies(match, unit):
    return [u for u in match["units"] if u["alive"] and u["hp"] > 0 and u["side"] != unit["side"]]


def _allies(match, unit):
    return [u for u in match["units"] if u["alive"] and u["hp"] > 0 and u["side"] == unit["side"]]


def _pit_clamp(x, y, pit):
    return (
        max(pit[0] + 1, min(pit[2] - 1, x)),
        max(pit[1] + 1, min(pit[3] - 1, y)),
    )


def _adjacent_tiles(tx, ty, pit):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield _pit_clamp(tx + dx, ty + dy, pit)


def _dressing_tile(unit, target, occupied, pit):
    """Hold 4–5 tiles behind the clash on our side instead of milling in a tight ring."""
    side = unit.get("side") or "you"
    # You approach from the west; foes from the east — dress further back on own side.
    back = -1 if side == "you" else 1
    candidates = []
    for radius in (4, 5):
        base_x = target["x"] + back * radius
        for dy in range(-3, 4):
            ax, ay = _pit_clamp(base_x, target["y"] + dy, pit)
            if (ax, ay) == (unit["x"], unit["y"]) or (ax, ay) not in occupied:
                candidates.append((ax, ay))
        if candidates:
            break
    if not candidates:
        return (unit["x"], unit["y"])
    return min(
        candidates,
        key=lambda p: (_chebyshev(unit["x"], unit["y"], p[0], p[1]), abs(p[1] - unit["y"])),
    )


def _approach_spot_key(ux, uy, spot, target, unit=None):
    """Prefer same file on our side of the foe (don't path behind them)."""
    ax, ay = spot
    tx, ty = target["x"], target["y"]
    side = (unit or {}).get("side") or "you"
    # Behind the foe from our perspective — strongly penalize.
    crossed = 1 if (side == "you" and ax > tx) or (side == "foe" and ax < tx) else 0
    # Prefer standing on the foe's row so swords meet horizontally.
    return (crossed, abs(ay - ty), _chebyshev(ux, uy, ax, ay), abs(ay - uy))


def _melee_stand_tiles(target, pit, unit=None):
    """Tiles at MATCH_MELEE_RANGE on our side — preferred same Y as the foe."""
    side = (unit or {}).get("side") or "you"
    back = -1 if side == "you" else 1
    tx, ty = target["x"], target["y"]
    r = MATCH_MELEE_RANGE
    spots = []
    # Primary: same row, r tiles back (classic duel spacing).
    spots.append(_pit_clamp(tx + back * r, ty, pit))
    # Secondary: slight file offsets for surround when the primary is taken.
    for dy in (-1, 1, -2, 2):
        spots.append(_pit_clamp(tx + back * r, ty + dy, pit))
    # Tertiary: diagonal standoff at exact chebyshev r on our side.
    for dy in range(-r, r + 1):
        dx = back * (r if abs(dy) < r else r)
        if max(abs(dx), abs(dy)) != r:
            continue
        if (side == "you" and dx > 0) or (side == "foe" and dx < 0):
            continue
        spots.append(_pit_clamp(tx + dx, ty + dy, pit))
    return spots


def _free_approach_tile(ux, uy, target, occupied, pit, unit=None, focus_count=0):
    """Stand-off tile at MATCH_MELEE_RANGE so sprites don't stack.

    Prefer our side / same file. Surplus attackers hold a dressing line further back.
    """
    spots = []
    for ax, ay in _melee_stand_tiles(target, pit, unit):
        if (ax, ay) == (ux, uy) or (ax, ay) not in occupied:
            spots.append((ax, ay))
    # De-dupe while preserving order
    seen = set()
    uniq = []
    for p in spots:
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    spots = uniq
    if spots and focus_count < MATCH_FOCUS_MAX:
        return min(spots, key=lambda p: _approach_spot_key(ux, uy, p, target, unit))
    if unit is not None and (not spots or focus_count >= MATCH_FOCUS_MAX):
        return _dressing_tile(unit, target, occupied, pit)
    if spots:
        return min(spots, key=lambda p: _approach_spot_key(ux, uy, p, target, unit))
    return (target["x"] + (-MATCH_MELEE_RANGE if (unit or {}).get("side") == "you" else MATCH_MELEE_RANGE),
            target["y"])


def _try_step(ux, uy, goal_x, goal_y, occupied, pit, unit=None, target=None):
    """Step toward goal; if blocked, try alternate directions that close distance.

    When a target is known: refuse crossing behind them, and never step
    closer than MATCH_MELEE_RANGE (keeps sword room when both sides charge).
    """
    primary = _step_toward(ux, uy, goal_x, goal_y)
    options = [primary, (ux, uy)]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        options.append((ux + dx, uy + dy))
    before = _chebyshev(ux, uy, goal_x, goal_y)
    side = (unit or {}).get("side") or "you"
    tx = target["x"] if target else None
    ty = target["y"] if target else None
    cur_foe = _chebyshev(ux, uy, tx, ty) if tx is not None else 99
    best = None
    best_key = None
    for nx, ny in options:
        nx, ny = _pit_clamp(nx, ny, pit)
        if (nx, ny) != (ux, uy) and (nx, ny) in occupied:
            continue
        after = _chebyshev(nx, ny, goal_x, goal_y)
        crossed = 0
        foe_d = cur_foe
        if tx is not None:
            if side == "you" and nx > tx:
                crossed = 1
            elif side == "foe" and nx < tx:
                crossed = 1
            foe_d = _chebyshev(nx, ny, tx, ty)
        # 0 = at/above sword range, 1 = still too close but improving, 2 = worse/cramped
        if tx is None:
            prox = 0
        elif foe_d >= MATCH_MELEE_RANGE:
            prox = 0
        elif foe_d > cur_foe:
            prox = 1
        else:
            prox = 2
        key = (
            prox,
            crossed,
            0 if after < before else 1 if after == before else 2,
            after,
            -foe_d,
            abs(ny - uy),
        )
        if best_key is None or key < best_key:
            best_key = key
            best = (nx, ny)
    return best


def _eligible_foes(match, unit):
    """Front only fights enemy front until reserves are released."""
    foes = _enemies(match, unit)
    if match.get("reserves_released"):
        return foes
    front = [f for f in foes if f.get("rank") != "rear" and not f.get("held_reserve")]
    return front or foes


def _assign_targets(living, match):
    """Pair by file first so fronts clash head-on; then spread / focus rules."""
    focus = {}
    assigned = {}
    for u in living:
        if u.get("held_reserve") and not match.get("reserves_released"):
            continue
        foes = _eligible_foes(match, u)
        if not foes:
            continue
        cur_id = u.get("target_id")
        sticky = next((f for f in foes if f["id"] == cur_id), None)
        spread = len(foes) >= 3
        my_file = int(u.get("file") if u.get("file") is not None else 0)

        def score(f, _spread=spread, _sticky=sticky, _file=my_file):
            n = focus.get(f["id"], 0)
            if _spread:
                over = n
            else:
                over = max(0, n - (MATCH_FOCUS_MAX - 1))
            # Same file first — stops fronts from crossing to a different column.
            file_gap = abs(int(f.get("file") if f.get("file") is not None else 0) - _file)
            y_gap = abs(f["y"] - u["y"])
            dist = _chebyshev(u["x"], u["y"], f["x"], f["y"])
            wounded = f["hp"] / max(1, f["max_hp"])
            stick = 0 if _sticky and f["id"] == _sticky["id"] and n < MATCH_FOCUS_MAX + 1 else 1
            return (over, file_gap, stick, y_gap, dist, wounded)

        target = min(foes, key=score)
        assigned[u["id"]] = target
        focus[target["id"]] = focus.get(target["id"], 0) + 1
        u["target_id"] = target["id"]
    return assigned


def _release_reserves(match, events):
    """Call when the first soldier falls — rear ranks join."""
    if match.get("reserves_released"):
        return
    match["reserves_released"] = True
    for u in match.get("units") or []:
        u["held_reserve"] = False
    _push_log(match, "A soldier falls — reserves join the battle!")
    events.append({"type": "ARENA_RESERVES", "released": True})


def tick_live_match(match: dict) -> list[dict]:
    """Advance one game tick. Returns combat/event dicts for the client."""
    events = []
    if match.get("phase") != "fight":
        return events
    match["tick"] = int(match.get("tick") or 0) + 1
    units = match["units"]
    pit = match.get("pit") or list(ARENA_PIT)
    # Decay attack anim
    for u in units:
        if u.get("attacking"):
            u["attacking"] = max(0.0, float(u["attacking"]) - 0.35)

    # First-strike openers on tick 1 (front rank only, clash range)
    if match["tick"] == 1:
        for u in units:
            if not u.get("first_strike") or u["hp"] <= 0 or u.get("held_reserve"):
                continue
            foes = _eligible_foes(match, u)
            if not foes:
                continue
            target = min(foes, key=lambda f: (
                abs(int(f.get("file") or 0) - int(u.get("file") or 0)),
                _chebyshev(u["x"], u["y"], f["x"], f["y"]),
                f["hp"],
            ))
            if _chebyshev(u["x"], u["y"], target["x"], target["y"]) > 2:
                continue
            dmg = _apply_hit(u, target)
            u["first_strike"] = False
            u["attacking"] = 1.0
            u["facing"] = "e" if target["x"] >= u["x"] else "w"
            u["target_id"] = target["id"]
            events.append(_hit_event(u, target, dmg))
            if target["hp"] <= 0:
                target["alive"] = False
                events.append({"type": "DEATH", "entity_id": target["id"], "entity_kind": "arena"})
                _release_reserves(match, events)
            _push_log(match, f"{u['name']} First Strike hits {target['name']} for {dmg}")

    # Medic pulse every 8 ticks (reserves can heal once released)
    if match["tick"] % 8 == 0:
        for side in ("you", "foe"):
            team = [
                u for u in units if u["side"] == side
                and (match.get("reserves_released") or not u.get("held_reserve"))
            ]
            _try_medic(team)

    living = [u for u in units if u["alive"] and u["hp"] > 0]
    active = [
        u for u in living
        if match.get("reserves_released") or not u.get("held_reserve")
    ]
    random.shuffle(active)
    assigned = _assign_targets(active, match)
    occupied = {(u["x"], u["y"]) for u in units if u["alive"] and u["hp"] > 0}

    for u in active:
        if not (u["alive"] and u["hp"] > 0):
            continue
        target = assigned.get(u["id"])
        if not target or not (target["alive"] and target["hp"] > 0):
            foes = _eligible_foes(match, u)
            if not foes:
                continue
            target = min(foes, key=lambda f: (
                abs(int(f.get("file") or 0) - int(u.get("file") or 0)),
                f["hp"],
            ))
            u["target_id"] = target["id"]
        dist = _chebyshev(u["x"], u["y"], target["x"], target["y"])
        u["facing"] = "e" if target["x"] >= u["x"] else "w"
        # Too far → close in. Too close → step back to sword range so sprites don't stack.
        if dist != MATCH_MELEE_RANGE:
            adj_focus = sum(
                1
                for a in active
                if a["side"] == u["side"]
                and a["id"] != u["id"]
                and a.get("target_id") == target["id"]
                and _chebyshev(a["x"], a["y"], target["x"], target["y"]) <= MATCH_MELEE_RANGE
            )
            goal = _free_approach_tile(
                u["x"], u["y"], target, occupied, pit, unit=u, focus_count=adj_focus,
            )
            step = _try_step(
                u["x"], u["y"], goal[0], goal[1], occupied, pit, unit=u, target=target,
            )
            if step and step != (u["x"], u["y"]):
                occupied.discard((u["x"], u["y"]))
                u["x"], u["y"] = step
                occupied.add(step)
            continue
        # At sword range — swing on cooldown
        cd = int(u.get("attack_cd") or 0)
        if cd > 0:
            u["attack_cd"] = cd - 1
            continue
        dmg = _apply_hit(u, target)
        u["attack_cd"] = MATCH_ATTACK_TICKS
        u["attacking"] = 1.0
        events.append(_hit_event(u, target, dmg))
        _push_log(match, f"{u['name']} hits {target['name']} for {dmg}")
        if target["hp"] <= 0:
            target["alive"] = False
            occupied.discard((target["x"], target["y"]))
            events.append({"type": "DEATH", "entity_id": target["id"], "entity_kind": "arena"})
            _push_log(match, f"{target['name']} falls!")
            _release_reserves(match, events)
        elif u.get("ability") == "riposte" and dmg > 0:
            retal = max(1, dmg // 5)
            u["hp"] = max(0, u["hp"] - retal)
            if u["hp"] <= 0:
                u["alive"] = False
                occupied.discard((u["x"], u["y"]))
                events.append({"type": "DEATH", "entity_id": u["id"], "entity_kind": "arena"})
                _release_reserves(match, events)

    you_alive = [u for u in units if u["side"] == "you" and u["alive"] and u["hp"] > 0]
    foe_alive = [u for u in units if u["side"] == "foe" and u["alive"] and u["hp"] > 0]
    timed_out = match["tick"] >= MATCH_TIMEOUT_TICKS
    if not you_alive or not foe_alive or timed_out:
        match["phase"] = "done"
        if timed_out:
            you_hp = sum(u["hp"] for u in units if u["side"] == "you")
            foe_hp = sum(u["hp"] for u in units if u["side"] == "foe")
            match["won"] = you_hp >= foe_hp
        else:
            match["won"] = bool(you_alive) and not foe_alive
        match["your_alive"] = len(you_alive)
        match["foe_alive"] = len(foe_alive)
        match["your_hp_left"] = sum(u["hp"] for u in units if u["side"] == "you")
        match["foe_hp_left"] = sum(u["hp"] for u in units if u["side"] == "foe")
        match["rounds"] = match["tick"]
    return events


def _hit_event(attacker, defender, dmg):
    return {
        "type": "COMBAT_EVENT",
        "attacker_id": attacker["id"],
        "defender_id": defender["id"],
        "damage": dmg,
        "hit": True,
        "defender_hp": defender["hp"],
        "defender_max_hp": defender["max_hp"],
        "kind": "arena",
        "ranged": False,
    }


def _push_log(match, text):
    log = match.setdefault("log", [])
    log.append(text)
    if len(log) > 24:
        del log[:-24]


def grant_survivor_xp(conn, match: dict) -> list[dict]:
    """Survivors earn combat XP so repeated wins harden the roster."""
    tier = max(1, int(match.get("tier") or 1))
    won = bool(match.get("won"))
    # Per-skill XP: scales with foe tier; losses still teach survivors a little.
    per_skill = int(round((18 + tier * 14) * (1.0 if won else 0.4)))
    skills = ("attack", "strength", "defence", "hitpoints")
    grants = []
    for u in match.get("units") or []:
        if u.get("side") != "you" or not u.get("alive") or int(u.get("hp") or 0) <= 0:
            continue
        rid = u.get("roster_id")
        if not rid:
            continue
        row = conn.execute(
            "SELECT * FROM mercenary_roster WHERE id = ?", (int(rid),)
        ).fetchone()
        if not row:
            continue
        before_lv = {
            "attack": combat.level_from_xp(int(row["attack_xp"])),
            "strength": combat.level_from_xp(int(row["strength_xp"])),
            "defence": combat.level_from_xp(int(row["defence_xp"])),
            "hitpoints": combat.level_from_xp(int(row["hitpoints_xp"])),
        }
        after = {}
        leveled = []
        cols = []
        vals = []
        for sk in skills:
            col = f"{sk}_xp"
            after_xp = int(row[col]) + per_skill
            cols.append(f"{col} = ?")
            vals.append(after_xp)
            after[sk] = combat.level_from_xp(after_xp)
            if after[sk] > before_lv[sk]:
                leveled.append(f"{sk.title()} {before_lv[sk]}→{after[sk]}")
        vals.append(int(rid))
        conn.execute(
            f"UPDATE mercenary_roster SET {', '.join(cols)} WHERE id = ?",
            vals,
        )
        grants.append({
            "id": int(rid),
            "name": u.get("name") or row["name"],
            "xp": per_skill * len(skills),
            "per_skill": per_skill,
            "leveled": leveled,
            "combat_level": soldier_combat_level(after),
        })
    if grants:
        conn.commit()
    return grants


def settle_live_practice(conn, session, match: dict) -> tuple[str, dict]:
    """Apply Command XP / coins / ore / survivor XP after a finished live match."""
    entry = match.get("entry") or next(
        (e for e in PRACTICE_TIERS if e["id"] == match.get("foe_id")), None
    )
    won = bool(match.get("won"))
    xp = int((entry or {}).get("command_xp_win" if won else "command_xp_loss") or 20)
    coins = 0
    ore = 0
    if won and entry:
        coins = int(entry.get("coin_win") or 0)
        from content import MAX_PURSE_COINS
        session.coins = min(int(session.coins) + coins, MAX_PURSE_COINS)
        set_practice_highest(conn, session.player_id, int(entry.get("tier") or 1))
        if int(entry.get("tier") or 0) >= 5:
            chance = 0.08 if int(entry["tier"]) == 5 else 0.15
            if command_level(session) >= 70:
                chance *= 1.35
            if random.random() < chance:
                ore = 1
    survivors = grant_survivor_xp(conn, match)
    daily = daily_fights(conn, session.player_id)
    summary = {
        "foe_id": match.get("foe_id"),
        "foe_name": match.get("foe_name"),
        "won": won,
        "winner": "You" if won else match.get("foe_name"),
        "loser": match.get("foe_name") if won else "You",
        "command_xp": xp,
        "coins": coins,
        "mythos_ore": ore,
        "rounds": match.get("rounds") or match.get("tick") or 0,
        "your_alive": match.get("your_alive") or 0,
        "foe_alive": match.get("foe_alive") or 0,
        "your_hp_left": match.get("your_hp_left") or 0,
        "foe_hp_left": match.get("foe_hp_left") or 0,
        "log": list(match.get("log") or [])[-12:],
        "roster_cl": match.get("roster_cl") or 0,
        "foe_cl": match.get("foe_cl") or 0,
        "live": True,
        "daily": daily,
        "survivor_xp": survivors,
    }
    verb = "Victory" if won else "Defeat"
    surv_n = len(survivors)
    surv_bit = ""
    if surv_n:
        lv_n = sum(1 for g in survivors if g.get("leveled"))
        surv_bit = f" · {surv_n} survivor{'s' if surv_n != 1 else ''} trained"
        if lv_n:
            surv_bit += f" ({lv_n} leveled)"
    msg = (
        f"{verb}! {summary['winner']} defeated {summary['loser']}. "
        f"+{xp} Command XP"
        + (f", +{coins:,} coins" if coins else "")
        + (" · Mythos ore!" if ore else "")
        + surv_bit
        + f" · {daily['remaining']}/{DAILY_FIGHT_CAP} fights left today."
    )
    return msg, summary


def practice_fight(conn, session, foe_id: str) -> tuple[bool, str, dict | None]:
    """Instant resolve kept for tests / fallback. Prefer start_live_practice in play."""
    ok, err, entry = validate_practice(conn, session, foe_id)
    if not ok:
        return False, err, None
    rows = roster_rows(conn, session.player_id)
    your_team = [_fighter_from_row(r) for r in rows]
    foe_team = [_fighter_from_snap(t, g, lv) for t, g, lv in entry["army"]]
    result = simulate_battle(your_team, foe_team)
    match = {
        "foe_id": foe_id,
        "foe_name": entry["name"],
        "entry": entry,
        "won": bool(result["won"]),
        "rounds": result["rounds"],
        "your_alive": result["your_alive"],
        "foe_alive": result["foe_alive"],
        "your_hp_left": result["your_hp_left"],
        "foe_hp_left": result["foe_hp_left"],
        "log": result["log"],
        "roster_cl": roster_total_cl(roster_public(conn, session.player_id)),
        "foe_cl": _snapshot_army_cl(entry["army"]),
        "tick": result["rounds"],
    }
    return True, *settle_live_practice(conn, session, match)


def match_hud(match: dict) -> dict:
    you = [u for u in match["units"] if u["side"] == "you"]
    foe = [u for u in match["units"] if u["side"] == "foe"]
    return {
        "foe_name": match.get("foe_name"),
        "tick": match.get("tick") or 0,
        "phase": match.get("phase"),
        "your_alive": sum(1 for u in you if u["alive"] and u["hp"] > 0),
        "your_total": len(you),
        "foe_alive": sum(1 for u in foe if u["alive"] and u["hp"] > 0),
        "foe_total": len(foe),
        "your_hp": sum(max(0, u["hp"]) for u in you),
        "your_max_hp": sum(u["max_hp"] for u in you),
        "foe_hp": sum(max(0, u["hp"]) for u in foe),
        "foe_max_hp": sum(u["max_hp"] for u in foe),
        "log": list(match.get("log") or [])[-6:],
    }


def match_sync_fingerprint(match: dict) -> tuple:
    """Position / life / facing only — swing anim is client-local after COMBAT_EVENT."""
    units = match.get("units") or []
    return tuple(
        (
            int(u["id"]),
            int(u["x"]),
            int(u["y"]),
            int(u["hp"]),
            bool(u.get("alive") and u["hp"] > 0),
            u.get("facing") or "",
            bool(u.get("held_reserve")),
        )
        for u in units
    )


# --- Field deploy (follow the commander in Castle Realm only) ----------------

FIELD_STEP_EVERY = 2  # ~1.2s, matches pet cadence
FIELD_MELEE_RANGE = 2
FIELD_ATTACK_TICKS = 1


def in_castle_realm(session) -> bool:
    d = getattr(session, "dungeon", None) or {}
    return d.get("id") == "castle_realm"


def deployed_list(session) -> list:
    return list(getattr(session, "deployed_soldiers", None) or [])


def deployed_roster_ids(session) -> list[int]:
    return [
        int(u["roster_id"])
        for u in deployed_list(session)
        if u.get("roster_id") is not None
    ]


def clear_deployed(session) -> int:
    """Recall everyone. Returns how many were out."""
    n = len(deployed_list(session))
    session.deployed_soldiers = []
    session._soldier_lord_shout = False
    return n


def _field_walkable(session, nx, ny) -> bool:
    import castle_realm
    d = session.dungeon or {}
    return castle_realm.walkable(d.get("plane"), int(nx), int(ny))


def _field_follow_goal(session, index: int, occupied: set) -> tuple[int, int]:
    """Stand behind the commander in two ranks of five."""
    px, py = int(session.x), int(session.y)
    last = getattr(session, "last_step", None)
    if last in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        bx, by = -int(last[0]), -int(last[1])
    else:
        bx, by = 0, 1
    # Perpendicular for file spread.
    sx, sy = -by, bx
    file_i = int(index) % 5
    rank = int(index) // 5
    file_off = file_i - 2
    gx = px + bx * (2 + rank) + sx * file_off
    gy = py + by * (2 + rank) + sy * file_off
    if (gx, gy) not in occupied and (gx, gy) != (px, py) and _field_walkable(session, gx, gy):
        return gx, gy
    # Spiral search near the ideal spot.
    for rad in range(0, 5):
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) != rad:
                    continue
                tx, ty = gx + dx, gy + dy
                if (tx, ty) == (px, py) or (tx, ty) in occupied:
                    continue
                if _field_walkable(session, tx, ty):
                    return tx, ty
    return px, py


def _field_face_toward(unit, tx, ty) -> None:
    """Face the destination's dominant axis — not a lateral correction step."""
    tdx = int(tx) - int(unit["x"])
    tdy = int(ty) - int(unit["y"])
    if tdx == 0 and tdy == 0:
        return
    if abs(tdy) > abs(tdx):
        unit["facing"] = "s" if tdy > 0 else "n"
    elif tdx != 0:
        unit["facing"] = "e" if tdx > 0 else "w"
    elif tdy != 0:
        unit["facing"] = "s" if tdy > 0 else "n"


def _field_face_march(unit, session) -> None:
    """Match the commander's travel direction while holding formation."""
    last = getattr(session, "last_step", None)
    if last in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        lx, ly = int(last[0]), int(last[1])
        if abs(ly) >= abs(lx) and ly != 0:
            unit["facing"] = "s" if ly > 0 else "n"
        elif lx != 0:
            unit["facing"] = "e" if lx > 0 else "w"


def _field_step_toward(unit, tx, ty, session, occupied: set) -> bool:
    ux, uy = int(unit["x"]), int(unit["y"])
    if (ux, uy) == (tx, ty):
        return False
    dx = 0 if ux == tx else (1 if tx > ux else -1)
    dy = 0 if uy == ty else (1 if ty > uy else -1)
    options = []
    for nx, ny in ((ux + dx, uy), (ux, uy + dy), (ux + dx, uy + dy)):
        if (nx, ny) == (int(session.x), int(session.y)):
            continue
        if (nx, ny) in occupied:
            continue
        if _field_walkable(session, nx, ny):
            options.append((nx, ny))
    if not options:
        return False
    options.sort(key=lambda p: max(abs(p[0] - tx), abs(p[1] - ty)))
    nx, ny = options[0]
    occupied.discard((ux, uy))
    unit["x"], unit["y"] = nx, ny
    occupied.add((nx, ny))
    # Prefer goal / march facing so file-correction sidesteps don't turn the sprite.
    gdx = int(tx) - nx
    gdy = int(ty) - ny
    if gdx == 0 and gdy == 0:
        _field_face_march(unit, session)
    else:
        _field_face_toward(unit, tx, ty)
    return True


def _field_unit_from_row(row, session, xy, index: int) -> dict:
    fighter = _fighter_from_row(row)
    fighter["template_id"] = row["template_id"]
    u = _unit_from_fighter(fighter, "you", xy, row["template_id"])
    u["field_soldier"] = True
    u["owner_id"] = int(session.player_id)
    u["file"] = int(index) % 5
    u["rank"] = "front" if index < 5 else "rear"
    u["held_reserve"] = False
    u["first_strike"] = False  # field: no free opener spam
    return u


def _can_deploy(session) -> tuple[bool, str]:
    if not in_castle_realm(session):
        return False, "Deploy only works inside the Castle Realm."
    match = getattr(session, "arena_match", None)
    if match and match.get("phase") in ("preview", "fight"):
        return False, "Recall your army after the arena match first."
    return True, ""


def deploy_soldiers(conn, session, soldier_id: int | None = None) -> tuple[bool, str]:
    """Deploy one roster soldier or the whole army to follow in Castle Realm."""
    ok, err = _can_deploy(session)
    if not ok:
        return False, err
    rows = roster_rows(conn, session.player_id)
    if not rows:
        return False, "Recruit at least one soldier first."
    if soldier_id is not None:
        rows = [r for r in rows if int(r["id"]) == int(soldier_id)]
        if not rows:
            return False, "That soldier is not in your roster."
    already = {int(u["roster_id"]) for u in deployed_list(session) if u.get("roster_id") is not None}
    to_add = [r for r in rows if int(r["id"]) not in already]
    if not to_add:
        return False, "Those soldiers are already deployed."
    deployed = deployed_list(session)
    occupied = {(int(u["x"]), int(u["y"])) for u in deployed}
    occupied.add((int(session.x), int(session.y)))
    base_index = len(deployed)
    for i, row in enumerate(to_add):
        idx = base_index + i
        xy = _field_follow_goal(session, idx, occupied)
        unit = _field_unit_from_row(row, session, xy, idx)
        occupied.add((unit["x"], unit["y"]))
        deployed.append(unit)
    session.deployed_soldiers = deployed
    # Fresh deploy — allow one "Protect your lord!" cry on the next strike.
    if not already:
        session._soldier_lord_shout = False
    n = len(to_add)
    if soldier_id is not None:
        return True, f"{deployed[-1]['name']} falls in beside you."
    return True, f"Deployed {n} soldier{'s' if n != 1 else ''} — they follow you in the Castle Realm."


def recall_soldiers(session, soldier_id: int | None = None) -> tuple[bool, str]:
    deployed = deployed_list(session)
    if not deployed:
        return False, "No soldiers are deployed."
    if soldier_id is None:
        n = clear_deployed(session)
        return True, f"Recalled {n} soldier{'s' if n != 1 else ''}."
    keep = []
    found = None
    for u in deployed:
        if int(u.get("roster_id") or -1) == int(soldier_id):
            found = u
        else:
            keep.append(u)
    if not found:
        return False, "That soldier is not deployed."
    session.deployed_soldiers = keep
    return True, f"{found['name']} falls back."


def tick_field_soldiers(session, events: list, resolve_monster, tick: int = 0, on_kill=None) -> None:
    """Follow the commander; engage the monster they are fighting.

    resolve_monster(mid) -> monster instance or None (castle-plane aware).
    Appends COMBAT_EVENT / DEATH dicts into events (same shape as process_pets).
    """
    from content import MELEE_STAND_GAP
    deployed = deployed_list(session)
    if not deployed or not in_castle_realm(session):
        if deployed and not in_castle_realm(session):
            clear_deployed(session)
        return
    # Decay swings
    for u in deployed:
        if u.get("attacking"):
            u["attacking"] = max(0.0, float(u["attacking"]) - 0.35)
    # Target = player's current foe (same rule as pets).
    target = None
    if session.in_combat_with and session.in_combat_with[0] == "monster":
        target = resolve_monster(session.in_combat_with[1])
        if target is None or not getattr(target, "alive", False):
            target = None

    occupied = {(int(u["x"]), int(u["y"])) for u in deployed if u.get("alive") and u.get("hp", 0) > 0}
    occupied.add((int(session.x), int(session.y)))
    dungeon_tag = session.player_id
    killed = set()

    for index, u in enumerate(deployed):
        if not (u.get("alive") and u.get("hp", 0) > 0):
            continue
        # Snap back if left the view
        dx = abs(int(u["x"]) - int(session.x))
        dy = abs(int(u["y"]) - int(session.y))
        if dx > 12 or dy > 9:
            occupied.discard((int(u["x"]), int(u["y"])))
            gx, gy = _field_follow_goal(session, index, occupied)
            u["x"], u["y"] = gx, gy
            occupied.add((gx, gy))

        if target is not None and getattr(target, "id", None) not in killed:
            dist = max(abs(int(u["x"]) - int(target.x)), abs(int(u["y"]) - int(target.y)))
            # Face the foe on the dominant axis so N/S approaches use north/south strips.
            tdx = int(target.x) - int(u["x"])
            tdy = int(target.y) - int(u["y"])
            if abs(tdx) >= abs(tdy) and tdx != 0:
                u["facing"] = "e" if tdx > 0 else "w"
            elif tdy != 0:
                u["facing"] = "s" if tdy > 0 else "n"
            reach = max(FIELD_MELEE_RANGE, int(MELEE_STAND_GAP))
            if dist > reach:
                ready = int(u.get("step_ready") or 0)
                if tick >= ready:
                    if _field_step_toward(u, int(target.x), int(target.y), session, occupied):
                        u["step_ready"] = tick + FIELD_STEP_EVERY
                continue
            cd = int(u.get("attack_cd") or 0)
            if cd > 0:
                u["attack_cd"] = cd - 1
                continue
            # Hit the monster with soldier combat stats.
            mstats = target.def_stats()
            astat = fight_stats(
                u["levels"], u["gear_tier"], u.get("ability"),
                u["hp"] / max(1, u["max_hp"]),
            )
            dmg, hit = combat.resolve_hit(
                {
                    "attack": astat["attack"], "strength": astat["strength"],
                    "attack_bonus": astat.get("attack_bonus", 0),
                    "strength_bonus": astat.get("strength_bonus", 0),
                },
                {"defence": mstats["defence"], "defence_bonus": mstats.get("def_bonus", 0)},
            )
            target.hp = max(0, target.hp - dmg)
            u["attack_cd"] = FIELD_ATTACK_TICKS
            u["attacking"] = 1.0
            events.append({
                "type": "COMBAT_EVENT",
                "data": {
                    "attacker_id": u["id"],
                    "defender_id": target.id,
                    "damage": dmg,
                    "hit": hit,
                    "defender_hp": target.hp,
                    "defender_max_hp": target.max_hp,
                    "kind": "soldier_hits_monster",
                    "_dungeon_player": dungeon_tag,
                },
            })
            # One soldier cries out once per deploy when steel first meets flesh.
            if hit and dmg > 0 and not getattr(session, "_soldier_lord_shout", False):
                session._soldier_lord_shout = True
                events.append({
                    "type": "CHAT_MSG",
                    "data": {
                        "from": u.get("name") or "Soldier",
                        "text": "Protect your lord!",
                        "_dungeon_player": dungeon_tag,
                    },
                })
            if target.hp <= 0:
                killed.add(target.id)
                if on_kill:
                    try:
                        on_kill(target)
                    except Exception:
                        pass
                events.append({
                    "type": "DEATH",
                    "data": {
                        "entity_id": target.id,
                        "entity_kind": "monster",
                        "_dungeon_player": dungeon_tag,
                    },
                })
                events.append({
                    "type": "_DUNGEON_LOOT",
                    "data": {"_dungeon_player": session.player_id, "monster_id": target.id},
                })
                if session.in_combat_with == ("monster", target.id):
                    session.in_combat_with = None
                target = None
            continue

        # Idle follow — face the march even while standing in file.
        ready = int(u.get("step_ready") or 0)
        goal = _field_follow_goal(session, index, occupied - {(int(u["x"]), int(u["y"]))})
        dist = max(abs(int(u["x"]) - goal[0]), abs(int(u["y"]) - goal[1]))
        if dist <= 0:
            _field_face_march(u, session)
            continue
        if tick >= ready:
            if _field_step_toward(u, goal[0], goal[1], session, occupied):
                u["step_ready"] = tick + FIELD_STEP_EVERY
            else:
                _field_face_march(u, session)
        else:
            _field_face_toward(u, goal[0], goal[1])


def barracks_payload(conn, session) -> dict:
    cmd = command_level(session)
    rows = roster_rows(conn, session.player_id)
    soldiers = [soldier_public(r, session=session) for r in rows]
    total_cl = roster_total_cl(soldiers)
    ladder = ladder_row(conn, session.player_id)
    daily = daily_fights(conn, session.player_id)
    deployed_ids = deployed_roster_ids(session)
    for s in soldiers:
        s["deployed"] = int(s["id"]) in deployed_ids
    return {
        "command_level": cmd,
        "command_xp": int(session.xp.get("command") or 0),
        "next_unlock": next_unlock(cmd),
        "unlocks": unlocks_for(cmd),
        "roster": soldiers,
        "roster_total_cl": total_cl,
        "roster_max": ROSTER_MAX,
        "recruit": recruitable_templates(cmd, rows),
        "kits": kit_catalogue(cmd),
        "practice": practice_board(conn, session.player_id, total_cl),
        "ladder": ladder,
        "coins": int(session.coins),
        "bank_coins": int(getattr(session, "bank_coins", 0) or 0),
        "wealth": wealth(session),
        "mythos_smelt_ready": cmd >= 60 and session.level("smithing") >= 60,
        "mythos_soldier_ready": cmd >= 80,
        "daily_fights": daily,
        "daily_train_cap": DAILY_TRAIN_CAP,
        "in_castle_realm": in_castle_realm(session),
        "deployed_ids": deployed_ids,
        "deployed_count": len(deployed_ids),
        "personal_house": _personal_house_payload(conn, session),
    }


def _personal_house_payload(conn, session) -> dict | None:
    try:
        import player_houses
        return player_houses.public(conn, session.player_id)
    except Exception:
        return None
