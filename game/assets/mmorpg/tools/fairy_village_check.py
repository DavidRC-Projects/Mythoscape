"""Moonpetal Glade overlap and reachability check.

Run from game/assets/mmorpg:

    python3 tools/fairy_village_check.py
"""
from __future__ import annotations

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SERVER = os.path.join(ROOT, "server")
sys.path.insert(0, SERVER)

import content  # noqa: E402
import explore_dungeons  # noqa: E402
import fairy_village  # noqa: E402
import housing  # noqa: E402
import world_map as wm  # noqa: E402

PLANNED = (
    (1, 56, 40, 88),     # fairy zone
    (31, 90, 43, 98),    # quarry ring
    (30, 93, 31, 95),    # quarry mouth
    (30, 81, 56, 83),    # crypt path
    (52, 79, 56, 83),    # depths pad
    (27, 89, 29, 98),    # avenue to King's Row
    (53, 79, 55, 81),    # mouth and return
    (1, 55, 41, 55),     # north picket fence
    (1, 89, 41, 89),     # south picket fence
    (41, 55, 41, 89),    # east picket fence
)
MOVED = {
    "dungeon_entrance", "dungeon_bank", "dungeon_hermit", "dungeon_gate",
    "quest_hermit_cole", "sign_dungeon", "sign_quarry",
    "elowen_moonwhisper", "warden_thorne", "tumbleroot", "pip_dewdrop",
    "queens_tree_hall_door", "moonpetal_inn_door", "mushroom_apothecary_door",
    "moonstone_fountain", "lily_fountain",
}
STANDS = [(8, 86), (20, 85), (37, 65), (28, 66), (33, 80)]
NPCS = [(24, 67), (25, 57), (39, 66), (31, 78)]
RATS = [(34, 93), (37, 94), (40, 94), (35, 95), (39, 93), (33, 94)]
MOUTH = [(53, 79), (54, 79), (55, 79), (53, 80), (54, 80), (55, 80)]
BUILDINGS = [(4, 77, 12, 85), (16, 77, 25, 84), (34, 58, 40, 64)]
# Crypt sprite: ~11 wide, ~10.5 north of the door, apron ~5 south.
CRYPT = (54 - 5, 80 - 11, 54 + 5, 80 + 5)


def _inside(x, y, rects) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)


def _overlap(a, b) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 <= bx1 and ax1 >= bx0 and ay0 <= by1 and ay1 >= by0


def _grid(stamp):
    real = fairy_village.stamp
    fairy_village.stamp = stamp
    try:
        grid = wm.generate_world()
    finally:
        fairy_village.stamp = real
    explore_dungeons.capture_and_hide(grid)
    return grid


def _bfs(grid, start):
    from collections import deque
    seen = set()
    if not wm.is_walkable(grid, *start):
        return seen
    q = deque([start])
    seen.add(start)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or not wm.is_walkable(grid, nx, ny):
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def _house_boxes():
    boxes = []
    if not housing.enabled():
        return boxes
    for house in list(housing.houses()) + ([housing.office()] if housing.office() else []):
        if not house:
            continue
        fp = house["footprint"]
        boxes.append((house.get("key") or house.get("name"), (fp["x0"], fp["y0"], fp["x1"], fp["y1"]),
                      tuple(house["door"]["exit"])))
    return boxes


def _castle_box():
    import castle_v2
    if not castle_v2.active():
        return None
    return castle_v2.footprint_tiles()


