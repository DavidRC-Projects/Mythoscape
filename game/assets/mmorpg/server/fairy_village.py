"""Moonpetal Glade. Always on: no feature flag.

The stamp paints the old mine into the glade and blocks building and
fountain footprints with WALL. Fountains are never WATER.
"""
from __future__ import annotations

import json
import os
import time

_DATA = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "fairy_village", "data",
))
_DIALOGUE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "fairy_village", "dialogue", "fairy_story.json",
))

FAIRY_NPCS = {
    "elowen_moonwhisper",
    "warden_thorne",
    "tumbleroot",
    "pip_dewdrop",
}

# Overworld crypt mouth. The interior door stays at (46, 71).
CRYPT_ENTRANCE = (54, 80)
CRYPT_PAD = (52, 79, 56, 83)

_FENCE = None

_STORY = None
_MOONWATER_WAIT = 60.0
_MOONWATER_HEAL = 8


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def story():
    global _STORY
    if _STORY is None:
        _STORY = _load_json(_DIALOGUE)
    return _STORY


def stamp(grid):
    """Paint the glade, then WALL every blocked footprint cell."""
    import world_map as wm

    names = {
        "GRASS": wm.GRASS,
        "PATH": wm.PATH,
        "STONE": wm.STONE,
        "WALL": wm.WALL,
        "FLOOR": wm.FLOOR,
    }
    layout = _load_json(os.path.join(_DATA, "village_layout.json"))
    height = len(grid)
    width = len(grid[0]) if height else 0

    def put(x, y, tile):
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = tile

    for op in layout.get("paint_ops") or []:
        tile = names.get(op.get("tile"), wm.GRASS)
        x0, y0, x1, y1 = op["rect"]
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                put(x, y, tile)
    for name in list(layout.get("buildings") or []) + list(layout.get("fountains") or []):
        path = os.path.join(_DATA, "collision", name + ".json")
        if not os.path.isfile(path):
            continue
        blocked = _load_json(path).get("blocked_tiles") or []
        for x, y in blocked:
            put(int(x), int(y), wm.WALL)
    # Old mouth, painted before capture so the saved interior stays as it was.
    for x in (45, 46, 47):
        for y in (79, 80, 81):
            put(x, y, wm.PATH)
    for x, y in fence_cells():
        if grid[y][x] in (wm.GRASS,) or grid[y][x] in wm.TREE_TILES:
            put(x, y, wm.WALL)


def fence_cells():
    """Picket posts around the glade. The roads stay open."""
    global _FENCE
    if _FENCE is None:
        cells = set()
        for x in range(1, 42):
            if x not in (27, 28, 29):
                cells.add((x, 55))
                cells.add((x, 89))
        for y in range(55, 90):
            if y not in (70, 71, 72, 81, 82, 83):
                cells.add((41, y))
        for y in range(56, 89):
            cells.add((1, y))
        _FENCE = cells
    return _FENCE


def is_fence(x, y):
    return (int(x), int(y)) in fence_cells()


def lay_crypt_path(grid):
    """Walkway from the glade to the crypt. Runs after the dungeon interior is saved."""
    import world_map as wm

    height = len(grid)
    width = len(grid[0]) if height else 0
    x0, y0, x1, y1 = CRYPT_PAD

    def put(x, y):
        if 0 <= x < width and 0 <= y < height and not is_fence(x, y):
            grid[y][x] = wm.PATH

    for y in (81, 82, 83):
        for x in range(30, x1 + 1):
            put(x, y)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(x, y)


def oath_progress(session):
    """Four objective lines and whether all of them are done."""
    from content import QUESTS
    import castle_owners
    import clans
    from server import WORLD, quest_status_for

    combat = int(session.combat_level())
    owned = 0
    try:
        rows = castle_owners.owners(WORLD.db.conn).values()
    except Exception:
        rows = []
    for row in rows:
        if int(row.get("owner_id") or 0) == int(session.player_id):
            owned = 1
            break
    others = [qid for qid in QUESTS if qid != "fairy_oath"]
    done_q = sum(
        1 for qid in others
        if (quest_status_for(session, qid) or {}).get("status") == "complete"
    )
    clan_id = clans.clan_of(session.player_id)
    members = clans.member_count(clan_id) if clan_id else 0
    lines = [
        ("✓ " if combat >= 100 else "") + f"Combat {combat}/100",
        ("✓ " if owned else "") + f"Castle {owned}/1",
        ("✓ " if others and done_q >= len(others) else "") + f"Quests {done_q}/{len(others)}",
        ("✓ " if members >= 25 else "") + f"{members}/25 members",
    ]
    ready = combat >= 100 and owned >= 1 and others and done_q >= len(others) and members >= 25
    return lines, ready


