"""Three lines for a character that was just created.

The comic explains the kingdom. This explains the first clicks.
"""
import time

import pygame

LINES = (
    "Click the ground to walk. The arrow keys step one tile.",
    "Elder Miriam is in the northwest cottage. Click her, then press A for Rat Problem.",
    "Press H for the full control list. R eats. Space attacks the nearest monster.",
)


def start(client):
    if not getattr(client, "arrival_guide", False):
        return
    client.arrival_guide = False
    client.guide_until = time.time() + 16.0
    for line in LINES:
        client.add_chat(line, color=(255, 220, 150), highlight=True)


def draw(client):
    if time.time() >= float(getattr(client, "guide_until", 0) or 0):
        return
    screen = client.screen
    box = pygame.Rect(16, 16, 520, 78)
    pygame.draw.rect(screen, (18, 16, 14), box)
    pygame.draw.rect(screen, (196, 150, 72), box, 2)
    title = client.font.render("First steps", True, (255, 220, 140))
    screen.blit(title, (box.x + 12, box.y + 8))
    body = client.font_small.render(
        "Northwest cottage — Elder Miriam — press A to take the rat quest.",
        True, (236, 224, 196),
    )
    screen.blit(body, (box.x + 12, box.y + 36))
    note = client.font_tiny.render("This fades on its own. Press H if you need the rest.", True, (170, 160, 140))
    screen.blit(note, (box.x + 12, box.y + 56))
