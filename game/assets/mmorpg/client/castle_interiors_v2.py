"""Draw v2 castle interiors. Exterior sprites are left alone.

When the flag is on, the old floor cutaway is the wrong size for these
planes, so the room is the tile grid plus the pack's prop sprites.
"""
from __future__ import annotations

import json
from pathlib import Path

import pygame

import feature_flags

_ROOT = Path(__file__).resolve().parents[2] / "interiors_v2"
_PROPS = Path(__file__).resolve().parents[2] / "interior_props"
_JSON = _ROOT / "json"
_SPRITES = _ROOT / "sprites"
_FILES = (
    "duskspire_interiors_v2.json",
    "white_rose_interiors_v2.json",
    "kings_interiors_v2.json",
    "sky_anchor_interiors_v2.json",
)
_SPRITE = {
    "four_poster": "prop_four_poster_bed.png",
    "bed": "prop_four_poster_bed.png",
    "bunk": "prop_four_poster_bed.png",
    "feast_table": "prop_feast_table.png",
    "long_table": "prop_feast_table.png",
    "prep_table": "prop_dining_table.png",
    "duty_table": "prop_dining_table.png",
    "map_table": "prop_dining_table.png",
    "throne": "prop_throne.png",
    "crystal_throne": "prop_throne.png",
    "hearth": "prop_hearth.png",
    "chest": "prop_chest.png",
    "decoy_chest": "prop_chest.png",
    "candelabra": "prop_candelabra.png",
    "taper_candle": "prop_candelabra.png",
    "candle": "prop_candelabra.png",
    "white_flower_drape": "prop_white_flower_drape.png",
}
# Larger art from interior_props. Falls back to the v2 sprites above.
_PROP_SPRITE = {
    "four_poster": "props/prop_canopy_bed.png",
    "bed": "props/prop_canopy_bed.png",
    "bench": "props/prop_banquet_bench.png",
    "pew": "props/prop_gothic_pew.png",
    "shelf": "props/prop_bookshelf.png",
    "bookshelf": "props/prop_bookshelf.png",
    "banner": "props/prop_tapestry.png",
    "weapon_rack": "props/prop_weapon_rack.png",
    "desk": "props/prop_writing_desk.png",
    "dresser": "props/prop_sideboard.png",
    "wardrobe": "props/prop_sideboard.png",
    "altar": "props/prop_crystal_altar.png",
    "crystal_altar": "props/prop_crystal_altar.png",
    "map_table": "props/prop_map_table.png",
    "harp": "props/prop_harp.png",
    "chain_winch": "props/prop_chain_winch.png",
    "chain_ring": "props/prop_chain_winch.png",
    "armour_stand": "props/prop_suit_of_armour.png",
}
_STAIR_ART = {
    "gothic": "spiral_stair/spiral_stair_duskspire.png",
    "rose": "spiral_stair/spiral_stair_white_rose.png",
    "king": "spiral_stair/spiral_stair_king.png",
    "sky": "spiral_stair/spiral_stair_sky_anchor.png",
}
_ROOM_PROP = {
    "petal bath": "props/prop_bathtub.png",
    "royal bath": "props/prop_bathtub.png",
    "rose gallery": "props/prop_rose_trellis.png",
    "glass conservatory": "props/prop_rose_trellis.png",
    "gallery walk": "props/prop_rose_trellis.png",
    "roof terrace": "props/prop_rose_trellis.png",
}
_CHANDELIER_ROOMS = {
    "great hall", "great hall of roses", "throne room", "candle chapel", "hall of winds",
}
_CACHE = {}
_FLOORS = None
_THEMES = {
    "gothic": {"floor": ((58, 56, 64), (72, 68, 78), (48, 46, 54)), "wall": (28, 26, 32), "wall_hi": (52, 48, 58), "rug": (92, 28, 36)},
    "rose": {"floor": ((214, 196, 170), (228, 214, 190), (196, 176, 154)), "wall": (122, 92, 102), "wall_hi": (166, 136, 144), "rug": (176, 120, 138)},
    "king": {"floor": ((168, 132, 86), (186, 150, 98), (150, 114, 72)), "wall": (92, 62, 42), "wall_hi": (128, 96, 64), "rug": (138, 32, 36)},
    "sky": {"floor": ((70, 96, 118), (84, 114, 136), (58, 82, 104)), "wall": (36, 48, 64), "wall_hi": (70, 96, 120), "rug": (64, 140, 160)},
}


