"""The Endless Depths — one reused private room, theme plates, scaled MONSTERS.

Petaldeep-style single-room swap: same tiles every floor; theme, spawns, and
scaled MonsterInstance stats change. Progression door north; south leaves.
"""
from __future__ import annotations

import json
import math
import time

DUNGEON_ID = "endless_depths"
SPEAKER = "Endless Depths"

# Village landmark — east of the bank / south of the Crypt approach.
MOUTH = (11, 21)
STAND = (11, 23)

# Default client map is 900×640 at TILE=40 → 22×16 tiles.
W, H = 22, 16
CX = W // 2  # 11
SPAWN = (CX, H - 3)
EXIT = (CX, H - 2)
DOOR = ((CX - 1, 1), (CX, 1), (CX + 1, 1))
ROOM_BOX = (1, 1, W - 2, H - 2)

THEMES = (
    "crypt", "catacomb", "frozen", "toxic", "volcanic",
    "demonic", "shadow", "forest", "dragon", "cosmic",
)

# Theme → environmental hazard. Selected floors (every 5th, or themed) apply it.
THEME_HAZARD = {
    "toxic": "poison",
    "catacomb": "poison",
    "volcanic": "fire",
    "dragon": "fire",
    "demonic": "fire",
    "frozen": "freeze",
    "shadow": "darkness",
    "cosmic": "darkness",
    "forest": "roots",
    "crypt": None,
}

HAZARD_LABEL = {
    "poison": "Poison mist",
    "fire": "Searing heat",
    "freeze": "Biting frost",
    "darkness": "Smothering dark",
    "roots": "Grasping roots",
}

HAZARD_TIP = {
    "poison": "Poison mist — keep food ready.",
    "fire": "Searing heat — don't linger without healing.",
    "freeze": "Biting frost — your steps may lock.",
    "darkness": "Smothering dark — stay near the centre.",
    "roots": "Grasping roots — expect to be held.",
}

THEME_AMBIENT = {
    "crypt": (
        "Dust and bone grit underfoot.",
        "Something older than kings sleeps here.",
        "Torchlight dies in the vaulted dark.",
    ),
    "catacomb": (
        "Stacked niches stare from every wall.",
        "The air tastes of old incense and mould.",
        "Footfalls echo where processions once walked.",
    ),
    "frozen": (
        "Breath hangs white in the still cold.",
        "Ice webs the stone like frozen lace.",
        "A wind that should not exist finds you.",
    ),
    "toxic": (
        "Green vapour curls along the floor.",
        "Your throat catches on every breath.",
        "Something alive thrives in this poison.",
    ),
    "volcanic": (
        "Heat rolls off the cracked basalt.",
        "Ash settles on your gear between blinks.",
        "The floor thrums with buried fire.",
    ),
    "demonic": (
        "The walls sweat a ruddy light.",
        "A laugh without a throat brushes past.",
        "Your shadow does not quite match your steps.",
    ),
    "shadow": (
        "Light forgets itself a pace ahead.",
        "Shapes peel from the gloom and wait.",
        "You feel watched from no particular direction.",
    ),
    "forest": (
        "Roots force the masonry apart.",
        "Leaves that never saw sun whisper overhead.",
        "The chamber smells of wet earth and sap.",
    ),
    "dragon": (
        "Scorch marks claw up the pillars.",
        "A scale the size of a shield lies half-buried.",
        "The air tastes of copper and old fire.",
    ),
    "cosmic": (
        "Stars wheel where a ceiling should be.",
        "Distance refuses to stay honest.",
        "A soft hum sits behind your thoughts.",
    ),
}

THEME_FIRST_CLEAR_COINS = 40
THEME_FIRST_CLEAR_XP = 25

# Shared multiplayer runs (party_id or solo run key) → run dict.
_RUNS = {}

# Fixed combat pads inside the room (avoid door/exit/spawn).
SPAWN_PADS = (
    (5, 5), (9, 5), (13, 5), (17, 5),
    (5, 8), (11, 7), (17, 8),
    (8, 10),
)

PROP_SPOTS = (
    {"x": 3, "y": 4, "kind": "torch"},
    {"x": 18, "y": 4, "kind": "torch"},
    {"x": 3, "y": 11, "kind": "pillar"},
    {"x": 18, "y": 11, "kind": "pillar"},
    {"x": 7, "y": 3, "kind": "torch"},
    {"x": 15, "y": 3, "kind": "torch"},
)

MILESTONES = (10, 25, 50, 75, 100, 150, 200)
N_EFF_CAP = 200

# Clear reward soft-caps (per floor advance).
COIN_SOFT_CAP = 4000
XP_SOFT_CAP = 2500

# Scaling knobs (plan formulas).
HP_A, HP_B = 0.10, 0.0005
DMG_A, DMG_B = 0.08, 0.00035
R_A, R_B = 0.06, 0.0002

DUNGEON_SPAWN = SPAWN
CAVE_RETURN = STAND


def _srv():
    import server
    return server


def here(session):
    return bool(session.dungeon) and session.dungeon.get("id") == DUNGEON_ID


def theme_for(floor: int) -> str:
    n = max(1, int(floor))
    return THEMES[(n - 1) % len(THEMES)]


def is_boss_floor(floor: int) -> bool:
    n = max(1, int(floor))
    return n % 10 == 0


def is_milestone_floor(floor: int) -> bool:
    return max(1, int(floor)) in MILESTONES


def ambient_line(theme: str, floor: int = 1) -> str:
    lines = THEME_AMBIENT.get(theme) or THEME_AMBIENT["crypt"]
    idx = (max(1, int(floor)) - 1) % len(lines)
    return lines[idx]


def n_eff(floor: int) -> int:
    return min(max(1, int(floor)), N_EFF_CAP)


def hp_mult(floor: int) -> float:
    """H(n) — HP scale curve."""
    n = n_eff(floor)
    return 1.0 + HP_A * n + HP_B * (n * n)


def dmg_mult(floor: int) -> float:
    """Damage / att / str / def multiplier."""
    n = n_eff(floor)
    return 1.0 + DMG_A * n + DMG_B * (n * n)


def reward_mult(floor: int) -> float:
    """R(n) — clear reward / XP bonus curve."""
    n = n_eff(floor)
    return 1.0 + R_A * n + R_B * (n * n)


