"""Unique room props for castle interiors. Sprites and placement only.

Feet land on the south edge of an interior floor tile, and the prop sorts
in front of the wall face it stands against. Flag off leaves this unused.
"""

import json
from pathlib import Path

import pygame

_ROOT = Path(__file__).resolve().parents[2] / "room_layouts"
_ORIGINS = None
_SCALED = {}
_PLANS = {}

_VAULT = {
    "gothic": "vault_gothic_iron",
    "rose": "vault_rose_marble",
    "king": "vault_king_gold",
    "sky": "vault_sky_crystal",
}

_KEEP = {
    "bedroom": ("four_poster", "bed"),
    "dining": ("feast_table", "long_table", "dining_table"),
}


def _origins():
    global _ORIGINS
    if _ORIGINS is None:
        path = _ROOT / "json" / "prop_origins.json"
        with open(path, encoding="utf-8") as handle:
            _ORIGINS = json.load(handle)["props"]
    return _ORIGINS


def _role(plane, name):
    text = (name or "").lower()
    if "bedchamber" in text:
        return "bedroom"
    if "great hall" in text or text in ("feast gallery", "mess hall"):
        return "dining"
    if "chapel" in text:
        return "chapel"
    if "armoury" in text or text == "guard room":
        return "armoury"
    if text in ("main vault", "petal vault", "royal treasury", "crystal vault"):
        return "vault"
    if text == "nursery":
        return "nursery"
    if plane.startswith("rose") and text == "solar":
        return "solar"
    return None


def _pads(rows):
    pads = set()
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char not in "DEUV":
                continue
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    pads.add((x + dx, y + dy))
    return pads


def _inside(rect, x, y):
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def _open(rows, x, y, pads, used):
    if not (0 <= y < len(rows) and 0 <= x < len(rows[y])):
        return False
    if rows[y][x] not in ".x":
        return False
    if (x, y) in pads or (x, y) in used:
        return False
    return True


def _against(rows, x, y, side):
    if side == "north":
        return y > 0 and rows[y - 1][x] == "#"
    if side == "west":
        return x > 0 and rows[y][x - 1] == "#"
    if side == "east":
        return x + 1 < len(rows[y]) and rows[y][x + 1] == "#"
    return False


def _take(rows, rect, pads, used, side, *, avoid_x=None, min_gap=2, prefer_x=True):
    x0, y0, x1, y1 = rect
    best = None
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if not _open(rows, x, y, pads, used):
                continue
            if not _against(rows, x, y, side):
                continue
            if avoid_x is not None and abs(x - avoid_x) < min_gap:
                continue
            center = (x0 + x1) / 2
            on_block = 0 if prefer_x and rows[y][x] == "x" else 1
            score = (on_block, abs(x - center) if side == "north" else y, x)
            if best is None or score < best[0]:
                best = (score, (x, y))
    if best is None:
        return None
    used.add(best[1])
    return best[1]


