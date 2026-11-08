"""Petaldeep — five halls under the north-west of the fairy glade.

Linear private instance. Halls fill the default map viewport.
North arches stay open so you can move through; south returns (or leaves).
"""
from __future__ import annotations

DUNGEON_ID = "petaldeep"
KEY_ID = "petaldeep_key"
PETAL_ID = "black_petal"
SPEAKER = "Petaldeep"

MOUTH = (8, 65)
STAND = (8, 67)

ROOM1_LEVEL = 200
FUTURE_BOSS_LEVEL = 2000  # Queen — kept for old callers / chat

WARN = "I wouldn't go in there if I were you. See what the fairies know."
KEY_GIFT = (
    "{name} presses a black key into your hand. "
    "\"The mouth in the north-west of the glade will open for this. "
    "What sleeps there is far beyond the village.\""
)

# Default client map is 900×640 at TILE=40 → 22×16 tiles. Size halls so the
# plate and floor fill the panel with a one-tile wall rim (no void letterbox).
W, H = 22, 16
CX = W // 2  # 11
SPAWN = (CX, H - 3)       # south approach
EXIT = (CX, H - 2)        # leave / previous hall
# North transition — always walkable (halls are not sealed shut).
DOOR = ((CX - 1, 1), (CX, 1), (CX + 1, 1))
ROOM_BOX = (1, 1, W - 2, H - 2)

# art keys match client/assets/petaldeep/rooms/{art}.png
HALLS = (
    {
        "id": "orchard",
        "label": "The Black Orchard",
        "art": "room1_orchard",
        "level": 200,
        "spawns": (
            ("petal_thrall", 5, 7, False),
            ("petal_thrall", CX, 6, True),  # Black Petal
            ("petal_thrall", 16, 7, False),
        ),
    },
    {
        "id": "thorn",
        "label": "Thorn Choir",
        "art": "room2_thorn",
        "level": 500,
        "spawns": (
            ("petal_thrall_thorn", 4, 7, False),
            ("petal_thrall_thorn", 8, 5, False),
            ("petal_thrall_thorn", 13, 5, False),
            ("petal_thrall_thorn", 17, 7, False),
        ),
    },
    {
        "id": "mirror",
        "label": "Mirror Bloom",
        "art": "room3_mirror",
        "level": 900,
        "spawns": (
            ("petal_thrall_mirror", 4, 7, False),
            ("petal_thrall_mirror", 7, 5, False),
            ("petal_elite_mirror", CX, 6, False),
            ("petal_thrall_mirror", 14, 5, False),
            ("petal_thrall_mirror", 17, 8, False),
        ),
    },
    {
        "id": "night",
        "label": "Root of Night",
        "art": "room4_night",
        "level": 1400,
        "spawns": (
            ("petal_thrall_night", 3, 7, False),
            ("petal_thrall_night", 6, 5, False),
            ("petal_elite_night", CX, 6, False),
            ("petal_thrall_night", 14, 5, False),
            ("petal_thrall_night", 18, 7, False),
            ("petal_thrall_night", 10, 9, False),
        ),
    },
    {
        "id": "queen",
        "label": "Queen of Petaldeep",
        "art": "room5_queen",
        "level": 2000,
        "spawns": (
            ("petaldeep_queen", CX, 5, False),
        ),
    },
)


def _srv():
    import server
    return server


def here(session):
    return bool(session.dungeon) and session.dungeon.get("id") == DUNGEON_ID


def _owns(session, item_id):
    srv = _srv()
    if srv.session_has_item(session, item_id):
        return True
    bank = getattr(session, "bank", None) or {}
    return any((e or {}).get("item_id") == item_id for e in bank.values())


def has_key(session):
    return _owns(session, KEY_ID)


def is_opened(session):
    """True once the key has been used — mouth stays open forever after."""
    import fairy_friendship as FF
    srv = _srv()
    d = FF.load(srv.WORLD.db.conn, session.player_id)
    return bool(d.get("petaldeep_opened"))


def can_enter(session):
    return is_opened(session) or has_key(session)


def _strip_all_keys(session):
    """Remove every Petaldeep Key from inventory and bank."""
    srv = _srv()
    while srv.WORLD.count_item(session, KEY_ID) > 0:
        srv.WORLD.remove_item_qty(session, KEY_ID, srv.WORLD.count_item(session, KEY_ID))
    bank_n = srv.WORLD.count_item_bank(session, KEY_ID)
    if bank_n > 0:
        srv._remove_bank_item_qty(session, KEY_ID, bank_n)


