"""Crownfall phase 8: Royal Treasury panel (monarch full view, council limited view).

Opened by /treasury (server answers ROYAL_STATE). Text and simple buttons only.
Bounties and appointments use chat: /treasury bounty <monster> <amount>, /treasury appoint <post> <player>.
"""
from __future__ import annotations

import time

import pygame

_BOX = pygame.Rect(120, 40, 680, 580)


def _btn(client, rects, key, label, x, y, enabled=True):
    w = client.font_tiny.size(label)[0] + 14
    r = pygame.Rect(x, y, w, 20)
    pygame.draw.rect(client.screen, (60, 90, 70) if enabled else (50, 50, 56), r, border_radius=4)
    pygame.draw.rect(client.screen, (200, 200, 200), r, 1, border_radius=4)
    client.screen.blit(client.font_tiny.render(label, True, (255, 255, 255)), (r.x + 7, r.y + 3))
    if enabled:
        rects[key] = r
    return r.right + 6


def _text(client, s, x, y, col=(225, 225, 235), font=None):
    client.screen.blit((font or client.font_tiny).render(s, True, col), (x, y))


def draw(client):
    st = getattr(client, "royal_panel", None)
    if not st:
        return
    rects = {}
    box = _BOX
    pygame.draw.rect(client.screen, (22, 22, 32), box)
    pygame.draw.rect(client.screen, (255, 205, 60), box, 2)
    role = st.get("role") or "?"
    _text(client, f"Royal Treasury  ·  {role}", box.x + 14, box.y + 10, (255, 215, 90), client.font)
    _btn(client, rects, "close", "Close", box.right - 64, box.y + 10)
    y = box.y + 42
    _text(client, f"Balance {st['balance']:,}  ·  spent today {st['spent']:,}/{st['cap']:,}  ·  "
                  f"reserved for bounties {st['reserved']:,}", box.x + 14, y)
    y += 22
    monarch = role == "Monarch"
    _text(client, "Rates (take effect at the next daily tick, one change per 24h)", box.x + 14, y, (180, 200, 255))
    y += 18
    for key, s in st["settings"].items():
        pct = key == "sales_tax"
        val = f"{round(s['value'] * 100)}%" if pct else f"{int(s['value']):,}"
        pend = s.get("pending")
        ptxt = f" → {round(pend * 100)}%" if pend is not None and pct else (f" → {int(pend):,}" if pend is not None else "")
        cd = s.get("cooldown") or 0
        bounds = f"{round(s['min'] * 100)}–{round(s['max'] * 100)}%" if pct else f"{int(s['min'])}–{int(s['max'])}"
        _text(client, f"{s['label'].capitalize()}: {val}{ptxt}  ({bounds})" + (f"  cooldown {cd // 3600}h" if cd else ""),
              box.x + 24, y + 3)
        can = (monarch or (role == "Steward" and not pct)) and not cd
        step = 0.01 if pct else max(10, int(s["min"] * 0.1))
        bx = box.x + 470
        bx = _btn(client, rects, f"tax-:{key}:{max(s['min'], s['value'] - step)}", "−", bx, y, can)
        _btn(client, rects, f"tax+:{key}:{min(s['max'], s['value'] + step)}", "+", bx, y, can)
        y += 22
    y += 6
    _text(client, "Public works (7 days each)", box.x + 14, y, (180, 200, 255))
    y += 18
    for key, w in st["works"].items():
        _text(client, f"{w['name']} · {w['cost']:,} · " + ("ACTIVE" if w["active"] else "idle"), box.x + 24, y + 3)
        _btn(client, rects, f"work:{key}", "Fund", box.x + 470, y,
             (monarch or role == "Chancellor") and not w["active"])
        y += 22
    y += 6
    _text(client, "Bounties (/treasury bounty <monster> <1000-20000>)", box.x + 14, y, (180, 200, 255))
    y += 18
    for b in st["bounties"] or [{"id": None}]:
        if b["id"] is None:
            _text(client, "none active", box.x + 24, y + 3, (150, 150, 160))
        else:
            _text(client, f"#{b['id']} {b['monster']} · {b['amount']:,}", box.x + 24, y + 3)
            _btn(client, rects, f"cancel:{b['id']}", "Cancel", box.x + 470, y, role in ("Monarch", "Marshal"))
        y += 22
    y += 6
    _text(client, "Council (/treasury appoint <post> <player>, /treasury dismiss <post>)", box.x + 14, y, (180, 200, 255))
    y += 18
    council = st.get("council") or {}
    _text(client, "  ·  ".join(f"{p}: #{pid}" for p, pid in council.items()) or "no one appointed", box.x + 24, y)
    y += 20
    ok_king = st.get("old_king")
    if monarch and ok_king in ("imprisoned", "exiled"):
        label = "Free the old King (25,000)" if ok_king == "imprisoned" else "Recall the old King (50,000)"
        _btn(client, rects, "king", label, box.x + 24, y)
        y += 24
    _text(client, "Audit (latest 20)", box.x + 14, y, (180, 200, 255))
    y += 16
    for ts, post, action, amount, detail in (st.get("audit") or [])[:20]:
        if y > box.bottom - 16:
            break
        when = time.strftime("%d %b %H:%M", time.localtime(ts or 0))
        _text(client, f"{when}  {post or '-'}  {action}  {amount:,}  {str(detail)[:40]}", box.x + 24, y, (170, 170, 180))
        y += 14
    client.royal_panel_rects = rects


def click(client, mx, my):
    """True when the panel used the click."""
    st = getattr(client, "royal_panel", None)
    if not st:
        return False
    for key, r in (getattr(client, "royal_panel_rects", None) or {}).items():
        if not r.collidepoint(mx, my):
            continue
        if key == "close":
            client.royal_panel = None
        elif key.startswith("tax"):
            _k, setting, value = key.split(":")
            client.net.send("RULE_SET_TAX", key=setting, value=float(value))
        elif key.startswith("work:"):
            client.net.send("RULE_FUND_WORK", key=key[5:])
        elif key.startswith("cancel:"):
            client.net.send("RULE_CANCEL_BOUNTY", id=int(key[7:]))
        elif key == "king":
            client.net.send("RULE_FREE_KING" if st.get("old_king") == "imprisoned" else "RULE_RECALL_KING")
        return True
    if not _BOX.collidepoint(mx, my):
        client.royal_panel = None
    return True