def _pair(rows, rect, pads, used, y_from, y_to):
    x0, y0, x1, y1 = rect
    cx = (x0 + x1) // 2
    ys = list(range(max(y_from, y0), min(y_to, y1 + 1)))
    if not ys:
        return None, None
    mid = ys[len(ys) // 2]
    for y in sorted(ys, key=lambda row: abs(row - mid)):
        lefts = [x for x in range(x0, cx) if _open(rows, x, y, pads, used)]
        rights = [x for x in range(cx + 1, x1 + 1) if _open(rows, x, y, pads, used)]
        best = None
        for left_x in lefts:
            for right_x in rights:
                if right_x - left_x < 3:
                    continue
                score = (
                    0 if rows[y][left_x] == "x" and rows[y][right_x] == "x" else 1,
                    right_x - left_x,
                    abs(left_x - cx) + abs(right_x - cx),
                )
                if best is None or score < best[0]:
                    best = (score, (left_x, y), (right_x, y))
        if best:
            used.add(best[1])
            used.add(best[2])
            return best[1], best[2]
    return None, None


def _guard_mat(rows, rect, pads, used):
    """Empty 2x2 the vault plan leaves clear. Nothing is placed on it."""
    x0, y0, x1, y1 = rect
    for y in range(y1 - 1, y0 + 1, -1):
        for x in range(x1 - 1, x0 + 1, -1):
            block = [(x + dx, y + dy) for dy in (0, 1) for dx in (0, 1)]
            if all(_open(rows, tx, ty, pads, used) and rows[ty][tx] == "." for tx, ty in block):
                used.update(block)
                return


def _add(props, key, tile):
    if tile is not None:
        props.append((key, tile[0], tile[1]))


def _layout(rows, rect, pads, role, plane, used):
    props = []
    rugs = []
    x0, y0, x1, y1 = rect
    if role == "bedroom":
        portrait = _take(rows, rect, pads, used, "north", prefer_x=False)
        mirror = _take(rows, rect, pads, used, "north", avoid_x=portrait[0] if portrait else None, min_gap=3)
        press = _take(rows, rect, pads, used, "west")
        wash = None
        if press:
            for y in range(press[1] + 2, y1 + 1):
                if _open(rows, press[0], y, pads, used) and _against(rows, press[0], y, "west"):
                    wash = (press[0], y)
                    used.add(wash)
                    break
        _add(props, "prop_portrait", portrait)
        _add(props, "prop_cheval_mirror", mirror)
        _add(props, "prop_linen_press", press)
        _add(props, "prop_washstand", wash)
    elif role == "dining":
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        cauldron = None
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if _open(rows, x, y, pads, used) and _against(rows, x, y, "north") and _against(rows, x, y, "west"):
                    cauldron = (x, y)
                    used.add(cauldron)
                    break
            if cauldron:
                break
        pair = _pair(rows, rect, pads, used, max(y0 + 1, cy - 1), min(y1, cy + 3))
        rack = _take(rows, rect, pads, used, "west")
        cart = None
        if rack:
            for y in range(rack[1] + 2, y1 + 1):
                if _open(rows, rack[0], y, pads, used) and _against(rows, rack[0], y, "west"):
                    cart = (rack[0], y)
                    used.add(cart)
                    break
            if cart is None:
                cart = _take(rows, rect, pads, used, "east")
        portrait = _take(rows, rect, pads, used, "north", prefer_x=False) or _take(rows, rect, pads, used, "east", prefer_x=False)
        if pair and pair[0]:
            _add(props, "prop_dining_chair", pair[0])
            _add(props, "prop_dining_chair", pair[1])
        _add(props, "prop_wine_rack", rack)
        _add(props, "prop_serving_cart", cart)
        _add(props, "prop_cauldron", cauldron)
        _add(props, "prop_portrait", portrait)
    elif role == "chapel":
        altar = _take(rows, rect, pads, used, "north")
        lectern = _take(rows, rect, pads, used, "north", avoid_x=altar[0] if altar else None, min_gap=3)
        if lectern and altar and lectern[0] > altar[0]:
            used.discard(lectern)
            lectern = None
            for x in range((altar[0] - 3), x0 - 1, -1):
                y = altar[1]
                if _open(rows, x, y, pads, used) and _against(rows, x, y, "north"):
                    lectern = (x, y)
                    used.add(lectern)
                    break
        pair = _pair(rows, rect, pads, used, y0 + 1, y1)
        portrait = _take(rows, rect, pads, used, "west", prefer_x=False) or _take(rows, rect, pads, used, "east", prefer_x=False)
        _add(props, "prop_chapel_altar", altar)
        _add(props, "prop_lectern", lectern)
        if pair and pair[0]:
            _add(props, "prop_prayer_kneeler", pair[0])
            _add(props, "prop_prayer_kneeler", pair[1])
        _add(props, "prop_portrait", portrait)
        if pair and pair[0]:
            aisle_y = pair[0][1]
            cx = (x0 + x1) // 2
            for y in range(aisle_y + 2, y1):
                if _open(rows, cx, y, pads, set()) and rows[y][cx] == ".":
                    rugs.append((cx, y))
    elif role == "armoury":
        spear = _take(rows, rect, pads, used, "west")
        dummy = _take(rows, rect, pads, used, "north")
        shield = _take(rows, rect, pads, used, "north", avoid_x=dummy[0] if dummy else None, min_gap=2, prefer_x=False)
        _add(props, "prop_spear_stand", spear)
        _add(props, "prop_arming_dummy", dummy)
        _add(props, "prop_heater_shield", shield)
        if dummy and _open(rows, dummy[0], dummy[1] + 2, pads, set()):
            rugs.append((dummy[0], dummy[1] + 2))
    elif role == "vault":
        _guard_mat(rows, rect, pads, used)
        theme = "gothic"
        if plane.startswith("rose"):
            theme = "rose"
        elif plane.startswith("king"):
            theme = "king"
        elif plane.startswith("sky"):
            theme = "sky"
        door = _take(rows, rect, pads, used, "north")
        rack = _take(rows, rect, pads, used, "west")
        if rack is None and door is not None:
            rack = _take(rows, rect, pads, used, "north", avoid_x=door[0], min_gap=3)
        if rack is None:
            rack = _take(rows, rect, pads, used, "east")
        _add(props, _VAULT[theme], door)
        _add(props, "prop_relic_rack", rack)
    elif role == "nursery":
        _add(props, "prop_cradle", _take(rows, rect, pads, used, "west") or _take(rows, rect, pads, used, "north"))
    elif role == "solar":
        _add(props, "prop_spinning_wheel", _take(rows, rect, pads, used, "west") or _take(rows, rect, pads, used, "north"))
    return props, rugs


def plan(plane, floor):
    """Props to draw, furniture tiles to hide, and rug tiles. Cached per plane."""
    cached = _PLANS.get(plane)
    if cached is not None:
        return cached
    rows = floor.get("rows") or []
    pads = _pads(rows)
    props = []
    rugs = []
    rects = []
    kept = set()
    for room in floor.get("rooms") or []:
        role = _role(plane, room.get("name"))
        if role is None:
            continue
        rect = tuple(int(v) for v in room["rect"])
        rects.append(rect)
        used = set()
        keep_kinds = _KEEP.get(role)
        if keep_kinds:
            kept_one = False
            for item in floor.get("furniture") or []:
                x, y = int(item["tile"][0]), int(item["tile"][1])
                if not _inside(rect, x, y) or item.get("kind") not in keep_kinds or kept_one:
                    continue
                kept.add((x, y))
                used.add((x, y))
                kept_one = True
                if role == "bedroom" and y + 1 <= rect[3] and rows[y + 1][x] in ".x":
                    rugs.append((x, y + 1))
                    used.add((x, y + 1))
                elif role == "dining":
                    rugs.append((x, y))
        room_props, room_rugs = _layout(rows, rect, pads, role, plane, used)
        props.extend(room_props)
        rugs.extend(room_rugs)
    hide = set()
    for item in floor.get("furniture") or []:
        x, y = int(item["tile"][0]), int(item["tile"][1])
        if (x, y) in kept:
            continue
        if any(_inside(rect, x, y) for rect in rects):
            hide.add((x, y))
    result = {"props": props, "hide": hide, "rects": rects, "rugs": rugs}
    _PLANS[plane] = result
    return result


def _height_tiles(key):
    """How tall the sprite should read, in floor tiles. A person is about two."""
    if key.startswith("vault_"):
        return 2.6
    if key in ("prop_relic_rack", "prop_wine_rack", "prop_linen_press", "prop_chapel_altar"):
        return 2.1
    if key in ("prop_cheval_mirror", "prop_spinning_wheel", "prop_spear_stand", "prop_arming_dummy", "prop_lectern"):
        return 1.8
    if key == "prop_portrait":
        return 1.45
    if key == "prop_heater_shield":
        return 1.05
    return 1.35


def _image(key, tile):
    cache_key = (key, int(tile))
    if cache_key in _SCALED:
        return _SCALED[cache_key]
    spec = _origins().get(key)
    if spec is None:
        _SCALED[cache_key] = None
        return None
    path = _ROOT / spec["file"]
    if not path.is_file():
        _SCALED[cache_key] = None
        return None
    image = pygame.image.load(str(path)).convert_alpha()
    scale = (float(tile) * _height_tiles(key)) / max(image.get_height(), 1)
    size = (
        max(1, int(round(image.get_width() * scale))),
        max(1, int(round(image.get_height() * scale))),
    )
    image = pygame.transform.smoothscale(image, size)
    _SCALED[cache_key] = (image, spec["origin_px"], scale)
    return _SCALED[cache_key]


def queue(client, draw_list, floor, plane, cam_x, cam_y, tile):
    """Queue layout sprites. sort_y is the south edge of the anchor tile, layer 2."""
    tile = int(tile)
    placed = plan(plane, floor)
    vis_w = max(1, 900 // max(tile, 1)) + 2
    vis_h = max(1, 640 // max(tile, 1)) + 2
    for key, x, y in placed["props"]:
        packed = _image(key, tile)
        if packed is None:
            continue
        sx, sy = client.world_to_view_offset(x, y, cam_x, cam_y)
        if not (-6 <= sx <= vis_w + 2 and -2 <= sy <= vis_h + 4):
            continue
        image, origin, scale = packed
        ox, oy = origin
        foot_x = sx * tile + tile // 2
        foot_y = sy * tile + tile
        left = int(round(foot_x - ox * scale))
        top = int(round(foot_y - oy * scale))

        def _draw(image=image, left=left, top=top):
            client.screen.blit(image, (left, top))

        draw_list.append((foot_y, 2, _draw))