def mark_opened(session):
    """First entry: consume the key and permanently unlock the mouth."""
    import fairy_friendship as FF
    srv = _srv()
    d = FF.load(srv.WORLD.db.conn, session.player_id)
    d["petaldeep_opened"] = True
    FF.save(srv.WORLD.db.conn, session.player_id, d)
    _strip_all_keys(session)


def try_grant_key(session):
    import fairy_friendship as FF
    srv = _srv()
    d = FF.load(srv.WORLD.db.conn, session.player_id)
    if not FF.all_maxed(d):
        return False
    # Already used the key — mouth stays open; do not mint another.
    if d.get("petaldeep_opened") or is_opened(session):
        return False
    if _owns(session, KEY_ID):
        return False
    return bool(srv.WORLD.add_item_to_inventory(session, KEY_ID, 1))


def prepare_account(session):
    import fairy_friendship as FF
    srv = _srv()
    if (getattr(session, "username", "") or "").strip().lower() == "david":
        FF.grant_full_trust(srv.WORLD.db.conn, session.player_id)
    return try_grant_key(session)


def dungeon_walkable(tiles, x, y):
    from world_map import FLOOR
    if not tiles or y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


def build_tiles(door_open=True):
    """Full-screen hall: floor fills the interior; north arch always open."""
    from world_map import FLOOR, WALL
    tiles = [[WALL for _ in range(W)] for _ in range(H)]
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            tiles[y][x] = FLOOR
    # North transition cells stay floor — never seal the path between halls.
    for x, y in DOOR:
        tiles[y][x] = FLOOR
    return tiles


def _state(session):
    return (session.dungeon or {}).setdefault("petaldeep", {
        "room": 0, "cleared": False, "door_open": True,
    })


def _hall(idx):
    return HALLS[max(0, min(int(idx), len(HALLS) - 1))]


def _spawn_room(session, hall):
    srv = _srv()
    from content import MONSTERS
    session.dungeon["monsters"] = {}
    for mtype, x, y, carries_petal in hall["spawns"]:
        mid = srv.next_id()
        stats = None
        if carries_petal:
            base = list((MONSTERS.get(mtype) or {}).get("drops") or [])
            stats = {"drops": base + [(PETAL_ID, 1.0, (1, 1))]}
        m = srv.MonsterInstance(mid, mtype, x, y, no_respawn=True, stats=stats)
        m.home_room = ROOM_BOX
        session.dungeon["monsters"][mid] = m


def _apply_room(session, idx, announce=False):
    hall = _hall(idx)
    st = _state(session)
    st["room"] = int(idx)
    st["cleared"] = False
    st["door_open"] = True  # always passable
    session.dungeon["tiles"] = build_tiles(door_open=True)
    session.dungeon["label"] = hall["label"]
    session.dungeon["floor"] = int(idx) + 1
    session.dungeon["floors"] = len(HALLS)
    session.dungeon["exit_x"], session.dungeon["exit_y"] = EXIT
    session.dungeon["width"], session.dungeon["height"] = W, H
    _spawn_room(session, hall)
    session.x, session.y = SPAWN
    session.in_combat_with = None
    session.gathering_node = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None
    return hall


def build(session):
    session.dungeon = {
        "id": DUNGEON_ID, "explore": True, "floor": 1, "floors": len(HALLS),
        "label": HALLS[0]["label"], "name": "Petaldeep",
        "tiles": build_tiles(True), "width": W, "height": H, "monsters": {},
        "return_x": STAND[0], "return_y": STAND[1],
        "exit_x": EXIT[0], "exit_y": EXIT[1], "props": [],
        "petaldeep": {"room": 0, "cleared": False, "door_open": True},
    }
    _apply_room(session, 0)


def client_extra(session=None):
    if session is None:
        st = {"room": 0, "cleared": False, "door_open": True}
    else:
        st = _state(session)
    hall = _hall(st.get("room") or 0)
    return {
        "room": int(st.get("room") or 0),
        "room_id": hall["id"],
        "label": hall["label"],
        "art": hall["art"],
        "cleared": bool(st.get("cleared")),
        "door_open": True,
        "door": [list(p) for p in DOOR],
        "arch": [list(p) for p in DOOR],
        "room_level": int(hall["level"]),
        "boss_level": FUTURE_BOSS_LEVEL,
        "rooms_total": len(HALLS),
        "fill_screen": True,
        "size": [W, H],
    }


