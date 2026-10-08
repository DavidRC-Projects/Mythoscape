"""Code-drawn chat and combat bar.

Used when USE_HUD_DRAWN_PANELS is on. Chat, the style row, and the
sword / potion / bones / trash row are pygame rects and text. The
sidebar inventory and profile stay on the navy/gold drawer in hud_v2.
No chat plate, inventory crop, or action-bar plate is blitted.
"""
import pygame

import hud_v2

STYLES = (
    ("attack", "ATK"),
    ("strength", "STR"),
    ("defence", "DEF"),
    ("archery", "RNG"),
    ("eat", "EAT"),
)
TOOLS = (
    ("sword", "Sword"),
    ("potion", "Potion"),
    ("bones", "Bones"),
    ("trash", "Trash"),
)


def _metrics():
    """Chat leaves a 16 px gap, then the combat bar, then 8 px before the sidebar."""
    _map_w, map_h, sidebar_x, _screen_w, screen_h = hud_v2._layout()
    slot_w = 44
    gap = 4
    bar_w = 10 + len(STYLES) * (slot_w + gap)
    room = sidebar_x - 8 - 16 - 8
    if bar_w > room - 240:
        slot_w = max(28, (room - 240 - 10 - len(STYLES) * gap) // len(STYLES))
        bar_w = 10 + len(STYLES) * (slot_w + gap)
    chat_w = max(160, sidebar_x - 8 - 16 - bar_w - 8)
    chat = pygame.Rect(8, map_h, chat_w, screen_h - map_h - 8)
    bar_h = 78
    bar = pygame.Rect(chat.right + 16, screen_h - bar_h - 12, bar_w, bar_h)
    if bar.right + 8 > sidebar_x:
        bar.w = max(1, sidebar_x - 8 - bar.x)
    return chat, bar, slot_w


def draw_world(client):
    """Zone chip and left nav, including one Map button. No plate crops."""
    hud_v2.ensure(client)
    if not client.player:
        return
    hud_v2._draw_zone_chip(client)
    hud_v2._draw_left_nav(client)
    hud_v2._draw_event_banner(client)


def draw_chat(client):
    hud_v2.ensure(client)
    chat, bar, slot_w = _metrics()
    screen = client.screen
    hud_v2._panel(screen, chat, hud_v2.NAVY, hud_v2.GOLD, radius=8, width=2)
    tabs = {}
    x = chat.x + 8
    for channel in hud_v2.CHANNELS:
        label = channel.title()
        surf = hud_v2._text(client, client.font_tiny, label, hud_v2.INK if client.hud_channel == channel else hud_v2.MUTED)
        rect = pygame.Rect(x, chat.y + 6, surf.get_width() + 14, 18)
        if rect.right > chat.right - 8:
            break
        if client.hud_channel == channel:
            hud_v2._panel(screen, rect, hud_v2.NAVY_HI, hud_v2.GOLD, radius=4)
        screen.blit(surf, (rect.x + 7, rect.y + 1))
        tabs[channel] = rect
        x = rect.right + 4
    client.hud_rects["channels"] = tabs

    quick_w = 92
    log_right = chat.right - quick_w - 12
    prev = screen.get_clip()
    log = pygame.Rect(chat.x + 8, chat.y + 28, max(40, log_right - chat.x - 8), chat.h - 58)
    screen.set_clip(log)
    y = log.y
    for line in hud_v2._visible_lines(client)[-max(1, log.h // 16):]:
        color = line.get("color") or hud_v2.CHANNEL_COLOR.get(line.get("channel") or "system", hud_v2.INK)
        surf = hud_v2._text(client, client.font_tiny, str(line.get("text") or ""), color)
        screen.blit(surf, (log.x, y))
        y += 16
    screen.set_clip(prev)

    quick = {}
    qy = chat.y + 28
    for phrase in hud_v2.QUICK:
        rect = pygame.Rect(chat.right - quick_w - 8, qy, quick_w, 18)
        hud_v2._panel(screen, rect, hud_v2.NAVY_CARD, hud_v2.GOLD_DIM, radius=4)
        surf = hud_v2._text(client, client.font_tiny, phrase, hud_v2.INK)
        screen.blit(surf, (rect.x + 6, rect.centery - surf.get_height() // 2))
        quick[phrase] = rect
        qy += 20
    client.hud_rects["quick"] = quick

    input_rect = pygame.Rect(chat.x + 8, chat.bottom - 26, chat.w - 16, 20)
    hud_v2._panel(screen, input_rect, (8, 12, 24), hud_v2.GOLD if client.chat_typing else hud_v2.GOLD_DIM, radius=4)
    prompt = ("> " + client.chat_text) if client.chat_typing else "Press Enter to chat"
    hud_v2._blit(client, client.font_tiny, prompt, (input_rect.x + 6, input_rect.y + 2), hud_v2.INK if client.chat_typing else hud_v2.MUTED)
    client.hud_rects["chat_input"] = input_rect
    _draw_combat_bar(client, bar, slot_w)


def _button(client, rect, label, selected, hover):
    """Chrome, then the label. The highlight is this same rect."""
    fill = hud_v2.NAVY_HI if selected or hover else hud_v2.NAVY_CARD
    border = hud_v2.GOLD if selected or hover else hud_v2.GOLD_DIM
    hud_v2._panel(client.screen, rect, fill, border, radius=6, width=2 if selected or hover else 1)
    color = hud_v2.SAFE_GREEN if label == "EAT" else hud_v2.INK
    surf = hud_v2._text(client, client.font_tiny, label, color)
    client.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))


def _draw_combat_bar(client, bar, slot_w):
    screen = client.screen
    hud_v2._panel(screen, bar, hud_v2.NAVY, hud_v2.GOLD, radius=8, width=2)
    mx, my = pygame.mouse.get_pos()
    style = getattr(client, "combat_style", None)
    tools = {}
    gap = 4
    tool_w = max(28, (bar.w - 10 - gap * (len(TOOLS) - 1)) // len(TOOLS))
    for i, (key, label) in enumerate(TOOLS):
        rect = pygame.Rect(bar.x + 5 + i * (tool_w + gap), bar.y + 6, tool_w, 26)
        _button(client, rect, label, False, rect.collidepoint(mx, my))
        tools[key] = rect
    styles = {}
    for i, (key, label) in enumerate(STYLES):
        rect = pygame.Rect(bar.x + 5 + i * (slot_w + gap), bar.bottom - 40, slot_w, 32)
        if rect.right > bar.right - 4:
            rect.w = max(1, bar.right - 4 - rect.x)
        selected = style == key
        _button(client, rect, label, selected, rect.collidepoint(mx, my))
        styles[key] = rect
    world = client.hud_world_rects
    world["tools"] = tools
    world["actions"] = styles
    world["combat_bar"] = bar


def handle_click(client, mx, my, button):
    hud_v2.ensure(client)
    world = client.hud_world_rects or {}
    for key, rect in (world.get("tools") or {}).items():
        if rect.collidepoint(mx, my):
            _tool_click(client, key)
            return True
    return False


def _tool_click(client, key):
    if key == "sword":
        client.set_combat_style("attack")
        client.add_chat("Combat style: attack.")
        return
    if key == "potion":
        client.net.send("QUICK_CONSUME", kind="health")
        return
    if key == "bones":
        client.add_chat("Select bones in the inventory, then Use.")
        return
    hud_v2._inventory_action(client, "drop")
