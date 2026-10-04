"""King's Row estate sprites. Ground, body, and cutaway, plus the name plaque."""
from __future__ import annotations

import json
import os

import pygame

import feature_flags
import housing

_DIR = os.path.join(os.path.dirname(__file__), "assets", "housing")
_CACHE = {}


def _meta(key):
    path = os.path.join(_DIR, "sprites", "1x", key, "meta.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _floor_keys(data, width, height):
    """The big flat interior fill. Doors, posts, and the step are smaller colors."""
    buckets = {}
    for y in range(0, height, 3):
        row = y * width * 4
        for x in range(0, width, 3):
            i = row + x * 4
            if data[i + 3] < 200:
                continue
            key = (data[i] // 16 * 16, data[i + 1] // 16 * 16, data[i + 2] // 16 * 16)
            buckets[key] = buckets.get(key, 0) + 1
    if not buckets:
        return []
    total = sum(buckets.values())
    keys = [key for key, count in buckets.items() if count >= total * 0.08]
    return keys or [max(buckets, key=buckets.get)]


def _is_floor_fill(r, g, b, a, keys):
    if a < 200:
        return False
    for kr, kg, kb in keys:
        if abs(r - kr) <= 18 and abs(g - kg) <= 18 and abs(b - kb) <= 18:
            return True
    return False


def _decorate_floor(image, accent, style):
    """Boards, a border, and a rug on the bare interior fill."""
    width, height = image.get_size()
    data = bytearray(pygame.image.tobytes(image, "RGBA"))
    keys = _floor_keys(data, width, height)
    if not keys:
        return image
    min_x, min_y, max_x, max_y = width, height, 0, 0
    found = False
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            i = row + x * 4
            if not _is_floor_fill(data[i], data[i + 1], data[i + 2], data[i + 3], keys):
                continue
            found = True
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
    if not found:
        return image
    floor_w = max_x - min_x + 1
    floor_h = max_y - min_y + 1
    rug_w = max(8, int(floor_w * (0.34 if style else 0.48)))
    rug_h = max(8, int(floor_h * (0.28 if style else 0.40)))
    rug_x = (min_x + max_x) // 2 - rug_w // 2
    rug_y = (min_y + max_y) // 2 - rug_h // 2 - int(floor_h * 0.08)
    accent = accent or (150, 118, 54)
    border = 5 if style < 2 else 3

    def clamp(value):
        return 0 if value < 0 else 255 if value > 255 else value

    for y in range(min_y, max_y + 1):
        row = y * width * 4
        for x in range(min_x, max_x + 1):
            i = row + x * 4
            if not _is_floor_fill(data[i], data[i + 1], data[i + 2], data[i + 3], keys):
                continue
            if style == 1:
                base = (176, 132, 108)
                pitch = 14
                seam = (x % pitch) < 1
                delta = -24 if seam else (8 if (x // pitch) % 2 else -5)
            elif style >= 2:
                base = (164, 136, 98)
                pitch = 8
                seam = (y % pitch) < 1
                delta = -20 if seam else (4 if (y // pitch) % 2 else -6)
            else:
                base = (188, 150, 98)
                pitch = 11
                seam = (y % pitch) < 1
                joint = (x % 34) == ((y // pitch) * 13) % 34
                delta = -30 if seam or joint else (12 if (y // pitch) % 2 else -6)
            red, green, blue = base[0] + delta, base[1] + delta, base[2] + delta // 2
            on_edge = (
                x < min_x + border or x > max_x - border
                or y < min_y + border or y > max_y - border
            )
            if on_edge:
                red, green, blue = red - 36, green - 28, blue - 18
            if rug_x <= x < rug_x + rug_w and rug_y <= y < rug_y + rug_h:
                fringe = (
                    x < rug_x + 2 or x >= rug_x + rug_w - 2
                    or y < rug_y + 2 or y >= rug_y + rug_h - 2
                )
                weave = 10 if ((x // 5) + (y // 5)) % 2 == 0 else -8
                if fringe:
                    red, green, blue = accent[0] - 40, accent[1] - 36, accent[2] - 28
                else:
                    red = accent[0] + weave
                    green = accent[1] + weave // 2
                    blue = accent[2] + weave // 3
            data[i] = clamp(red)
            data[i + 1] = clamp(green)
            data[i + 2] = clamp(blue)
    return pygame.image.frombytes(bytes(data), (width, height), "RGBA").convert_alpha()


def _surface(relative, tile, style=0):
    bucket, base = ("2x", 80) if tile > 40 else ("1x", 40)
    rel = relative.replace("/1x/", f"/{bucket}/") if bucket == "2x" else relative
    key = (rel, int(tile), int(style))
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(_DIR, rel)
    if not os.path.isfile(path) and bucket == "2x":
        path = os.path.join(_DIR, relative)
        base = 40
    if not os.path.isfile(path):
        _CACHE[key] = None
        return None
    image = pygame.image.load(path).convert_alpha()
    if rel.endswith("cutaway.png"):
        key_name = rel.split("/")[-2]
        house = None
        try:
            house = housing.house_by_key(key_name)
        except Exception:
            house = None
        accent = _RUG.get((house or {}).get("accent") or "", (150, 118, 54))
        image = _decorate_floor(image, accent, style)
    size = (
        max(1, round(image.get_width() * tile / base)),
        max(1, round(image.get_height() * tile / base)),
    )
    if size != image.get_size():
        image = pygame.transform.smoothscale(image, size)
    _CACHE[key] = image
    return image


def _inside(client, house):
    if not client.player:
        return False
    px, py = client.player_xy()
    fl = house.get("floor") or {}
    if fl.get("floor_x0", 1) <= px <= fl.get("floor_x1", 0) and fl.get("floor_y0", 1) <= py <= fl.get("floor_y1", 0):
        return True
    door = house.get("door") or {}
    return [px, py] in (door.get("doorway_path_tiles") or [])


def queue(client, draw_list, cam_x, cam_y, tile):
    if not feature_flags.USE_PLAYER_HOUSING or client.dungeon:
        return
    estate = housing.load()
    screen = client.screen
    owners = getattr(client, "housing_owners", {}) or {}
    for house in list(housing.houses()) + [housing.office()]:
        if not house:
            continue
        fp = house["footprint"]
        label = None
        if not house.get("office"):
            label = owners.get(house["key"]) or (house.get("ownership") or {}).get("vacant_label") or "For Sale"
        elif not _inside(client, house):
            label = "ESTATE AGENT"
        _queue_piece(
            client, draw_list, cam_x, cam_y, tile, house["key"],
            int(fp["x0"]), int(fp["y0"]), int(fp["x1"]), int(fp["y1"]),
            inside=_inside(client, house), label=label, screen=screen,
            sign=bool(house.get("office")),
        )
        _queue_interior(client, draw_list, cam_x, cam_y, tile, house, _inside(client, house), screen)


def _queue_piece(client, draw_list, cam_x, cam_y, tile, key, x0, y0, x1, y1, inside, label, clip_x=None, screen=None, sign=False):
    meta = _meta(key)
    if not meta:
        return
    screen = screen or client.screen
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    if tile > 40 and meta.get("origin_2x"):
        ox, oy = meta["origin_2x"]
        base = 80
    else:
        ox, oy = meta.get("origin_px") or (0, 0)
        base = 40
    scale = tile / float(base)
    left, top = sx * tile - ox * scale, sy * tile - oy * scale
    layers = meta.get("layers") or {}
    ground = layers.get("ground")
    body_name = "cutaway" if inside and layers.get("cutaway") else "body"
    body = layers.get(body_name)
    _sx1, south = client.world_to_view_offset(x0, y1, cam_x, cam_y)
    sort_y = -(10 ** 8) if inside else south * tile + tile
    floor_style = int((client.player or {}).get("house_level") or 0) if inside else 0

    def blit(relative, x=left, y=top, n=tile, clip=clip_x, floor_style=floor_style):
        style = floor_style if relative and str(relative).endswith("cutaway.png") else 0
        image = _surface(relative, n, style)
        if image is None:
            return
        previous = screen.get_clip()
        if clip is not None:
            cx, _cy = client.world_to_view_offset(clip, y0, cam_x, cam_y)
            screen.set_clip(pygame.Rect(0, 0, max(0, cx * n), screen.get_height()))
        screen.blit(image, (x, y))
        screen.set_clip(previous)

    if ground:
        draw_list.append((-10 ** 9, 0, lambda g=ground: blit(g)))
    if body:
        draw_list.append((sort_y, 0, lambda g=body: blit(g)))
    if label and not inside:
        def _plaque(_left=left, _width=(x1 - x0 + 1) * tile, _y=sort_y, _label=label, _sign=sign, _x0=x0, _y0=y0):
            font = client.font if _sign else client.font_small
            text = font.render(_label, True, (255, 236, 170) if _sign else (255, 230, 180))
            if _sign:
                _sx, north = client.world_to_view_offset(_x0, _y0, cam_x, cam_y)
                px = _sx * tile + _width * 0.5 - text.get_width() / 2
                py = north * tile - text.get_height() - 8
                pad = pygame.Rect(px - 8, py - 4, text.get_width() + 16, text.get_height() + 8)
                pygame.draw.rect(screen, (28, 22, 12), pad, border_radius=4)
                pygame.draw.rect(screen, (212, 175, 70), pad, 2, border_radius=4)
                screen.blit(text, (px, py))
            else:
                screen.blit(text, (_left + _width * 0.5 - text.get_width() / 2, _y - 18))
        draw_list.append(((10 ** 8) if sign else sort_y, 4, _plaque))


_PROPS = os.path.join(os.path.dirname(__file__), "..", "..", "interior_props", "props")
_PROP_CACHE = {}
_RUG = {
    "green": (72, 108, 74),
    "yellow": (148, 118, 58),
    "flower_r": (132, 72, 78),
    "beam": (118, 86, 54),
    "blue": (64, 92, 128),
    "red": (128, 64, 58),
    "gold": (150, 118, 54),
    "teal": (58, 112, 108),
}
_KITS = {
    "office": ("prop_writing_desk.png", "prop_bookshelf.png", "prop_tapestry.png"),
    "ground": ("prop_map_table.png", "prop_banquet_bench.png", "prop_bookshelf.png"),
    "upper": ("prop_canopy_bed.png", "prop_sideboard.png", "prop_bookshelf.png"),
    "top": ("prop_writing_desk.png", "prop_bookshelf.png", "prop_tapestry.png"),
}


def _fit(filename, tile, tiles_tall):
    key = (filename, int(tile), tiles_tall)
    if key in _PROP_CACHE:
        return _PROP_CACHE[key]
    path = os.path.join(_PROPS, filename)
    if not os.path.isfile(path):
        _PROP_CACHE[key] = None
        return None
    image = pygame.image.load(path).convert_alpha()
    bounds = image.get_bounding_rect(min_alpha=8)
    if bounds.w > 0 and bounds.h > 0:
        image = image.subsurface(bounds).copy()
    height = max(8, int(tile * tiles_tall))
    width = max(8, int(height * image.get_width() / max(image.get_height(), 1)))
    image = pygame.transform.smoothscale(image, (width, height))
    _PROP_CACHE[key] = image
    return image


def _spread(spots, count):
    spots = sorted(spots)
    if not spots or count <= 0:
        return []
    if len(spots) <= count:
        return spots
    if count == 1:
        return [spots[len(spots) // 2]]
    step = (len(spots) - 1) / (count - 1)
    return [spots[int(round(index * step))] for index in range(count)]


def _queue_interior(client, draw_list, cam_x, cam_y, tile, house, inside, screen):
    """A few pieces of furniture on the floor the player is standing in."""
    if not inside or not client.player:
        return
    fl = house["floor"]
    x0, y0 = int(fl["floor_x0"]), int(fl["floor_y0"])
    x1, y1 = int(fl["floor_x1"]), int(fl["floor_y1"])
    width, depth = x1 - x0 + 1, y1 - y0 + 1
    level = int(client.player.get("house_level") or 0)
    plans = house.get("floor_plans") or []
    if level >= len(plans):
        level = 0
    plan = plans[level] if plans else {}
    reserved = set()
    door = house.get("door") or {}
    enter = door.get("enter") or []
    if len(enter) == 2:
        reserved.add((int(enter[0]) - x0, int(enter[1]) - y0))
    for key in ("stairs_up", "stairs_down"):
        stair = plan.get(key)
        if stair:
            reserved.add((int(stair[0]), int(stair[1])))
    walkable = plan.get("walkable") or []
    north = []
    for ly in range(depth):
        for lx in range(width):
            if (lx, ly) in reserved:
                continue
            if ly < len(walkable) and lx < len(walkable[ly]) and not walkable[ly][lx]:
                continue
            if ly == 0:
                north.append((lx, ly))
    if house.get("office"):
        kit = _KITS["office"]
    elif level <= 0:
        kit = _KITS["ground"]
    elif level >= 2:
        kit = _KITS["top"]
    else:
        kit = _KITS["upper"]
    cap = 2 if width <= 6 else 3
    spots = _spread(north, min(cap, len(kit)))
    rug = _RUG.get(house.get("accent") or "", (110, 78, 52))
    for lx, ly in spots[:1]:
        sx, sy = client.world_to_view_offset(x0 + lx, y0 + ly, cam_x, cam_y)
        rect = pygame.Rect(sx * tile + 2, sy * tile + tile // 5, tile - 4, tile - tile // 4)
        foot = sy * tile + tile // 2

        def _rug(rect=rect, rug=rug):
            pygame.draw.rect(screen, rug, rect)
            pygame.draw.rect(screen, tuple(max(0, c - 30) for c in rug), rect, 1)

        draw_list.append((foot, 0, _rug))
    tall = {"prop_canopy_bed.png": 1.35, "prop_bookshelf.png": 1.45, "prop_tapestry.png": 1.3}
    for filename, (lx, ly) in zip(kit, spots):
        image = _fit(filename, tile, tall.get(filename, 1.15))
        if image is None:
            continue
        sx, sy = client.world_to_view_offset(x0 + lx, y0 + ly, cam_x, cam_y)
        left = sx * tile + (tile - image.get_width()) // 2
        top = sy * tile + tile - image.get_height()
        foot = sy * tile + tile

        def _prop(image=image, left=left, top=top):
            screen.blit(image, (left, top))

        draw_list.append((foot, 2, _prop))
    for key, word in (("stairs_up", "Up"), ("stairs_down", "Down")):
        stair = plan.get(key)
        if not stair:
            continue
        sx, sy = client.world_to_view_offset(x0 + int(stair[0]), y0 + int(stair[1]), cam_x, cam_y)
        foot = sy * tile + tile

        def _stair(sx=sx, sy=sy, word=word):
            for step in range(3):
                bar = pygame.Rect(sx * tile + 4, sy * tile + tile // 2 + step * max(3, tile // 8), tile - 8, max(3, tile // 10))
                pygame.draw.rect(screen, (92, 78, 58), bar)
                pygame.draw.rect(screen, (180, 150, 80), bar, 1)
            text = client.font_tiny.render(word, True, (255, 230, 170))
            screen.blit(text, (sx * tile + (tile - text.get_width()) // 2, sy * tile + 2))

        draw_list.append((foot, 2, _stair))
    floor_name = plan.get("name") or ("Office" if house.get("office") else "")
    if floor_name:
        sx, sy = client.world_to_view_offset(x0 + width // 2, y0, cam_x, cam_y)
        title = f"{house.get('name') or ''}  ·  {floor_name}"

        def _name(sx=sx, sy=sy, title=title):
            text = client.font_tiny.render(title, True, (255, 244, 220))
            screen.blit(text, (sx * tile - text.get_width() // 2, sy * tile - text.get_height() - 2))

        draw_list.append((sy * tile, 3, _name))


def draw_panel(client):
    if not getattr(client, "housing_open", False):
        return
    box = pygame.Rect(80, 70, 420, 500)
    pygame.draw.rect(client.screen, (24, 26, 34), box)
    pygame.draw.rect(client.screen, (212, 175, 90), box, 2)
    title = client.font.render("King's Row", True, (255, 220, 140))
    client.screen.blit(title, (box.x + 16, box.y + 12))
    bank = getattr(client, "housing_bank", 0)
    sub = client.font_small.render(f"Bank: {bank:,} gold", True, (210, 200, 170))
    client.screen.blit(sub, (box.x + 16, box.y + 40))
    client.housing_rects = []
    y = box.y + 68
    for lot in client.housing_lots:
        name = client.font_small.render(lot["name"], True, (255, 245, 220))
        client.screen.blit(name, (box.x + 16, y))
        detail = "For sale" if lot.get("vacant") else f"Owned by {lot.get('owner')}"
        price = client.font_tiny.render(f"{int(lot['price']):,}   ·   {detail}", True, (180, 170, 150))
        client.screen.blit(price, (box.x + 16, y + 16))
        if lot.get("vacant"):
            rect = pygame.Rect(box.right - 78, y + 4, 62, 24)
            pygame.draw.rect(client.screen, (90, 70, 30), rect, border_radius=4)
            label = client.font_tiny.render("Buy", True, (255, 230, 170))
            client.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.y + 5))
            client.housing_rects.append((rect, lot["key"]))
        y += 40
    close = pygame.Rect(box.right - 78, box.bottom - 32, 62, 22)
    pygame.draw.rect(client.screen, (60, 60, 70), close, border_radius=4)
    close_label = client.font_tiny.render("Close", True, (230, 230, 230))
    client.screen.blit(close_label, (close.centerx - close_label.get_width() // 2, close.y + 4))
    client.housing_rects.append((close, None))


def panel_click(client, mx, my):
    if not getattr(client, "housing_open", False):
        return False
    for rect, key in getattr(client, "housing_rects", []):
        if rect.collidepoint(mx, my):
            if key:
                client.net.send("HOUSING_BUY", key=key)
            else:
                client.housing_open = False
            return True
    client.housing_open = False
    return True
