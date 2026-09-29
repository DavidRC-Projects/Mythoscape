"""The Depths v2: crypt layout, sarcophagi, grasping hands, and Morvath.

Doors, keys, secrets, chests, fog, and the shrine checkpoint go through
dungeon_v2_common. This module only adds what is crypt-specific.
Entered only when USE_NEW_DEPTHS_DUNGEON is on.
"""
import importlib.util
import os
import random

from world_map import FLOOR, WALL

_MAP = None

DOOR_HINTS = {
    "A": "Unlock Bone Gate: Locked. A Bone Key fits here; the Ossuary Keeper carries one.",
    "B": "Unlock Drowned Gate: Locked. A Tide Key fits here; the skulls hide it.",
    "C": "Unlock Knights' Seal: Locked. A Knights' Seal fits here; Sir Aldric carries one.",
}

CHEST_LOOT = {
    "ossuary_chest": [("coins", (80, 200)), ("bones", (1, 2)), ("iron_sword", (1, 1), 0.3)],
    "catacomb_chest": [("coins", (60, 140)), ("steel_longsword", (1, 1), 0.25), ("health_potion", (1, 1))],
    "hideyhole_chest": [("coins", (40, 100)), ("cooked_lobster", (1, 2)), ("emerald", (1, 1), 0.2)],
    "reliquary_chest": [("coins", (100, 220)), ("ruby", (1, 1), 0.4), ("gold_ring", (1, 1), 0.25)],
    "armoury_chest": [("coins", (80, 180)), ("mithril_sword", (1, 1), 0.4)],
    "wyrm_chest": [("coins", (200, 500)), ("adamant_sword", (1, 1), 0.15), ("dragon_bones", (1, 1), 0.3)],
}

CACHE_LOOT = [("cooked_lobster", (3, 3)), ("health_potion", (1, 1))]

SARCOPHAGUS_LOOT = [
    ("coins", (40, 120)),
    (("steel_longsword", "mithril_dagger", "ruby"), (1, 1), 0.45),
]

GROUND_TABLE = [("coins", (15, 40)), ("bones", (1, 1)), ("health_potion", (1, 1))]

WHISPERS = (
    "Water drips somewhere in the dark.",
    "The dead count the footsteps above them.",
    "A bone settles. Then another.",
    "The King still wears his crown.",
)

ARENA = (13, 92, 53, 105)
ARENA_TOMBS = ((22, 95), (44, 95), (22, 101), (44, 101))
PHASE_NAME = {1: "Bone Storm", 2: "Raise the Dead", 3: "Crypt Collapse"}


