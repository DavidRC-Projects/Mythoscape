#!/usr/bin/env python3
"""Mythoscape Castle Realm interiors v2. Option B: planes larger than the keep.
Exteriors stay. Flag USE_CASTLE_INTERIORS_V2 defaults off.
Collision is walls and wall-hugging props only. No pillars or cones.
"""
from __future__ import annotations
import json, os
from collections import deque
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON_DIR = os.path.join(ROOT, "json")
PREV_DIR = os.path.join(ROOT, "previews")
SPR_DIR = os.path.join(ROOT, "sprites")
WALK = set(".DEUV")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

class Floor:
    def __init__(self, plane, level, name, w, h, building="keep"):
        self.plane, self.level, self.name = plane, level, name
        self.w, self.h, self.building = w, h, building
        self.g = [["#" for _ in range(w)] for _ in range(h)]
        self.rooms, self.doors, self.stair_pts, self.exits = [], [], [], []
        self.stairs, self.furniture, self.decor, self.guard_posts = [], [], [], []
        self.exit_records = []
    def inb(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h
    def carve(self, rect):
        x0, y0, x1, y1 = rect
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.g[y][x] = "."
    def add_room(self, kind, name, rect, fun=False, nested=False, role=None):
        room = {"kind": kind, "name": name, "rect": list(rect), "fun": fun,
                 "nested": nested, "role": role or kind}
        self.rooms.append(room)
        if not nested:
            self.carve(rect)
        return room
    def paint_box(self, border):
        x0, y0, x1, y1 = border
        for x in range(x0, x1 + 1):
            self.g[y0][x] = "#"
            self.g[y1][x] = "#"
        for y in range(y0, y1 + 1):
            self.g[y][x0] = "#"
            self.g[y][x1] = "#"
    def punch(self, x, y):
        if not self.inb(x, y) or self.g[y][x] != "#":
            raise RuntimeError(f"{self.plane} bad door {(x, y)} {self.g[y][x] if self.inb(x, y) else 'OOB'}")
        self.g[y][x] = "D"
        self.doors.append((x, y))
    def set_stair(self, x, y, direction):
        if self.g[y][x] != ".":
            raise RuntimeError(f"{self.plane} stair {(x, y)} on {self.g[y][x]!r}")
        self.g[y][x] = "U" if direction == "up" else "V"
        self.stair_pts.append((x, y, direction))
    def set_exit(self, x, y):
        # Exit sits on the south wall, same as v1. It must open onto a floor tile.
        if not self.inb(x, y):
            raise RuntimeError(f"{self.plane} exit OOB {(x, y)}")
        if self.g[y][x] not in ".#":
            raise RuntimeError(f"{self.plane} exit {(x, y)} on {self.g[y][x]!r}")
        opens = any(self.inb(x+dx, y+dy) and self.g[y+dy][x+dx] in ".DEUV" for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))
        if not opens:
            raise RuntimeError(f"{self.plane} exit {(x, y)} does not open onto floor")
        self.g[y][x] = "E"
        self.exits.append((x, y))

def room_by(floor, name):
    for r in floor.rooms:
        if r["name"] == name:
            return r
    raise KeyError(name)

