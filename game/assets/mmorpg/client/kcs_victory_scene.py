"""Siege victory cutscene (David t648u), drawn live in the game (no film file).

Played once per war when the attackers win (KCS_RESULT, winner "attack"). The winner sits on the
throne in the King outfit (king_coat -> outfit_king_hd, the original art; queen_gown for a woman),
the old king (the NPC King art) bows before them and is spared and sent into exile, and the
attacking soldiers cheer with raised swords. About 13 s; any key or click skips; then the game
carries on underneath. Flag USE_KCS_VICTORY_SCENE (default OFF; on in the sandbox launchers).
Sandbox preview: F11 while KCS_SANDBOX_PREP=1.
"""
from __future__ import annotations

import math
import os
import random

import pygame

DURATION = 13.0
ANNOUNCE = 4.0     # t662u: full-screen win card before the cutscene (same music, no restart)
GRACE = 0.6
TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "iron", "steel", "bronze")
_STATE = {}
_CACHE = {}
_DIR = os.path.dirname(os.path.abspath(__file__))


def enabled() -> bool:
    return str(os.environ.get("USE_KCS_VICTORY_SCENE", "0")).strip().lower() in ("1", "true", "yes", "on")


def playing() -> bool:
    return bool(_STATE.get("on"))


def start(client, info=None, war_id=None) -> bool:
    """Begin the scene. info: {name, gender, appearance, monarch_player_id} from the server."""
    if playing():
        return False
    info = dict(info or {})
    me = getattr(client, "player", None) or {}
    mid = info.get("monarch_player_id")
    person = None
    if mid is not None and me and mid == me.get("id"):
        person = me
    elif mid is not None:
        person = (getattr(client, "players", None) or {}).get(mid)
    person = person or {}
    gender = str(info.get("gender") or person.get("gender") or "male").lower()
    sex = "female" if gender.startswith("f") else "male"
    look = info.get("appearance") or person.get("appearance")
    name = info.get("name") or person.get("username") or person.get("name") or "The victor"
    _STATE.clear()
    _STATE.update(on=True, t0=pygame.time.get_ticks(), sex=sex, look=look, name=str(name), war_id=war_id,
                  guild=str(info.get("guild") or ""),
                  confetti=[(random.random(), random.random(), random.random()) for _ in range(90)])
    try:
        import kcs_client
        kcs_client.ensure_assets()
    except Exception:
        pass
    try:   # Coronation of the Realm starts with the win card and runs on through the cutscene
        import area_music
        area_music.victory_start()
    except Exception:
        pass
    return True


def start_throne_sequence(client) -> None:
    """'Take the Throne' (t664u). The ONE entry point the button calls. For now: claim the crown on the
    server (KCS_CLAIM take_throne) - the server's KCS_RESULT then plays the existing win card,
    Coronation of the Realm and this cutscene. Replace the body with the throne-room entry later."""
    try:
        import kcs_client
        kcs_client._send(client, "KCS_CLAIM", take_throne=True)
        kcs_client.note(client, "You stride through the broken keep doors to take the throne...")
    except Exception:
        pass


def stop():
    room = _STATE.get("room")
    if room:
        try:
            import kcs_throne_room
            kcs_throne_room.stop_video(room)
        except Exception:
            pass
    _STATE.clear()
    try:
        import area_music
        area_music.victory_end()
    except Exception:
        pass


def elapsed() -> float:
    return (pygame.time.get_ticks() - _STATE.get("t0", 0)) / 1000.0


def handle_event(client, event) -> bool:
    """Swallow input while playing; a key/click on the win card skips to the cutscene, then skips that."""
    if not playing():
        return False
    if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and elapsed() >= GRACE:
        if elapsed() < ANNOUNCE:
            _STATE["t0"] = pygame.time.get_ticks() - int(ANNOUNCE * 1000)   # music keeps playing
        elif _STATE.get("room"):
            try:
                import kcs_throne_room
                verdict = kcs_throne_room.handle_event(event, _STATE["room"], client.screen)
            except Exception:
                verdict = "failed"
            if verdict == "done":
                stop()
            elif verdict == "failed":
                _fallback()
        else:
            stop()
    return event.type in (pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEMOTION, pygame.TEXTINPUT, pygame.MOUSEWHEEL)


