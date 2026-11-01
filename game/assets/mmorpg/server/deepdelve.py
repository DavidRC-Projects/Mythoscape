"""Deepdelve Mine (MINE_SPEC.md): lift gauntlets, floor unlocks, the Heartstone Colossus.

The overworld square (server/deepdelve_layout.py) is shared and has no monsters.
v2: the shaft mouth leads down to Level 2 (Silver Dark, mithril) and a ladder shaft there to
Level 3 (The Green Deep, adamantite). The B0 lift only serves the Coal Seams now.
Each lower floor's chamber is sealed; a B0 lift pad either drops a player straight
into it (floor already unlocked) or into a private gauntlet instance: three rooms,
one guardian each, a rock door that opens on the kill, then the lift cage. Reaching
the cage unlocks the floor for that character for good.

The Heart door in the floor-3 chamber leads to a private Colossus arena. Killing the
Colossus opens that character's Heartstone vein for HEART_OPEN_S seconds.
"""
import random
import time

from world_map import FLOOR, WALL
import deepdelve_layout as L

DEEPDELVE_ID = "deepdelve"
SPEAKER = "Deepdelve"
HEART_OPEN_S = 30 * 60

GAUNTLETS = {
    1: ("tunnel_scavenger", "ember_crawler", "scavenger_foreman"),
    2: ("mithril_wraith", "mithril_wraith", "shackled_wraith"),
    3: ("adamant_golem", "adamant_golem", "ancient_adamant_golem"),
}
COLOSSUS = "heartstone_colossus"

# Gauntlet instance: landing, then room / door / passage x3, then the lift cage.
GW, GH = 46, 9
G_LANDING = (1, 2, 4, 6)
G_ROOMS = ((8, 1, 15, 7), (19, 1, 26, 7), (30, 1, 37, 7))
G_DOORS = ((16, 4), (27, 4), (38, 4))
G_SPAWN = (2, 4)
G_ENTRY_EXIT = (1, 4)      # back up the lift: step here to leave without unlocking
G_CAGE = (43, 4)           # far lift cage: reaching it unlocks the floor

# Colossus arena.
CW, CH = 17, 13
C_ROOM = (1, 1, 15, 11)
C_SPAWN = (8, 10)
C_EXIT = (8, 11)
C_BOSS = (8, 4)

LINES = {
    "gate": "Your pick wouldn't scratch these walls yet. (Mining {need} for {floor})",
    "enter": "The lift groans down into {floor}. Something is waiting in the dark.",
    "door": "The rock door grinds open.",
    "unlock": "{floor} is yours now. The lift will bring you straight here from now on.",
    "heart_locked": "A sealed door of red crystal. Clear The Green Deep first.",
    "colossus_enter": "The Heartstone Colossus wakes. The floor shakes.",
    "colossus_dead": "The Colossus falls. The Heartstone vein glows - it is yours for 30 minutes.",
    "heart_closed": "The Heartstone vein is dark. Only a fallen Colossus wakes it.",
    "down": "You climb down into {floor}.",
    "up": "You climb back up to {floor}.",
}


def _srv():
    import server as srv
    return srv


# --------------------------------------------------------------------------- db
def ensure_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS deepdelve ("
        " player_id INTEGER PRIMARY KEY, f1 INTEGER NOT NULL DEFAULT 0,"
        " f2 INTEGER NOT NULL DEFAULT 0, f3 INTEGER NOT NULL DEFAULT 0,"
        " heart_until REAL NOT NULL DEFAULT 0, colossus_kills INTEGER NOT NULL DEFAULT 0)"
    )


def _row(conn, pid):
    ensure_table(conn)
    r = conn.execute("SELECT f1, f2, f3, heart_until, colossus_kills FROM deepdelve WHERE player_id=?",
                     (pid,)).fetchone()
    if r is None:
        conn.execute("INSERT OR IGNORE INTO deepdelve (player_id) VALUES (?)", (pid,))
        conn.commit()
        return {"f1": 0, "f2": 0, "f3": 0, "heart_until": 0.0, "colossus_kills": 0}
    return {"f1": int(r[0]), "f2": int(r[1]), "f3": int(r[2]),
            "heart_until": float(r[3] or 0), "colossus_kills": int(r[4] or 0)}


def _set(conn, pid, **fields):
    _row(conn, pid)
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE deepdelve SET {cols} WHERE player_id=?", (*fields.values(), pid))
    conn.commit()


def _conn():
    return _srv().WORLD.db.conn


def unlocked(session, floor):
    try:
        return bool(_row(_conn(), session.player_id)[f"f{int(floor)}"])
    except Exception:
        return False


def unlock(session, floor):
    _set(_conn(), session.player_id, **{f"f{int(floor)}": 1})


def heart_open(session, now=None):
    now = time.time() if now is None else now
    try:
        return _row(_conn(), session.player_id)["heart_until"] > now
    except Exception:
        return False


# --------------------------------------------------------------------------- helpers
def walkable(tiles, x, y):
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


dungeon_walkable = walkable
DUNGEON_SPAWN = G_SPAWN
CAVE_RETURN = L.UP_ARRIVE[1]