def _theme(plane):
    if plane.startswith("rose"):
        return _THEMES["rose"]
    if plane.startswith("king"):
        return _THEMES["king"]
    if plane.startswith("sky"):
        return _THEMES["sky"]
    return _THEMES["gothic"]


def active():
    return feature_flags.USE_CASTLE_INTERIORS_V2


def _widen_doors(rows):
    """Turn each one-tile doorway into a three-tile opening."""
    if not rows:
        return rows
    grid = [list(row) for row in rows]
    height, width = len(grid), len(grid[0])
    doors = [(x, y) for y in range(height) for x in range(width) if grid[y][x] == "D"]
    for x, y in doors:
        horizontal = (
            (x > 0 and grid[y][x - 1] == "#")
            or (x + 1 < width and grid[y][x + 1] == "#")
        )
        vertical = (
            (y > 0 and grid[y - 1][x] == "#")
            or (y + 1 < height and grid[y + 1][x] == "#")
        )
        if horizontal:
            for nx in (x - 1, x + 1):
                if 0 < nx < width - 1 and grid[y][nx] == "#":
                    grid[y][nx] = "D"
        if vertical:
            for ny in (y - 1, y + 1):
                if 0 < ny < height - 1 and grid[ny][x] == "#":
                    grid[ny][x] = "D"
    return ["".join(row) for row in grid]


def _floors():
    global _FLOORS
    if _FLOORS is None:
        found = {}
        if active():
            for filename in _FILES:
                path = _JSON / filename
                if not path.is_file():
                    continue
                with path.open(encoding="utf-8") as handle:
                    blob = json.load(handle)
                for floor in blob.get("floors", []):
                    floor = dict(floor)
                    floor["rows"] = _widen_doors(floor.get("rows") or [])
                    found[floor["plane"]] = floor
        _FLOORS = found
    return _FLOORS


def handles(plane: str) -> bool:
    return active() and plane in _floors()


def rooms(plane: str):
    floor = _floors().get(plane)
    if floor is None:
        return None
    return floor.get("rooms") or []


def _theme_key(plane):
    if plane.startswith("rose"):
        return "rose"
    if plane.startswith("king"):
        return "king"
    if plane.startswith("sky"):
        return "sky"
    return "gothic"


def _image(path, tile, scale):
    key = (str(path), int(tile), round(float(scale), 2))
    if key in _CACHE:
        return _CACHE[key]
    if not path.is_file():
        _CACHE[key] = None
        return None
    image = pygame.image.load(str(path)).convert_alpha()
    bounds = image.get_bounding_rect(min_alpha=8)
    if bounds.w > 0 and bounds.h > 0:
        image = image.subsurface(bounds).copy()
    side = max(12, int(tile * scale))
    width, height = image.get_size()
    if width >= height:
        size = (side, max(8, int(side * height / max(width, 1))))
    else:
        size = (max(8, int(side * width / max(height, 1))), side)
    image = pygame.transform.smoothscale(image, size)
    _CACHE[key] = image
    return image


def _lookup(kind):
    relative = _PROP_SPRITE.get(kind)
    if relative:
        path = _PROPS / relative
        if path.is_file():
            return path, 3.4
    name = _SPRITE.get(kind)
    if name:
        return _SPRITES / name, _prop_scale(kind)
    return None, 0


def stair_tiles(plane):
    floor = _floors().get(plane) or {}
    tiles = []
    for stair in floor.get("stairs") or []:
        tile = stair.get("tile") or [0, 0]
        tiles.append((int(tile[0]), int(tile[1])))
    return tiles


def stair_pad(plane, x, y):
    """Stair tile under a click, including the spiral sprite around it."""
    tiles = stair_tiles(plane)
    if not tiles:
        return None
    near = [tile for tile in tiles if max(abs(x - tile[0]), abs(y - tile[1])) <= 2]
    if not near:
        return None
    return min(near, key=lambda tile: abs(tile[0] - x) + abs(tile[1] - y))


def _prop_scale(kind):
    if kind in ("taper_candle", "candle", "torch_sconce", "crystal_sconce", "candelabra"):
        return 1.35
    if kind == "white_flower_drape":
        return 1.8
    return 2.6


