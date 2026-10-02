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


def _surface(relative, tile):
    bucket, base = ("2x", 80) if tile > 40 else ("1x", 40)
    rel = relative.replace("/1x/", f"/{bucket}/") if bucket == "2x" else relative
    key = (rel, int(tile))
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
    plot = estate["estate"]
    _queue_piece(
        client, draw_list, cam_x, cam_y, tile, "estate_grounds",
        int(plot["x0"]), int(plot["y0"]), int(plot["x1"]), int(plot["y1"]),
        inside=False, label=None, clip_x=44,
    )
    for house in list(housing.houses()) + [housing.office()]:
        if not house:
            continue
        fp = house["footprint"]
        label = None
        if not house.get("office"):
            label = owners.get(house["key"]) or (house.get("ownership") or {}).get("vacant_label") or "For Sale"
        elif not _inside(client, house):
            label = "Estate Office"
        _queue_piece(
            client, draw_list, cam_x, cam_y, tile, house["key"],
            int(fp["x0"]), int(fp["y0"]), int(fp["x1"]), int(fp["y1"]),
            inside=_inside(client, house), label=label, screen=screen,
        )


def _queue_piece(client, draw_list, cam_x, cam_y, tile, key, x0, y0, x1, y1, inside, label, clip_x=None, screen=None):
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

    def blit(relative, x=left, y=top, n=tile, clip=clip_x):
        image = _surface(relative, n)
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
        def _plaque(_left=left, _width=(x1 - x0 + 1) * tile, _y=sort_y, _label=label):
            text = client.font_small.render(_label, True, (255, 230, 180))
            screen.blit(text, (_left + _width * 0.5 - text.get_width() / 2, _y - 18))
        draw_list.append((sort_y, 4, _plaque))


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
