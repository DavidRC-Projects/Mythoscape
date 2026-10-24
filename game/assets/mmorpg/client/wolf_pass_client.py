"""Wolf Pass painted massif on the client (MOUNTAIN_SPEC.md §3-§6).

L1 shadow decal (35 %) under the road, North Ridge queued behind entities, South Ridge queued in front
(fades to 40 % while it covers the player), minimap shape + "Wolf Pass" label. Only for camera yaw 0;
other yaws keep the old rock tiles. Ridge art is scaled once per tile size and cached.
"""
import os
import pygame

import wolf_pass as WP

_IMG = {}
_SCALED = {}


def active(client):
    return WP.enabled() and not getattr(client, "dungeon", None) and int(getattr(client, "camera_yaw", 0)) % 4 == 0


def _img(name):
    if name not in _IMG:
        try:
            _IMG[name] = pygame.image.load(os.path.join(WP.PACK, name)).convert_alpha()
        except Exception as exc:     # missing art: fall back to the old tiles
            print("[wolf_pass]", exc)
            _IMG[name] = None
    return _IMG[name]


def _scaled(which, tile):
    key = (which, tile)
    if key not in _SCALED:
        g = WP.geo()[which]
        src = _img(g["img"])
        if src is None:
            _SCALED[key] = None
        else:
            w_tiles = WP.geo()["x1"] - WP.geo()["x0"] + 1
            w = int(w_tiles * tile)
            h = int(src.get_height() * w / src.get_width())
            _SCALED[key] = pygame.transform.smoothscale(src, (w, h))
            # keep at most 2 zoom levels per ridge (texture budget)
            for k in [k for k in _SCALED if k[1] != tile][:-3]:
                _SCALED.pop(k, None)
    return _SCALED[key]


def draw_ground(client, rect, wx, wy):
    """Cliff tiles under the painted ridge: draw grass (the ridge art covers them). True when handled."""
    if not active(client) or not WP.is_cliff(wx, wy):
        return False
    # Same ground painter as the surrounding open tiles, so no rectangle shows where the ridge base feathers out.
    import world_map as wm
    client.draw_terrain_tile(rect, wm.GRASS, wx, wy, 0.0)
    return True


def _south_base_row():
    rows = [max(c[3]) for c in WP.geo()["cols"].values() if c and len(c) > 3 and c[3]]
    return max(rows) if rows else 28


def _origin(client, cam_x, cam_y, tile):
    sx, sy = client.world_to_view_offset(WP.geo()["x0"], 0, cam_x, cam_y)
    return sx * tile, sy * tile


def queue(client, draw_list, cam_x, cam_y, tile, t=0.0):
    if not active(client):
        return
    g = WP.geo()
    ox, oy = _origin(client, cam_x, cam_y, tile)
    scr = client.screen
    view = scr.get_rect()
    north = _scaled("north", tile)
    south = _scaled("south", tile)
    if north is None or south is None:
        return
    n_top = oy + g["north"]["top"] * tile
    s_top = oy + g["south"]["top"] * tile
    if n_top > view.bottom or s_top + south.get_height() < view.top or ox > view.right or ox + north.get_width() < view.left:
        return

    def _shadow():
        # L1: ridge cast shadow across the road (multiply 35 %), a soft band under the north base
        r0 = g["road"][0]
        band = _SCALED.get(("shadow", tile))
        if band is None:
            band = pygame.Surface((north.get_width(), int(tile * 2.2)), pygame.SRCALPHA)
            bw, bh = band.get_size()
            edge = max(1, int(tile * 4))
            for i in range(bh):
                for x0 in range(0, bw, 4):
                    fx = min(1.0, min(x0, bw - x0) / edge)
                    a = int(255 * g.get("shadow_alpha", 0.35) * (1 - i / bh) * fx)
                    band.fill((255 - a, 255 - a, 255 - int(a * 0.8), 255), (x0, i, 4, 1))
            _SCALED[("shadow", tile)] = band
        scr.blit(band, (ox, oy + r0 * tile - tile * 0.3), special_flags=pygame.BLEND_RGBA_MULT)

    def _north():
        scr.blit(north, (ox, n_top))

    def _south():
        img = south
        me = client.player_xy() if getattr(client, "player", None) else None
        if me is not None:
            psx, psy = client.world_to_view_offset(me[0], me[1], cam_x, cam_y)
            prect = pygame.Rect(int(psx * tile), int(psy * tile - tile * 1.2), tile, int(tile * 2.2))
            lx, ly = prect.centerx - int(ox), prect.top - int(s_top)
            covered = False
            if 0 <= lx < img.get_width():
                for yy in (ly, ly + tile // 2, ly + tile, ly + int(tile * 1.6)):
                    if 0 <= yy < img.get_height() and img.get_at((lx, yy)).a > 128:
                        covered = True
                        break
            if covered:
                faded = _SCALED.get(("south_fade", tile))
                if faded is None:
                    faded = img.copy()
                    faded.fill((255, 255, 255, int(255 * g.get("overhang_fade", 0.4))), special_flags=pygame.BLEND_RGBA_MULT)
                    _SCALED[("south_fade", tile)] = faded
                img = faded
        scr.blit(img, (ox, s_top))

    # North ridge base sits on the canyon's north edge: everything on the floor sorts after it.
    draw_list.append((-10 ** 6, -1, _shadow))
    draw_list.append((int(oy + (g["road"][0] - 0.6) * tile), 0, _north))
    # South ridge: foreground (L3) over anything on the canyon floor, but y-sorted at
    # its own base row so whatever stands south of the ridge (the castle and its
    # tower roofs) draws over the mountain instead of being cut off by it.
    draw_list.append((int(oy + (_south_base_row() + 1) * tile), 9, _south))


def minimap(client, surf, mm_w, mm_h, vw, vh):
    """One mountain shape: dark grey fill, white peak dots, brown road line, label."""
    if not WP.enabled() or int(getattr(client, "camera_yaw", 0)) % 4:
        return
    x0, y0, x1, y1 = WP.bounds()
    r0, r1 = WP.geo().get("road") or (14, 17)
    pts = []
    for wy in range(y0, y1 + 1):
        for wx in range(x0, x1 + 1):
            vx, vy = client.world_to_view(wx, wy)
            px0, py0 = int(vx * mm_w / vw), int(vy * mm_h / vh)
            px1, py1 = max(px0 + 1, int((vx + 1) * mm_w / vw)), max(py0 + 1, int((vy + 1) * mm_h / vh))
            if WP.blocked(wx, wy):
                col = (70, 70, 76)
            elif r0 <= wy <= r1:
                col = (132, 98, 62)
            else:
                continue
            surf.fill(col, (px0, py0, px1 - px0, py1 - py0))
            if WP.blocked(wx, wy) and (wx * 7 + wy * 13) % 29 == 0 and (wy < r0 - 5 or wy > r1 + 5):
                pts.append(((px0 + px1) // 2, (py0 + py1) // 2))
    for p in pts:
        surf.fill((236, 240, 246), (p[0], p[1], 2, 2))
    try:
        font = pygame.font.SysFont("arial", 10, bold=True)
        lab = font.render("Wolf Pass", True, (240, 230, 200))
        vx, vy = client.world_to_view((x0 + x1) // 2, y1 + 1)
        surf.blit(lab, (int(vx * mm_w / vw) - lab.get_width() // 2, int(vy * mm_h / vh)))
    except Exception:
        pass