def map_pack():
    global _MAP
    if _MAP is None:
        path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "depths_dungeon", "reference_code", "depths_map.py",
        ))
        spec = importlib.util.spec_from_file_location("depths_map_pack", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MAP = mod
    return _MAP.build(), _MAP


def _zone_for(x, y, zones):
    hits = []
    stair = None
    for zone in zones:
        zid, _name, _band, rect, _style = zone
        x0, y0, x1, y1 = rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            if zid == "stair":
                stair = zone
            else:
                hits.append(zone)
    if hits:
        return hits[-1]
    return stair


def _inside(x, y, rects):
    for rect in rects:
        x0, y0, x1, y1 = rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def _secret_open_at(x, y, open_secrets, secrets):
    for sid in open_secrets:
        spec = secrets.get(sid) or {}
        if tuple(spec.get("wall") or ()) == (x, y):
            return True
        if _inside(x, y, spec.get("reveal") or []):
            return True
    return False


def _blocked_prop(ch):
    return ch in "Zoiw"


def bake(chars, opened, open_secrets, gate_open, pack, sarc_state):
    secrets = pack["secrets"]
    doors = pack["doors"]
    tiles = []
    decor = {}
    closed = set()
    for sid, spec in secrets.items():
        if sid in open_secrets:
            continue
        for rect in spec["reveal"]:
            x0, y0, x1, y1 = rect
            for yy in range(y0, y1 + 1):
                for xx in range(x0, x1 + 1):
                    closed.add((xx, yy))
    for y, row in enumerate(chars):
        out = []
        for x, ch in enumerate(row):
            hidden = (x, y) in closed
            if ch in "#~W" or hidden:
                tile = WALL
            elif ch in doors and ch not in opened:
                tile = WALL
            elif ch == "X" and not gate_open:
                tile = WALL
            elif ch in "SK" and not _secret_open_at(x, y, open_secrets, secrets):
                tile = WALL
            elif _blocked_prop(ch):
                tile = WALL
            else:
                tile = FLOOR
            out.append(tile)
            if hidden:
                continue
            kind = _decor(ch, x, y, opened, open_secrets, gate_open, pack, sarc_state)
            if kind:
                decor[f"{x},{y}"] = kind
        tiles.append(out)
    return tiles, decor


def _decor(ch, x, y, opened, open_secrets, gate_open, pack, sarc_state):
    secrets = pack["secrets"]
    if ch == "~":
        return "pit"
    if ch == "W":
        return "deep"
    if ch == "%":
        return "shallow"
    if ch == "=":
        return "bridge"
    if ch == "Z":
        state = (sarc_state or {}).get(f"{x},{y}")
        return f"sarcophagus:{state}" if state else "sarcophagus"
    if ch in "ABC":
        return None if ch in opened else f"seal:{ch}"
    if ch == "X":
        return None if gate_open else "gate"
    if ch == "S" and not _secret_open_at(x, y, open_secrets, secrets):
        return "secret"
    if ch == "K" and not _secret_open_at(x, y, open_secrets, secrets):
        return "skull"
    if ch == "o":
        return "candle"
    if ch == "i":
        return "clutter"
    if ch == "w":
        return "warning"
    if ch == "H":
        return "shrine"
    if ch == "v":
        return "lever"
    if ch == "c":
        return "chest"
    if ch == "l":
        return "lore"
    if ch == "g":
        return "cache"
    if ch == "$":
        return "loot"
    if ch == "k":
        return "pedestal"
    return None


def refresh(d):
    tiles, decor = bake(
        d["chars"], set(d["opened"]), set(d["secrets"]), d.get("gate_open"),
        d["pack"], d.get("sarc_state") or {},
    )
    for key in d.get("chests") or []:
        decor[key] = "chest_open"
    for key in d.get("caches") or []:
        decor[key] = "cache_open"
    d["tiles"] = tiles
    d["decor"] = decor
    return tiles


def _shortcut_open(session):
    row = (getattr(session, "quests", None) or {}).get("depths_shortcut") or {}
    return row.get("status") == "complete"


def build(session, next_id, monster_cls, spawns=None):
    """Install a private Depths crypt. The overworld spawns argument is ignored."""
    from content import MONSTERS
    pack, _mod = map_pack()
    chars = [list(row) for row in pack["grid"]]
    gate = _shortcut_open(session)
    tiles, decor = bake(chars, set(), set(), gate, pack, {})
    zones = pack["zones"]
    monsters = {}
    for mtype, mx, my in pack["spawns"]:
        if mtype not in MONSTERS:
            continue
        mid = next_id()
        m = monster_cls(mid, mtype, mx, my, no_respawn=(mtype in set(pack["no_respawn"])))
        zone = _zone_for(mx, my, zones)
        if zone:
            m.home_room = tuple(zone[3])
        else:
            m.home_room = (mx - 4, my - 4, mx + 4, my + 4)
        m.v2_type = mtype
        if mtype == "drowned_dead":
            m.concealed = True
        monsters[mid] = m
    ground = {}
    for i, (x, y) in enumerate(pack["ground_loot"]):
        item_id, bounds = GROUND_TABLE[i % len(GROUND_TABLE)]
        ground[(x, y)] = [{"item_id": item_id, "qty": random.randint(*bounds)}]
    sx, sy = pack["spawn"]
    ex, ey = pack["exit"]
    hints = {}
    for sid, spec in pack["secrets"].items():
        wx, wy = spec["wall"]
        hints[f"{wx},{wy}"] = spec.get("hint") or ""
    session.dungeon = {
        "id": "depths",
        "explore": True,
        "v2": "depths",
        "floor": 1,
        "floors": 1,
        "label": "The Depths",
        "name": "The Depths",
        "tiles": tiles,
        "chars": ["".join(row) for row in chars],
        "decor": decor,
        "width": pack["width"],
        "height": pack["height"],
        "monsters": monsters,
        "return_x": None,
        "return_y": None,
        "exit_x": ex,
        "exit_y": ey,
        "props": [],
        "opened": [],
        "secrets": [],
        "chests": [],
        "caches": [],
        "pedestal": False,
        "shrine_used": False,
        "checkpoint": None,
        "ground": ground,
        "gate_open": gate,
        "boss": {
            "phase": 1,
            "next_storm": 6,
            "storm": None,
            "next_add": 8,
            "next_debris": 8,
            "debris": None,
        },
        "hands": None,
        "hands_at": 7,
        "boss_phase": "Bone Storm",
        "mitigate_boss": "morvath",
        "pack": pack,
        "sarc_state": {},
        "sarc_done": [],
        "search": None,
        "aldric_called": False,
        "zones": [
            {"id": zid, "name": name, "band": band, "rect": list(rect), "style": style}
            for zid, name, band, rect, style in zones
        ],
        "lore": pack["lore"],
        "spec": {
            "chat_from": "The Depths",
            "doors": pack["doors"],
            "door_hints": DOOR_HINTS,
            "secrets": pack["secrets"],
            "chests": pack["chests"],
            "chest_loot": CHEST_LOOT,
            "cache_loot": CACHE_LOOT,
            "pedestal_item": "depths_tide_key",
            "pedestal_text": "You take the Tide Key from the pedestal.",
            "shortcut_quest": "depths_shortcut",
            "lever_text": "A bar lifts somewhere above. The Sexton's Stair is open.",
        },
        "secret_hints": hints,
        "door_hints": DOOR_HINTS,
    }
    session.x, session.y = sx, sy
    session.in_combat_with = None
    session.gathering_node = None
    if session.pet_id:
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


def client_extra(session):
    d = session.dungeon
    return {
        "v2": "depths",
        "decor": d.get("decor") or {},
        "zones": d.get("zones") or [],
        "lore": d.get("lore") or {},
        "ground_items": _ground_public(d),
        "whispers": list(WHISPERS),
        "banner_place": "The Depths",
        "boss_type": "morvath",
        "boss_label": "Morvath",
        "depth_of": {},
        "secret_hints": d.get("secret_hints") or {},
        "door_hints": d.get("door_hints") or {},
    }


def _ground_public(d):
    out = {}
    for (x, y), items in (d.get("ground") or {}).items():
        if items:
            out[f"{x},{y}"] = items
    return out


async def handle_interact(session, msg):
    import dungeon_v2_common as common
    import server as srv
    d = session.dungeon
    if not d or d.get("v2") != "depths":
        return
    try:
        x, y = int(msg.get("x")), int(msg.get("y"))
    except (TypeError, ValueError):
        return
    ch = ""
    if 0 <= y < d["height"] and 0 <= x < d["width"]:
        ch = d["chars"][y][x]
    if ch == "Z":
        await _search_sarcophagus(session, x, y)
        return
    await common.handle_interact(session, msg)


def roll_sarcophagus(weights, rng=None):
    rng = rng or random
    roll = rng.randint(1, 100)
    if roll <= weights["loot"]:
        return "loot"
    if roll <= weights["loot"] + weights["ambush"]:
        return "ambush"
    return "empty"


async def _search_sarcophagus(session, x, y):
    import server as srv
    d = session.dungeon
    pack = d["pack"]
    who = "The Depths"
    if max(abs(session.x - x), abs(session.y - y)) > 1:
        await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "You need to stand next to that."})
        return
    key = f"{x},{y}"
    if (x, y) not in [tuple(p) for p in pack["sarcophagi"]]:
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": who, "text": "The lid is sealed from within.",
        })
        return
    if key in d["sarc_done"]:
        await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "You already searched this sarcophagus."})
        return
    if d.get("search"):
        return
    d["search"] = {"x": x, "y": y, "ready": srv.WORLD.tick_count + 2}
    await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "You search the Knight's sarcophagus..."})