async def _push(session, chat=None):
    srv = _srv()
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    if chat:
        await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": chat})


async def enter(session):
    srv = _srv()
    first = not is_opened(session)
    if first:
        mark_opened(session)
    session._dungeon_return = STAND
    srv.WORLD.db.save_player_position(session.player_id, *STAND)
    srv._clear_dungeon_resume(session)
    build(session)
    srv._bring_pet(session)
    srv._save_dungeon_resume(session)
    hall = HALLS[0]
    used = (
        "The black key turns once in the root-mouth and is gone — "
        "the way stays open to you now. "
        if first else ""
    )
    await _push(session, (
        f"{used}Hall 1 of {len(HALLS)} — {hall['label']}. "
        f"Combat level {hall['level']}. The north root-arch is open — walk "
        "through to go deeper. South exit leaves to the glade."
    ))


async def resume(session, resume):
    """Wake back inside Petaldeep after logout. Never uses floor_info."""
    srv = _srv()
    room = max(0, min(int(resume.get("floor") or 1) - 1, len(HALLS) - 1))
    session._dungeon_return = STAND
    rx, ry = resume.get("return_x"), resume.get("return_y")
    if rx is not None and ry is not None:
        session._dungeon_return = (int(rx), int(ry))
    build(session)
    _apply_room(session, room)
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
    hall = _hall(room)
    await _push(session, (
        f"You wake in {hall['label']} (hall {room + 1} of {len(HALLS)}). "
        f"Combat level {hall['level']}."
    ))


async def on_kill(session, monster):
    """Mark the hall cleared; north was already open for free movement."""
    if not here(session):
        return
    st = _state(session)
    if st.get("cleared"):
        return
    alive = [m for m in session.dungeon["monsters"].values() if m.alive]
    if alive:
        return
    st["cleared"] = True
    st["door_open"] = True
    srv = _srv()
    hall = _hall(st["room"])
    idx = int(st["room"])
    if idx >= len(HALLS) - 1:
        text = (
            f"The Queen of Petaldeep falls. Combat level {hall['level']} — "
            "the deepest blight under the glade is quiet. The south exit remains open."
        )
    else:
        nxt = HALLS[idx + 1]
        text = (
            f"{hall['label']} falls silent. North still leads to "
            f"{nxt['label']} (combat {nxt['level']})."
        )
    await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": text})
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))


async def on_step(session):
    """North door advances; south exit leaves room 0 or returns one hall."""
    if not here(session):
        return False
    st = _state(session)
    x, y = int(session.x), int(session.y)
    if (x, y) in DOOR:
        idx = int(st.get("room") or 0)
        if idx >= len(HALLS) - 1:
            return False
        hall = _apply_room(session, idx + 1)
        await _push(session, (
            f"Hall {idx + 2} of {len(HALLS)} — {hall['label']}. "
            f"Combat level {hall['level']}."
        ))
        srv = _srv()
        srv._save_dungeon_resume(session)
        return True
    if (x, y) == EXIT:
        idx = int(st.get("room") or 0)
        if idx <= 0:
            srv = _srv()
            await srv.handle_leave_dungeon(session)
            return True
        prev = idx - 1
        hall = _hall(prev)
        st["room"] = prev
        st["cleared"] = True
        st["door_open"] = True
        session.dungeon["tiles"] = build_tiles(door_open=True)
        session.dungeon["label"] = hall["label"]
        session.dungeon["floor"] = prev + 1
        session.dungeon["monsters"] = {}
        session.x, session.y = SPAWN
        session.in_combat_with = None
        if getattr(session, "pet_id", None):
            session.pet_x, session.pet_y = session.x, session.y
        await _push(session, f"You fall back to {hall['label']}.")
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
    idx = int(st.get("room") or 0)
    if idx >= len(HALLS) - 1:
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": SPEAKER, "text": "The Queen's hollow. The south exit returns.",
        })
        return
    hall = _apply_room(session, idx + 1)
    await _push(session, (
        f"Hall {idx + 2} of {len(HALLS)} — {hall['label']}. "
        f"Combat level {hall['level']}."
    ))
    srv._save_dungeon_resume(session)