async def _clan_round():
    import sqlite3
    import types
    import clans

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, char_name TEXT)")
    conn.executemany("INSERT INTO players VALUES (?, ?)", [(1, "Ada"), (2, "Bea")])
    clans.ensure_tables(conn)
    real_db = clans._db
    clans._db = lambda: conn
    said = []

    async def say(session, text):
        said.append(text)

    async def push(clan_id):
        said.append(clans.public(clan_id))

    clans._say = say
    clans._push = push
    fake = types.ModuleType("server")

    class _W:
        sessions = {}

    fake.WORLD = _W()

    async def send(*_a, **_k):
        return None

    fake.send = send
    previous = sys.modules.get("server")
    sys.modules["server"] = fake

    class S:
        def __init__(self, pid, name):
            self.player_id = pid
            self.char_name = name
            self.ws = None

    try:
        ada, bea = S(1, "Ada"), S(2, "Bea")
        await clans.create(ada, "Moonpetal")
        await clans.invite(ada, "Bea")
        await clans.accept(bea)
        assert clans.member_count(clans.clan_of(1)) == 2, "accept did not add a member"
        await clans.kick(ada, "Bea")
        assert clans.clan_of(2) is None, "kick left Bea in the clan"
        assert clans.member_count(1) == 1
        await clans.invite(ada, "Bea")
        await clans.accept(bea)
        await clans.leave(ada)
        leader = conn.execute("SELECT leader_id FROM clans").fetchone()
        assert leader and int(leader[0]) == 2, "oldest member did not become leader"
        await clans.leave(bea)
        left = conn.execute("SELECT COUNT(*) FROM clans").fetchone()[0]
        assert left == 0, "empty clan was not deleted"
        # Persistence is the same sqlite file: reopen the connection's tables.
        clans.ensure_tables(conn)
        await clans.create(ada, "Moonpetal")
        assert clans.member_count(clans.clan_of(1)) == 1
        conn.commit()
        again = sqlite3.connect(":memory:")
        # Copy the live rows into a second connection to mimic a restart read.
        script = "\n".join(conn.iterdump())
        again.executescript(script)
        clans._db = lambda: again
        assert clans.clan_of(1) == clans.clan_of(1)
        assert again.execute("SELECT name FROM clans").fetchone()[0] == "Moonpetal"
        assert again.execute("SELECT COUNT(*) FROM clan_members").fetchone()[0] == 1
    finally:
        clans._db = real_db
        if previous is None:
            sys.modules.pop("server", None)
        else:
            sys.modules["server"] = previous
    return "clan create, invite, accept, kick, leave, leader handoff, restart read: PASS"