def in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def here(session):
    return bool(session.dungeon) and session.dungeon.get("id") == DEEPDELVE_ID


def state(session):
    return (session.dungeon or {}).get("deepdelve") or {}


async def say(session, key, **kw):
    srv = _srv()
    await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": LINES[key].format(**kw)})


def _rect(t, r, v=FLOOR):
    for y in range(r[1], r[3] + 1):
        for x in range(r[0], r[2] + 1):
            t[y][x] = v


def gauntlet_tiles():
    t = [[WALL] * GW for _ in range(GH)]
    _rect(t, G_LANDING)
    _rect(t, (G_LANDING[2] + 1, 4, G_ROOMS[0][0] - 1, 4))
    for i, room in enumerate(G_ROOMS):
        _rect(t, room)
        nxt = G_ROOMS[i + 1][0] - 1 if i + 1 < len(G_ROOMS) else 44
        _rect(t, (room[2] + 1, 4, nxt, 4))
    _rect(t, (41, 3, 44, 5))
    for room in G_ROOMS:
        for x, y in ((room[0], room[1]), (room[2], room[1]), (room[0], room[3]), (room[2], room[3])):
            t[y][x] = WALL
    for dx, dy in G_DOORS:
        t[dy][dx] = WALL
    return t


def _round_room(t, r, keep=()):
    """Knock the square corners off a room so it reads as a cave (same cells both sides)."""
    cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
    ax, ay = (r[2] - r[0]) / 2.0 + 0.5, (r[3] - r[1]) / 2.0 + 0.5
    for y in range(r[1], r[3] + 1):
        for x in range(r[0], r[2] + 1):
            if (x, y) in keep:
                continue
            bump = ((x * 7 + y * 13) % 5) * 0.03
            if ((x - cx) / ax) ** 2 + ((y - cy) / ay) ** 2 > 1.12 + bump:
                t[y][x] = WALL


def colossus_tiles():
    t = [[WALL] * CW for _ in range(CH)]
    _rect(t, C_ROOM)
    _round_room(t, C_ROOM, keep={C_SPAWN, C_EXIT, C_BOSS, (8, 9)})
    return t


def _spawn(session, mtype, x, y, room):
    srv = _srv()
    mid = srv.next_id()
    m = srv.MonsterInstance(mid, mtype, x, y, no_respawn=True)
    m.home_room = room
    session.dungeon["monsters"][mid] = m
    return m


def _place(session, xy):
    session.x, session.y = xy
    session.in_combat_with = None
    session.gathering_node = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


# --------------------------------------------------------------------------- build
def build_gauntlet(session, floor):
    session.dungeon = {
        "id": DEEPDELVE_ID, "explore": True, "floor": 1, "floors": 1,
        "label": L.FLOOR_NAMES.get(floor, "Deepdelve"), "name": "Deepdelve Mine",
        "tiles": gauntlet_tiles(), "width": GW, "height": GH, "monsters": {},
        "return_x": L.UP_ARRIVE[floor][0], "return_y": L.UP_ARRIVE[floor][1],
        "exit_x": G_ENTRY_EXIT[0], "exit_y": G_ENTRY_EXIT[1], "props": [],
        "deepdelve": {"kind": "gauntlet", "mine_floor": floor, "open": [False, False, False]},
    }
    for i, (mtype, room) in enumerate(zip(GAUNTLETS[floor], G_ROOMS)):
        cx = (room[0] + room[2]) // 2 + 1
        _spawn(session, mtype, cx, 4, room)
    _place(session, G_SPAWN)


def build_colossus(session):
    session.dungeon = {
        "id": DEEPDELVE_ID, "explore": True, "floor": 1, "floors": 1,
        "label": "Heartstone Vault", "name": "Deepdelve Mine",
        "tiles": colossus_tiles(), "width": CW, "height": CH, "monsters": {},
        "return_x": L.HEART_DOOR_STAND[0], "return_y": L.HEART_DOOR_STAND[1],
        "exit_x": C_EXIT[0], "exit_y": C_EXIT[1], "props": [],
        "deepdelve": {"kind": "colossus", "mine_floor": 3, "open": []},
    }
    _spawn(session, COLOSSUS, C_BOSS[0], C_BOSS[1], C_ROOM)
    _place(session, C_SPAWN)


def client_extra(session):
    st = state(session)
    d = session.dungeon or {}
    out = {"kind": st.get("kind"), "mine_floor": st.get("mine_floor"), "label": d.get("label")}
    if st.get("kind") == "gauntlet":
        out.update({"rooms": [list(r) for r in G_ROOMS], "doors": [list(g) for g in G_DOORS],
                    "open": list(st.get("open") or []), "cage": list(G_CAGE),
                    "entry": list(G_ENTRY_EXIT), "landing": list(G_LANDING)})
    else:
        out.update({"room": list(C_ROOM), "exit": list(C_EXIT)})
    return out


