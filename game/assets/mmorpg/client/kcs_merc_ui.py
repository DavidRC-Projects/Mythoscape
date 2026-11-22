"""'How many mercenaries?' prompt before the siege (David t648u).

Shown in the siege when the server's status carries a `mercs` block (server flag
USE_KCS_MERCENARIES) and this player has not answered for this war. The number is capped by the
server: soldiers you own (Barracks roster) and the side's fighter cap. Sends KCS_MERCS_BRING.
"""
from __future__ import annotations

import pygame

_UI = {"war": None, "pick": None, "rects": {}, "sent": None}


def _info(view):
    st = view.status or {}
    info = st.get("mercs")
    if not isinstance(info, dict) or st.get("status") not in ("registration", "locking", "active"):
        return None
    if info.get("chosen") is not None or _UI["sent"] == st.get("war_id") or not info.get("can_choose"):
        return None
    return info


def _banner(client, view) -> None:
    """One line for guild members who do not choose (and for the chooser once chosen), before the battle."""
    st = view.status or {}
    info = st.get("mercs")
    if not isinstance(info, dict) or not info.get("in_clan"):
        return
    if not (st.get("status") in ("registration", "locking") or st.get("preparing")):
        return
    n = info.get("chosen")
    if n is None:
        if info.get("can_choose"):
            return                      # the chooser sees the prompt instead
        text = "Waiting for your guild leader to choose mercenaries."
    elif int(n) <= 0:
        text = "Your guild is fighting without mercenaries."
    else:
        text = f"Your guild is bringing {int(n)} mercenar{'y' if int(n) == 1 else 'ies'}."
    font = pygame.font.Font(None, 22)
    img = font.render(text, True, (246, 222, 150))
    sw = client.screen.get_width()
    r = img.get_rect(midtop=(sw // 2, 58)).inflate(24, 10)
    plate = pygame.Surface(r.size, pygame.SRCALPHA)
    plate.fill((14, 10, 8, 190))
    client.screen.blit(plate, r)
    pygame.draw.rect(client.screen, (170, 140, 70), r, 1, border_radius=6)
    client.screen.blit(img, img.get_rect(center=r.center))


def draw(client, view) -> None:
    info = _info(view)
    _UI["rects"] = {}
    if info is None:
        _banner(client, view)
        return
    war = (view.status or {}).get("war_id")
    cap = int(info.get("cap") or 0)
    if _UI["war"] != war or _UI["pick"] is None:
        _UI.update(war=war, pick=cap)
    _UI["pick"] = max(0, min(cap, int(_UI["pick"])))
    screen = client.screen
    sw, sh = screen.get_size()
    box = pygame.Rect(0, 0, 420, 190)
    box.center = (sw // 2, int(sh * .42))
    pygame.draw.rect(screen, (18, 14, 10), box, border_radius=10)
    pygame.draw.rect(screen, (212, 175, 90), box, 2, border_radius=10)
    big = pygame.font.Font(None, 30)
    small = pygame.font.Font(None, 20)
    screen.blit(big.render("Bring guild mercenaries?", True, (246, 222, 150)), (box.x + 18, box.y + 14))
    owned = int(info.get("owned") or 0)
    if owned:
        line = f"Your guild has {owned} recruits. Up to {cap} can fight for your side."
    else:
        line = "Your guild has no recruits. Hire some with /guild hire."
    screen.blit(small.render(line, True, (230, 214, 180)), (box.x + 18, box.y + 48))
    # number picker
    cy = box.y + 98
    minus = pygame.Rect(box.centerx - 90, cy - 18, 36, 36)
    plus = pygame.Rect(box.centerx + 54, cy - 18, 36, 36)
    for r, s in ((minus, "-"), (plus, "+")):
        pygame.draw.rect(screen, (60, 46, 30), r, border_radius=6)
        pygame.draw.rect(screen, (212, 175, 90), r, 1, border_radius=6)
        g = big.render(s, True, (246, 222, 150))
        screen.blit(g, g.get_rect(center=r.center))
    n = big.render(str(_UI["pick"]), True, (255, 255, 255))
    screen.blit(n, n.get_rect(center=(box.centerx, cy)))
    bring = pygame.Rect(box.x + 40, box.bottom - 50, 160, 34)
    none = pygame.Rect(box.right - 200, box.bottom - 50, 160, 34)
    for r, s, c in ((bring, f"Bring {_UI['pick']}", (52, 96, 52)), (none, "No mercenaries", (70, 40, 34))):
        pygame.draw.rect(screen, c, r, border_radius=8)
        pygame.draw.rect(screen, (212, 175, 90), r, 1, border_radius=8)
        g = small.render(s, True, (246, 236, 210))
        screen.blit(g, g.get_rect(center=r.center))
    _UI["rects"] = {"minus": minus, "plus": plus, "bring": bring, "none": none, "box": box}
    try:
        view.ui_regions.append(box)
    except Exception:
        pass


def _send(client, view, count):
    net = getattr(client, "net", None)
    if net is not None:
        net.send("KCS_MERCS_BRING", count=int(count))
    _UI["sent"] = (view.status or {}).get("war_id")


def click(client, view, pos) -> bool:
    rects = _UI.get("rects") or {}
    if not rects or _info(view) is None:
        return False
    cap = int((_info(view) or {}).get("cap") or 0)
    if rects["minus"].collidepoint(pos):
        _UI["pick"] = max(0, int(_UI["pick"] or 0) - 1)
    elif rects["plus"].collidepoint(pos):
        _UI["pick"] = min(cap, int(_UI["pick"] or 0) + 1)
    elif rects["bring"].collidepoint(pos):
        _send(client, view, _UI["pick"] or 0)
    elif rects["none"].collidepoint(pos):
        _send(client, view, 0)
    elif not rects["box"].collidepoint(pos):
        return False
    return True


def key(client, view, event) -> bool:
    if not _UI.get("rects") or _info(view) is None:
        return False
    cap = int((_info(view) or {}).get("cap") or 0)
    if event.key in (pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
        _UI["pick"] = max(0, int(_UI["pick"] or 0) - 1)
    elif event.key in (pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
        _UI["pick"] = min(cap, int(_UI["pick"] or 0) + 1)
    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        _send(client, view, _UI["pick"] or 0)
    elif event.key == pygame.K_ESCAPE:
        _send(client, view, 0)
    else:
        return False
    return True
