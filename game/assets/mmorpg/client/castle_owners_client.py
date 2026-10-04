"""Castle Realm seller standees and gate plaques. Drawn only on the realm plane."""
import os

import pygame

import castle_owners

_DIR = os.path.join(os.path.dirname(__file__), "assets", "castle_realm", "owners")
_SPRITES = {}


def _image(rel):
    cached = _SPRITES.get(rel)
    if cached is not None:
        return cached
    path = os.path.join(_DIR, rel)
    if not os.path.isfile(path):
        return None
    image = pygame.image.load(path).convert_alpha()
    _SPRITES[rel] = image
    return image


def _scaled(rel, height):
    image = _image(rel)
    if image is None or height < 4:
        return None
    width = max(1, int(image.get_width() * height / image.get_height()))
    key = (rel, width, height)
    cached = _SPRITES.get(key)
    if cached is None:
        cached = pygame.transform.smoothscale(image, (width, height))
        _SPRITES[key] = cached
    return cached


def seller_at(x, y):
    """Feet tile, or the standee above it. The figure is taller than one tile."""
    x, y = int(x), int(y)
    for seller in castle_owners.sellers():
        sx, sy = (int(v) for v in seller["spawn"]["tile"])
        if abs(x - sx) <= 1 and 0 <= sy - y <= 3:
            return seller
    return None


def queue(client, draw_list, cam_x, cam_y, tile):
    dungeon = client.dungeon or {}
    if dungeon.get("plane") != "realm" or not castle_owners.enabled():
        return
    for seller in castle_owners.sellers():
        sx, sy = seller["spawn"]["tile"]
        _queue_standee(client, draw_list, cam_x, cam_y, tile, seller, int(sx), int(sy))
    for plaque in getattr(client, "castle_plaques", None) or []:
        _queue_plaque(client, draw_list, cam_x, cam_y, tile, plaque)


def _queue_standee(client, draw_list, cam_x, cam_y, tile, seller, x, y):
    vx, vy = client.world_to_view_offset(x, y, cam_x, cam_y)
    if not (-2 <= vx <= 40 and -4 <= vy <= 30):
        return
    cx = vx * tile + tile // 2
    foot = vy * tile + tile
    height = max(8, int(90 * tile / 40))
    sprite = _scaled(seller["sprite"]["1x"], height)

    def _draw(_cx=cx, _foot=foot, _sprite=sprite, _seller=seller, _height=height):
        if _sprite is not None:
            client.screen.blit(_sprite, (_cx - _sprite.get_width() // 2, _foot - _sprite.get_height()))
        name_y = _foot - (_height + 4)
        client.blit_nameplate(_seller["display_name"], _cx, name_y, (255, 220, 160))
        hint = getattr(client, "_hover_hint", None)
        if hint and hint[0] == "seller" and hint[1] == _seller["npc_id"]:
            client.blit_action_hint(hint[2], _cx, name_y - 18, hint[3])

    draw_list.append((foot, 3, _draw))


def _queue_plaque(client, draw_list, cam_x, cam_y, tile, plaque):
    x, y = int(plaque["x"]), int(plaque["y"])
    vx, vy = client.world_to_view_offset(x, y, cam_x, cam_y)
    if not (-2 <= vx <= 40 and -2 <= vy <= 30):
        return
    cx = vx * tile + tile // 2
    cy = vy * tile + tile // 2
    height = max(8, int(48 * tile / 40))
    sprite = _scaled(plaque["sprite"], height)
    title = str(plaque.get("title") or "")
    vacant = bool(plaque.get("vacant"))

    def _draw(_cx=cx, _cy=cy, _sprite=sprite, _title=title, _vacant=vacant):
        if _sprite is None:
            return
        left = _cx - _sprite.get_width() // 2
        top = _cy - _sprite.get_height()
        client.screen.blit(_sprite, (left, top))
        if not _vacant:
            band = pygame.Rect(left + 6, top + _sprite.get_height() // 2, _sprite.get_width() - 12, _sprite.get_height() // 2 - 4)
            pygame.draw.rect(client.screen, (118, 86, 48), band)
            name = client.font_tiny.render(_title[:16], True, (40, 28, 16))
            client.screen.blit(name, (band.centerx - name.get_width() // 2, band.y + 1))

    draw_list.append((cy + tile, 2, _draw))


def draw_dialogue(client):
    castle = (client.dialogue or {}).get("castle") or {}
    box = pygame.Rect(80, 150, 640, 300)
    pygame.draw.rect(client.screen, (25, 25, 35), box)
    pygame.draw.rect(client.screen, (236, 232, 220), box, 2)
    client.dialogue_btn_rects = {}
    name = client.font.render(client.dialogue.get("npc_name") or "Seller", True, (255, 220, 120))
    client.screen.blit(name, (box.x + 12, box.y + 10))
    y = box.y + 40
    max_w = box.w - 24
    for line in client.dialogue.get("lines") or []:
        for wrapped in client._wrap_ui_text(line, client.font_small, max_w):
            if y > box.bottom - 180:
                break
            client.screen.blit(client.font_small.render(wrapped, True, (236, 232, 220)), (box.x + 12, y))
            y += 18
    y += 8
    for option in castle.get("options") or []:
        if y + 26 > box.bottom - 8:
            break
        rect = pygame.Rect(box.x + 12, y, box.w - 24, 24)
        pygame.draw.rect(client.screen, (48, 56, 78), rect, border_radius=4)
        pygame.draw.rect(client.screen, (180, 160, 90), rect, 1, border_radius=4)
        label = option.get("label") or ""
        surf = client.font_tiny.render(label, True, (236, 232, 220))
        client.screen.blit(surf, (rect.x + 8, rect.centery - surf.get_height() // 2))
        client.dialogue_btn_rects[option["id"]] = rect
        y += 28
    if not castle.get("options"):
        rect = pygame.Rect(box.right - 90, box.bottom - 32, 76, 24)
        pygame.draw.rect(client.screen, (60, 60, 70), rect, border_radius=4)
        close = client.font_tiny.render("Close", True, (236, 232, 220))
        client.screen.blit(close, (rect.centerx - close.get_width() // 2, rect.centery - close.get_height() // 2))
        client.dialogue_btn_rects["close"] = rect
    client._castle_dialogue_box = box


def click_dialogue(client, mx, my):
    box = getattr(client, "_castle_dialogue_box", None)
    if box is None or not box.collidepoint(mx, my):
        client.dialogue = None
        return
    castle = (client.dialogue or {}).get("castle") or {}
    for option_id, rect in (client.dialogue_btn_rects or {}).items():
        if not rect.collidepoint(mx, my):
            continue
        if option_id == "close":
            client.dialogue = None
            return
        client.net.send(
            "CASTLE_OPTION",
            npc_id=client.dialogue.get("npc_id"),
            node=castle.get("node"),
            option_id=option_id,
        )
        return
