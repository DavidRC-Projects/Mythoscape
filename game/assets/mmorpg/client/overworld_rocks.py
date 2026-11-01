"""Painted rock outcrops for the overworld mountain WALL tiles (art only, collision unchanged).

Reuses the Crownfall Vale ring kit (assets/vale_ring peaks, softened feet, scree ground):
each connected WALL mass in the "mountains" zone gets Y-sorted painted peaks, and its tiles
get meadow + rounded scree ground so the mass reads as one rocky outcrop, never squares.
Missing art or a failure -> False, and the old tile painter runs.
"""
import random

import pygame

_S = {}


def _rocks(client):
    if "tiles" in _S:
        return _S["tiles"]
    import world_map as wm
    try:
        import wolf_pass as WP
        wp = WP.is_cliff if WP.enabled() else (lambda x, y: False)
    except Exception:
        wp = lambda x, y: False
    import vale_ring_client as VRC
    vale = VRC._ROCK.get("tiles", set())
    fps = getattr(wm, "_BUILDING_FOOTPRINTS", [])
    tiles = client.tiles
    out = set()
    for y in range(len(tiles)):
        row = tiles[y]
        for x in range(len(row)):
            if row[x] != wm.WALL or (x, y) in vale or wp(x, y):
                continue
            if any(a <= x <= c and b <= y <= d for a, b, c, d in fps):
                continue
            try:
                if wm.get_zone(x, y) != "mountains":
                    continue
            except Exception:
                continue
            out.add((x, y))
    _S["tiles"] = out
    _S["place"] = _place(out)
    _S["grid"] = {}
    for p in _S["place"]:
        _S["grid"].setdefault((int(p[1]) // 8, int(p[2]) // 8), []).append(p)
    return out


def _place(rock):
    import vale_ring as VR
    rng = random.Random(4417)
    seen, comps = set(), []
    for t in sorted(rock):
        if t in seen:
            continue
        st, comp = [t], []
        seen.add(t)
        while st:
            c = st.pop()
            comp.append(c)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if n in rock and n not in seen:
                    seen.add(n)
                    st.append(n)
        comps.append(comp)
    out = []
    for comp in comps:
        cs = set(comp)
        if len(comp) <= 3:                       # lone boulders -> one low outcrop
            cx = sum(c[0] for c in comp) / len(comp) + 0.5
            by = max(c[1] for c in comp) + 1.05
            out.append((rng.choice(VR.LOW_PEAKS), cx, by, 1.8 + 0.5 * len(comp), rng.random() < 0.5, rng.randrange(3)))
            continue
        for (x, y) in sorted(comp, key=lambda t: (t[1], t[0])):
            face = (x, y + 1) not in cs
            inner = (y % 3 == 0) and ((x + (y // 3) % 2 * 2) % 3 == 0) and not face
            if not (inner or (face and x % 2 == 0)):
                continue
            l = r = x
            while (l - 1, y) in cs:
                l -= 1
            while (r + 1, y) in cs:
                r += 1
            span = r - l + 1
            w = max(2.6, min(6.5, span + 1.4)) * rng.uniform(0.85, 1.1)
            cx = (l + r + 1) / 2.0 if span <= 4 else x + 0.5 + rng.uniform(-0.3, 0.3)
            by = y + (1.05 if face else 1.0 + rng.uniform(0.0, 0.5))
            out.append((rng.choice(VR.PEAKS if span > 4 else VR.LOW_PEAKS), cx, by, w, rng.random() < 0.5, rng.randrange(3)))
        for (x, y) in comp:                      # foothills on the south faces
            if (x, y + 1) in cs or x % 2 == 0:
                continue
            out.append((rng.choice(VR.LOW_PEAKS), x + 0.5, y + 1.2, rng.uniform(2.2, 3.2), rng.random() < 0.5, rng.randrange(3)))
    out.sort(key=lambda p: p[2])
    kept = []
    for p in out:
        if any(abs(p[1] - q[1]) < 1.1 and abs(p[2] - q[2]) < 0.6 for q in kept[-24:]):
            continue
        kept.append(p)
    return kept


def ready(client):
    import vale_ring_client as VRC
    return VRC.ready(client)


def draw_ground(client, rect, wx, wy):
    try:
        if not ready(client) or (wx, wy) not in _rocks(client):
            return False
        import world_map as wm
        import vale_ring_client as VRC
        client.draw_terrain_tile(rect, wm.GRASS, wx, wy, 0.0)
        rk = _S["tiles"]
        mask = ((wx, wy - 1) in rk) | ((wx + 1, wy) in rk) << 1 | ((wx, wy + 1) in rk) << 2 | ((wx - 1, wy) in rk) << 3
        client.screen.blit(VRC._scree_tile(rect.width, mask, (wx * 7 + wy * 13) % 4), rect.topleft)
        return True
    except Exception as exc:
        print("[overworld_rocks]", exc)
        return False


def queue(client, draw_list, cam_x, cam_y, tile, t=0.0):
    if not ready(client):
        return
    import vale_ring_client as VRC
    _rocks(client)
    view = client.screen.get_rect()
    # visible world window (yaw 0): cam is view-space == world-space
    vw, vh = view.w // tile + 2, view.h // tile + 2
    gx0, gy0 = (int(cam_x) - 8) // 8, (int(cam_y) - 4) // 8
    gx1, gy1 = (int(cam_x) + vw + 8) // 8, (int(cam_y) + vh + 12) // 8
    rock = _S["tiles"]
    keep = []
    for item in draw_list:                      # drop old cones queued for these tiles
        d = getattr(item[2], "__defaults__", None) or ()
        if len(d) >= 4 and isinstance(d[2], int) and isinstance(d[3], int) and (d[2], d[3]) in rock:
            continue
        keep.append(item)
    draw_list[:] = keep
    pr = VRC._player_rect(client, cam_x, cam_y, tile)
    for gy in range(gy0, gy1 + 1):
        for gx in range(gx0, gx1 + 1):
            for (name, cx, base_y, w_tiles, flip, tint) in _S["grid"].get((gx, gy), ()):
                w_px = max(8, int(round(w_tiles * 2)) * tile // 2)
                img = VRC._scaled(name, w_px, flip, 255, tint)
                if img is None:
                    continue
                bx, by = VRC._screen_xy(client, cx, base_y, cam_x, cam_y, tile)
                anc = VRC.ANCHOR.get(name, 0.96)
                top = int(by - img.get_height() * anc)
                left = int(bx - img.get_width() / 2)
                r = pygame.Rect(left, top, img.get_width(), img.get_height())
                if not r.colliderect(view):
                    continue
                faded = False
                if pr is not None and pr[1] < base_y and r.colliderect(pr[0]):
                    lx, ly = pr[0].centerx - left, pr[0].centery - top
                    if 0 <= lx < img.get_width() and 0 <= ly < img.get_height() and img.get_at((lx, ly)).a > 120:
                        faded = True

                def _draw(name=name, w_px=w_px, flip=flip, pos=(left, top), faded=faded, tint=tint, anc=anc):
                    im = VRC._scaled(name, w_px, flip, 115 if faded else 255, tint)
                    if im is not None:
                        sh = VRC._shadow(int(w_px * 0.9), max(4, int(w_px * 0.22)))
                        client.screen.blit(sh, (pos[0] + (w_px - sh.get_width()) // 2,
                                                int(pos[1] + im.get_height() * anc - sh.get_height() * 0.6)))
                        client.screen.blit(im, pos)
                draw_list.append((int(by - tile * 0.15), 0, _draw))
