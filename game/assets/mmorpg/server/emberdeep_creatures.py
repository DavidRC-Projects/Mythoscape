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


def swing_tiles(cone_tiles):
    """Where a melee swing at the wyrm lands.

    The breath tiles, plus one step to either side so you can hit it
    without standing in the fire or on its body.
    """
    spots = {_spot(spot) for spot in (cone_tiles or [])}
    if not spots:
        return spots
    xs = [p[0] for p in spots]
    lo, hi = min(xs), max(xs)
    for y in {p[1] for p in spots}:
        spots.add((lo - 1, y))
        spots.add((hi + 1, y))
    return spots


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
            stats["cone_tiles"] = [
                [int(spot["x"]), int(spot["y"])] for spot in (boss.get("cone_tiles") or [])
            ]
            mid = next_id()
            monsters.append(monster_cls(mid, boss["id"], x, y, stats=dict(stats)))
    return props, monsters