async def _finish_search(session):
    import dungeon_v2_common as common
    import server as srv
    d = session.dungeon
    job = d.get("search")
    if not job or srv.WORLD.tick_count < job["ready"]:
        return
    d["search"] = None
    x, y = job["x"], job["y"]
    key = f"{x},{y}"
    d["sarc_done"].append(key)
    outcome = roll_sarcophagus(d["pack"]["sarcophagus_roll"])
    d["sarc_state"][key] = outcome
    refresh(d)
    await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
    if outcome == "loot":
        await common.grant_table(session, SARCOPHAGUS_LOOT, "The Depths")
    elif outcome == "empty":
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "The Depths", "text": "Dust, and a line of prayer. Nothing else.",
        })
    else:
        await srv.send(session.ws, "CHAT_MSG", **{"from": "The Depths", "text": "The dead stir!"})
        _spawn_ambush(session, x, y)


def _spawn_ambush(session, x, y):
    import server as srv
    from content import MONSTERS
    d = session.dungeon
    spots = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)):
        nx, ny = x + dx, y + dy
        if 0 <= ny < d["height"] and 0 <= nx < d["width"] and d["tiles"][ny][nx] == FLOOR:
            spots.append((nx, ny))
    if not spots:
        spots = [(x, y)]
    plan = [("skeleton", 1), ("barrow_knight", 1)]
    for mtype, count in plan:
        for _ in range(count):
            sx, sy = spots[len(d["monsters"]) % len(spots)]
            mid = srv.next_id()
            stats = None
            if mtype == "skeleton":
                stats = dict(MONSTERS["skeleton"])
                stats["level"] = 40
                stats["hp"] = 80
            m = srv.MonsterInstance(mid, mtype, sx, sy, stats=stats, no_respawn=True)
            m.home_room = (x - 4, y - 4, x + 4, y + 4)
            m.boss_add = False
            d["monsters"][mid] = m


