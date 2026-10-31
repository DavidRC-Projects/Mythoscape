"""Crownfall Vale mountain ring on the client (ZONES_SPEC.md sections 2, 5, 6, 8).

Painted peaks stand on the ring's cliff-base tiles (vale_ring.py), Y-sorted with
everything else so players walking in front pass over the mountain foot; a peak
that covers the player fades to 45 %. Watchtowers and flickering torches mark
the passes. The ring also draws on the minimap (grey peaks, pass markers,
"Crownfall Vale" label) and an "Entering Crownfall Vale" banner shows when a
player comes back into the vale (0.4 s in, 2.5 s hold, 0.6 s out, 8 s cooldown).
Missing art falls back to the old tiles (draw_ground returns False).
"""
import math
import os
import time

import pygame

import vale_ring as VR

_IMG = {}
_SCALED = {}
_STATE = {"inside": None, "until": 0.0, "last": -99.0}
FADE_IN, HOLD, FADE_OUT, COOLDOWN = 0.4, 2.5, 0.6, 8.0


# First kit (peak_1-4, ridges) came out slightly lavender: desaturate a little and
# warm it so it sits with the HD village palette and the warm second kit.
_COOL_KIT = {"peak_1", "peak_2", "peak_3", "peak_4", "ridge_1", "ridge_2", "ridge_3", "ridge_4"}
# Where the art's foot sits, as a fraction of image height (kit 2 has a grass apron).
ANCHOR = {"peak_5": 0.86, "peak_6": 0.88, "peak_7": 0.86, "peak_8": 0.87, "peak_9": 0.86, "peak_10": 0.88,
          "gate_2": 0.95}
TINTS = ((255, 255, 255), (255, 243, 226), (240, 236, 228))


def _img(name):
    if name not in _IMG:
        try:
            img = pygame.image.load(os.path.join(VR.ASSET_DIR, name + ".png")).convert_alpha()
            if name in _COOL_KIT:
                try:
                    gray = pygame.transform.grayscale(img)
                    gray.set_alpha(90)
                    img.blit(gray, (0, 0))
                except Exception:
                    pass
                img.fill((255, 236, 212, 255), special_flags=pygame.BLEND_RGBA_MULT)
            if name.startswith(("peak_", "ridge_")):
                img = _soften(img)
            _IMG[name] = img
        except Exception as exc:          # missing art: old tiles stay
            print("[vale_ring]", exc)
            _IMG[name] = None
    return _IMG[name]