def difficulty_tier(floor: int) -> str:
    n = max(1, int(floor))
    if n < 10:
        return "Nascent"
    if n < 25:
        return "Deepening"
    if n < 50:
        return "Abyssal"
    if n < 100:
        return "Infernal"
    if n < 150:
        return "Mythic"
    return "Endless"


def next_milestone(floor: int, claimed) -> int | None:
    claimed = set(claimed or [])
    for m in MILESTONES:
        if m > int(floor) and m not in claimed:
            return m
        if m == int(floor) and m not in claimed:
            return m
    for m in MILESTONES:
        if m not in claimed:
            return m
    return None


# --------------------------------------------------------------------------- db
def ensure_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS endless_depths ("
        " player_id INTEGER PRIMARY KEY,"
        " highest_floor INTEGER NOT NULL DEFAULT 0,"
        " solo_highest_floor INTEGER NOT NULL DEFAULT 0,"
        " continue_floor INTEGER NOT NULL DEFAULT 0,"
        " milestones_claimed TEXT NOT NULL DEFAULT '[]',"
        " themes_cleared TEXT NOT NULL DEFAULT '[]',"
        " title TEXT NOT NULL DEFAULT '',"
        " updated_at REAL NOT NULL DEFAULT 0)"
    )
    # Older DBs created before solo hiscores / continue checkpoint / theme clears.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(endless_depths)")}
    if "solo_highest_floor" not in cols:
        conn.execute(
            "ALTER TABLE endless_depths ADD COLUMN solo_highest_floor INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
        cols.add("solo_highest_floor")
    if "continue_floor" not in cols:
        conn.execute(
            "ALTER TABLE endless_depths ADD COLUMN continue_floor INTEGER NOT NULL DEFAULT 0"
        )
        # Seed from deepest recorded floor so existing players get a continue prompt.
        conn.execute(
            "UPDATE endless_depths SET continue_floor = "
            "CASE WHEN solo_highest_floor > highest_floor THEN solo_highest_floor "
            "ELSE highest_floor END "
            "WHERE continue_floor = 0 AND (highest_floor > 1 OR solo_highest_floor > 1)"
        )
        conn.commit()
        cols.add("continue_floor")
    if "themes_cleared" not in cols:
        conn.execute(
            "ALTER TABLE endless_depths ADD COLUMN themes_cleared TEXT NOT NULL DEFAULT '[]'"
        )
        conn.commit()


def _parse_json_list(raw):
    try:
        val = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return list(val) if isinstance(val, list) else []


def _row(conn, pid):
    ensure_table(conn)
    r = conn.execute(
        "SELECT highest_floor, milestones_claimed, title, solo_highest_floor, "
        "continue_floor, themes_cleared "
        "FROM endless_depths WHERE player_id=?",
        (pid,),
    ).fetchone()
    if r is None:
        conn.execute("INSERT OR IGNORE INTO endless_depths (player_id) VALUES (?)", (pid,))
        conn.commit()
        return {
            "highest_floor": 0,
            "solo_highest_floor": 0,
            "continue_floor": 0,
            "milestones_claimed": [],
            "themes_cleared": [],
            "title": "",
        }
    return {
        "highest_floor": int(r[0] or 0),
        "milestones_claimed": [int(x) for x in _parse_json_list(r[1])],
        "title": r[2] or "",
        "solo_highest_floor": int(r[3] or 0),
        "continue_floor": int(r[4] or 0),
        "themes_cleared": [str(x) for x in _parse_json_list(r[5])],
    }


def _set(conn, pid, **fields):
    _row(conn, pid)
    payload = dict(fields)
    for key in ("milestones_claimed", "themes_cleared"):
        if key in payload and not isinstance(payload[key], str):
            payload[key] = json.dumps(list(payload[key]))
    payload["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in payload)
    conn.execute(
        f"UPDATE endless_depths SET {cols} WHERE player_id=?",
        (*payload.values(), pid),
    )
    conn.commit()


def load(session):
    """Cache highest floor + title on the session (login / after persist)."""
    srv = _srv()
    try:
        row = _row(srv.WORLD.db.conn, session.player_id)
    except Exception:
        return
    session.endless_highest = row["highest_floor"]
    session.endless_solo_highest = row["solo_highest_floor"]
    session.endless_continue = row["continue_floor"]
    session.endless_milestones = list(row["milestones_claimed"])
    session.endless_themes_cleared = list(row["themes_cleared"])
    session.endless_title = row["title"]


def highest_floor(session) -> int:
    if not hasattr(session, "endless_highest"):
        load(session)
    return int(getattr(session, "endless_highest", 0) or 0)


def solo_highest_floor(session) -> int:
    if not hasattr(session, "endless_solo_highest"):
        load(session)
    return int(getattr(session, "endless_solo_highest", 0) or 0)


def continue_floor(session) -> int:
    """Floor to offer on the next entry prompt (0/1 = no continue)."""
    if not hasattr(session, "endless_continue"):
        load(session)
    n = int(getattr(session, "endless_continue", 0) or 0)
    if n == 0:
        # Older rows with no checkpoint yet — seed from deepest recorded floor.
        n = max(highest_floor(session), solo_highest_floor(session))
    return max(0, n)


def note_continue(session, floor: int):
    """Remember where to resume next time the player enters the mouth."""
    floor = max(1, int(floor))
    cur = int(getattr(session, "endless_continue", 0) or 0)
    if cur == floor:
        return
    session.endless_continue = floor
    srv = _srv()
    try:
        _set(srv.WORLD.db.conn, session.player_id, continue_floor=floor)
    except Exception:
        pass


def milestones_claimed(session) -> list:
    if not hasattr(session, "endless_milestones"):
        load(session)
    return list(getattr(session, "endless_milestones", []) or [])


def themes_cleared(session) -> list:
    if not hasattr(session, "endless_themes_cleared"):
        load(session)
    return list(getattr(session, "endless_themes_cleared", []) or [])


def note_theme_clear(session, theme: str) -> bool:
    """Record first clear of a theme plate. True if this was the first time."""
    theme = str(theme or "")
    if not theme:
        return False
    claimed = themes_cleared(session)
    if theme in claimed:
        return False
    claimed.append(theme)
    session.endless_themes_cleared = claimed
    srv = _srv()
    try:
        _set(srv.WORLD.db.conn, session.player_id, themes_cleared=claimed)
    except Exception:
        return True
    return True


def note_highest(session, floor: int, solo: bool | None = None) -> dict:
    """Bump personal best. Solo runs also feed the Endless Depths hiscores.

    Returns {"highest": bool, "solo": bool} for PB tease chat.
    """
    floor = max(0, int(floor))
    if solo is None:
        st = _state(session) if here(session) else {}
        solo = int(st.get("group_size") or 1) <= 1
    fields = {}
    out = {"highest": False, "solo": False}
    cur = highest_floor(session)
    if floor > cur:
        fields["highest_floor"] = floor
        session.endless_highest = floor
        out["highest"] = True
    if solo:
        scur = solo_highest_floor(session)
        if floor > scur:
            fields["solo_highest_floor"] = floor
            session.endless_solo_highest = floor
            out["solo"] = True
    if not fields:
        return out
    srv = _srv()
    _set(srv.WORLD.db.conn, session.player_id, **fields)
    return out


def leaderboard_rows(conn, limit=50):
    """Hiscores board: solo deepest floor only (each room = one level)."""
    ensure_table(conn)
    limit = max(1, min(50, int(limit or 50)))
    rows = conn.execute(
        "SELECT e.solo_highest_floor AS floor, p.char_name "
        "FROM endless_depths e "
        "JOIN players p ON p.id = e.player_id "
        "WHERE e.solo_highest_floor > 0 "
        "ORDER BY e.solo_highest_floor DESC, p.char_name ASC "
        "LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for row in rows:
        floor = int(row[0] or 0)
        name = row[1] or ""
        out.append({
            "name": name,
            "level": floor,   # hiscores UI: LEVEL column = floor reached
            "xp": floor,      # tie-breaker / display filler
            "floor": floor,
            "guild": "",
        })
    return out


def claim_milestone(session, floor: int) -> dict | None:
    """One-time milestone claim at floor N. Returns reward summary or None."""
    floor = int(floor)
    if floor not in MILESTONES:
        return None
    claimed = milestones_claimed(session)
    if floor in claimed:
        return None
    claimed.append(floor)
    import titles as titles_mod
    _tid, title = titles_mod.ENDLESS_TITLES.get(floor, (f"endless_{floor}", f"Floor {floor}"))
    coins = int(min(COIN_SOFT_CAP, 80 * floor * reward_mult(floor)))
    srv = _srv()
    _set(
        srv.WORLD.db.conn,
        session.player_id,
        milestones_claimed=claimed,
        title=title,
    )
    session.endless_milestones = claimed
    session.endless_title = title
    note_highest(session, floor)  # solo hiscores only when group_size == 1
    if coins > 0:
        srv.WORLD.add_coins(session, coins)
    return {"floor": floor, "title": title, "coins": coins, "title_id": _tid}


# --------------------------------------------------------------------------- monsters
def _eligible_types():
    from content import MONSTERS
    import combat
    out = []
    for mtype, mdef in MONSTERS.items():
        if not mdef:
            continue
        if mdef.get("passive") or mdef.get("requires_pk"):
            continue
        # Training / story-bound combatants that break a small-room AI loop.
        if mtype in ("adamant_duelist", "eclipse_champion"):
            continue
        lvl = combat.monster_combat_level(mdef, mtype)
        out.append((mtype, int(lvl), bool(mdef.get("boss"))))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def _roster():
    """Cached eligible roster sorted by combat level."""
    global _ROSTER
    if not _ROSTER:
        _ROSTER = _eligible_types()
    return _ROSTER


_ROSTER = []


def pick_types(floor: int) -> list[str]:
    """Floor n picks a sliding window into the roster; every 10th is a boss floor."""
    roster = _roster()
    if not roster:
        return ["goblin"]
    n = max(1, int(floor))
    # Window drifts through the list; wraps with stronger variants via scaling.
    span = 8
    start = ((n - 1) * 2) % max(1, len(roster))
    window = []
    for i in range(span):
        window.append(roster[(start + i) % len(roster)])
    count = 3 + ((n - 1) % 4)  # 3..6
    count = min(count, len(SPAWN_PADS), len(window))
    picks = [window[i][0] for i in range(count)]
    if n % 10 == 0:
        bosses = [t for t in window if t[2]]
        boss = bosses[-1][0] if bosses else window[-1][0]
        picks[-1] = boss
    return picks


def group_hp_mult(group_size: int) -> float:
    n = max(1, min(4, int(group_size or 1)))
    return 1.0 + 0.55 * (n - 1)


def group_dmg_mult(group_size: int) -> float:
    n = max(1, min(4, int(group_size or 1)))
    return 1.0 + 0.25 * (n - 1)


def group_reward_mult(group_size: int) -> float:
    """Per-player clear reward bump for grouping (still worth co-op)."""
    n = max(1, min(4, int(group_size or 1)))
    return 1.0 + 0.20 * (n - 1)


def hazard_for(floor: int, theme: str | None = None) -> str | None:
    """Environmental challenge on selected floors (every 5th, or hazard themes)."""
    theme = theme or theme_for(floor)
    kind = THEME_HAZARD.get(theme)
    if not kind:
        return None
    n = max(1, int(floor))
    # Always on matching themes from floor 3+; intensify schedule every 5th.
    if n < 3:
        return None
    return kind


def hazard_intensity(floor: int) -> float:
    n = n_eff(floor)
    base = 1.0 + 0.04 * n
    if int(floor) % 5 == 0:
        base *= 1.35
    return base


def scale_stats(mtype: str, floor: int, group_size: int = 1) -> dict:
    from content import MONSTERS
    import combat
    base = dict(MONSTERS.get(mtype) or {})
    hmul = hp_mult(floor) * group_hp_mult(group_size)
    dmul = dmg_mult(floor) * group_dmg_mult(group_size)
    wraps = max(0, (max(1, int(floor)) - 1) // max(1, len(_roster()) or 1))
    # After a full roster wrap, nudge stats further (no new defs).
    wrap_bonus = 1.0 + 0.12 * wraps
    hp = max(8, int(round(int(base.get("hp") or 10) * hmul * wrap_bonus)))
    att = max(1, int(round(int(base.get("attack") or 1) * dmul * wrap_bonus)))
    strength = max(1, int(round(int(base.get("strength") or 1) * dmul * wrap_bonus)))
    defence = max(1, int(round(int(base.get("defence") or 1) * dmul * wrap_bonus)))
    xp = max(5, int(round(int(base.get("xp") or 10) * reward_mult(floor))))
    level = combat.monster_combat_level(
        {**base, "hp": hp, "attack": att, "strength": strength, "defence": defence},
        mtype,
    )
    # Pin a readable level so the HUD matches the scaled fight.
    level_override = max(1, int(round(level * (1.0 + 0.02 * wraps))))
    return {
        "hp": hp,
        "attack": att,
        "strength": strength,
        "defence": defence,
        "xp": xp,
        "level_override": level_override,
        "def_bonus": int(round(int(base.get("def_bonus") or 0) * dmul)),
    }


# --------------------------------------------------------------------------- room
def dungeon_walkable(tiles, x, y):
    from world_map import FLOOR
    if not tiles or y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


def build_tiles(door_open=False):
    """Build the single reused room.

    North door tiles are always FLOOR so the player can walk onto them.
    ``door_open`` only gates advancement (on_step / interact) — sealing them
    as WALL made "walk to the door" stop one tile short and never descend.
    """
    from world_map import FLOOR, WALL
    tiles = [[WALL for _ in range(W)] for _ in range(H)]
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            tiles[y][x] = FLOOR
    # Door sits on the north rim (already FLOOR from the loop); keep it open.
    for x, y in DOOR:
        tiles[y][x] = FLOOR
    return tiles


def _state(session):
    return (session.dungeon or {}).setdefault("endless_depths", {
        "floor": 1,
        "cleared": False,
        "door_open": False,
        "floor_rewarded": False,
        "theme": THEMES[0],
        "hazard": None,
        "group_size": 1,
        "run_id": None,
    })


def _run_of(session):
    st = _state(session)
    rid = st.get("run_id")
    return _RUNS.get(rid) if rid else None


def _party_sessions(session):
    """Online party members (including self), else just self."""
    import party as party_mod
    srv = _srv()
    ids = party_mod.members(session.player_id)
    out = []
    for pid in ids:
        s = srv.WORLD.sessions.get(pid)
        if s:
            out.append(s)
    return out or [session]


def _near_mouth(session) -> bool:
    return abs(int(session.x) - MOUTH[0]) <= 4 and abs(int(session.y) - MOUTH[1]) <= 4


def _group_size_for_enter(session) -> int:
    """Count party members near the mouth (including self) for scaling."""
    import party as party_mod
    if not party_mod.party_of(session.player_id):
        return 1
    n = 0
    for s in _party_sessions(session):
        if s.dungeon and s.dungeon.get("id") != DUNGEON_ID:
            continue
        if s.dungeon and s.dungeon.get("id") == DUNGEON_ID:
            n += 1
            continue
        if _near_mouth(s):
            n += 1
    return max(1, min(4, n))


def _sync_session_from_run(session, run):
    st = _state(session)
    st["floor"] = run["floor"]
    st["cleared"] = run["cleared"]
    st["door_open"] = run["door_open"]
    st["theme"] = run["theme"]
    st["hazard"] = run.get("hazard")
    st["group_size"] = run.get("group_size") or 1
    st["run_id"] = run["id"]
    st["run_cleared"] = int(run.get("floors_cleared") or 0)
    st["run_coins"] = int(run.get("coins_earned") or 0)
    st["run_start"] = int(run.get("start_floor") or run["floor"])
    st["boss_floor"] = is_boss_floor(run["floor"])
    session.dungeon["tiles"] = run["tiles"]
    session.dungeon["monsters"] = run["monsters"]
    session.dungeon["label"] = run["label"]
    session.dungeon["floor"] = run["floor"]
    session.dungeon["floors"] = run["floor"]
    session.dungeon["exit_x"], session.dungeon["exit_y"] = EXIT
    session.dungeon["width"], session.dungeon["height"] = W, H
    session.dungeon["props"] = [dict(p) for p in PROP_SPOTS]
    session.dungeon["endless_run"] = run["id"]


def _spawn_into(run, floor: int, group_size: int):
    srv = _srv()
    types = pick_types(floor)
    run["monsters"] = {}
    for i, mtype in enumerate(types):
        pad = SPAWN_PADS[i % len(SPAWN_PADS)]
        mid = srv.next_id()
        stats = scale_stats(mtype, floor, group_size=group_size)
        m = srv.MonsterInstance(mid, mtype, pad[0], pad[1], no_respawn=True, stats=stats)
        m.home_room = ROOM_BOX
        run["monsters"][mid] = m


def _make_run(floor: int, group_size: int, member_ids):
    floor = max(1, int(floor))
    theme = theme_for(floor)
    hazard = hazard_for(floor, theme)
    rid = f"ed-{int(time.time() * 1000)}-{member_ids[0]}"
    run = {
        "id": rid,
        "floor": floor,
        "theme": theme,
        "hazard": hazard,
        "cleared": False,
        "door_open": False,
        "group_size": max(1, int(group_size)),
        "member_ids": list(member_ids),
        "rewarded": set(),
        "tiles": build_tiles(door_open=False),
        "monsters": {},
        "label": f"Floor {floor} — {theme.title()}",
        "start_floor": floor,
        "floors_cleared": 0,
        "coins_earned": 0,
        "xp_earned": 0,
    }
    if hazard:
        run["label"] += f" [{HAZARD_LABEL.get(hazard, hazard)}]"
    if is_boss_floor(floor):
        run["label"] += " [Boss]"
    _spawn_into(run, floor, run["group_size"])
    _RUNS[rid] = run
    return run


def _apply_floor_run(run, floor: int):
    floor = max(1, int(floor))
    theme = theme_for(floor)
    hazard = hazard_for(floor, theme)
    run["floor"] = floor
    run["theme"] = theme
    run["hazard"] = hazard
    run["cleared"] = False
    run["door_open"] = False
    run["rewarded"] = set()
    run["tiles"] = build_tiles(door_open=False)
    run["label"] = f"Floor {floor} — {theme.title()}"
    if hazard:
        run["label"] += f" [{HAZARD_LABEL.get(hazard, hazard)}]"
    if is_boss_floor(floor):
        run["label"] += " [Boss]"
    _spawn_into(run, floor, run.get("group_size") or 1)


def _apply_floor(session, floor: int, announce=False):
    """Solo helper — creates/updates a personal run."""
    st = _state(session)
    run = _run_of(session)
    group_size = int(st.get("group_size") or 1)
    if run is None:
        run = _make_run(floor, group_size, [session.player_id])
    else:
        _apply_floor_run(run, floor)
    st["floor_rewarded"] = False
    _sync_session_from_run(session, run)
    session.x, session.y = SPAWN
    session.in_combat_with = None
    session.gathering_node = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None
    return st


def build(session, group_size=1, member_ids=None, run=None):
    load(session)
    member_ids = list(member_ids or [session.player_id])
    group_size = max(1, int(group_size or 1))
    session.dungeon = {
        "id": DUNGEON_ID,
        "explore": True,
        "floor": 1,
        "floors": 1,
        "label": f"Floor 1 — {THEMES[0].title()}",
        "name": "The Endless Depths",
        "tiles": build_tiles(False),
        "width": W,
        "height": H,
        "monsters": {},
        "return_x": STAND[0],
        "return_y": STAND[1],
        "exit_x": EXIT[0],
        "exit_y": EXIT[1],
        "props": [dict(p) for p in PROP_SPOTS],
        "endless_depths": {
            "floor": 1,
            "cleared": False,
            "door_open": False,
            "floor_rewarded": False,
            "theme": THEMES[0],
            "hazard": None,
            "group_size": group_size,
            "run_id": None,
        },
    }
    if run is None:
        run = _make_run(1, group_size, member_ids)
    _sync_session_from_run(session, run)
    session.x, session.y = SPAWN
    session.in_combat_with = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


def client_extra(session=None):
    if session is None:
        floor, theme = 1, THEMES[0]
        cleared = door_open = False
        remaining = 0
        highest = solo_best = 0
        claimed = []
        rmul = reward_mult(1)
        hazard = None
        group_size = 1
        run_cleared = run_coins = 0
        boss = False
    else:
        st = _state(session)
        floor = int(st.get("floor") or 1)
        theme = st.get("theme") or theme_for(floor)
        cleared = bool(st.get("cleared"))
        door_open = bool(st.get("door_open"))
        monsters = (session.dungeon or {}).get("monsters") or {}
        remaining = sum(1 for m in monsters.values() if m.alive)
        highest = highest_floor(session)
        solo_best = solo_highest_floor(session)
        claimed = milestones_claimed(session)
        group_size = int(st.get("group_size") or 1)
        rmul = reward_mult(floor) * group_reward_mult(group_size)
        hazard = st.get("hazard") or hazard_for(floor, theme)
        run = _run_of(session)
        run_cleared = int((run or {}).get("floors_cleared") or st.get("run_cleared") or 0)
        run_coins = int((run or {}).get("coins_earned") or st.get("run_coins") or 0)
        boss = is_boss_floor(floor)
    nxt = next_milestone(floor, claimed)
    return {
        "floor": floor,
        "theme": theme,
        "art": theme,
        "cleared": cleared,
        "door_open": door_open,
        "door": [list(p) for p in DOOR],
        "remaining": remaining,
        "highest": highest,
        "solo_highest": solo_best if session else 0,
        "best": max(highest, solo_best) if session else 0,
        "run_cleared": run_cleared,
        "run_coins": run_coins,
        "boss_floor": boss,
        "tier": difficulty_tier(floor),
        "reward_mult": round(rmul, 3),
        "next_milestone": nxt,
        "milestones_claimed": list(claimed),
        "title": getattr(session, "endless_title", "") if session else "",
        "hazard": hazard,
        "hazard_label": HAZARD_LABEL.get(hazard) if hazard else None,
        "hazard_tip": HAZARD_TIP.get(hazard) if hazard else None,
        "ambient": ambient_line(theme, floor),
        "group_size": group_size if session else 1,
        "fill_screen": True,
        "size": [W, H],
        "exit": list(EXIT),
    }


async def _send_banner(session, kind, title, subtitle=""):
    """Client-side centre banner (boss / milestone / theme / PB)."""
    srv = _srv()
    await srv.send(session.ws, "ENDLESS_BANNER", **{
        "kind": kind,
        "title": title,
        "subtitle": subtitle or "",
        "until": time.time() + (4.2 if kind == "milestone" else 3.2),
    })


async def _announce_floor(session, floor: int, *, joining=False):
    """Ambient + hazard tip + boss/milestone banner on floor arrival."""
    theme = theme_for(floor)
    haz = hazard_for(floor, theme)
    bits = []
    if joining:
        bits.append(f"You join on floor {floor} — {theme.title()}.")
    else:
        bits.append(ambient_line(theme, floor))
    if haz:
        bits.append(HAZARD_TIP.get(haz) or f"Hazard: {HAZARD_LABEL.get(haz, haz)}.")
    if is_boss_floor(floor):
        bits.append("Boss floor — a champion waits.")
        await _send_banner(session, "boss", "Boss floor", f"Floor {floor} · {theme.title()}")
    elif is_milestone_floor(floor):
        bits.append(f"Milestone floor {floor}.")
        await _send_banner(session, "milestone", f"Milestone {floor}", theme.title())
    srv = _srv()
    await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": " ".join(bits)})


async def _party_chat(session, text, *, exclude_self=False):
    """Broadcast a short callout to everyone sharing this run."""
    srv = _srv()
    for s in run_mates(session):
        if exclude_self and s.player_id == session.player_id:
            continue
        await srv.send(s.ws, "CHAT_MSG", **{"from": SPEAKER, "text": text})


async def _push(session, chat=None):
    srv = _srv()
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if chat:
        await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": chat})


def _clear_reward_amounts(floor: int, group_size: int = 1) -> tuple[int, int]:
    rmul = reward_mult(floor) * group_reward_mult(group_size)
    coins = int(min(COIN_SOFT_CAP, 25 * floor * rmul))
    xp = int(min(XP_SOFT_CAP, 18 * floor * rmul))
    return coins, xp


async def _grant_theme_first_clear(session, theme: str):
    """One-time coins/XP the first time this player clears a theme plate."""
    if not note_theme_clear(session, theme):
        return None
    coins = THEME_FIRST_CLEAR_COINS
    xp = THEME_FIRST_CLEAR_XP
    srv = _srv()
    if coins > 0:
        srv.WORLD.add_coins(session, coins)
    if xp > 0:
        for skill in ("attack", "strength", "defence"):
            srv.WORLD.grant_xp(session, skill, max(1, xp // 3))
    await _send_banner(
        session, "theme",
        f"First clear — {theme.title()}",
        f"+{coins} coins, +{xp} XP",
    )
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": SPEAKER,
        "text": (
            f"First clear of the {theme.title()} plate — "
            f"+{coins} coins and combat XP."
        ),
    })
    return {"coins": coins, "xp": xp, "theme": theme}


async def _grant_floor_clear(session, floor: int):
    """Award clear rewards once per player when advancing after a clear."""
    st = _state(session)
    run = _run_of(session)
    if run is not None:
        if session.player_id in run.get("rewarded", ()):
            st["floor_rewarded"] = True
            return None
        run.setdefault("rewarded", set()).add(session.player_id)
    if st.get("floor_rewarded"):
        return None
    st["floor_rewarded"] = True
    coins, xp = _clear_reward_amounts(floor, int(st.get("group_size") or 1))
    srv = _srv()
    if coins > 0:
        srv.WORLD.add_coins(session, coins)
    if xp > 0:
        for skill in ("attack", "strength", "defence"):
            srv.WORLD.grant_xp(session, skill, max(1, xp // 3))
    if run is not None:
        # Coins/XP accumulate per member; floor count bumps once per advance.
        run["coins_earned"] = int(run.get("coins_earned") or 0) + coins
        run["xp_earned"] = int(run.get("xp_earned") or 0) + xp
        st["run_coins"] = run["coins_earned"]
        st["run_cleared"] = int(run.get("floors_cleared") or 0)
    pb = note_highest(session, floor)
    mile = claim_milestone(session, floor)
    if mile:
        await _send_banner(
            session, "milestone",
            f"Milestone {mile['floor']}",
            f"{mile['title']} · +{mile['coins']} coins",
        )
    if pb.get("solo"):
        await _send_banner(
            session, "pb",
            "New solo best!",
            f"Floor {floor}",
        )
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": SPEAKER,
            "text": f"New solo personal best — floor {floor}.",
        })
    elif pb.get("highest"):
        await _send_banner(
            session, "pb",
            "New personal best!",
            f"Floor {floor}",
        )
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": SPEAKER,
            "text": f"New personal best — floor {floor}.",
        })
    return {"coins": coins, "xp": xp, "milestone": mile, "pb": pb}


async def _push_run(run, chat=None):
    """Refresh dungeon payload for every member still inside this run."""
    srv = _srv()
    for mid in list(run.get("member_ids") or []):
        s = srv.WORLD.sessions.get(mid)
        if not s or not here(s):
            continue
        if _state(s).get("run_id") != run["id"]:
            continue
        _sync_session_from_run(s, run)
        await _push(s, chat)
        srv._save_dungeon_resume(s)


async def enter(session, msg=None):
    """Solo or party entry. Nearby party members are pulled into a shared run.

    When the player has a saved continue floor (>1) and has not chosen yet,
    send ENDLESS_ENTRY_PROMPT instead of entering. Client replies with
    ENTER_DUNGEON + endless_mode=continue|fresh.
    """
    import party as party_mod
    srv = _srv()
    load(session)
    msg = msg or {}

    # Join an existing party leader run if they are already inside.
    existing = None
    for s in _party_sessions(session):
        if s.player_id == session.player_id:
            continue
        if here(s):
            run = _run_of(s)
            if run is not None:
                existing = run
                break

    if existing is not None:
        session._dungeon_return = STAND
        srv.WORLD.db.save_player_position(session.player_id, *STAND)
        srv._clear_dungeon_resume(session)
        if session.player_id not in existing["member_ids"]:
            existing["member_ids"].append(session.player_id)
        build(session, group_size=existing.get("group_size") or 1,
              member_ids=existing["member_ids"], run=existing)
        srv._bring_pet(session)
        srv._save_dungeon_resume(session)
        await _push(session)
        await _announce_floor(session, int(existing["floor"]), joining=True)
        name = session.char_name or "A teammate"
        await _party_chat(
            session,
            f"{name} joins on floor {existing['floor']}.",
            exclude_self=True,
        )
        return

    mode = str(msg.get("endless_mode") or msg.get("mode") or "").strip().lower()
    saved = continue_floor(session)
    # Ask before entering when there is something to continue.
    if mode not in ("continue", "fresh", "start", "restart") and saved > 1:
        theme = theme_for(saved)
        haz = hazard_for(saved, theme)
        await srv.send(session.ws, "ENDLESS_ENTRY_PROMPT", **{
            "continue_floor": saved,
            "theme": theme,
            "theme_label": theme.title(),
            "highest": highest_floor(session),
            "solo_highest": solo_highest_floor(session),
            "hazard": haz,
            "hazard_label": HAZARD_LABEL.get(haz) if haz else None,
            "hazard_tip": HAZARD_TIP.get(haz) if haz else None,
            "boss_floor": is_boss_floor(saved),
        })
        return

    start_floor = 1
    if mode in ("continue",) and saved > 1:
        start_floor = saved
    elif mode in ("fresh", "start", "restart"):
        start_floor = 1
    else:
        try:
            asked = int(msg.get("start_floor") or 0)
        except (TypeError, ValueError):
            asked = 0
        if asked > 1:
            start_floor = asked

    session._dungeon_return = STAND
    srv.WORLD.db.save_player_position(session.player_id, *STAND)
    srv._clear_dungeon_resume(session)

    # Fresh / continue run — pull nearby party members at the mouth.
    group = [session]
    if party_mod.party_of(session.player_id):
        for s in _party_sessions(session):
            if s.player_id == session.player_id:
                continue
            if s.dungeon:
                continue
            if _near_mouth(s):
                group.append(s)
    group_size = max(1, len(group))
    member_ids = [s.player_id for s in group]
    run = _make_run(start_floor, group_size, member_ids)

    for s in group:
        s._dungeon_return = STAND
        srv.WORLD.db.save_player_position(s.player_id, *STAND)
        srv._clear_dungeon_resume(s)
        build(s, group_size=group_size, member_ids=member_ids, run=run)
        # Slight spawn scatter so bodies don't stack.
        off = member_ids.index(s.player_id)
        s.x = min(W - 2, SPAWN[0] + (off % 3) - 1)
        s.y = SPAWN[1]
        srv._bring_pet(s)
        srv._save_dungeon_resume(s)
        note_continue(s, start_floor)

    gnote = f" Party of {group_size}." if group_size > 1 else ""
    for s in group:
        if start_floor <= 1:
            await _push(s, (
                "Floor 1 — Crypt. Clear the chamber to open the north door. "
                f"South exit leaves anytime.{gnote}"
            ))
        else:
            await _push(s)
        await _announce_floor(s, start_floor)


async def resume(session, resume):
    srv = _srv()
    load(session)
    floor = max(1, int(resume.get("floor") or 1))
    session._dungeon_return = STAND
    rx, ry = resume.get("return_x"), resume.get("return_y")
    if rx is not None and ry is not None:
        session._dungeon_return = (int(rx), int(ry))
    build(session)
    _apply_floor(session, floor)
    # Resume mid-clear: do not re-grant rewards for this floor.
    st = _state(session)
    st["floor_rewarded"] = True
    run = _run_of(session)
    if run is not None:
        run.setdefault("rewarded", set()).add(session.player_id)
    x = int(resume.get("x") or SPAWN[0])
    y = int(resume.get("y") or SPAWN[1])
    if not dungeon_walkable(session.dungeon["tiles"], x, y):
        x, y = SPAWN
    session.x, session.y = x, y
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None
    if rx is not None and ry is not None:
        session.dungeon["return_x"] = int(rx)
        session.dungeon["return_y"] = int(ry)
    else:
        session.dungeon["return_x"], session.dungeon["return_y"] = STAND
    srv._bring_pet(session)
    srv._save_dungeon_resume(session)
    await _push(session)
    await _announce_floor(session, floor)


async def _unlock_door(session, announce=True):
    """Open the north door after a clear. Idempotent."""
    st = _state(session)
    run = _run_of(session)
    already = bool(st.get("door_open")) and (run is None or run.get("door_open"))
    if already:
        return False
    tiles = build_tiles(door_open=True)
    st["cleared"] = True
    st["door_open"] = True
    session.dungeon["tiles"] = tiles
    mates = []
    if run is not None:
        run["cleared"] = True
        run["door_open"] = True
        run["tiles"] = tiles
        # Keep every member's tiles in sync before the push.
        for mid in list(run.get("member_ids") or []):
            s = _srv().WORLD.sessions.get(mid)
            if s and here(s) and _state(s).get("run_id") == run["id"]:
                _state(s)["cleared"] = True
                _state(s)["door_open"] = True
                s.dungeon["tiles"] = tiles
                mates.append(s)
    else:
        mates = [session]
    floor = int(st.get("floor") or 1)
    theme = st.get("theme") or theme_for(floor)
    text = (
        f"Floor {floor} falls silent. The north door unlocks — "
        "step through to descend. South still leads out."
    ) if announce else None
    if run is not None:
        await _push_run(run, chat=text)
    else:
        srv = _srv()
        if text:
            await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": text})
        await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
        srv._save_dungeon_resume(session)
    # Theme first-clear + party callout (who finished the last foe).
    for s in mates:
        await _grant_theme_first_clear(s, theme)
    if announce and len(mates) > 1:
        killer = session.char_name or "A teammate"
        await _party_chat(
            session,
            f"{killer} clears floor {floor}. North door open.",
            exclude_self=False,
        )
    if announce and is_boss_floor(floor):
        for s in mates:
            await _send_banner(s, "boss", "Boss fallen", f"Floor {floor} clear")
    return True


def _chamber_empty(session) -> bool:
    run = _run_of(session)
    monsters = (run["monsters"] if run else (session.dungeon or {}).get("monsters")) or {}
    return not any(m.alive for m in monsters.values())


async def on_kill(session, monster):
    if not here(session):
        return
    st = _state(session)
    run = _run_of(session)
    if st.get("cleared") and st.get("door_open"):
        return
    if not _chamber_empty(session):
        srv = _srv()
        if run:
            await _push_run(run)
        else:
            await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
        return
    await _unlock_door(session, announce=True)


async def advance_floor(session):
    """Bump floor after a clear; grant rewards once per member."""
    if not here(session):
        return False
    st = _state(session)
    run = _run_of(session)
    if not st.get("cleared") or not st.get("door_open"):
        return False
    floor = int(st.get("floor") or 1)
    srv = _srv()
    members = []
    if run is not None:
        for mid in list(run.get("member_ids") or []):
            s = srv.WORLD.sessions.get(mid)
            if s and here(s) and _state(s).get("run_id") == run["id"]:
                members.append(s)
    if not members:
        members = [session]

    summaries = {}
    for s in members:
        summaries[s.player_id] = await _grant_floor_clear(s, floor)

    if run is not None:
        run["floors_cleared"] = int(run.get("floors_cleared") or 0) + 1
        for s in members:
            _state(s)["run_cleared"] = run["floors_cleared"]
            _state(s)["run_coins"] = int(run.get("coins_earned") or 0)

    nxt = floor + 1
    if run is not None:
        _apply_floor_run(run, nxt)
        for s in members:
            _sync_session_from_run(s, run)
            s.x, s.y = SPAWN
            s.in_combat_with = None
            if getattr(s, "pet_id", None):
                s.pet_x, s.pet_y = s.x, s.y
            _state(s)["floor_rewarded"] = False
            note_continue(s, nxt)
            srv._save_dungeon_resume(s)
    else:
        _apply_floor(session, nxt)
        note_continue(session, nxt)
        srv._save_dungeon_resume(session)

    for s in members:
        summary = summaries.get(s.player_id)
        reward_bits = []
        if summary:
            reward_bits.append(f"+{summary['coins']} coins, combat XP.")
            mile = summary.get("milestone")
            if mile:
                reward_bits.append(
                    f"Milestone {mile['floor']}: unlocked title {mile['title']} "
                    f"(+{mile['coins']} coins). Choose it in Settings."
                )
        gs = int(_state(s).get("group_size") or 1)
        if gs > 1:
            reward_bits.append(f"Group ×{gs}.")
        chat = " ".join(reward_bits) if reward_bits else None
        await _push(s, chat)
        await _announce_floor(s, nxt)
    return True


async def on_step(session):
    if not here(session):
        return False
    st = _state(session)
    x, y = int(session.x), int(session.y)
    if (x, y) in DOOR:
        # Heal a missed unlock, then descend. Door tiles are always walkable.
        if not st.get("door_open"):
            if _chamber_empty(session):
                await _unlock_door(session, announce=True)
                st = _state(session)
            if not st.get("door_open"):
                srv = _srv()
                last = float(getattr(session, "_endless_door_chat", 0) or 0)
                now = time.time()
                if now - last > 2.5:
                    session._endless_door_chat = now
                    await srv.send(session.ws, "CHAT_MSG", **{
                        "from": SPEAKER,
                        "text": "The north door is sealed. Clear every foe first.",
                    })
                return False
        return await advance_floor(session)
    if (x, y) == EXIT:
        srv = _srv()
        note_highest(session, int(st.get("floor") or 1))
        await srv.handle_leave_dungeon(session)
        return True
    return False


async def handle_interact(session, msg):
    srv = _srv()
    try:
        x, y = int(msg.get("x")), int(msg.get("y"))
    except (TypeError, ValueError):
        return
    if (x, y) not in DOOR:
        return
    st = _state(session)
    if not st.get("door_open"):
        # Safety net: chamber already empty but door never flipped (missed kill push).
        if _chamber_empty(session):
            await _unlock_door(session, announce=True)
            st = _state(session)
        if not st.get("door_open"):
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": SPEAKER,
                "text": "The north door is sealed. Clear every foe first.",
            })
            return
    await advance_floor(session)