def _bridge_tiles(d):
    bridge = d["pack"]["bridge"]
    x = bridge["x"]
    tiles = []
    chars = d["chars"]
    for y in range(bridge["y0"], bridge["y1"] + 1):
        if 0 <= y < len(chars) and chars[y][x] == "=":
            tiles.append((x, y))
    return tiles


def _in_arena(x, y):
    x0, y0, x1, y1 = ARENA
    return x0 <= x <= x1 and y0 <= y <= y1


async def tick_sessions():
    import server as srv
    for session in list(srv.WORLD.sessions.values()):
        d = session.dungeon
        if not d or d.get("v2") != "depths":
            continue
        await _finish_search(session)
        _reveal_drowned(session)
        await _hands(session)
        await _keeper_toss(session)
        await _aldric_call(session)
        await _morvath(session)


def _reveal_drowned(session):
    d = session.dungeon
    rose = False
    for m in d["monsters"].values():
        if not getattr(m, "concealed", False) or not m.alive:
            continue
        if max(abs(session.x - m.x), abs(session.y - m.y)) <= 4:
            m.concealed = False
            rose = True
    return rose


async def _hands(session):
    import server as srv
    d = session.dungeon
    tick = srv.WORLD.tick_count
    tiles = _bridge_tiles(d)
    if not tiles:
        return
    pending = d.get("hands")
    if pending and tick >= pending["at"]:
        d["hands"] = None
        if (session.x, session.y) in [tuple(p) for p in pending["tiles"]]:
            session.rooted_until = tick + random.randint(2, 3)
            session.hp = max(0, session.hp - random.randint(5, 6))
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": "The Depths", "text": "Bones crack beneath you: grasping hands!",
            })
            await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            if session.hp <= 0:
                await _downed(session)
        return
    if pending or tick < d.get("hands_at", 0):
        return
    pick = random.sample(tiles, k=min(len(tiles), random.randint(2, 3)))
    d["hands"] = {"tiles": pick, "at": tick + 3}
    d["hands_at"] = tick + 7
    await srv.send(session.ws, "BOSS_TELEGRAPH", tiles=[[x, y] for x, y in pick], at=tick + 3, kind="hands")


