"""Manifest spawns for the Emberdeep v2 floor.

Coordinates match the floor file: x from the left, y from the top, y south.
Off unless USE_EMBERDEEP_CREATURES is set. Does not read the first-person flag.
"""
from __future__ import annotations

import json
import os

import feature_flags
from world_map import FLOOR

_MANIFEST = None


def _path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "emberdeep_creatures_pack", "manifest.json")


def _floor_chars():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "..", "emberdeep_v2_pack", "interior", "emberdeep_v2_floor.txt")
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line:
                rows.append(line)
    return rows


def manifest():
    global _MANIFEST
    if _MANIFEST is None:
        with open(_path(), encoding="utf-8") as handle:
            _MANIFEST = json.load(handle)
    return _MANIFEST


def _spot(spot):
    if isinstance(spot, dict):
        return int(spot["x"]), int(spot["y"])
    return int(spot[0]), int(spot[1])


def footprint(ax, ay):
    """Wyrm body: anchor ±2 in x and ±1 in y."""
    cells = []
    for dx in range(-2, 3):
        for dy in range(-1, 2):
            cells.append((int(ax) + dx, int(ay) + dy))
    return cells


def cone_tiles_for(ax, ay, facing, tiles=None):
    """Breath tiles in front of a post. Clipped to lair floor."""
    ax, ay = int(ax), int(ay)
    spots = []
    if facing == "south":
        for y in (ay + 2, ay + 3):
            for x in range(ax - 2, ax + 3):
                spots.append((x, y))
    elif facing == "east":
        for x in (ax + 3, ax + 4):
            for y in range(ay - 2, ay + 3):
                spots.append((x, y))
    else:
        for x in (ax - 3, ax - 4):
            for y in range(ay - 2, ay + 3):
                spots.append((x, y))
    lair = (manifest().get("boss") or {}).get("lair") or {}
    out = []
    for x, y in spots:
        if lair and not (lair["x0"] <= x <= lair["x1"] and lair["y0"] <= y <= lair["y1"]):
            continue
        if tiles is not None:
            if y < 0 or x < 0 or y >= len(tiles) or x >= len(tiles[0]) or tiles[y][x] != FLOOR:
                continue
        out.append([x, y])
    return out


def swing_tiles(cone_tiles, footprint_cells=None):
    """Tiles a melee swing can use.

    With a footprint, that is the cone plus every floor tile touching the body.
    Without one, it is the cone plus one step to either side.
    """
    spots = {_spot(spot) for spot in (cone_tiles or [])}
    if not spots and not footprint_cells:
        return spots
    if footprint_cells:
        for ax, ay in footprint_cells:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    spots.add((int(ax) + dx, int(ay) + dy))
        return spots
    xs = [p[0] for p in spots]
    lo, hi = min(xs), max(xs)
    for y in {p[1] for p in spots}:
        spots.add((lo - 1, y))
        spots.add((hi + 1, y))
    return spots


def _in_lair(px, py, lair):
    if not lair:
        return False
    return lair["x0"] <= px <= lair["x1"] and lair["y0"] <= py <= lair["y1"] + 1


def wyrm_tick(monster, tiles, players_xy, tick):
    """Step the wyrm between lair posts. Breath telegraph holds it still."""
    if getattr(monster, "_cone_pending", False):
        return
    import random
    boss = manifest().get("boss") or {}
    lair = boss.get("lair") or {}
    posts = [tuple(p) for p in boss.get("posts") or []]
    ax, ay = int(monster.x), int(monster.y)
    facing = (monster.stats or {}).get("facing") or boss.get("facing") or "south"
    players = [(int(px), int(py)) for px, py in players_xy]
    inside = [p for p in players if _in_lair(p[0], p[1], lair)]

    def blocked(post):
        body = set(footprint(post[0], post[1]))
        return any(p in body for p in players)

    moved = False
    turned = False
    if not inside:
        if tick % 3 == 0:
            neighbours = [
                p for p in posts
                if abs(p[0] - ax) + abs(p[1] - ay) == 1 and not blocked(p)
            ]
            if neighbours:
                nx, ny = random.choice(neighbours)
                if nx != ax:
                    facing = "east" if nx > ax else "west"
                ax, ay = nx, ny
                moved = True
    elif tick % 2 == 0:
        px, py = inside[0]
        want = "south" if py > ay + 1 else ("east" if px > ax else "west")
        if want != facing:
            facing = want
            turned = True
            monster._turned_tick = tick
        else:
            best = None
            for post in posts:
                if blocked(post):
                    continue
                face = "south" if py > post[1] + 1 else ("east" if px > post[0] else "west")
                cone = {(c[0], c[1]) for c in cone_tiles_for(post[0], post[1], face, tiles)}
                if (px, py) not in cone:
                    continue
                dist = abs(post[0] - ax) + abs(post[1] - ay)
                if best is None or dist < best[0]:
                    best = (dist, post)
            if best and best[0] > 0:
                tx, ty = best[1]
                options = [
                    p for p in posts
                    if abs(p[0] - ax) + abs(p[1] - ay) == 1
                    and not blocked(p)
                    and abs(p[0] - tx) + abs(p[1] - ty) < abs(ax - tx) + abs(ay - ty)
                ]
                if options:
                    nx, ny = options[0]
                    if nx != ax:
                        facing = "east" if nx > ax else "west"
                    ax, ay = nx, ny
                    moved = True
    if moved or turned:
        monster.stats["cone_tiles"] = cone_tiles_for(ax, ay, facing, tiles)
        monster.stats["facing"] = facing
        monster.x, monster.y = ax, ay