async def on_leave(session):
    """Called when leaving — bump highest; cash-out summary; detach run."""
    if not session.dungeon or session.dungeon.get("id") != DUNGEON_ID:
        return
    st = _state(session)
    floor = int(st.get("floor") or 1)
    note_highest(session, floor)
    note_continue(session, floor)
    run = _run_of(session)
    cleared = int((run or {}).get("floors_cleared") or st.get("run_cleared") or 0)
    coins = int((run or {}).get("coins_earned") or st.get("run_coins") or 0)
    start = int((run or {}).get("start_floor") or st.get("run_start") or floor)
    srv = _srv()
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": SPEAKER,
        "text": (
            f"Cash out — floors cleared this run: {cleared} "
            f"(started {start}, left on {floor}). Coins earned: {coins}."
        ),
    })
    if run is not None and int(run.get("group_size") or 1) > 1:
        name = session.char_name or "A teammate"
        await _party_chat(
            session,
            f"{name} leaves on floor {floor}.",
            exclude_self=True,
        )
    if run is None:
        return
    rid = run["id"]
    run["member_ids"] = [m for m in run["member_ids"] if m != session.player_id]
    st["run_id"] = None
    if not run["member_ids"]:
        _RUNS.pop(rid, None)


async def on_death(session):
    """Party callout when a delver falls; leave path still handles cash-out."""
    if not here(session):
        return
    st = _state(session)
    floor = int(st.get("floor") or 1)
    name = session.char_name or "A teammate"
    if int(st.get("group_size") or 1) > 1:
        await _party_chat(
            session,
            f"{name} falls on floor {floor}.",
            exclude_self=True,
        )


