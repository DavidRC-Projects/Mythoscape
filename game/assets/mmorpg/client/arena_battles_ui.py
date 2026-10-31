"""Arena battles client: champion boss sprites, crowd meter + announcer, boss bar,
Champions / Ladder barracks tabs and the extra result-card lines.

Boss units (boss=True) are drawn by client.py via draw_boss / draw_boss_plate;
if the sheet is missing client.py falls back to the normal soldier doll.
"""
from __future__ import annotations

import math
import os
import time

import pygame

try:  # registers the gladiator gear items into content.ITEMS on the client too
    import arena_battles as _ab  # noqa: F401
except Exception:  # pragma: no cover
    _ab = None

_DIR = os.path.join(os.path.dirname(__file__), "assets", "castle_realm", "arena", "bosses")
_FEET = {"1x": (64, 118), "2x": (128, 236)}
_BASE = {"1x": 40, "2x": 80}
BOSS_HEIGHT_TILES = 3.2
_IMG = {}
_SCALED = {}

_GOLD = (220, 180, 70)
_GOLD_DIM = (140, 110, 40)
_TEXT = (235, 230, 210)
_MUTED = (160, 155, 140)
_OK = (90, 190, 110)
_BAD = (210, 90, 80)
_SAND = (210, 170, 70)
_NAVY = (18, 22, 34)
_NAVY2 = (28, 34, 52)


def _load(boss_id, tag, face):
    key = (boss_id, tag, face)
    if key not in _IMG:
        path = os.path.join(_DIR, boss_id, tag, f"{face}.png")
        try:
            _IMG[key] = pygame.image.load(path).convert_alpha() if os.path.isfile(path) else None
        except Exception:
            _IMG[key] = None
    return _IMG[key]


def boss_surface(boss_id, face, tile_px):
    """(surface, feet_x, feet_y) scaled so the figure is BOSS_HEIGHT_TILES tall."""
    face = face if face in ("n", "e", "s", "w") else "s"
    tag = "1x" if tile_px <= 44 else "2x"
    img = _load(boss_id, tag, face)
    if img is None:
        return None
    k = (boss_id, tag, face, int(tile_px))
    if k not in _SCALED:
        body_px = 112 if tag == "1x" else 224
        s = (BOSS_HEIGHT_TILES * tile_px) / float(body_px)
        w, h = max(1, int(img.get_width() * s)), max(1, int(img.get_height() * s))
        bb = img.get_bounding_rect(min_alpha=60)
        foot_y = (bb.bottom - 2) if bb.h else _FEET[tag][1]   # measured sole line, not the nominal anchor
        _SCALED[k] = (pygame.transform.smoothscale(img, (w, h)), _FEET[tag][0] * s, foot_y * s)
        if len(_SCALED) > 96:
            _SCALED.clear()
    return _SCALED[k]


WALK_FRAMES = 4
ATTACK_FRAMES = 3
_FRAMES = {}


def _body_top(img):
    r = img.get_bounding_rect(min_alpha=40)
    return r.top if r.h else 0


def _walk_frame(img, fx, fy, face, k):
    """Stride frame k (0..3) built from the HD sheet: the leg band is split and
    each leg is stepped forward/back in opposite phase; the upper body bobs."""
    w, h = img.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    top = _body_top(img)
    hip = int(top + (fy - top) * 0.62)
    phase = (0.0, 1.0, 0.0, -1.0)[k % 4]
    bob = (0, -1, 0, -1)[k % 4] * max(1, int((fy - top) * 0.025))
    upper = img.subsurface((0, 0, w, min(h, hip + 4))).copy()   # overlap the leg band: no seam on the bob
    legs = img.subsurface((0, hip, w, h - hip)).copy()
    step = max(1, int((fy - top) * 0.045))
    if face in ("e", "w"):
        # side view: shear the legs forward/back with the stride
        lh = legs.get_height()
        sheared = pygame.Surface(legs.get_size(), pygame.SRCALPHA)
        for row in range(0, lh, 2):
            off = int(phase * step * (row / max(1, lh)) * 1.6)
            sheared.blit(legs, (off, row), (0, row, w, 2))
        legs = sheared
        out.blit(legs, (0, hip))
    else:
        # front/back: left and right leg lift alternately
        half = int(fx)
        lift_l = int(max(0.0, phase) * step)
        lift_r = int(max(0.0, -phase) * step)
        out.blit(legs, (0, hip - lift_l), (0, 0, half, h - hip))
        out.blit(legs, (half, hip - lift_r), (half, 0, w - half, h - hip))
    out.blit(upper, (0, bob))
    return out


