"""King's Row player housing. Flag off leaves the map and NPCs alone."""
from __future__ import annotations

import json
import time
from pathlib import Path

import feature_flags

# Houses are re-laid on open grass. The office is the northernmost building
# so it is the first thing you reach. Gaps between footprints are 5 or 6 tiles.
# King's Folly's pack spot crossed the dungeon, and the row is too wide for
# the west meadow, so the smaller homes continue on the grass south of the city.
_LAYOUT = {
    "estate_office": (2, 94),
    "kings_folly": (2, 109),
    "crown_villa": (25, 109),
    "cedar_townhouse": (16, 111),
    "riverview_estate": (2, 130),
    "meadow_house": (16, 131),
    "stonehaven_row": (26, 131),
    "ash_manor": (92, 136),
    "oak_villa": (108, 137),
    "reed_cottage": (123, 138),
    "willow_cottage": (136, 138),
}
WEEK = 7 * 24 * 3600
LEASE_GOLD = 50_000

_ROOT = Path(__file__).resolve().parent.parent / "client" / "assets" / "housing"
_ESTATE = None
_HOUSES = {}
_WORLD = None
_SEND = None


def enabled():
    return feature_flags.USE_PLAYER_HOUSING


def bind(world):
    global _WORLD
    _WORLD = world
    if enabled():
        ensure_schema(world.db.conn)
        install_items()


async def _send(ws, *args, **kwargs):
    import sys
    fn = getattr(sys.modules.get("__main__"), "send", None)
    if fn is None:
        import server
        fn = server.send
    await fn(ws, *args, **kwargs)


def load():
    global _ESTATE, _HOUSES
    if _ESTATE is not None:
        return _ESTATE
    with (_ROOT / "estate.json").open(encoding="utf-8") as handle:
        _ESTATE = json.load(handle)
    houses = []
    for house in _ESTATE.get("houses", []):
        houses.append(_move(house))
    _ESTATE["houses"] = houses
    office = _ESTATE.get("agent")
    if office:
        office = _move(dict(office))
        office["key"] = office.get("key") or "estate_office"
        office["name"] = "Estate Agent"
        office["office"] = True
    _HOUSES = {house["key"]: house for house in houses}
    if office:
        _HOUSES[office["key"]] = office
    _ESTATE["office"] = office
    return _ESTATE


def houses():
    load()
    return [house for house in _HOUSES.values() if not house.get("office")]


def office():
    load()
    return _ESTATE.get("office")


def house_by_key(key):
    load()
    return _HOUSES.get(key)


def _move(house):
    """Slide a pack footprint so its northwest corner sits on the new plot."""
    spot = _LAYOUT.get(house.get("key") or house.get("building_id"))
    if spot is None:
        return house
    house = json.loads(json.dumps(house))
    fp = house["footprint"]
    dx = int(spot[0]) - int(fp["x0"])
    dy = int(spot[1]) - int(fp["y0"])
    fp["x0"] += dx
    fp["x1"] += dx
    fp["y0"] += dy
    fp["y1"] += dy
    fl = house["floor"]
    fl["floor_x0"] += dx
    fl["floor_x1"] += dx
    fl["floor_y0"] += dy
    fl["floor_y1"] += dy
    door = house["door"]
    door["x"] += dx
    door["y"] += dy
    door["enter"][0] += dx
    door["enter"][1] += dy
    door["exit"][0] += dx
    door["exit"][1] += dy
    door["doorway_path_tiles"] = [[x + dx, y + dy] for x, y in door["doorway_path_tiles"]]
    return house


def attach(npcs):
    if not enabled():
        return
    if any(npc.get("id") == "estate_agent_mira" for npc in npcs):
        return
    spot = office()
    enter = (spot or {}).get("door", {}).get("enter") or [27, 138]
    npcs.append({
        "id": "estate_agent_mira",
        "name": "Estate Agent Mira",
        "x": int(enter[0]),
        "y": int(enter[1]),
        "lines": [
            "King's Row. The office is the building to the north. Homes are south of it, and more stand along the south road.",
            "The weekly lease is 50,000 gold. Miss it, and you have a week of grace.",
            "Press B to see what is still for sale.",
        ],
        "housing": True,
    })


def install_items():
    if not enabled():
        return
    from content import ITEMS
    for house in houses():
        item_id = (house.get("ownership") or {}).get("deed_item") or f"deed_{house['key']}"
        ITEMS.setdefault(item_id, {
            "name": f"Deed: {house['name']}",
            "examine": f"Proves you own {house['name']}.",
            "tradeable": False,
            "sellable": False,
            "bankable": True,
            "stackable": False,
        })


def ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS housing_deeds (
            house_key TEXT PRIMARY KEY,
            owner_id INTEGER,
            owner_name TEXT,
            deed_issued_at REAL,
            lease_paid_through REAL,
            grace_until REAL
        )"""
    )
    conn.commit()


def stamp(grid, wm):
    """Paint shells and lanes onto empty grass. Never touch the dungeon."""
    if not enabled():
        return
    load()
    soft = {wm.GRASS, wm.TREE}

    def paint_soft(x, y, tile):
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return
        if grid[y][x] in soft:
            grid[y][x] = tile

    def claim(x, y, tile):
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return
        if 44 <= x <= 90:
            return
        if grid[y][x] not in (wm.GRASS, wm.TREE, wm.PATH, wm.WALL, wm.FLOOR):
            return
        grid[y][x] = tile

    # Lanes on grass first. Shells below replace whatever they cover.
    for y in range(99, 140):
        paint_soft(12, y, wm.PATH)
        paint_soft(24, y, wm.PATH)
    for x in range(92, 148):
        paint_soft(x, 143, wm.PATH)
    for house in list(houses()) + [office()]:
        if not house:
            continue
        door = house["door"]
        ex, ey = int(door["exit"][0]), int(door["exit"][1])
        for ox in range(-2, 3):
            paint_soft(ex + ox, ey, wm.PATH)

    for house in list(houses()) + [office()]:
        if not house:
            continue
        fp = house["footprint"]
        fl = house["floor"]
        door = house["door"]
        for y in range(int(fp["y0"]), int(fp["y1"]) + 1):
            for x in range(int(fp["x0"]), int(fp["x1"]) + 1):
                claim(x, y, wm.WALL)
        for y in range(int(fl["floor_y0"]), int(fl["floor_y1"]) + 1):
            for x in range(int(fl["floor_x0"]), int(fl["floor_x1"]) + 1):
                claim(x, y, wm.FLOOR)
        for x, y in door.get("doorway_path_tiles") or []:
            claim(int(x), int(y), wm.PATH)
        claim(int(door["x"]), int(door["y"]), wm.PATH)
        claim(int(door["exit"][0]), int(door["exit"][1]), wm.PATH)


def owners(conn):
    rows = conn.execute(
        "SELECT house_key, owner_id, owner_name, lease_paid_through, grace_until FROM housing_deeds"
    ).fetchall()
    return {row[0]: {
        "owner_id": row[1],
        "owner_name": row[2],
        "lease_paid_through": row[3],
        "grace_until": row[4],
    } for row in rows}


def public_owners(conn):
    return {key: row["owner_name"] for key, row in owners(conn).items()}


def lots(conn):
    owned = owners(conn)
    out = []
    for house in houses():
        row = owned.get(house["key"])
        out.append({
            "key": house["key"],
            "name": house["name"],
            "price": int(house["price_gold"]),
            "floors": int(house["floors"]),
            "owner": None if row is None else row["owner_name"],
            "vacant": row is None,
        })
    return out


def _deed_id(house):
    return (house.get("ownership") or {}).get("deed_item") or f"deed_{house['key']}"


def _strip_deed(session, item_id):
    world = _WORLD
    if world is None:
        return
    world.remove_item_qty(session, item_id, 99)
    for slot, entry in list(session.bank.items()):
        if entry.get("item_id") == item_id:
            del session.bank[slot]
            world.db.clear_bank_slot(session.player_id, slot)


async def on_login(session):
    if not enabled() or _WORLD is None:
        return
    await settle_lease(session, quiet=False)
    await _send(session.ws, "HOUSING_OWNERS", owners=public_owners(_WORLD.db.conn))


async def open_lots(session):
    await _send(session.ws, "HOUSING_LIST", lots=lots(_WORLD.db.conn), bank_coins=int(session.bank_coins))


async def buy(session, key):
    house = house_by_key(key)
    if house is None or house.get("office"):
        await _send(session.ws, "ERROR", message="That home is not for sale.")
        return
    conn = _WORLD.db.conn
    owned = owners(conn)
    if key in owned:
        await _send(session.ws, "ERROR", message="Someone already owns that home.")
        return
    if any(row["owner_id"] == session.player_id for row in owned.values()):
        await _send(session.ws, "ERROR", message="You already own a home on King's Row.")
        return
    price = int(house["price_gold"])
    if int(session.bank_coins) < price:
        await _send(session.ws, "ERROR", message="Not enough gold in your bank.")
        return
    session.bank_coins -= price
    _WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
    now = time.time()
    conn.execute(
        """INSERT INTO housing_deeds
           (house_key, owner_id, owner_name, deed_issued_at, lease_paid_through, grace_until)
           VALUES (?, ?, ?, ?, ?, NULL)""",
        (key, session.player_id, session.char_name, now, now + WEEK),
    )
    conn.commit()
    install_items()
    deed = _deed_id(house)
    if not _WORLD.add_item_to_inventory(session, deed, 1):
        await _send(session.ws, "CHAT_MSG", **{
            "from": "Estate",
            "text": "Your pack is full. The deed is recorded at the office; make a space and speak to Mira again.",
        })
    await _send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await _send(session.ws, "CHAT_MSG", **{
        "from": "Estate Agent Mira",
        "text": f"{house['name']} is yours. The first lease is due in seven days.",
    })
    await _broadcast_owners()
    await open_lots(session)


async def _broadcast_owners():
    payload = public_owners(_WORLD.db.conn)
    for session in list(_WORLD.sessions.values()):
        try:
            await _send(session.ws, "HOUSING_OWNERS", owners=payload)
        except Exception:
            pass


def allow_step(session, nx, ny):
    level = int(getattr(session, "house_level", 0) or 0)
    if level <= 0:
        return True
    house = _inside_floor(session.x, session.y)
    if house is None:
        session.house_level = 0
        return True
    fl = house["floor"]
    if fl["floor_x0"] <= nx <= fl["floor_x1"] and fl["floor_y0"] <= ny <= fl["floor_y1"]:
        return True
    return False


async def on_step(session):
    house = _inside_floor(session.x, session.y)
    if house is None:
        if int(getattr(session, "house_level", 0) or 0):
            session.house_level = 0
            await _send(session.ws, "HOUSE_LEVEL", level=0, floor="", house="")
        session.house_level = 0
        session.stair_lock = None
        return
    plans = house.get("floor_plans") or []
    level = int(getattr(session, "house_level", 0) or 0)
    if level >= len(plans):
        session.house_level = 0
        level = 0
    if not plans:
        return
    plan = plans[level]
    local = (session.x - int(house["floor"]["floor_x0"]), session.y - int(house["floor"]["floor_y0"]))
    if getattr(session, "stair_lock", None) == (session.x, session.y):
        return
    up = tuple(plan["stairs_up"]) if plan.get("stairs_up") else None
    down = tuple(plan["stairs_down"]) if plan.get("stairs_down") else None
    name = None
    if up and local == tuple(up) and level + 1 < len(plans):
        session.house_level = level + 1
        session.stair_lock = (session.x, session.y)
        name = plans[level + 1].get("name") or "Upper"
    elif down and local == tuple(down) and level > 0:
        session.house_level = level - 1
        session.stair_lock = (session.x, session.y)
        name = plans[level - 1].get("name") or "Ground"
    else:
        session.stair_lock = None
        return
    await _send(session.ws, "HOUSE_LEVEL", level=session.house_level, floor=name, house=house["key"])
    await _send(session.ws, "CHAT_MSG", **{"from": house["name"], "text": f"You climb to the {name}."})


def _inside_floor(x, y):
    load()
    for house in _HOUSES.values():
        fl = house.get("floor") or {}
        if fl.get("floor_x0", 1) <= x <= fl.get("floor_x1", 0) and fl.get("floor_y0", 1) <= y <= fl.get("floor_y1", 0):
            return house
    return None


async def settle_lease(session, quiet=False):
    if not enabled() or _WORLD is None:
        return
    conn = _WORLD.db.conn
    row = conn.execute(
        "SELECT house_key, lease_paid_through, grace_until FROM housing_deeds WHERE owner_id = ?",
        (session.player_id,),
    ).fetchone()
    if row is None:
        return
    key, paid_through, grace_until = row
    house = house_by_key(key)
    if house is None:
        return
    now = time.time()
    if paid_through is None or now <= float(paid_through):
        return
    if int(session.bank_coins) >= LEASE_GOLD:
        session.bank_coins -= LEASE_GOLD
        _WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
        nxt = float(paid_through) + WEEK
        while nxt < now:
            nxt += WEEK
        conn.execute(
            "UPDATE housing_deeds SET lease_paid_through = ?, grace_until = NULL WHERE house_key = ?",
            (nxt, key),
        )
        conn.commit()
        if not quiet:
            await _send(session.ws, "CHAT_MSG", **{
                "from": "Estate",
                "text": f"The king collects {LEASE_GOLD:,} gold from your bank for {house['name']}.",
            })
            await _send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return
    if grace_until is None:
        grace = now + WEEK
        conn.execute("UPDATE housing_deeds SET grace_until = ? WHERE house_key = ?", (grace, key))
        conn.commit()
        await _send(session.ws, "CHAT_MSG", **{
            "from": "Estate",
            "text": f"Your bank cannot pay the lease on {house['name']}. You have seven days of grace.",
        })
        return
    if now <= float(grace_until):
        return
    _strip_deed(session, _deed_id(house))
    conn.execute("DELETE FROM housing_deeds WHERE house_key = ?", (key,))
    conn.commit()
    await _send(session.ws, "CHAT_MSG", **{
        "from": "Estate",
        "text": f"The lease on {house['name']} went unpaid. The deed is void and the home is for sale again.",
    })
    await _send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await _broadcast_owners()


async def tick_leases():
    if not enabled() or _WORLD is None:
        return
    for session in list(_WORLD.sessions.values()):
        try:
            await settle_lease(session)
        except Exception:
            pass