def objective_text(session):
    lines, _ready = oath_progress(session)
    return " · ".join(lines)


async def open_talk(session, npc):
    """Elowen's pages, or the short lines for the other three fairies."""
    from server import WORLD, send, quest_status_for

    data = story()
    npc_id = npc["id"]
    if npc_id != "elowen_moonwhisper":
        pages = ((data.get("other_npcs") or {}).get(npc_id) or {}).get("pages") or []
        flat = []
        for page in pages:
            flat.extend(page)
        await send(
            session.ws, "DIALOGUE",
            npc_id=npc_id, npc_name=npc["name"],
            lines=flat or npc.get("lines") or [],
            pages=pages or None,
            shop_id=npc.get("shop_id"),
        )
        if npc.get("shop_id"):
            from server import send_shop_state
            await send_shop_state(session, npc["shop_id"])
        return

    lines, ready = oath_progress(session)
    status_line = " · ".join(lines)
    prog = session.quests.get("fairy_oath")
    if prog is None:
        session.quests["fairy_oath"] = {"status": "active", "progress": 0}
        WORLD.db.set_quest_progress(session.player_id, "fairy_oath", "active", 0)
        pages = [list(page.get("lines") or []) for page in data.get("pages") or []]
    elif ready:
        if prog.get("status") != "complete":
            session.quests["fairy_oath"] = {"status": "complete", "progress": 1}
            WORLD.db.set_quest_progress(session.player_id, "fairy_oath", "complete", 1)
        pages = [list((data.get("repeat_pages") or {}).get("all_done") or [])]
    else:
        raw = list((data.get("repeat_pages") or {}).get("in_progress") or [])
        pages = [[line.replace("{objectives_status}", status_line) for line in raw]]
    quest_info = {
        "quest_id": "fairy_oath",
        "name": data.get("quest_title") or "The Moonwater Oath",
        "description": status_line,
        "state": "complete" if ready else "active",
        "objective": status_line,
        "quest_points": 1,
    }
    await send(
        session.ws, "DIALOGUE",
        npc_id=npc_id, npc_name=npc["name"],
        lines=pages[0] if pages else [],
        pages=pages,
        quest=quest_info,
    )
    await send(
        session.ws, "QUEST_LOG",
        quests={qid: quest_status_for(session, qid) for qid in __import__("content").QUESTS},
    )


async def act(session, spot_id):
    """Door flavour or a drink from a fountain. Once a minute."""
    from content import INTERACTABLES
    from server import WORLD, send

    spot = next((s for s in INTERACTABLES if s.get("id") == spot_id), None)
    if spot is None:
        return
    sx, sy = int(spot["x"]), int(spot["y"])
    stand = spot.get("stand") or [sx, sy]
    near = (
        max(abs(session.x - sx), abs(session.y - sy)) <= 1
        or (session.x, session.y) == (int(stand[0]), int(stand[1]))
    )
    if not near:
        await send(session.ws, "ERROR", message="Get closer.")
        return
    if spot.get("kind") == "moonwater":
        now = time.time()
        last = float(getattr(session, "moonwater_at", 0) or 0)
        if now - last < _MOONWATER_WAIT:
            wait = int(_MOONWATER_WAIT - (now - last)) + 1
            await send(session.ws, "CHAT_MSG", **{
                "from": spot.get("name") or "Fountain",
                "text": f"The Moonwater is still settling. Try again in {wait}s.",
            })
            return
        session.moonwater_at = now
        before = session.hp
        session.hp = min(session.max_hp(), session.hp + _MOONWATER_HEAL)
        WORLD.db.save_player_stats(session.player_id, hp=session.hp)
        gained = session.hp - before
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": spot.get("name") or "Fountain",
            "text": "You drink the Moonwater." + (f" (+{gained} hp)" if gained else " You already feel whole."),
        })
        return
    for line in spot.get("lines") or ["The door is shut."]:
        await send(session.ws, "CHAT_MSG", **{"from": spot.get("name") or "Door", "text": line})
    if spot.get("shop_id"):
        from server import send_shop_state
        await send_shop_state(session, spot["shop_id"])
