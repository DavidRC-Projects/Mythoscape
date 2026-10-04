"""Shared dungeon v2 actions: doors, secrets, chests, caches, lore, shrine, lever.

Void Sanctum keeps its own copy of these steps. The Depths crypt calls this
module so the same rules are not written a second time. Crypt-only rolls
(sarcophagi, grasping hands, Morvath) stay in depths_v2.
"""
import random


def _world():
    import server as srv
    return getattr(srv, "WORLD", None)


def _has_item(session, item_id):
    return any(e.get("item_id") == item_id for e in session.inventory.values())


def _take_one(session, item_id):
    world = _world()
    if world is None:
        return False
    return world.remove_item_qty(session, item_id, 1)


def _give(session, item_id, qty):
    world = _world()
    if item_id == "coins":
        if world:
            world.add_coins(session, qty)
        return True
    if world and world.add_item_to_inventory(session, item_id, qty):
        return True
    return False


def _refresh(d):
    import depths_v2
    depths_v2.refresh(d)


def _changes_from(before, after):
    changes = []
    for y, row in enumerate(after):
        for x, tile in enumerate(row):
            if before[y][x] != tile:
                changes.append([x, y, tile])
    return changes


async def grant_table(session, table, speaker="Loot"):
    import server as srv
    got = []
    for row in table:
        item_id, bounds = row[0], row[1]
        chance = row[2] if len(row) > 2 else 1.0
        if random.random() > chance:
            continue
        if isinstance(item_id, tuple):
            item_id = random.choice(item_id)
        qty = random.randint(bounds[0], bounds[1])
        if _give(session, item_id, qty):
            from content import ITEMS
            name = ITEMS.get(item_id, {}).get("name", item_id)
            got.append(f"{qty}x {name}" if qty > 1 else name)
        else:
            await srv.send(session.ws, "CHAT_MSG", **{"from": speaker, "text": "Your inventory is full."})
            break
    if got:
        await srv.send(session.ws, "CHAT_MSG", **{"from": speaker, "text": "Loot: " + ", ".join(got) + "."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    return got


async def try_blocked_step(session, nx, ny):
    """Walking into a locked door with the key opens it. A bare bump explains the lock."""
    import time
    d = session.dungeon
    spec = (d or {}).get("spec") or {}
    if not d or not spec:
        return None
    if not (0 <= ny < d["height"] and 0 <= nx < d["width"]):
        return None
    ch = d["chars"][ny][nx]
    doors = spec.get("doors") or {}
    secrets = spec.get("secrets") or {}
    is_secret = any(tuple(secret.get("wall") or ()) == (nx, ny) for secret in secrets.values())
    if ch not in doors and not is_secret:
        return None
    if ch in doors and ch in d.get("opened", []):
        return None
    now = time.time()
    if getattr(session, "_block_hint_tile", None) == (nx, ny) and now < getattr(session, "_block_hint_at", 0) + 2.5:
        return "blocked"
    session._block_hint_tile = (nx, ny)
    session._block_hint_at = now
    await handle_interact(session, {"x": nx, "y": ny})
    from world_map import WALL
    tiles = d.get("tiles") or []
    if 0 <= ny < len(tiles) and tiles[ny][nx] != WALL:
        return "opened"
    return "blocked"


async def handle_interact(session, msg):
    """Doors, secrets, pedestal, chests, caches, notes, shrine, and the shortcut lever."""
    import server as srv
    d = session.dungeon
    spec = (d or {}).get("spec") or {}
    if not d or not spec:
        return False
    who = spec.get("chat_from") or "Dungeon"
    try:
        x, y = int(msg.get("x")), int(msg.get("y"))
    except (TypeError, ValueError):
        return False
    if max(abs(session.x - x), abs(session.y - y)) > 1:
        await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "You need to stand next to that."})
        return True
    if not (0 <= y < d["height"] and 0 <= x < d["width"]):
        return True
    ch = d["chars"][y][x]
    doors = spec.get("doors") or {}
    if ch in doors and ch not in d["opened"]:
        _x, _y, key, name = doors[ch]
        if not _has_item(session, key):
            hint = (spec.get("door_hints") or {}).get(ch) or f"The {name} is locked."
            await srv.send(session.ws, "CHAT_MSG", **{"from": name, "text": hint})
            return True
        _take_one(session, key)
        d["opened"].append(ch)
        srv._save_dungeon_resume(session)
        before = [row[:] for row in d["tiles"]]
        _refresh(d)
        changes = _changes_from(before, d["tiles"])
        await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
        await srv.send(session.ws, "CHAT_MSG", **{"from": name, "text": f"The {name} grinds open."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return True
    for sid, secret in (spec.get("secrets") or {}).items():
        if tuple(secret["wall"]) == (x, y) and sid not in d["secrets"]:
            d["secrets"].append(sid)
            before = [row[:] for row in d["tiles"]]
            _refresh(d)
            changes = _changes_from(before, d["tiles"])
            await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
            await srv.send(session.ws, "CHAT_MSG", **{
                "from": who, "text": "The wall gives way. A hidden room opens.",
            })
            return True
    if ch == "k" and not d.get("pedestal"):
        if not _revealed(x, y, set(d["secrets"]), spec.get("secrets") or {}):
            return True
        item_id = spec.get("pedestal_item")
        if not item_id:
            return True
        d["pedestal"] = True
        if _give(session, item_id, 1):
            text = spec.get("pedestal_text") or "You take the key from the pedestal."
            await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": text})
        else:
            d["pedestal"] = False
            await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "Your inventory is full."})
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        _refresh(d)
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return True
    if ch == "c":
        key = f"{x},{y}"
        if key in d["chests"]:
            await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "The chest is empty."})
            return True
        table_name = (spec.get("chests") or {}).get(key)
        table = (spec.get("chest_loot") or {}).get(table_name)
        if not table:
            return True
        d["chests"].append(key)
        await grant_table(session, table, who)
        _refresh(d)
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return True
    if ch == "g":
        key = f"{x},{y}"
        if key in d["caches"]:
            await srv.send(session.ws, "CHAT_MSG", **{"from": who, "text": "The cache is empty."})
            return True
        d["caches"].append(key)
        await grant_table(session, spec.get("cache_loot") or [("health_potion", (1, 1))], who)
        _refresh(d)
        await srv.send(session.ws, "DUNGEON_TILES", changes=[], decor=d["decor"])
        return True
    if ch == "l":
        title, text = (d.get("lore") or {}).get(f"{x},{y}", ("Note", "..."))
        if isinstance(title, (list, tuple)):
            title, text = title[0], title[1]
        await srv.send(session.ws, "LORE_NOTE", title=title, text=text)
        return True
    if ch == "H":
        if d.get("shrine_used"):
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Shrine", "text": "The shrine is dark."})
            return True
        d["shrine_used"] = True
        d["checkpoint"] = [x, y]
        heal = max(1, session.max_hp() // 2)
        session.hp = min(session.max_hp(), session.hp + heal)
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "Shrine", "text": "Warm light knits your wounds. This place will remember you.",
        })
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        return True
    if ch == "v":
        if d.get("gate_open"):
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Lever", "text": "The passage is already open."})
            return True
        d["gate_open"] = True
        world = _world()
        quest = spec.get("shortcut_quest") or "depths_shortcut"
        if world and session.player_id:
            world.db.set_quest_progress(session.player_id, quest, "complete", 1)
            session.quests[quest] = {"status": "complete", "progress": 1}
        before = [row[:] for row in d["tiles"]]
        _refresh(d)
        changes = _changes_from(before, d["tiles"])
        await srv.send(session.ws, "DUNGEON_TILES", changes=changes, decor=d["decor"])
        await srv.send(session.ws, "CHAT_MSG", **{
            "from": "Lever",
            "text": spec.get("lever_text") or "A bar lifts somewhere above.",
        })
        return True
    if ch == "w":
        await srv.send(session.ws, "WARNING_STONE")
        return True
    return False


def _revealed(x, y, open_secrets, secrets):
    for sid in open_secrets:
        spec = secrets.get(sid) or {}
        for rect in spec.get("reveal") or []:
            x0, y0, x1, y1 = rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                return True
    return False
