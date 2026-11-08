"""War for the Crown — castle structures, registration, storehouse, weapons, captures.

Milestone 1: shared structure HP / damage states and the founding King.
Milestone 2: siege declaration, guild registration, 48-hour confirm (or next guild),
and alliances under a lead guild.
Milestone 3: shared war storehouse, material deposits, leader allocations (spent against
deposit × %), contribution scores (non-damage recognition).
Milestone 4+: siege weapons / breaches, staged captures, Last Stand, roster caps,
assault clock, structure effects, war board / Herald.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

HOUR = 3600
DAY = 86400

# ---- milestone 2: declaration / registration ---------------------------------
CONFIRM_SECONDS = 48 * HOUR
HUMAN_MIN = 20                 # confirmed human fighters required to confirm a reserved slot
# Design: under-strength wars are postponed or run at a smaller scale.
SMALL_SCALE_HUMAN_MIN = max(1, HUMAN_MIN // 2)
SIDE_CAP = 100                 # milestone 8: max fighters per side (humans + mercs)
MERC_MAX_FRACTION = 0.40       # mercenaries may not exceed 40% of a side
# Design: guild membership is not participation — each human enlists, picks a role, confirms.
BATTLE_ROLES = ("infantry", "archer", "healer", "engineer", "heavy")
BATTLE_ROLE_LABELS = {
    "infantry": "Infantry",
    "archer": "Archer",
    "healer": "Healer",
    "engineer": "Engineer",
    "heavy": "Heavy fighter",
}
FIGHTER_ENLISTED = "enlisted"
FIGHTER_CONFIRMED = "confirmed"
# Design: War Forge — siege-only armour/weapons; personal gear unavailable in the assault.
# Smithing gates quality. Equipment locks when the assault begins.
FORGE_GRADES = {
    "standard": {
        "name": "Standard",
        "smithing_req": 1,
        "cost": {"bars": 5, "ore": 5, "timber": 5},
        "base": {
            "att_bonus": 2, "str_bonus": 2, "def_bonus": 2,
            "ranged_att": 2, "ranged_str": 2,
        },
        "contrib": 3,
    },
    "reinforced": {
        "name": "Reinforced",
        "smithing_req": 40,
        "cost": {"bars": 12, "ore": 10, "timber": 8},
        "base": {
            "att_bonus": 5, "str_bonus": 5, "def_bonus": 5,
            "ranged_att": 5, "ranged_str": 5,
        },
        "contrib": 8,
    },
    "masterwork": {
        "name": "Masterwork",
        "smithing_req": 70,
        "cost": {"bars": 22, "ore": 18, "timber": 12, "stone": 5},
        "base": {
            "att_bonus": 9, "str_bonus": 9, "def_bonus": 9,
            "ranged_att": 9, "ranged_str": 9,
        },
        "contrib": 15,
    },
}
# Role bias on top of grade base (never drops a bonus below 0).
FORGE_ROLE_BIAS = {
    "infantry": {},
    "archer": {
        "ranged_att": 2, "ranged_str": 2, "att_bonus": -1, "str_bonus": -1,
    },
    "healer": {"def_bonus": 3, "att_bonus": -1, "str_bonus": -1},
    "engineer": {"def_bonus": 1, "att_bonus": -1, "str_bonus": -1},
    "heavy": {
        "def_bonus": 3, "str_bonus": 2, "att_bonus": -1,
        "ranged_att": -2, "ranged_str": -2,
    },
}
FORGE_BONUS_KEYS = ("att_bonus", "str_bonus", "def_bonus", "ranged_att", "ranged_str")
# Design: max two active attackers vs one player — server-enforced focus fire.
SIEGE_MAX_ATTACKERS = 2
# Area attacks may still hit crowded tiles, but at reduced direct effect.
SIEGE_AREA_DAMAGE_MULT = 0.50
INTEREST_RADIUS = 24           # tiles: combat / state interest during an active war
INTEREST_RADIUS_BREACHED = 36  # after the watchtower falls, the battlefield opens up
# Milestone 8: interest fan-out keeps at most SIDE_CAP other fighters (profiled for 100-a-side).
INTEREST_CAP = SIDE_CAP
ASSAULT_DELAY = 1 * HOUR       # default after both confirm if attackers do not pick a window
ASSAULT_SECONDS = 3 * HOUR     # design: siege runs two to three hours
# Design: attacking alliance selects a coordinated assault window; several days to prepare.
ASSAULT_WINDOW_MIN_H = max(1, ASSAULT_DELAY // HOUR)
ASSAULT_WINDOW_MAX_H = 72      # three days — "several days" of community preparation
SIEGE_COOLDOWN = 30 * DAY      # monthly war cadence between completed wars
# Design: monthly siege calendar builds anticipation toward Day 30 — The Siege.
MONTHLY_CALENDAR = (
    (1, 7, "Days 1–7 — Royal announcements, guild recruitment and diplomacy"),
    (8, 14, "Days 8–14 — Gathering wood, stone, ore and supplies"),
    (15, 21, "Days 15–21 — Crafting weapons, siege engines and fortifications"),
    (22, 27, "Days 22–27 — Final alliances, Engineering and military preparation"),
    (28, 29, "Days 28–29 — War registration and battle assignments"),
    (30, 30, "Day 30 — The Siege of Crownfall"),
)
BREACH_STRUCTURES = ("outer_gate", "west_wall", "east_wall")
CAPTURE_CONTRIB = 25           # points each fighter present when a point flips to their side
SIDES = ("attack", "defend")
WAR_OPEN = ("registration", "scheduled", "active")
SLOT_LIVE = ("queued", "reserved", "confirmed")

# ---- milestone 3: war storehouse ---------------------------------------------
# item_id → (store resource key, contribution points per item)
STORE_ITEMS = {
    "logs": ("timber", 1),
    "oak_logs": ("timber", 2),
    "willow_logs": ("timber", 3),
    "maple_logs": ("timber", 4),
    "yew_logs": ("timber", 5),
    "magic_logs": ("timber", 6),
    "iron_ore": ("ore", 2),
    "copper_ore": ("ore", 1),
    "tin_ore": ("ore", 1),
    "mithril_ore": ("ore", 4),
    "coal": ("stone", 1),          # stand-in for quarried stone until a stone node exists
    "iron_bar": ("bars", 3),
    "bronze_bar": ("bars", 2),
    "steel_bar": ("bars", 4),
    "mithril_bar": ("bars", 5),
}
STORE_RESOURCES = ("timber", "ore", "bars", "stone")
# Leader allocation buckets (percentages must sum to 100).
ALLOC_BUCKETS = ("rams", "ladders", "barricades", "reserve")
DEFAULT_ALLOC = {"rams": 40, "ladders": 25, "barricades": 20, "reserve": 15}

# ---- milestone 4: siege weapons + breaches -----------------------------------
WEAPONS = {
    "ram": {
        "name": "Battering Ram",
        "cost": {"timber": 40, "bars": 5},
        "alloc": "rams",
        "damage": 1200,
        "targets": ("outer_gate",),
    },
    "ladder": {
        "name": "Siege Ladder",
        "cost": {"timber": 25},
        "alloc": "ladders",
        "damage": 500,
        "targets": ("west_wall", "east_wall"),
    },
    "tower": {
        # Design: woodcutters supply timber for ladders, rams and siege towers.
        "name": "Siege Tower",
        "cost": {"timber": 50, "bars": 4},
        "alloc": "ladders",
        "damage": 900,
        "targets": ("west_wall", "east_wall", "watchtower"),
    },
    "catapult": {
        "name": "Catapult",
        "cost": {"timber": 30, "ore": 10, "bars": 3},
        "alloc": "rams",
        "damage": 800,
        "targets": (
            "outer_gate", "west_wall", "east_wall", "watchtower",
            "armoury", "supply_depot", "royal_keep",
        ),
    },
    "barricade": {
        "name": "Barricade",
        "cost": {"timber": 20, "stone": 10},
        "alloc": "barricades",
        "damage": 0,
        "targets": (),  # defenders deploy onto capture points, not structures
        "contrib": 0,
    },
}
# Contribution for combat path that is not a kill (engines / repairs).
for _wid, _wspec in WEAPONS.items():
    _wspec.setdefault("contrib", max(1, int(_wspec.get("damage") or 0) // 100))
REPAIR_CONTRIB_PER_BATCH = 4
# Wall / gate tiles that become walkable once the named structure is destroyed.
_BREACH_CACHE = None
_BREACH_STATES = None
_CONN = None  # tests set this; live code uses server.WORLD.db.conn

# ---- milestone 5: capture points, throne hold, Last Stand --------------------
# Attackers push stages in order (outer settlement → walls/gate → court → throne).
CAPTURE_ORDER = ("outer_yard", "gatehouse", "courtyard", "throne")
# Design stages 1–4 map onto capture points; Stage 5 is Crownfall on resolve.
CAPTURE_STAGES = {
    "outer_yard": (1, "Break the outer defences"),
    "gatehouse": (2, "Breach the walls"),
    "courtyard": (3, "Capture the courtyard"),
    "throne": (4, "Take the throne room"),
}
CAPTURE_POINTS = {
    "outer_yard": {
        "name": "Outer Yard",
        "plane": "realm",
        "rect": (140, 70, 160, 80),
        "capture_need": 30,
    },
    "gatehouse": {
        "name": "Gatehouse",
        "plane": "realm",
        "rect": (145, 60, 155, 70),
        "capture_need": 40,
    },
    "courtyard": {
        "name": "Courtyard",
        "plane": "realm",
        "rect": (140, 48, 160, 58),
        "capture_need": 50,
    },
    "throne": {
        "name": "Throne Room",
        "plane": "king_f1",
        "rect": (16, 12, 36, 22),  # matches throne.THRONE_AREA
        "capture_need": 100,
        "hold_seconds": 120,
    },
}
THRONE_HOLD_SECONDS = 120
BARRICADE_DEPLOY_HP = 40       # HP added per deployed barricade on a capture point
GUARD_DEPLOY_HP = 30           # HP added per Guard recruit posted on a capture point
FALLBACK_BARRICADE_HP = 20     # hasty fortification when defenders regroup to the next stage
ROYAL_GUARD_HP = 50            # throne fortification when the keep falls (final hold)
ROYAL_GUARD_SENTINEL = -1      # crown_war_guards.recruit_id for the system royal-guard grant
# Design: limited appointed players who can protect the King.
ROYAL_GUARD_PLAYER_CAP = 4
KING_CASTLE_ID = "king"

# Anchored to the existing King's Castle (king_castle.json footprint / Great Hall).
STRUCTURES = (
    {
        "id": "outer_gate",
        "name": "Outer Gate",
        "max_hp": 10000,
        "plane": "realm",
        "anchor": (149, 66),
        "effect": "Opens the main entrance",
    },
    {
        "id": "west_wall",
        "name": "West Wall",
        "max_hp": 8000,
        "plane": "realm",
        "anchor": (125, 45),
        "effect": "Creates a breach for attackers",
    },
    {
        "id": "east_wall",
        "name": "East Wall",
        "max_hp": 8000,
        "plane": "realm",
        "anchor": (174, 45),
        "effect": "Creates a breach for attackers",
    },
    {
        "id": "watchtower",
        "name": "Watchtower",
        "max_hp": 6000,
        "plane": "realm",
        "anchor": (120, 20),
        "effect": "Removes defensive archers and visibility",
    },
    {
        "id": "armoury",
        "name": "Armoury",
        "max_hp": 5000,
        "plane": "realm",
        "anchor": (160, 40),
        "effect": "Weakens defender resupply",
    },
    {
        "id": "supply_depot",
        "name": "Supply Depot",
        "max_hp": 5000,
        "plane": "realm",
        "anchor": (140, 55),
        "effect": "Reduces defender repair capacity",
    },
    {
        "id": "royal_keep",
        "name": "Royal Keep",
        "max_hp": 12000,
        "plane": "king_f1",
        "anchor": (26, 17),
        "effect": "Opens the final route to the throne",
    },
)

_BY_ID = {s["id"]: s for s in STRUCTURES}
STATES = ("intact", "damaged", "heavily_damaged", "destroyed")
FOUNDER_USERNAME = "david"
FOUNDER_CHAR_NAME = "The Creator"


def state_for(hp, max_hp):
    """HP band → visible damage state."""
    hp = max(0, int(hp))
    max_hp = max(1, int(max_hp))
    if hp <= 0:
        return "destroyed"
    if hp < max_hp / 3:
        return "heavily_damaged"
    if hp < (2 * max_hp) / 3:
        return "damaged"
    return "intact"


def ensure_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_structures ("
        "id TEXT PRIMARY KEY,"
        "hp INTEGER NOT NULL,"
        "max_hp INTEGER NOT NULL,"
        "updated_at REAL NOT NULL)"
    )
    now = time.time()
    for spec in STRUCTURES:
        conn.execute(
            "INSERT OR IGNORE INTO crown_structures (id, hp, max_hp, updated_at) VALUES (?, ?, ?, ?)",
            (spec["id"], spec["max_hp"], spec["max_hp"], now),
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_wars ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "status TEXT NOT NULL,"
        "opened_at REAL NOT NULL,"
        "scheduled_at REAL,"
        "closed_at REAL,"
        "note TEXT)"
    )
    war_cols = {r[1] for r in conn.execute("PRAGMA table_info(crown_wars)")}
    if "started_at" not in war_cols:
        conn.execute("ALTER TABLE crown_wars ADD COLUMN started_at REAL")
    if "postpones" not in war_cols:
        conn.execute(
            "ALTER TABLE crown_wars ADD COLUMN postpones INTEGER NOT NULL DEFAULT 0"
        )
    if "scale" not in war_cols:
        conn.execute("ALTER TABLE crown_wars ADD COLUMN scale TEXT")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_slots ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "war_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "side TEXT NOT NULL,"
        "status TEXT NOT NULL,"
        "registered_at REAL NOT NULL,"
        "reserved_at REAL,"
        "confirm_deadline REAL,"
        "confirmed_at REAL,"
        "human_count INTEGER NOT NULL DEFAULT 0,"
        "UNIQUE(war_id, clan_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_allies ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "war_id INTEGER NOT NULL,"
        "lead_clan_id INTEGER NOT NULL,"
        "ally_clan_id INTEGER NOT NULL,"
        "side TEXT NOT NULL,"
        "status TEXT NOT NULL,"
        "invited_at REAL NOT NULL,"
        "resolved_at REAL,"
        "UNIQUE(war_id, ally_clan_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_store ("
        "war_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "resource TEXT NOT NULL,"
        "qty INTEGER NOT NULL DEFAULT 0,"
        "PRIMARY KEY (war_id, clan_id, resource))"
    )
    store_cols = {r[1] for r in conn.execute("PRAGMA table_info(crown_war_store)")}
    if "deposited" not in store_cols:
        conn.execute(
            "ALTER TABLE crown_war_store ADD COLUMN deposited INTEGER NOT NULL DEFAULT 0"
        )
        # Existing stock was deposited at some point — treat current qty as deposited floor.
        conn.execute(
            "UPDATE crown_war_store SET deposited = MAX(deposited, qty)"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_spent ("
        "war_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "bucket TEXT NOT NULL,"
        "resource TEXT NOT NULL,"
        "qty INTEGER NOT NULL DEFAULT 0,"
        "PRIMARY KEY (war_id, clan_id, bucket, resource))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_alloc ("
        "war_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "bucket TEXT NOT NULL,"
        "pct INTEGER NOT NULL,"
        "PRIMARY KEY (war_id, clan_id, bucket))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_contrib ("
        "war_id INTEGER NOT NULL,"
        "player_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "points INTEGER NOT NULL DEFAULT 0,"
        "deposits INTEGER NOT NULL DEFAULT 0,"
        "PRIMARY KEY (war_id, player_id))"
    )
    contrib_cols = {r[1] for r in conn.execute("PRAGMA table_info(crown_war_contrib)")}
    if "kills" not in contrib_cols:
        conn.execute(
            "ALTER TABLE crown_war_contrib ADD COLUMN kills INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_weapons ("
        "war_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "weapon_id TEXT NOT NULL,"
        "qty INTEGER NOT NULL DEFAULT 0,"
        "PRIMARY KEY (war_id, clan_id, weapon_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_captures ("
        "war_id INTEGER NOT NULL,"
        "point_id TEXT NOT NULL,"
        "owner TEXT NOT NULL DEFAULT 'none',"
        "progress INTEGER NOT NULL DEFAULT 0,"
        "hold_started_at REAL,"
        "updated_at REAL NOT NULL,"
        "PRIMARY KEY (war_id, point_id))"
    )
    cap_cols = {r[1] for r in conn.execute("PRAGMA table_info(crown_war_captures)")}
    if "barricades" not in cap_cols:
        conn.execute(
            "ALTER TABLE crown_war_captures ADD COLUMN barricades INTEGER NOT NULL DEFAULT 0"
        )
    if "guards" not in cap_cols:
        conn.execute(
            "ALTER TABLE crown_war_captures ADD COLUMN guards INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_guards ("
        "war_id INTEGER NOT NULL,"
        "recruit_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "point_id TEXT NOT NULL,"
        "deployed_at REAL NOT NULL,"
        "PRIMARY KEY (war_id, recruit_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_elim ("
        "war_id INTEGER NOT NULL,"
        "player_id INTEGER NOT NULL,"
        "eliminated_at REAL NOT NULL,"
        "PRIMARY KEY (war_id, player_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_heraldry ("
        "castle_id TEXT PRIMARY KEY,"
        "player_id INTEGER NOT NULL,"
        "banner_json TEXT,"
        "outfit_unlocked INTEGER NOT NULL DEFAULT 1,"
        "granted_at REAL NOT NULL,"
        "war_id INTEGER)"
    )
    # Design: limited appointed players who can protect the King.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_royal_players ("
        "war_id INTEGER NOT NULL,"
        "player_id INTEGER NOT NULL,"
        "appointed_by INTEGER NOT NULL,"
        "appointed_at REAL NOT NULL,"
        "PRIMARY KEY (war_id, player_id))"
    )
    # Design: each human explicitly registers, chooses a role, and confirms attendance.
    # Guild membership alone must not count toward the human minimum / merc balance.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_fighters ("
        "war_id INTEGER NOT NULL,"
        "player_id INTEGER NOT NULL,"
        "clan_id INTEGER NOT NULL,"
        "side TEXT NOT NULL,"
        "status TEXT NOT NULL,"
        "role TEXT NOT NULL DEFAULT 'infantry',"
        "equipment_ready INTEGER NOT NULL DEFAULT 0,"
        "enlisted_at REAL NOT NULL,"
        "confirmed_at REAL,"
        "PRIMARY KEY (war_id, player_id))"
    )
    fighter_cols = {r[1] for r in conn.execute("PRAGMA table_info(crown_war_fighters)")}
    if "equipment_grade" not in fighter_cols:
        conn.execute(
            "ALTER TABLE crown_war_fighters ADD COLUMN equipment_grade TEXT"
        )
    if "equipment_forged_at" not in fighter_cols:
        conn.execute(
            "ALTER TABLE crown_war_fighters ADD COLUMN equipment_forged_at REAL"
        )
    # Design: two-attacker focus lock during the assault.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crown_war_focus ("
        "war_id INTEGER NOT NULL,"
        "defender_id INTEGER NOT NULL,"
        "attacker_id INTEGER NOT NULL,"
        "engaged_at REAL NOT NULL,"
        "PRIMARY KEY (war_id, attacker_id))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crown_war_focus_def "
        "ON crown_war_focus (war_id, defender_id)"
    )
    conn.commit()


def _row(conn, structure_id):
    return conn.execute(
        "SELECT id, hp, max_hp, updated_at FROM crown_structures WHERE id = ?",
        (structure_id,),
    ).fetchone()


def get_structure(conn, structure_id):
    spec = _BY_ID.get(structure_id)
    if not spec:
        return None
    row = _row(conn, structure_id)
    if not row:
        return None
    hp, max_hp = int(row[1]), int(row[2])
    return {
        "id": structure_id,
        "name": spec["name"],
        "hp": hp,
        "max_hp": max_hp,
        "state": state_for(hp, max_hp),
        "plane": spec["plane"],
        "anchor": spec["anchor"],
        "effect": spec["effect"],
        "updated_at": float(row[3]),
    }


def list_structures(conn):
    return [get_structure(conn, s["id"]) for s in STRUCTURES]


def public_state(conn):
    """Castle payload: structure id → state, plus optional ``war`` board."""
    out = {}
    for s in list_structures(conn):
        if not s:
            continue
        out[s["id"]] = {
            "name": s["name"],
            "hp": s["hp"],
            "max_hp": s["max_hp"],
            "state": s["state"],
            "plane": s["plane"],
            "anchor": list(s["anchor"]),
        }
    tick_wars(conn)
    war = current_war(conn)
    out["war"] = war_public(conn, war) if war else None
    out["heraldry"] = castle_heraldry(conn)
    return out


def destruction_presentation(structure_id, structure=None):
    """Player-facing line when a structure falls (design: visible battlefield change)."""
    spec = _BY_ID.get(structure_id) or {}
    name = (structure or {}).get("name") or spec.get("name") or structure_id
    effect = (structure or {}).get("effect") or spec.get("effect") or ""
    if structure_id == "outer_gate":
        return (
            f"The {name} is destroyed — the main entrance stands open. "
            "Attackers can pour through the gateway."
        )
    if structure_id in ("west_wall", "east_wall"):
        return (
            f"The {name} collapses — a breach opens an alternate route into the castle."
        )
    if structure_id == "watchtower":
        return (
            f"The {name} falls — defensive archers lose their vantage. "
            "Realm capture work is no longer doubled."
        )
    if structure_id == "supply_depot":
        return (
            f"The {name} burns — defender repairs now cost double materials."
        )
    if structure_id == "armoury":
        return (
            f"The {name} is ruined — defender engine crafts cost double."
        )
    if structure_id == "royal_keep":
        return (
            f"The {name} is breached — the final route to the throne chamber opens. "
            "Last Stand: Royal Guard fortifies the Throne Room."
        )
    if effect:
        return f"The {name} is destroyed — {effect}."
    return f"The {name} is destroyed."


def battlefield_effects_lines(conn):
    """Active assault presentation: breaches, depot, tower, throne hold."""
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return []
    lines = ["Battlefield:"]
    if _structure_destroyed(conn, "outer_gate"):
        lines.append("  Outer Gate open — main entrance breached.")
    for wall, label in (("west_wall", "West Wall"), ("east_wall", "East Wall")):
        if _structure_destroyed(conn, wall):
            lines.append(f"  {label} breach — alternate route open.")
    if _structure_destroyed(conn, "watchtower"):
        lines.append("  Watchtower down — no archer cover bonus for defenders.")
    else:
        lines.append("  Watchtower standing — defensive archers double realm capture work.")
    if _structure_destroyed(conn, "supply_depot"):
        lines.append("  Supply Depot destroyed — repairs cost double.")
    if _structure_destroyed(conn, "armoury"):
        lines.append("  Armoury destroyed — defender crafts cost double.")
    if _structure_destroyed(conn, "royal_keep"):
        lines.append(
            "  Royal Keep down — throne chamber is the final confrontation "
            f"(hold {THRONE_HOLD_SECONDS}s, not a single touch)."
        )
    throne = next((p for p in capture_state(conn, war["id"]) if p["id"] == "throne"), None)
    if throne and throne.get("owner") == "attack" and throne.get("hold_started_at"):
        held = max(0, int(time.time() - float(throne["hold_started_at"])))
        need = int(throne.get("hold_seconds") or THRONE_HOLD_SECONDS)
        lines.append(f"  Throne hold in progress: {held}s / {need}s — defend or break it.")
    lines.append(
        "Defenders can rebuild temporary barricades and post guards on capture points."
    )
    return lines


def apply_damage(conn, structure_id, amount, now=None):
    """Subtract HP. Returns the updated structure dict, or None if unknown."""
    if structure_id not in _BY_ID:
        return None
    amount = max(0, int(amount))
    now = time.time() if now is None else float(now)
    row = _row(conn, structure_id)
    if not row:
        return None
    before = state_for(int(row[1]), int(row[2]))
    hp = max(0, int(row[1]) - amount)
    conn.execute(
        "UPDATE crown_structures SET hp = ?, updated_at = ? WHERE id = ?",
        (hp, now, structure_id),
    )
    conn.commit()
    updated = get_structure(conn, structure_id)
    if before != "destroyed" and updated and updated["state"] == "destroyed":
        invalidate_breaches()
        try:
            import castle_realm
            castle_realm.build_plane.cache_clear()
        except Exception:
            pass
    return updated


def repair(conn, structure_id, amount, now=None):
    """Add HP up to max. Same no-live-caller rule as apply_damage for now."""
    if structure_id not in _BY_ID:
        return None
    amount = max(0, int(amount))
    now = time.time() if now is None else float(now)
    row = _row(conn, structure_id)
    if not row:
        return None
    hp = min(int(row[2]), int(row[1]) + amount)
    conn.execute(
        "UPDATE crown_structures SET hp = ?, updated_at = ? WHERE id = ?",
        (hp, now, structure_id),
    )
    conn.commit()
    return get_structure(conn, structure_id)


def reset_all(conn, now=None):
    """Restore every structure to full HP (new siege / tests)."""
    now = time.time() if now is None else float(now)
    for spec in STRUCTURES:
        conn.execute(
            "UPDATE crown_structures SET hp = max_hp, updated_at = ? WHERE id = ?",
            (now, spec["id"]),
        )
    conn.commit()


def _founder_row(conn):
    row = conn.execute(
        "SELECT id, username, char_name FROM players "
        "WHERE lower(username) = ? OR char_name = ? ORDER BY id LIMIT 1",
        (FOUNDER_USERNAME, FOUNDER_CHAR_NAME),
    ).fetchone()
    return row


def ensure_founder(conn, now=None):
    """Crown The Creator once if the throne is still an NPC. Returns True when crowned."""
    import throne

    now = time.time() if now is None else float(now)
    st = throne.state(conn)
    if st.get("monarch_kind") != "npc":
        return False
    row = _founder_row(conn)
    if not row:
        return False
    pid = int(row[0])
    throne._crown(conn, pid, "founder", "reigning", now)
    throne.log(
        conn, "founder_reign", pid,
        "The crown was founded. No siege has been fought.",
        now,
    )
    conn.commit()
    return True


def recent_war_notes(conn, limit=5):
    """Completed War for the Crown notes, newest first."""
    try:
        rows = conn.execute(
            "SELECT id, note, closed_at FROM crown_wars "
            "WHERE status = 'completed' AND note IS NOT NULL AND note != '' "
            "ORDER BY closed_at DESC, id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
    except Exception:
        return []
    return [
        {"id": int(r[0]), "note": str(r[1]), "closed_at": float(r[2]) if r[2] else None}
        for r in rows
    ]


def hall_lines(conn, now=None):
    """Great Hall chronicle: founding notice, reign board, and siege outcomes."""
    import ruling

    now = time.time() if now is None else float(now)
    lines = []
    cur = ruling.current_reign(conn)
    wars = recent_war_notes(conn, limit=5)
    if cur and cur.get("path") == "founder" and not wars:
        lines.append(
            "The crown was founded. No siege has been fought. "
            f"{cur['title']} {cur['name']} holds Crownfall."
        )
    elif cur and cur.get("path") == "founder":
        lines.append(
            f"The crown was founded by {cur['title']} {cur['name']}. "
            "Wars for the Crown have since been fought."
        )
    else:
        lines.append("The Chronicle of Kings records every reign of Crownfall.")
    lines.extend(ruling.reign_lines(conn, now) or ["The records are empty."])
    # Design: Royal Crown while holding the throne; King's Outfit / throne-room after siege.
    if cur and cur.get("name"):
        lines.append(
            f"Royal Crown: exclusive wearable crown while holding the throne "
            f"({cur.get('title') or 'Monarch'} {cur['name']})."
        )
    heraldry = castle_heraldry(conn)
    if heraldry and heraldry.get("banner"):
        charge = (heraldry.get("banner") or {}).get("charge", "arms")
        lines.append(
            f"Throne-room appearance: royal heraldry flies here "
            f"(banner charge: {charge}). King's Outfit — exclusive royal robes, "
            "mantle, and armour variants unlock at Mae's for the victor."
        )
    elif cur and cur.get("path") == "siege":
        lines.append(
            "King's Outfit — exclusive royal robes, mantle, and armour variants "
            "unlock at Mae's for the War for the Crown victor."
        )
    if wars:
        lines.append("Chronicles of the War for the Crown:")
        # Oldest first so the hall reads as a chronicle.
        for w in reversed(wars):
            lines.append(f"  {w['note']}")
    return lines


# ---- milestone 2: war registration -------------------------------------------
def _clan_of(conn, player_id):
    if not player_id:
        return None
    row = conn.execute(
        "SELECT clan_id FROM clan_members WHERE player_id = ?", (int(player_id),)
    ).fetchone()
    return int(row[0]) if row else None


def _clan_name(conn, clan_id):
    if not clan_id:
        return None
    row = conn.execute("SELECT name FROM clans WHERE clan_id = ?", (int(clan_id),)).fetchone()
    return row[0] if row else f"Guild #{clan_id}"


def _clan_by_name(conn, name):
    if not name:
        return None
    row = conn.execute(
        "SELECT clan_id, name, leader_id FROM clans WHERE name = ? COLLATE NOCASE",
        (str(name).strip(),),
    ).fetchone()
    return row


def _rank_of(conn, player_id):
    if not player_id:
        return None
    row = conn.execute(
        "SELECT m.rank, c.leader_id FROM clan_members m JOIN clans c ON c.clan_id = m.clan_id "
        "WHERE m.player_id = ?",
        (int(player_id),),
    ).fetchone()
    if not row:
        return None
    if int(row[1]) == int(player_id):
        return "Leader"
    return row[0] or "Member"


def _guild_member_count(conn, clan_id):
    """Raw guild size — not a siege participation count."""
    if not clan_id:
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (int(clan_id),)
    ).fetchone()
    return int(row[0] if row else 0)


def _humans(conn, war_id, clan_id):
    """Confirmed human siege participants in this clan for this war.

    Design: guild membership must not count — only fighters who enlisted and
    confirmed attendance count toward the human minimum and merc balance.
    """
    if not clan_id or not war_id:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM crown_war_fighters "
            "WHERE war_id = ? AND clan_id = ? AND status = ?",
            (int(war_id), int(clan_id), FIGHTER_CONFIRMED),
        ).fetchone()
        return int(row[0] if row else 0)
    except Exception:
        return 0


def _alliance_humans(conn, war_id, lead_clan_id, side):
    total = _humans(conn, war_id, lead_clan_id)
    rows = conn.execute(
        "SELECT ally_clan_id FROM crown_war_allies WHERE war_id = ? AND lead_clan_id = ? "
        "AND side = ? AND status = 'accepted'",
        (int(war_id), int(lead_clan_id), side),
    ).fetchall()
    for (ally,) in rows:
        total += _humans(conn, war_id, ally)
    return total


def _side_confirmed_humans(conn, war_id, side):
    """All confirmed human fighters on a side (any clan in the alliance)."""
    lead = _lead_slot(conn, war_id, side)
    if not lead:
        return 0
    return _alliance_humans(conn, war_id, lead["clan_id"], side)


def _sides_meet_human_min(conn, war_id, min_humans=None):
    """True when both confirmed leads still field the required alliance humans."""
    if min_humans is None:
        war = current_war(conn)
        if war and int(war.get("id") or 0) == int(war_id):
            min_humans = effective_human_min(war)
        else:
            min_humans = HUMAN_MIN
    need = max(1, int(min_humans))
    weak = []
    for side in SIDES:
        lead = _lead_slot(conn, war_id, side)
        if not lead or lead["status"] != "confirmed":
            return False, f"{side} is not confirmed"
        humans = _alliance_humans(conn, war_id, lead["clan_id"], side)
        if humans < need:
            weak.append(f"{lead['name']} ({side}, {humans}/{need})")
    if weak:
        return False, "under strength — " + "; ".join(weak)
    return True, None


def army_composition_lines(conn, war=None, now=None):
    """Design: human/mercenary numbers visible to both leaders before roster locks."""
    war = war or current_war(conn)
    if not war or war.get("status") not in ("registration", "scheduled", "active"):
        return []
    bits = []
    counts = {}
    for side in SIDES:
        lead = _lead_slot(conn, war["id"], side)
        if not lead:
            bits.append(f"{side.title()} open")
            continue
        humans = _alliance_humans(conn, war["id"], lead["clan_id"], side)
        mercs = _alliance_mercs(conn, war["id"], lead["clan_id"], side)
        counts[side] = humans
        bits.append(f"{side.title()} {humans}h/{mercs}m ({lead['name']})")
    if war.get("status") == "active":
        lock = " — locked for the assault"
    else:
        lock = " — visible to both leaders; locks when the assault begins"
    lines = [
        "Army composition (confirmed fighters only — /siege enlist · /siege attend): "
        + " · ".join(bits) + lock
    ]
    atk_h = counts.get("attack")
    dfn_h = counts.get("defend")
    if atk_h is not None and dfn_h is not None and atk_h != dfn_h:
        behind = "Attack" if atk_h < dfn_h else "Defend"
        lines.append(
            f"{behind} trails in humans — cannot hire mercenaries to pad that "
            "combat-power disadvantage."
        )
    return lines


def roster_locked(conn, clan_id=None):
    """Ally invites and recruit hires freeze once the assault is active."""
    war = current_war(conn)
    return bool(war and war.get("status") == "active")


def hiring_locked(conn, clan_id=None):
    """Guild recruit contracts lock for the duration of an active assault."""
    return roster_locked(conn, clan_id)


def war_merc_caps_ok(humans, mercs=0):
    """Side cap + 40% merc ceiling without requiring HUMAN_MIN (confirm still does).

    Stops a side from hiring mercenaries past the war roster rules — including
    padding a combat-power gap beyond the 40% ceiling of their own humans.
    """
    humans = max(0, int(humans))
    mercs = max(0, int(mercs))
    total = humans + mercs
    if total > SIDE_CAP:
        return False, f"A side may field at most {SIDE_CAP} fighters (you would have {total})."
    if humans <= 0 and mercs > 0:
        return False, "Recruit human fighters before hiring war mercenaries."
    if total > 0 and mercs / total > MERC_MAX_FRACTION + 1e-9:
        max_mercs = int(humans * MERC_MAX_FRACTION / (1.0 - MERC_MAX_FRACTION))
        return False, (
            f"War mercenaries may be at most {int(MERC_MAX_FRACTION * 100)}% of the side "
            f"(max {max_mercs} for {humans} humans; you would have {mercs})."
        )
    return True, None


def hire_allowed(conn, clan_id):
    """Whether a guild may hire another recruit under open-war roster rules.

    Returns (ok, message). Peacetime / unregistered guilds always ok.

    Design: a side cannot hire extra mercenaries to compensate for a major
    combat-power disadvantage — if the opposing alliance fields more humans,
    further war merc hires are refused.
    """
    if not clan_id:
        return True, None
    if hiring_locked(conn, clan_id):
        return False, "Recruit contracts are locked during the War for the Crown assault."
    war = current_war(conn)
    if not war or war.get("status") not in WAR_OPEN:
        return True, None
    side, lead_id = _player_war_side(conn, war["id"], int(clan_id))
    if not side or not lead_id:
        return True, None
    humans = _alliance_humans(conn, war["id"], lead_id, side)
    mercs = _alliance_mercs(conn, war["id"], lead_id, side)
    foe_side = "defend" if side == "attack" else "attack"
    foe = _lead_slot(conn, war["id"], foe_side)
    if foe and foe.get("status") in ("reserved", "confirmed"):
        foe_humans = _alliance_humans(conn, war["id"], foe["clan_id"], foe_side)
        if humans < foe_humans:
            return False, (
                "You cannot hire mercenaries to pad a combat-power disadvantage "
                f"({humans} humans vs {foe_humans} on the opposing side). "
                "Recruit more human fighters first."
            )
    ok, msg = war_merc_caps_ok(humans, mercs + 1)
    if not ok:
        return False, msg
    return True, None


def _monarch_clan(conn):
    try:
        import throne
        st = throne.state(conn)
    except Exception:
        return None
    if st.get("monarch_kind") != "player" or not st.get("monarch_player_id"):
        return None
    return _clan_of(conn, st["monarch_player_id"])


def _is_leader(conn, player_id):
    return _rank_of(conn, player_id) == "Leader"


def assault_starts_at(war):
    """Unix time when a scheduled war's assault auto-begins."""
    if not war or war.get("scheduled_at") is None:
        return None
    return float(war["scheduled_at"]) + ASSAULT_DELAY