def _attack_frame(img, fx, fy, face, k):
    """0 wind-up (lean back), 1 strike (lean in), 2 recover."""
    ang = (6.0, -9.0, -3.0)[k % 3]
    if face == "w":
        ang = -ang
    elif face in ("n", "s"):
        ang *= 0.5
    rot = pygame.transform.rotozoom(img, ang, 1.0)
    out = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    out.blit(rot, ((img.get_width() - rot.get_width()) // 2, img.get_height() - rot.get_height()))
    return out


def boss_frame(boss_id, face, tile_px, anim, frame):
    got = boss_surface(boss_id, face, tile_px)
    if got is None:
        return None
    img, fx, fy = got
    if anim not in ("walk", "melee"):
        return got
    k = (boss_id, face, int(tile_px), anim, frame)
    if k not in _FRAMES:
        _FRAMES[k] = (_walk_frame if anim == "walk" else _attack_frame)(img, fx, fy, face, frame)
        if len(_FRAMES) > 240:
            _FRAMES.clear()
    return _FRAMES[k], fx, fy


def draw_boss(screen, m, cx, feet, tile_px, t, anim, atk, swing, face):
    """Draw an arena champion. Returns the y of the top of its head (for the plate),
    or None when the sheet is missing (caller falls back to the soldier doll)."""
    face = face if face in ("n", "e", "s", "w") else ("e" if m.get("facing") == "e" else "w")
    p = max(float(atk or 0), float(swing or 0))
    if anim == "walk":
        frame = int(t * 8.0) % WALK_FRAMES
    elif anim == "melee":
        frame = 0 if p < 0.35 else (1 if p < 0.75 else 2)
    else:
        frame = 0
    got = boss_frame(m.get("boss_id") or "", face, tile_px, anim, frame)
    if got is None:
        return None
    img, fx, fy = got
    dx = dy = 0.0
    if anim == "melee":
        lunge = math.sin(min(1.0, p) * math.pi) * tile_px * 0.14
        dx = {"e": lunge, "w": -lunge}.get(face, 0.0)
        dy = {"s": lunge * 0.4, "n": -lunge * 0.4}.get(face, 0.0)
    elif anim != "walk":
        dy = math.sin(t * 2.2) * tile_px * 0.015
    # champion's ground ring + soft shadow so the boss reads as the centrepiece
    rw, rh = int(tile_px * 1.9), int(tile_px * 0.62)
    ring = pygame.Surface((rw + 8, rh + 8), pygame.SRCALPHA)
    pygame.draw.ellipse(ring, (0, 0, 0, 95), (4, 4, rw, rh))
    side_col = (255, 120, 90) if m.get("side") == "foe" else (110, 190, 255)
    pulse = 150 + int(60 * math.sin(t * 3.0))
    pygame.draw.ellipse(ring, (255, 196, 90, pulse), (4, 4, rw, rh), 3)
    pygame.draw.ellipse(ring, side_col + (110,), (10, 8, rw - 12, rh - 8), 1)
    screen.blit(ring, (int(cx - ring.get_width() / 2), int(feet - ring.get_height() / 2)))
    screen.blit(img, (int(cx - fx + dx), int(feet - fy + dy)))
    if m.get("stunned"):
        f = pygame.font.Font(None, max(14, int(tile_px * 0.5)))
        st = f.render("STUNNED", True, (255, 230, 120))
        screen.blit(st, (int(cx - st.get_width() / 2), int(feet - tile_px * 0.2)))
    return int(feet - fy + _body_top(img) + dy)


def draw_boss_plate(client, m, cx, head_y):
    """Small HP pip over the boss's head (name + big bar live in the top-centre HUD)."""
    screen = client.screen
    hb = pygame.Rect(0, 0, 44, 6)
    hb.midbottom = (int(cx), int(head_y) - 6)
    pygame.draw.rect(screen, (20, 8, 6), hb.inflate(2, 2))
    frac = max(0.0, min(1.0, float(m.get("hp") or 0) / max(1, int(m.get("max_hp") or 1))))
    pygame.draw.rect(screen, (220, 60, 45), (hb.x, hb.y, int(hb.w * frac), hb.h))
    pygame.draw.rect(screen, (240, 200, 120), hb.inflate(2, 2), 1)


# --- HUD -----------------------------------------------------------------------
def _panel(surf, rect, alpha=232):
    bg = pygame.Surface(rect.size, pygame.SRCALPHA)
    bg.fill((12, 16, 26, alpha))
    surf.blit(bg, rect.topleft)
    pygame.draw.rect(surf, _GOLD_DIM, rect, 1, border_radius=8)


def crowd_colour(v):
    if v >= 80:
        return (255, 205, 80)
    if v >= 50:
        return (120, 200, 120)
    if v >= 25:
        return (210, 170, 90)
    return (210, 90, 80)


def crowd_mood(v):
    return "Adoring" if v >= 80 else "Cheering" if v >= 55 else "Restless" if v >= 30 else "Jeering"


def draw_hud(client, hud, map_w=900, map_h=640):
    surf, small, font = client.screen, client.font_small, client.font
    # crowd meter under the left army card
    v = int(hud.get("crowd", 50))
    if hud.get("duel"):
        return  # duels show the crowd as the finisher meter in arena_duel_ui
    r = pygame.Rect(68, 152, 250, 46)
    _panel(surf, r)
    surf.blit(small.render("CROWD FAVOUR", True, _SAND), (r.x + 12, r.y + 6))
    mood = small.render(crowd_mood(v), True, crowd_colour(v))
    surf.blit(mood, (r.right - mood.get_width() - 12, r.y + 6))
    bar = pygame.Rect(r.x + 12, r.y + 26, r.w - 24, 10)
    pygame.draw.rect(surf, (40, 40, 52), bar, border_radius=5)
    fill = bar.copy()
    fill.w = int(bar.w * v / 100)
    pygame.draw.rect(surf, crowd_colour(v), fill, border_radius=5)
    for mark in (50, 80):
        x = bar.x + bar.w * mark // 100
        pygame.draw.line(surf, (230, 230, 230), (x, bar.y - 2), (x, bar.bottom + 1), 1)
    pulse = int(40 + 30 * math.sin(time.time() * 6)) if v >= 80 else 0
    if pulse:
        pygame.draw.rect(surf, (255, 220, 120), bar.inflate(4, 4), 1, border_radius=6)
    # announcer ribbon
    ann = list(hud.get("announce") or [])
    if ann:
        text = str(ann[-1])
        lab = font.render(text[:64], True, (255, 232, 170))
        rib = pygame.Rect(0, 0, lab.get_width() + 48, 34)
        rib.midbottom = (map_w // 2, map_h - 120)
        _panel(surf, rib, 210)
        pygame.draw.line(surf, _GOLD, (rib.x + 10, rib.y + 2), (rib.right - 10, rib.y + 2), 1)
        surf.blit(lab, lab.get_rect(center=rib.center))
    # champion bar
    boss = hud.get("boss")
    if boss:
        br = pygame.Rect(0, 0, 240, 44)
        br.midtop = (map_w // 2, 54)      # directly under the CROWNFALL ARENA plaque
        _panel(surf, br)
        nm = small.render(f"{boss['name']} — {boss['title']}".upper(), True, (255, 200, 120))
        if nm.get_width() > br.w - 16:   # long names: drop the title rather than spill out of the bar
            nm = small.render(str(boss["name"]).upper(), True, (255, 200, 120))
        surf.blit(nm, nm.get_rect(midtop=(br.centerx, br.y + 5)))
        hb = pygame.Rect(br.x + 14, br.y + 24, br.w - 28, 12)
        pygame.draw.rect(surf, (50, 20, 20), hb, border_radius=5)
        f = hb.copy()
        f.w = int(hb.w * max(0, boss["hp"]) / max(1, boss["max_hp"]))
        pygame.draw.rect(surf, (200, 60, 50), f, border_radius=5)
        pygame.draw.rect(surf, (255, 170, 120), hb, 1, border_radius=5)
    if hud.get("ranked"):
        tag = small.render("RANKED", True, (150, 200, 255))
        surf.blit(tag, (map_w - 278 + 18, 118))


def result_lines(summary):
    out = []
    if summary.get("renown_gain"):
        out.append((f"+{summary['renown_gain']} Arena Renown  ·  {summary.get('renown_title', '')}"
                    f" ({summary.get('renown', 0)})", _GOLD))
    if summary.get("crowd") is not None:
        bit = f"Crowd {crowd_mood(int(summary['crowd']))} ({summary['crowd']})"
        if summary.get("crowd_purse"):
            bit += f"  ·  crowd purse +{summary['crowd_purse']:,}"
        out.append((bit, crowd_colour(int(summary["crowd"]))))
    if summary.get("elo"):
        e = summary["elo"]
        out.append((f"Ladder {e['before']} → {e['after']} ({e['delta']:+d})", (150, 200, 255)))
    if summary.get("gear_drop"):
        out.append((f"Spoils: {summary['gear_drop']['name']}", (255, 210, 120)))
    deed = summary.get("deed") or {}
    if deed.get("kind") == "deed":
        out.append((f"The King grants you the deed to {deed['house_name']}!", (255, 230, 140)))
    elif deed.get("kind") == "gold":
        out.append((f"Champion's purse {deed['bank']:,} to your bank", (255, 230, 140)))
    return out


# --- Barracks tabs -----------------------------------------------------------------
def tab_height(tab, data):
    a = data.get("arena") or {}
    if tab == "champions":
        return 10 + 40 + len(a.get("bosses") or []) * 96 + 12
    if tab == "ladder":
        return 10 + 120 + 30 + max(len(a.get("rivals") or []), 1) * 64 + 40 + len(a.get("leaderboard") or []) * 22 + 20
    return 0


def _icon(surf, rect, item_id):
    try:
        import realistic_item_icons as rii
        return rii.draw_icon(surf, rect, item_id)
    except Exception:
        return False


def _btn(surf, font, rects, key, label, rect, bg, fg, border):
    pygame.draw.rect(surf, bg, rect, border_radius=8)
    pygame.draw.rect(surf, border, rect, 1, border_radius=8)
    t = font.render(label, True, fg)
    surf.blit(t, t.get_rect(center=rect.center))
    rects[key] = rect


def draw_champions(client, surf, font, small, body, data, rects, scroll):
    a = data.get("arena") or {}
    y = body.y + 10 - scroll
    remaining = int((data.get("daily_fights") or {}).get("remaining", 10))
    surf.blit(font.render(f"Arena Renown {a.get('renown', 0)}  ·  {a.get('renown_title', 'Tiro')}", True, _GOLD),
              (body.x + 16, y))
    surf.blit(small.render("Renown raises your Standing (nobility). Beat The Unbroken for a King's Row deed.",
                           True, _MUTED), (body.x + 16, y + 22))
    y += 50
    for b in a.get("bosses") or []:
        row = pygame.Rect(body.x + 10, y, body.w - 28, 88)
        y += 96
        if row.bottom < body.y or row.top > body.bottom:
            continue
        un = b.get("unlocked")
        pygame.draw.rect(surf, (40, 32, 26) if un else (28, 28, 34), row, border_radius=8)
        pygame.draw.rect(surf, _GOLD if un and not b.get("beaten") else (_OK if b.get("beaten") else _GOLD_DIM),
                         row, 2 if un else 1, border_radius=8)
        got = boss_surface(b["boss_id"], "s", 30)
        if got:
            img, fx, fy = got
            if not un:
                img = img.copy()
                img.fill((70, 70, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
            _clip = surf.get_clip()
            surf.set_clip(row.inflate(-4, -4).clip(_clip) if _clip else row.inflate(-4, -4))
            surf.blit(img, (row.x + 40 - fx, row.bottom - 6 - fy))
            surf.set_clip(_clip)
        tx = row.x + 84
        surf.blit(font.render(f"T{b['tier']}  {b['name']}", True, _TEXT if un else _MUTED), (tx, row.y + 8))
        surf.blit(small.render(b["title"] + ("  ·  DEFEATED" if b.get("beaten") else ""), True,
                               _OK if b.get("beaten") else _SAND), (tx, row.y + 32))
        surf.blit(small.render(b["ability"], True, _MUTED), (tx, row.y + 52))
        ir = pygame.Rect(row.right - 220, row.y + 18, 48, 48)
        _icon(surf, ir, b["drop_id"])
        surf.blit(small.render(b["drop"], True, (255, 210, 120)), (ir.x - 4, ir.bottom + 2))
        if un and remaining > 0:
            _btn(surf, font, rects, f"practice:{b['id']}", "Challenge",
                 pygame.Rect(row.right - 136, row.y + 26, 120, 36), (80, 40, 20), _SAND, _GOLD)
        elif not un:
            surf.blit(small.render("Beat this tier's house first", True, _MUTED), (row.right - 200, row.y + 70))


def draw_ladder(client, surf, font, small, body, data, rects, scroll):
    a = data.get("arena") or {}
    lad = a.get("ladder") or {}
    y = body.y + 10 - scroll
    card = pygame.Rect(body.x + 10, y, body.w - 28, 110)
    pygame.draw.rect(surf, (26, 34, 52), card, border_radius=8)
    pygame.draw.rect(surf, (120, 170, 230), card, 1, border_radius=8)
    surf.blit(font.render(f"Ranked Season {lad.get('season', '')}", True, (150, 200, 255)), (card.x + 14, card.y + 10))
    left = max(0, int(lad.get("ends_at", 0) - time.time()))
    surf.blit(small.render(f"Resets in {left // 86400}d {left % 86400 // 3600}h  ·  soft reset to halfway to 1000",
                           True, _MUTED), (card.x + 14, card.y + 36))
    surf.blit(font.render(f"Rating {lad.get('rating', 1000)}   ·   {lad.get('band', 'Iron')} band   ·   "
                          f"W {lad.get('wins', 0)} / L {lad.get('losses', 0)}", True, _TEXT), (card.x + 14, card.y + 58))
    surf.blit(small.render("Season rewards: Gold 1600+ 60k · Silver 1400+ 25k · Bronze 1200+ 10k · Iron 2k (+renown)",
                           True, _SAND), (card.x + 14, card.y + 86))
    y += 120
    surf.blit(font.render("Rival commanders (their saved rosters, AI-led)", True, _GOLD), (body.x + 16, y))
    y += 30
    remaining = int((data.get("daily_fights") or {}).get("remaining", 10))
    rivals = a.get("rivals") or []
    if not rivals:
        surf.blit(small.render("No rival rosters yet — every fight you finish saves yours for others.", True, _MUTED),
                  (body.x + 16, y + 8))
        y += 64
    for r in rivals:
        row = pygame.Rect(body.x + 10, y, body.w - 28, 56)
        y += 64
        pygame.draw.rect(surf, (32, 36, 50), row, border_radius=8)
        pygame.draw.rect(surf, _GOLD_DIM, row, 1, border_radius=8)
        surf.blit(font.render(f"{r['name']}  ·  {r['soldiers']} soldiers  ·  CL {r['roster_cl']}", True, _TEXT),
                  (row.x + 14, row.y + 8))
        surf.blit(small.render(f"Rating {r['rating']}  ·  win {r['elo_win']:+d} / loss {r['elo_loss']:+d}", True,
                               _MUTED), (row.x + 14, row.y + 32))
        if remaining > 0:
            _btn(surf, font, rects, f"practice:{r['id']}", "Ranked fight",
                 pygame.Rect(row.right - 156, row.y + 10, 140, 36), (30, 50, 80), (170, 210, 255), (120, 170, 230))
    y += 8
    surf.blit(font.render("This week's top commanders", True, _GOLD), (body.x + 16, y))
    y += 30
    for e in a.get("leaderboard") or []:
        col = (255, 215, 90) if e["rank"] == 1 else _TEXT
        surf.blit(small.render(f"#{e['rank']:>2}  {e['name'][:22]:<22}  {e['rating']}   {e['wins']}-{e['losses']}",
                               True, col), (body.x + 26, y))
        y += 22