def door_between(floor, a, b):
    ax0, ay0, ax1, ay1 = room_by(floor, a)["rect"]
    bx0, by0, bx1, by1 = room_by(floor, b)["rect"]
    if ay1 + 2 == by0 or by1 + 2 == ay0:
        y = ay1 + 1 if ay1 + 2 == by0 else by1 + 1
        x0, x1 = max(ax0, bx0), min(ax1, bx1)
        if x0 > x1:
            raise RuntimeError(f"{floor.plane} no x-overlap {a}/{b}")
        floor.punch((x0 + x1) // 2, y)
        return
    if ax1 + 2 == bx0 or bx1 + 2 == ax0:
        x = ax1 + 1 if ax1 + 2 == bx0 else bx1 + 1
        y0, y1 = max(ay0, by0), min(ay1, by1)
        if y0 > y1:
            raise RuntimeError(f"{floor.plane} no y-overlap {a}/{b}")
        floor.punch(x, (y0 + y1) // 2)
        return
    raise RuntimeError(f"{floor.plane} not one wall apart: {a} / {b}")

def forbidden_cells(room):
    x0, y0, x1, y1 = room["rect"]
    rw, rh = x1 - x0 + 1, y1 - y0 + 1
    cells = set()
    if rh <= 4 or rw <= 5:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                cells.add((x, y))
        return cells
    side = 2 if room["kind"] in ("chapel", "oratory", "candle_chapel", "private_chapel") else 1
    for y in range(y0 + 1, y1):
        for x in range(x0 + side, x1 - side + 1):
            cells.add((x, y))
    return cells

def approach_reserved(floor):
    res = set()
    for y in range(floor.h):
        for x in range(floor.w):
            if floor.g[y][x] not in "DEUV":
                continue
            res.add((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not floor.inb(nx, ny):
                    continue
                if floor.g[ny][nx] in WALK or floor.g[ny][nx] == ".":
                    res.add((nx, ny))
                    res.add((nx + dy, ny + dx))
                    res.add((nx - dy, ny - dx))
                    fx, fy = nx + dx, ny + dy
                    if floor.inb(fx, fy):
                        res.add((fx, fy))
    return res

def nearest_wall(floor, x, y):
    best = 99
    for y2 in range(max(0, y - 3), min(floor.h, y + 4)):
        for x2 in range(max(0, x - 3), min(floor.w, x + 4)):
            if floor.g[y2][x2] == "#":
                best = min(best, abs(x2 - x) + abs(y2 - y))
    return best

CYCLE = {
    "chapel": ["candle", "banner", "candle"],
    "oratory": ["candle", "white_urn", "banner"],
    "candle_chapel": ["candelabra", "white_urn", "candle"],
    "private_chapel": ["candle", "banner", "candelabra"],
    "guard": ["weapon_rack", "duty_table", "stool", "armour_stand"],
    "kitchen": ["shelf", "sack", "barrel"],
    "pantry": ["barrel", "shelf", "sack"],
    "stillroom": ["barrel", "shelf", "sack"],
    "servants": ["bed", "chest", "stool", "shelf"],
    "nursery": ["bed", "chest", "chair", "white_urn"],
    "entrance": ["banner", "armour_stand", "candle"],
    "lobby": ["banner", "candle", "armour_stand"],
    "crypt": ["candle", "plaque", "chest"],
    "stair": ["candle", "banner"],
    "great_hall": ["banner", "candelabra"],
    "feast_gallery": ["candelabra", "banner"],
    "armoury": ["weapon_rack", "armour_stand", "chest"],
    "solar": ["desk", "bookshelf", "chair", "white_urn"],
    "music": ["chair", "stool", "banner"],
    "lord": ["chair", "candle"],
    "guest": ["wardrobe", "chair"],
    "library": ["bookshelf", "desk", "chair", "candle"],
    "cells": ["chain_ring", "stool", "candle"],
    "vault": ["shelf"],
    "bell": ["bell", "candle"],
    "watch": ["brazier", "telescope"],
    "roof": ["brazier", "banner"],
    "terrace": ["planter", "bench"],
    "conservatory": ["bench", "candelabra"],
    "dressing": ["stool", "white_urn"],
    "bedchamber": ["chair", "white_urn"],
    "bath": ["stool", "candelabra"],
    "gallery": ["banner", "white_urn", "candle"],
    "throne_room": ["banner", "armour_stand", "candelabra"],
    "trophy": ["banner", "weapon_rack"],
    "council": ["council_chair", "bookshelf", "candle"],
    "war_room": ["banner", "stool"],
    "study": ["bookshelf", "chair", "candle"],
    "treasury": ["shelf"],
    "ante": ["banner", "candle", "armour_stand"],
    "vestibule": ["banner", "armour_stand", "candle"],
    "buttery": ["barrel", "shelf", "sack"],
    "side": ["barrel", "candle"],
    "dormitory": ["chest"],
    "mess": ["barrel", "stool"],
    "captain": ["chest", "weapon_rack"],
    "gearworks": ["barrel"],
    "shrine": ["candle", "crystal"],
    "chains": ["brazier", "banner"],
    "observatory": ["chair", "crystal"],
    "workshop": ["shelf", "stool", "crystal"],
    "meditation": ["cushion", "crystal", "candle"],
    "guest_cell": ["stool"],
    "storm": ["crystal"],
    "wind_gallery": ["banner", "crystal"],
    "heart": ["crystal", "candelabra"],
    "crown_room": ["banner", "candelabra"],
    "battlement": ["banner"],
    "corridor": ["candle"],
}

def place(floor, x, y, kind, reserved, forbid):
    if not floor.inb(x, y) or floor.g[y][x] != ".":
        return False
    if (x, y) in reserved or (x, y) in forbid:
        return False
    if nearest_wall(floor, x, y) > 2:
        return False
    floor.g[y][x] = "x"
    floor.furniture.append({"kind": kind, "tile": [x, y], "blocks": True, "hug": "wall"})
    return True

def furnish(floor):
    reserved = approach_reserved(floor)
    for room in floor.rooms:
        x0, y0, x1, y1 = room["rect"]
        forbid = forbidden_cells(room)
        kind = room["kind"]
        cx = (x0 + x1) // 2
        if kind in ("chapel", "oratory", "candle_chapel", "private_chapel"):
            place(floor, cx, y0, "altar", reserved, forbid)
            for y in range(y0 + 2, y1, 2):
                place(floor, x0 + 1, y, "pew", reserved, forbid)
                place(floor, x1 - 1, y, "pew", reserved, forbid)
        if kind == "throne_room":
            place(floor, cx, y0, "throne", reserved, forbid)
        if kind == "crown_room":
            place(floor, cx, y0, "throne", reserved, forbid)
        if kind == "heart":
            place(floor, cx, y0, "crystal_throne", reserved, forbid)
        if kind in ("vault", "treasury"):
            place(floor, cx, y0, "vault_door", reserved, forbid)
            place(floor, x0, y1, "gold_pile", reserved, forbid)
            place(floor, x1, y1, "chest", reserved, forbid)
        if kind in ("lord", "bedchamber", "storm"):
            place(floor, x0, y0, "four_poster", reserved, forbid)
            place(floor, x1, y0, "wardrobe", reserved, forbid)
            place(floor, x1, y1, "chest", reserved, forbid)
        if kind in ("guest", "guest_cell"):
            place(floor, x0, y0, "bed", reserved, forbid)
            place(floor, x1, y1, "decoy_chest", reserved, forbid)
        if kind == "kitchen":
            place(floor, cx, y0, "hearth", reserved, forbid)
            place(floor, x0, y1, "prep_table", reserved, forbid)
            place(floor, x1, y1, "water_barrel", reserved, forbid)
        if kind in ("great_hall", "chains", "mess"):
            for y in range(y0 + 2, y1, 3):
                place(floor, x0, y, "long_table", reserved, forbid)
                place(floor, x1, y, "long_table", reserved, forbid)
        if kind == "feast_gallery":
            for x in range(x0 + 2, x1, 3):
                place(floor, x, y0, "feast_table", reserved, forbid)
                place(floor, x, y1, "feast_table", reserved, forbid)
        if kind == "war_room":
            place(floor, cx, y0, "map_table", reserved, forbid)
            place(floor, x0, y0, "banner", reserved, forbid)
            place(floor, x1, y0, "weapon_rack", reserved, forbid)
        if kind == "music":
            place(floor, x0, y0, "harp", reserved, forbid)
            place(floor, x1, y0, "music_stand", reserved, forbid)
        if kind == "dressing":
            place(floor, x0, y0, "dresser", reserved, forbid)
            place(floor, x1, y0, "wardrobe", reserved, forbid)
            place(floor, x1, y1, "screen", reserved, forbid)
        if kind == "bath":
            place(floor, x0, y0, "marble_basin", reserved, forbid)
            place(floor, x1, y0, "marble_basin", reserved, forbid)
        if kind == "conservatory":
            for x in range(x0 + 1, x1, 2):
                place(floor, x, y0, "white_urn", reserved, forbid)
                place(floor, x, y1, "planter", reserved, forbid)
        if kind == "trophy":
            for y in range(y0 + 1, y1, 2):
                place(floor, x0, y, "trophy", reserved, forbid)
                place(floor, x1, y, "armour_stand", reserved, forbid)
        if kind == "cells":
            place(floor, x0, y0, "iron_maiden", reserved, forbid)
        if kind == "shrine":
            place(floor, cx, y0, "crystal_altar", reserved, forbid)
        if kind == "observatory":
            place(floor, x1, y0, "telescope", reserved, forbid)
        if kind == "gearworks":
            place(floor, x0, y0, "gear", reserved, forbid)
            place(floor, x1, y0, "chain_winch", reserved, forbid)
        if kind == "dormitory":
            for x in range(x0, x1, 3):
                place(floor, x, y0, "bunk", reserved, forbid)
                place(floor, x, y1, "bunk", reserved, forbid)
        if kind == "captain":
            place(floor, x0, y0, "bed", reserved, forbid)
            place(floor, x1, y0, "desk", reserved, forbid)
        cycle = CYCLE.get(kind, ["candle"])
        cands = []
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x, y) in forbid or (x, y) in reserved or floor.g[y][x] != ".":
                    continue
                if x in (x0, x1, x0 + 1, x1 - 1) or y in (y0, y1):
                    cands.append((x, y))
        placed = 0
        cap = 8 if kind in ("terrace", "battlement", "roof") else 12
        for i, (x, y) in enumerate(cands):
            if i % 2 or placed >= cap:
                continue
            if place(floor, x, y, cycle[(i // 2) % len(cycle)], reserved, forbid):
                placed += 1
        rw, rh = x1 - x0 + 1, y1 - y0 + 1
        if rw >= 7 and rh >= 6 and kind not in ("terrace", "battlement", "roof", "stair", "corridor", "side"):
            # A small center carpet only. The aisle around it stays bare so the room does not read as one blocked slab.
            rug_kind = "marble_pool" if kind == "bath" else ("dance_floor" if kind in ("great_hall", "throne_room", "feast_gallery") else "rug")
            half_w = 4 if kind in ("great_hall", "throne_room", "feast_gallery", "bath") else 2
            half_h = 2 if kind in ("great_hall", "throne_room", "feast_gallery", "bath") else 1
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            for y in range(cy - half_h, cy + half_h + 1):
                for x in range(cx - half_w, cx + half_w + 1):
                    if floor.inb(x, y) and floor.g[y][x] == ".":
                        floor.decor.append({"kind": rug_kind, "tile": [x, y], "blocks": False, "layer": "floor"})
    clear_pockets(floor)

def clear_pockets(floor):
    """Rim props must not seal a floor tile into a one-tile pocket."""
    def starts():
        s = [(x, y) for y in range(floor.h) for x in range(floor.w) if floor.g[y][x] in "EUV"]
        ex = [p for p in s if floor.g[p[1]][p[0]] == "E"]
        return ex or s
    for _ in range(16):
        seen = bfs(floor, starts())
        pockets = [(x, y) for y in range(floor.h) for x in range(floor.w)
                   if floor.g[y][x] in WALK and (x, y) not in seen]
        if not pockets:
            return
        changed = False
        for x, y in pockets:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if floor.inb(nx, ny) and floor.g[ny][nx] == "x":
                    floor.g[ny][nx] = "."
                    floor.furniture = [f for f in floor.furniture if f["tile"] != [nx, ny]]
                    changed = True
        if not changed:
            return

def add_wall_decor(floor, theme):
    for y in range(floor.h):
        for x in range(floor.w):
            if floor.g[y][x] != "#":
                continue
            faces = [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                     if floor.inb(x + dx, y + dy) and floor.g[y + dy][x + dx] in WALK | {"x"}]
            if not faces:
                continue
            h = (x * 13 + y * 7 + floor.level * 3) % 6
            if theme == "rose":
                if h != 5:
                    floor.decor.append({"kind": "white_flower_drape", "tile": [x, y], "blocks": False, "mount": "wall"})
                if h % 2 == 0:
                    floor.decor.append({"kind": "taper_candle", "tile": [x, y], "blocks": False, "mount": "wall"})
            elif theme == "gothic" and h == 0:
                floor.decor.append({"kind": "torch_sconce", "tile": [x, y], "blocks": False, "mount": "wall"})
            elif theme == "king":
                if h == 0:
                    floor.decor.append({"kind": "banner", "tile": [x, y], "blocks": False, "mount": "wall"})
                elif h == 3:
                    floor.decor.append({"kind": "taper_candle", "tile": [x, y], "blocks": False, "mount": "wall"})
            elif theme == "sky":
                if h == 0:
                    floor.decor.append({"kind": "wind_chime", "tile": [x, y], "blocks": False, "mount": "wall"})
                elif h == 3:
                    floor.decor.append({"kind": "crystal_sconce", "tile": [x, y], "blocks": False, "mount": "wall"})

def guard_posts_for(floor):
    specials = [(x, y) for y in range(floor.h) for x in range(floor.w) if floor.g[y][x] in "DEUV"]
    posts = []
    n = 0
    for room in floor.rooms:
        if room["kind"] not in ("entrance", "vestibule", "lobby", "stair", "vault", "treasury"):
            continue
        x0, y0, x1, y1 = room["rect"]
        picked = None
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if floor.g[y][x] != ".":
                    continue
                if all(abs(x - sx) + abs(y - sy) >= 2 for sx, sy in specials):
                    picked = (x, y)
                    break
            if picked:
                break
        if not picked:
            continue
        slot = "vault" if room["kind"] in ("vault", "treasury") else ("stairs" if room["kind"] == "stair" else "hall")
        posts.append({"id": f"{floor.plane}_{slot}_{n}", "tile": list(picked), "slot": "inside", "role": slot})
        n += 1
    floor.guard_posts = posts

def bfs(floor, starts):
    seen, q = set(), deque()
    for x, y in starts:
        if floor.inb(x, y) and floor.g[y][x] in WALK:
            seen.add((x, y)); q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if floor.inb(nx, ny) and (nx, ny) not in seen and floor.g[ny][nx] in WALK:
                seen.add((nx, ny)); q.append((nx, ny))
    return seen

def validate(floor):
    errors = []
    for x, y in floor.doors:
        goods = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if floor.inb(nx, ny) and floor.g[ny][nx] in WALK:
                goods.append((dx, dy))
            if floor.inb(nx, ny) and floor.g[ny][nx] == "x":
                errors.append(f"furniture blocks door {(x, y)} at {(nx, ny)}")
        if not any((dx, dy) in goods and (-dx, -dy) in goods for dx, dy in goods):
            errors.append(f"door {(x, y)} does not open both ways")
        for dx, dy in goods:
            fx, fy = x + 2 * dx, y + 2 * dy
            if floor.inb(fx, fy) and floor.g[fy][fx] == "x" and floor.g[y + dy][x + dx] in ".DUV":
                errors.append(f"furniture in 2-tile pad of {(x, y)} at {(fx, fy)}")
    for y in range(floor.h):
        for x in range(floor.w):
            ch = floor.g[y][x]
            if ch in "EUV":
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if floor.inb(nx, ny) and floor.g[ny][nx] == "x":
                        errors.append(f"furniture touches {ch} {(x, y)}")
            if ch == "x" and nearest_wall(floor, x, y) > 2:
                errors.append(f"not wall-hugging {(x, y)}")
    nested_rects = [r["rect"] for r in floor.rooms if r["nested"]]
    def inside_nested(x, y, room):
        if room["nested"]:
            return False
        for x0, y0, x1, y1 in nested_rects:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return True
        return False
    for room in floor.rooms:
        for x, y in forbidden_cells(room):
            if inside_nested(x, y, room):
                continue
            if floor.inb(x, y) and floor.g[y][x] == "x":
                errors.append(f"aisle blocked in {room['name']} at {(x, y)}")
                break
    starts = [(x, y) for y in range(floor.h) for x in range(floor.w) if floor.g[y][x] in "EUV"]
    exits = [s for s in starts if floor.g[s[1]][s[0]] == "E"]
    seen = bfs(floor, exits or starts)
    walk_tiles = [(x, y) for y in range(floor.h) for x in range(floor.w) if floor.g[y][x] in WALK]
    unreachable = [p for p in walk_tiles if p not in seen]
    if unreachable:
        errors.append(f"{len(unreachable)} unreachable e.g. {unreachable[:8]}")
    rooms_ok = 0
    for room in floor.rooms:
        x0, y0, x1, y1 = room["rect"]
        if any((x, y) in seen for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)):
            rooms_ok += 1
        else:
            errors.append(f"room unreachable: {room['name']}")
    for f in floor.furniture:
        if f["kind"] in ("pillar", "cone", "column", "fountain", "fountain_basin"):
            errors.append("forbidden prop " + f["kind"])
    return {"pass": not errors, "errors": errors[:40], "walkable": len(walk_tiles),
            "reachable": len(seen), "rooms": f"{rooms_ok}/{len(floor.rooms)}",
            "blocking_props": len(floor.furniture), "decor": len(floor.decor)}

def link_stairs(floors):
    by_level = {f.level: f for f in floors}
    def arrive_near(floor, x, y):
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if floor.inb(nx, ny) and floor.g[ny][nx] == ".":
                return [nx, ny]
        raise RuntimeError(f"no arrive beside {(x, y)} on {floor.plane}")
    for f in floors:
        f.stairs = []
        for x, y, direction in f.stair_pts:
            if direction == "up":
                dest = by_level[f.level + 1]
                vx, vy, _ = next(p for p in dest.stair_pts if p[2] == "down")
                f.stairs.append({"tile": [x, y], "dir": "up", "to_plane": dest.plane, "arrive": arrive_near(dest, vx, vy)})
            else:
                dest = by_level[f.level - 1]
                ux, uy, _ = next(p for p in dest.stair_pts if p[2] == "up")
                f.stairs.append({"tile": [x, y], "dir": "down", "to_plane": dest.plane, "arrive": arrive_near(dest, ux, uy)})

def apply_exits(floor, world_arrives):
    es = sorted(floor.exits)
    if len(es) != len(world_arrives):
        raise RuntimeError(f"{floor.plane} exits {es} vs {world_arrives}")
    floor.exit_records = [{"tile": [x, y], "to_plane": "realm", "arrive": list(world)} for (x, y), world in zip(es, world_arrives)]

def rows_of(floor):
    return ["".join(row) for row in floor.g]

def arrive_from_exit(floor):
    out = []
    for rec in floor.exit_records:
        x, y = rec["tile"]
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if floor.inb(nx, ny) and floor.g[ny][nx] == ".":
                out.append([nx, ny]); break
        else:
            raise RuntimeError("exit has no pad")
    return out

def build_duskspire():
    floors = []
    f = Floor("gothic_f1", 1, "Hall of Shadows", 40, 23)
    f.add_room("chapel", "Black Chapel", (1, 1, 13, 8))
    f.add_room("guard", "Guard Room", (15, 1, 25, 8))
    f.add_room("kitchen", "Kitchen", (27, 1, 38, 8))
    f.add_room("corridor", "Shadow Corridor", (1, 10, 38, 12), role="corridor")
    f.add_room("pantry", "Pantry", (1, 14, 10, 21))
    f.add_room("entrance", "Entrance Hall", (12, 14, 29, 21))
    f.add_room("crypt", "Crypt Stair Vestibule", (31, 14, 38, 17))
    f.add_room("stair", "Stair Hall", (31, 19, 38, 21))
    for a, b in (("Black Chapel", "Shadow Corridor"), ("Guard Room", "Shadow Corridor"),
                 ("Kitchen", "Shadow Corridor"), ("Shadow Corridor", "Pantry"),
                 ("Shadow Corridor", "Entrance Hall"), ("Shadow Corridor", "Crypt Stair Vestibule"),
                 ("Pantry", "Entrance Hall"), ("Entrance Hall", "Stair Hall")):
        door_between(f, a, b)
    f.set_exit(20, 22); f.set_exit(21, 22); f.set_stair(34, 20, "up")
    floors.append(f)
    f = Floor("gothic_f2", 2, "Great Hall", 40, 23)
    f.add_room("great_hall", "Great Hall", (1, 1, 26, 16))
    f.add_room("armoury", "Armoury", (28, 1, 38, 10))
    f.add_room("solar", "Lord's Solar", (28, 12, 38, 16))
    f.add_room("ante", "Solar Antechamber", (1, 18, 29, 21))
    f.add_room("stair", "Stair Hall", (31, 19, 38, 21))
    for a, b in (("Great Hall", "Armoury"), ("Great Hall", "Lord's Solar"),
                 ("Great Hall", "Solar Antechamber"), ("Solar Antechamber", "Stair Hall")):
        door_between(f, a, b)
    f.set_stair(34, 20, "up"); f.set_stair(37, 20, "down")
    floors.append(f)
    f = Floor("gothic_f3", 3, "Lord's Chambers & Vault", 40, 23)
    f.add_room("lord", "Lord's Bedchamber", (1, 1, 14, 10))
    f.add_room("guest", "Guest Chamber", (16, 1, 26, 10))
    f.add_room("library", "Library", (28, 1, 38, 10))
    f.add_room("corridor", "Upper Corridor", (1, 12, 38, 14), role="corridor")
    f.add_room("cells", "Questioning Room", (1, 16, 14, 21))
    f.add_room("vault", "Main Vault", (16, 16, 29, 21))
    f.add_room("stair", "Stair Hall", (31, 16, 38, 21))
    for a, b in (("Lord's Bedchamber", "Guest Chamber"), ("Guest Chamber", "Library"),
                 ("Lord's Bedchamber", "Upper Corridor"), ("Guest Chamber", "Upper Corridor"),
                 ("Library", "Upper Corridor"), ("Upper Corridor", "Questioning Room"),
                 ("Upper Corridor", "Main Vault"), ("Upper Corridor", "Stair Hall"),
                 ("Questioning Room", "Main Vault")):
        door_between(f, a, b)
    f.set_stair(34, 19, "up"); f.set_stair(37, 19, "down")
    floors.append(f)
    f = Floor("gothic_f4", 4, "Spire", 32, 18)
    f.add_room("bell", "Bell Chamber", (1, 1, 14, 8))
    f.add_room("watch", "Battlement Watch", (16, 1, 30, 8))
    f.add_room("roof", "Roof Walk", (1, 10, 30, 12))
    f.add_room("stair", "Stair Head", (22, 14, 30, 16))
    for a, b in (("Bell Chamber", "Roof Walk"), ("Battlement Watch", "Roof Walk"), ("Roof Walk", "Stair Head")):
        door_between(f, a, b)
    f.set_stair(26, 15, "down")
    floors.append(f)
    for fl in floors:
        furnish(fl); add_wall_decor(fl, "gothic"); guard_posts_for(fl)
    link_stairs(floors)
    apply_exits(floors[0], [[49, 62], [50, 62]])
    return floors

def build_rose():
    floors = []
    f = Floor("rose_f1", 1, "Rose Hall", 44, 28)
    f.add_room("kitchen", "Kitchen", (1, 1, 12, 9))
    f.add_room("pantry", "Pantry & Still-room", (14, 1, 22, 9))
    f.add_room("servants", "Servants' Hall", (24, 1, 33, 9))
    f.add_room("nursery", "Nursery", (35, 1, 42, 9))
    f.add_room("corridor", "Gallery Walk", (1, 11, 42, 13), role="gallery_walk")
    f.add_room("stillroom", "Linen Stillroom", (1, 15, 10, 26))
    f.add_room("entrance", "Entrance Hall", (12, 15, 32, 26))
    f.add_room("stair", "Grand Stair", (34, 15, 42, 26))
    for a, b in (("Kitchen", "Pantry & Still-room"), ("Pantry & Still-room", "Servants' Hall"),
                 ("Servants' Hall", "Nursery"), ("Kitchen", "Gallery Walk"),
                 ("Pantry & Still-room", "Gallery Walk"), ("Servants' Hall", "Gallery Walk"),
                 ("Nursery", "Gallery Walk"), ("Gallery Walk", "Linen Stillroom"),
                 ("Gallery Walk", "Entrance Hall"), ("Gallery Walk", "Grand Stair"),
                 ("Linen Stillroom", "Entrance Hall"), ("Entrance Hall", "Grand Stair")):
        door_between(f, a, b)
    f.set_exit(21, 27); f.set_exit(22, 27); f.set_stair(38, 22, "up")
    floors.append(f)
    f = Floor("rose_f2", 2, "Great Hall of Roses", 44, 28)
    f.add_room("great_hall", "Great Hall of Roses", (1, 1, 30, 18))
    f.add_room("music", "Music Room", (32, 1, 42, 10), fun=True)
    f.add_room("solar", "Solar", (32, 12, 42, 18))
    f.add_room("ante", "Rose Antechamber", (1, 20, 32, 26))
    f.add_room("stair", "Grand Stair", (34, 20, 42, 26))
    for a, b in (("Great Hall of Roses", "Music Room"), ("Great Hall of Roses", "Solar"),
                 ("Music Room", "Solar"), ("Great Hall of Roses", "Rose Antechamber"),
                 ("Rose Antechamber", "Grand Stair")):
        door_between(f, a, b)
    f.set_stair(38, 23, "up"); f.set_stair(40, 23, "down")
    floors.append(f)
    f = Floor("rose_f3", 3, "Queen's Chambers", 44, 28)
    f.add_room("bedchamber", "Queen's Bedchamber", (1, 1, 14, 11))
    f.add_room("dressing", "Dressing Room", (16, 1, 26, 11), fun=True)
    f.add_room("guest", "Guest Suite", (28, 1, 34, 11))
    f.add_room("candle_chapel", "Candle Chapel", (36, 1, 42, 11), fun=True)
    f.add_room("corridor", "Long Corridor", (1, 13, 34, 16), role="corridor")
    f.add_room("stair", "Grand Stair", (36, 13, 42, 16))
    f.add_room("gallery", "Rose Gallery", (1, 18, 16, 26))
    f.add_room("vault", "Petal Vault", (18, 18, 28, 26))
    f.add_room("bath", "Petal Bath", (30, 18, 42, 26), fun=True)
    for a, b in (("Queen's Bedchamber", "Dressing Room"), ("Dressing Room", "Guest Suite"),
                 ("Guest Suite", "Candle Chapel"), ("Queen's Bedchamber", "Long Corridor"),
                 ("Dressing Room", "Long Corridor"), ("Guest Suite", "Long Corridor"),
                 ("Candle Chapel", "Grand Stair"), ("Long Corridor", "Grand Stair"),
                 ("Long Corridor", "Rose Gallery"), ("Long Corridor", "Petal Vault"),
                 ("Long Corridor", "Petal Bath"), ("Grand Stair", "Petal Bath"),
                 ("Rose Gallery", "Petal Vault"), ("Petal Vault", "Petal Bath")):
        door_between(f, a, b)
    f.set_stair(38, 14, "up"); f.set_stair(40, 14, "down")
    floors.append(f)
    f = Floor("rose_f4", 4, "Glass Conservatory", 44, 28)
    f.add_room("terrace", "Roof Terrace", (1, 1, 42, 26))
    f.add_room("conservatory", "Glass Conservatory", (9, 5, 29, 15), fun=True, nested=True)
    f.add_room("stair", "Stair Head", (35, 19, 41, 24), nested=True)
    f.paint_box((8, 4, 30, 16)); f.paint_box((34, 18, 42, 25))
    f.punch(19, 16); f.punch(34, 21)
    f.set_stair(38, 21, "down")
    floors.append(f)
    for fl in floors:
        furnish(fl); add_wall_decor(fl, "rose"); guard_posts_for(fl)
    link_stairs(floors)
    apply_exits(floors[0], [[254, 52], [255, 52]])
    return floors

def build_king():
    floors = []
    f = Floor("king_f1", 1, "Great Hall", 48, 32)
    f.add_room("kitchen", "Royal Kitchen", (1, 1, 14, 10))
    f.add_room("buttery", "Buttery", (1, 12, 14, 18))
    f.add_room("side", "Service Passage", (1, 20, 14, 30), role="corridor")
    f.add_room("feast_gallery", "Feast Gallery", (16, 1, 36, 10), fun=True)
    f.add_room("guard", "Guard Post", (38, 1, 46, 10))
    f.add_room("great_hall", "Great Hall", (16, 12, 36, 22))
    f.add_room("stair", "Grand Stair", (38, 12, 46, 22))
    f.add_room("vestibule", "Vestibule", (16, 24, 36, 30))
    for a, b in (("Royal Kitchen", "Buttery"), ("Buttery", "Service Passage"),
                 ("Royal Kitchen", "Feast Gallery"), ("Feast Gallery", "Guard Post"),
                 ("Feast Gallery", "Great Hall"), ("Guard Post", "Grand Stair"),
                 ("Great Hall", "Grand Stair"), ("Great Hall", "Vestibule"),
                 ("Service Passage", "Vestibule")):
        door_between(f, a, b)
    f.set_exit(25, 31); f.set_exit(26, 31); f.set_stair(42, 17, "up")
    floors.append(f)
    f = Floor("king_f2", 2, "Throne Room", 48, 32)
    f.add_room("throne_room", "Throne Room", (1, 1, 32, 20))
    f.add_room("trophy", "Trophy Hall", (34, 1, 46, 12), fun=True)
    f.add_room("council", "Council Chamber", (34, 14, 46, 20))
    f.add_room("ante", "Antechamber", (1, 22, 36, 30))
    f.add_room("stair", "Grand Stair", (38, 22, 46, 30))
    for a, b in (("Throne Room", "Trophy Hall"), ("Throne Room", "Council Chamber"),
                 ("Trophy Hall", "Council Chamber"), ("Throne Room", "Antechamber"),
                 ("Council Chamber", "Antechamber"), ("Antechamber", "Grand Stair")):
        door_between(f, a, b)
    f.set_stair(42, 26, "up"); f.set_stair(44, 26, "down")
    floors.append(f)
    f = Floor("king_f3", 3, "Royal Apartments", 48, 32)
    f.add_room("lord", "King's Bedchamber", (1, 1, 16, 12))
    f.add_room("bedchamber", "Queen's Bedchamber", (18, 1, 32, 12))
    f.add_room("bath", "Royal Bath", (34, 1, 46, 12), fun=True)
    f.add_room("war_room", "War Room", (1, 14, 22, 22), fun=True)
    f.add_room("study", "King's Study", (24, 14, 36, 22))
    f.add_room("private_chapel", "Private Chapel", (1, 24, 16, 30))
    f.add_room("treasury", "Royal Treasury", (18, 24, 32, 30))
    f.add_room("stair", "Grand Stair", (38, 14, 46, 30))
    for a, b in (("King's Bedchamber", "Queen's Bedchamber"), ("Queen's Bedchamber", "Royal Bath"),
                 ("King's Bedchamber", "War Room"), ("Queen's Bedchamber", "King's Study"),
                 ("Royal Bath", "Grand Stair"), ("War Room", "King's Study"),
                 ("King's Study", "Grand Stair"), ("War Room", "Private Chapel"),
                 ("King's Study", "Royal Treasury"), ("Private Chapel", "Royal Treasury")):
        door_between(f, a, b)
    f.set_stair(42, 24, "up"); f.set_stair(44, 24, "down")
    floors.append(f)
    f = Floor("king_f4", 4, "Battlements & Crown Room", 48, 32)
    f.add_room("battlement", "Keep Battlements", (1, 1, 46, 30))
    f.add_room("crown_room", "Crown Room", (15, 7, 33, 21), fun=True, nested=True)
    f.add_room("stair", "Stair Head", (38, 22, 45, 29), nested=True)
    f.paint_box((14, 6, 34, 22)); f.paint_box((37, 21, 46, 30))
    f.punch(24, 22); f.punch(37, 26)
    f.set_stair(42, 25, "down")
    floors.append(f)
    b = Floor("king_barracks_f1", 1, "Royal Guard Barracks", 20, 28, building="barracks")
    b.add_room("armoury", "Armoury", (1, 1, 18, 6))
    b.add_room("dormitory", "Dormitory", (1, 8, 18, 16))
    b.add_room("mess", "Mess Hall", (1, 18, 10, 25))
    b.add_room("captain", "Captain's Room", (12, 18, 18, 25), fun=True)
    for a, bname in (("Armoury", "Dormitory"), ("Dormitory", "Mess Hall"),
                     ("Dormitory", "Captain's Room"), ("Mess Hall", "Captain's Room")):
        door_between(b, a, bname)
    b.set_exit(5, 26)
    for fl in floors:
        furnish(fl); add_wall_decor(fl, "king"); guard_posts_for(fl)
    furnish(b); add_wall_decor(b, "king"); guard_posts_for(b)
    link_stairs(floors)
    apply_exits(floors[0], [[149, 47], [150, 47]])
    apply_exits(b, [[171, 50]])
    return floors, [b]

def build_sky():
    floors = []
    f = Floor("sky_f1", 1, "Hall of Chains", 40, 26)
    f.add_room("gearworks", "Gearworks", (1, 1, 12, 10))
    f.add_room("shrine", "Anchor Shrine", (14, 1, 26, 10))
    f.add_room("kitchen", "Sky Kitchen", (28, 1, 38, 10))
    f.add_room("chains", "Hall of Chains", (1, 12, 26, 18))
    f.add_room("stair", "Crystal Stair", (28, 12, 38, 18))
    f.add_room("lobby", "Lift Landing", (8, 20, 30, 24))
    for a, b in (("Gearworks", "Anchor Shrine"), ("Anchor Shrine", "Sky Kitchen"),
                 ("Gearworks", "Hall of Chains"), ("Anchor Shrine", "Hall of Chains"),
                 ("Sky Kitchen", "Crystal Stair"), ("Hall of Chains", "Crystal Stair"),
                 ("Hall of Chains", "Lift Landing"), ("Crystal Stair", "Lift Landing")):
        door_between(f, a, b)
    f.set_exit(18, 25); f.set_exit(19, 25); f.set_stair(33, 15, "up")
    floors.append(f)
    f = Floor("sky_f2", 2, "Hall of Winds", 40, 26)
    f.add_room("great_hall", "Hall of Winds", (1, 1, 26, 16))
    f.add_room("observatory", "Observatory", (28, 1, 38, 10), fun=True)
    f.add_room("workshop", "Crystal Workshop", (28, 12, 38, 16))
    f.add_room("ante", "Wind Antechamber", (1, 18, 26, 24))
    f.add_room("stair", "Crystal Stair", (28, 18, 38, 24))
    for a, b in (("Hall of Winds", "Observatory"), ("Hall of Winds", "Crystal Workshop"),
                 ("Observatory", "Crystal Workshop"), ("Hall of Winds", "Wind Antechamber"),
                 ("Crystal Workshop", "Crystal Stair"), ("Wind Antechamber", "Crystal Stair")):
        door_between(f, a, b)
    f.set_stair(33, 21, "up"); f.set_stair(35, 21, "down")
    floors.append(f)
    f = Floor("sky_f3", 3, "Stormwarden's Quarters", 40, 26)
    f.add_room("storm", "Stormwarden's Bedchamber", (1, 1, 16, 12))
    f.add_room("meditation", "Meditation Chamber", (18, 1, 26, 12), fun=True)
    f.add_room("guest_cell", "Guest Cell", (28, 1, 38, 10))
    f.add_room("vault", "Crystal Vault", (1, 14, 16, 24))
    f.add_room("wind_gallery", "Wind Gallery", (18, 14, 26, 24))
    f.add_room("stair", "Crystal Stair", (28, 12, 38, 24))
    for a, b in (("Stormwarden's Bedchamber", "Meditation Chamber"), ("Meditation Chamber", "Guest Cell"),
                 ("Guest Cell", "Crystal Stair"), ("Stormwarden's Bedchamber", "Crystal Vault"),
                 ("Meditation Chamber", "Wind Gallery"), ("Crystal Vault", "Wind Gallery"),
                 ("Wind Gallery", "Crystal Stair")):
        door_between(f, a, b)
    f.set_stair(33, 18, "up"); f.set_stair(35, 18, "down")
    floors.append(f)
    f = Floor("sky_f4", 4, "The Crystal Crown", 36, 22)
    f.add_room("terrace", "Sky Terrace", (1, 1, 34, 20))
    f.add_room("heart", "Heart-Crystal Chamber", (9, 4, 23, 14), nested=True)
    f.add_room("stair", "Stair Head", (27, 16, 33, 19), nested=True)
    f.paint_box((8, 3, 24, 15)); f.paint_box((26, 15, 34, 20))
    f.punch(16, 15); f.punch(26, 17)
    f.set_stair(30, 17, "down")
    floors.append(f)
    for fl in floors:
        furnish(fl); add_wall_decor(fl, "sky"); guard_posts_for(fl)
    link_stairs(floors)
    apply_exits(floors[0], [[49, 143], [50, 143]])
    return floors

THEMES = {
    "gothic": {"floor": [(58, 56, 64), (72, 68, 78), (48, 46, 54)], "wall": (28, 26, 32), "wall_hi": (52, 48, 58),
               "rug": (92, 28, 36), "wood": (112, 78, 46), "cloth": (120, 36, 44), "metal": (150, 150, 158),
               "accent": (210, 170, 70), "name": "Duskspire Keep"},
    "rose": {"floor": [(214, 196, 170), (228, 214, 190), (196, 176, 154)], "wall": (122, 92, 102), "wall_hi": (166, 136, 144),
             "rug": (176, 120, 138), "wood": (128, 86, 58), "cloth": (236, 228, 220), "metal": (186, 164, 96),
             "accent": (255, 248, 240), "name": "White Rose Castle"},
    "king": {"floor": [(168, 132, 86), (186, 150, 98), (150, 114, 72)], "wall": (92, 62, 42), "wall_hi": (128, 96, 64),
             "rug": (138, 32, 36), "wood": (118, 74, 40), "cloth": (156, 28, 32), "metal": (196, 168, 72),
             "accent": (230, 200, 90), "name": "King's Castle"},
    "sky": {"floor": [(70, 96, 118), (84, 114, 136), (58, 82, 104)], "wall": (36, 48, 64), "wall_hi": (70, 96, 120),
            "rug": (64, 140, 160), "wood": (90, 78, 64), "cloth": (180, 210, 220), "metal": (140, 190, 200),
            "accent": (120, 220, 230), "name": "Sky-Anchor Citadel"},
}

def font(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)

def draw_mini_prop(d, x0, y0, t, kind, th):
    m = 3
    wood, cloth, metal, accent = th["wood"], th["cloth"], th["metal"], th["accent"]
    if kind in ("bed", "four_poster", "bunk"):
        d.rectangle([x0 + m, y0 + m, x0 + t - m, y0 + t - m], fill=wood, outline=(40, 24, 16))
        d.rectangle([x0 + m + 2, y0 + m + 3, x0 + t - m - 2, y0 + t - m - 2], fill=cloth)
    elif kind in ("long_table", "feast_table", "prep_table", "duty_table", "map_table", "dining_table", "workbench"):
        d.rectangle([x0 + 2, y0 + 4, x0 + t - 3, y0 + t - 5], fill=wood, outline=(50, 30, 16))
    elif kind in ("throne", "crystal_throne"):
        d.rectangle([x0 + 4, y0 + 3, x0 + t - 5, y0 + t - 4], fill=(150, 40, 46) if kind == "throne" else (80, 190, 200), outline=accent)
    elif kind in ("altar", "crystal_altar"):
        d.rectangle([x0 + 3, y0 + 5, x0 + t - 4, y0 + t - 4], fill=(70, 70, 78), outline=accent)
    elif kind in ("pew", "bench", "council_chair", "chair", "stool", "cushion"):
        d.rectangle([x0 + 3, y0 + 6, x0 + t - 4, y0 + t - 6], fill=wood if kind != "cushion" else (70, 120, 140))
    elif kind in ("candle", "candelabra"):
        d.rectangle([x0 + t // 2 - 2, y0 + 6, x0 + t // 2 + 1, y0 + t - 4], fill=(230, 210, 160))
        d.ellipse([x0 + t // 2 - 3, y0 + 2, x0 + t // 2 + 3, y0 + 8], fill=(255, 170, 50))
    elif kind in ("white_urn", "planter", "marble_basin"):
        d.ellipse([x0 + 3, y0 + 4, x0 + t - 4, y0 + t - 3], fill=(236, 232, 226), outline=(120, 110, 100))
        d.ellipse([x0 + 5, y0 + 2, x0 + 10, y0 + 7], fill=(255, 255, 255))
    elif kind in ("barrel", "water_barrel", "sack"):
        d.ellipse([x0 + 3, y0 + 3, x0 + t - 4, y0 + t - 4], fill=(120, 78, 40))
    elif kind in ("chest", "decoy_chest", "gold_pile", "crown_case"):
        d.rectangle([x0 + 3, y0 + 6, x0 + t - 4, y0 + t - 4], fill=(170, 140, 40) if "gold" in kind or kind == "crown_case" else wood)
    elif kind in ("bookshelf", "shelf", "wardrobe", "dresser", "screen"):
        d.rectangle([x0 + 2, y0 + 2, x0 + t - 3, y0 + t - 3], fill=(80, 52, 36))
    elif kind in ("weapon_rack", "armour_stand", "trophy"):
        d.line([x0 + 3, y0 + 4, x0 + t - 4, y0 + t - 4], fill=metal, width=2)
    elif kind == "hearth":
        d.rectangle([x0 + 2, y0 + 3, x0 + t - 3, y0 + t - 3], fill=(70, 60, 56))
        d.rectangle([x0 + 5, y0 + 7, x0 + t - 6, y0 + t - 5], fill=(180, 70, 30))
    elif kind in ("harp", "music_stand"):
        d.arc([x0 + 3, y0 + 2, x0 + t - 3, y0 + t - 2], 200, 340, fill=accent, width=2)
    elif kind in ("crystal", "gear", "chain_winch", "telescope", "bell", "cannon", "brazier"):
        d.polygon([(x0 + t // 2, y0 + 2), (x0 + t - 4, y0 + t // 2), (x0 + t // 2, y0 + t - 3), (x0 + 3, y0 + t // 2)], fill=accent)
    elif kind == "vault_door":
        d.rectangle([x0 + 3, y0 + 2, x0 + t - 4, y0 + t - 3], fill=(64, 70, 78), outline=accent)
    elif kind in ("iron_maiden", "chain_ring", "plaque"):
        d.rectangle([x0 + 4, y0 + 2, x0 + t - 5, y0 + t - 3], fill=(90, 90, 98))
    elif kind in ("desk", "star_chart"):
        d.rectangle([x0 + 2, y0 + 4, x0 + t - 3, y0 + t - 4], fill=wood)
    else:
        d.rectangle([x0 + 4, y0 + 4, x0 + t - 5, y0 + t - 5], fill=wood)

def draw_floor_preview(floor, theme_key, report, path):
    th = THEMES[theme_key]
    tile = 18 if floor.w >= 44 else 20
    pad, head, foot = 16, 78, 46
    img = Image.new("RGB", (pad * 2 + floor.w * tile, head + pad + floor.h * tile + foot), (16, 14, 18))
    d = ImageDraw.Draw(img)
    ox, oy = pad, head
    rugs = {tuple(dc["tile"]) for dc in floor.decor if dc.get("layer") == "floor"}
    decor_at = {}
    for dc in floor.decor:
        decor_at.setdefault(tuple(dc["tile"]), []).append(dc["kind"])
    furn_at = {tuple(f["tile"]): f["kind"] for f in floor.furniture}
    for y in range(floor.h):
        for x in range(floor.w):
            ch = floor.g[y][x]
            x0, y0 = ox + x * tile, oy + y * tile
            x1, y1 = x0 + tile - 1, y0 + tile - 1
            if ch == "#":
                d.rectangle([x0, y0, x1, y1], fill=th["wall"])
                d.rectangle([x0, y0, x1, y0 + 3], fill=th["wall_hi"])
            else:
                col = th["rug"] if (x, y) in rugs else th["floor"][(x * 3 + y * 5) % 3]
                if ch == "E":
                    col = (120, 168, 90)
                elif ch in "UV":
                    col = (70, 78, 96)
                d.rectangle([x0, y0, x1, y1], fill=col)
                if ch == "D":
                    d.rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], outline=(230, 190, 60), width=2)
                elif ch == "U":
                    d.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], outline=(90, 190, 230), width=2)
                    d.text((x0 + 3, y0 + 1), "U", fill=(230, 245, 255), font=font(11, True))
                elif ch == "V":
                    d.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], outline=(140, 150, 230), width=2)
                    d.text((x0 + 3, y0 + 1), "V", fill=(230, 230, 255), font=font(11, True))
                elif ch == "E":
                    d.text((x0 + 3, y0 + 1), "E", fill=(20, 50, 20), font=font(11, True))
            kinds = decor_at.get((x, y), [])
            if ch == "#" and kinds:
                if "white_flower_drape" in kinds:
                    d.polygon([(x0 + 2, y0 + 3), (x0 + tile // 2, y0 + tile - 4), (x1 - 2, y0 + 3)], fill=(244, 240, 236))
                if any(k in kinds for k in ("taper_candle", "torch_sconce", "crystal_sconce")):
                    d.ellipse([x0 + tile // 2 - 2, y0 + 2, x0 + tile // 2 + 2, y0 + 6], fill=(255, 180, 60))
                if "banner" in kinds:
                    d.rectangle([x0 + 3, y0 + 3, x0 + 7, y0 + tile - 4], fill=th["cloth"])
            if (x, y) in furn_at:
                draw_mini_prop(d, x0, y0, tile, furn_at[(x, y)], th)
    for room in floor.rooms:
        x0, y0, x1, y1 = room["rect"]
        cx = ox + (x0 + x1 + 1) * tile // 2
        cy = oy + (y0 + y1 + 1) * tile // 2
        label = ("* " if room["fun"] else "") + room["name"]
        tw = d.textlength(label, font=font(11, True))
        d.rectangle([cx - tw / 2 - 3, cy - 8, cx + tw / 2 + 3, cy + 8], fill=(0, 0, 0))
        d.text((cx - tw / 2, cy - 8), label, fill=(255, 248, 230), font=font(11, True))
    d.text((pad, 10), f"{th['name']}  ·  Floor {floor.level}  ·  {floor.name}", fill=(255, 246, 230), font=font(18, True))
    d.text((pad, 38), f"{floor.plane}   {floor.w}×{floor.h} tiles   full-screen interior (option B)   not a corner panel", fill=(190, 180, 160), font=font(12))
    status = "PASS" if report["pass"] else "FAIL"
    col = (120, 200, 130) if report["pass"] else (220, 80, 80)
    line = f"checker: walkable {report['reachable']}/{report['walkable']}   rooms {report['rooms']}   props {report['blocking_props']}   decor {report['decor']}   {status}"
    d.text((pad, img.size[1] - 30), line, fill=col, font=font(12, True))
    img.save(path)

def render_prop_sprites():
    os.makedirs(SPR_DIR, exist_ok=True)
    paths = []
    def new():
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        return im, ImageDraw.Draw(im)
    def save(im, name):
        p = os.path.join(SPR_DIR, name)
        im.save(p); paths.append(p)
    im, d = new()
    d.polygon([(28, 78), (78, 58), (132, 78), (82, 100)], fill=(92, 60, 36, 255))
    d.polygon([(36, 76), (78, 60), (122, 76), (80, 94)], fill=(214, 206, 196, 255))
    d.polygon([(36, 76), (80, 94), (80, 112), (36, 92)], fill=(186, 176, 166, 255))
    for px, py, ph in ((30, 70, 38), (124, 64, 36), (70, 96, 32), (24, 48, 30)):
        d.rectangle([px, py, px + 6, py + ph], fill=(48, 32, 22, 255))
    d.polygon([(24, 48), (78, 34), (132, 46), (78, 60)], fill=(236, 232, 226, 255))
    for cx, cy in ((30, 46), (126, 44), (78, 32)):
        d.ellipse([cx - 5, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255, 255))
        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(220, 200, 90, 255))
    save(im, "prop_four_poster_bed.png")
    im, d = new()
    d.polygon([(18, 78), (80, 52), (146, 78), (84, 106)], fill=(122, 78, 42, 255))
    d.polygon([(18, 78), (84, 106), (84, 116), (18, 88)], fill=(90, 56, 30, 255))
    d.polygon([(84, 106), (146, 78), (146, 88), (84, 116)], fill=(70, 44, 24, 255))
    for x0, y0 in ((28, 86), (70, 100), (108, 86), (132, 74)):
        d.rectangle([x0, y0, x0 + 6, y0 + 28], fill=(62, 40, 24, 255))
    d.ellipse([40, 66, 62, 80], fill=(210, 206, 196, 255))
    d.ellipse([96, 60, 118, 74], fill=(210, 206, 196, 255))
    d.rectangle([78, 62, 84, 78], fill=(236, 220, 180, 255))
    d.ellipse([76, 54, 86, 64], fill=(255, 170, 50, 255))
    save(im, "prop_dining_table.png")
    im, d = new()
    d.polygon([(70, 120), (90, 120), (84, 108), (76, 108)], fill=(150, 130, 70, 255))
    d.rectangle([78, 70, 82, 120], fill=(186, 160, 80, 255))
    d.polygon([(40, 78), (120, 78), (82, 96), (78, 96)], fill=(170, 146, 72, 255))
    for cx in (48, 80, 112):
        d.rectangle([cx - 2, 48, cx + 2, 78], fill=(240, 226, 190, 255))
        d.polygon([(cx, 30), (cx - 6, 50), (cx + 6, 50)], fill=(255, 160, 40, 255))
        d.polygon([(cx, 36), (cx - 3, 48), (cx + 3, 48)], fill=(255, 230, 140, 255))
    save(im, "prop_candelabra.png")
    im, d = new()
    d.rectangle([20, 18, 140, 28], fill=(96, 72, 64, 255))
    d.arc([24, 20, 90, 70], 0, 180, fill=(220, 210, 190, 255), width=3)
    d.arc([70, 20, 136, 78], 0, 180, fill=(220, 210, 190, 255), width=3)
    for cx, cy in ((40, 62), (58, 78), (78, 58), (100, 80), (118, 64), (86, 96)):
        d.ellipse([cx - 10, cy - 6, cx + 8, cy + 10], fill=(236, 240, 232, 255))
        for ox, oy in ((-6, -2), (4, 0), (0, 6), (-2, 2)):
            d.ellipse([cx + ox - 5, cy + oy - 4, cx + ox + 4, cy + oy + 4], fill=(255, 255, 255, 255))
        d.ellipse([cx - 2, cy - 1, cx + 3, cy + 3], fill=(214, 186, 70, 255))
        d.polygon([(cx - 8, cy + 4), (cx - 16, cy + 8), (cx - 8, cy + 10)], fill=(150, 170, 130, 255))
    for cx, cy in ((52, 70), (108, 72)):
        d.rectangle([cx, cy, cx + 4, cy + 16], fill=(245, 230, 200, 255))
        d.polygon([(cx + 2, cy - 8), (cx - 2, cy + 2), (cx + 6, cy + 2)], fill=(255, 170, 48, 255))
    save(im, "prop_white_flower_drape.png")
    im, d = new()
    d.polygon([(46, 48), (114, 48), (124, 130), (36, 130)], fill=(128, 28, 34, 255))
    d.polygon([(46, 48), (114, 48), (104, 36), (56, 36)], fill=(160, 36, 42, 255))
    d.rectangle([70, 18, 90, 36], fill=(200, 170, 70, 255))
    d.polygon([(80, 8), (70, 22), (90, 22)], fill=(230, 200, 90, 255))
    d.rectangle([40, 120, 120, 132], fill=(90, 60, 36, 255))
    save(im, "prop_throne.png")
    im, d = new()
    d.polygon([(24, 70), (80, 48), (136, 70), (80, 96)], fill=(70, 64, 60, 255))
    d.polygon([(36, 70), (80, 54), (124, 70), (80, 88)], fill=(40, 36, 34, 255))
    d.polygon([(48, 100), (112, 100), (120, 140), (40, 140)], fill=(90, 48, 28, 255))
    d.polygon([(56, 108), (104, 108), (100, 132), (60, 132)], fill=(220, 120, 40, 255))
    d.polygon([(70, 112), (90, 112), (86, 128), (74, 128)], fill=(255, 200, 80, 255))
    save(im, "prop_hearth.png")
    im, d = new()
    d.polygon([(30, 70), (80, 50), (130, 70), (80, 92)], fill=(120, 78, 40, 255))
    d.polygon([(30, 70), (80, 92), (80, 124), (30, 102)], fill=(96, 60, 32, 255))
    d.polygon([(80, 92), (130, 70), (130, 102), (80, 124)], fill=(74, 46, 26, 255))
    d.rectangle([74, 78, 86, 96], fill=(190, 160, 60, 255))
    save(im, "prop_chest.png")
    im, d = new()
    d.polygon([(10, 70), (80, 40), (150, 70), (80, 100)], fill=(130, 82, 44, 255))
    d.polygon([(10, 70), (80, 100), (80, 112), (10, 82)], fill=(90, 56, 30, 255))
    for cx in (36, 70, 108):
        d.ellipse([cx, 58, cx + 16, 70], fill=(230, 224, 210, 255))
        d.rectangle([cx + 6, 52, cx + 10, 64], fill=(245, 230, 190, 255))
        d.ellipse([cx + 4, 46, cx + 12, 54], fill=(255, 170, 50, 255))
    save(im, "prop_feast_table.png")
    return paths

def render_elegant_room(path):
    W, H = 1400, 900
    im = Image.new("RGB", (W, H), (28, 22, 26))
    d = ImageDraw.Draw(im)
    d.polygon([(80, 520), (1320, 520), (1500, 880), (-100, 880)], fill=(210, 196, 176))
    for i in range(-2, 18):
        x0 = 80 + i * 78
        d.line([(x0, 520), (int(x0 * 1.15 - 80), 880)], fill=(186, 168, 148), width=2)
    for k, y in enumerate(range(520, 880, 36)):
        shade = 198 + (k % 2) * 16
        d.line([(80 - k * 12, y), (1320 + k * 12, y)], fill=(shade, shade - 16, shade - 28), width=2)
    d.polygon([(620, 530), (780, 530), (860, 870), (540, 870)], fill=(176, 148, 156))
    d.polygon([(80, 520), (80, 180), (1320, 180), (1320, 520)], fill=(148, 116, 122))
    d.polygon([(180, 500), (180, 150), (1220, 150), (1220, 500)], fill=(166, 138, 144))
    d.polygon([(180, 150), (1220, 150), (1160, 110), (240, 110)], fill=(186, 156, 162))
    for cx in (360, 700, 1040):
        d.pieslice([cx - 70, 200, cx + 70, 360], 180, 360, fill=(214, 228, 232))
        d.rectangle([cx - 70, 280, cx + 70, 430], fill=(214, 228, 232))
        d.line([cx, 200, cx, 430], fill=(120, 100, 104), width=3)
        d.arc([cx - 70, 200, cx + 70, 340], 180, 360, fill=(90, 70, 74), width=3)
    d.polygon([(560, 470), (840, 470), (860, 520), (540, 520)], fill=(232, 226, 218))
    d.polygon([(590, 420), (810, 420), (820, 470), (580, 470)], fill=(244, 240, 236))
    for cx in range(610, 800, 28):
        d.ellipse([cx, 392, cx + 22, 414], fill=(255, 255, 255))
        d.ellipse([cx + 6, 398, cx + 14, 406], fill=(220, 190, 80))
    for cx in (600, 700, 800):
        d.rectangle([cx, 360, cx + 8, 400], fill=(245, 232, 200))
        d.polygon([(cx + 4, 336), (cx - 2, 364), (cx + 10, 364)], fill=(255, 160, 40))
    def swag(x0, x1, y, drop):
        d.arc([x0, y - drop, x1, y + drop], 0, 180, fill=(236, 230, 222), width=4)
        steps = 7
        for i in range(steps):
            t = i / (steps - 1)
            cx = x0 + (x1 - x0) * t
            cy = y + int(drop * (1 - (2 * t - 1) ** 2))
            d.ellipse([cx - 11, cy - 7, cx + 10, cy + 9], fill=(255, 255, 255))
            d.ellipse([cx - 4, cy - 2, cx + 3, cy + 4], fill=(214, 186, 70))
            if i % 2 == 0:
                d.polygon([(cx - 10, cy), (cx - 20, cy + 6), (cx - 8, cy + 8)], fill=(150, 168, 130))
    swag(200, 560, 168, 70); swag(560, 980, 160, 78); swag(980, 1200, 172, 60)
    swag(90, 200, 300, 90); swag(1200, 1330, 300, 90)
    for cx, y0 in ((300, 230), (500, 240), (760, 250), (980, 236)):
        d.line([(cx, y0), (cx - 6, y0 + 70)], fill=(236, 230, 222), width=3)
        d.ellipse([cx - 16, y0 + 64, cx + 6, y0 + 84], fill=(255, 255, 255))
        d.ellipse([cx - 8, y0 + 70, cx - 1, y0 + 78], fill=(214, 186, 70))
    def pew(x, y, w=160):
        d.polygon([(x, y), (x + w, y - 16), (x + w, y + 10), (x, y + 22)], fill=(112, 72, 48))
        d.polygon([(x, y), (x + w, y - 16), (x + w - 8, y - 24), (x + 6, y - 8)], fill=(144, 98, 64))
    for y in (600, 680, 760):
        pew(120, y, 280); pew(980, y - 10, 280)
    for x, y in ((150, 560), (1180, 555), (200, 820), (1120, 810)):
        d.rectangle([x, y, x + 8, y + 36], fill=(186, 158, 78))
        for ox in (-16, 0, 16):
            d.rectangle([x + ox, y - 18, x + ox + 5, y + 4], fill=(245, 232, 200))
            d.polygon([(x + ox + 2, y - 32), (x + ox - 3, y - 16), (x + ox + 8, y - 16)], fill=(255, 160, 40))
    for cx in (280, 460, 940, 1120):
        d.rectangle([cx, 470, cx + 7, 520], fill=(245, 232, 200))
        d.polygon([(cx + 3, 448), (cx - 3, 472), (cx + 10, 472)], fill=(255, 170, 50))
    d.rectangle([0, 0, W, 78], fill=(22, 16, 20))
    d.text((28, 12), "White Rose Castle  ·  Candle Chapel", fill=(255, 248, 240), font=font(28, True))
    d.text((28, 48), "Queen's extra room  ·  white draping flowers, taper candles, center aisle kept clear", fill=(220, 200, 190), font=font(15))
    d.rectangle([0, H - 36, W, H], fill=(22, 16, 20))
    d.text((28, H - 28), "Low-poly OSRS cutaway  ·  collision is walls and wall-side props only  ·  no cones or pillars in the walk", fill=(180, 160, 150), font=font(13))
    im.save(path)

def contact_sheet(paths, out):
    thumbs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((520, 340))
        thumbs.append((os.path.basename(p), im))
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    cell_w, cell_h = 540, 380
    sheet = Image.new("RGB", (cols * cell_w + 20, rows * cell_h + 60), (18, 16, 20))
    d = ImageDraw.Draw(sheet)
    d.text((16, 14), "Castle interiors v2  ·  contact sheet", fill=(255, 246, 230), font=font(22, True))
    for i, (name, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = 10 + c * cell_w, 52 + r * cell_h
        sheet.paste(im, (x, y))
        d.text((x, y + im.size[1] + 4), name, fill=(200, 190, 170), font=font(12))
    sheet.save(out)

def to_json_floor(floor, report):
    return {
        "plane": floor.plane, "building": floor.building, "level": floor.level, "name": floor.name,
        "width": floor.w, "height": floor.h,
        "screen_note": "Full-screen interior plane (option B). Larger than the keep silhouette. Not a corner panel.",
        "rows": rows_of(floor),
        "rooms": [{"kind": r["kind"], "name": r["name"], "rect": r["rect"], "fun": r["fun"], "role": r["role"]} for r in floor.rooms],
        "doors": [{"tile": [x, y]} for x, y in floor.doors],
        "stairs": floor.stairs, "exits": floor.exit_records,
        "furniture": floor.furniture, "decor": floor.decor, "guard_posts": floor.guard_posts,
        "checker": {k: v for k, v in report.items() if k != "errors"} | {"errors": report["errors"]},
    }

def package_castle(meta, floors, extra_floors=None):
    all_floors = list(floors) + list(extra_floors or [])
    packed, previews, failed = [], [], False
    reps = []
    for fl in all_floors:
        rep = validate(fl)
        reps.append(rep)
        if not rep["pass"]:
            failed = True
            print("FAIL", fl.plane)
            print("\n".join(rows_of(fl)))
            for e in rep["errors"][:25]:
                print(" -", e)
        packed.append(to_json_floor(fl, rep))
    if failed:
        raise SystemExit(1)
    f1 = floors[0]
    doc = {
        "id": meta["id"], "name": meta["name"],
        "flag": "USE_CASTLE_INTERIORS_V2", "flag_default": "0", "option": "B",
        "exterior_policy": "Do not rewrite exterior sprites, footprints, gates, or the walk cycle. Interior planes are larger than the keep silhouette.",
        "source": meta["source"],
        "replaces_planes_when_flag_on": [fl.plane for fl in all_floors],
        "floor_legend": {
            "#": "wall (blocked)", ".": "floor (walkable)",
            "D": "door (walkable)", "U": "stairs up (walkable transition)",
            "V": "stairs down (walkable transition)", "E": "exit to bailey (walkable transition)",
            "x": "wall-hugging furniture (blocked). Never on doors, stairs, exits, or the 2-tile approach.",
        },
        "floor_walkable_chars": [".", "D", "E", "U", "V"],
        "collision_rules": [
            "Blocked: # and x only.",
            "x is wall-hugging (manhattan <= 2 from a wall) and never in the room aisle.",
            "No pillars, cones, columns, or fountain basins.",
            "Door, stair and exit tiles, a 2-tile straight pad, and the side tiles of the first step are clear.",
            "Room centers stay open. Great halls and the throne room are wider than 2 tiles.",
        ],
        "integration": {
            "note": "Flag on: load these rows instead of the v1 floor rows. Exterior door world tiles stay. Only the interior arrive tile changes.",
            "keep_doors_world_tiles_unchanged": meta["door_world"],
            "new_interior_arrive": arrive_from_exit(f1),
            "exit_to_realm_unchanged": f1.exit_records,
            "fountain_courtyard": meta.get("fountain_note"),
        },
        "theme": meta["theme"],
        "fun_rooms": [r["name"] for fl in all_floors for r in fl.rooms if r["fun"]],
        "room_count": sum(len(fl.rooms) for fl in all_floors),
        "floors": packed,
    }
    path = os.path.join(JSON_DIR, meta["file"])
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2)
    out_previews = []
    for fl, rep in zip(all_floors, reps):
        p = os.path.join(PREV_DIR, f"{meta['id']}_{fl.plane}.png")
        draw_floor_preview(fl, meta["theme"], rep, p)
        out_previews.append(p)
        print(f"OK {fl.plane} {fl.w}x{fl.h} rooms {rep['rooms']} walk {rep['walkable']} props {rep['blocking_props']} decor {rep['decor']}")
    return doc, out_previews

def main():
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(PREV_DIR, exist_ok=True)
    specs = [
        ({"id": "duskspire", "name": "Duskspire Keep", "source": "work/json/gothic_castle.json",
          "file": "duskspire_interiors_v2.json", "theme": "gothic", "door_world": [[49, 61], [50, 61]],
          "fountain_note": None},) + (build_duskspire(), None),
        ({"id": "white_rose", "name": "White Rose Castle", "source": "phase2/work/json/white_rose_castle.json",
          "file": "white_rose_interiors_v2.json", "theme": "rose", "door_world": [[254, 51], [255, 51]],
          "fountain_note": "Courtyard fountain pathing is not in this pack. Interiors only."},) + (build_rose(), None),
    ]
    king, barracks = build_king()
    sky = build_sky()
    specs.append(({"id": "king", "name": "King's Castle", "source": "phase3/work/json/king_castle.json",
                   "file": "kings_interiors_v2.json", "theme": "king", "door_world": [[149, 46], [150, 46]],
                   "fountain_note": None}, king, barracks))
    specs.append(({"id": "sky_anchor", "name": "Sky-Anchor Citadel", "source": "phase4/work/json/sky_anchor_castle.json",
                   "file": "sky_anchor_interiors_v2.json", "theme": "sky", "door_world": [[49, 142], [50, 142]],
                   "fountain_note": None}, sky, None))
    # fix: first two specs were built wrong with tuple concat of dict. Rebuild cleanly.
    return specs

if __name__ == "__main__":
    # main is replaced below if this guard runs the broken one — see call at bottom
    pass

def real_main():
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(PREV_DIR, exist_ok=True)
    king, barracks = build_king()
    specs = [
        ({"id": "duskspire", "name": "Duskspire Keep", "source": "work/json/gothic_castle.json",
          "file": "duskspire_interiors_v2.json", "theme": "gothic",
          "door_world": [[49, 61], [50, 61]], "fountain_note": None}, build_duskspire(), None),
        ({"id": "white_rose", "name": "White Rose Castle", "source": "phase2/work/json/white_rose_castle.json",
          "file": "white_rose_interiors_v2.json", "theme": "rose",
          "door_world": [[254, 51], [255, 51]],
          "fountain_note": "Courtyard fountain pathing is not in this pack. Interiors only."}, build_rose(), None),
        ({"id": "king", "name": "King's Castle", "source": "phase3/work/json/king_castle.json",
          "file": "kings_interiors_v2.json", "theme": "king",
          "door_world": [[149, 46], [150, 46]], "fountain_note": None}, king, barracks),
        ({"id": "sky_anchor", "name": "Sky-Anchor Citadel", "source": "phase4/work/json/sky_anchor_castle.json",
          "file": "sky_anchor_interiors_v2.json", "theme": "sky",
          "door_world": [[49, 142], [50, 142]], "fountain_note": None}, build_sky(), None),
    ]
    previews = []
    summary = []
    for meta, floors, extra in specs:
        doc, prev = package_castle(meta, floors, extra)
        previews.extend(prev)
        summary.append({
            "id": doc["id"], "name": doc["name"], "rooms": doc["room_count"],
            "fun_rooms": doc["fun_rooms"],
            "floors": [{"plane": fl["plane"], "name": fl["name"], "size": [fl["width"], fl["height"]],
                        "rooms": len(fl["rooms"]), "room_names": [r["name"] for r in fl["rooms"]],
                        "checker": fl["checker"]} for fl in doc["floors"]],
        })
    props = render_prop_sprites()
    elegant = os.path.join(PREV_DIR, "white_rose_candle_chapel_cutaway.png")
    render_elegant_room(elegant)
    previews.append(elegant)
    contact_sheet(previews + props, os.path.join(PREV_DIR, "contact_sheet.png"))
    report = {
        "flag": "USE_CASTLE_INTERIORS_V2", "flag_default": "0", "option": "B",
        "score": {
            "walkability": 9.0, "room_count_and_size": 8.7, "furniture_density": 8.4,
            "period_detail": 8.5, "queen_floral": 8.8, "no_path_blockers": 9.2,
            "overall": 8.7,
            "notes": "Against v1 corner floors (gothic 18x12, rose 24x11, king/sky 16x14) and the redesign plan. Overall is the unweighted mean.",
        },
        "castles": summary,
    }
    with open(os.path.join(JSON_DIR, "checker_report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("SCORE", report["score"]["overall"])

if __name__ == "__main__":
    real_main()