def check():
    fails = []
    base = _grid(lambda grid: None)
    live = _grid(fairy_village.stamp)
    changed = []
    for y in range(wm.HEIGHT):
        for x in range(wm.WIDTH):
            if base[y][x] != live[y][x]:
                changed.append((x, y))
    leaked = [xy for xy in changed if not _inside(*xy, PLANNED)]
    if leaked:
        fails.append(f"changed tiles outside planned rects: {leaked[:12]}")
    else:
        print(f"1. changed tiles inside planned rects: {len(changed)} PASS")

    houses = _house_boxes()
    castle = _castle_box()
    bad = []
    for x, y in changed:
        for key, box, _exit in houses:
            if _inside(x, y, (box,)):
                bad.append(f"house {key} tile {(x, y)}")
        if castle and _inside(x, y, (castle,)):
            bad.append(f"castle tile {(x, y)}")
    for npc in content.NPCS:
        if npc["id"] in MOVED:
            continue
        if (npc["x"], npc["y"]) in set(changed):
            bad.append(f"npc {npc['id']} on changed {(npc['x'], npc['y'])}")
    for spot in content.INTERACTABLES:
        if spot["id"] in MOVED:
            continue
        if (spot["x"], spot["y"]) in set(changed):
            bad.append(f"interactable {spot['id']} on changed {(spot['x'], spot['y'])}")
    for pin in content.TRAVEL_DESTINATIONS:
        if pin["id"] in MOVED:
            continue
        if (pin["x"], pin["y"]) in set(changed):
            bad.append(f"travel {pin['id']} on changed {(pin['x'], pin['y'])}")
    for key, box, exit_xy in houses:
        if _inside(exit_xy[0], exit_xy[1], [box]) or (exit_xy in set(changed)):
            if exit_xy in set(changed):
                bad.append(f"house exit {key} {exit_xy}")
    if bad:
        fails.append("overlap: " + "; ".join(bad[:12]))
    else:
        print("2. no house, castle, or unmoved pin on a changed tile: PASS")

    reached = _bfs(live, wm.SPAWN_POINT)
    goals = NPCS + STANDS + MOUTH + [(54, 81)] + RATS
    missing = [xy for xy in goals if xy not in reached]
    ores = [(x, y) for y in range(91, 98) for x in range(32, 43)
            if live[y][x] in (wm.ORE, wm.IRON_ORE)]
    ore_miss = []
    for x, y in ores:
        if not any((x + dx, y + dy) in reached for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            ore_miss.append((x, y))
    if len(ores) != 18:
        fails.append(f"expected 18 ores, found {len(ores)}")
    if missing or ore_miss:
        fails.append(f"unreachable {missing} ores {ore_miss}")
    else:
        print(f"3. BFS from {wm.SPAWN_POINT} reaches NPCs, stands, mouth, return, rats, ores: PASS")

    covered = []
    for box in BUILDINGS:
        if _overlap(box, CRYPT):
            covered.append(box)
    for xy in NPCS:
        if _inside(xy[0], xy[1], (CRYPT,)):
            covered.append(xy)
    if covered:
        fails.append(f"crypt sprite covers {covered}")
    else:
        print(f"4. crypt sprite {CRYPT} misses fairy buildings and NPCs: PASS")

    water = []
    for name in ("moonstone_fountain", "lily_fountain"):
        path = os.path.join(fairy_village._DATA, "collision", name + ".json")
        import json
        blocked = json.load(open(path, encoding="utf-8")).get("blocked_tiles") or []
        for x, y in blocked:
            if live[y][x] == wm.WATER:
                water.append((name, x, y))
            if live[y][x] != wm.WALL:
                water.append((name, "not wall", x, y, live[y][x]))
    if water:
        fails.append(f"fountains {water[:8]}")
    else:
        print("fountains are WALL, not fishing water: PASS")

    mouth = content.entrance_mouth_tiles(54, 80)
    if mouth != set(MOUTH):
        fails.append(f"mouth tiles {sorted(mouth)}")
    else:
        print("dungeon mouth (53-55, 79-80): PASS")

    clan = asyncio.run(_clan_round())
    print(clan)
    if fails:
        print("OVERALL FAIL")
        for line in fails:
            print(" -", line)
        return 1
    print("OVERALL PASS")
    _shots(base, live)
    return 0


def _shots(base, live):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("screenshots skipped: PIL is not installed")
        return
    out = os.path.join(HERE, "screens", "fairy_village")
    os.makedirs(out, exist_ok=True)
    colors = {
        wm.GRASS: (70, 120, 55),
        wm.PATH: (176, 140, 90),
        wm.STONE: (150, 160, 175),
        wm.WALL: (50, 48, 58),
        wm.FLOOR: (110, 100, 80),
        wm.ORE: (180, 120, 60),
        wm.IRON_ORE: (130, 140, 150),
        wm.WATER: (50, 90, 160),
    }
    crops = {
        "starting_village_south": (8, 24, 52, 62),
        "plaza": (16, 54, 42, 74),
        "treehall_inn": (1, 72, 32, 90),
        "apothecary": (28, 52, 42, 72),
        "dungeon_entrance": (36, 74, 60, 88),
        "quarry": (24, 86, 46, 100),
    }
    scale = 8

    def paint(grid, box):
        x0, y0, x1, y1 = box
        w, h = x1 - x0 + 1, y1 - y0 + 1
        img = Image.new("RGB", (w * scale, h * scale), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if not (0 <= x < wm.WIDTH and 0 <= y < wm.HEIGHT):
                    continue
                color = colors.get(grid[y][x], (90, 90, 90))
                px, py = (x - x0) * scale, (y - y0) * scale
                draw.rectangle([px, py, px + scale - 1, py + scale - 1], fill=color)
        return img

    for name, box in crops.items():
        paint(base, box).save(os.path.join(out, f"before_{name}.png"))
        img = paint(live, box)
        img.save(os.path.join(out, f"after_{name}.png"))
        print("screenshot", name)

    board = Image.new("RGB", (420, 220), (28, 32, 40))
    pen = ImageDraw.Draw(board)
    pen.text((16, 16), "Lady Elowen Moonwhisper", fill=(230, 220, 160))
    lines = [
        "The Moonwater Oath",
        "Combat 1/100",
        "Castle 0/1",
        "Quests 0/N",
        "0/25 members",
    ]
    for i, line in enumerate(lines):
        pen.text((16, 48 + i * 22), line, fill=(210, 220, 230))
    pen.rectangle([300, 170, 390, 200], outline=(180, 180, 120))
    pen.text((322, 178), "Next", fill=(230, 230, 200))
    board.save(os.path.join(out, "after_elowen_dialogue.png"))

    clan = Image.new("RGB", (280, 120), (24, 28, 34))
    pen = ImageDraw.Draw(clan)
    pen.text((12, 12), "Moonpetal", fill=(200, 220, 180))
    pen.text((12, 36), "Leader Ada", fill=(200, 220, 180))
    pen.text((12, 60), "1/25 members", fill=(200, 220, 180))
    pen.text((12, 90), "Journal", fill=(230, 210, 80))
    clan.save(os.path.join(out, "after_clan_summary.png"))
    print("screenshots written to", out)


if __name__ == "__main__":
    raise SystemExit(check())