def _draw_furniture(screen, kind, sx, sy, tile, theme):
    """Larger stand-in when a furniture kind has no pack sprite."""
    wood = (118, 78, 46)
    cloth = theme["rug"]
    name = kind or ""
    if "pew" in name or "bench" in name:
        body = pygame.Rect(sx * tile - tile // 3, sy * tile + tile // 3, int(tile * 1.7), max(8, tile // 3))
    elif any(word in name for word in ("shelf", "book", "wardrobe", "cabinet", "banner")):
        body = pygame.Rect(sx * tile + 2, sy * tile - tile // 2, tile - 4, int(tile * 1.45))
    elif "altar" in name or "table" in name:
        body = pygame.Rect(sx * tile - tile // 4, sy * tile + tile // 5, int(tile * 1.5), int(tile * 0.7))
    else:
        body = pygame.Rect(sx * tile + tile // 8, sy * tile + tile // 8, int(tile * 0.75), int(tile * 0.75))
    pygame.draw.rect(screen, cloth if "pew" in name or "banner" in name else wood, body)
    pygame.draw.rect(screen, (40, 28, 18), body, 2)


def queue_walls(client, draw_list, cam_x, cam_y, tile):
    """Stone wall faces. Replaces the dungeon cone cliffs inside a keep."""
    plane = (client.dungeon or {}).get("plane") or ""
    floor = _floors().get(plane)
    if floor is None:
        return
    tile = int(tile)
    rows = floor.get("rows") or []
    theme = _theme(plane)
    vis_w = max(1, 900 // max(tile, 1)) + 2
    vis_h = max(1, 640 // max(tile, 1)) + 2
    height = max(tile, int(tile * 1.35))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "#":
                continue
            south = rows[y + 1][x] if y + 1 < len(rows) and x < len(rows[y + 1]) else "#"
            if south == "#":
                continue
            sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
            if not (-1 <= sx <= vis_w and -1 <= sy <= vis_h):
                continue
            left = sx * tile + 1
            width = tile - 2
            bottom = (sy + 1) * tile
            top = bottom - height

            def _draw(left=left, top=top, width=width, height=height, theme=theme):
                face = pygame.Rect(left, top, width, height)
                pygame.draw.rect(client.screen, theme["wall"], face)
                pygame.draw.rect(client.screen, theme["wall_hi"], (left, top, width, max(4, tile // 6)))
                mortar = tuple(max(0, c - 18) for c in theme["wall"])
                for i in range(1, 4):
                    yy = top + i * height // 4
                    pygame.draw.line(client.screen, mortar, (left + 2, yy), (left + width - 2, yy), 1)
                pygame.draw.rect(client.screen, mortar, face, 1)

            draw_list.append((bottom, 1, _draw))


def _hero_spots(floor, rows):
    pads = set()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in "DEUV":
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        pads.add((x + dx, y + dy))
    hero = {}
    for room in floor.get("rooms") or []:
        name = (room.get("name") or "").lower()
        art = _ROOM_PROP.get(name)
        if art is None and name not in _CHANDELIER_ROOMS:
            continue
        x0, y0, x1, y1 = room["rect"]
        if name in _CHANDELIER_ROOMS:
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            if 0 <= cy < len(rows) and 0 <= cx < len(rows[cy]) and rows[cy][cx] != "#":
                hero[(cx, cy)] = "props/prop_chandelier.png"
        if art is None:
            continue
        spot = None
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if not (0 <= y < len(rows) and 0 <= x < len(rows[y])):
                    continue
                if rows[y][x] not in ".x" or (x, y) in pads:
                    continue
                touches_wall = False
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < len(rows) and 0 <= nx < len(rows[ny]) and rows[ny][nx] == "#":
                        touches_wall = True
                if touches_wall and (spot is None or rows[y][x] == "x"):
                    spot = (x, y)
                    if rows[y][x] == "x":
                        break
            if spot and rows[spot[1]][spot[0]] == "x":
                break
        if spot:
            hero[spot] = art
    return hero


_SHELF_KINDS = {"shelf", "bookshelf"}
_CANDLE_KINDS = {"candle", "taper_candle", "candelabra", "torch_sconce", "crystal_sconce"}
_WALL_DECOR = _CANDLE_KINDS | {"white_flower_drape"}


def _room_name(floor, x, y):
    for room in floor.get("rooms") or []:
        x0, y0, x1, y1 = room["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return room.get("name") or ""
    return ""


def _spread(tiles, limit):
    tiles = sorted(tiles)
    if len(tiles) <= limit:
        return tiles
    if limit <= 1:
        return tiles[:1]
    step = (len(tiles) - 1) / (limit - 1)
    return [tiles[int(round(index * step))] for index in range(limit)]


def _spaced(points, gap):
    kept = []
    for point in sorted(points):
        x, y = point
        if all(max(abs(x - ox), abs(y - oy)) >= gap for ox, oy in kept):
            kept.append(point)
    return kept


def _furniture_keep(floor, plane, hide):
    """At most two bookshelves a room. Ground floors keep two of any repeated kind."""
    ground = plane.endswith("_f1")
    groups = {}
    for item in floor.get("furniture") or []:
        x, y = int(item["tile"][0]), int(item["tile"][1])
        if (x, y) in hide:
            continue
        kind = item.get("kind") or ""
        groups.setdefault((_room_name(floor, x, y), kind), []).append((x, y))
    allowed = set()
    for (room, kind), tiles in groups.items():
        limit = None
        if kind in _SHELF_KINDS or kind in _CANDLE_KINDS:
            limit = 2
        elif ground and room and len(tiles) > 2:
            limit = 2
        chosen = tiles if limit is None or len(tiles) <= limit else _spread(tiles, limit)
        allowed.update(chosen)
    return allowed


def _decor_keep(floor):
    """A few candles and drapes along a wall, not a candle on every tile."""
    allowed = set()
    by_room = {}
    outside_candles = []
    outside_drapes = []
    for item in floor.get("decor") or []:
        x, y = int(item["tile"][0]), int(item["tile"][1])
        kind = item.get("kind") or ""
        if kind not in _WALL_DECOR:
            allowed.add((x, y))
            continue
        room = _room_name(floor, x, y)
        if room:
            by_room.setdefault((room, kind), []).append((x, y))
        elif kind == "white_flower_drape":
            outside_drapes.append((x, y))
        else:
            outside_candles.append((x, y))
    for tiles in by_room.values():
        allowed.update(_spread(tiles, 2))
    allowed.update(_spaced(outside_candles, 8))
    allowed.update(_spaced(outside_drapes, 8))
    return allowed


def queue_props(client, draw_list, cam_x, cam_y, tile):
    """Furniture and room props. Feet sort in front of the wall faces (layer 1)."""
    plane = (client.dungeon or {}).get("plane") or ""
    floor = _floors().get(plane)
    if floor is None:
        return
    import castle_room_layouts
    tile = int(tile)
    placed = castle_room_layouts.plan(plane, floor)
    hide = placed["hide"]
    rects = placed["rects"]
    rows = floor.get("rows") or []
    theme = _theme(plane)
    hero = _hero_spots(floor, rows)
    furn_keep = _furniture_keep(floor, plane, hide)
    decor_keep = _decor_keep(floor)
    vis_w = max(1, 900 // max(tile, 1)) + 2
    vis_h = max(1, 640 // max(tile, 1)) + 2

    def _view(x, y):
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        return -6 <= sx <= vis_w + 2 and -2 <= sy <= vis_h + 4, sx, sy

    def _queue_image(image, sx, sy):
        if image is None:
            return
        left = sx * tile + (tile - image.get_width()) // 2
        top = sy * tile + tile - image.get_height()
        foot_y = sy * tile + tile

        def _draw(image=image, left=left, top=top):
            client.screen.blit(image, (left, top))

        draw_list.append((foot_y, 2, _draw))

    def _in_layout(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)

    for item in floor.get("decor") or []:
        x, y = int(item["tile"][0]), int(item["tile"][1])
        if _in_layout(x, y):
            continue
        visible, sx, sy = _view(x, y)
        if not visible:
            continue
        kind = item.get("kind")
        if kind in ("rug", "dance_floor", "marble_pool"):
            continue
        if (x, y) not in decor_keep:
            continue
        path, scale = _lookup(kind)
        if path is not None:
            _queue_image(_image(path, tile, scale), sx, sy)
            continue
        if kind == "white_flower_drape":
            points = (
                (sx * tile + 2, sy * tile - tile // 2),
                (sx * tile + tile // 2, sy * tile + tile - 2),
                (sx * tile + tile - 2, sy * tile - tile // 2),
            )
            foot_y = sy * tile + tile

            def _drape(points=points):
                pygame.draw.polygon(client.screen, (244, 240, 236), points)

            draw_list.append((foot_y, 2, _drape))
        elif kind in ("taper_candle", "candle", "torch_sconce", "crystal_sconce"):
            center = (sx * tile + tile // 2, sy * tile + tile // 3)
            radius = max(3, tile // 6)
            foot_y = sy * tile + tile

            def _candle(center=center, radius=radius):
                pygame.draw.circle(client.screen, (255, 180, 60), center, radius)

            draw_list.append((foot_y, 2, _candle))
    for item in floor.get("furniture") or []:
        x, y = int(item["tile"][0]), int(item["tile"][1])
        if (x, y) in hero or (x, y) in hide or (x, y) not in furn_keep:
            continue
        visible, sx, sy = _view(x, y)
        if not visible:
            continue
        kind = item.get("kind") or ""
        path, scale = _lookup(kind)
        if path is not None:
            _queue_image(_image(path, tile, scale), sx, sy)
            continue
        foot_y = sy * tile + tile

        def _furn(kind=kind, sx=sx, sy=sy):
            _draw_furniture(client.screen, kind, sx, sy, tile, theme)

        draw_list.append((foot_y, 2, _furn))
    for (x, y), relative in hero.items():
        if _in_layout(x, y):
            continue
        visible, sx, sy = _view(x, y)
        if visible:
            _queue_image(_image(_PROPS / relative, tile, 3.2), sx, sy)
    castle_room_layouts.queue(client, draw_list, floor, plane, cam_x, cam_y, tile)


def draw(client, plane, cam_x, cam_y, tile):
    """Paint a v2 floor in its own colours. Returns True when this plane is v2."""
    floor = _floors().get(plane)
    if floor is None:
        return False
    tile = int(tile)
    vis_w = max(1, 900 // max(tile, 1)) + 2
    vis_h = max(1, 640 // max(tile, 1)) + 2
    screen = client.screen
    theme = _theme(plane)
    rows = floor.get("rows") or []
    rugs = {
        (int(item["tile"][0]), int(item["tile"][1]))
        for item in (floor.get("decor") or [])
        if item.get("kind") in ("rug", "dance_floor", "marble_pool")
    }
    import castle_room_layouts
    rugs.update((x, y) for x, y in castle_room_layouts.plan(plane, floor)["rugs"])

    def _onscreen(x, y):
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        return -1 <= sx <= vis_w and -1 <= sy <= vis_h, sx, sy

    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            visible, sx, sy = _onscreen(x, y)
            if not visible:
                continue
            rect = pygame.Rect(sx * tile, sy * tile, tile, tile)
            if ch == "#":
                pygame.draw.rect(screen, theme["wall"], rect)
                pygame.draw.rect(screen, theme["wall_hi"], (rect.x, rect.y, rect.w, max(2, tile // 8)))
                continue
            if (x, y) in rugs:
                col = theme["rug"]
            elif ch == "E":
                col = (120, 168, 90)
            elif ch in "UV":
                col = (70, 78, 96)
            else:
                col = theme["floor"][(x * 3 + y * 5) % 3]
            pygame.draw.rect(screen, col, rect)
            if ch == "D":
                pygame.draw.rect(screen, (230, 190, 60), rect.inflate(-4, -4), 2)

    cluster = stair_tiles(plane)
    if cluster:
        art = _PROPS / _STAIR_ART[_theme_key(plane)]
        cx = sum(tile_x for tile_x, _tile_y in cluster) / len(cluster)
        cy = sum(tile_y for _tile_x, tile_y in cluster) / len(cluster)
        span = max(max(tile_x for tile_x, _tile_y in cluster) - min(tile_x for tile_x, _tile_y in cluster),
                   max(tile_y for _tile_x, tile_y in cluster) - min(tile_y for _tile_x, tile_y in cluster), 2)
        image = _image(art, tile, span + 2.2)
        visible, sx, sy = _onscreen(int(round(cx)), int(round(cy)))
        if image is not None and visible:
            screen.blit(image, (
                sx * tile + (tile - image.get_width()) // 2,
                sy * tile + tile - image.get_height(),
            ))
    font = getattr(client, "font_tiny", None)
    if font:
        for room in floor.get("rooms") or []:
            x0, y0, x1, y1 = room["rect"]
            visible, sx, sy = _onscreen((x0 + x1) // 2, (y0 + y1) // 2)
            if not visible:
                continue
            text = font.render(room.get("name") or "", True, (255, 248, 230))
            screen.blit(text, (sx * tile + tile // 2 - text.get_width() // 2, sy * tile))
    return True