def _soften(img):
    """Blend a peak's foot into the ground: the grass apron becomes scree and the
    bottom edge fades out with noise, so no oval grass pad shows (31 Oct)."""
    try:
        import numpy as np
        w, h = img.get_size()
        rgb = pygame.surfarray.pixels3d(img)
        al = pygame.surfarray.pixels_alpha(img)
        a = al.astype(np.float32)
        r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        ys = np.arange(h, dtype=np.float32)[None, :]
        low = ys > h * 0.45
        opaque = a > 40
        bottom = np.where(opaque.any(1), h - 1 - np.argmax(opaque[:, ::-1], 1), 0).astype(np.float32)
        top = np.where(opaque.any(1), np.argmax(opaque, 1), 0).astype(np.float32)
        feather = np.maximum(4.0, (bottom - top) * 0.30)[:, None]
        rng = np.random.default_rng(w * 31 + h)
        ns = pygame.Surface((w // 8 + 2, h // 8 + 2))
        pygame.surfarray.blit_array(ns, (rng.random(ns.get_size()) * 255).astype(np.uint32) * 0x010101)
        n = pygame.surfarray.array_red(pygame.transform.smoothscale(ns, (w, h))).astype(np.float32) / 255.0
        # apron (bottom band near the foot): grass -> warm scree; pines (dark) stay
        band = (bottom[:, None] - ys) < feather * 0.9
        green = (g > r * 1.02) & (g > b * 1.05) & low & band & (lum > 70)
        k = np.where(green, 0.7, 0.0)[..., None]
        scree = np.stack([lum * 1.04, lum * 0.95, lum * 0.82], -1)
        rgb[...] = np.clip(rgb.astype(np.float32) * (1 - k) + scree * k, 0, 255).astype(np.uint8)
        f = np.clip((bottom[:, None] - ys) / feather + (n - 0.5) * 0.5, 0.0, 1.0)
        # side edges of the apron fade too (soft oval instead of a hard rim)
        al[...] = (a * f * f * (3 - 2 * f)).astype(np.uint8)
        del rgb, al
    except Exception as exc:
        print("[vale_ring] soften", exc)
    return img


_SHADOW = {}


def _shadow(w, h):
    key = (w, h)
    s = _SHADOW.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(10):
            k = i / 10.0
            rr = pygame.Rect(0, 0, int(w * (1 - k * 0.7)), int(h * (1 - k * 0.7)))
            rr.center = (w // 2, h // 2)
            pygame.draw.ellipse(s, (30, 24, 16, 9), rr)
        _SHADOW[key] = s
    return s


_SCREE = {}


def _scree_tile(tile, mask, var):
    """Rock-scree ground with edges fading where the neighbour is not ring rock."""
    key = (tile, mask, var)
    s = _SCREE.get(key)
    if s is not None:
        return s
    import random
    rng = random.Random(var * 977 + 13)
    s = pygame.Surface((tile, tile), pygame.SRCALPHA)
    step = max(2, tile // 12)
    for yy in range(0, tile, step):
        for xx in range(0, tile, step):
            fx, fy = (xx + step / 2) / tile, (yy + step / 2) / tile
            d = 1.0
            if not mask & 1: d = min(d, fy * 1.6)          # N
            if not mask & 2: d = min(d, (1 - fx) * 1.6)    # E
            if not mask & 4: d = min(d, (1 - fy) * 1.6)    # S
            if not mask & 8: d = min(d, fx * 1.6)          # W
            d = max(0.0, min(1.0, d + rng.uniform(-0.3, 0.3)))
            v = rng.randint(-14, 14)
            c = (118 + v, 106 + v, 90 + v, int(225 * d))
            pygame.draw.rect(s, c, (xx, yy, step, step))
            if rng.random() < 0.12 and d > 0.3:
                pygame.draw.circle(s, (150 + v, 140 + v, 124 + v, int(240 * d)), (xx + step // 2, yy + step // 2), max(1, step // 2))
    _SCREE[key] = s
    return s


def ready(client):
    if getattr(client, "dungeon", None) or not getattr(client, "tiles", None):
        return False
    if int(getattr(client, "camera_yaw", 0)) % 4:
        return False
    if _img("peak_1") is None:
        return False
    VR.load_from_tiles(client.tiles)
    _rock_masses(client)
    return True


_ROCK = {}


def _rock_masses(client):
    """Plain WALL blocks on the south rim (ROCK_REGION) -> painted mountain, no new collision."""
    if "tiles" in _ROCK:
        return _ROCK["tiles"]
    import world_map as wm
    try:
        import fairy_glade as FG
    except Exception:
        FG = None
    tiles = client.tiles
    x0, y0, x1, y1 = VR.ROCK_REGION
    fps = getattr(wm, "_BUILDING_FOOTPRINTS", [])
    out = set()
    ex0, ey0, ex1, ey1 = VR.ROCK_EXTRA
    cells = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    cells += [(x, y) for y in range(ey0, ey1 + 1) for x in range(ex0, ex1 + 1)]
    for gx0, gy0, gx1, gy1 in VR.GLADE_CUT:      # hedge trunks whose trees the peaks replace
        cells += [(x, y) for y in range(gy0, gy1 + 1) for x in range(gx0, gx1 + 1)]
    for (x, y) in cells:
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
            if tiles[y][x] != wm.WALL:
                continue
            if any(a <= x <= c and b <= y <= d for a, b, c, d in fps):
                continue
            if FG is not None and (FG.is_trunk(x, y) or FG.is_lane(x, y)) and not VR.glade_tree_replaced(x, y):
                continue
            try:
                if wm.get_zone(x, y) == "city":
                    continue
            except Exception:
                pass
            out.add((x, y))
    _ROCK["tiles"] = out
    _ROCK["place"] = _rock_place(out)
    return out


def _rock_place(rock):
    """Peaks over the rock blocks: one every ~3 tiles inside, plus a front row on each south face."""
    import random
    rng = random.Random(7731)
    out = []
    def run(x, y):
        l = r = x
        while (l - 1, y) in rock:
            l -= 1
        while (r + 1, y) in rock:
            r += 1
        return l, r
    for (x, y) in sorted(rock, key=lambda t: (t[1], t[0])):
        face = (x, y + 1) not in rock
        inner = (y % 3 == 0) and ((x + (y // 3) % 2 * 2) % 3 == 0) and not face
        if not (inner or (face and x % 2 == 0)):
            continue
        l, r = run(x, y)
        span = r - l + 1
        w = max(3.2, min(7.0, span + 1.6)) * rng.uniform(0.85, 1.1)
        cx = x + 0.5 + rng.uniform(-0.3, 0.3)
        if span <= 5:
            cx = (l + r + 1) / 2.0 + rng.uniform(-0.3, 0.3)
        by = y + (1.05 if face else 1.0 + rng.uniform(0.0, 0.6))
        out.append((rng.choice(VR.PEAKS), cx, by, w, rng.random() < 0.5, rng.randrange(3)))
    # foothills along every south face: small peaks between the big ones
    for (x, y) in sorted(rock, key=lambda t: (t[1], t[0])):
        if (x, y + 1) in rock or x % 2 == 0:
            continue
        out.append((rng.choice(VR.LOW_PEAKS), x + 0.5 + rng.uniform(-0.3, 0.3), y + 1.25,
                    rng.uniform(3.0, 4.0), rng.random() < 0.5, rng.randrange(3)))
    # thin out duplicates on narrow columns (same centre, close rows)
    out.sort(key=lambda p: p[2])
    kept = []
    for p in out:
        if any(abs(p[1] - q[1]) < 1.2 and abs(p[2] - q[2]) < 0.6 for q in kept[-16:]):
            continue
        kept.append(p)
    return kept


def draw_ground(client, rect, wx, wy):
    """Cliff-base tiles under the painted peaks: meadow ground (the art covers them)."""
    if not ready(client) or not (VR.is_cliff(wx, wy) or (wx, wy) in _ROCK.get("tiles", ())):
        return False
    import world_map as wm
    client.draw_terrain_tile(rect, wm.GRASS, wx, wy, 0.0)
    rock = _ROCK.get("tiles", ())
    def r(x, y):
        return VR.is_cliff(x, y) or (x, y) in rock
    mask = r(wx, wy - 1) | r(wx + 1, wy) << 1 | r(wx, wy + 1) << 2 | r(wx - 1, wy) << 3
    try:
        client.screen.blit(_scree_tile(rect.width, mask, (wx * 7 + wy * 13) % 4), rect.topleft)
    except Exception:
        pass
    return True


def _scaled(name, w_px, flip, alpha=255, tint=0):
    key = (name, w_px, flip, alpha, tint)
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    src = _img(name)
    if src is None:
        return None
    h_px = max(1, int(src.get_height() * w_px / src.get_width()))
    img = pygame.transform.smoothscale(src, (w_px, h_px))
    if flip:
        img = pygame.transform.flip(img, True, False)
    if tint:
        img = img.copy()
        img.fill(TINTS[tint] + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    if alpha < 255:
        img = img.copy()
        img.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    if len(_SCALED) > 600:
        _SCALED.clear()
    _SCALED[key] = img
    return img


def _screen_xy(client, wx, wy, cam_x, cam_y, tile):
    ix, iy = int(math.floor(wx)), int(math.floor(wy))
    sx, sy = client.world_to_view_offset(ix, iy, cam_x, cam_y)
    return (sx + (wx - ix)) * tile, (sy + (wy - iy)) * tile


def _player_rect(client, cam_x, cam_y, tile):
    if not getattr(client, "player", None):
        return None
    px, py = client.player_xy()
    sx, sy = client.world_to_view_offset(int(px), int(py), cam_x, cam_y)
    sx += px - int(px); sy += py - int(py)
    return pygame.Rect(int(sx * tile), int(sy * tile - tile * 1.2), tile, int(tile * 2.2)), py


def _drop_old_cones(draw_list):
    """The old dark cliff cones (queued just before us) on tiles the ring now paints."""
    rock = _ROCK.get("tiles", ())
    keep = []
    for item in draw_list:
        d = getattr(item[2], "__defaults__", None) or ()
        if len(d) >= 4 and isinstance(d[2], int) and isinstance(d[3], int) and ((d[2], d[3]) in rock or VR.is_cliff(d[2], d[3])):
            continue
        keep.append(item)
    draw_list[:] = keep


_BD = {}


def _backdrop_piece(tile, h_tiles, x_frac, w_frac, flip, edge_fade):
    """A crop of the painted range (backdrop_1), scaled so it is h_tiles tall.
    edge_fade: feather the right edge (west slices) so no vertical seam shows."""
    key = (tile, h_tiles, x_frac, w_frac, flip, edge_fade)
    s = _BD.get(key)
    if s is not None:
        return s
    src = _img("backdrop_1")
    if src is None:
        return None
    sw, sh = src.get_size()
    crop = src.subsurface(pygame.Rect(int(sw * x_frac), 0, max(8, int(sw * w_frac)), sh)).copy()
    h_px = int(h_tiles * tile)
    w_px = max(4, crop.get_width() * h_px // sh)
    s = pygame.transform.smoothscale(crop, (w_px, h_px))
    if flip:
        s = pygame.transform.flip(s, True, False)
    if edge_fade:
        try:
            import numpy as np
            al = pygame.surfarray.pixels_alpha(s)
            xs = np.arange(w_px, dtype=np.float32)[:, None]
            ys = np.arange(h_px, dtype=np.float32)[None, :]
            wob = 0.10 * np.sin(ys / max(1, h_px) * 9.0 + x_frac * 20)
            f = np.clip((1.0 - xs / w_px) / 0.40 + wob, 0, 1)
            fl = np.clip(xs / w_px / 0.25 + wob, 0, 1)
            al[...] = (al * (f * f * (3 - 2 * f)) * (fl * fl * (3 - 2 * fl))).astype(np.uint8)
            del al
        except Exception:
            pass
    if len(_BD) > 200:
        _BD.clear()
    _BD[key] = s
    return s


def _queue_backdrop(client, draw_list, cam_x, cam_y, tile, view):
    """North: a continuous painted range along the map edge. West: overlapping
    slices of it stacked down the edge, so both read as solid as the east side."""
    items = []
    x = -2.0
    k = 0
    while x < 100:                       # north band, ~10 tiles per copy, mirrored alternately
        items.append((x, 3.7, 4.4, 0.0, 1.0, k % 2 == 1, False))
        x += 4.4 * 2.0 * 0.92
        k += 1
    for i, y in enumerate([2.5 + 1.5 * j for j in range(34)]):     # west slices
        items.append((-1.2 + (i % 3) * 0.35, y + 1.6, 4.2, (i * 0.23) % 0.62, 0.36, i % 2 == 1, True))
    for (lx, base, h, xf, wf, flip, fade) in items:
        img = _backdrop_piece(tile, h, xf, wf, flip, fade)
        if img is None:
            return
        bx, by = _screen_xy(client, lx, base, cam_x, cam_y, tile)
        pos = (int(bx), int(by - img.get_height()))
        r = pygame.Rect(pos, img.get_size())
        if not r.colliderect(view):
            continue

        def _draw(img=img, pos=pos):
            client.screen.blit(img, pos)
        draw_list.append((int(by - tile * 0.6), 0, _draw))


def queue(client, draw_list, cam_x, cam_y, tile, t=0.0):
    if not ready(client):
        return
    view = client.screen.get_rect()
    _drop_old_cones(draw_list)
    pr = _player_rect(client, cam_x, cam_y, tile)
    _queue_backdrop(client, draw_list, cam_x, cam_y, tile, view)
    for pl in list(VR.placements()) + _ROCK.get("place", []):
        name, cx, base_y, w_tiles, flip = pl[:5]
        tint = pl[5] if len(pl) > 5 else 0
        w_px = max(8, int(round(w_tiles * 2)) * tile // 2)
        img = _scaled(name, w_px, flip, 255, tint)
        if img is None:
            continue
        bx, by = _screen_xy(client, cx, base_y, cam_x, cam_y, tile)
        # art's foot (scree + pines / grass apron) sits a little above the image bottom
        top = int(by - img.get_height() * ANCHOR.get(name, 0.96))
        left = int(bx - img.get_width() / 2)
        r = pygame.Rect(left, top, img.get_width(), img.get_height())
        if not r.colliderect(view):
            continue
        faded = False
        if pr is not None and pr[1] < base_y and r.colliderect(pr[0]):
            lx, ly = pr[0].centerx - left, pr[0].centery - top
            if 0 <= lx < img.get_width() and 0 <= ly < img.get_height() and img.get_at((lx, ly)).a > 120:
                faded = True

        def _draw(name=name, w_px=w_px, flip=flip, pos=(left, top), faded=faded, tint=tint):
            im = _scaled(name, w_px, flip, 115 if faded else 255, tint)
            if im is not None:
                sh = _shadow(int(w_px * 0.9), max(4, int(w_px * 0.22)))
                client.screen.blit(sh, (pos[0] + (w_px - sh.get_width()) // 2,
                                        int(pos[1] + im.get_height() * ANCHOR.get(name, 0.96) - sh.get_height() * 0.6)))
                client.screen.blit(im, pos)
        draw_list.append((int(by - tile * 0.15), 0, _draw))
    try:
        import village_decor
        village_decor.queue(client, draw_list, cam_x, cam_y, tile, _screen_xy, pr)
    except Exception as exc:
        if not _STATE.get("decor_err"):
            print("[village_decor]", exc); _STATE["decor_err"] = True
    for kind, wx, wy in VR.props():
        name = {"tower": "prop_1", "pillar": "gate_2"}.get(kind, "prop_2")
        w_px = int(tile * {"tower": 2.6, "pillar": 1.9}.get(kind, 0.95))
        img = _scaled(name, w_px, False)
        if img is None:
            continue
        bx, by = _screen_xy(client, wx, wy, cam_x, cam_y, tile)
        left, top = int(bx - img.get_width() / 2), int(by - img.get_height() * ANCHOR.get(name, 0.97))
        r = pygame.Rect(left, top, img.get_width(), img.get_height())
        if not r.colliderect(view.inflate(tile * 2, tile * 2)):
            continue

        def _draw(img=img, pos=(left, top), kind=kind, w=img.get_width(), h=img.get_height()):
            client.screen.blit(img, pos)
            # flame flicker glow (torch cup ~top 10 %, tower bracket ~62 % down, 74 % across)
            fx, fy = {"torch": (0.5, 0.10), "pillar": (0.22, 0.42)}.get(kind, (0.73, 0.63))
            k = 0.75 + 0.25 * math.sin(time.time() * 9.0 + pos[0] * 0.13) * math.sin(time.time() * 5.3 + pos[1])
            rad = int(tile * (0.6 if kind == "torch" else 0.5) * k)
            if rad > 2:
                glow = _glow(rad)
                client.screen.blit(glow, (pos[0] + int(w * fx) - rad, pos[1] + int(h * fy) - rad),
                                   special_flags=pygame.BLEND_ADD)
        draw_list.append((int(by), 2, _draw))


_GLOW = {}


def _glow(rad):
    g = _GLOW.get(rad)
    if g is None:
        g = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
        for i in range(rad, 0, -1):
            a = int(34 * (1 - i / rad) ** 2.0)
            pygame.draw.circle(g, (255, 150, 60, a), (rad, rad), i)
        if len(_GLOW) > 40:
            _GLOW.clear()
        _GLOW[rad] = g
    return g


# ---- minimap ------------------------------------------------------------------
def minimap(client, surf, mm_w, mm_h, vw, vh):
    if not ready(client):
        return
    cells = set(VR._CACHE.get("cliff", ())) | set(VR.south_rock()) | set(_ROCK.get("tiles", ()))
    for (wx, wy) in cells:
        vx, vy = (wx, wy)
        x0, y0 = int(vx * mm_w / vw), int(vy * mm_h / vh)
        x1, y1 = max(x0 + 1, int((vx + 1) * mm_w / vw)), max(y0 + 1, int((vy + 1) * mm_h / vh))
        surf.fill((84, 82, 86), (x0, y0, x1 - x0, y1 - y0))
    # little grey peaks with snowy tips along the ring
    sx_, sy_ = mm_w / float(vw), mm_h / float(vh)
    for (wx, wy) in sorted(cells):
        if (wx * 7 + wy * 13) % 11 != 0:
            continue
        px, py = int((wx + 0.5) * sx_), int((wy + 1) * sy_)
        pygame.draw.polygon(surf, (112, 106, 100), [(px - 3, py + 1), (px, py - 3), (px + 3, py + 1)])
        pygame.draw.polygon(surf, (238, 240, 244), [(px - 1, py - 1), (px, py - 3), (px + 1, py - 1)])
    for _n, (ax, ay), _r in VR.PASSES:
        vx, vy = (ax, ay)
        px, py = int(vx * mm_w / vw), int(vy * mm_h / vh)
        pygame.draw.polygon(surf, (250, 214, 120), [(px, py - 3), (px + 3, py), (px, py + 3), (px - 3, py)])
        pygame.draw.polygon(surf, (70, 44, 20), [(px, py - 3), (px + 3, py), (px, py + 3), (px - 3, py)], 1)
    try:
        font = pygame.font.SysFont("arial", 8, bold=True)
        lab = font.render("Crownfall Vale", True, (240, 230, 200))
        vx, vy = (46, 6)
        lx = max(2, min(surf.get_width() - lab.get_width() - 2, int(vx * mm_w / vw) - lab.get_width() // 2))
        surf.blit(lab, (lx, int(vy * mm_h / vh)))
    except Exception:
        pass


# ---- banner -------------------------------------------------------------------
def banner_alpha(now, until):
    """0..255 for a banner that ends at `until` (fade in 0.4, hold 2.5, fade out 0.6)."""
    total = FADE_IN + HOLD + FADE_OUT
    age = total - (until - now)
    if age < 0 or age > total:
        return 0
    if age < FADE_IN:
        return int(255 * age / FADE_IN)
    if age < FADE_IN + HOLD:
        return 255
    return int(255 * max(0.0, (total - age) / FADE_OUT))


def _near_pass(x, y, pad=1):
    return any(x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad for _n, _a, (x0, y0, x1, y1) in VR.PASSES)


def track(client, now=None):
    """Banner only when the player WALKS in through a pass: the previous sample was
    outside the vale at a pass and the step was short. Spawn, login, teleport and
    death respawn (big jumps, or no previous sample) never fire it (31 Oct)."""
    now = time.time() if now is None else now
    if getattr(client, "dungeon", None) or not getattr(client, "player", None):
        _STATE["inside"] = None
        _STATE["pos"] = None
        return
    px, py = client.player_xy()
    ix, iy = int(px), int(py)
    inside = VR.in_vale(ix, iy)
    prev = _STATE.get("pos")
    walked = prev is not None and abs(prev[0] - ix) + abs(prev[1] - iy) <= 3
    if (_STATE["inside"] is False and inside and walked and _near_pass(*prev, pad=3)
            and _near_pass(ix, iy, pad=3) and now - _STATE["last"] >= COOLDOWN):
        _STATE["until"] = now + FADE_IN + HOLD + FADE_OUT
        _STATE["last"] = now
    elif not walked and prev is not None:
        _STATE["until"] = 0.0          # a jump cancels any banner in flight
    _STATE["inside"] = inside
    _STATE["pos"] = (ix, iy)


_AMB = {"snd": None, "chan": None, "vol": 0.0, "tried": False}
AMB_MAX = 0.10      # quiet: wind and birds under the music
AMB_RANGE = 6.0     # tiles from a pass anchor


def ambience(client):
    """Soft wind + birdsong near the passes, faded by distance (no file: silent)."""
    try:
        if not pygame.mixer.get_init():
            return
        if not _AMB["tried"]:
            _AMB["tried"] = True
            _AMB["snd"] = pygame.mixer.Sound(os.path.join(VR.ASSET_DIR, "pass_wind.wav"))
        snd = _AMB["snd"]
        if snd is None:
            return
        target = 0.0
        if not getattr(client, "dungeon", None) and getattr(client, "player", None):
            px, py = client.player_xy()
            d = min(math.hypot(px - ax, py - ay) for _n, (ax, ay), _r in VR.PASSES)
            if d < AMB_RANGE:
                target = AMB_MAX * (1.0 - d / AMB_RANGE)
        _AMB["vol"] += (target - _AMB["vol"]) * 0.05
        ch = _AMB["chan"]
        if _AMB["vol"] > 0.004:
            if ch is None or not ch.get_busy():
                _AMB["chan"] = ch = snd.play(loops=-1)
            if ch is not None:
                ch.set_volume(_AMB["vol"])
        elif ch is not None:
            ch.stop()
            _AMB["chan"] = None
    except Exception:
        _AMB["snd"] = None


def draw_banner(client):
    track(client)
    ambience(client)
    a = banner_alpha(time.time(), _STATE["until"])
    if a <= 0:
        return
    font = getattr(client, "font_label", None) or pygame.font.SysFont("georgia", 26, bold=True)
    text = font.render("Entering Crownfall Vale", True, (250, 238, 210))
    w, h = text.get_width() + 56, text.get_height() + 18
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (44, 34, 24, 215), panel.get_rect(), border_radius=12)
    pygame.draw.rect(panel, (222, 186, 110, 235), panel.get_rect(), 2, border_radius=12)
    panel.blit(text, (28, 9))
    for ox in (14, w - 14):
        pygame.draw.polygon(panel, (250, 214, 120), [(ox, h // 2 - 5), (ox + 5, h // 2), (ox, h // 2 + 5), (ox - 5, h // 2)])
    panel.set_alpha(a)
    map_w = min(client.screen.get_width(), 900)
    client.screen.blit(panel, ((map_w - w) // 2, 70))


RIM_FLOOR = (44, 52, 92, 72)


def draw_rim_floor(client, rect, tile_id, wx, wy):
    """Outdoor FLOOR on the south rim (the old maze flagstones next to the farm) -> dirt track."""
    import world_map as wm
    if tile_id != wm.FLOOR or getattr(client, "dungeon", None):
        return False
    x0, y0, x1, y1 = RIM_FLOOR
    if not (x0 <= wx <= x1 and y0 <= wy <= y1):
        return False
    if client.building_at_tile(wx, wy) is not None:
        return False
    try:
        if wm.get_zone(wx, wy) != "dungeon":
            return False
    except Exception:
        return False
    import village_ground
    return bool(village_ground.draw_world_path(client.screen, rect, wx, wy, client=client))