def _is_attack_lead_leader(conn, player_id, war):
    """True when the player leads the attacking alliance's lead guild."""
    if not war or not _is_leader(conn, player_id):
        return False
    clan_id = _clan_of(conn, player_id)
    atk = _lead_slot(conn, war["id"], "attack")
    return bool(atk and clan_id and int(atk["clan_id"]) == int(clan_id))


def current_war(conn):
    try:
        row = conn.execute(
            "SELECT id, status, opened_at, scheduled_at, closed_at, note, started_at, "
            "COALESCE(postpones, 0), scale "
            "FROM crown_wars WHERE status IN ('registration', 'scheduled', 'active') "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except Exception:
        try:
            row = conn.execute(
                "SELECT id, status, opened_at, scheduled_at, closed_at, note, started_at "
                "FROM crown_wars WHERE status IN ('registration', 'scheduled', 'active') "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                row = tuple(row) + (0, None)
        except Exception:
            row = conn.execute(
                "SELECT id, status, opened_at, scheduled_at, closed_at, note "
                "FROM crown_wars WHERE status IN ('registration', 'scheduled', 'active') "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                row = tuple(row) + (None, 0, None)
    if not row:
        return None
    return {
        "id": int(row[0]),
        "status": row[1],
        "opened_at": float(row[2]),
        "scheduled_at": float(row[3]) if row[3] is not None else None,
        "closed_at": float(row[4]) if row[4] is not None else None,
        "note": row[5],
        "started_at": float(row[6]) if len(row) > 6 and row[6] is not None else None,
        "postpones": int(row[7] or 0) if len(row) > 7 else 0,
        "scale": row[8] if len(row) > 8 else None,
    }


def effective_human_min(war=None):
    """Human minimum for this war — full roster, or smaller scale after postpone."""
    if war and str(war.get("scale") or "") == "small":
        return SMALL_SCALE_HUMAN_MIN
    return HUMAN_MIN


def _last_closed(conn):
    row = conn.execute(
        "SELECT closed_at FROM crown_wars WHERE status IN ('completed', 'cancelled') "
        "AND closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _slots(conn, war_id, side=None, statuses=None):
    sql = (
        "SELECT id, war_id, clan_id, side, status, registered_at, reserved_at, "
        "confirm_deadline, confirmed_at, human_count FROM crown_war_slots WHERE war_id = ?"
    )
    args = [int(war_id)]
    if side:
        sql += " AND side = ?"
        args.append(side)
    if statuses:
        sql += " AND status IN (" + ",".join("?" * len(statuses)) + ")"
        args.extend(statuses)
    sql += " ORDER BY registered_at, id"
    out = []
    for r in conn.execute(sql, args).fetchall():
        out.append({
            "id": int(r[0]),
            "war_id": int(r[1]),
            "clan_id": int(r[2]),
            "side": r[3],
            "status": r[4],
            "registered_at": float(r[5]),
            "reserved_at": float(r[6]) if r[6] is not None else None,
            "confirm_deadline": float(r[7]) if r[7] is not None else None,
            "confirmed_at": float(r[8]) if r[8] is not None else None,
            "human_count": int(r[9] or 0),
            "name": _clan_name(conn, r[2]),
        })
    return out


def _allies(conn, war_id, side=None):
    sql = (
        "SELECT id, lead_clan_id, ally_clan_id, side, status, invited_at, resolved_at "
        "FROM crown_war_allies WHERE war_id = ?"
    )
    args = [int(war_id)]
    if side:
        sql += " AND side = ?"
        args.append(side)
    sql += " ORDER BY invited_at, id"
    out = []
    for r in conn.execute(sql, args).fetchall():
        out.append({
            "id": int(r[0]),
            "lead_clan_id": int(r[1]),
            "ally_clan_id": int(r[2]),
            "side": r[3],
            "status": r[4],
            "invited_at": float(r[5]),
            "resolved_at": float(r[6]) if r[6] is not None else None,
            "lead_name": _clan_name(conn, r[1]),
            "ally_name": _clan_name(conn, r[2]),
        })
    return out


def _lead_slot(conn, war_id, side):
    for st in ("confirmed", "reserved"):
        rows = _slots(conn, war_id, side=side, statuses=(st,))
        if rows:
            return rows[0]
    return None


def _promote_next(conn, war_id, side, now):
    """Give the next queued guild the reserved slot + 48h confirm window."""
    queued = _slots(conn, war_id, side=side, statuses=("queued",))
    if not queued:
        return None
    nxt = queued[0]
    deadline = now + CONFIRM_SECONDS
    conn.execute(
        "UPDATE crown_war_slots SET status = 'reserved', reserved_at = ?, confirm_deadline = ?, "
        "human_count = ? WHERE id = ?",
        (now, deadline, _humans(conn, war_id, nxt["clan_id"]), nxt["id"]),
    )
    conn.commit()
    try:
        import politics
        politics.news(
            conn, "siege",
            f"{nxt['name']} now holds the {side} slot for the War for the Crown "
            f"(confirm with {HUMAN_MIN}+ confirmed fighters within 48 hours).",
            now,
        )
    except Exception:
        pass
    return get_slot(conn, nxt["id"])


def get_slot(conn, slot_id):
    row = conn.execute(
        "SELECT id, war_id, clan_id, side, status, registered_at, reserved_at, "
        "confirm_deadline, confirmed_at, human_count FROM crown_war_slots WHERE id = ?",
        (int(slot_id),),
    ).fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "war_id": int(row[1]),
        "clan_id": int(row[2]),
        "side": row[3],
        "status": row[4],
        "registered_at": float(row[5]),
        "reserved_at": float(row[6]) if row[6] is not None else None,
        "confirm_deadline": float(row[7]) if row[7] is not None else None,
        "confirmed_at": float(row[8]) if row[8] is not None else None,
        "human_count": int(row[9] or 0),
        "name": _clan_name(conn, row[2]),
    }


def tick_wars(conn, now=None):
    """Expire unconfirmed reservations and promote the next guild. Returns notices."""
    now = time.time() if now is None else float(now)
    notices = []
    war = current_war(conn)
    if war and war["status"] in ("registration", "scheduled"):
        for side in SIDES:
            reserved = _slots(conn, war["id"], side=side, statuses=("reserved",))
            for slot in reserved:
                deadline = slot.get("confirm_deadline") or 0
                if now < deadline:
                    continue
                conn.execute(
                    "UPDATE crown_war_slots SET status = 'forfeited', human_count = ? WHERE id = ?",
                    (_humans(conn, war["id"], slot["clan_id"]), slot["id"]),
                )
                conn.commit()
                msg = (
                    f"{slot['name']} failed to confirm the {side} slot in time. "
                    "The next eligible guild may take it."
                )
                notices.append(msg)
                try:
                    import politics
                    politics.news(conn, "siege", msg, now)
                except Exception:
                    pass
                promoted = _promote_next(conn, war["id"], side, now)
                if promoted:
                    notices.append(
                        f"{promoted['name']} now holds the {side} slot "
                        f"(confirm by reaching {HUMAN_MIN} humans within 48 hours)."
                    )
    # If both sides confirmed while registration was open, mark scheduled.
    war = current_war(conn)
    if war and war["status"] == "registration":
        atk = _lead_slot(conn, war["id"], "attack")
        dfn = _lead_slot(conn, war["id"], "defend")
        if atk and atk["status"] == "confirmed" and dfn and dfn["status"] == "confirmed":
            conn.execute(
                "UPDATE crown_wars SET status = 'scheduled', scheduled_at = ? WHERE id = ?",
                (now, war["id"]),
            )
            conn.commit()
            notices.append(
                "Both sides confirmed. The War for the Crown is scheduled — "
                f"assault begins in {ASSAULT_DELAY // HOUR} hour(s) by default. "
                f"Attack Leader: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h "
                "to set the coordinated assault window."
            )
            try:
                import politics
                politics.news(
                    conn, "siege",
                    "Both sides confirmed. The War for the Crown is scheduled — "
                    "the attacking alliance may select the assault window.",
                    now,
                )
            except Exception:
                pass
    # Auto-start the assault after the confirm delay (inline — do not call
    # begin_assault here; that function calls tick_wars and would recurse).
    war = current_war(conn)
    if war and war["status"] == "scheduled":
        start_at = assault_starts_at(war) or 0
        if now >= start_at:
            atk = _lead_slot(conn, war["id"], "attack")
            dfn = _lead_slot(conn, war["id"], "defend")
            if atk and atk["status"] == "confirmed" and dfn and dfn["status"] == "confirmed":
                ready, why = _sides_meet_human_min(conn, war["id"], HUMAN_MIN)
                if ready:
                    msg = _activate_assault(conn, war["id"], now)
                    notices.append(msg)
                else:
                    postpones = int(war.get("postpones") or 0)
                    # Design: postponed or run at a smaller scale.
                    if postpones >= 1:
                        ready_small, why_small = _sides_meet_human_min(
                            conn, war["id"], SMALL_SCALE_HUMAN_MIN,
                        )
                        if ready_small:
                            conn.execute(
                                "UPDATE crown_wars SET scale = 'small' WHERE id = ?",
                                (war["id"],),
                            )
                            conn.commit()
                            msg = _activate_assault(conn, war["id"], now)
                            notices.append(
                                f"Assault begins at a smaller scale "
                                f"({SMALL_SCALE_HUMAN_MIN}+ humans per side). {msg}"
                            )
                            try:
                                import politics
                                politics.news(
                                    conn, "siege",
                                    f"The War for the Crown begins at a smaller scale "
                                    f"({SMALL_SCALE_HUMAN_MIN}+ humans).",
                                    now,
                                )
                            except Exception:
                                pass
                            # Skip the postpone path this tick.
                            ready = True
                    if not ready:
                        # Push the delay window forward so ticks do not spam.
                        conn.execute(
                            "UPDATE crown_wars SET scheduled_at = ?, "
                            "postpones = COALESCE(postpones, 0) + 1 WHERE id = ?",
                            (now, war["id"]),
                        )
                        conn.commit()
                        msg = (
                            f"Assault postponed — {why}. "
                            f"Field enough humans within {ASSAULT_DELAY // HOUR} hour(s)"
                        )
                        if postpones >= 1:
                            msg += (
                                f", or hold at least {SMALL_SCALE_HUMAN_MIN} humans "
                                "per side for a smaller-scale assault"
                            )
                        else:
                            msg += (
                                f" (or the war may run at a smaller scale "
                                f"with {SMALL_SCALE_HUMAN_MIN}+ humans next window)"
                            )
                        msg += "."
                        notices.append(msg)
                        try:
                            import politics
                            politics.news(conn, "siege", msg, now)
                        except Exception:
                            pass
    # Assault clock: defenders win if attackers fail to crown in time.
    war = current_war(conn)
    if war and war["status"] == "active":
        started = float(war.get("started_at") or war.get("scheduled_at") or 0)
        if started and now >= started + ASSAULT_SECONDS:
            ok, msg = resolve_war(conn, winner="defend", now=now)
            if ok:
                notices.append(
                    "Assault time expired — " + msg
                )
    # Monthly cadence: after cooldown, open the next registration window.
    if not current_war(conn):
        last = _last_closed(conn)
        if last is not None and (now - last) >= SIEGE_COOLDOWN:
            conn.execute(
                "INSERT INTO crown_wars (status, opened_at, note) VALUES ('registration', ?, ?)",
                (now, "Guilds may register to attack or defend."),
            )
            conn.commit()
            msg = "Registration is open for the War for the Crown."
            notices.append(msg)
            try:
                import politics
                politics.news(conn, "siege", msg, now)
            except Exception:
                pass
    return notices


def open_registration(conn, now=None, force=False):
    """Open a new war registration window. Returns (ok, message, war_or_None)."""
    now = time.time() if now is None else float(now)
    before = current_war(conn)
    before_id = before["id"] if before else None
    tick_wars(conn, now)
    cur = current_war(conn)
    # tick_wars may have auto-opened after the monthly cooldown.
    if cur and before_id != cur["id"]:
        return True, "Registration is open for the War for the Crown.", cur
    if cur:
        return False, "A War for the Crown is already open.", cur
    last = _last_closed(conn)
    if last is not None and not force and (now - last) < SIEGE_COOLDOWN:
        days = int((SIEGE_COOLDOWN - (now - last) + DAY - 1) // DAY)
        return False, f"The next war opens in about {days} day(s).", None
    conn.execute(
        "INSERT INTO crown_wars (status, opened_at, note) VALUES ('registration', ?, ?)",
        (now, "Guilds may register to attack or defend."),
    )
    conn.commit()
    war = current_war(conn)
    try:
        import politics
        politics.news(conn, "siege", "Registration is open for the War for the Crown.", now)
    except Exception:
        pass
    return True, "Registration is open for the War for the Crown.", war


def register(conn, player_id, side, now=None):
    """Guild leader registers for attack or defend. First eligible gets the 48h reserved slot."""
    now = time.time() if now is None else float(now)
    side = str(side or "").lower().strip()
    if side not in SIDES:
        return False, "Choose attack or defend."
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can register for the war."
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "You must lead a guild."
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        ok, msg, war = open_registration(conn, now)
        if not ok:
            return False, msg
    if war["status"] not in ("registration", "scheduled"):
        return False, "Registration is closed for this war."
    monarch_clan = _monarch_clan(conn)
    if side == "attack" and monarch_clan and int(clan_id) == int(monarch_clan):
        return False, "The King's guild cannot register to attack the crown."
    existing = conn.execute(
        "SELECT id, side, status FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    if existing:
        return False, f"Your guild is already listed as {existing[1]} ({existing[2]})."
    # Already an accepted ally somewhere in this war?
    ally = conn.execute(
        "SELECT side, status FROM crown_war_allies WHERE war_id = ? AND ally_clan_id = ? "
        "AND status IN ('invited', 'accepted')",
        (war["id"], clan_id),
    ).fetchone()
    if ally:
        return False, "Your guild is already tied to this war as an ally."
    lead = _lead_slot(conn, war["id"], side)
    humans = _humans(conn, war["id"], clan_id)
    if lead is None:
        deadline = now + CONFIRM_SECONDS
        conn.execute(
            "INSERT INTO crown_war_slots (war_id, clan_id, side, status, registered_at, "
            "reserved_at, confirm_deadline, human_count) VALUES (?, ?, ?, 'reserved', ?, ?, ?, ?)",
            (war["id"], clan_id, side, now, now, deadline, humans),
        )
        conn.commit()
        name = _clan_name(conn, clan_id)
        # Leader still must /siege attend; enlist them so the next step is clear.
        enlist(conn, player_id, role="infantry", now=now)
        try:
            import politics
            politics.news(
                conn, "siege",
                f"{name} reserved the {side} slot. Confirm within 48 hours "
                f"with at least {HUMAN_MIN} confirmed fighters "
                f"(/siege enlist · /siege attend).",
                now,
            )
        except Exception:
            pass
        row = conn.execute(
            "SELECT id FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
            (war["id"], clan_id),
        ).fetchone()
        return True, (
            f"{name} reserved the {side} slot. Members /siege enlist [role] then "
            f"/siege attend. Confirm with /siege confirm once {HUMAN_MIN}+ fighters "
            f"have confirmed attendance (you have {humans} now; "
            f"deadline in {CONFIRM_SECONDS // HOUR}h)."
        ), get_slot(conn, int(row[0])) if row else None
    # Slot held — queue behind them.
    conn.execute(
        "INSERT INTO crown_war_slots (war_id, clan_id, side, status, registered_at, human_count) "
        "VALUES (?, ?, ?, 'queued', ?, ?)",
        (war["id"], clan_id, side, now, humans),
    )
    conn.commit()
    name = _clan_name(conn, clan_id)
    enlist(conn, player_id, role="infantry", now=now)
    row = conn.execute(
        "SELECT id FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    return True, (
        f"{name} joined the {side} queue behind {lead['name']}. "
        "Members /siege enlist [role] then /siege attend. "
        "If the lead guild fails to confirm within 48 hours, the next guild takes the slot."
    ), get_slot(conn, int(row[0])) if row else None


def enlist(conn, player_id, role="infantry", now=None):
    """Explicitly register as a human siege participant for your guild's side."""
    now = time.time() if now is None else float(now)
    role = str(role or "infantry").lower().strip()
    if role not in BATTLE_ROLES:
        return False, (
            "Choose a battle role: "
            + ", ".join(BATTLE_ROLES)
            + "."
        )
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "Join a guild before enlisting for the war."
    tick_wars(conn, now)
    war = current_war(conn)
    if not war or war["status"] not in ("registration", "scheduled"):
        return False, "No War for the Crown is open for enlistment."
    if war.get("status") == "active":
        return False, "The roster is locked for the assault."
    side, _lead = _player_war_side(conn, war["id"], clan_id)
    if not side:
        return False, "Your guild must register or accept an alliance first."
    existing = conn.execute(
        "SELECT status, role FROM crown_war_fighters WHERE war_id = ? AND player_id = ?",
        (war["id"], int(player_id)),
    ).fetchone()
    if existing:
        # Allow role change while still only enlisted (not yet attended).
        if existing[0] == FIGHTER_CONFIRMED:
            if existing[1] == role:
                return False, "You are already confirmed for this war."
            return False, "Attendance is confirmed — role is locked. (Leaders: wait for War Forge.)"
        conn.execute(
            "UPDATE crown_war_fighters SET role = ?, clan_id = ?, side = ? "
            "WHERE war_id = ? AND player_id = ?",
            (role, int(clan_id), side, war["id"], int(player_id)),
        )
        conn.commit()
        return True, (
            f"Enlisted as {BATTLE_ROLE_LABELS[role]}. "
            "Confirm attendance with /siege attend."
        )
    conn.execute(
        "INSERT INTO crown_war_fighters "
        "(war_id, player_id, clan_id, side, status, role, equipment_ready, enlisted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (war["id"], int(player_id), int(clan_id), side, FIGHTER_ENLISTED, role, now),
    )
    conn.commit()
    return True, (
        f"Enlisted for the {side} as {BATTLE_ROLE_LABELS[role]}. "
        "Confirm attendance with /siege attend when you will fight."
    )


def attend(conn, player_id, now=None):
    """Confirm attendance — only confirmed fighters count as humans for the war."""
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    war = current_war(conn)
    if not war or war["status"] not in ("registration", "scheduled"):
        return False, "No War for the Crown is open."
    if war.get("status") == "active":
        return False, "The roster is locked for the assault."
    row = conn.execute(
        "SELECT status, role, side FROM crown_war_fighters WHERE war_id = ? AND player_id = ?",
        (war["id"], int(player_id)),
    ).fetchone()
    if not row:
        return False, "Enlist first with /siege enlist [role]."
    if row[0] == FIGHTER_CONFIRMED:
        return False, "Your attendance is already confirmed."
    conn.execute(
        "UPDATE crown_war_fighters SET status = ?, confirmed_at = ? "
        "WHERE war_id = ? AND player_id = ?",
        (FIGHTER_CONFIRMED, now, war["id"], int(player_id)),
    )
    # Refresh cached human_count on the guild slot.
    clan_id = _clan_of(conn, player_id)
    if clan_id:
        humans = _humans(conn, war["id"], clan_id)
        conn.execute(
            "UPDATE crown_war_slots SET human_count = ? WHERE war_id = ? AND clan_id = ?",
            (humans, war["id"], clan_id),
        )
    conn.commit()
    side_h = _side_confirmed_humans(conn, war["id"], row[2])
    return True, (
        f"Attendance confirmed as {BATTLE_ROLE_LABELS.get(row[1], row[1])} — "
        f"you count toward the {row[2]} human roster "
        f"({side_h} confirmed on your side)."
    )


def set_fighter_role(conn, player_id, role, now=None):
    """Change battle role before attendance is confirmed / assault locks."""
    return enlist(conn, player_id, role=role, now=now)


def is_confirmed_fighter(conn, player_id, war_id=None):
    """True when this player enlisted and confirmed attendance for the war."""
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war:
        return False
    row = conn.execute(
        "SELECT 1 FROM crown_war_fighters WHERE war_id = ? AND player_id = ? AND status = ?",
        (int(war["id"]), int(player_id), FIGHTER_CONFIRMED),
    ).fetchone()
    return bool(row)


def fighter_role(conn, player_id, war_id=None):
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war:
        return None
    row = conn.execute(
        "SELECT role FROM crown_war_fighters WHERE war_id = ? AND player_id = ?",
        (int(war["id"]), int(player_id)),
    ).fetchone()
    return row[0] if row else None


def forge_locked(conn, war=None):
    """True once the assault has begun — War Forge kits cannot change."""
    war = war or current_war(conn)
    return bool(war and war.get("status") == "active")


def _forge_bonuses_for(grade, role):
    """Combine grade base with role bias; bonuses never drop below 0."""
    spec = FORGE_GRADES.get(grade) or FORGE_GRADES["standard"]
    bias = FORGE_ROLE_BIAS.get(role) or {}
    out = {k: 0 for k in FORGE_BONUS_KEYS}
    for k in FORGE_BONUS_KEYS:
        out[k] = max(0, int(spec["base"].get(k, 0)) + int(bias.get(k, 0)))
    return out


def fighter_equipment(conn, player_id, war_id=None):
    """Return forged kit info for a fighter, or None if not enlisted."""
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war:
        return None
    row = conn.execute(
        "SELECT role, status, equipment_ready, equipment_grade, equipment_forged_at "
        "FROM crown_war_fighters WHERE war_id = ? AND player_id = ?",
        (int(war["id"]), int(player_id)),
    ).fetchone()
    if not row:
        return None
    role, status, ready, grade, forged_at = row
    grade = (grade or "").lower().strip() or None
    bonuses = _forge_bonuses_for(grade, role) if ready and grade else {
        k: 0 for k in FORGE_BONUS_KEYS
    }
    return {
        "role": role,
        "status": status,
        "ready": bool(ready),
        "grade": grade,
        "grade_name": (FORGE_GRADES.get(grade) or {}).get("name") if grade else None,
        "forged_at": float(forged_at) if forged_at else None,
        "bonuses": bonuses,
    }


def siege_equipment_bonuses(conn, player_id):
    """Combat bonuses for an active-siege confirmed fighter.

    Returns a bonus dict (possibly all zeros if unforged) when personal gear
    must be replaced by War Forge kit; None when the player is not under siege rules.
    """
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return None
    if not is_confirmed_fighter(conn, player_id, war["id"]):
        return None
    info = fighter_equipment(conn, player_id, war["id"])
    if not info:
        return {k: 0 for k in FORGE_BONUS_KEYS}
    return dict(info["bonuses"])


def forge_equipment(conn, player_id, grade="standard", now=None):
    """Craft siege-only armour and weapons from the lead guild's reserve stock.

    Personal gear is unavailable during the assault — fighters must forge here.
    Equipment locks when the assault begins.
    """
    now = time.time() if now is None else float(now)
    grade = str(grade or "standard").lower().strip()
    if grade not in FORGE_GRADES:
        return False, (
            "Unknown War Forge grade. Choose: "
            + ", ".join(FORGE_GRADES)
            + "."
        )
    spec = FORGE_GRADES[grade]
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err
    if forge_locked(conn, war):
        return False, (
            "War Forge is locked — equipment was sealed when the assault began. "
            "You cannot change kit mid-battle."
        )
    if war["status"] not in ("registration", "scheduled"):
        return False, "War Forge opens during registration and preparation."
    if not is_confirmed_fighter(conn, player_id, war["id"]):
        return False, (
            "Confirm attendance with /siege enlist and /siege attend "
            "before forging battle equipment."
        )
    smith = _player_skill_level(conn, player_id, "smithing")
    if smith < int(spec["smithing_req"]):
        return False, (
            f"{spec['name']} kit needs Smithing {spec['smithing_req']} "
            f"(you have {smith}). Forge a lower grade or train Smithing."
        )
    row = conn.execute(
        "SELECT role, equipment_ready, equipment_grade FROM crown_war_fighters "
        "WHERE war_id = ? AND player_id = ?",
        (war["id"], int(player_id)),
    ).fetchone()
    role = row[0] if row else "infantry"
    already_ready = bool(row and row[1])
    already_grade = (row[2] or "").lower().strip() if row else ""
    if already_ready and already_grade == grade:
        return False, (
            f"You already forged a {spec['name']} kit for this war. "
            "Upgrade with /siege forge reinforced or /siege forge masterwork "
            "before the assault locks equipment."
        )
    # Higher grades may replace a lower kit (full cost; war economy sink).
    if already_ready and already_grade:
        order = list(FORGE_GRADES.keys())
        if order.index(grade) < order.index(already_grade):
            return False, (
                f"You already have {FORGE_GRADES[already_grade]['name']} kit — "
                "War Forge does not downgrade. Wait for the next war."
            )
    cost = dict(spec["cost"])
    ok, msg = _spend_store(conn, war["id"], lead_id, cost, bucket="reserve")
    if not ok:
        return False, msg
    bonuses = _forge_bonuses_for(grade, role)
    conn.execute(
        "UPDATE crown_war_fighters SET equipment_ready = 1, equipment_grade = ?, "
        "equipment_forged_at = ? WHERE war_id = ? AND player_id = ?",
        (grade, now, war["id"], int(player_id)),
    )
    pts = max(1, int(spec.get("contrib") or 1))
    _credit_points(conn, war["id"], player_id, pts)
    conn.commit()
    role_label = BATTLE_ROLE_LABELS.get(role, role)
    bonus_bits = ", ".join(
        f"{k.replace('_bonus', '').replace('_', ' ')}+{v}"
        for k, v in bonuses.items() if v
    )
    verb = "Upgraded to" if already_ready else "Forged"
    return True, (
        f"{verb} {spec['name']} War Forge kit for {role_label} "
        f"(spent " + ", ".join(f"{v} {k}" for k, v in cost.items())
        + f"). Bonuses: {bonus_bits or 'none'}. "
        f"Personal armour and weapons are sealed for the assault. (+{pts} contrib)"
    )


def forge_lines(conn, player_id=None, now=None):
    """War Forge panel: grades, smithing gates, and this fighter's kit."""
    now = time.time() if now is None else float(now)
    lines = [
        "War Forge — siege-only armour and weapons",
        "Personal gear is unavailable during the assault. "
        "Forge here before the battle locks equipment.",
    ]
    for gid, spec in FORGE_GRADES.items():
        cost = ", ".join(f"{v} {k}" for k, v in spec["cost"].items())
        lines.append(
            f"  {spec['name']}: Smithing {spec['smithing_req']}+ · "
            f"cost {cost} (from reserve allocation)"
        )
    lines.append(
        "Roles shape the kit (Infantry balanced · Archer ranged · "
        "Healer tougher · Engineer modest · Heavy armoured)."
    )
    war = current_war(conn)
    if not war:
        lines.append("No War for the Crown is open.")
        return lines
    if forge_locked(conn, war):
        lines.append("Equipment is locked for the assault.")
    else:
        lines.append(
            "Craft with /siege forge [standard|reinforced|masterwork] "
            "after /siege attend. Kits lock when the assault begins."
        )
    if player_id:
        info = fighter_equipment(conn, player_id, war["id"])
        if info and info["status"] == FIGHTER_CONFIRMED:
            if info["ready"]:
                lines.append(
                    f"Your kit: {info['grade_name']} "
                    f"({BATTLE_ROLE_LABELS.get(info['role'], info['role'])})."
                )
            else:
                smith = _player_skill_level(conn, player_id, "smithing")
                lines.append(
                    f"You are confirmed ({BATTLE_ROLE_LABELS.get(info['role'], info['role'])}) "
                    f"but unforged — Smithing {smith}. /siege forge to outfit."
                )
        elif info:
            lines.append("Enlist and /siege attend before forging.")
        else:
            lines.append("You are not enlisted for this war.")
    # Side readiness summary.
    for side in SIDES:
        lead = _lead_slot(conn, war["id"], side)
        if not lead:
            continue
        ready_n = conn.execute(
            "SELECT COUNT(*) FROM crown_war_fighters "
            "WHERE war_id = ? AND side = ? AND status = ? AND equipment_ready = 1",
            (war["id"], side, FIGHTER_CONFIRMED),
        ).fetchone()[0]
        total_n = _side_confirmed_humans(conn, war["id"], side)
        lines.append(
            f"{side.title()} forged: {int(ready_n)}/{int(total_n)} confirmed fighters."
        )
    return lines


def focus_attackers(conn, defender_id, war_id=None):
    """Player IDs currently allowed to deal direct damage to this defender."""
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war or not defender_id:
        return []
    rows = conn.execute(
        "SELECT attacker_id FROM crown_war_focus "
        "WHERE war_id = ? AND defender_id = ? ORDER BY engaged_at, attacker_id",
        (int(war["id"]), int(defender_id)),
    ).fetchall()
    return [int(r[0]) for r in rows]


def _clear_attacker_focus(conn, war_id, attacker_id):
    conn.execute(
        "DELETE FROM crown_war_focus WHERE war_id = ? AND attacker_id = ?",
        (int(war_id), int(attacker_id)),
    )


def _clear_defender_focus(conn, war_id, defender_id):
    conn.execute(
        "DELETE FROM crown_war_focus WHERE war_id = ? AND defender_id = ?",
        (int(war_id), int(defender_id)),
    )


def clear_war_focus(conn, war_id):
    conn.execute("DELETE FROM crown_war_focus WHERE war_id = ?", (int(war_id),))
    conn.commit()


def disengage_player(conn, attacker_id, now=None):
    """Drop this attacker's focus lock (frees a slot on their former target)."""
    war = current_war(conn)
    if not war or not attacker_id:
        return False, "No active war."
    _clear_attacker_focus(conn, war["id"], attacker_id)
    conn.commit()
    return True, "You break off the engagement."


def engage_player(conn, attacker_id, defender_id, now=None):
    """Claim a direct-damage focus slot on a defender (max SIEGE_MAX_ATTACKERS).

    Returns (ok, message). Re-engaging the same target refreshes the lock.
    Switching targets releases the previous defender slot.
    """
    now = time.time() if now is None else float(now)
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return False, "Focus fire only applies during the assault."
    if not attacker_id or not defender_id:
        return False, "Need both fighters."
    if int(attacker_id) == int(defender_id):
        return False, "You cannot engage yourself."
    if is_eliminated(conn, attacker_id, war["id"]):
        return False, "You are eliminated from this siege."
    if is_eliminated(conn, defender_id, war["id"]):
        return False, "That fighter is already eliminated."
    if not is_confirmed_fighter(conn, attacker_id, war["id"]):
        return False, "Only confirmed fighters may engage in the assault."
    if not is_confirmed_fighter(conn, defender_id, war["id"]):
        return False, "That player is not a confirmed fighter in this war."
    a_side = player_side(conn, attacker_id, war["id"])
    d_side = player_side(conn, defender_id, war["id"])
    if not a_side or not d_side:
        return False, "Both fighters must still be in the war."
    if a_side == d_side:
        return False, "You cannot focus-fire an ally."
    # Already holding this target — refresh timestamp.
    row = conn.execute(
        "SELECT defender_id FROM crown_war_focus WHERE war_id = ? AND attacker_id = ?",
        (war["id"], int(attacker_id)),
    ).fetchone()
    if row and int(row[0]) == int(defender_id):
        conn.execute(
            "UPDATE crown_war_focus SET engaged_at = ? "
            "WHERE war_id = ? AND attacker_id = ?",
            (now, war["id"], int(attacker_id)),
        )
        conn.commit()
        return True, "You keep pressure on your target."
    current = focus_attackers(conn, defender_id, war["id"])
    if int(attacker_id) not in current and len(current) >= SIEGE_MAX_ATTACKERS:
        return False, (
            f"Two fighters are already engaged with that target "
            f"(cap {SIEGE_MAX_ATTACKERS}). Wait for a slot to open."
        )
    _clear_attacker_focus(conn, war["id"], attacker_id)
    conn.execute(
        "INSERT INTO crown_war_focus (war_id, defender_id, attacker_id, engaged_at) "
        "VALUES (?, ?, ?, ?)",
        (war["id"], int(defender_id), int(attacker_id), now),
    )
    conn.commit()
    n = len(focus_attackers(conn, defender_id, war["id"]))
    return True, (
        f"You engage the target ({n}/{SIEGE_MAX_ATTACKERS} attackers on them)."
    )


def can_direct_damage(conn, attacker_id, defender_id):
    """True when this attacker may deal direct player damage to the defender.

    Outside an active siege, always allowed (normal world rules apply).
    During the assault, the attacker must hold a focus slot (max two per target).
    """
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return True, None
    if not is_confirmed_fighter(conn, attacker_id, war["id"]):
        return True, None  # non-siege participants use normal world rules
    if not is_confirmed_fighter(conn, defender_id, war["id"]):
        return True, None
    a_side = player_side(conn, attacker_id, war["id"])
    d_side = player_side(conn, defender_id, war["id"])
    if not a_side or not d_side or a_side == d_side:
        return False, "You cannot strike that fighter."
    if is_eliminated(conn, attacker_id, war["id"]) or is_eliminated(conn, defender_id, war["id"]):
        return False, "That bout is over."
    current = focus_attackers(conn, defender_id, war["id"])
    if int(attacker_id) in current:
        return True, None
    if len(current) >= SIEGE_MAX_ATTACKERS:
        return False, (
            f"Two fighters are already engaged with that target "
            f"(cap {SIEGE_MAX_ATTACKERS})."
        )
    # Auto-claim a free slot on the first successful strike attempt.
    ok, msg = engage_player(conn, attacker_id, defender_id)
    if not ok:
        return False, msg
    return True, None


def can_area_damage(conn, attacker_id, defender_id):
    """Area effects may hit players beyond the two-attacker lock, at reduced power.

    Returns (allowed, damage_multiplier, message).
    """
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return True, 1.0, None
    if not is_confirmed_fighter(conn, attacker_id, war["id"]):
        return True, 1.0, None
    if not is_confirmed_fighter(conn, defender_id, war["id"]):
        return True, 1.0, None
    a_side = player_side(conn, attacker_id, war["id"])
    d_side = player_side(conn, defender_id, war["id"])
    if not a_side or not d_side or a_side == d_side:
        return False, 0.0, "Friendly fire blocked."
    if is_eliminated(conn, defender_id, war["id"]):
        return False, 0.0, "Already eliminated."
    ok, _ = can_direct_damage(conn, attacker_id, defender_id)
    if ok:
        return True, 1.0, None
    # Beyond the two-attacker lock — splash still applies at half effect.
    return True, SIEGE_AREA_DAMAGE_MULT, (
        f"Area hit at {int(SIEGE_AREA_DAMAGE_MULT * 100)}% — "
        f"direct focus is capped at {SIEGE_MAX_ATTACKERS} attackers."
    )


def confirm(conn, player_id, now=None):
    """Confirm a reserved slot once enough fighters have confirmed attendance."""
    now = time.time() if now is None else float(now)
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can confirm the war slot."
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "You must lead a guild."
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    row = conn.execute(
        "SELECT id, side, status, confirm_deadline FROM crown_war_slots "
        "WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    if not row:
        return False, "Your guild has not registered for this war."
    slot_id, side, status, deadline = int(row[0]), row[1], row[2], row[3]
    if status == "confirmed":
        return False, "Your guild has already confirmed."
    if status != "reserved":
        return False, f"Your guild is {status}, not holding the reserved slot."
    if deadline is not None and now > float(deadline):
        tick_wars(conn, now)
        return False, "Your confirmation window has expired."
    humans = _alliance_humans(conn, war["id"], clan_id, side)
    mercs = _alliance_mercs(conn, war["id"], clan_id, side)
    ok_cap, cap_msg = roster_caps_ok(humans, mercs)
    if not ok_cap:
        return False, cap_msg
    conn.execute(
        "UPDATE crown_war_slots SET status = 'confirmed', confirmed_at = ?, human_count = ? "
        "WHERE id = ?",
        (now, humans, slot_id),
    )
    conn.commit()
    name = _clan_name(conn, clan_id)
    try:
        import politics
        politics.news(
            conn, "siege",
            f"{name} confirmed the {side} slot for the War for the Crown "
            f"with {humans} confirmed fighters.",
            now,
        )
    except Exception:
        pass
    tick_wars(conn, now)
    return True, (
        f"{name} confirmed the {side} slot with {humans} confirmed fighters"
        + (f" and {mercs} mercenaries." if mercs else ".")
        + " (Guild membership alone does not count — only /siege attend.)"
    )


def _clan_mercs(conn, clan_id):
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM clan_recruits WHERE clan_id = ? AND active = 1",
            (int(clan_id),),
        ).fetchone()
        return int(row[0] if row else 0)
    except Exception:
        return 0


def _alliance_mercs(conn, war_id, lead_clan_id, side):
    total = _clan_mercs(conn, lead_clan_id)
    rows = conn.execute(
        "SELECT ally_clan_id FROM crown_war_allies WHERE war_id = ? AND lead_clan_id = ? "
        "AND side = ? AND status = 'accepted'",
        (int(war_id), int(lead_clan_id), side),
    ).fetchall()
    for (ally,) in rows:
        total += _clan_mercs(conn, ally)
    return total


def roster_caps_ok(humans, mercs=0):
    """Milestone 8 roster rules: confirmed human min, side cap, 40% mercenary ceiling."""
    humans = max(0, int(humans))
    mercs = max(0, int(mercs))
    if humans < HUMAN_MIN:
        return False, (
            f"Need at least {HUMAN_MIN} confirmed fighters "
            f"(/siege enlist · /siege attend) across the lead guild and accepted allies "
            f"(you have {humans}). Guild membership alone does not count."
        )
    total = humans + mercs
    if total > SIDE_CAP:
        return False, f"A side may field at most {SIDE_CAP} fighters (you have {total})."
    if total > 0 and mercs / total > MERC_MAX_FRACTION + 1e-9:
        max_mercs = int(humans * MERC_MAX_FRACTION / (1.0 - MERC_MAX_FRACTION))
        return False, (
            f"Mercenaries may be at most {int(MERC_MAX_FRACTION * 100)}% of the side "
            f"(max {max_mercs} for {humans} humans; you have {mercs})."
        )
    return True, None


def forfeit(conn, player_id, now=None):
    """Give up a reserved or confirmed slot; next queued guild is promoted."""
    now = time.time() if now is None else float(now)
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can forfeit the war slot."
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "You must lead a guild."
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    if war.get("status") == "active":
        return False, "You cannot forfeit once the assault has begun."
    row = conn.execute(
        "SELECT id, side, status FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    if not row:
        return False, "Your guild is not registered for this war."
    slot_id, side, status = int(row[0]), row[1], row[2]
    if status not in ("reserved", "confirmed", "queued"):
        return False, f"Your guild is already {status}."
    was_lead = status in ("reserved", "confirmed")
    conn.execute(
        "UPDATE crown_war_slots SET status = 'forfeited' WHERE id = ?", (slot_id,)
    )
    # Drop pending ally invites from this lead.
    conn.execute(
        "UPDATE crown_war_allies SET status = 'declined', resolved_at = ? "
        "WHERE war_id = ? AND lead_clan_id = ? AND status = 'invited'",
        (now, war["id"], clan_id),
    )
    conn.commit()
    name = _clan_name(conn, clan_id)
    msg = f"{name} forfeited the {side} registration."
    if was_lead:
        promoted = _promote_next(conn, war["id"], side, now)
        if promoted:
            msg += f" {promoted['name']} now holds the slot."
        # Confirmed → back to registration if we lost a side.
        if war["status"] == "scheduled":
            conn.execute(
                "UPDATE crown_wars SET status = 'registration', scheduled_at = NULL WHERE id = ?",
                (war["id"],),
            )
            conn.commit()
    try:
        import politics
        politics.news(conn, "siege", msg, now)
    except Exception:
        pass
    return True, msg


def invite_ally(conn, player_id, guild_name, now=None):
    """Lead guild invites another guild into its attack/defend alliance."""
    now = time.time() if now is None else float(now)
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can invite war allies."
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "You must lead a guild."
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    if roster_locked(conn):
        return False, "Alliance invites are locked once the assault begins."
    row = conn.execute(
        "SELECT side, status FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    if not row or row[1] not in ("reserved", "confirmed"):
        return False, "Your guild must hold the reserved or confirmed slot to invite allies."
    side = row[0]
    target = _clan_by_name(conn, guild_name)
    if not target:
        return False, "No guild by that name."
    ally_id = int(target[0])
    if ally_id == int(clan_id):
        return False, "You cannot ally with yourself."
    if conn.execute(
        "SELECT 1 FROM crown_war_slots WHERE war_id = ? AND clan_id = ? AND status IN "
        "('queued', 'reserved', 'confirmed')",
        (war["id"], ally_id),
    ).fetchone():
        return False, "That guild is already registered for this war."
    existing = conn.execute(
        "SELECT status FROM crown_war_allies WHERE war_id = ? AND ally_clan_id = ?",
        (war["id"], ally_id),
    ).fetchone()
    if existing and existing[0] in ("invited", "accepted"):
        return False, f"That guild is already {existing[0]} for this war."
    if existing:
        conn.execute(
            "UPDATE crown_war_allies SET lead_clan_id = ?, side = ?, status = 'invited', "
            "invited_at = ?, resolved_at = NULL WHERE war_id = ? AND ally_clan_id = ?",
            (clan_id, side, now, war["id"], ally_id),
        )
    else:
        conn.execute(
            "INSERT INTO crown_war_allies (war_id, lead_clan_id, ally_clan_id, side, status, invited_at) "
            "VALUES (?, ?, ?, ?, 'invited', ?)",
            (war["id"], clan_id, ally_id, side, now),
        )
    conn.commit()
    return True, f"Invited {target[1]} to join your {side} alliance. Their Leader uses /siege accept."


def respond_ally(conn, player_id, accept=True, now=None):
    """Ally guild leader accepts or declines an invite."""
    now = time.time() if now is None else float(now)
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can answer a war alliance invite."
    clan_id = _clan_of(conn, player_id)
    if not clan_id:
        return False, "You must lead a guild."
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    if accept and roster_locked(conn):
        return False, "Alliance accepts are locked once the assault begins."
    row = conn.execute(
        "SELECT id, lead_clan_id, side FROM crown_war_allies "
        "WHERE war_id = ? AND ally_clan_id = ? AND status = 'invited'",
        (war["id"], clan_id),
    ).fetchone()
    if not row:
        return False, "Your guild has no pending war alliance invite."
    status = "accepted" if accept else "declined"
    conn.execute(
        "UPDATE crown_war_allies SET status = ?, resolved_at = ? WHERE id = ?",
        (status, now, int(row[0])),
    )
    conn.commit()
    lead = _clan_name(conn, row[1])
    if accept:
        return True, f"Your guild joins {lead}'s {row[2]} alliance for the War for the Crown."
    return True, f"Declined the alliance invite from {lead}."


def war_public(conn, war=None):
    war = war or current_war(conn)
    if not war:
        return None
    sides = {}
    for side in SIDES:
        lead = _lead_slot(conn, war["id"], side)
        queued = _slots(conn, war["id"], side=side, statuses=("queued",))
        allies = [a for a in _allies(conn, war["id"], side=side) if a["status"] == "accepted"]
        pending = [a for a in _allies(conn, war["id"], side=side) if a["status"] == "invited"]
        humans = 0
        mercs = 0
        if lead:
            humans = _alliance_humans(conn, war["id"], lead["clan_id"], side)
            mercs = _alliance_mercs(conn, war["id"], lead["clan_id"], side)
        stock = store_stock(conn, war["id"], lead["clan_id"]) if lead else None
        alloc = store_alloc(conn, war["id"], lead["clan_id"]) if lead else None
        spend = alloc_status(conn, war["id"], lead["clan_id"]) if lead else None
        sides[side] = {
            "lead": (
                {
                    "clan_id": lead["clan_id"],
                    "name": lead["name"],
                    "status": lead["status"],
                    "confirm_deadline": lead.get("confirm_deadline"),
                    "humans": humans,
                    "mercs": mercs,
                    "human_min": HUMAN_MIN,
                    "side_cap": SIDE_CAP,
                    "merc_max_fraction": MERC_MAX_FRACTION,
                }
                if lead else None
            ),
            "queue": [{"clan_id": q["clan_id"], "name": q["name"]} for q in queued],
            "allies": [{"clan_id": a["ally_clan_id"], "name": a["ally_name"]} for a in allies],
            "pending_allies": [
                {"clan_id": a["ally_clan_id"], "name": a["ally_name"], "lead_name": a["lead_name"]}
                for a in pending
            ],
            "store": stock,
            "alloc": alloc,
            "alloc_spend": spend,
        }
    return {
        "id": war["id"],
        "status": war["status"],
        "opened_at": war["opened_at"],
        "scheduled_at": war.get("scheduled_at"),
        "started_at": war.get("started_at"),
        "assault_at": assault_starts_at(war) if war.get("status") == "scheduled" else None,
        "assault_at_utc": (
            utc_stamp(assault_starts_at(war))
            if war.get("status") == "scheduled" and assault_starts_at(war) is not None
            else None
        ),
        "assault_delay": ASSAULT_DELAY,
        "assault_seconds": ASSAULT_SECONDS,
        "assault_window_min_h": ASSAULT_WINDOW_MIN_H,
        "assault_window_max_h": ASSAULT_WINDOW_MAX_H,
        "human_min": effective_human_min(war),
        "human_min_full": HUMAN_MIN,
        "human_min_small": SMALL_SCALE_HUMAN_MIN,
        "scale": war.get("scale") or "full",
        "postpones": int(war.get("postpones") or 0),
        "confirm_hours": CONFIRM_SECONDS // HOUR,
        "sides": sides,
        "contributors": contrib_board(conn, war["id"], limit=5),
        "captures": capture_state(conn, war["id"]) if war["status"] in ("active", "scheduled") else [],
    }


def war_lines(conn, now=None):
    """Chat / Herald lines describing the open war."""
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        last = _last_closed(conn)
        if last is not None and (now - last) < SIEGE_COOLDOWN:
            days = int((SIEGE_COOLDOWN - (now - last) + DAY - 1) // DAY)
            return [f"No War for the Crown is open. Next window in about {days} day(s)."]
        return [
            "No War for the Crown is open. A guild Leader may /siege register attack|defend "
            "to open registration."
        ]
    pub = war_public(conn, war)
    lines = [
        f"War for the Crown — {war['status']} "
        f"(confirm window {CONFIRM_SECONDS // HOUR}h, {HUMAN_MIN}+ humans)."
    ]
    for side in SIDES:
        info = pub["sides"][side]
        lead = info["lead"]
        if not lead:
            lines.append(f"{side.title()}: open — guild priority: first eligible application reserves the slot.")
            continue
        rem = ""
        if lead["status"] == "reserved" and lead.get("confirm_deadline"):
            left = max(0, int(lead["confirm_deadline"] - now))
            rem = f", {left // HOUR}h {(left % HOUR) // 60}m left to confirm"
        mercs = int(lead.get("mercs") or 0)
        merc_bit = f", {mercs} mercs" if mercs else ""
        lines.append(
            f"{side.title()}: {lead['name']} ({lead['status']}, "
            f"{lead['humans']}/{HUMAN_MIN} humans{merc_bit}{rem})"
        )
        if info["allies"]:
            lines.append("  Allies: " + ", ".join(a["name"] for a in info["allies"]))
        if info["queue"]:
            lines.append("  Queue: " + ", ".join(q["name"] for q in info["queue"]))
    return lines


HERALD_SIEGE_OPTIONS = [
    {"id": "siege_guide", "label": "How the War for the Crown works"},
    {"id": "siege_status", "label": "War for the Crown"},
    {"id": "siege_register_attack", "label": "Register to attack"},
    {"id": "siege_register_defend", "label": "Register to defend"},
    {"id": "siege_confirm", "label": "Confirm our war slot"},
    {"id": "siege_store", "label": "War storehouse"},
    {"id": "siege_costs", "label": "Siege resource costs"},
    {"id": "siege_scout", "label": "Survey damage (Engineering)"},
    {"id": "siege_survey", "label": "Engineering survey"},
    {"id": "siege_royalguard", "label": "Royal Guard"},
    {"id": "siege_report", "label": "Battle report"},
]


def utc_stamp(ts):
    """Design: clearly published start time for different time zones."""
    if ts is None:
        return None
    return (
        datetime.fromtimestamp(float(ts), tz=timezone.utc)
        .strftime("%Y-%m-%d %H:%M UTC")
    )


# ---- milestone 4: weapons + path breaches ------------------------------------
def invalidate_breaches():
    global _BREACH_CACHE, _BREACH_STATES
    _BREACH_CACHE = None
    _BREACH_STATES = None


def _king_walk_rows():
    import json
    from pathlib import Path
    path = (
        Path(__file__).resolve().parent.parent
        / "client" / "assets" / "castle_realm" / "json" / "king_castle.json"
    )
    blob = json.loads(path.read_text(encoding="utf-8"))
    fp = blob.get("footprint") or {}
    return blob.get("walkability") or [], int(fp.get("x0", 0)), int(fp.get("y0", 0))


def _tiles_near(ax, ay, chars, radius):
    rows, x0, y0 = _king_walk_rows()
    out = []
    for ly, row in enumerate(rows):
        for lx, ch in enumerate(row):
            if ch not in chars:
                continue
            wx, wy = x0 + lx, y0 + ly
            if abs(wx - ax) + abs(wy - ay) <= radius:
                out.append((wx, wy))
    return out


def structure_breach_tiles(structure_id):
    """World tiles that open when this structure is destroyed."""
    spec = _BY_ID.get(structure_id)
    if not spec:
        return ()
    ax, ay = spec["anchor"]
    if structure_id == "outer_gate":
        # Flanking wall stones beside the portcullis become a rubble breach.
        return tuple(_tiles_near(ax, ay, "W", 5))
    if structure_id in ("west_wall", "east_wall"):
        return tuple(_tiles_near(ax, ay, "W", 3))
    return ()


def breach_tile_set(conn=None):
    """All currently open breach tiles from destroyed gate/walls."""
    global _BREACH_CACHE, _BREACH_STATES
    states = {}
    if conn is None:
        conn = _CONN
    if conn is None:
        try:
            import server as srv
            conn = srv.WORLD.db.conn
        except Exception:
            return _BREACH_CACHE or frozenset()
    for sid in ("outer_gate", "west_wall", "east_wall"):
        s = get_structure(conn, sid)
        states[sid] = s["state"] if s else "intact"
    if _BREACH_CACHE is not None and states == _BREACH_STATES:
        return _BREACH_CACHE
    tiles = set()
    for sid, st in states.items():
        if st == "destroyed":
            tiles.update(structure_breach_tiles(sid))
    _BREACH_CACHE = frozenset(tiles)
    _BREACH_STATES = dict(states)
    return _BREACH_CACHE


def is_breach_tile(x, y, conn=None):
    return (int(x), int(y)) in breach_tile_set(conn)


def _player_skill_level(conn, player_id, skill):
    """Combat-style level from the player's stored XP column (1 if unknown)."""
    col = f"{skill}_xp"
    try:
        row = conn.execute(
            f"SELECT COALESCE({col}, 0) FROM players WHERE id = ?",
            (int(player_id),),
        ).fetchone()
    except Exception:
        return 1
    xp = int(row[0] if row else 0)
    try:
        from combat import level_from_xp
        return max(1, int(level_from_xp(xp)))
    except Exception:
        return 1


def _skill_bonus_mult(level):
    """Level 1 → 1.00×, roughly +0.5% per level, cap +50%."""
    level = max(1, int(level or 1))
    bonus = min(0.50, max(0.0, (level - 1.0) * 0.005))
    return 1.0 + bonus


def siege_skill_mult(conn, player_id):
    """Engineering operates engines, repairs and barricades (design: not Construction).

    Smithing still helps slightly with mechanisms; Engineering is the primary skill.
    """
    if not player_id:
        return 1.0
    eng = _player_skill_level(conn, player_id, "engineering")
    smith = _player_skill_level(conn, player_id, "smithing")
    blended = eng * 0.75 + smith * 0.25
    return _skill_bonus_mult(blended)


def _grant_engineering_xp(conn, player_id, amount):
    """Award Engineering XP for siege craft / repair / deploy work."""
    amount = max(0, int(amount or 0))
    if not player_id or amount <= 0:
        return 0
    try:
        conn.execute(
            "UPDATE players SET engineering_xp = COALESCE(engineering_xp, 0) + ? WHERE id = ?",
            (amount, int(player_id)),
        )
        conn.commit()
        return amount
    except Exception:
        return 0


def deposit_skill_mult(conn, player_id, resource):
    """Gatherer / smith skill boosts storehouse contribution (design material table).

    Timber ← Woodcutting; ore/stone ← Mining; bars ← Smithing.
    Players who dislike large-scale PvP still earn war contribution by supplying.
    """
    if not player_id or resource not in STORE_RESOURCES:
        return 1.0
    if resource == "timber":
        skill = "woodcutting"
    elif resource in ("ore", "stone"):
        skill = "mining"
    else:  # bars
        skill = "smithing"
    return _skill_bonus_mult(_player_skill_level(conn, player_id, skill))


def _side_operator(conn, player_id):
    """Any registered/allied fighter may craft, fire, repair, or deploy for their side.

    Design: smiths craft, repair crews mend walls, warriors fight — contribution is
    not limited to the lead Leader. Allocation % stays a Leader decision.
    """
    war = current_war(conn)
    if not war:
        return None, None, "No War for the Crown is open."
    blocked = action_blocked(conn, player_id)
    if blocked:
        return war, None, blocked
    clan_id = _clan_of(conn, player_id)
    side, lead_id = _player_war_side(conn, war["id"], clan_id)
    if not side or not lead_id:
        return war, None, "Your guild is not fighting in this war."
    return war, lead_id, None


def _lead_for_player(conn, player_id):
    """Leader-only path (kept for callers that still need the lead Leader)."""
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return war, lead_id, err
    clan_id = _clan_of(conn, player_id)
    if int(clan_id) != int(lead_id) or not _is_leader(conn, player_id):
        return war, lead_id, "Only the lead guild's Leader can do that."
    return war, lead_id, None


def weapon_stock(conn, war_id, clan_id):
    rows = conn.execute(
        "SELECT weapon_id, qty FROM crown_war_weapons WHERE war_id = ? AND clan_id = ?",
        (int(war_id), int(clan_id)),
    ).fetchall()
    out = {wid: 0 for wid in WEAPONS}
    for wid, qty in rows:
        out[str(wid)] = int(qty)
    return out


def store_deposited(conn, war_id, clan_id):
    """Lifetime materials ever deposited into this side's war storehouse."""
    _ensure_alloc(conn, war_id, clan_id)
    rows = conn.execute(
        "SELECT resource, COALESCE(deposited, 0) FROM crown_war_store "
        "WHERE war_id = ? AND clan_id = ?",
        (int(war_id), int(clan_id)),
    ).fetchall()
    out = {r: 0 for r in STORE_RESOURCES}
    for res, qty in rows:
        out[str(res)] = int(qty)
    return out


def store_spent(conn, war_id, clan_id, bucket):
    """Materials already spent from one allocation bucket."""
    rows = conn.execute(
        "SELECT resource, qty FROM crown_war_spent "
        "WHERE war_id = ? AND clan_id = ? AND bucket = ?",
        (int(war_id), int(clan_id), str(bucket)),
    ).fetchall()
    out = {r: 0 for r in STORE_RESOURCES}
    for res, qty in rows:
        out[str(res)] = int(qty)
    return out


def alloc_budget(conn, war_id, clan_id, bucket):
    """Max materials this bucket may spend, from deposited totals × allocation %."""
    alloc = store_alloc(conn, war_id, clan_id)
    pct = int(alloc.get(bucket) or 0)
    deposited = store_deposited(conn, war_id, clan_id)
    return {res: (int(deposited.get(res, 0)) * pct) // 100 for res in STORE_RESOURCES}


def alloc_status(conn, war_id, clan_id):
    """Per-bucket budget / spent / left for the leader board (both sides can see)."""
    alloc = store_alloc(conn, war_id, clan_id)
    out = {}
    for bucket in ALLOC_BUCKETS:
        budget = alloc_budget(conn, war_id, clan_id, bucket)
        spent = store_spent(conn, war_id, clan_id, bucket)
        resources = {}
        for res in STORE_RESOURCES:
            b = int(budget.get(res, 0))
            s = int(spent.get(res, 0))
            resources[res] = {"budget": b, "spent": s, "left": max(0, b - s)}
        out[bucket] = {"pct": int(alloc.get(bucket) or 0), "resources": resources}
    return out


def _alloc_board_bits(conn, war_id, clan_id):
    """Compact timber remaining per bucket — the bottleneck for most crafts."""
    status = alloc_status(conn, war_id, clan_id)
    bits = []
    for bucket in ALLOC_BUCKETS:
        t = status[bucket]["resources"]["timber"]
        bits.append(f"{bucket} {t['spent']}/{t['budget']}t")
    return bits


def _check_alloc_budget(conn, war_id, clan_id, bucket, cost):
    """True if spending ``cost`` still fits the leader's allocation for ``bucket``."""
    if bucket not in ALLOC_BUCKETS:
        return False, f"Unknown allocation bucket {bucket}."
    budget = alloc_budget(conn, war_id, clan_id, bucket)
    spent = store_spent(conn, war_id, clan_id, bucket)
    alloc = store_alloc(conn, war_id, clan_id)
    for res, need in cost.items():
        need = int(need)
        if need <= 0:
            continue
        room = int(budget.get(res, 0)) - int(spent.get(res, 0))
        if need > room:
            return False, (
                f"{bucket} allocation is {alloc.get(bucket, 0)}% of deposited {res} "
                f"(budget {budget.get(res, 0)}, spent {spent.get(res, 0)}; need {need} more). "
                f"/siege alloc to rebalance before the assault."
            )
    return True, None


def _record_spent(conn, war_id, clan_id, bucket, cost):
    for res, need in cost.items():
        need = int(need)
        if need <= 0:
            continue
        conn.execute(
            "INSERT INTO crown_war_spent (war_id, clan_id, bucket, resource, qty) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(war_id, clan_id, bucket, resource) DO UPDATE SET "
            "qty = qty + excluded.qty",
            (int(war_id), int(clan_id), str(bucket), str(res), need),
        )


def _spend_store(conn, war_id, clan_id, cost, bucket=None):
    stock = store_stock(conn, war_id, clan_id)
    for res, need in cost.items():
        if stock.get(res, 0) < int(need):
            return False, f"Need {need} {res} (have {stock.get(res, 0)})."
    if bucket is not None:
        ok, msg = _check_alloc_budget(conn, war_id, clan_id, bucket, cost)
        if not ok:
            return False, msg
    for res, need in cost.items():
        conn.execute(
            "UPDATE crown_war_store SET qty = qty - ? WHERE war_id = ? AND clan_id = ? AND resource = ?",
            (int(need), int(war_id), int(clan_id), res),
        )
    if bucket is not None:
        _record_spent(conn, war_id, clan_id, bucket, cost)
    conn.commit()
    return True, None


def craft_weapon(conn, player_id, weapon_id, qty=1, now=None):
    """Spend storehouse materials to build siege engines for the side's lead stock."""
    now = time.time() if now is None else float(now)
    weapon_id = str(weapon_id or "").lower().strip()
    qty = max(1, int(qty or 1))
    spec = WEAPONS.get(weapon_id)
    if not spec:
        return False, f"Unknown weapon. Choose: {', '.join(WEAPONS)}."
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err
    cost = {k: v * qty for k, v in spec["cost"].items()}
    side = player_side(conn, player_id, war["id"])
    armoury_gone = _structure_destroyed(conn, "armoury")
    # Destroyed armoury weakens defender resupply — craft costs double for them.
    if side == "defend" and armoury_gone:
        cost = {k: v * 2 for k, v in cost.items()}
    bucket = spec.get("alloc")
    ok, msg = _spend_store(conn, war["id"], lead_id, cost, bucket=bucket)
    if not ok:
        if side == "defend" and armoury_gone and "allocation" not in (msg or "").lower():
            return False, msg + " (armoury destroyed — craft costs double)."
        return False, msg
    conn.execute(
        "INSERT INTO crown_war_weapons (war_id, clan_id, weapon_id, qty) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(war_id, clan_id, weapon_id) DO UPDATE SET qty = qty + excluded.qty",
        (war["id"], lead_id, weapon_id, qty),
    )
    conn.commit()
    have = weapon_stock(conn, war["id"], lead_id)[weapon_id]
    # Engineering (and a little Smithing) improves craft contribution.
    mult = siege_skill_mult(conn, player_id)
    craft_pts = max(1, int(round(2 * qty * mult)))
    _credit_points(conn, war["id"], player_id, craft_pts)
    eng_xp = _grant_engineering_xp(conn, player_id, max(8, 6 * qty))
    note = (
        f"Crafted {qty}× {spec['name']} (spent "
        + ", ".join(f"{v} {k}" for k, v in cost.items())
        + f"). Ready: {have}. (+{craft_pts} contrib"
        + (f", +{eng_xp} Engineering XP" if eng_xp else "")
        + ")"
    )
    if mult > 1.0:
        note += f" [Engineering ×{mult:.2f}]"
    if side == "defend" and armoury_gone:
        note += " Armoury destroyed — paid double."
    return True, note


def fire_weapon(conn, player_id, weapon_id, structure_id, now=None):
    """Consume one crafted weapon and apply_damage to a valid target.

    Returns (ok, message, sync_meta_or_None).
    """
    now = time.time() if now is None else float(now)
    weapon_id = str(weapon_id or "").lower().strip()
    structure_id = str(structure_id or "").strip()
    spec = WEAPONS.get(weapon_id)
    if not spec:
        return False, f"Unknown weapon. Choose: {', '.join(WEAPONS)}.", None
    if weapon_id == "barricade":
        return False, "Barricades are deployed with /siege barricade <point>, not fired.", None
    if structure_id not in spec["targets"]:
        return False, f"{spec['name']} can hit: {', '.join(spec['targets'])}.", None
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err, None
    if war.get("status") == "active" and not is_confirmed_fighter(conn, player_id, war["id"]):
        return False, "Only confirmed fighters may operate siege engines in the assault.", None
    # Any confirmed side fighter may operate a crafted engine from the shared stock.
    row = conn.execute(
        "SELECT qty FROM crown_war_weapons WHERE war_id = ? AND clan_id = ? AND weapon_id = ?",
        (war["id"], lead_id, weapon_id),
    ).fetchone()
    if not row or int(row[0]) < 1:
        return False, f"No {spec['name']} ready. /siege craft {weapon_id} first.", None
    conn.execute(
        "UPDATE crown_war_weapons SET qty = qty - 1 WHERE war_id = ? AND clan_id = ? AND weapon_id = ?",
        (war["id"], lead_id, weapon_id),
    )
    conn.commit()
    before = get_structure(conn, structure_id)
    mult = siege_skill_mult(conn, player_id)
    dmg = max(1, int(round(int(spec["damage"]) * mult)))
    updated = apply_damage(conn, structure_id, dmg, now=now)
    if not updated:
        return False, "Unknown structure.", None
    pts = int(spec.get("contrib") or 0)
    if pts:
        pts = max(1, int(round(pts * mult)))
        _credit_points(conn, war["id"], player_id, pts)
    eng_xp = _grant_engineering_xp(conn, player_id, 10)
    extras = []
    if pts:
        extras.append(f"+{pts} contrib")
    if eng_xp:
        extras.append(f"+{eng_xp} Engineering XP")
    note = (
        f"{spec['name']} strikes the {updated['name']} for {dmg} damage "
        f"({updated['hp']}/{updated['max_hp']}, {updated['state']})"
        + (f" ({', '.join(extras)})." if extras else ".")
    )
    if mult > 1.0:
        note += f" [Engineering ×{mult:.2f}]"
    # Design: banners burn, siege towers catch fire as the castle is pressed.
    if weapon_id == "tower":
        note += " The siege tower catches fire as it presses the walls!"
    elif updated["state"] in ("heavily_damaged", "destroyed") and (
        not before or before.get("state") not in ("heavily_damaged", "destroyed")
    ):
        note += " Banners burn amid the fire and debris."
    breached = bool(before and before["state"] != "destroyed" and updated["state"] == "destroyed")
    if breached:
        note += " " + destruction_presentation(structure_id, updated)
        try:
            import politics
            politics.news(conn, "siege", note, now)
        except Exception:
            pass
    return True, note, {"structure": updated, "breached": breached, "sync": True}


# Repair costs per 500 HP restored (defenders spend storehouse stock).
REPAIR_BATCH_HP = 500
REPAIR_COST = {"timber": 8, "stone": 12, "bars": 2}


def repair_structure(conn, player_id, structure_id, batches=1, now=None):
    """Defending lead spends storehouse materials to restore structure HP."""
    now = time.time() if now is None else float(now)
    structure_id = str(structure_id or "").strip()
    batches = max(1, min(20, int(batches or 1)))
    if structure_id not in _BY_ID:
        return False, "Unknown structure.", None
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err, None
    side = player_side(conn, player_id, war["id"])
    if side != "defend":
        return False, "Only defenders can repair castle structures.", None
    before = get_structure(conn, structure_id)
    if not before:
        return False, "Unknown structure.", None
    if before["hp"] >= before["max_hp"]:
        return False, f"{before['name']} is already intact.", None
    cost = {k: v * batches for k, v in REPAIR_COST.items()}
    depot = get_structure(conn, "supply_depot")
    depot_gone = bool(depot and depot["state"] == "destroyed")
    if depot_gone:
        # Destroyed depot: repairs cost twice as much material.
        cost = {k: v * 2 for k, v in cost.items()}
    # Defenders spend the reserve allocation on repairs.
    ok, msg = _spend_store(conn, war["id"], lead_id, cost, bucket="reserve")
    if not ok:
        if depot_gone and "allocation" not in (msg or "").lower():
            return False, msg + " (supply depot destroyed — repairs cost double).", None
        return False, msg, None
    mult = siege_skill_mult(conn, player_id)
    amount = max(1, int(round(REPAIR_BATCH_HP * batches * mult)))
    updated = repair(conn, structure_id, amount, now=now)
    if before["state"] == "destroyed" and updated and updated["state"] != "destroyed":
        invalidate_breaches()
        try:
            import castle_realm
            castle_realm.build_plane.cache_clear()
        except Exception:
            pass
    pts = max(1, int(round(REPAIR_CONTRIB_PER_BATCH * batches * mult)))
    _credit_points(conn, war["id"], player_id, pts)
    eng_xp = _grant_engineering_xp(conn, player_id, max(6, 5 * batches))
    note = (
        f"Repaired the {updated['name']} by {amount} HP "
        f"({updated['hp']}/{updated['max_hp']}, {updated['state']}) "
        f"(+{pts} contrib"
        + (f", +{eng_xp} Engineering XP" if eng_xp else "")
        + ")."
    )
    if mult > 1.0:
        note += f" [Engineering ×{mult:.2f}]"
    return True, note, {"structure": updated, "breached": False, "sync": True}


def structure_sync(conn):
    """Payload for SIEGE_UPDATE — structures, open breaches, war, heraldry."""
    invalidate_breaches()  # refresh from DB before read
    structs = {}
    for s in list_structures(conn):
        if not s:
            continue
        structs[s["id"]] = {
            "name": s["name"],
            "hp": s["hp"],
            "max_hp": s["max_hp"],
            "state": s["state"],
            "plane": s["plane"],
            "anchor": list(s["anchor"]),
        }
    breaches = [list(t) for t in sorted(breach_tile_set(conn))]
    war = current_war(conn)
    return {
        "structures": structs,
        "breaches": breaches,
        "war": war_public(conn, war) if war else None,
        "heraldry": castle_heraldry(conn),
    }


def _ensure_captures(conn, war_id, now):
    """Make sure capture rows exist without wiping fortifications mid-prep."""
    for point_id in CAPTURE_POINTS:
        conn.execute(
            "INSERT OR IGNORE INTO crown_war_captures "
            "(war_id, point_id, owner, progress, hold_started_at, updated_at) "
            "VALUES (?, ?, 'defend', 0, NULL, ?)",
            (int(war_id), point_id, now),
        )
    conn.commit()


def _init_captures(conn, war_id, now):
    """Reset capture ownership for a fresh assault; keep prep fortifications."""
    _ensure_captures(conn, war_id, now)
    conn.execute(
        "UPDATE crown_war_captures SET owner = 'defend', progress = 0, hold_started_at = NULL "
        "WHERE war_id = ?",
        (int(war_id),),
    )
    conn.commit()


def _activate_assault(conn, war_id, now):
    """Flip a confirmed war to active and seed capture points. Returns notice text."""
    ready, why = _sides_meet_human_min(conn, war_id)
    if not ready:
        raise ValueError(f"Assault cannot begin — {why}.")
    # Fresh war: castle starts intact so prior damage does not leak.
    reset_all(conn, now)
    invalidate_breaches()
    try:
        import castle_realm
        castle_realm.build_plane.cache_clear()
    except Exception:
        pass
    conn.execute(
        "UPDATE crown_wars SET status = 'active', "
        "scheduled_at = COALESCE(scheduled_at, ?), started_at = ? WHERE id = ?",
        (now, now, int(war_id)),
    )
    conn.commit()
    _init_captures(conn, int(war_id), now)
    hours = ASSAULT_SECONDS // HOUR
    try:
        import politics
        politics.news(
            conn, "siege",
            f"The assault on Crownfall Castle has begun! Defenders win if the "
            f"throne is not held within {hours} hour(s).",
            now,
        )
    except Exception:
        pass
    return (
        f"The assault on Crownfall Castle has begun! "
        f"Hold the Throne Room within {hours} hour(s), or the defenders keep the crown."
    )


def begin_assault(conn, player_id=None, now=None):
    """Move a confirmed war into the active assault.

    Design: the attacking alliance opens the coordinated window early with
    /siege begin, or waits for the scheduled auto-start.
    """
    now = time.time() if now is None else float(now)
    before = current_war(conn)
    before_status = before["status"] if before else None
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    if war["status"] == "active":
        # tick_wars may have just auto-started after ASSAULT_DELAY.
        if before_status == "scheduled":
            return True, "The assault on Crownfall Castle has begun!"
        return False, "The assault is already underway."
    atk = _lead_slot(conn, war["id"], "attack")
    dfn = _lead_slot(conn, war["id"], "defend")
    if not (atk and atk["status"] == "confirmed" and dfn and dfn["status"] == "confirmed"):
        return False, "Both sides must confirm before the assault begins."
    if player_id is not None and not _is_attack_lead_leader(conn, player_id, war):
        return False, "Only the attacking alliance Leader can open the assault."
    ready, why = _sides_meet_human_min(conn, war["id"], HUMAN_MIN)
    if not ready:
        # After a postpone, Leaders may open a smaller-scale assault.
        if int(war.get("postpones") or 0) >= 1:
            ready_small, why_small = _sides_meet_human_min(
                conn, war["id"], SMALL_SCALE_HUMAN_MIN,
            )
            if not ready_small:
                return False, f"Assault cannot begin — {why_small}."
            conn.execute(
                "UPDATE crown_wars SET scale = 'small' WHERE id = ?",
                (war["id"],),
            )
            conn.commit()
        else:
            return False, f"Assault cannot begin — {why}."
    try:
        msg = _activate_assault(conn, war["id"], now)
        if str((current_war(conn) or {}).get("scale") or "") == "small":
            msg = (
                f"Assault begins at a smaller scale "
                f"({SMALL_SCALE_HUMAN_MIN}+ humans per side). {msg}"
            )
        return True, msg
    except ValueError as exc:
        return False, str(exc)


def set_assault_window(conn, player_id, hours, now=None):
    """Attacking lead Leader picks when the assault begins (coordinated window).

    ``hours`` is delay from now until the assault auto-starts. Bounds match
    design prep ("several days") via ASSAULT_WINDOW_MIN_H / ASSAULT_WINDOW_MAX_H.
    """
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    if war["status"] != "scheduled":
        if war["status"] == "active":
            return False, "The assault is already underway."
        return False, "Both sides must confirm before the assault window can be set."
    if not _is_attack_lead_leader(conn, player_id, war):
        return False, "Only the attacking alliance Leader can set the assault window."
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        return False, (
            f"Usage: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h"
        )
    if hours < ASSAULT_WINDOW_MIN_H or hours > ASSAULT_WINDOW_MAX_H:
        return False, (
            f"Assault window must be {ASSAULT_WINDOW_MIN_H}–{ASSAULT_WINDOW_MAX_H} "
            f"hours from now (several days to prepare)."
        )
    # scheduled_at + ASSAULT_DELAY is the auto-start instant.
    scheduled_at = now + hours * HOUR - ASSAULT_DELAY
    conn.execute(
        "UPDATE crown_wars SET scheduled_at = ? WHERE id = ?",
        (scheduled_at, war["id"]),
    )
    conn.commit()
    start_at = now + hours * HOUR
    msg = (
        f"Assault window set — the attack begins in {hours} hour(s) "
        f"({utc_stamp(start_at)}). Defenders, finish preparations."
    )
    try:
        import politics
        politics.news(conn, "siege", msg, now)
    except Exception:
        pass
    return True, msg


def capture_state(conn, war_id=None):
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war:
        return []
    try:
        rows = conn.execute(
            "SELECT point_id, owner, progress, hold_started_at, updated_at, "
            "COALESCE(barricades, 0), COALESCE(guards, 0) "
            "FROM crown_war_captures WHERE war_id = ?",
            (int(war["id"]),),
        ).fetchall()
    except Exception:
        rows = conn.execute(
            "SELECT point_id, owner, progress, hold_started_at, updated_at, 0, 0 "
            "FROM crown_war_captures WHERE war_id = ?",
            (int(war["id"]),),
        ).fetchall()
    by_id = {r[0]: r for r in rows}
    out = []
    for pid, spec in CAPTURE_POINTS.items():
        row = by_id.get(pid)
        out.append({
            "id": pid,
            "name": spec["name"],
            "plane": spec["plane"],
            "rect": list(spec["rect"]),
            "owner": row[1] if row else "none",
            "progress": int(row[2]) if row else 0,
            "need": _capture_need(conn, spec),
            "hold_started_at": float(row[3]) if row and row[3] is not None else None,
            "hold_seconds": int(spec.get("hold_seconds") or 0),
            "barricades": int(row[5]) if row else 0,
            "guards": int(row[6]) if row and len(row) > 6 else 0,
            "unlocked_for_attack": _capture_unlocked(conn, war["id"], pid),
        })
    return out


def capture_board_lines(conn, war_id=None):
    """Compact territory lines for the public war progress board.

    Design: five-stage siege — Stages 1–4 are capture points; Stage 5 is Crownfall.
    """
    points = capture_state(conn, war_id)
    if not points:
        return []
    by_id = {p["id"]: p for p in points}
    lines = [
        "Territory — Stages 1–4 (attack order); Stage 5 is Crownfall:",
    ]
    # Design Stage 1: capture supply depots, destroy barricades, take outer settlement.
    outer = by_id.get("outer_yard")
    gate = by_id.get("gatehouse")
    court = by_id.get("courtyard")
    if outer and outer.get("owner") != "attack":
        depot = get_structure(conn, "supply_depot")
        depot_bit = (
            "Supply Depot already rubble (repairs cost double)."
            if depot and depot.get("state") == "destroyed"
            else "Press the Supply Depot to cut defender repair capacity."
        )
        lines.append(
            "Stage 1 focus: take the Outer Yard, clear barricades/guards, "
            f"and capture supply depots — {depot_bit}"
        )
    # Design Stage 2: siege engines hit gates/towers/walls; repair crews slow the assault.
    elif gate and gate.get("owner") != "attack":
        if walls_breached(conn):
            breach_bit = "Breach open — take the Gatehouse."
        else:
            breach_bit = (
                "Fire rams, ladders, and siege towers at the Outer Gate and walls "
                "until a breach opens the Gatehouse."
            )
        tower = get_structure(conn, "watchtower")
        tower_bit = (
            "Watchtower down (battlefield opens)."
            if tower and tower.get("state") == "destroyed"
            else "Drop the Watchtower to open interest and ease realm captures."
        )
        lines.append(
            f"Stage 2 focus: breach the walls — {breach_bit} "
            f"Repair crews can still slow the assault. {tower_bit}"
        )
    # Design Stage 3: control points inside; defenders regroup; territory contest.
    elif court and court.get("owner") != "attack":
        lines.append(
            "Stage 3 focus: capture the Courtyard — establish control inside the castle. "
            "Defenders may regroup at fallback positions; the battle is a territory contest."
        )
    # Design Stage 4: break royal guard; defenders' final opportunity to hold.
    throne = by_id.get("throne")
    if throne and throne.get("unlocked_for_attack"):
        wid = war_id
        if wid is None:
            war = current_war(conn)
            wid = war["id"] if war else None
        appt = list_royal_guard_players(conn, wid) if wid is not None else []
        appt_bit = (
            f" Appointed Royal Guard: {', '.join(g['name'] for g in appt)}."
            if appt else ""
        )
        if throne.get("owner") == "attack" and throne.get("hold_started_at"):
            lines.append(
                "Stage 4 — Last Stand: attackers hold the throne chamber — "
                "defenders' final opportunity to retake it before Crownfall."
                + appt_bit
            )
            # Design Stage 5: winning alliance claims the castle; coronation to the realm.
            lines.append(
                "Stage 5 — Crownfall imminent: the winning alliance claims the castle. "
                "A coronation will announce the new ruler to the entire realm."
            )
        elif throne.get("guards") or appt:
            lines.append(
                "Stage 4 — Last Stand: break through the royal guard and secure "
                "the throne chamber. Defenders get a final opportunity to hold."
                + appt_bit
            )
        else:
            lines.append(
                "Stage 4 — Last Stand: secure the throne chamber. "
                "Defenders get a final opportunity to hold the castle."
            )
    for p in points:
        bits = [f"{p['progress']}/{p['need']}"]
        if p.get("guards"):
            bits.append(f"guards {p['guards']}")
        if p.get("barricades"):
            bits.append(f"barricades {p['barricades']}")
        if p["id"] == "throne" and p.get("owner") == "attack" and p.get("hold_started_at"):
            held = max(0, int(time.time() - float(p["hold_started_at"])))
            bits.append(f"holding {held}s/{p.get('hold_seconds') or THRONE_HOLD_SECONDS}s")
        if not p.get("unlocked_for_attack"):
            bits.append("locked")
        stage = CAPTURE_STAGES.get(p["id"])
        if stage:
            num, title = stage
            label = f"Stage {num} — {p['name']} ({title})"
        else:
            label = p["name"]
        lines.append(
            f"  {label}: {p.get('owner') or 'defend'} ({', '.join(bits)})"
        )
    return lines


def _capture_owner(conn, war_id, point_id):
    row = conn.execute(
        "SELECT owner FROM crown_war_captures WHERE war_id = ? AND point_id = ?",
        (int(war_id), point_id),
    ).fetchone()
    return row[0] if row else "defend"


def _structure_destroyed(conn, structure_id):
    row = get_structure(conn, structure_id)
    return bool(row and row["state"] == "destroyed")


def walls_breached(conn):
    """True when a gate or wall section is rubble (stage 2 path is open)."""
    return any(_structure_destroyed(conn, sid) for sid in BREACH_STRUCTURES)


def effective_interest_radius(conn):
    """Watchtower intact keeps a tight interest ring; destroyed opens the field."""
    if _structure_destroyed(conn, "watchtower"):
        return INTEREST_RADIUS_BREACHED
    return INTEREST_RADIUS


def _capture_need(conn, spec):
    """Realm points cost double while the watchtower still stands (archer cover)."""
    need = int(spec["capture_need"])
    if spec.get("plane") == "realm" and not _structure_destroyed(conn, "watchtower"):
        return need * 2
    return need


def _add_point_fortification(conn, war_id, point_id, *, barricades=0, guards=0, now=None):
    """Bump fortification HP on a capture point (rows must already exist)."""
    now = time.time() if now is None else float(now)
    if point_id not in CAPTURE_POINTS:
        return
    if barricades:
        conn.execute(
            "UPDATE crown_war_captures SET barricades = COALESCE(barricades, 0) + ?, "
            "updated_at = ? WHERE war_id = ? AND point_id = ?",
            (int(barricades), now, int(war_id), point_id),
        )
    if guards:
        conn.execute(
            "UPDATE crown_war_captures SET guards = COALESCE(guards, 0) + ?, "
            "updated_at = ? WHERE war_id = ? AND point_id = ?",
            (int(guards), now, int(war_id), point_id),
        )


def _fallback_fortify(conn, war_id, fallen_point_id, now=None):
    """When attackers take a stage, defenders regroup at the next point.

    Design: 'Defenders can regroup at fallback positions.'
    """
    now = time.time() if now is None else float(now)
    try:
        idx = CAPTURE_ORDER.index(fallen_point_id)
    except ValueError:
        return None
    if idx + 1 >= len(CAPTURE_ORDER):
        return None
    nxt = CAPTURE_ORDER[idx + 1]
    _ensure_captures(conn, war_id, now)
    _add_point_fortification(conn, war_id, nxt, barricades=FALLBACK_BARRICADE_HP, now=now)
    conn.commit()
    name = CAPTURE_POINTS[nxt]["name"]
    return f"Defenders regroup at the {name} (+{FALLBACK_BARRICADE_HP} barricade fortification)!"


def _grant_royal_guard(conn, war_id, now=None):
    """Once the royal keep falls, the throne gets a final Guard line.

    Design: 'break through the royal guard' / 'final opportunity to hold'.
    """
    now = time.time() if now is None else float(now)
    if not _structure_destroyed(conn, "royal_keep"):
        return None
    # One grant per war (sentinel recruit_id).
    existing = conn.execute(
        "SELECT 1 FROM crown_war_guards WHERE war_id = ? AND recruit_id = ?",
        (int(war_id), ROYAL_GUARD_SENTINEL),
    ).fetchone()
    if existing:
        return None
    try:
        conn.execute(
            "INSERT INTO crown_war_guards "
            "(war_id, recruit_id, clan_id, point_id, deployed_at) "
            "VALUES (?, ?, 0, 'throne', ?)",
            (int(war_id), ROYAL_GUARD_SENTINEL, now),
        )
    except Exception:
        return None
    _ensure_captures(conn, war_id, now)
    _add_point_fortification(conn, war_id, "throne", guards=ROYAL_GUARD_HP, now=now)
    conn.commit()
    return (
        f"The Royal Guard forms in the Throne Room "
        f"(+{ROYAL_GUARD_HP} guard fortification) — Stage 4 Last Stand: "
        "break through the royal guard; defenders get a final opportunity to hold!"
    )


def _resolve_player_name(conn, name):
    """Lookup a player id by character name (case-insensitive)."""
    name = (name or "").strip()
    if not name:
        return None
    row = conn.execute(
        "SELECT id FROM players WHERE char_name = ? COLLATE NOCASE LIMIT 1",
        (name,),
    ).fetchone()
    return int(row[0]) if row else None


def _can_manage_royal_guard(conn, player_id):
    """Monarch or Marshal may appoint the limited player Royal Guard."""
    try:
        import ruling
        r = ruling.role(conn, player_id)
    except Exception:
        return False
    return r in ("Monarch", "Marshal")


def list_royal_guard_players(conn, war_id=None):
    """Appointed player royal guards for the current (or given) war."""
    war_id = int(war_id) if war_id is not None else None
    if war_id is None:
        war = current_war(conn)
        if not war:
            return []
        war_id = int(war["id"])
    rows = conn.execute(
        "SELECT r.player_id, COALESCE(p.char_name, '#' || r.player_id), r.appointed_at "
        "FROM crown_war_royal_players r "
        "LEFT JOIN players p ON p.id = r.player_id "
        "WHERE r.war_id = ? ORDER BY r.appointed_at, r.player_id",
        (war_id,),
    ).fetchall()
    return [
        {"player_id": int(r[0]), "name": r[1], "appointed_at": float(r[2])}
        for r in rows
    ]


def appoint_royal_guard(conn, actor_id, name, now=None):
    """Appoint a defending player to the limited Royal Guard (protect the King)."""
    now = time.time() if now is None else float(now)
    if not _can_manage_royal_guard(conn, actor_id):
        return False, "Only the Monarch or Marshal can appoint the Royal Guard."
    war = current_war(conn)
    if not war or war["status"] not in WAR_OPEN:
        return False, "No War for the Crown is open."
    target_id = _resolve_player_name(conn, name)
    if not target_id:
        return False, f"No player named {name!r}."
    if player_side(conn, target_id, war["id"]) != "defend":
        return False, "Royal Guard appointments must be defending fighters."
    existing = list_royal_guard_players(conn, war["id"])
    if any(e["player_id"] == int(target_id) for e in existing):
        return False, f"{name} is already in the Royal Guard."
    if len(existing) >= ROYAL_GUARD_PLAYER_CAP:
        return False, (
            f"The Royal Guard is full ({ROYAL_GUARD_PLAYER_CAP} appointed players). "
            "Dismiss one with /siege royalguard dismiss <name>."
        )
    conn.execute(
        "INSERT INTO crown_war_royal_players "
        "(war_id, player_id, appointed_by, appointed_at) VALUES (?, ?, ?, ?)",
        (int(war["id"]), int(target_id), int(actor_id), now),
    )
    conn.commit()
    return (
        True,
        f"{name} is appointed to the Royal Guard "
        f"({len(existing) + 1}/{ROYAL_GUARD_PLAYER_CAP}) — they can protect the King "
        "in the Throne Room.",
    )


def dismiss_royal_guard(conn, actor_id, name, now=None):
    """Remove an appointed player from the Royal Guard."""
    if not _can_manage_royal_guard(conn, actor_id):
        return False, "Only the Monarch or Marshal can dismiss the Royal Guard."
    war = current_war(conn)
    if not war or war["status"] not in WAR_OPEN:
        return False, "No War for the Crown is open."
    target_id = _resolve_player_name(conn, name)
    if not target_id:
        return False, f"No player named {name!r}."
    cur = conn.execute(
        "DELETE FROM crown_war_royal_players WHERE war_id = ? AND player_id = ?",
        (int(war["id"]), int(target_id)),
    )
    conn.commit()
    if cur.rowcount == 0:
        return False, f"{name} is not in the Royal Guard."
    return True, f"{name} is dismissed from the Royal Guard."


def royal_guard_lines(conn, war_id=None):
    """Board / command lines for appointed player royal guards."""
    guards = list_royal_guard_players(conn, war_id)
    if not guards:
        return [
            f"Royal Guard (players): none appointed "
            f"(cap {ROYAL_GUARD_PLAYER_CAP}). "
            "Monarch/Marshal: /siege royalguard <name>"
        ]
    names = ", ".join(g["name"] for g in guards)
    return [
        f"Royal Guard (players): {names} "
        f"({len(guards)}/{ROYAL_GUARD_PLAYER_CAP}) — "
        "standing in the Throne Room they protect the King."
    ]


def _appointed_royal_guards_at(conn, war_id, presence, point_id="throne"):
    """Count appointed Royal Guard players present on a capture point (defend)."""
    appointed = {
        int(g["player_id"]) for g in list_royal_guard_players(conn, war_id)
    }
    if not appointed:
        return 0
    n = 0
    for player_id, plane, x, y in presence:
        if int(player_id) not in appointed:
            continue
        if is_eliminated(conn, player_id, war_id):
            continue
        if player_side(conn, player_id, war_id) != "defend":
            continue
        if _point_at(plane, x, y) == point_id:
            n += 1
    return n


def _capture_unlocked(conn, war_id, point_id):
    """Attackers must take stages in CAPTURE_ORDER; defenders may always contest.

    Gatehouse also needs a wall/gate breach. Throne needs the royal keep destroyed.
    """
    if point_id not in CAPTURE_ORDER:
        return True
    idx = CAPTURE_ORDER.index(point_id)
    if idx == 0:
        return True
    if _capture_owner(conn, war_id, CAPTURE_ORDER[idx - 1]) != "attack":
        return False
    if point_id == "gatehouse" and not walls_breached(conn):
        return False
    if point_id == "throne" and not _structure_destroyed(conn, "royal_keep"):
        return False
    return True


def deploy_barricade(conn, player_id, point_id, now=None):
    """Defenders spend one crafted barricade to fortify a capture point."""
    now = time.time() if now is None else float(now)
    point_id = str(point_id or "").strip()
    if point_id not in CAPTURE_POINTS:
        return False, f"Unknown point. Choose: {', '.join(CAPTURE_ORDER)}."
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err
    if player_side(conn, player_id, war["id"]) != "defend":
        return False, "Only defenders can deploy barricades."
    if war["status"] not in ("scheduled", "active", "registration"):
        return False, "No war is open for barricades."
    stock = weapon_stock(conn, war["id"], lead_id)
    if stock.get("barricade", 0) < 1:
        return False, "No barricades in stock. /siege craft barricade"
    conn.execute(
        "UPDATE crown_war_weapons SET qty = qty - 1 "
        "WHERE war_id = ? AND clan_id = ? AND weapon_id = 'barricade' AND qty >= 1",
        (war["id"], lead_id),
    )
    if conn.total_changes == 0:
        return False, "No barricades in stock. /siege craft barricade"
    _ensure_captures(conn, war["id"], now)
    conn.execute(
        "UPDATE crown_war_captures SET barricades = COALESCE(barricades, 0) + ?, "
        "updated_at = ? WHERE war_id = ? AND point_id = ?",
        (BARRICADE_DEPLOY_HP, now, war["id"], point_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT barricades FROM crown_war_captures WHERE war_id = ? AND point_id = ?",
        (war["id"], point_id),
    ).fetchone()
    name = CAPTURE_POINTS[point_id]["name"]
    return True, (
        f"Deployed a barricade at the {name} "
        f"(fortification {int(row[0] if row else 0)} HP)."
    )


def _available_guard_recruit(conn, war_id, clan_id):
    """Pick an active Guard recruit from this clan that is not already posted this war."""
    try:
        row = conn.execute(
            "SELECT r.id, r.name FROM clan_recruits r "
            "WHERE r.clan_id = ? AND r.active = 1 AND r.role = 'Guard' "
            "AND r.id NOT IN ("
            "  SELECT recruit_id FROM crown_war_guards WHERE war_id = ?"
            ") ORDER BY r.id LIMIT 1",
            (int(clan_id), int(war_id)),
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return {"id": int(row[0]), "name": row[1]}


def deploy_guard(conn, player_id, point_id, now=None):
    """Post a Guard recruit on a capture point (design: defenders deploy guards).

    Attackers must clear guard HP before barricades and capture progress. The
    recruit stays hired but cannot be posted twice in the same war.
    """
    now = time.time() if now is None else float(now)
    point_id = str(point_id or "").strip()
    if point_id not in CAPTURE_POINTS:
        return False, f"Unknown point. Choose: {', '.join(CAPTURE_ORDER)}."
    war, lead_id, err = _side_operator(conn, player_id)
    if err:
        return False, err
    if player_side(conn, player_id, war["id"]) != "defend":
        return False, "Only defenders can deploy guards."
    if war["status"] not in ("scheduled", "active", "registration"):
        return False, "No war is open for guard posts."
    clan_id = _clan_of(conn, player_id)
    recruit = _available_guard_recruit(conn, war["id"], clan_id)
    if not recruit:
        return False, (
            "No free Guard recruit to post. Hire a Guard (/guild hire Guard) "
            "or wait until a posted Guard is free next war."
        )
    _ensure_captures(conn, war["id"], now)
    conn.execute(
        "INSERT INTO crown_war_guards (war_id, recruit_id, clan_id, point_id, deployed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (war["id"], recruit["id"], int(clan_id), point_id, now),
    )
    conn.execute(
        "UPDATE crown_war_captures SET guards = COALESCE(guards, 0) + ?, "
        "updated_at = ? WHERE war_id = ? AND point_id = ?",
        (GUARD_DEPLOY_HP, now, war["id"], point_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT COALESCE(guards, 0) FROM crown_war_captures WHERE war_id = ? AND point_id = ?",
        (war["id"], point_id),
    ).fetchone()
    name = CAPTURE_POINTS[point_id]["name"]
    return True, (
        f"Posted Guard {recruit['name']} at the {name} "
        f"(guard fortification {int(row[0] if row else 0)} HP)."
    )


def _point_at(plane, x, y):
    for pid, spec in CAPTURE_POINTS.items():
        if spec["plane"] != plane:
            continue
        x0, y0, x1, y1 = spec["rect"]
        if x0 <= int(x) <= x1 and y0 <= int(y) <= y1:
            return pid
    return None


def is_eliminated(conn, player_id, war_id=None):
    war = current_war(conn) if war_id is None else {"id": int(war_id)}
    if not war:
        return False
    row = conn.execute(
        "SELECT 1 FROM crown_war_elim WHERE war_id = ? AND player_id = ?",
        (int(war["id"]), int(player_id)),
    ).fetchone()
    return bool(row)


def action_blocked(conn, player_id):
    """Last Stand: eliminated fighters may watch, not act in the active assault."""
    war = current_war(conn)
    if not war or war.get("status") != "active":
        return None
    if not player_id:
        return None
    if is_eliminated(conn, player_id, war["id"]):
        return "You are eliminated from this siege and cannot act in it."
    return None


def player_side(conn, player_id, war_id=None):
    """Return 'attack', 'defend', or None for this player's guild in the war."""
    war = current_war(conn)
    if war_id is not None:
        if not war or int(war["id"]) != int(war_id):
            war = {"id": int(war_id)}
    if not war:
        return None
    if is_eliminated(conn, player_id, war["id"]):
        return None
    clan_id = _clan_of(conn, player_id)
    side, _lead = _player_war_side(conn, war["id"], clan_id)
    return side


def tick_captures(conn, presence, now=None):
    """Advance capture progress from ``(player_id, plane, x, y)`` rows."""
    now = time.time() if now is None else float(now)
    war = current_war(conn)
    if not war or war["status"] != "active":
        return []
    notices = []
    # Royal keep down → royal guard forms BEFORE attackers can chip the throne
    # (design: break through the royal guard to secure the chamber).
    rg = _grant_royal_guard(conn, war["id"], now=now)
    if rg:
        notices.append(rg)
    counts = {pid: {"attack": 0, "defend": 0} for pid in CAPTURE_POINTS}
    for player_id, plane, x, y in presence:
        if is_eliminated(conn, player_id, war["id"]):
            continue
        # Design: only confirmed siege participants fight for capture points.
        if not is_confirmed_fighter(conn, player_id, war["id"]):
            continue
        side = player_side(conn, player_id, war["id"])
        if side not in SIDES:
            continue
        point = _point_at(plane, x, y)
        if point:
            counts[point][side] += 1

    for point_id, spec in CAPTURE_POINTS.items():
        try:
            row = conn.execute(
                "SELECT owner, progress, hold_started_at, "
                "COALESCE(barricades, 0), COALESCE(guards, 0) "
                "FROM crown_war_captures WHERE war_id = ? AND point_id = ?",
                (war["id"], point_id),
            ).fetchone()
        except Exception:
            row = conn.execute(
                "SELECT owner, progress, hold_started_at, 0, 0 "
                "FROM crown_war_captures WHERE war_id = ? AND point_id = ?",
                (war["id"], point_id),
            ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO crown_war_captures (war_id, point_id, owner, progress, updated_at) "
                "VALUES (?, ?, 'defend', 0, ?)",
                (war["id"], point_id, now),
            )
            owner, progress, hold_started, barricades, guards = "defend", 0, None, 0, 0
        else:
            owner, progress, hold_started, barricades, guards = (
                row[0], int(row[1]), row[2], int(row[3] or 0), int(row[4] or 0),
            )
        atk, dfn = counts[point_id]["attack"], counts[point_id]["defend"]
        # Intact watchtower: defensive archers double the work on realm points.
        need = _capture_need(conn, spec)
        unlocked = _capture_unlocked(conn, war["id"], point_id)
        # Design: appointed players in the Throne Room protect the King.
        rg_here = (
            _appointed_royal_guards_at(conn, war["id"], presence, "throne")
            if point_id == "throne" else 0
        )
        pushing = None
        if atk > dfn:
            delta = atk - dfn
            if not unlocked:
                # Prior stage still held — attackers cannot push this point yet.
                pushing = None
            elif rg_here > 0:
                # Appointed Royal Guard holds the chamber — no chip / no flip.
                # (Board lines name them; avoid per-tick spam.)
                hold_started = None
            elif guards > 0:
                # Posted Guards hold the line before barricades and capture.
                chip = min(guards, delta)
                guards -= chip
                if guards == 0 and chip > 0:
                    notices.append(f"Defending Guards at the {spec['name']} are broken!")
            elif barricades > 0:
                # Clear barricades before capture progress advances.
                chip = min(barricades, delta)
                barricades -= chip
                if barricades == 0 and chip > 0:
                    notices.append(f"Barricades at the {spec['name']} are destroyed!")
            else:
                progress = min(need, progress + delta)
                pushing = "attack"
        elif dfn > atk:
            progress = min(need, progress + (dfn - atk))
            pushing = "defend"
        if pushing and progress >= need and owner != pushing:
            owner = pushing
            progress = 0
            hold_started = now if point_id == "throne" and owner == "attack" else None
            notices.append(f"{spec['name']} falls to the {pushing}!")
            # Credit fighters present on the point when it flips.
            for player_id, plane, x, y in presence:
                if is_eliminated(conn, player_id, war["id"]):
                    continue
                if player_side(conn, player_id, war["id"]) != pushing:
                    continue
                if _point_at(plane, x, y) == point_id:
                    _credit_points(conn, war["id"], player_id, CAPTURE_CONTRIB)
            # Defenders fall back and fortify the next stage.
            if pushing == "attack":
                fb = _fallback_fortify(conn, war["id"], point_id, now=now)
                if fb:
                    notices.append(fb)
        elif point_id == "throne" and owner == "attack" and rg_here > 0:
            # Appointed guard re-enters — interrupt Crownfall hold.
            hold_started = None
        elif point_id == "throne" and owner == "attack" and hold_started is None and atk > 0:
            hold_started = now
        elif point_id == "throne" and owner != "attack":
            hold_started = None
        conn.execute(
            "UPDATE crown_war_captures SET owner = ?, progress = ?, hold_started_at = ?, "
            "barricades = ?, guards = ?, updated_at = ? WHERE war_id = ? AND point_id = ?",
            (owner, progress, hold_started, barricades, guards, now, war["id"], point_id),
        )
    conn.commit()

    throne = conn.execute(
        "SELECT owner, hold_started_at FROM crown_war_captures "
        "WHERE war_id = ? AND point_id = 'throne'",
        (war["id"],),
    ).fetchone()
    if throne and throne[0] == "attack" and throne[1] is not None:
        if now - float(throne[1]) >= THRONE_HOLD_SECONDS:
            ok, msg = resolve_war(conn, winner="attack", now=now)
            if ok:
                notices.append(msg)
    return notices


def coronation_payload(note, winner=None, crowned_name=None, guild_name=None):
    """Structured Stage-5 Crownfall event for a realm-wide announce.

    Design: 'A coronation event announces the new ruler to the entire realm.'
    """
    text = str(note or "").strip()
    if not text.upper().startswith("CROWNFALL"):
        return None
    title = "CROWNFALL"
    if winner == "attack" or (crowned_name and "crowned" in text.lower()):
        subtitle = (
            f"All hail {crowned_name}!" if crowned_name
            else "A new ruler claims the King's Castle!"
        )
    elif winner == "defend":
        subtitle = (
            f"{guild_name} held the walls!" if guild_name
            else "The defenders keep the crown!"
        )
    else:
        # Infer from the note when callers only pass the herald line.
        low = text.lower()
        if "held the walls" in low or "defenders keep" in low:
            subtitle = "The defenders keep the crown!"
        elif "all hail" in low:
            # Prefer the crowned name after "All hail".
            after = text.split("All hail", 1)[-1].strip(" !.")
            name = after.split("!")[0].strip() if after else ""
            subtitle = f"All hail {name}!" if name else "A new ruler claims the King's Castle!"
        else:
            subtitle = "The War for the Crown is over."
    return {
        "title": title,
        "text": text,
        "subtitle": subtitle,
        "winner": winner,
        "crowned_name": crowned_name,
        "guild_name": guild_name,
    }


def _alliance_recognition(conn, war_id, side):
    """Accepted ally guild names for Crownfall recognition.

    Design: 'Smaller guilds can join alliances and receive recognition.'
    """
    allies = [
        a for a in _allies(conn, war_id, side=side) if a.get("status") == "accepted"
    ]
    names = [a.get("ally_name") for a in allies if a.get("ally_name")]
    if not names:
        return ""
    if len(names) == 1:
        return f" with {names[0]}"
    if len(names) == 2:
        return f" with {names[0]} and {names[1]}"
    return f" with {', '.join(names[:-1])}, and {names[-1]}"


def resolve_war(conn, winner="attack", now=None):
    """End the war. Attacker victory crowns the attacking lead guild's leader."""
    now = time.time() if now is None else float(now)
    war = current_war(conn)
    if not war or war["status"] not in ("active", "scheduled"):
        return False, "No resolvable war."
    lead = _lead_slot(conn, war["id"], winner)
    note = f"War #{war['id']} won by {winner}."
    crowned_pid = None
    crowned_name = None
    ally_bit = _alliance_recognition(conn, war["id"], winner) if lead else ""
    if winner == "attack" and lead:
        row = conn.execute(
            "SELECT leader_id FROM clans WHERE clan_id = ?", (lead["clan_id"],)
        ).fetchone()
        if row:
            try:
                import throne
                crowned_pid = int(row[0])
                throne._crown(conn, crowned_pid, "siege", "reigning", now)
                name_row = conn.execute(
                    "SELECT char_name FROM players WHERE id = ?", (crowned_pid,)
                ).fetchone()
                crowned_name = (name_row[0] if name_row else None) or lead["name"]
                note = (
                    f"CROWNFALL — {lead['name']}{ally_bit} takes the castle! "
                    f"{crowned_name} is crowned. The War for the Crown is over."
                )
            except Exception as exc:
                note = f"War won by {lead['name']}{ally_bit}, but crowning failed: {exc}"
    elif winner == "defend":
        hold_name = (lead["name"] if lead else "the defenders") + ally_bit
        note = (
            f"CROWNFALL — {hold_name} held the walls. "
            "The defenders keep the crown. The War for the Crown is over."
        )
    conn.execute(
        "UPDATE crown_wars SET status = 'completed', closed_at = ?, note = ? WHERE id = ?",
        (now, note, war["id"]),
    )
    conn.commit()
    clear_war_focus(conn, war["id"])
    if crowned_pid:
        try:
            grant_siege_heraldry(conn, crowned_pid, war_id=war["id"], now=now)
            note += (
                f" All hail {crowned_name or 'the new monarch'}! "
                "Royal heraldry flies over the King's Castle; Regal robes unlock at Mae's."
            )
            conn.execute(
                "UPDATE crown_wars SET note = ? WHERE id = ?", (note, war["id"]),
            )
            conn.commit()
        except Exception:
            pass
    try:
        import politics
        politics.news(conn, "siege", note, now)
        politics.news(conn, "throne", note, now)
    except Exception:
        pass
    invalidate_breaches()
    # Leave battle scars until the next assault's reset_all — the castle
    # should look fought-over between wars.
    return True, note


def grant_siege_heraldry(conn, player_id, war_id=None, now=None):
    """After a real siege win: castle banner + immediate Regal outfit unlock (no coin mint)."""
    import json
    now = time.time() if now is None else float(now)
    banner = None
    try:
        import player_houses
        house = player_houses.get_house(conn, int(player_id))
        if house:
            banner = house.get("banner")
        if not banner:
            banner = player_houses.banner_from_seed(int(player_id) * 17 + 3)
    except Exception:
        banner = {"field": "crimson", "ordinaries": ["pale"], "charge": "crown"}
    conn.execute(
        "INSERT OR REPLACE INTO crown_heraldry "
        "(castle_id, player_id, banner_json, outfit_unlocked, granted_at, war_id) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (KING_CASTLE_ID, int(player_id), json.dumps(banner), now, war_id),
    )
    conn.commit()
    return {
        "castle_id": KING_CASTLE_ID,
        "player_id": int(player_id),
        "banner": banner,
        "outfit_unlocked": True,
        "granted_at": now,
        "war_id": war_id,
    }


def castle_heraldry(conn, castle_id=KING_CASTLE_ID):
    import json
    row = conn.execute(
        "SELECT player_id, banner_json, outfit_unlocked, granted_at, war_id "
        "FROM crown_heraldry WHERE castle_id = ?",
        (castle_id,),
    ).fetchone()
    if not row:
        return None
    banner = None
    try:
        banner = json.loads(row[1]) if row[1] else None
    except Exception:
        banner = None
    return {
        "castle_id": castle_id,
        "player_id": int(row[0]),
        "banner": banner,
        "outfit_unlocked": bool(row[2]),
        "granted_at": float(row[3]),
        "war_id": int(row[4]) if row[4] is not None else None,
    }


def siege_regal_unlocked(conn, player_id):
    """Siege victors skip the 7-day Regal wait for the king's T7 set."""
    row = conn.execute(
        "SELECT 1 FROM crown_heraldry WHERE player_id = ? AND outfit_unlocked = 1",
        (int(player_id),),
    ).fetchone()
    return bool(row)


def council_lines(conn, player_id=None, now=None):
    """Surface the existing ruling council + public works for the reigning monarch."""
    import ruling
    now = time.time() if now is None else float(now)
    lines = []
    r = ruling.role(conn, player_id) if player_id else None
    if r == "Monarch":
        lines.append(
            "You hold the Crown. Appoint a Chancellor, Marshal, Steward and Royal Herald "
            "with /treasury appoint <post> <name>. Fund public works with /treasury fund <key>."
        )
    council = dict(conn.execute("SELECT post, player_id FROM council").fetchall())
    if council:
        bits = []
        for post in ruling.POSTS:
            pid = council.get(post)
            if not pid:
                bits.append(f"{post}: vacant")
                continue
            name = conn.execute(
                "SELECT char_name FROM players WHERE id = ?", (pid,)
            ).fetchone()
            bits.append(f"{post}: {(name[0] if name else '#'+str(pid))}")
        lines.append("Council — " + " · ".join(bits))
    else:
        lines.append("The royal council stands empty.")
    works = []
    for key, (name, _cost) in ruling.PUBLIC_WORKS.items():
        if ruling.work_active(conn, key, now):
            works.append(name)
    if works:
        lines.append("Public works in effect: " + ", ".join(works) + ".")
    else:
        lines.append(
            "No public works funded. Keys: " + ", ".join(ruling.PUBLIC_WORKS.keys()) + "."
        )
    # Never mint coins or items here — treasury spends stay in ruling.fund_work.
    return lines


def _credit_points(conn, war_id, player_id, points, deposits=0):
    """Award contribution points (engines, repairs, supplies)."""
    if not player_id or int(points) <= 0:
        return
    clan_id = _clan_of(conn, player_id) or 0
    conn.execute(
        "INSERT INTO crown_war_contrib (war_id, player_id, clan_id, points, deposits, kills) "
        "VALUES (?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(war_id, player_id) DO UPDATE SET "
        "points = points + excluded.points, "
        "deposits = deposits + excluded.deposits, "
        "clan_id = excluded.clan_id",
        (int(war_id), int(player_id), int(clan_id), int(points), int(deposits)),
    )
    conn.commit()


def _credit_kill(conn, war_id, killer_id, victim_clan_id=None):
    """Award one siege kill to the killer's contribution row."""
    if not killer_id:
        return
    clan_id = _clan_of(conn, killer_id) or 0
    conn.execute(
        "INSERT INTO crown_war_contrib (war_id, player_id, clan_id, points, deposits, kills) "
        "VALUES (?, ?, ?, 0, 0, 1) "
        "ON CONFLICT(war_id, player_id) DO UPDATE SET "
        "kills = kills + 1, clan_id = excluded.clan_id",
        (int(war_id), int(killer_id), int(clan_id)),
    )
    conn.commit()


def eliminate(conn, player_id, now=None, killer_id=None):
    """Last Stand: remove a player from the active siege only."""
    now = time.time() if now is None else float(now)
    war = current_war(conn)
    if not war or war["status"] != "active":
        return False, "No active assault."
    if is_eliminated(conn, player_id, war["id"]):
        return False, "Already eliminated from this siege."
    clan_id = _clan_of(conn, player_id)
    side, _ = _player_war_side(conn, war["id"], clan_id)
    if side not in SIDES:
        return False, "You are not fighting in this war."
    conn.execute(
        "INSERT OR REPLACE INTO crown_war_elim (war_id, player_id, eliminated_at) VALUES (?, ?, ?)",
        (war["id"], int(player_id), now),
    )
    # Free focus slots: this fighter no longer attacks or absorbs focus fire.
    _clear_attacker_focus(conn, war["id"], player_id)
    _clear_defender_focus(conn, war["id"], player_id)
    conn.commit()
    # Credit opposite-side player kills only (not monsters / friendly fire).
    if killer_id and int(killer_id) != int(player_id):
        killer_side = player_side(conn, killer_id, war["id"])
        if killer_side in SIDES and killer_side != side:
            _credit_kill(conn, war["id"], killer_id, clan_id)
    return True, (
        "You fall in the War for the Crown. You are out of this siege — "
        "respawn outside, watch and cheer your alliance, then /siege report "
        "for the full battle report after Crownfall."
    )


def can_enter_siege(conn, player_id):
    war = current_war(conn)
    if not war or war["status"] != "active":
        return True, None
    if is_eliminated(conn, player_id, war["id"]):
        return False, "You are eliminated from this siege. Wait for the next War for the Crown."
    return True, None


def on_siege_death(conn, player_id, dungeon=None, now=None, killer_id=None):
    """Combat death hook. Returns (eliminated, player_message, herald_notice)."""
    dungeon = dungeon or {}
    if dungeon.get("id") != "castle_realm":
        return False, None, None
    war = current_war(conn)
    if not war or war["status"] != "active":
        return False, None, None
    clan_id = _clan_of(conn, player_id)
    side, _ = _player_war_side(conn, war["id"], clan_id)
    if side not in SIDES:
        return False, None, None
    ok, msg = eliminate(conn, player_id, now=now, killer_id=killer_id)
    if not ok:
        return False, msg, None
    row = conn.execute(
        "SELECT char_name FROM players WHERE id = ?", (int(player_id),)
    ).fetchone()
    name = (row[0] if row and row[0] else None) or f"#{int(player_id)}"
    herald = f"{name} has fallen in the War for the Crown and is out of this siege."
    try:
        import politics
        politics.news(conn, "siege", herald, now if now is not None else time.time())
    except Exception:
        pass
    return True, msg, herald


def live_presence(sessions, conn=None):
    """Build capture presence rows from live castle_realm sessions."""
    conn = conn or _CONN
    out = []
    for session in sessions:
        d = getattr(session, "dungeon", None) or {}
        if d.get("id") != "castle_realm":
            continue
        pid = int(getattr(session, "player_id", 0) or 0)
        if not pid:
            continue
        if conn is not None and is_eliminated(conn, pid):
            continue
        plane = d.get("plane") or "realm"
        out.append((pid, plane, int(session.x), int(session.y)))
    return out


def in_interest(ax, ay, bx, by, radius=None):
    """Chebyshev interest check used for siege state fan-out."""
    radius = INTEREST_RADIUS if radius is None else int(radius)
    return max(abs(int(ax) - int(bx)), abs(int(ay) - int(by))) <= radius


def filter_by_interest(origin, others, radius=None, cap=None):
    """Keep ``origin`` plus nearby fighters, capped for a 100-a-side profile.

    ``origin`` is a public_state dict with x/y; ``others`` is a list of the same.
    When more than ``cap`` (default INTEREST_CAP / SIDE_CAP) others fall inside the
    interest radius, keep the nearest by Chebyshev distance so STATE_UPDATE stays
    profiled for large assaults.
    """
    if not origin:
        return list(others or [])
    ox, oy = int(origin.get("x", 0)), int(origin.get("y", 0))
    oid = origin.get("id") or origin.get("player_id")
    cap = INTEREST_CAP if cap is None else max(0, int(cap))
    self_row = None
    nearby = []
    for row in others or []:
        rid = row.get("id") or row.get("player_id")
        if oid is not None and rid == oid:
            self_row = row
            continue
        if in_interest(ox, oy, row.get("x", 0), row.get("y", 0), radius):
            dist = max(abs(ox - int(row.get("x", 0))), abs(oy - int(row.get("y", 0))))
            nearby.append((dist, rid if rid is not None else 0, row))
    nearby.sort(key=lambda t: (t[0], t[1]))
    kept = [t[2] for t in nearby[:cap]]
    if self_row is not None:
        kept.insert(0, self_row)
    elif oid is not None:
        # Origin may not be in ``others``; still return nearby-only list.
        pass
    return kept


def interest_profile_lines(conn, war=None):
    """Milestone 8: surface interest radius + profiled roster/fan-out caps."""
    war = war or current_war(conn)
    if not war or war.get("status") not in ("registration", "scheduled", "active"):
        return []
    radius = effective_interest_radius(conn)
    lines = [
        f"Roster profile: {HUMAN_MIN}–{SIDE_CAP} fighters/side · "
        f"mercs ≤{int(MERC_MAX_FRACTION * 100)}% · "
        f"interest radius {radius} tiles · fan-out cap {INTEREST_CAP} nearest."
    ]
    if war.get("status") == "active":
        lines.append(
            "Interest management: assault STATE fan-out only includes fighters "
            f"within {radius} tiles (nearest {INTEREST_CAP} when crowded)."
        )
    return lines




def month_day_in_cycle(conn, now=None):
    """1–30 day index in the monthly siege calendar, or None if unknown."""
    now = time.time() if now is None else float(now)
    war = current_war(conn)
    if war and war.get("status") == "active":
        return 30
    if war and war.get("status") in ("registration", "scheduled"):
        # Registration / assault window selection = late-month battle assignments.
        return 29
    last = _last_closed(conn)
    if last is None:
        return None
    elapsed = max(0.0, now - float(last))
    day = int(elapsed // DAY) + 1  # day 1 begins immediately after Crownfall
    return max(1, min(30, day))


def monthly_calendar_phase(conn, now=None):
    """(day, label) for the current monthly calendar phase, or (None, None)."""
    day = month_day_in_cycle(conn, now)
    if day is None:
        return None, None
    for lo, hi, label in MONTHLY_CALENDAR:
        if lo <= day <= hi:
            return day, label
    return day, MONTHLY_CALENDAR[-1][2]


def monthly_calendar_lines(conn, now=None):
    """Design: build anticipation over the entire month toward The Siege of Crownfall."""
    now = time.time() if now is None else float(now)
    day, label = monthly_calendar_phase(conn, now)
    if not label:
        return []
    lines = [f"Monthly siege calendar (day {day}/30): {label}."]
    war = current_war(conn)
    if not war:
        if day <= 27:
            lines.append(
                "Contribute throughout the month — gather supplies now; "
                "deposit into the war storehouse when registration opens (days 28–29)."
            )
        elif day >= 28:
            lines.append(
                "Registration window — a guild Leader may /siege register attack|defend "
                "once the cooldown ends."
            )
    elif war.get("status") in ("registration", "scheduled"):
        lines.append(
            "Battle assignments are open — form alliances, deposit supplies, craft engines, "
            "run Engineering surveys, and set the coordinated assault window."
        )
    elif war.get("status") == "active":
        lines.append(
            "The Siege of Crownfall is underway — hold or take the throne before the assault clock ends."
        )
    return lines


def next_war_opens_in_days(conn, now=None):
    """Days until the monthly War for the Crown may open, or None if unknown/open.

    Returns 0 when the cooldown has already elapsed (registration can open).
    """
    now = time.time() if now is None else float(now)
    if current_war(conn):
        return None
    last = _last_closed(conn)
    if last is None:
        return None
    remaining = float(SIEGE_COOLDOWN) - (now - float(last))
    if remaining <= 0:
        return 0
    return int((remaining + DAY - 1) // DAY)



def _completed_war(conn, war_id=None):
    """Fetch a completed war row (latest if war_id omitted)."""
    if war_id is not None:
        row = conn.execute(
            "SELECT id, status, opened_at, scheduled_at, started_at, closed_at, note, scale "
            "FROM crown_wars WHERE id = ?",
            (int(war_id),),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, status, opened_at, scheduled_at, started_at, closed_at, note, scale "
            "FROM crown_wars WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "status": row[1],
        "opened_at": float(row[2]) if row[2] is not None else None,
        "scheduled_at": float(row[3]) if row[3] is not None else None,
        "started_at": float(row[4]) if row[4] is not None else None,
        "closed_at": float(row[5]) if row[5] is not None else None,
        "note": row[6],
        "scale": row[7],
    }


def battle_report_lines(conn, war_id=None, now=None):
    """Full battle report after a war (design: eliminated fighters still get a report).

    Uses the latest completed war when ``war_id`` is omitted. During an active war,
    returns a live progress report instead.
    """
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    live = current_war(conn)
    if live and live.get("status") == "active" and war_id is None:
        war = live
        lines = [f"Battle report — War #{war['id']} (live assault):"]
        left = assault_time_left(war, now)
        if left is not None:
            lines.append(
                f"Assault clock: {left // HOUR}h {(left % HOUR) // 60}m remaining."
            )
    else:
        war = _completed_war(conn, war_id)
        if not war:
            return ["No completed War for the Crown battle report yet."]
        lines = [f"Battle report — War #{war['id']}:"]
        if war.get("note"):
            lines.append(str(war["note"]))
        started = war.get("started_at") or war.get("scheduled_at")
        closed = war.get("closed_at")
        if started and closed:
            dur = max(0, int(float(closed) - float(started)))
            lines.append(
                f"Assault lasted {dur // HOUR}h {(dur % HOUR) // 60}m"
                + (f" · scale {war['scale']}" if war.get("scale") else "")
                + "."
            )
        elif war.get("scale"):
            lines.append(f"Scale: {war['scale']}.")

    # Sides / composition snapshot.
    for side in SIDES:
        lead = _lead_slot(conn, war["id"], side)
        if not lead:
            lines.append(f"{side.title()}: —")
            continue
        humans = _alliance_humans(conn, war["id"], lead["clan_id"], side)
        mercs = _alliance_mercs(conn, war["id"], lead["clan_id"], side)
        lines.append(
            f"{side.title()}: {lead['name']} — {humans} humans / {mercs} mercs"
        )

    fighters = contrib_board(conn, war["id"], limit=5)
    if fighters:
        lines.append(
            "Top fighters: "
            + " · ".join(
                f"{e['name']} {e['points']}pts/{e['kills']}k"
                for e in fighters
            )
        )
    elim_n = conn.execute(
        "SELECT COUNT(*) FROM crown_war_elim WHERE war_id = ?", (war["id"],)
    ).fetchone()[0]
    lines.append(f"Fallen this siege: {int(elim_n)}.")
    weak = [
        s["name"] for s in list_structures(conn)
        if s and s["state"] in ("heavily_damaged", "destroyed")
    ]
    if weak:
        lines.append("Castle scars: " + ", ".join(weak) + ".")
    if live and live.get("status") == "active" and war_id is None:
        lines.append(
            "Eliminated fighters may watch and cheer their alliance — "
            "a full battle report is waiting after Crownfall (/siege report)."
        )
    else:
        lines.append("Herald: /siege report · Great Hall chronicle · world map War Council.")
    return lines


def king_defend_lines(conn, player_id=None, war=None, now=None):
    """Design: King protects the keep, organises defenders, and decides tactics."""
    war = war or current_war(conn)
    if not war or war.get("status") not in ("registration", "scheduled", "active"):
        return []
    try:
        import throne
        st = throne.state(conn)
    except Exception:
        return []
    if st.get("monarch_kind") != "player" or not st.get("monarch_player_id"):
        return []
    lines = [
        "King's duties in this war: protect the royal keep · organise defending guilds "
        "(/siege ally) · appoint a limited Royal Guard (/siege royalguard <name>) · "
        "make tactical decisions (/siege alloc, /siege status, /siege when). "
        "If the King falls, the castle still stands — attackers must take the throne."
    ]
    if player_id and int(player_id) == int(st["monarch_player_id"]):
        lines.append(
            "You are the reigning monarch — defend Crownfall; your death does not "
            "end the siege by itself. Appoint up to "
            f"{ROYAL_GUARD_PLAYER_CAP} players to protect you in the Throne Room."
        )
    lines.extend(royal_guard_lines(conn, war["id"]))
    return lines


def role_roster(conn, war_id, side=None):
    """Confirmed fighter counts by battle role (optionally one side)."""
    counts = {r: 0 for r in BATTLE_ROLES}
    forged = {r: 0 for r in BATTLE_ROLES}
    sql = (
        "SELECT role, equipment_ready, COUNT(*) FROM crown_war_fighters "
        "WHERE war_id = ? AND status = ?"
    )
    args = [int(war_id), FIGHTER_CONFIRMED]
    if side in SIDES:
        sql += " AND side = ?"
        args.append(side)
    sql += " GROUP BY role, equipment_ready"
    for role, ready, n in conn.execute(sql, args).fetchall():
        role = str(role or "infantry")
        if role not in counts:
            counts[role] = 0
            forged[role] = 0
        counts[role] += int(n)
        if ready:
            forged[role] += int(n)
    return {"counts": counts, "forged": forged}


def role_roster_lines(conn, war=None):
    """Readable battle-role breakdown for the War Council / /siege roles."""
    war = war or current_war(conn)
    if not war:
        return ["No War for the Crown is open."]
    lines = [
        "Battle roles (confirmed fighters) — "
        "/siege enlist <role> · /siege role <role> before /siege attend:",
    ]
    for side in SIDES:
        roster = role_roster(conn, war["id"], side=side)
        bits = []
        for role in BATTLE_ROLES:
            n = int(roster["counts"].get(role) or 0)
            if n <= 0:
                continue
            ready = int(roster["forged"].get(role) or 0)
            label = BATTLE_ROLE_LABELS.get(role, role)
            bits.append(f"{label} {n} ({ready} forged)")
        if not bits:
            bits = ["none confirmed"]
        lines.append(f"  {side.title()}: " + " · ".join(bits))
    lines.append(
        "Roles: Infantry (frontline) · Archer (ranged/walls) · Healer (restore) · "
        "Engineer (engines/repairs) · Heavy (armoured)."
    )
    return lines


def war_council_panels(conn, player_id=None, now=None):
    """Structured War Council panels for the graphical / atlas UI.

    Panels: Army, Roles, Equipment, Storehouse, Castle, Objectives, Battle.
    """
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    war = current_war(conn)
    panels = {
        "army": {"title": "Army", "lines": [], "sides": {}},
        "roles": {"title": "Roles", "lines": []},
        "equipment": {"title": "Equipment", "lines": []},
        "storehouse": {"title": "Storehouse", "lines": []},
        "castle": {"title": "Castle", "lines": []},
        "objectives": {"title": "Objectives", "lines": []},
        "battle": {"title": "Battle", "lines": []},
    }
    if not war:
        panels["army"]["lines"] = ["No war open."]
        notes = recent_war_notes(conn, limit=1)
        if notes:
            panels["battle"]["lines"] = [notes[0]["note"], " /siege report for the full tally."]
        return panels

    pub = war_public(conn, war) or {}
    for side in SIDES:
        lead = ((pub.get("sides") or {}).get(side) or {}).get("lead") or {}
        humans = int(lead.get("humans") or 0)
        mercs = int(lead.get("mercs") or 0)
        name = lead.get("name") or "—"
        panels["army"]["sides"][side] = {
            "name": name, "humans": humans, "mercs": mercs,
        }
        panels["army"]["lines"].append(
            f"{side.title()}: {name} — {humans} humans / {mercs} mercs"
        )

    panels["roles"]["lines"] = role_roster_lines(conn, war)[1:]  # skip header
    panels["roles"]["by_side"] = {
        side: role_roster(conn, war["id"], side=side) for side in SIDES
    }

    for side in SIDES:
        ready_n = conn.execute(
            "SELECT COUNT(*) FROM crown_war_fighters "
            "WHERE war_id = ? AND side = ? AND status = ? AND equipment_ready = 1",
            (war["id"], side, FIGHTER_CONFIRMED),
        ).fetchone()[0]
        total_n = _side_confirmed_humans(conn, war["id"], side)
        panels["equipment"]["lines"].append(
            f"{side.title()} War Forge: {int(ready_n)}/{int(total_n)} ready "
            f"(/siege forge)"
        )
    if player_id:
        info = fighter_equipment(conn, player_id, war["id"])
        if info and info.get("ready"):
            panels["equipment"]["lines"].append(
                f"Your kit: {info.get('grade_name')} "
                f"({BATTLE_ROLE_LABELS.get(info.get('role'), info.get('role'))})"
            )
        elif info and info.get("status") == FIGHTER_CONFIRMED:
            panels["equipment"]["lines"].append(
                "You are confirmed but unforged — /siege forge before the assault."
            )

    for side in SIDES:
        lead = ((pub.get("sides") or {}).get(side) or {}).get("lead")
        stock = ((pub.get("sides") or {}).get(side) or {}).get("store") or {}
        if not lead:
            continue
        panels["storehouse"]["lines"].append(
            f"{side.title()} ({lead.get('name')}): "
            + " · ".join(f"{stock.get(r, 0)} {r}" for r in STORE_RESOURCES)
        )

    for s in list_structures(conn):
        if not s:
            continue
        panels["castle"]["lines"].append(
            f"{s['name']}: {s['state']} ({s['hp']}/{s['max_hp']})"
        )

    if war["status"] in ("active", "scheduled"):
        for p in capture_state(conn, war["id"]):
            stage_bit = ""
            if p["id"] in CAPTURE_STAGES:
                num, label = CAPTURE_STAGES[p["id"]]
                stage_bit = f"Stage {num} — {label}: "
            panels["objectives"]["lines"].append(
                f"{stage_bit}{p['name']}: {p['owner']} ({p['progress']}/{p['need']})"
            )
    else:
        panels["objectives"]["lines"].append(
            "Capture stages unlock when the assault begins."
        )

    elim_n = conn.execute(
        "SELECT COUNT(*) FROM crown_war_elim WHERE war_id = ?", (war["id"],)
    ).fetchone()[0]
    alive = max(0, _side_confirmed_humans(conn, war["id"], "attack")
                + _side_confirmed_humans(conn, war["id"], "defend") - int(elim_n))
    panels["battle"]["lines"].append(
        f"Status: {war['status']} · confirmed alive ~{alive} · eliminated {int(elim_n)}"
    )
    board = contrib_board(conn, war["id"], limit=3)
    if board:
        panels["battle"]["lines"].append(
            "Top contribution: "
            + " · ".join(f"{e['name']} {e['points']}pts" for e in board)
        )
    if war["status"] == "active":
        panels["battle"]["lines"].append(
            "Eliminated fighters may spectate — /siege report after Crownfall."
        )
    return panels


def war_council_lines(conn, player_id=None, now=None):
    """Notice-board / War Council blurb — public contribution board when a war is open."""
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        # Keep the last Crownfall note visible between monthly wars.
        notes = recent_war_notes(conn, limit=1)
        if not notes:
            return []
        lines = [
            "Royal War Council — no War for the Crown is open.",
            f"Last Crownfall: {notes[0]['note']}",
        ]
        days = next_war_opens_in_days(conn, now)
        if days is None:
            lines.append(
                "A guild Leader may /siege register attack|defend to open registration."
            )
        elif days <= 0:
            lines.append(
                "The monthly cooldown has ended — a guild Leader may "
                "/siege register attack|defend to open registration."
            )
        else:
            lines.append(
                f"Monthly cadence: the next War for the Crown opens in about {days} day(s). "
                "Leaders may /siege register once the cooldown ends."
            )
        # Design: monthly siege calendar builds anticipation toward Day 30.
        lines.extend(monthly_calendar_lines(conn, now=now))
        # Design: receive a full battle report afterwards.
        report = battle_report_lines(conn, war_id=notes[0]["id"], now=now)
        if report:
            lines.append("Last battle report — /siege report for the full tally.")
            # Compact: outcome + top fighters if present.
            for ln in report[1:4]:
                lines.append(ln)
        return lines
    lines = ["Royal War Council — War for the Crown"]
    # Compact status + both sides so the board shows community contribution at a glance.
    for ln in board_lines(conn, player_id, now=now)[:6]:
        lines.append(ln)
    panels = war_council_panels(conn, player_id, now=now)
    # Panel digest — Army / Roles / Equipment at a glance.
    for key in ("army", "roles", "equipment", "battle"):
        panel = panels.get(key) or {}
        for ln in (panel.get("lines") or [])[:3]:
            lines.append(f"[{panel.get('title', key)}] {ln}")
    lines.append(
        "Herald at the castle · /siege status · /siege roles · /siege forge · "
        "/siege store · world map War Council"
    )
    return lines


def atlas_war_summary(conn, player_id=None, now=None):
    """World-map War Council card (design: notice board, guild panel, and world map).

    Returns None when there is nothing to show (no open war and no last Crownfall).
    """
    now = time.time() if now is None else float(now)
    tick_wars(conn, now)
    lines = war_council_lines(conn, player_id, now=now)
    panels = war_council_panels(conn, player_id, now=now)
    war = current_war(conn)
    if war:
        pub = war_public(conn, war) or {}
        atk = ((pub.get("sides") or {}).get("attack") or {}).get("lead") or {}
        dfn = ((pub.get("sides") or {}).get("defend") or {}).get("lead") or {}
        line = f"War for the Crown — {war['status']}"
        if atk.get("name") or dfn.get("name"):
            line += f": {atk.get('name') or '—'} vs {dfn.get('name') or '—'}"
        if war["status"] == "scheduled":
            start = assault_starts_at(war)
            if start is not None:
                left = max(0, int(start - now))
                line += f" · assault in {left // HOUR}h {(left % HOUR) // 60}m"
        elif war["status"] == "active":
            left = assault_time_left(war, now)
            if left is not None:
                line += f" · {left // HOUR}h {(left % HOUR) // 60}m left"
        return {
            "open": True,
            "status": war["status"],
            "line": line,
            "lines": lines,
            "panels": panels,
        }
    if not lines:
        return None
    note = next(
        (ln for ln in lines if str(ln).lower().startswith("last crownfall")),
        lines[0],
    )
    days = next_war_opens_in_days(conn, now)
    cal_day, cal_label = monthly_calendar_phase(conn, now)
    if days is not None and days > 0:
        line = f"War for the Crown — next war in about {days} day(s)"
        if cal_day is not None:
            line += f" · calendar day {cal_day}/30"
    elif days == 0:
        line = "War for the Crown — registration can open"
    else:
        line = note
    if cal_label and days is not None:
        # Prefer a short calendar tag on the atlas card.
        short = cal_label.split(" — ", 1)[0]
        if short not in line:
            line += f" · {short}"
    return {
        "open": False,
        "status": None,
        "line": line,
        "next_war_days": days,
        "lines": lines,
        "panels": panels,
    }


def guild_war_summary(conn, clan_id, now=None):
    """Compact war blurb for the guild panel when this guild is registered or allied."""
    now = time.time() if now is None else float(now)
    if not clan_id:
        return None
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        return None
    side, lead_id = _player_war_side(conn, war["id"], int(clan_id))
    if not side:
        return None
    lead = _lead_slot(conn, war["id"], side)
    role = "lead" if lead and int(lead["clan_id"]) == int(clan_id) else "ally"
    foe = _lead_slot(conn, war["id"], "defend" if side == "attack" else "attack")
    bit = f"{side} ({role})"
    if lead:
        bit += f" · {lead['name']}"
        if lead.get("status"):
            bit += f" [{lead['status']}]"
    if foe and foe.get("name"):
        bit += f" vs {foe['name']}"
    out = {
        "war_id": war["id"],
        "status": war["status"],
        "side": side,
        "role": role,
        "line": f"War for the Crown — {war['status']}: {bit}",
    }
    if war["status"] == "scheduled" and war.get("scheduled_at") is not None:
        start_at = assault_starts_at(war)
        left = max(0, int(start_at - now)) if start_at is not None else 0
        out["assault_in"] = left
        out["assault_at"] = start_at
        out["line"] += f" · assault in {left // HOUR}h {(left % HOUR) // 60}m"
    elif war["status"] == "active":
        left = assault_time_left(war, now)
        if left is not None:
            out["assault_left"] = left
            out["line"] += f" · {left // HOUR}h {(left % HOUR) // 60}m left"
    return out


def hud_snapshot(conn, player_id=None):
    """Compact war/heraldry blob for STATE_UPDATE / client chips."""
    tick_wars(conn)
    war = current_war(conn)
    snap = {
        "war": war_public(conn, war) if war else None,
        "heraldry": castle_heraldry(conn),
        "interest_radius": effective_interest_radius(conn),
        "interest_cap": INTEREST_CAP,
        "side_cap": SIDE_CAP,
        "human_min": HUMAN_MIN,
        "merc_max_fraction": MERC_MAX_FRACTION,
        "side": player_side(conn, player_id) if player_id else None,
        "eliminated": bool(player_id and is_eliminated(conn, player_id)),
        "board": board_lines(conn, player_id) if war else [],
        "walls_breached": walls_breached(conn),
        "watchtower_down": _structure_destroyed(conn, "watchtower"),
        "armoury_down": _structure_destroyed(conn, "armoury"),
        "depot_down": _structure_destroyed(conn, "supply_depot"),
        "keep_down": _structure_destroyed(conn, "royal_keep"),
        "last_stand": bool(
            war
            and war.get("status") == "active"
            and _capture_unlocked(conn, war["id"], "throne")
        ),
    }
    if war:
        guards = list_royal_guard_players(conn, war["id"])
        snap["royal_guard"] = [g["name"] for g in guards]
        snap["is_royal_guard"] = bool(
            player_id and any(int(g["player_id"]) == int(player_id) for g in guards)
        )
    else:
        snap["royal_guard"] = []
        snap["is_royal_guard"] = False
    return snap


def tick_live(conn, sessions, now=None):
    """Server tick: advance captures from live presence. Returns notice strings."""
    now = time.time() if now is None else float(now)
    notices = []
    notices.extend(tick_wars(conn, now))
    war = current_war(conn)
    if war and war["status"] == "active":
        presence = live_presence(sessions, conn)
        notices.extend(tick_captures(conn, presence, now=now))
    return notices


def _player_war_side(conn, war_id, clan_id):
    """Return (side, lead_clan_id) if this clan fights in the war, else (None, None)."""
    if not clan_id:
        return None, None
    row = conn.execute(
        "SELECT side, status FROM crown_war_slots WHERE war_id = ? AND clan_id = ? "
        "AND status IN ('queued', 'reserved', 'confirmed')",
        (int(war_id), int(clan_id)),
    ).fetchone()
    if row:
        # Queued guilds prepare with the side they hope to take; store credits the
        # current lead for that side so supplies are not stranded if they never promote.
        lead = _lead_slot(conn, war_id, row[0])
        return row[0], int(lead["clan_id"]) if lead else int(clan_id)
    ally = conn.execute(
        "SELECT side, lead_clan_id, status FROM crown_war_allies "
        "WHERE war_id = ? AND ally_clan_id = ? AND status = 'accepted'",
        (int(war_id), int(clan_id)),
    ).fetchone()
    if ally:
        return ally[0], int(ally[1])
    return None, None


def _ensure_alloc(conn, war_id, clan_id):
    for bucket, pct in DEFAULT_ALLOC.items():
        conn.execute(
            "INSERT OR IGNORE INTO crown_war_alloc (war_id, clan_id, bucket, pct) VALUES (?, ?, ?, ?)",
            (int(war_id), int(clan_id), bucket, int(pct)),
        )
    conn.commit()


def store_stock(conn, war_id, clan_id):
    _ensure_alloc(conn, war_id, clan_id)
    rows = conn.execute(
        "SELECT resource, qty FROM crown_war_store WHERE war_id = ? AND clan_id = ?",
        (int(war_id), int(clan_id)),
    ).fetchall()
    stock = {r: 0 for r in STORE_RESOURCES}
    for res, qty in rows:
        stock[str(res)] = int(qty)
    return stock


def store_alloc(conn, war_id, clan_id):
    _ensure_alloc(conn, war_id, clan_id)
    rows = conn.execute(
        "SELECT bucket, pct FROM crown_war_alloc WHERE war_id = ? AND clan_id = ?",
        (int(war_id), int(clan_id)),
    ).fetchall()
    out = {b: 0 for b in ALLOC_BUCKETS}
    for bucket, pct in rows:
        out[str(bucket)] = int(pct)
    return out


def credit_deposit(conn, war_id, lead_clan_id, player_id, resource, qty, points, now=None):
    """Add stock and contribution. Leaders cannot withdraw this for personal use."""
    now = time.time() if now is None else float(now)
    qty = max(0, int(qty))
    points = max(0, int(points))
    if qty <= 0 or resource not in STORE_RESOURCES:
        return False
    conn.execute(
        "INSERT INTO crown_war_store (war_id, clan_id, resource, qty, deposited) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(war_id, clan_id, resource) DO UPDATE SET "
        "qty = qty + excluded.qty, deposited = deposited + excluded.deposited",
        (int(war_id), int(lead_clan_id), resource, qty, qty),
    )
    conn.execute(
        "INSERT INTO crown_war_contrib (war_id, player_id, clan_id, points, deposits) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(war_id, player_id) DO UPDATE SET "
        "points = points + excluded.points, deposits = deposits + excluded.deposits, "
        "clan_id = excluded.clan_id",
        (int(war_id), int(player_id), int(lead_clan_id), points, qty),
    )
    _ensure_alloc(conn, war_id, lead_clan_id)
    conn.commit()
    return True


def deposit(conn, player_id, item_id, qty, now=None, take_fn=None):
    """Deposit war materials. ``take_fn(item_id, qty)`` removes from the player; optional in tests."""
    now = time.time() if now is None else float(now)
    item_id = str(item_id or "").strip()
    qty = int(qty or 0)
    if item_id not in STORE_ITEMS:
        return False, (
            "That is not a war material. Deposit logs, ores, bars, or coal (stone)."
        )
    if qty <= 0:
        return False, "Deposit a positive amount."
    war = current_war(conn)
    if not war:
        return False, "No War for the Crown is open."
    blocked = action_blocked(conn, player_id)
    if blocked:
        return False, blocked
    clan_id = _clan_of(conn, player_id)
    side, lead_id = _player_war_side(conn, war["id"], clan_id)
    if not side or not lead_id:
        return False, "Your guild must be registered or allied in this war to supply the storehouse."
    resource, points_each = STORE_ITEMS[item_id]
    if take_fn is not None:
        if not take_fn(item_id, qty):
            return False, "You do not have that many."
    mult = deposit_skill_mult(conn, player_id, resource)
    pts = int(round(points_each * qty * mult))
    credit_deposit(conn, war["id"], lead_id, player_id, resource, qty, pts, now)
    stock = store_stock(conn, war["id"], lead_id)
    note = (
        f"Deposited {qty}× {item_id.replace('_', ' ')} into {_clan_name(conn, lead_id)}'s "
        f"war storehouse (+{pts} contribution). "
        f"Stock: timber {stock['timber']}, ore {stock['ore']}, bars {stock['bars']}, "
        f"stone {stock['stone']}."
    )
    if mult > 1.001:
        note += f" [skill ×{mult:.2f}]"
    return True, note


def set_allocation(conn, player_id, mapping, now=None):
    """Leader sets percentage buckets; must sum to 100. Stock itself cannot be withdrawn."""
    now = time.time() if now is None else float(now)
    if not _is_leader(conn, player_id):
        return False, "Only a guild Leader can set war allocations."
    clan_id = _clan_of(conn, player_id)
    war = current_war(conn)
    if not war or not clan_id:
        return False, "No open war, or you have no guild."
    if war.get("status") == "active":
        return False, "Allocations lock once the assault begins."
    blocked = action_blocked(conn, player_id)
    if blocked:
        return False, blocked
    row = conn.execute(
        "SELECT status FROM crown_war_slots WHERE war_id = ? AND clan_id = ?",
        (war["id"], clan_id),
    ).fetchone()
    if not row or row[0] not in ("reserved", "confirmed"):
        return False, "Your guild must hold the war slot to allocate supplies."
    cleaned = {}
    for bucket in ALLOC_BUCKETS:
        if bucket not in mapping:
            return False, f"Missing allocation for {bucket}."
        try:
            pct = int(mapping[bucket])
        except (TypeError, ValueError):
            return False, f"Bad percentage for {bucket}."
        if pct < 0 or pct > 100:
            return False, "Percentages must be between 0 and 100."
        cleaned[bucket] = pct
    if sum(cleaned.values()) != 100:
        return False, f"Allocations must sum to 100 (got {sum(cleaned.values())})."
    for bucket, pct in cleaned.items():
        conn.execute(
            "INSERT INTO crown_war_alloc (war_id, clan_id, bucket, pct) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(war_id, clan_id, bucket) DO UPDATE SET pct = excluded.pct",
            (war["id"], clan_id, bucket, pct),
        )
    conn.commit()
    parts = ", ".join(f"{b} {cleaned[b]}%" for b in ALLOC_BUCKETS)
    return True, f"War storehouse allocation set: {parts}."


def contrib_board(conn, war_id=None, limit=10):
    war = current_war(conn) if war_id is None else (
        {"id": int(war_id)} if war_id else None
    )
    if war_id is not None and not isinstance(war, dict):
        war = {"id": int(war_id)}
    if not war:
        war = current_war(conn)
    if not war:
        return []
    # Prefer supply points, then kills, then deposits.
    try:
        rows = conn.execute(
            "SELECT c.player_id, p.char_name, c.points, c.deposits, c.clan_id, "
            "COALESCE(c.kills, 0) "
            "FROM crown_war_contrib c LEFT JOIN players p ON p.id = c.player_id "
            "WHERE c.war_id = ? ORDER BY c.points DESC, COALESCE(c.kills, 0) DESC, "
            "c.deposits DESC, c.player_id LIMIT ?",
            (int(war["id"]), int(limit)),
        ).fetchall()
    except Exception:
        rows = conn.execute(
            "SELECT c.player_id, p.char_name, c.points, c.deposits, c.clan_id, 0 "
            "FROM crown_war_contrib c LEFT JOIN players p ON p.id = c.player_id "
            "WHERE c.war_id = ? ORDER BY c.points DESC, c.deposits DESC, c.player_id "
            "LIMIT ?",
            (int(war["id"]), int(limit)),
        ).fetchall()
    out = []
    for i, (pid, name, points, deposits, clan_id, kills) in enumerate(rows, 1):
        out.append({
            "rank": i,
            "player_id": int(pid),
            "name": name or f"#{pid}",
            "points": int(points),
            "deposits": int(deposits),
            "kills": int(kills or 0),
            "clan_id": int(clan_id),
            "guild": _clan_name(conn, clan_id),
        })
    return out


def structure_lines(conn):
    """Engineering survey — design: Engineers reveal defensive weak points.

    Damaged / heavily damaged / destroyed structures are listed first so the
    assault window and Herald Engineering survey call out soft spots.
    """
    lines = ["Engineering survey — Crownfall structure report:"]
    structs = [s for s in list_structures(conn) if s]
    order = {"destroyed": 0, "heavily_damaged": 1, "damaged": 2, "intact": 3}
    weak = [s for s in structs if s["state"] != "intact"]
    weak.sort(key=lambda s: (order.get(s["state"], 9), s["name"]))
    intact = [s for s in structs if s["state"] == "intact"]
    if weak:
        lines.append("Weak points:")
        for s in weak:
            pct = int(100 * s["hp"] / max(1, s["max_hp"]))
            bit = f"  {s['name']}: {s['state']} ({s['hp']}/{s['max_hp']}, {pct}%)"
            # Design damage bands: progressive devastation stays visible.
            if s["state"] == "destroyed":
                bit += " — rubble and a changed battlefield"
                if s.get("effect"):
                    bit += f" ({s['effect']})"
            elif s["state"] == "heavily_damaged":
                bit += " — missing sections, fire and debris"
            elif s["state"] == "damaged":
                bit += " — cracks and smoke"
            lines.append(bit)
        if len(weak) >= 2:
            lines.append(
                "Damage is persistent — the castle grows more devastated as the battle develops."
            )
    if intact:
        if weak:
            lines.append("Still holding:")
        for s in intact:
            pct = int(100 * s["hp"] / max(1, s["max_hp"]))
            lines.append(
                f"  {s['name']}: intact ({s['hp']}/{s['max_hp']}, {pct}%)"
            )
    if not structs:
        lines.append("  No structures recorded.")
    if walls_breached(conn):
        lines.append("A wall or gate breach is open.")
    else:
        lines.append("No wall/gate breach yet.")
    return lines


def assault_time_left(war, now=None):
    """Seconds remaining in an active assault, or None."""
    now = time.time() if now is None else float(now)
    if not war or war.get("status") != "active":
        return None
    started = war.get("started_at") or war.get("scheduled_at")
    if not started:
        return None
    return max(0, int(float(started) + ASSAULT_SECONDS - now))


def requirement_lines():
    """Public resource costs for siege engines and repairs (both sides can see)."""
    lines = ["Siege resource requirements (shared storehouse materials):"]
    for wid, spec in WEAPONS.items():
        cost = ", ".join(f"{v} {k}" for k, v in spec["cost"].items())
        lines.append(f"  {spec['name']}: {cost}")
    lines.append(
        f"  Repair batch (+{REPAIR_BATCH_HP} HP): "
        + ", ".join(f"{v} {k}" for k, v in REPAIR_COST.items())
        + " (defenders)"
    )
    lines.append("War Forge kits (personal gear sealed for the assault; spend reserve):")
    for _gid, spec in FORGE_GRADES.items():
        cost = ", ".join(f"{v} {k}" for k, v in spec["cost"].items())
        lines.append(
            f"  {spec['name']}: Smithing {spec['smithing_req']}+ · {cost}"
        )
    lines.append(
        "Any fighter on your side may craft, fire, repair, forge, or deploy. "
        "Engineering (with some Smithing) operates engines and repairs more effectively. "
        "Mining, Woodcutting, and Smithing raise contribution when you deposit matching supplies."
    )
    return lines


def board_lines(conn, player_id=None, now=None):
    """Full war board for the client panel / Herald."""
    now = time.time() if now is None else float(now)
    lines = list(war_lines(conn, now))
    war = current_war(conn)
    if war and war["status"] == "scheduled" and war.get("scheduled_at") is not None:
        start_at = assault_starts_at(war)
        left = max(0, int(start_at - now)) if start_at is not None else 0
        utc_bit = f", {utc_stamp(start_at)}" if start_at is not None else ""
        lines.append(
            f"Assault window: begins in {left // HOUR}h {(left % HOUR) // 60}m{utc_bit} "
            f"(attack Leader: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h "
            "or /siege begin)."
        )
    # Design: monthly siege calendar (late-month registration / Day 30 siege).
    if war and war["status"] in ("registration", "scheduled", "active"):
        lines.extend(monthly_calendar_lines(conn, now=now))
    # Design: siege preparation — register, alliances form, deposit, craft, reinforce, scout.
    if war and war["status"] in ("registration", "scheduled"):
        lines.append(
            "Preparation: guilds register · fighters /siege enlist + /siege attend · "
            "Leaders form alliances (/siege ally <guild>, /siege accept) · "
            "deposit war supplies · War Forge kits (/siege forge) · "
            "craft rams, ladders, siege towers · defenders reinforce gates/walls "
            "(/siege repair) · Engineers /siege survey weak points · "
            f"attack Leader sets the coordinated assault window "
            f"(/siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h)."
        )
        # Design: community roles — guild leaders organise; non-PvP players still matter.
        lines.append(
            "Community roles: Guild leaders organise attack or defence · "
            "Infantry, Archers, Healers, Engineers, Heavy fighters · "
            "Miners gather ore/stone · Smiths forge kits and engines · "
            "Woodcutters supply timber · War Forge locks when the assault begins."
        )
    if war and war["status"] in ("registration", "scheduled", "active"):
        # Design: human/mercenary numbers visible to both leaders before roster locks.
        lines.extend(army_composition_lines(conn, war, now=now))
        # Milestone 8: interest management + profiled roster/fan-out caps.
        lines.extend(interest_profile_lines(conn, war))
        # Design: King genuinely defendable — duties + death does not auto-fall.
        lines.extend(king_defend_lines(conn, player_id, war, now=now))
        if war["status"] == "active":
            lines.append(
                "Recruit contracts are locked for the assault — "
                "no new hires or dismissals until Crownfall."
            )
            lines.append(
                f"Focus fire: at most {SIEGE_MAX_ATTACKERS} attackers may deal "
                "direct damage to one fighter. Area hits still splash at reduced power."
            )
            lines.extend(battlefield_effects_lines(conn))
        if str(war.get("scale") or "") == "small":
            lines.append(
                f"Smaller-scale war — human minimum {SMALL_SCALE_HUMAN_MIN} per side "
                f"(full roster needs {HUMAN_MIN})."
            )
        elif int(war.get("postpones") or 0) >= 1 and war["status"] == "scheduled":
            lines.append(
                f"Under-strength postpone used — next window may run at a smaller scale "
                f"({SMALL_SCALE_HUMAN_MIN}+ humans), or field {HUMAN_MIN}+ for a full assault."
            )
    # Supplies + costs stay public before the roster locks and through the assault.
    # Keep room for both sides' stock / alloc / spent lines plus costs + suppliers.
    if war and war["status"] in ("registration", "scheduled", "active"):
        lines.extend(store_lines(conn, player_id, now, include_costs=True)[:14])
    if war and war["status"] == "active":
        left = assault_time_left(war, now)
        if left is not None:
            lines.append(
                f"Assault clock: {left // HOUR}h {(left % HOUR) // 60}m remaining "
                f"(defenders win if time runs out)."
            )
        # Design: public war progress board — territory contest during the assault.
        lines.extend(capture_board_lines(conn, war["id"]))
        board = contrib_board(conn, war["id"], limit=5)
        if board:
            lines.append(
                "Top fighters: "
                + " · ".join(
                    f"{e['name']} {e['points']}pts/{e['kills']}k"
                    for e in board
                )
            )
        elim_rows = conn.execute(
            "SELECT e.player_id, COALESCE(p.char_name, '#' || e.player_id) "
            "FROM crown_war_elim e "
            "LEFT JOIN players p ON p.id = e.player_id "
            "WHERE e.war_id = ? ORDER BY e.eliminated_at, e.player_id",
            (war["id"],),
        ).fetchall()
        n_elim = len(elim_rows)
        lines.append(f"Eliminated this siege: {n_elim}.")
        if elim_rows:
            names = [str(r[1]) for r in elim_rows[:8]]
            extra = n_elim - len(names)
            bit = ", ".join(names)
            if extra > 0:
                bit += f" (+{extra} more)"
            lines.append(f"  Fallen: {bit}.")
        # Compact weak-point summary for the public board.
        weak = [
            s["name"] for s in list_structures(conn)
            if s and s["state"] in ("heavily_damaged", "destroyed")
        ]
        if weak:
            lines.append("Weakened: " + ", ".join(weak) + ".")
    h = castle_heraldry(conn)
    if h and h.get("banner"):
        lines.append(
            f"Royal banner charge: {(h.get('banner') or {}).get('charge', 'arms')}."
        )
    return lines


def store_lines(conn, player_id=None, now=None, include_costs=False):
    """Herald / chat lines for the war storehouse and contribution board."""
    tick_wars(conn, now)
    war = current_war(conn)
    if not war:
        return ["No War for the Crown is open — the storehouse is sealed."]
    lines = ["War Storehouse — deposits earn contribution (combat is not the only path)."]
    # Design: leader sees stock and allocates; cannot withdraw deposits for personal use.
    lines.append(
        "Deposits cannot be withdrawn for personal use — the lead Leader allocates "
        "stock to rams, ladders, barricades, and reserve only."
    )
    if include_costs:
        # Compact one-liners so the board stays readable.
        cost_bits = []
        for wid, spec in WEAPONS.items():
            cost = "+".join(f"{v}{k[0]}" for k, v in spec["cost"].items())
            cost_bits.append(f"{spec['name']} {cost}")
        lines.append("Costs: " + " · ".join(cost_bits))
        lines.append(
            f"Repair +{REPAIR_BATCH_HP} HP: "
            + "+".join(f"{v}{k[0]}" for k, v in REPAIR_COST.items())
            + " (defend)"
        )
    for side in SIDES:
        lead = _lead_slot(conn, war["id"], side)
        if not lead:
            lines.append(f"{side.title()}: no lead guild yet.")
            continue
        stock = store_stock(conn, war["id"], lead["clan_id"])
        alloc = store_alloc(conn, war["id"], lead["clan_id"])
        mercs = _alliance_mercs(conn, war["id"], lead["clan_id"], side) if lead else 0
        humans = _alliance_humans(conn, war["id"], lead["clan_id"], side) if lead else 0
        lines.append(
            f"{side.title()} ({lead['name']}): timber {stock['timber']} · ore {stock['ore']} · "
            f"bars {stock['bars']} · stone {stock['stone']} "
            f"· roster {humans}h/{mercs}m"
        )
        lines.append(
            "  Alloc: " + " · ".join(f"{b} {alloc[b]}%" for b in ALLOC_BUCKETS)
        )
        # Spent vs timber budget so both sides see remaining room before / during assault.
        spend = alloc_status(conn, war["id"], lead["clan_id"])
        if any(spend[b]["resources"]["timber"]["budget"] > 0 for b in ALLOC_BUCKETS):
            bits = [
                f"{b} {spend[b]['resources']['timber']['spent']}/"
                f"{spend[b]['resources']['timber']['budget']}t"
                for b in ALLOC_BUCKETS
            ]
            lines.append("  Spent (timber): " + " · ".join(bits))
    board = contrib_board(conn, war["id"], limit=5)
    if board:
        lines.append(
            "Top suppliers: "
            + " · ".join(f"{e['name']} {e['points']}pts" for e in board)
        )
    else:
        lines.append("No supplies deposited yet. /siege deposit <item> <qty>")
    return lines


def handle_command(conn, player_id, text):
    """Parse /siege …  Returns (ok, list_of_reply_lines)."""
    parts = (text or "").split()
    if not parts:
        return True, war_lines(conn)
    cmd = parts[0].lower().lstrip("/")
    if cmd != "siege":
        return False, ["Unknown command."]
    sub = parts[1].lower() if len(parts) > 1 else "status"
    if sub in ("status", "board", "info"):
        return True, board_lines(conn, player_id)
    if sub == "register":
        side = parts[2].lower() if len(parts) > 2 else ""
        ok, msg, *_rest = _pack_register(conn, player_id, side)
        return ok, [msg]
    if sub == "confirm":
        ok, msg = confirm(conn, player_id)
        return ok, [msg]
    if sub in ("enlist", "signup", "joinfight"):
        role = parts[2].lower() if len(parts) > 2 else "infantry"
        ok, msg = enlist(conn, player_id, role=role)
        return ok, [msg]
    if sub in ("attend", "ready", "here"):
        ok, msg = attend(conn, player_id)
        return ok, [msg]
    if sub == "role":
        if len(parts) < 3:
            return False, [
                "Usage: /siege role <"
                + "|".join(BATTLE_ROLES)
                + ">  (before you /siege attend)"
            ]
        ok, msg = set_fighter_role(conn, player_id, parts[2].lower())
        return ok, [msg]
    if sub in ("forge", "warforge", "kit", "outfit"):
        # /siege forge → panel; /siege forge reinforced → craft
        if len(parts) < 3 or parts[2].lower() in ("info", "panel", "help"):
            return True, forge_lines(conn, player_id)
        ok, msg = forge_equipment(conn, player_id, grade=parts[2].lower())
        return ok, [msg]
    if sub in ("roles", "rolelist", "rosterroles"):
        return True, role_roster_lines(conn)
    if sub in ("panels", "councilpanels"):
        panels = war_council_panels(conn, player_id)
        lines = ["War Council panels:"]
        for key in ("army", "roles", "equipment", "storehouse", "castle", "objectives", "battle"):
            panel = panels.get(key) or {}
            lines.append(f"— {panel.get('title', key)} —")
            for ln in panel.get("lines") or ["(empty)"]:
                lines.append(f"  {ln}")
        return True, lines
    if sub == "forfeit":
        ok, msg = forfeit(conn, player_id)
        return ok, [msg]
    if sub == "ally":
        name = " ".join(parts[2:]).strip()
        if not name:
            return False, ["Usage: /siege ally <guild name>"]
        ok, msg = invite_ally(conn, player_id, name)
        return ok, [msg]
    if sub == "accept":
        ok, msg = respond_ally(conn, player_id, True)
        return ok, [msg]
    if sub == "decline":
        ok, msg = respond_ally(conn, player_id, False)
        return ok, [msg]
    if sub == "open":
        if not _is_leader(conn, player_id):
            return False, ["Only a guild Leader can open registration."]
        ok, msg, _w = open_registration(conn)
        return ok, [msg]
    if sub in ("store", "storehouse", "supplies"):
        return True, store_lines(conn, player_id, include_costs=True)
    if sub in ("costs", "requirements", "recipes"):
        return True, requirement_lines()
    if sub in ("withdraw", "take", "retrieve"):
        return False, [
            "War storehouse deposits cannot be withdrawn for personal use. "
            "The lead Leader allocates stock with /siege alloc — materials stay in the war."
        ]
    if sub == "deposit":
        if len(parts) < 4:
            return False, ["Usage: /siege deposit <item> <qty>"]
        item_id = parts[2].lower()
        try:
            qty = int(parts[3])
        except ValueError:
            return False, ["Quantity must be a number."]
        # Inventory removal is applied by the server wrapper when a session is live.
        ok, msg = deposit(conn, player_id, item_id, qty)
        return ok, [msg]
    if sub == "alloc":
        # /siege alloc  → show current % and timber spent/budget
        # /siege alloc rams=40 ladders=25 barricades=20 reserve=15
        if len(parts) < 3:
            war = current_war(conn)
            clan_id = _clan_of(conn, player_id)
            if not war or not clan_id:
                return False, ["No open war, or you have no guild."]
            side, lead_id = _player_war_side(conn, war["id"], clan_id)
            if not side or not lead_id:
                return False, ["Your guild must be registered or allied to view allocations."]
            alloc = store_alloc(conn, war["id"], lead_id)
            lines = [
                "War storehouse allocation — "
                + " · ".join(f"{b} {alloc[b]}%" for b in ALLOC_BUCKETS),
                "Timber spent/budget: "
                + " · ".join(_alloc_board_bits(conn, war["id"], lead_id)),
            ]
            if war.get("status") == "active":
                lines.append("Allocations are locked for the assault.")
            else:
                lines.append(
                    "Rebalance with /siege alloc rams=40 ladders=25 barricades=20 reserve=15"
                )
            return True, lines
        mapping = {}
        for bit in parts[2:]:
            if "=" not in bit:
                return False, ["Usage: /siege alloc rams=40 ladders=25 barricades=20 reserve=15"]
            k, _, v = bit.partition("=")
            mapping[k.lower()] = v
        ok, msg = set_allocation(conn, player_id, mapping)
        return ok, [msg]
    if sub in ("report", "battle", "battlereport"):
        return True, battle_report_lines(conn, now=time.time())
    if sub in ("contrib", "contribution", "suppliers"):
        board = contrib_board(conn)
        if not board:
            return True, ["No war contributions recorded yet."]
        return True, [
            f"#{e['rank']} {e['name']} ({e['guild']}) — {e['points']} pts, "
            f"{e['kills']} kills, {e['deposits']} items"
            for e in board
        ]
    if sub == "craft":
        if len(parts) < 3:
            return False, [f"Usage: /siege craft <{'|'.join(WEAPONS)}> [qty]"]
        weapon_id = parts[2].lower()
        qty = 1
        if len(parts) >= 4:
            try:
                qty = int(parts[3])
            except ValueError:
                return False, ["Quantity must be a number."]
        ok, msg = craft_weapon(conn, player_id, weapon_id, qty)
        return ok, [msg]
    if sub == "fire":
        if len(parts) < 4:
            return False, [
                "Usage: /siege fire <weapon> <structure>  "
                f"weapons={','.join(WEAPONS)} structures={','.join(_BY_ID)}"
            ]
        ok, msg, _meta = fire_weapon(conn, player_id, parts[2].lower(), parts[3].lower())
        return ok, [msg]
    if sub == "repair":
        if len(parts) < 3:
            return False, [
                f"Usage: /siege repair <structure> [batches]  structures={','.join(_BY_ID)}"
            ]
        batches = 1
        if len(parts) >= 4:
            try:
                batches = int(parts[3])
            except ValueError:
                return False, ["Batches must be a number."]
        ok, msg, _meta = repair_structure(conn, player_id, parts[2].lower(), batches)
        return ok, [msg]
    if sub in ("weapons", "engines"):
        war = current_war(conn)
        clan_id = _clan_of(conn, player_id)
        if not war or not clan_id:
            return True, ["No weapons stocked."]
        _side, lead_id = _player_war_side(conn, war["id"], clan_id)
        if not lead_id:
            return True, ["Your guild is not in this war."]
        stock = weapon_stock(conn, war["id"], lead_id)
        return True, [
            "Siege engines: "
            + ", ".join(f"{WEAPONS[w]['name']}×{stock[w]}" for w in WEAPONS)
        ]
    if sub in ("begin", "assault", "start"):
        ok, msg = begin_assault(conn, player_id)
        return ok, [msg]
    if sub in ("roster", "army", "composition"):
        war = current_war(conn)
        if not war:
            return True, ["No War for the Crown is open."]
        lines = army_composition_lines(conn, war)
        need = effective_human_min(war)
        lines.append(
            f"Human minimum: {need} "
            f"(full {HUMAN_MIN}; smaller scale {SMALL_SCALE_HUMAN_MIN} after postpone)."
        )
        if war.get("status") != "active":
            lines.append("Roster locks when the assault begins.")
        else:
            lines.append("Roster is locked for this assault.")
        return True, lines
    if sub in ("when", "window", "schedule"):
        # Design: attacking alliance selects a coordinated assault window.
        if len(parts) < 3:
            return False, [
                f"Usage: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h  "
                "(attack Leader sets when the assault begins)"
            ]
        raw = parts[2].lower().rstrip("h")
        if raw.endswith("d"):
            try:
                raw_h = int(raw[:-1]) * 24
            except ValueError:
                return False, [
                    f"Usage: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h"
                ]
            ok, msg = set_assault_window(conn, player_id, raw_h)
            return ok, [msg]
        try:
            hours = int(raw)
        except ValueError:
            return False, [
                f"Usage: /siege when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h"
            ]
        ok, msg = set_assault_window(conn, player_id, hours)
        return ok, [msg]
    if sub in ("scout", "survey", "structures", "damage", "weak", "engineering"):
        # /siege scout kept as alias; Engineering survey is the design name.
        return True, structure_lines(conn)
    if sub in ("barricade", "barricades", "fortify"):
        if len(parts) < 3:
            return False, [
                f"Usage: /siege barricade <{'|'.join(CAPTURE_ORDER)}>  "
                "(defenders deploy crafted barricades onto a capture point)"
            ]
        ok, msg = deploy_barricade(conn, player_id, parts[2].lower())
        return ok, [msg]
    if sub in ("guard", "guards", "post"):
        if len(parts) < 3:
            return False, [
                f"Usage: /siege guard <{'|'.join(CAPTURE_ORDER)}>  "
                "(defenders post a Guard recruit onto a capture point)"
            ]
        ok, msg = deploy_guard(conn, player_id, parts[2].lower())
        return ok, [msg]
    if sub in ("royalguard", "royalguards", "rg"):
        # Design: limited appointed players who can protect the King.
        if len(parts) < 3:
            return True, royal_guard_lines(conn)
        action = parts[2].lower()
        if action == "dismiss":
            name = " ".join(parts[3:]).strip()
            if not name:
                return False, ["Usage: /siege royalguard dismiss <name>"]
            ok, msg = dismiss_royal_guard(conn, player_id, name)
            return ok, [msg]
        name = " ".join(parts[2:]).strip()
        ok, msg = appoint_royal_guard(conn, player_id, name)
        return ok, [msg]
    if sub in ("capture", "captures", "points"):
        war = current_war(conn)
        if not war:
            return True, ["No war is open."]
        lines = [
            f"Capture points ({war['status']}) — attack order: "
            + " → ".join(CAPTURE_POINTS[p]["name"] for p in CAPTURE_ORDER)
        ]
        for p in capture_state(conn, war["id"]):
            hold = ""
            if p["id"] == "throne" and p["owner"] == "attack" and p.get("hold_started_at"):
                hold = f", holding {int(time.time() - p['hold_started_at'])}s/{p['hold_seconds']}s"
            grd = f", guards {p['guards']}" if p.get("guards") else ""
            bar = f", barricades {p['barricades']}" if p.get("barricades") else ""
            lock = "" if p.get("unlocked_for_attack") else ", locked for attack"
            lines.append(
                f"  {p['name']}: {p['owner']} "
                f"({p['progress']}/{p['need']}{hold}{grd}{bar}{lock})"
            )
        return True, lines
    if sub in ("council", "works"):
        return True, council_lines(conn, player_id)
    if sub in ("heraldry", "banner"):
        h = castle_heraldry(conn)
        if not h:
            return True, ["No siege heraldry flies yet — win the War for the Crown."]
        return True, [
            f"King's Castle heraldry set by player #{h['player_id']} "
            f"(banner charge: {(h.get('banner') or {}).get('charge', 'unknown')}). "
            "Regal robes unlock at Mae's for the victor."
        ]
    return False, [
        "Usage: /siege [status|register attack|register defend|"
        "enlist [role]|attend|role <"
        + "|".join(BATTLE_ROLES)
        + ">|roles|forge [standard|reinforced|masterwork]|panels|confirm|forfeit|"
        "ally <guild>|accept|decline|open|store|costs|report|deposit <item> <qty>|"
        "alloc rams=.. ladders=.. barricades=.. reserve=..|contrib|"
        "craft <weapon> [qty]|fire <weapon> <structure>|barricade <point>|"
        "guard <point>|royalguard <name>|royalguard dismiss <name>|"
        "repair <structure>|survey|weapons|begin|roster|"
        f"when <{ASSAULT_WINDOW_MIN_H}-{ASSAULT_WINDOW_MAX_H}>h|captures|council|heraldry]"
    ]


def _pack_register(conn, player_id, side):
    result = register(conn, player_id, side)
    # register returns (ok, msg) or (ok, msg, slot)
    ok = result[0]
    msg = result[1]
    return ok, msg, result[2] if len(result) > 2 else None