async def _keeper_toss(session):
    import server as srv
    d = session.dungeon
    if srv.WORLD.tick_count % 10 != 0:
        return
    for m in d["monsters"].values():
        if m.type != "ossuary_keeper" or not m.alive:
            continue
        if max(abs(session.x - m.x), abs(session.y - m.y)) > 6:
            continue
        dmg = random.randint(4, 7)
        session.hp = max(0, session.hp - dmg)
        await srv.send(session.ws, "CHAT_MSG", **{"from": "Ossuary Keeper", "text": "The Keeper hurls a bone!"})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if session.hp <= 0:
            await _downed(session)
        return


async def _aldric_call(session):
    import server as srv
    from content import MONSTERS
    d = session.dungeon
    if d.get("aldric_called"):
        return
    aldric = None
    for m in d["monsters"].values():
        if m.type == "sir_aldric" and m.alive:
            aldric = m
            break
    if aldric is None or aldric.hp > aldric.max_hp // 2:
        return
    d["aldric_called"] = True
    for dx in (-2, 2):
        mid = srv.next_id()
        m = srv.MonsterInstance(mid, "barrow_knight", aldric.x + dx, aldric.y, no_respawn=True)
        m.home_room = aldric.home_room
        m.boss_add = False
        if "barrow_knight" not in MONSTERS:
            continue
        d["monsters"][mid] = m
    await srv.send(session.ws, "CHAT_MSG", **{
        "from": "Sir Aldric", "text": "Aldric calls two barrow knights to his side.",
    })


async def _morvath(session):
    import server as srv
    from content import MONSTERS
    d = session.dungeon
    tick = srv.WORLD.tick_count
    boss = None
    for m in d["monsters"].values():
        if m.type == "morvath" and m.alive:
            boss = m
            break
    state = d["boss"]
    if boss is None:
        return
    if not _in_arena(session.x, session.y):
        if state["phase"] != 1 or boss.hp < boss.max_hp or any(getattr(m, "boss_add", False) and m.alive for m in d["monsters"].values()):
            _reset_boss(d, boss)
        return
    frac = boss.hp / max(1, boss.max_hp)
    phase = 1 if frac > 0.66 else (2 if frac > 0.33 else 3)
    if phase != state["phase"]:
        state["phase"] = phase
        d["boss_phase"] = PHASE_NAME[phase]
        if phase == 2:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Morvath", "text": "Morvath raises the dead."})
        elif phase == 3:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Morvath", "text": "The crypt begins to collapse."})
            stats = dict(MONSTERS["morvath"])
            stats["attack_cooldown"] = float(MONSTERS["morvath"].get("attack_cooldown") or 1.2) * 0.75
            boss.stats = stats
    await _resolve_mark(session, state, "storm",  random.randint(10, 14))
    await _resolve_mark(session, state, "debris", 12)
    gap = 10 if phase == 2 else (5 if phase == 3 else 6)
    if state.get("storm") is None and tick >= state.get("next_storm", 0):
        lines = _arena_lines(d, random.randint(1, 2))
        state["storm"] = {"tiles": lines, "at": tick + 2}
        state["next_storm"] = tick + gap + 2
        await srv.send(session.ws, "BOSS_TELEGRAPH", tiles=[[x, y] for x, y in lines], at=tick + 2, kind="storm")
    if phase == 2 and tick >= state.get("next_add", 0):
        _raise_dead(session, d)
        state["next_add"] = tick + 12
    if phase == 3 and state.get("debris") is None and tick >= state.get("next_debris", 0):
        rubble = _arena_rubble(d, random.randint(3, 5))
        state["debris"] = {"tiles": rubble, "at": tick + 2}
        state["next_debris"] = tick + 8
        await srv.send(session.ws, "BOSS_TELEGRAPH", tiles=[[x, y] for x, y in rubble], at=tick + 2, kind="debris")