# ---- art ------------------------------------------------------------------------------------
def _img(path):
    if path not in _CACHE:
        try:
            _CACHE[path] = pygame.image.load(path).convert_alpha()
        except Exception:
            _CACHE[path] = None
    return _CACHE[path]


def _background(sw, sh):
    key = ("bg", sw, sh)
    if key not in _CACHE:
        img = _img(os.path.join(_DIR, "assets", "ui", "stats_screen", "throne_hall_bg.jpg"))
        surf = pygame.Surface((sw, sh))
        surf.fill((26, 18, 14))
        if img is not None:
            k = max(sw / img.get_width(), sh / img.get_height())
            big = pygame.transform.smoothscale(img, (int(img.get_width() * k) + 1, int(img.get_height() * k) + 1))
            surf.blit(big, ((sw - big.get_width()) // 2, (sh - big.get_height()) // 2))
        shade = pygame.Surface((sw, sh), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 70))
        surf.blit(shade, (0, 0))
        _dais(surf, sw, sh)
        _CACHE[key] = surf
    return _CACHE[key]


def _dais(surf, sw, sh):
    """Three stone steps with gold trim, a red runner up the middle and a brazier each side."""
    cx = sw // 2
    top = int(sh * .56)
    steps = [(int(sw * .17), top), (int(sw * .20), top + int(sh * .035)), (int(sw * .23), top + int(sh * .07))]
    for i, (half, y) in enumerate(steps):
        h = int(sh * .035) + 1
        rect = pygame.Rect(cx - half, y, half * 2, h)
        for j in range(h):                        # lit tread on top, darker riser below
            k = j / max(1, h - 1)
            c = (int(118 - 50 * k - 8 * i), int(104 - 46 * k - 8 * i), int(92 - 40 * k - 6 * i))
            pygame.draw.line(surf, c, (rect.x, y + j), (rect.right, y + j))
        pygame.draw.line(surf, (214, 176, 86), (rect.x, y), (rect.right - 1, y), 2)
        pygame.draw.line(surf, (40, 30, 24), (rect.x, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
        for bx in range(rect.x + 18, rect.right - 10, 46):        # block joints
            pygame.draw.line(surf, (60, 50, 44), (bx, y + 3), (bx, rect.bottom - 2))
    bottom = steps[-1][1] + int(sh * .035)
    run = [(cx - int(sw * .045), top), (cx + int(sw * .045), top), (cx + int(sw * .16), sh), (cx - int(sw * .16), sh)]
    pygame.draw.polygon(surf, (128, 20, 28), run)
    pygame.draw.lines(surf, (214, 176, 86), False, [run[0], run[3]], 3)
    pygame.draw.lines(surf, (214, 176, 86), False, [run[1], run[2]], 3)
    for j in range(3):
        y = steps[j][1]
        pygame.draw.line(surf, (90, 12, 18), (cx - int(sw * (.045 + .011 * j)), y), (cx + int(sw * (.045 + .011 * j)), y), 2)
    for side in (-1, 1):                            # braziers on the top step
        bx = cx + side * int(sw * .15)
        by = top
        pygame.draw.rect(surf, (54, 44, 36), pygame.Rect(bx - 6, by - 46, 12, 46))
        pygame.draw.ellipse(surf, (150, 118, 60), pygame.Rect(bx - 20, by - 58, 40, 16))
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        for r in range(60, 0, -6):
            pygame.draw.circle(glow, (255, 150, 40, int(70 * (1 - r / 60.0)) + 8), (60, 60), r)
        surf.blit(glow, (bx - 60, by - 112))
        pygame.draw.polygon(surf, (255, 200, 80), [(bx - 14, by - 54), (bx, by - 92), (bx + 14, by - 54)])
        pygame.draw.polygon(surf, (255, 240, 170), [(bx - 6, by - 56), (bx, by - 76), (bx + 6, by - 56)])
    return bottom


def _figure(sex, look, tile, t, facing="front"):
    """The winner in the King outfit on a scratch canvas. Returns (surface, feet (x, y))."""
    import player_hd_client as phd
    look = dict(look or phd.get_default_appearance(sex))
    look["outfit"] = "queen_gown" if sex == "female" else "king_coat"
    look["set"] = None
    w, h = tile * 4, tile * 5
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    feet = (w // 2, int(h * .9))
    try:
        phd.draw_player(surf, sex, look, feet[0], feet[1], tile, t, anim="idle", facing=facing, equipment={})
    except Exception:
        pass
    return surf, feet


def _bounds(surf):
    rects = pygame.mask.from_surface(surf, 40).get_bounding_rects()
    if not rects:
        return None
    return rects[0].unionall(rects[1:]) if len(rects) > 1 else rects[0]


def _robe_colour(surf, rect):
    """Mean opaque colour inside rect (the outfit's own robe at the thighs)."""
    r = g = b = n = 0
    for y in range(rect.top, rect.bottom, 2):
        for x in range(rect.left, rect.right, 2):
            c = surf.get_at((x, y))
            if c.a > 200:
                r, g, b, n = r + c.r, g + c.g, b + c.b, n + 1
    return (r // n, g // n, b // n) if n else (40, 30, 40)


def _seated(fig, feet):
    """Front-view sitting from the standing figure's own pixels (there is no sit art).

    Torso kept whole to the hips. The thighs come toward the camera, so they shrink to a short lap that
    is wider than the hips (knees apart). Each shin (left / right half of the lower legs) hangs from its
    knee and slants back in to the feet. The robe, in the outfit's own colour, drapes from the lap over
    the seat edge between the knees, with folds and a shadow where it meets the seat."""
    box = _bounds(fig)
    if box is None:
        return fig, feet
    W, H = fig.get_size()
    hip = box.top + int(box.height * .54)
    leg_h = box.bottom - hip
    knee = hip + int(leg_h * .42)
    cx = box.centerx
    upper = fig.subsurface(pygame.Rect(0, 0, W, hip)).copy()
    thigh = fig.subsurface(pygame.Rect(0, hip, W, knee - hip)).copy()
    shin_h = box.bottom - knee
    left = fig.subsurface(pygame.Rect(0, knee, cx, shin_h)).copy()
    right = fig.subsurface(pygame.Rect(cx, knee, W - cx, shin_h)).copy()
    robe = _robe_colour(fig, pygame.Rect(cx - box.width // 6, hip + 2, max(2, box.width // 3), max(2, knee - hip - 4)))
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    y_feet = box.bottom
    spread = max(3, int(box.width * .10))            # knees sit this far out from the standing line
    shin_draw = int(shin_h * .95)
    y_knee = y_feet - shin_draw
    left = pygame.transform.smoothscale(left, (left.get_width(), shin_draw))
    right = pygame.transform.smoothscale(right, (right.get_width(), shin_draw))
    for y in range(shin_draw):                       # shins: knee out, foot back in (bent-leg read)
        k = 1.0 - y / max(1, shin_draw - 1)
        off = int(spread * (.25 + .75 * k))
        out.blit(left, (-off, y_knee + y), pygame.Rect(0, y, left.get_width(), 1))
        out.blit(right, (cx + off, y_knee + y), pygame.Rect(0, y, right.get_width(), 1))
    lap_h = max(3, int(thigh.get_height() * .42))
    lap_w = int(W * 1.0) + spread * 2
    lap = pygame.transform.smoothscale(thigh, (lap_w, lap_h))
    lap_top = y_knee - lap_h + 3
    # seat shadow behind the lap
    sh = pygame.Surface((int(box.width * 1.25), lap_h * 2 + 6), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 90), sh.get_rect())
    out.blit(sh, (cx - sh.get_width() // 2, lap_top - 2))
    # robe draped over the seat edge, between and over the knees
    top_w = int(box.width * .40)
    bot_w = int(box.width * .30)
    drop = int(shin_draw * .46)
    drape = pygame.Surface((W + spread * 2, drop + lap_h + 4), pygame.SRCALPHA)
    dcx = drape.get_width() // 2
    poly = [(dcx - top_w // 2, 0), (dcx + top_w // 2, 0), (dcx + bot_w // 2, drop), (dcx + bot_w // 6, drop + 4),
            (dcx - bot_w // 6, drop + 2), (dcx - bot_w // 2, drop)]
    pygame.draw.polygon(drape, (*robe, 245), poly)
    dark = tuple(max(0, int(c * .62)) for c in robe)
    lite = tuple(min(255, int(c * 1.25) + 8) for c in robe)
    for i, fx in enumerate((-.30, -.10, .12, .32)):
        x0 = dcx + int(top_w * fx)
        x1 = dcx + int(bot_w * fx * 1.1)
        pygame.draw.line(drape, (*(dark if i % 2 == 0 else lite), 200), (x0, 2), (x1, drop - 2), 2)
    pygame.draw.line(drape, (*dark, 220), poly[0], poly[1], 3)          # fold over the seat edge
    out.blit(drape, (cx - dcx, lap_top + lap_h - 3))
    out.blit(lap, (cx - lap_w // 2, lap_top))
    # top of the thighs catches the light; knee caps read as two rounded bumps
    lite_band = pygame.Surface((int(box.width * .9), 3), pygame.SRCALPHA)
    lite_band.fill((*tuple(min(255, int(c * 1.4) + 20) for c in robe), 120))
    out.blit(lite_band, (cx - lite_band.get_width() // 2, lap_top + 2))
    for side in (-1, 1):
        kx = cx + side * (box.width // 4 + spread // 2)
        pygame.draw.ellipse(out, (*tuple(min(255, int(c * 1.15) + 6) for c in robe), 230),
                            pygame.Rect(kx - box.width // 7, y_knee - lap_h // 2, box.width // 7 * 2, lap_h))
    out.blit(upper, (0, lap_top + 4 - hip))
    return out, (feet[0], y_feet)


def _old_king(tile, t, bow):
    """NPC King art facing the throne (west). bow 0..1: he sinks to one knee (legs fold) and bends from
    the waist with his head lowered, instead of snapping in half."""
    try:
        import npc_hd_client as npc
        root = npc._DIR
    except Exception:
        root = os.path.join(_DIR, "assets", "npc_hd")
    img = _img(os.path.join(root, "king", "sprite_2x", "w", "f00.png")) or _img(os.path.join(root, "king", "sprite_2x", "s", "f00.png"))
    if img is None:
        return None, (0, 0)
    k = tile / 80.0 * 1.15
    img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))
    box = _bounds(img)
    if box is None:
        return img, (img.get_width() // 2, img.get_height())
    feet = (box.centerx, box.bottom)
    if bow <= 0:
        return img, feet
    ease = bow * bow * (3 - 2 * bow)
    waist = box.top + int(box.height * .50)
    upper = img.subsurface(pygame.Rect(0, 0, img.get_width(), waist)).copy()
    legs = img.subsurface(pygame.Rect(0, waist, img.get_width(), box.bottom - waist)).copy()
    # kneel: legs fold to ~60 % height and lean back a touch (rear knee down)
    leg_h = max(2, int(legs.get_height() * (1 - .40 * ease)))
    legs = pygame.transform.smoothscale(legs, (int(legs.get_width() * (1 + .10 * ease)), leg_h))
    pad = img.get_height()
    canvas = pygame.Surface((img.get_width() + pad * 2, img.get_height() + pad), pygame.SRCALPHA)
    ox, oy = pad, pad // 2
    ground = oy + box.bottom
    lx = ox - (legs.get_width() - img.get_width()) // 2 + int(6 * ease * k)
    canvas.blit(legs, (lx, ground - leg_h))
    hip_y = ground - leg_h + 4
    angle = 24 * ease                       # counter-clockwise: chest and head lean toward the throne (left)
    pivot = pygame.math.Vector2(box.centerx, waist)
    rot = pygame.transform.rotozoom(upper, angle, 1.0)
    centre = pygame.math.Vector2(upper.get_width() / 2, upper.get_height() / 2)
    pos = pivot + (centre - pivot).rotate(-angle)
    canvas.blit(rot, (ox + pos.x - rot.get_width() / 2, hip_y - waist + pos.y - rot.get_height() / 2))
    return canvas, (ox + feet[0], ground)


def _soldier(dest, foot, tier, facing, cheer, t, scale):
    try:
        import kcs_siege_players as actors
        anim = "melee" if cheer else "idle"
        prog = (t * (0.9 if cheer else 1.2)) % 1.0
        hop = abs(math.sin(t * 5.0)) * 10 * scale if cheer else 0
        actors.actor_blit(dest, kind="male", tier=tier, facing=facing, anim=anim, progress=prog,
                          foot_screen=(int(foot[0]), int(foot[1] - hop)), scale=scale, weapon="sword",
                          shield=f"{tier}_shield")
    except Exception:
        pass


def _caption(screen, text, y, alpha, size=34, colour=(246, 222, 150)):
    if alpha <= 0 or not text:
        return
    font = pygame.font.Font(None, size)
    img = font.render(text, True, colour)
    sh = font.render(text, True, (0, 0, 0))
    x = (screen.get_width() - img.get_width()) // 2
    for s, d in ((sh, 2), (img, 0)):
        s.set_alpha(int(255 * alpha))
        screen.blit(s, (x + d, y + d))


def _fade(t, a, b, edge=.5):
    if t < a or t > b:
        return 0.0
    return max(0.0, min(1.0, (t - a) / edge, (b - t) / edge))


def _announce(screen, t):
    """Full-screen card: 'Victory! You have won the Crown of the Realm' + the guild, ~4 s."""
    sw, sh = screen.get_size()
    screen.fill((10, 8, 14))
    glow = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for i in range(8, 0, -1):
        pygame.draw.ellipse(glow, (212, 160, 60, 10), pygame.Rect(sw // 2 - i * sw // 16, sh // 2 - i * sh // 18,
                                                                  i * sw // 8, i * sh // 9))
    screen.blit(glow, (0, 0))
    a = _fade(t, 0.0, ANNOUNCE, .6)
    _caption(screen, "Victory!", int(sh * .30), a, size=max(64, sh // 7), colour=(250, 214, 120))
    _caption(screen, "You have won the Crown of the Realm", int(sh * .48), a, size=max(36, sh // 16))
    guild = _STATE.get("guild")
    if guild:
        _caption(screen, f"for {guild}", int(sh * .58), _fade(t, .5, ANNOUNCE, .6), size=max(30, sh // 20),
                 colour=(236, 226, 205))
    name = _STATE.get("name")
    if name:
        _caption(screen, f"{name} will take the throne.", int(sh * .68), _fade(t, 1.0, ANNOUNCE, .6), size=26,
                 colour=(200, 190, 170))


def _fallback():
    """The first-person room or the video failed: run the old procedural cutscene from its start."""
    room = _STATE.pop("room", None)
    if room:
        try:
            import kcs_throne_room
            kcs_throne_room.stop_video(room)
        except Exception:
            pass
    _STATE["old"] = True
    _STATE["old_t0"] = pygame.time.get_ticks()


def draw(client) -> None:
    if not playing():
        return
    t = elapsed()
    if t < ANNOUNCE:
        _announce(client.screen, t)
        return
    t -= ANNOUNCE
    # t666u: first-person throne room walk-in + AI coronation video, old cutscene only as fallback
    if not _STATE.get("old"):
        try:
            import kcs_throne_room
            if not kcs_throne_room.available():
                raise FileNotFoundError(kcs_throne_room.IMAGE)
            room = _STATE.setdefault("room", {})
            if kcs_throne_room.draw(client.screen, t, room) == "done":
                stop()
            return
        except Exception:
            _fallback()
    if _STATE.get("old_t0") is not None:
        t = (pygame.time.get_ticks() - _STATE["old_t0"]) / 1000.0
    if t >= DURATION:
        stop()
        return
    screen = client.screen
    sw, sh = screen.get_size()
    screen.blit(_background(sw, sh), (0, 0))
    tile = max(40, int(sh / 7.5))
    dais_y = int(sh * .59)
    # throne + seated winner
    throne = _img(os.path.join(_DIR, "assets", "props", "throne_s_1x.png"))
    if throne is not None:
        k = tile * 2.0 / throne.get_height()
        th = pygame.transform.smoothscale(throne, (int(throne.get_width() * k), int(throne.get_height() * k)))
        screen.blit(th, (sw // 2 - th.get_width() // 2, dais_y - th.get_height() + int(tile * .15)))
    fig, feet = _figure(_STATE["sex"], _STATE.get("look"), tile, t)
    fig, feet = _seated(fig, feet)
    screen.blit(fig, (sw // 2 - feet[0], dais_y + int(tile * .06) - feet[1]))
    # old king: walks in from the right (0-3 s), bows (3-5 s), holds, is led away into exile (9.5 s+)
    if t < 3.0:
        kx = sw * (1.02 - .30 * (t / 3.0))
        bow = 0.0
    elif t < 9.5:
        kx = sw * .72
        bow = min(1.0, (t - 3.0) / 1.6)
    else:
        kx = sw * (.72 + .35 * min(1.0, (t - 9.5) / 3.0))
        bow = max(0.0, 1.0 - (t - 9.5) / .6)
    king, kfeet = _old_king(tile, t, bow)
    if king is not None:
        screen.blit(king, (int(kx - kfeet[0]), int(sh * .80 - kfeet[1])))
    # soldiers: two cheering ranks either side of the carpet
    scale = tile / 40.0 * .55
    cheer = t > 1.0
    for i, tier in enumerate(TIERS):
        left = i % 2 == 0
        rank = i // 2
        x = sw * (.10 + .07 * rank) if left else sw * (.90 - .07 * rank)
        if not left and t < 9.5 and abs(x - kx) < sw * .05:
            x -= sw * .06
        y = sh * (.72 + .06 * (rank % 2)) + rank * 8
        _soldier(screen, (x, y), tier, "e" if left else "w", cheer and (i + int(t * 2)) % 3 != 0, t + i * .37, scale)
    for i in range(6):
        x = sw * (.18 + .13 * i)
        _soldier(screen, (x, sh * .97), TIERS[i], "n", cheer, t + i * .53, scale * 1.1)
    # gold confetti once the crown is taken
    if t > 1.0:
        for (fx, fy, sp) in _STATE["confetti"]:
            y = ((fy + (t - 1.0) * (.12 + .18 * sp)) % 1.0) * sh
            x = fx * sw + math.sin(t * 2 + fy * 9) * 12
            pygame.draw.rect(screen, (240, 200, 80) if sp > .5 else (200, 60, 60), pygame.Rect(int(x), int(y), 5, 3))
    name = _STATE.get("name") or "The victor"
    _caption(screen, "Victory! The castle has fallen.", int(sh * .06), _fade(t, .3, 4.0))
    _caption(screen, f"{name} takes the throne.", int(sh * .06), _fade(t, 4.0, 8.0))
    _caption(screen, "The old king bows before the new ruler.", int(sh * .12), _fade(t, 4.4, 9.5), size=26,
             colour=(236, 226, 205))
    _caption(screen, "He is spared, and sent into exile.", int(sh * .06), _fade(t, 9.5, DURATION), size=30)
    font = pygame.font.Font(None, 20)
    label = font.render("Skip  >", True, (240, 228, 200))
    r = pygame.Rect(0, 0, label.get_width() + 32, label.get_height() + 14)
    r.bottomright = (sw - 18, sh - 14)
    pygame.draw.rect(screen, (20, 18, 24), r, border_radius=14)
    pygame.draw.rect(screen, (212, 175, 90), r, 1, border_radius=14)
    screen.blit(label, (r.x + 16, r.y + 7))
    if t < .6 or t > DURATION - .6:
        veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
        a = (1 - t / .6) if t < .6 else (t - (DURATION - .6)) / .6
        veil.fill((0, 0, 0, int(255 * max(0, min(1, a)))))
        screen.blit(veil, (0, 0))