async def _enter(session, return_xy):
    srv = _srv()
    session._dungeon_return = tuple(return_xy)
    srv.WORLD.db.save_player_position(session.player_id, *return_xy)
    srv._clear_dungeon_resume(session)
    srv._bring_pet(session)
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def enter_gauntlet(session, floor):
    build_gauntlet(session, floor)
    await _enter(session, L.UP_ARRIVE[floor])
    await say(session, "enter", floor=L.FLOOR_NAMES[floor])


async def enter_colossus(session):
    build_colossus(session)
    await _enter(session, L.HEART_DOOR_STAND)
    await say(session, "colossus_enter")


async def _teleport(session, xy, level_change=None):
    srv = _srv()
    _place(session, xy)
    srv.WORLD.db.save_player_position(session.player_id, *xy)
    # level_change: informational only; the client spots the level change from the
    # player's tile and plays its own short fade (deepdelve_client.light).
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())


async def _go_down(session, floor, refuse_xy):
    """Down to mine level `floor` (2 or 3): gate, then gauntlet once, then straight there."""
    need = L.FLOOR_GATE[floor]
    if session.level("mining") < need:
        await say(session, "gate", need=need, floor=L.FLOOR_NAMES[floor])
        await _teleport(session, refuse_xy)
        return True
    if unlocked(session, floor):
        await _teleport(session, L.CHAMBER_ARRIVE[floor], level_change=floor)
        await say(session, "down", floor=L.LEVEL_NAMES[floor])
    else:
        await enter_gauntlet(session, floor)
    return True


# --------------------------------------------------------------------------- overworld pads
async def on_overworld_step(session):
    """Lift pads and the Heart door. Returns True if the player was moved."""
    xy = (session.x, session.y)
    if xy in L.TUNNEL_DOWN:
        return await _go_down(session, 2, L.TUNNEL_DOWN[xy])
    if xy == tuple(L.SHAFT_DOWN):
        return await _go_down(session, 3, L.SHAFT_DOWN_STAND)
    for floor, pad in L.LIFT_PADS.items():
        if xy == tuple(pad):
            need = L.FLOOR_GATE[floor]
            if session.level("mining") < need:
                await say(session, "gate", need=need, floor=L.FLOOR_NAMES[floor])
                return False
            if unlocked(session, floor):
                await _teleport(session, L.CHAMBER_ARRIVE[floor])
            else:
                await enter_gauntlet(session, floor)
            return True
    for floor, pad in L.LIFT_UP.items():
        if xy == tuple(pad):
            up = L.level_at(*L.UP_ARRIVE[floor])
            await _teleport(session, L.UP_ARRIVE[floor], level_change=up if floor >= 2 else None)
            if floor >= 2:
                await say(session, "up", floor=L.LEVEL_NAMES[up])
            return True
    if xy == tuple(L.HEART_DOOR):
        if not unlocked(session, 3):
            await say(session, "heart_locked")
            await _teleport(session, L.HEART_DOOR_STAND)
            return True
        await enter_colossus(session)
        return True
    return False


# --------------------------------------------------------------------------- instance events
async def on_step(session):
    """After a step inside. Returns True if the step left the dungeon."""
    srv = _srv()
    st = state(session)
    if st.get("kind") == "gauntlet" and (session.x, session.y) == G_CAGE:
        floor = st["mine_floor"]
        unlock(session, floor)
        session._dungeon_return = tuple(L.CHAMBER_ARRIVE[floor])
        await srv.handle_leave_dungeon(session, silent=True)
        await say(session, "unlock", floor=L.FLOOR_NAMES[floor])
        return True
    return False


async def on_kill(session, monster):
    srv = _srv()
    st = state(session)
    if st.get("kind") == "gauntlet":
        for i, room in enumerate(G_ROOMS):
            if st["open"][i] or not in_rect(monster.spawn_x, monster.spawn_y, room):
                continue
            alive = [m for m in session.dungeon["monsters"].values()
                     if m.alive and in_rect(m.spawn_x, m.spawn_y, room)]
            if not alive:
                st["open"][i] = True
                dx, dy = G_DOORS[i]
                session.dungeon["tiles"][dy][dx] = FLOOR
                await srv.send(session.ws, "DUNGEON_TILES", changes=[[dx, dy, FLOOR]])
                await say(session, "door")
    elif st.get("kind") == "colossus" and monster.type == COLOSSUS:
        row = _row(_conn(), session.player_id)
        _set(_conn(), session.player_id, heart_until=time.time() + HEART_OPEN_S,
             colossus_kills=row["colossus_kills"] + 1)
        await say(session, "colossus_dead")


# --------------------------------------------------------------------------- gathering
def can_gather(session, node_type):
    """None if fine, else the refusal text."""
    if node_type == "heart_vein" and not heart_open(session):
        return LINES["heart_closed"]
    return None


def gather_item(node_type, ydef, rng=random):
    table = ydef.get("gem_table")
    if table:
        total = sum(w for _, w in table)
        r = rng.uniform(0, total)
        for item, w in table:
            r -= w
            if r <= 0:
                return item
        return table[-1][0]
    return ydef["item"]


def heart_depletes(node_type):
    return node_type != "heart_vein"