def run_mates(session):
    """Sessions sharing this endless run (for STATE_UPDATE co-presence)."""
    if not here(session):
        return [session]
    run = _run_of(session)
    if run is None:
        return [session]
    srv = _srv()
    out = []
    for mid in run.get("member_ids") or []:
        s = srv.WORLD.sessions.get(mid)
        if s and here(s) and _state(s).get("run_id") == run["id"]:
            out.append(s)
    return out or [session]


async def tick_sessions():
    """Apply environmental hazards each game tick; heal stuck sealed doors."""
    srv = _srv()
    tick = int(srv.WORLD.tick_count or 0)
    for session in list(srv.WORLD.sessions.values()):
        if not here(session):
            continue
        st = _state(session)
        # Occasional repair if every foe is dead but the north door stayed sealed.
        if tick % 5 == 0 and not st.get("door_open") and _chamber_empty(session):
            await _unlock_door(session, announce=True)
            continue
        await _tick_hazard(session, tick)


async def _tick_hazard(session, tick: int):
    st = _state(session)
    hazard = st.get("hazard")
    if not hazard:
        return
    floor = int(st.get("floor") or 1)
    intensity = hazard_intensity(floor)
    srv = _srv()
    # Soft pulse every few ticks so DoTs are readable.
    if tick % 3 != 0:
        # Freeze/roots still apply movement gates continuously.
        if hazard in ("freeze", "roots") and tick % 8 == 0:
            session.rooted_until = max(int(getattr(session, "rooted_until", 0) or 0), tick + 2)
        return

    dmg = 0
    msg = None
    if hazard == "poison":
        dmg = max(1, int(2 * intensity))
        msg = "Poison mist burns your veins."
    elif hazard == "fire":
        dmg = max(1, int(3 * intensity))
        msg = "The chamber's heat sears you."
    elif hazard == "freeze":
        dmg = max(1, int(1 * intensity))
        session.rooted_until = max(int(getattr(session, "rooted_until", 0) or 0), tick + 3)
        msg = "Frost locks your steps."
    elif hazard == "darkness":
        # Accuracy/power tax — small chip damage + attack debuff.
        dmg = max(1, int(1 * intensity * 0.6))
        session.apply_stat_boost("attack", -max(1, int(2 + intensity)), 4)
        msg = "The dark gnaws at your aim."
    elif hazard == "roots":
        session.rooted_until = max(int(getattr(session, "rooted_until", 0) or 0), tick + 2)
        dmg = max(1, int(1 * intensity * 0.5))
        msg = "Roots coil around your ankles."

    if dmg <= 0:
        return
    # Don't execute via environment — leave a sliver so combat/food still matter.
    floor_hp = max(1, session.hp - dmg)
    if floor_hp >= session.hp:
        return
    session.hp = floor_hp
    session.last_combat_tick = tick
    srv.WORLD.db.save_player_stats(session.player_id, hp=session.hp)
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    # Throttle chat so it doesn't spam every pulse.
    last = float(getattr(session, "_endless_hazard_chat", 0) or 0)
    now = time.time()
    if msg and now - last > 6.0:
        session._endless_hazard_chat = now
        await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": msg})
    await srv.send(session.ws, "COMBAT_EVENT", **{
        "attacker_id": 0,
        "defender_id": session.player_id,
        "damage": dmg,
        "hit": True,
        "defender_hp": session.hp,
        "defender_max_hp": session.max_hp(),
        "kind": "hazard",
        "fx": hazard,
    })