def _reset_boss(d, boss):
    boss.hp = boss.max_hp
    boss.stats = None
    boss.x, boss.y = boss.spawn_x, boss.spawn_y
    d["boss"] = {
        "phase": 1, "next_storm": 6, "storm": None,
        "next_add": 8, "next_debris": 8, "debris": None,
    }
    d["boss_phase"] = "Bone Storm"
    for m in d["monsters"].values():
        if getattr(m, "boss_add", False):
            m.alive = False
            m.no_respawn = True


def _arena_lines(d, count):
    x0, y0, x1, y1 = ARENA
    tiles = []
    for _ in range(count):
        if random.random() < 0.5:
            y = random.randint(y0, y1)
            for x in range(x0, x1 + 1):
                if d["tiles"][y][x] == FLOOR:
                    tiles.append((x, y))
        else:
            x = random.randint(x0, x1)
            for y in range(y0, y1 + 1):
                if d["tiles"][y][x] == FLOOR:
                    tiles.append((x, y))
    return tiles


def _arena_rubble(d, count):
    x0, y0, x1, y1 = ARENA
    pool = [
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if d["tiles"][y][x] == FLOOR
    ]
    if not pool:
        return []
    return random.sample(pool, k=min(count, len(pool)))


async def _resolve_mark(session, state, key, dmg):
    import server as srv
    mark = state.get(key)
    if not mark or srv.WORLD.tick_count < mark["at"]:
        return
    state[key] = None
    if (session.x, session.y) in [tuple(p) for p in mark["tiles"]]:
        session.hp = max(0, session.hp - dmg)
        label = "Bone storm" if key == "storm" else "Falling masonry"
        await srv.send(session.ws, "CHAT_MSG", **{"from": "Morvath", "text": f"{label} strikes you for {dmg}."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        if session.hp <= 0:
            await _downed(session)


def _raise_dead(session, d):
    import server as srv
    from content import MONSTERS
    alive = sum(1 for m in d["monsters"].values() if getattr(m, "boss_add", False) and m.alive)
    if alive >= 4:
        return
    tombs = list(ARENA_TOMBS)
    random.shuffle(tombs)
    spawned = 0
    for tx, ty in tombs:
        if alive >= 4 or spawned >= 2:
            return
        mid = srv.next_id()
        stats = dict(MONSTERS["skeleton"])
        stats["level"] = 40
        stats["hp"] = 70
        m = srv.MonsterInstance(mid, "skeleton", tx, ty + 1, stats=stats, no_respawn=True)
        m.home_room = ARENA
        m.boss_add = True
        d["monsters"][mid] = m
        alive += 1
        spawned += 1


async def _downed(session):
    import server as srv
    import void_v2
    if session.hp > 0 or not session.dungeon or getattr(session, "_depths_down", False):
        return
    session._depths_down = True
    session.coins = 0
    session.in_combat_with = None
    session.pet_target_id = None
    if session.dungeon.get("checkpoint"):
        await void_v2.on_death(session)
    else:
        void_v2.strip_keys(session)
        session.hp = session.max_hp()
        await srv.handle_leave_dungeon(session, silent=True)
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "The Depths",
            "text": "You fall in the crypt and wake outside. The dead keep what you carried.",
        })
    session._depths_down = False


async def announce_first_kill(session):
    import server as srv
    row = (session.quests or {}).get("depths_morvath") or {}
    if row.get("status") == "complete":
        return
    if session.player_id:
        srv.WORLD.db.set_quest_progress(session.player_id, "depths_morvath", "complete", 1)
        session.quests["depths_morvath"] = {"status": "complete", "progress": 1}
    text = f"{session.char_name} has slain Morvath, the Bone King!"
    for other in srv.WORLD.sessions.values():
        await srv.send(other.ws, "CHAT_MSG", **{"from": "The Depths", "text": text, "style": "gold"})