def _tile_ok(tiles, chars, x, y, forbid_bridge=False):
    if y < 0 or x < 0 or y >= len(tiles) or x >= len(tiles[0]):
        return False
    if tiles[y][x] != FLOOR:
        return False
    ch = chars[y][x] if y < len(chars) and x < len(chars[y]) else "#"
    if ch in ("#", "L", "S", "E", "K", "H", "N"):
        return False
    if forbid_bridge and ch == "B" and x in (21, 22, 23):
        return False
    return True


def reserved_tiles(tiles):
    """Tiles the random Emberdeep roll must leave empty."""
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return set()
    chars = _floor_chars()
    taken = set()
    data = manifest()
    for creature in data.get("creatures") or []:
        bridge = creature.get("id") in ("bile_toad", "cinder_bitch")
        for spot in creature.get("spawns") or []:
            x, y = int(spot["x"]), int(spot["y"])
            if _tile_ok(tiles, chars, x, y, forbid_bridge=bridge):
                taken.add((x, y))
    for prop in data.get("props") or []:
        spot = prop.get("tile") or {}
        x, y = int(spot.get("x", -1)), int(spot.get("y", -1))
        if _tile_ok(tiles, chars, x, y):
            taken.add((x, y))
    boss = data.get("boss") or {}
    for spot in boss.get("footprint") or []:
        taken.add((int(spot["x"]), int(spot["y"])))
    anchor = boss.get("anchor") or {}
    if "x" in anchor:
        taken.add((int(anchor["x"]), int(anchor["y"])))
    return taken


def build(tiles, next_id, monster_cls, stats_for):
    """Return (props, monsters) for one Emberdeep floor. Empty when the flag is off."""
    if not feature_flags.USE_EMBERDEEP_CREATURES:
        return [], []
    chars = _floor_chars()
    data = manifest()
    used = set()
    props = []
    monsters = []
    for creature in data.get("creatures") or []:
        cid = creature["id"]
        bridge = cid in ("bile_toad", "cinder_bitch")
        stats = stats_for(int(creature["level"]))
        stats["name"] = creature["display_name"]
        stats["attack_cooldown"] = 1.2
        for spot in creature.get("spawns") or []:
            x, y = int(spot["x"]), int(spot["y"])
            if (x, y) in used or not _tile_ok(tiles, chars, x, y, forbid_bridge=bridge):
                continue
            used.add((x, y))
            mid = next_id()
            monsters.append(monster_cls(mid, cid, x, y, stats=dict(stats)))
    for prop in data.get("props") or []:
        spot = prop.get("tile") or {}
        x, y = int(spot.get("x", -1)), int(spot.get("y", -1))
        if (x, y) in used or not _tile_ok(tiles, chars, x, y):
            continue
        used.add((x, y))
        props.append({
            "key": prop["id"],
            "x": x,
            "y": y,
            "pack": "emberdeep_creatures",
        })
    boss = data.get("boss") or {}
    anchor = boss.get("anchor") or {}
    if "x" in anchor:
        x, y = int(anchor["x"]), int(anchor["y"])
        if (x, y) not in used and 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
            stats = stats_for(int(boss.get("level") or 250))
            stats["hp"] = int(boss.get("hp") or 2500)
            stats["name"] = boss["display_name"]
            stats["static"] = True
            stats["speed"] = 0
            stats["wander_radius"] = 0
            stats["attack_cooldown"] = 2.4
            stats["facing"] = boss.get("facing") or "south"
            stats["cone_tiles"] = cone_tiles_for(x, y, stats["facing"], tiles)
            mid = next_id()
            monsters.append(monster_cls(mid, boss["id"], x, y, stats=dict(stats)))
    return props, monsters
