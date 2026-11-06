"""Client renderer for the flag-gated Castle Realm."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pygame

import world_map as wm
import procedural_sprites_finished as sprites
import village_ground as vg

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE / "assets" / "castle_realm"
_CACHE = {}
_GATES = {}


def _json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_built():
    castles = {}
    floors = {}
    realm = _json(_ROOT / "json" / "castle_realm_map.json")
    for entry in realm.get("castles", []):
        if entry.get("status") != "built":
            continue
        path = _ROOT / "json" / entry.get("data", "")
        if not path.is_file():
            continue
        blob = _json(path)
        root = _ROOT / entry["id"]
        blob["_root"] = root
        castles[entry["id"]] = blob
        for floor in blob.get("floors", []):
            floor["_root"] = root
            floors[floor["plane"]] = floor
    return realm, castles, floors


REALM, CASTLE_DATA, FLOORS = _load_built()
REALM_ROWS = REALM.get("rows", [])
GOTHIC = CASTLE_DATA.get("gothic", {})


def ready():
    return any(_castle_ready(blob) for blob in CASTLE_DATA.values())


def _castle_ready(blob):
    root = blob.get("_root")
    return bool(root) and all((root / layer["file"]).is_file() for layer in blob.get("layers", []))


def _realm(client):
    return bool(client.dungeon and client.dungeon.get("id") == "castle_realm" and client.dungeon.get("plane") == "realm")


def _interior(client):
    return bool(client.dungeon and client.dungeon.get("id") == "castle_realm" and client.dungeon.get("plane") in FLOORS)


def _plane(client):
    return (client.dungeon or {}).get("plane", "realm")


def _surface(root, relative, tile):
    base = 80 if "/2x/" in str(relative) else 40
    key = (str(root), relative, int(tile))
    if key in _CACHE:
        return _CACHE[key]
    path = root / relative
    if not path.is_file() and "/2x/" in str(relative):
        path = root / str(relative).replace("/2x/", "/1x/")
        base = 40
    if not path.is_file():
        _CACHE[key] = None
        return None
    image = None
    # Painted HD layer (same geometry) beside the original; original = fallback.
    hd = path.with_name(path.stem + "_hd" + path.suffix)
    if hd.is_file():
        try:
            image = pygame.image.load(str(hd)).convert_alpha()
            if image.get_size() != pygame.image.load(str(path)).get_size():
                image = None
        except Exception as exc:
            print("[castle_realm] hd layer failed, using original:", hd.name, exc)
            image = None
    if image is None:
        image = pygame.image.load(str(path)).convert_alpha()
    image = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * tile / base)), max(1, round(image.get_height() * tile / base))))
    _CACHE[key] = image
    return image


def _gate_state(castle_id):
    return _GATES.setdefault(castle_id, {"frame": 0, "acc": 0.0, "dir": 0, "off_ms": None, "last": None})


def _siege_structures(client):
    d = getattr(client, "dungeon", None) or {}
    blob = d.get("crown_siege") or {}
    # Milestone 2 wraps structures under "structures"; older payloads were flat.
    if isinstance(blob.get("structures"), dict):
        return blob["structures"]
    return {k: v for k, v in blob.items() if k != "war" and isinstance(v, dict)}


def _siege_state(client, structure_id):
    row = _siege_structures(client).get(structure_id) or {}
    return str(row.get("state") or "intact")


# Fallback anchors matching server STRUCTURES (used when payload omits them).
_SIEGE_ANCHORS = {
    "watchtower": (120, 20),
    "armoury": (160, 40),
    "supply_depot": (140, 55),
}


def _siege_anchor(client, structure_id):
    row = _siege_structures(client).get(structure_id) or {}
    anchor = row.get("anchor")
    if isinstance(anchor, (list, tuple)) and len(anchor) >= 2:
        return int(anchor[0]), int(anchor[1])
    return _SIEGE_ANCHORS.get(structure_id)


def _queue_structure_scars(client, draw_list, cam_x, cam_y, tile):
    """Damage overlays for watchtower / armoury / supply depot on the realm."""
    screen = client.screen
    rects = getattr(client, "siege_scar_rects", None)
    if not isinstance(rects, dict):
        rects = {}
    client.siege_scar_rects = rects
    for sid in ("watchtower", "armoury", "supply_depot"):
        state = _siege_state(client, sid)
        if state == "intact":
            rects.pop(sid, None)
            continue
        anchor = _siege_anchor(client, sid)
        if not anchor:
            rects.pop(sid, None)
            continue
        ax, ay = anchor
        sx = int((ax - cam_x) * tile)
        sy = int((ay - cam_y) * tile)
        size = max(18, tile * 2)
        rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)
        rects[sid] = rect

        def _scar(r=rect, st=state, s=screen):
            _siege_overlay(s, r, st, cracks=True)

        draw_list.append((sy + size // 2, 44, _scar))


# Tint / alpha for structure damage overlays (no new siege paintings).
_SIEGE_TINT = {
    "intact": None,
    "damaged": ((70, 55, 40), 70),
    "heavily_damaged": ((45, 28, 18), 110),
    "destroyed": ((22, 14, 10), 160),
}


def _siege_overlay(screen, rect, state, cracks=False):
    """Darken and mark a castle sprite for the war damage band."""
    tint = _SIEGE_TINT.get(state)
    if not tint or rect.w < 4 or rect.h < 4:
        return
    colour, alpha = tint
    veil = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    veil.fill((*colour, alpha))
    if cracks or state in ("heavily_damaged", "destroyed"):
        for i in range(3 if state == "damaged" else 6):
            x0 = (i * 37 + 11) % max(1, rect.w - 2)
            y0 = (i * 23 + 7) % max(1, rect.h // 2)
            x1 = min(rect.w - 1, x0 + 18 + i * 4)
            y1 = min(rect.h - 1, y0 + 28 + i * 6)
            pygame.draw.line(veil, (12, 8, 6, 200), (x0, y0), (x1, y1), 2)
            pygame.draw.line(veil, (90, 70, 50, 120), (x0 + 1, y0), (x1 + 1, y1), 1)
    if state == "destroyed":
        rubble = pygame.Surface((rect.w, max(4, rect.h // 5)), pygame.SRCALPHA)
        rubble.fill((30, 22, 16, 200))
        for i in range(5):
            rx = (i * 29) % max(1, rect.w - 8)
            pygame.draw.ellipse(rubble, (50, 40, 30, 220), (rx, 2, 10, 6))
        veil.blit(rubble, (0, rect.h - rubble.get_height()))
    if state in ("heavily_damaged", "destroyed"):
        smoke = pygame.Surface((rect.w, max(6, rect.h // 3)), pygame.SRCALPHA)
        for i in range(4):
            sx = (i * 41 + 5) % max(1, rect.w - 12)
            pygame.draw.ellipse(smoke, (40, 40, 40, 70), (sx, i * 3, 14, 10))
        veil.blit(smoke, (0, 0))
    screen.blit(veil, rect.topleft)


def _gate_tiles(blob):
    result = set()
    for group in blob.get("trigger_tiles", {}).values():
        if isinstance(group, list):
            result.update((int(x), int(y)) for x, y in group)
    return result


def _gate_frame(castle_id, blob, px, py):
    state = _gate_state(castle_id)
    now = time.time() * 1000.0
    if state["last"] is None:
        state["last"] = now
    dt = max(0.0, min(80.0, now - state["last"]))
    state["last"] = now
    frames = blob.get("gate", {}).get("frames", [])
    if not frames:
        return 0
    delay = float(blob.get("gate", {}).get("close_delay_ms", 450))
    if (int(px), int(py)) in _gate_tiles(blob):
        state["off_ms"] = None
        state["dir"] = 1 if state["frame"] < len(frames) - 1 else 0
    else:
        state["off_ms"] = 0.0 if state["off_ms"] is None else state["off_ms"] + dt
        state["dir"] = -1 if state["off_ms"] >= delay and state["frame"] else 0
    if not state["dir"]:
        return state["frame"]
    state["acc"] += dt
    while state["dir"]:
        duration = float(frames[state["frame"]].get("ms", 80))
        if state["acc"] < duration:
            break
        state["acc"] -= duration
        nxt = state["frame"] + state["dir"]
        if nxt < 0 or nxt >= len(frames):
            state["frame"] = 0 if nxt < 0 else len(frames) - 1
            state["dir"] = 0
            break
        state["frame"] = nxt
    return state["frame"]


def _anim_frame(frames):
    """Loop an ambient frame list by each frame's ms value."""
    if not frames:
        return 0
    durations = [float(frame.get("ms", 110)) for frame in frames]
    total = sum(durations)
    if total <= 0:
        return 0
    cursor = (time.time() * 1000.0) % total
    acc = 0.0
    for index, duration in enumerate(durations):
        acc += duration
        if cursor < acc:
            return index
    return len(frames) - 1


def _inside_keep(blob, px, py):
    fp = blob.get("footprint") or {}
    rect = blob.get("keep_rect_local")
    if rect:
        x0 = int(fp.get("x0", 0)) + int(rect[0])
        y0 = int(fp.get("y0", 0)) + int(rect[1])
        x1 = int(fp.get("x0", 0)) + int(rect[2])
        y1 = int(fp.get("y0", 0)) + int(rect[3])
    else:
        x0, y0 = int(fp.get("x0", 0)), int(fp.get("y0", 0))
        x1, y1 = int(fp.get("x1", 0)), int(fp.get("y1", 0))
    return px is not None and x0 <= px <= x1 and y0 <= py <= y1


def _arena_hash(wx, wy, n=0):
    return (wx * 374761 + wy * 668265 + n * 127411) & 0xFFFF


def _draw_arena_sand(surf, rect, wx, wy):
    """Warm packed sand — grit, scuffs, and soft tone shifts under the pit overlay."""
    h = _arena_hash(wx, wy)
    tone = 10 + (h & 31)
    warm = (h >> 5) & 15
    base = [176 + tone, 142 + tone // 2 + warm // 3, 72 + tone // 3]
    # Packed lanes and darker tramp patches so the floor isn't flat ochre.
    if ((wx * 3 + wy * 5) % 11) in (0, 4):
        base[0] -= 16
        base[1] -= 12
        base[2] -= 6
    elif ((wx + wy * 2) % 9) == 2:
        base[0] = min(255, base[0] + 14)
        base[1] = min(255, base[1] + 10)
        base[2] = min(255, base[2] + 6)
    pygame.draw.rect(surf, tuple(base), rect)
    # Fine grit
    speck = (
        min(255, base[0] + 22),
        min(255, base[1] + 16),
        min(255, base[2] + 8),
    )
    dark = (max(0, base[0] - 28), max(0, base[1] - 22), max(0, base[2] - 12))
    r = max(1, rect.w // 12)
    if h & 1:
        pygame.draw.circle(surf, speck, (rect.centerx - 3, rect.centery + 2), r)
    if (h >> 2) & 3 == 0:
        pygame.draw.circle(surf, dark, (rect.centerx + 4, rect.centery - 2), max(1, r - 1))
    if (h >> 4) & 7 == 1:
        pygame.draw.line(
            surf, dark,
            (rect.left + 2, rect.centery + (h % 3) - 1),
            (rect.right - 2, rect.centery + ((h >> 3) % 3) - 1),
            1,
        )
    # Soft pebble
    if (h >> 8) & 15 == 3:
        pygame.draw.circle(
            surf, (150, 135, 110),
            (rect.left + 4 + (h % 5), rect.top + 3 + ((h >> 1) % 4)),
            max(1, rect.w // 16),
        )


def _draw_arena_ring(surf, rect, wx, wy):
    """Stone seating / ring — terraces, mortar, occasional crimson banner."""
    h = _arena_hash(wx, wy, 3)
    shade = 8 + (h & 19)
    # Alternate slightly cooler / warmer stone blocks.
    cool = (h >> 4) & 1
    base = (
        128 + shade - cool * 6,
        118 + shade // 2 - cool * 2,
        104 + shade // 3 + cool * 4,
    )
    pygame.draw.rect(surf, base, rect)
    # Mortar / seat risers
    mortar = (92, 84, 74)
    lip = (158, 148, 132)
    pygame.draw.line(surf, mortar, rect.topleft, rect.topright, 1)
    pygame.draw.line(surf, lip, (rect.left, rect.top + 1), (rect.right, rect.top + 1), 1)
    if (wy & 1) == 0:
        pygame.draw.line(surf, mortar, (rect.left, rect.centery), (rect.right, rect.centery), 1)
        pygame.draw.line(
            surf, (base[0] + 18, base[1] + 14, base[2] + 10),
            (rect.left, rect.centery + 1), (rect.right, rect.centery + 1), 1,
        )
    if (wx & 1) == 0:
        pygame.draw.line(surf, mortar, (rect.centerx, rect.top), (rect.centerx, rect.bottom), 1)
    # Crimson banner accents — match the campus art's red standards.
    if ((wx + wy * 3) % 13) == 0 and rect.w >= 8:
        bx = rect.centerx
        pygame.draw.line(surf, (70, 55, 40), (bx, rect.top + 2), (bx, rect.bottom - 2), 1)
        ban = pygame.Rect(bx - max(2, rect.w // 5), rect.top + 3, max(4, rect.w // 2), max(4, rect.h // 2))
        pygame.draw.rect(surf, (150, 38, 36), ban)
        pygame.draw.rect(surf, (190, 150, 50), ban, 1)


def _realm_grass(client, rect, wx, wy, t):
    """Painted meadow (ground_sheet via village_ground) with rounded pond shores; old tile on failure."""
    if vg.draw_world_grass(client.screen, rect, wx, wy, client=client):
        try:
            vg.draw_shore_land(client.screen, rect, wx, wy, t, client=client)
        except Exception:
            pass
        return
    sprites.draw_grass(client.screen, rect, wx, wy)


def draw_terrain_tile(client, rect, tile_id, wx, wy, t):
    if not (_realm(client) or _interior(client)):
        return False
    if _realm(client):
        char = REALM_ROWS[wy][wx] if 0 <= wy < len(REALM_ROWS) and 0 <= wx < len(REALM_ROWS[wy]) else "."
        if char == "T":
            _realm_grass(client, rect, wx, wy, t)     # tree itself is Y-sorted in queue()
        elif char == "~":
            if not vg.draw_world_water(client.screen, rect, wx, wy, t, client=client):
                sprites.draw_water_detailed(client.screen, rect, t, wx, wy)
        elif char == "s":
            if not _draw_arena_painted_tile(client.screen, rect, wx, wy, "sand_tile"):
                _draw_arena_sand(client.screen, rect, wx, wy)
        elif char == "A":
            if not _draw_arena_painted_tile(client.screen, rect, wx, wy, "ring_tile"):
                _draw_arena_ring(client.screen, rect, wx, wy)
        elif char in "=PSol":
            if not vg.draw_world_path(client.screen, rect, wx, wy, client=client):
                sprites.draw_path(client.screen, rect, wx, wy, zone="realm")
        else:
            _realm_grass(client, rect, wx, wy, t)
        return True
    if tile_id == wm.WATER:
        sprites.draw_water_detailed(client.screen, rect, t, wx, wy)
    elif tile_id == wm.WALL:
        sprites.draw_wall(client.screen, rect, "dungeon", wx, wy)
    else:
        sprites.draw_floor(client.screen, rect, wx, wy, zone="dungeon", interior=True)
    return True


def draw_floor_plane(client, cam_x, cam_y, tile):
    if not _interior(client):
        return
    plane = _plane(client)
    import castle_interiors_v2
    painted = castle_interiors_v2.draw(client, plane, cam_x, cam_y, tile)
    if not painted:
        floor = FLOORS[plane]
        relative = floor.get("sprite_1x" if tile <= 40 else "sprite_2x")
        image = _surface(floor.get("_root"), relative, tile) if relative else None
        if image is None:
            return
        sx, sy = client.world_to_view_offset(0, 0, cam_x, cam_y)
        origin = floor.get("origin_px_1x" if tile <= 40 else "origin_px_2x", (0, 0))
        scale = tile / (40.0 if tile <= 40 else 80.0)
        client.screen.blit(image, (sx * tile - origin[0] * scale, sy * tile - origin[1] * scale))
    # Great Hall shows keep damage as a soft veil over the map panel.
    if plane == "king_f1":
        dmg = _siege_state(client, "royal_keep")
        if dmg != "intact":
            try:
                import sys
                mod = sys.modules.get(type(client).__module__)
                mw = int(getattr(mod, "MAP_W", 900))
                mh = int(getattr(mod, "MAP_H", 640))
            except Exception:
                mw, mh = 900, 640
            _siege_overlay(client.screen, pygame.Rect(0, 0, mw, mh), dmg)


def return_portal_xy():
    portal = REALM.get("return_portal") or {}
    return int(portal.get("x", 150)), int(portal.get("y", 186))


def _colosseum_report(client, where, exc):
    """Visible failure: arena_colosseum.report (stderr traceback + log + chat line);
    if that module itself cannot load, print the full traceback here."""
    try:
        import arena_colosseum
        arena_colosseum.report(client, where, exc)
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)


def queue(client, draw_list, cam_x, cam_y, tile):
    if not _realm(client):
        return
    _queue_arena(client, draw_list, cam_x, cam_y, tile)
    try:
        import arena_colosseum  # crowd, pennants, fire, sand wear, dust, battle fx (5 Nov)
        arena_colosseum.queue(client, draw_list, cam_x, cam_y, tile, _arena_hd(), _arena_blob())
    except Exception as exc:  # keep the realm drawing, but report loudly (log + chat + traceback)
        client._colosseum_err = str(exc)
        _colosseum_report(client, "world layers", exc)
    _queue_trees(client, draw_list, cam_x, cam_y, tile)
    if not ready():
        return
    px, py = client.player_xy() if client.player else (None, None)
    for castle_id, blob in CASTLE_DATA.items():
        if not _castle_ready(blob):
            continue
        _queue_castle(client, draw_list, cam_x, cam_y, tile, castle_id, blob, px, py)


def _queue_trees(client, draw_list, cam_x, cam_y, tile):
    """Realm 'T' trees as Y-sorted sprites (31 Oct): drawn inside the tile pass, later
    ground tiles cut the canopy into a square patch."""
    import time
    t = time.time()
    view = client.screen.get_rect()
    x0, y0 = int(cam_x) - 2, int(cam_y) - 2
    x1, y1 = x0 + view.w // max(1, tile) + 5, y0 + view.h // max(1, tile) + 6
    for wy in range(max(0, y0), min(len(REALM_ROWS), y1)):
        row = REALM_ROWS[wy]
        for wx in range(max(0, x0), min(len(row), x1)):
            if row[wx] != "T":
                continue
            sx, sy = client.world_to_view_offset(wx, wy, cam_x, cam_y)
            cx, cy = int(sx * tile + tile // 2), int(sy * tile + tile // 2)

            def _draw(cx=cx, cy=cy, wx=wx, wy=wy):
                client.draw_resource_sprite("tree", cx, cy, t, wx=wx, wy=wy)
            draw_list.append((cy + tile // 3, 1, _draw))


def _arena_blob():
    return REALM.get("arena") or {}


_ARENA_META = None


def _arena_hd():
    """Painted HD arena block from arena/meta.json ({} when missing or broken)."""
    global _ARENA_META
    if _ARENA_META is None:
        try:
            _ARENA_META = (_json(_ROOT / "arena" / "meta.json").get("hd") or {})
        except (OSError, ValueError):
            _ARENA_META = {}
    return _ARENA_META


_ARENA_PATHS = {}


def _arena_hd_path(rel, tile):
    # Resolved once per (layer, res): this runs for every painted arena tile each
    # frame, and two stat() calls per tile were ~40% of a zoomed-out battle frame.
    res = "2x" if tile > 40 else "1x"
    hit = _ARENA_PATHS.get((rel, res), False)
    if hit is not False:
        return hit
    path = _ROOT / "arena" / rel.replace("{res}", res)
    if not path.is_file():
        path = _ROOT / "arena" / rel.replace("{res}", "1x")
    hit = path if path.is_file() else None
    _ARENA_PATHS[(rel, res)] = hit
    return hit


def _arena_hd_surface(kind, tile, target_w, target_h):
    """Painted HD arena layer, or None so the caller falls back to the old art."""
    rel = (_arena_hd().get("layers") or {}).get(kind)
    path = _arena_hd_path(rel, tile) if rel else None
    if path is None:
        return None
    key = ("arena_hd", str(path), int(tile), int(target_w), int(target_h))
    image = _CACHE.get(key)
    if image is None:
        try:
            raw = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, OSError):
            return None
        image = pygame.transform.smoothscale(raw, (max(1, int(target_w)), max(1, int(target_h))))
        if kind == "ground":
            try:
                _cut_pit_from_ground(image, tile)
            except Exception:
                pass  # keep the full painted ground if the mask can't be built
            try:
                _fade_ground_on_grass(image, tile)
            except Exception as exc:
                print("[castle_realm] ground fade", exc)
        _CACHE[key] = image
    return image


def _fade_ground_on_grass(image, tile):
    """The painted arena apron is a rectangle; over realm meadow ('.' / 'T') fade it out
    on a blurred, noisy contour so the grass meets it with a rounded edge (31 Oct)."""
    import numpy as np
    from scipy.ndimage import gaussian_filter, zoom
    art = _arena_hd().get("art_tiles") or []
    if len(art) < 4 or not REALM_ROWS:
        return
    w, h = image.get_size()
    ax, ay = float(art[0]), float(art[1])
    tx0, ty0 = int(np.floor(ax)) - 1, int(np.floor(ay)) - 1
    tw, th = int(np.ceil(w / tile)) + 3, int(np.ceil(h / tile)) + 3
    Q = 4
    m = np.zeros((tw, th), np.float32)
    for j in range(th):
        y = ty0 + j
        row = REALM_ROWS[y] if 0 <= y < len(REALM_ROWS) else ""
        for i in range(tw):
            x = tx0 + i
            ch = row[x] if 0 <= x < len(row) else "."
            m[i, j] = 1.0 if ch in ".T" else 0.0
    big = np.kron(m, np.ones((Q, Q), np.float32))
    f = gaussian_filter(big, Q * 0.85, mode="nearest")
    rng = np.random.default_rng(9127)
    n = gaussian_filter(rng.standard_normal(big.shape).astype(np.float32), Q * 1.2, mode="wrap")
    n /= max(1e-6, float(n.std()))
    f = f + 0.10 * n
    px = zoom(f, tile / Q, order=1)
    ox, oy = int(round((ax - tx0) * tile)), int(round((ay - ty0) * tile))
    sub = px[ox: ox + w, oy: oy + h]
    if sub.shape != (w, h):
        sub = np.pad(sub, ((0, max(0, w - sub.shape[0])), (0, max(0, h - sub.shape[1]))), mode="edge")[:w, :h]
    e = np.clip((sub - 0.40) / 0.22, 0.0, 1.0)
    keep = 1.0 - e * e * (3 - 2 * e)
    al = pygame.surfarray.pixels_alpha(image)
    al[...] = (al.astype(np.float32) * keep).astype(np.uint8)
    del al


def _cut_pit_from_ground(image, tile):
    """Fade the painted ground out over the sand pit ('s' tiles) so the crisp
    painted sand texture drawn per tile shows through in the fight view."""
    import numpy as np
    art = _arena_hd().get("art_tiles") or []
    if len(art) < 4:
        return
    w, h = image.get_size()
    sx, sy = w / float(art[2] - art[0]), h / float(art[3] - art[1])
    small = np.zeros((int(art[3] - art[1]) + 3, int(art[2] - art[0]) + 3), np.float32)
    x0, y0 = int(art[0]), int(art[1])
    for ty in range(small.shape[0]):
        row = REALM_ROWS[y0 + ty] if 0 <= y0 + ty < len(REALM_ROWS) else ""
        for tx in range(small.shape[1]):
            if 0 <= x0 + tx < len(row) and row[x0 + tx] == "s":
                small[ty, tx] = 1.0
    # erode one tile so the ring edge keeps the painted rim, then feather
    er = small.copy()
    er[1:-1, 1:-1] = np.minimum.reduce([small[1:-1, 1:-1], small[:-2, 1:-1], small[2:, 1:-1], small[1:-1, :-2], small[1:-1, 2:]])
    m = pygame.Surface((small.shape[1], small.shape[0]))
    pygame.surfarray.blit_array(m, np.repeat((er.T * 255).astype(np.uint8)[:, :, None], 3, axis=2))
    big = pygame.transform.smoothscale(m, (int(small.shape[1] * sx), int(small.shape[0] * sy)))
    big = pygame.transform.smoothscale(pygame.transform.smoothscale(big, (max(1, big.get_width() // 8), max(1, big.get_height() // 8))), big.get_size())
    ox, oy = int((x0 - art[0]) * sx), int((y0 - art[1]) * sy)
    cut = pygame.surfarray.array3d(big)[:, :, 0].astype(np.float32) / 255.0
    alpha = pygame.surfarray.pixels_alpha(image)
    cw, ch = min(alpha.shape[0] - max(0, ox), cut.shape[0]), min(alpha.shape[1] - max(0, oy), cut.shape[1])
    region = alpha[max(0, ox):max(0, ox) + cw, max(0, oy):max(0, oy) + ch]
    region[...] = (region * (1.0 - cut[:cw, :ch])).astype(np.uint8)
    del alpha


def _draw_arena_painted_tile(surf, rect, wx, wy, kind):
    """Blit a world-anchored window of the painted sand / ring texture."""
    rel = _arena_hd().get(kind)
    path = _arena_hd_path(rel, rect.w) if rel else None
    if path is None:
        return False
    key = ("arena_tex", str(path), int(rect.w))
    tex = _CACHE.get(key)
    if tex is None:
        try:
            raw = pygame.image.load(str(path)).convert()
        except (pygame.error, OSError):
            return False
        base = 40 if rect.w <= 40 else 80
        scale = rect.w / float(base)
        tex = pygame.transform.smoothscale(raw, (max(rect.w, int(raw.get_width() * scale)), max(rect.h, int(raw.get_height() * scale))))
        _CACHE[key] = tex
    tw, th = tex.get_size()
    ox, oy = (wx * rect.w) % tw, (wy * rect.h) % th
    # Draw the window piecewise so it wraps cleanly across the texture edge.
    x = 0
    while x < rect.w:
        sx = (ox + x) % tw
        w = min(rect.w - x, tw - sx)
        y = 0
        while y < rect.h:
            sy = (oy + y) % th
            h = min(rect.h - y, th - sy)
            surf.blit(tex, (rect.x + x, rect.y + y), pygame.Rect(sx, sy, w, h))
            y += h
        x += w
    return True


def _arena_layer_surface(name, tile, target_w, target_h):
    """Load a soft-edged arena layer (ground / back / front / gate), scaled to footprint."""
    use_2x = tile > 40
    rel = f"sprites/{'2x' if use_2x else '1x'}/{name}"
    path = _ROOT / "arena" / rel
    if not path.is_file():
        path = _ROOT / "arena" / f"sprites/1x/{name}"
    if not path.is_file():
        return None
    key = ("arena_layer", str(path), int(tile), int(target_w), int(target_h))
    image = _CACHE.get(key)
    if image is None:
        raw = pygame.image.load(str(path)).convert_alpha()
        image = pygame.transform.smoothscale(raw, (max(1, target_w), max(1, target_h)))
        _CACHE[key] = image
    return image


def _arena_gate_surface(open_: bool, tile):
    name = "arena_gate_open.png" if open_ else "arena_gate_closed.png"
    # Gates sit on ~3 tiles of sand between front and rear ranks.
    w = max(8, int(tile * 2.6))
    h = max(8, int(tile * 2.8))
    hd = _arena_hd_surface("gate_open" if open_ else "gate_closed", tile, w, h)
    return hd if hd is not None else _arena_layer_surface(name, tile, w, h)


def _queue_arena(client, draw_list, cam_x, cam_y, tile):
    """Draw Crownfall Arena in castle-style layers: ground, back wall, gates, front wall."""
    arena = _arena_blob()
    if not arena:
        return
    fp = arena.get("footprint") or [0, 0, 0, 0]
    x0, y0, x1, y1 = (int(fp[0]), int(fp[1]), int(fp[2]), int(fp[3]))
    if x1 <= x0 or y1 <= y0:
        return
    pit = arena.get("pit") or []
    px0 = py0 = px1 = py1 = None
    if len(pit) >= 4:
        px0, py0, px1, py1 = (int(pit[0]), int(pit[1]), int(pit[2]), int(pit[3]))

    target_w = max(1, (x1 - x0 + 1) * tile)
    target_h = max(1, (y1 - y0 + 1) * tile)
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    left, top = sx * tile, sy * tile
    # Sort rows: back wall behind the pit, front lip south of it (actors walk between).
    if px0 is not None:
        back_sy = client.world_to_view_offset(px0, py0 + 1, cam_x, cam_y)[1] * tile
        # Front wall sorts below the gate tunnel roof: actors in the passage (rows up to
        # front_sort_row) walk *under* the gatehouse, not over its roof.
        front_row = max(py1, int(arena.get("front_sort_row") or py1))
        front_sy = client.world_to_view_offset(px0, front_row, cam_x, cam_y)[1] * tile + tile
        mid_x = (px0 + px1) / 2.0
        mid_y = (py0 + py1) / 2.0
    else:
        back_sy = sy * tile
        front_sy = (sy + (y1 - y0)) * tile
        mid_x = (x0 + x1) / 2.0
        mid_y = (y0 + y1) / 2.0

    art = _arena_hd().get("art_tiles") or []
    ground = back = front = None
    if len(art) >= 4:
        # Painted HD bowl: its own world-tile rect (the walls rise past the footprint).
        aw = max(1, int(round((art[2] - art[0]) * tile)))
        ah = max(1, int(round((art[3] - art[1]) * tile)))
        hd = [_arena_hd_surface(k, tile, aw, ah) for k in ("ground", "back", "front")]
        if hd[1] is not None and hd[2] is not None:
            ground, back, front = hd
            asx, asy = client.world_to_view_offset(art[0], art[1], cam_x, cam_y)
            left, top = asx * tile, asy * tile
    if back is None:
        # Error fallback only: the old campus layers.
        ground = _arena_layer_surface("arena_ground.png", tile, target_w, target_h)
        back = _arena_layer_surface("arena_back.png", tile, target_w, target_h)
        front = _arena_layer_surface("arena_front.png", tile, target_w, target_h)

    # Fallback: old single campus plate if layers are missing.
    if ground is None and back is None and front is None:
        use_2x = tile > 40
        sprite = arena.get("sprite_2x" if use_2x else "sprite_1x") or arena.get("sprite_1x") or {}
        rel = sprite.get("file")
        if rel:
            path = (_ROOT / "arena" / rel)
            if path.is_file():
                key = ("arena_legacy", str(path), int(tile), x1 - x0, y1 - y0)
                image = _CACHE.get(key)
                if image is None:
                    raw = pygame.image.load(str(path)).convert_alpha()
                    image = pygame.transform.smoothscale(raw, (target_w, target_h))
                    _CACHE[key] = image
                draw_list.append((-10**9 + 50, 0, lambda img=image, l=left, t=top: client.screen.blit(img, (l, t))))
    else:
        if ground is not None:
            def _blit_ground(img=ground, l=left, t=top):
                client.screen.blit(img, (l, t))
            draw_list.append((-10**9 + 40, 0, _blit_ground))
        if back is not None:
            def _blit_back(img=back, l=left, t=top):
                client.screen.blit(img, (l, t))
            draw_list.append((back_sy, 40, _blit_back))
        if front is not None:
            def _blit_front(img=front, l=left, t=top):
                client.screen.blit(img, (l, t))
            # After actors (priority high) so the south lip occludes feet on the near rim.
            draw_list.append((front_sy, 45, _blit_front))

    # Reserve gates replace the old sports mid-line — closed until reserves join.
    match = getattr(client, "arena_match", None) or {}
    hud = match.get("hud") or {}
    gates_open = bool(hud.get("reserves_released") or match.get("reserves_released"))
    if px0 is not None:
        gate_img = _arena_gate_surface(gates_open, tile)
        if gate_img is not None:
            # West (your reserves) and east (foe reserves) between front / rear ranks.
            for gx, flip in ((mid_x - 8.0, False), (mid_x + 8.0, True)):
                gsx, gsy = client.world_to_view_offset(gx, mid_y, cam_x, cam_y)
                gcx = gsx * tile + tile // 2
                gfeet = gsy * tile + tile * 0.85
                img = pygame.transform.flip(gate_img, True, False) if flip else gate_img

                def _blit_gate(image=img, cx=gcx, feet=gfeet):
                    box = image.get_rect(midbottom=(int(cx), int(feet)))
                    client.screen.blit(image, box.topleft)

                draw_list.append((gfeet, 38, _blit_gate))

    label = arena.get("label") or arena.get("name") or "ARENA"
    cx = (x0 + x1) / 2.0
    cy = y0 + 2
    lsx, lsy = client.world_to_view_offset(cx, cy, cam_x, cam_y)
    south_row = client.world_to_view_offset(x0, y1, cam_x, cam_y)[1] * tile

    def _label(text=label, px=lsx * tile + tile // 2, py=lsy * tile):
        if getattr(client, "arena_match", None) and client.arena_match.get("active"):
            return
        font = getattr(client, "font", None) or pygame.font.Font(None, max(18, tile // 2))
        big = getattr(client, "font_large", None) or pygame.font.Font(None, max(28, int(tile * 0.85)))
        shadow = big.render(text, True, (20, 12, 4))
        glow = big.render(text, True, (255, 220, 90))
        rect = glow.get_rect(center=(int(px), int(py)))
        client.screen.blit(shadow, rect.move(2, 2))
        client.screen.blit(glow, rect)
        sub = font.render("Crownfall Arena", True, (255, 240, 180))
        client.screen.blit(sub, sub.get_rect(midtop=(rect.centerx, rect.bottom + 2)))

    draw_list.append((south_row + tile * 2, 5, _label))


def _queue_castle(client, draw_list, cam_x, cam_y, tile, castle_id, blob, px, py):
    fp = blob["footprint"]
    x0, y0, x1, y1 = int(fp["x0"]), int(fp["y0"]), int(fp["x1"]), int(fp["y1"])
    sx, sy = client.world_to_view_offset(x0, y0, cam_x, cam_y)
    sprite = blob.get("sprite_1x" if tile <= 40 else "sprite_2x") or blob.get("sprite_1x") or {}
    origin = sprite.get("origin_px", (0, 0))
    scale = tile / (40.0 if tile <= 40 or "sprite_2x" not in blob else 80.0)
    left, top = sx * tile - origin[0] * scale, sy * tile - origin[1] * scale
    root = blob["_root"]
    layers = {layer["name"]: layer["file"] for layer in blob.get("layers", [])}
    # A cutaway layer hides the roof of a keep you are standing inside.
    # Sky-Anchor has none: the keep is airborne, so the sort layer stays up.
    inside = _inside_keep(blob, px, py) and "cutaway" in layers
    # The 24-tile gothic keep stays one sprite sorted at its south edge.
    # A taller bailey, or a castle with sort layers, sorts the back wall at
    # the north edge so people in the yard draw in front of it. The gate,
    # posts and front lip stay at the south edge.
    if blob.get("sort_layers") or (y1 - y0) > 24:
        back_row = sy * tile
        south_row = (sy + (y1 - y0)) * tile
    else:
        back_row = (sy + 24) * tile
        south_row = back_row
    screen = client.screen

    def _blit(relative, x=left, y=top, n=tile, castle_root=root):
        image = _surface(castle_root, relative, n)
        if image is not None:
            screen.blit(image, (x, y))

    ground = layers.get("ground")
    if ground:
        draw_list.append((-10**9, 0, lambda g=ground: _blit(g)))
    back_name = "cutaway" if inside and "cutaway" in layers else "back"
    back = layers.get(back_name)
    if back:
        draw_list.append((back_row, 40, lambda g=back: _blit(g)))
    fountain = blob.get("fountain") or {}
    fountain_frames = fountain.get("frames") or []
    if fountain_frames:
        rel = fountain_frames[_anim_frame(fountain_frames)].get("file")
        crop = fountain.get("crop_1x") or (0, 0)
        fx = left + int(crop[0]) * scale
        fy = top + int(crop[1]) * scale
        tile_px = float(blob.get("tile_px") or 40)
        origin_y = float(origin[1]) if origin else 0.0
        if len(crop) >= 4:
            mid_y = (int(crop[1]) + int(crop[3])) / 2.0
        else:
            mid_y = float(crop[1])
        fountain_sy = sy + (mid_y - origin_y) / tile_px
        draw_list.append((fountain_sy * tile + tile // 2, 42, lambda g=rel, x=fx, y=fy: _blit(g, x, y)))
    posts = layers.get("posts")
    if posts:
        draw_list.append((south_row, 30, lambda g=posts: _blit(g)))
    frames = blob.get("gate", {}).get("frames", [])
    gate_damage = _siege_state(client, "outer_gate") if castle_id == "king" else "intact"
    keep_damage = _siege_state(client, "royal_keep") if castle_id == "king" else "intact"
    wall_w = _siege_state(client, "west_wall") if castle_id == "king" else "intact"
    wall_e = _siege_state(client, "east_wall") if castle_id == "king" else "intact"
    if frames:
        frame = _gate_frame(castle_id, blob, px or -1, py or -1)
        gate = frames[frame].get("file") or f"sprites/1x/gate/gate_{frame:02d}.png"
        crop = (blob.get("gate") or {}).get("crop_1x") or (0, 0)
        gx = left + int(crop[0]) * scale
        gy = top + int(crop[1]) * scale

        def _blit_gate(g=gate, x=gx, y=gy, dmg=gate_damage, castle_root=root, n=tile):
            image = _surface(castle_root, g, n)
            if image is None:
                return
            screen.blit(image, (x, y))
            _siege_overlay(screen, image.get_rect(topleft=(int(x), int(y))), dmg, cracks=True)

        draw_list.append((south_row, 41, _blit_gate))
    if castle_id == "king" and not inside:
        scar_rects = getattr(client, "siege_scar_rects", None)
        if not isinstance(scar_rects, dict):
            scar_rects = {}
            client.siege_scar_rects = scar_rects
        W = int((x1 - x0) * tile)
        H = int((y1 - y0) * tile)
        if wall_w != "intact":
            scar_rects["west_wall"] = pygame.Rect(
                int(left), int(top + H * 0.2), max(8, W // 5), max(8, H // 2)
            )
        else:
            scar_rects.pop("west_wall", None)
        if wall_e != "intact":
            scar_rects["east_wall"] = pygame.Rect(
                int(left + W * 0.75), int(top + H * 0.2), max(8, W // 5), max(8, H // 2)
            )
        else:
            scar_rects.pop("east_wall", None)
        if keep_damage != "intact":
            scar_rects["royal_keep"] = pygame.Rect(
                int(left + W * 0.28), int(top + H * 0.05),
                max(12, int(W * 0.44)), max(12, int(H * 0.45)),
            )
        else:
            scar_rects.pop("royal_keep", None)
        if frames and gate_damage != "intact":
            scar_rects["outer_gate"] = pygame.Rect(
                int(gx), int(gy), max(40, tile * 3), max(40, tile * 3)
            )
        else:
            scar_rects.pop("outer_gate", None)
    if castle_id == "king" and (wall_w != "intact" or wall_e != "intact"):
        # Soft scars on the bailey flanks without replacing wall art.
        def _wall_scars(ww=wall_w, we=wall_e, L=left, T=top, W=int((x1 - x0) * tile), H=int((y1 - y0) * tile)):
            if ww != "intact":
                _siege_overlay(screen, pygame.Rect(int(L), int(T + H * 0.2), max(8, W // 5), max(8, H // 2)), ww)
            if we != "intact":
                _siege_overlay(
                    screen,
                    pygame.Rect(int(L + W * 0.75), int(T + H * 0.2), max(8, W // 5), max(8, H // 2)),
                    we,
                )

        draw_list.append((south_row, 42, _wall_scars))
    if castle_id == "king" and keep_damage != "intact" and not inside:
        def _keep_scar(dmg=keep_damage, L=left, T=top, W=int((x1 - x0) * tile), H=int((y1 - y0) * tile)):
            # Keep sits in the northern half of the king footprint.
            _siege_overlay(
                screen,
                pygame.Rect(int(L + W * 0.28), int(T + H * 0.05), max(12, int(W * 0.44)), max(12, int(H * 0.45))),
                dmg,
                cracks=True,
            )

        draw_list.append((back_row + tile, 43, _keep_scar))
    if castle_id == "king" and not inside:
        # Watchtower / armoury / supply depot scars at their world anchors.
        _queue_structure_scars(client, draw_list, cam_x, cam_y, tile)
    if not inside:
        for sort_layer in blob.get("sort_layers", []):
            rel = sort_layer.get("file")
            sort_row = int(sort_layer.get("sort_row_world", y0))
            _sx, sort_sy = client.world_to_view_offset(x0, sort_row, cam_x, cam_y)
            sort_y = sort_sy * tile + tile // 2
            draw_list.append((sort_y, 35, lambda g=rel: _blit(g)))
        front = layers.get("front")
        if front:
            draw_list.append((10**9, 0, lambda g=front: _blit(g)))
    # Waterfalls sit with the floating rock, just after its sort layer.
    waterfall = blob.get("waterfall") or {}
    waterfall_frames = waterfall.get("frames") or []
    if waterfall_frames:
        rel = waterfall_frames[_anim_frame(waterfall_frames)].get("file")
        crop = waterfall.get("crop_1x") or (0, 0)
        wx = left + int(crop[0]) * scale
        wy = top + int(crop[1]) * scale
        sort_rows = [int(layer.get("sort_row_world", y0)) for layer in blob.get("sort_layers", [])]
        fall_row = max(sort_rows) if sort_rows else y0
        _sx, fall_sy = client.world_to_view_offset(x0, fall_row, cam_x, cam_y)
        draw_list.append((fall_sy * tile + tile // 2, 36, lambda g=rel, x=wx, y=wy: _blit(g, x, y)))


# keep in sync with server/safe_points.ARENA_GATE
ARENA_GATE_STAND = (196, 164)


def near_arena(client, reach: int = 8) -> bool:
    """True when the player stands on or beside the Crownfall Arena campus."""
    if not _realm(client) or not client.player:
        return False
    arena = _arena_blob()
    fp = arena.get("footprint") or []
    if len(fp) < 4:
        return False
    x0, y0, x1, y1 = map(int, fp[:4])
    px, py = client.player_xy()
    if (x0 - reach) <= px <= (x1 + reach) and (y0 - reach) <= py <= (y1 + reach):
        return True
    # The server parks players on the barracks foot outside the gate after a bout /
    # logout (server/safe_points.ARENA_GATE); that stand must reach Branna too.
    gx, gy = ARENA_GATE_STAND
    return abs(px - gx) <= 2 and abs(py - gy) <= 2


def draw_arena_prompt(client):
    """Bottom-centre chip while standing on the arena sand."""
    if not near_arena(client) or getattr(client, "show_barracks", False):
        client.arena_barracks_rect = None
        return
    font = client.font_small
    label = font.render("Crownfall Arena  ·  R Barracks / Practice", True, (255, 235, 160))
    pad_x, pad_y = 16, 8
    w, h = label.get_width() + pad_x * 2, label.get_height() + pad_y * 2
    rect = pygame.Rect(0, 0, w, h)
    rect.centerx = client.screen.get_width() // 2
    rect.bottom = client.screen.get_height() - 28
    pygame.draw.rect(client.screen, (28, 22, 12), rect, border_radius=8)
    pygame.draw.rect(client.screen, (220, 180, 70), rect, 2, border_radius=8)
    client.screen.blit(label, (rect.x + pad_x, rect.y + pad_y))
    client.arena_barracks_rect = rect


def _war_hud(client):
    d = getattr(client, "dungeon", None) or {}
    hud = d.get("crown_siege_hud")
    if isinstance(hud, dict):
        return hud
    blob = d.get("crown_siege") or {}
    if isinstance(blob, dict) and (blob.get("war") is not None or blob.get("heraldry") is not None):
        return {"war": blob.get("war"), "heraldry": blob.get("heraldry")}
    return {}


_OWNER_COLOUR = {
    "attack": (200, 90, 70),
    "defend": (70, 120, 200),
    "none": (140, 140, 150),
}


def draw_capture_markers(client):
    """World markers for capture points on the current castle plane."""
    hud = _war_hud(client)
    war = (hud or {}).get("war") if hud else None
    if not war or str(war.get("status") or "") != "active":
        return
    plane = _plane(client)
    caps = war.get("captures") or []
    if not caps:
        return
    font = getattr(client, "font_tiny", None) or client.font_small
    try:
        import client as _cmod
        tile = int(getattr(_cmod, "TILE", 40) or 40)
    except Exception:
        tile = 40
    if not hasattr(client, "camera_origin"):
        return
    try:
        cam_x, cam_y = client.camera_origin()
    except Exception:
        return
    for cap in caps:
        if cap.get("plane") != plane:
            continue
        rect = cap.get("rect") or []
        if len(rect) < 4:
            continue
        x0, y0, x1, y1 = [int(v) for v in rect]
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        sx = int((cx - cam_x) * tile)
        sy = int((cy - cam_y) * tile)
        owner = str(cap.get("owner") or "none")
        col = _OWNER_COLOUR.get(owner, _OWNER_COLOUR["none"])
        # Soft filled zone + border.
        zone = pygame.Rect(
            int((x0 - cam_x) * tile),
            int((y0 - cam_y) * tile),
            max(tile, int((x1 - x0 + 1) * tile)),
            max(tile, int((y1 - y0 + 1) * tile)),
        )
        overlay = pygame.Surface((zone.w, zone.h), pygame.SRCALPHA)
        overlay.fill((*col, 35))
        client.screen.blit(overlay, zone.topleft)
        pygame.draw.rect(client.screen, col, zone, 2)
        name = str(cap.get("name") or cap.get("id") or "?")
        prog = f"{int(cap.get('progress') or 0)}/{int(cap.get('need') or 0)}"
        bar = int(cap.get("barricades") or 0)
        lock = "" if cap.get("unlocked_for_attack", True) else " · locked"
        label = font.render(f"{name} · {owner} {prog}{lock}", True, (255, 235, 200))
        client.screen.blit(label, (sx - label.get_width() // 2, sy - 14))
        if bar:
            b = font.render(f"barricades {bar}", True, (255, 200, 120))
            client.screen.blit(b, (sx - b.get_width() // 2, sy + 2))


def draw_war_prompt(client):
    """Top-centre chip for an open / active War for the Crown."""
    client.war_chip_rect = None
    hud = _war_hud(client)
    war = hud.get("war") if hud else None
    heraldry = hud.get("heraldry") if hud else None
    if not war and not heraldry:
        return
    font = client.font_small
    parts = []
    if war:
        status = str(war.get("status") or "open")
        side = hud.get("side")
        bit = f"War for the Crown · {status}"
        if side:
            bit += f" · you: {side}"
        if hud.get("eliminated"):
            bit += " · eliminated"
        # Compact capture summary while the assault runs.
        caps = war.get("captures") or []
        if status == "active" and caps:
            held = sum(1 for c in caps if c.get("owner") == "attack")
            bit += f" · points {held}/{len(caps)}"
        if status == "scheduled" and war.get("scheduled_at"):
            delay = int(war.get("assault_delay") or 3600)
            left = max(0, int(float(war["scheduled_at"]) + delay - time.time()))
            bit += f" · assault in {left // 3600}h {(left % 3600) // 60}m"
        if status == "active":
            started = war.get("started_at") or war.get("scheduled_at")
            secs = int(war.get("assault_seconds") or 6 * 3600)
            if started:
                left = max(0, int(float(started) + secs - time.time()))
                bit += f" · {left // 3600}h {(left % 3600) // 60}m left"
        if status in ("registration", "scheduled"):
            # Surface the soonest confirm deadline so leaders see the 48h window.
            soonest = None
            for side in ("attack", "defend"):
                lead = ((war.get("sides") or {}).get(side) or {}).get("lead") or {}
                if lead.get("status") == "reserved" and lead.get("confirm_deadline"):
                    left = max(0, int(float(lead["confirm_deadline"]) - time.time()))
                    soonest = left if soonest is None else min(soonest, left)
            if soonest is not None:
                bit += f" · confirm {soonest // 3600}h {(soonest % 3600) // 60}m"
        if hud.get("watchtower_down"):
            bit += " · tower down"
        parts.append(bit)
    if heraldry and isinstance(heraldry.get("banner"), dict):
        charge = heraldry["banner"].get("charge") or "arms"
        parts.append(f"Royal banner: {charge}")
    if not parts:
        return
    label = font.render("  ·  ".join(parts), True, (255, 230, 170))
    pad_x, pad_y = 14, 7
    w, h = label.get_width() + pad_x * 2, label.get_height() + pad_y * 2
    rect = pygame.Rect(0, 0, w, h)
    rect.centerx = client.screen.get_width() // 2
    rect.top = 10
    pygame.draw.rect(client.screen, (24, 18, 28), rect, border_radius=8)
    pygame.draw.rect(client.screen, (200, 160, 70), rect, 2, border_radius=8)
    client.screen.blit(label, (rect.x + pad_x, rect.y + pad_y))
    client.war_chip_rect = rect
    if getattr(client, "show_war_board", False):
        draw_war_board(client, hud)


def draw_war_board(client, hud=None):
    """Clickable war board panel opened from the realm chip."""
    hud = hud if hud is not None else _war_hud(client)
    war = (hud or {}).get("war") or {}
    lines = list((hud or {}).get("board") or [])
    if not lines:
        # Compose a short board from the live war payload when board text
        # has not arrived yet (e.g. enter payload without a full HUD tick).
        status = str(war.get("status") or "open")
        lines = [f"War for the Crown — {status}"]
        for side in ("attack", "defend"):
            info = (war.get("sides") or {}).get(side) or {}
            lead = info.get("lead")
            if lead:
                mercs = int(lead.get("mercs") or 0)
                merc_bit = f", {mercs} mercs" if mercs else ""
                lines.append(
                    f"{side.title()}: {lead.get('name')} ({lead.get('status')}, "
                    f"{lead.get('humans', 0)}/{lead.get('human_min', 20)} humans{merc_bit})"
                )
            else:
                lines.append(f"{side.title()}: open")
            stock = info.get("store") or {}
            if stock:
                lines.append(
                    f"  Store: timber {stock.get('timber', 0)} · ore {stock.get('ore', 0)} · "
                    f"bars {stock.get('bars', 0)} · stone {stock.get('stone', 0)}"
                )
        contrib = war.get("contributors") or []
        if contrib:
            lines.append(
                "Top fighters: "
                + " · ".join(
                    f"{e.get('name')} {e.get('points', 0)}pts/{e.get('kills', 0)}k"
                    for e in contrib[:5]
                )
            )
        lines.append("Click the chip again or Esc to close. Herald: War for the Crown.")
    font = client.font_small
    tiny = getattr(client, "font_tiny", None) or font
    title = font.render("War Board", True, (255, 215, 90))
    rendered = [tiny.render(str(ln)[:78], True, (225, 225, 235)) for ln in lines[:18]]
    pad = 14
    body_h = sum(r.get_height() + 4 for r in rendered)
    box_w = max(
        420,
        title.get_width() + 80,
        max((r.get_width() for r in rendered), default=200) + pad * 2,
    )
    box_h = 40 + body_h + pad
    box = pygame.Rect(0, 0, box_w, box_h)
    box.centerx = client.screen.get_width() // 2
    box.top = 48
    pygame.draw.rect(client.screen, (22, 18, 28), box, border_radius=8)
    pygame.draw.rect(client.screen, (200, 160, 70), box, 2, border_radius=8)
    client.screen.blit(title, (box.x + pad, box.y + 10))
    close = tiny.render("Close", True, (255, 255, 255))
    close_r = pygame.Rect(box.right - close.get_width() - 18, box.y + 10,
                          close.get_width() + 12, close.get_height() + 4)
    pygame.draw.rect(client.screen, (60, 50, 40), close_r, border_radius=4)
    pygame.draw.rect(client.screen, (200, 200, 200), close_r, 1, border_radius=4)
    client.screen.blit(close, (close_r.x + 6, close_r.y + 2))
    y = box.y + 36
    for r in rendered:
        client.screen.blit(r, (box.x + pad, y))
        y += r.get_height() + 4
    client.war_board_rect = box
    client.war_board_close_rect = close_r


def war_board_click(client, mx, my):
    """Handle clicks on the war chip / board. True when the click was consumed."""
    if getattr(client, "show_war_board", False):
        close_r = getattr(client, "war_board_close_rect", None)
        box = getattr(client, "war_board_rect", None)
        if close_r and close_r.collidepoint(mx, my):
            client.show_war_board = False
            return True
        if box and box.collidepoint(mx, my):
            return True
        # Click outside closes.
        client.show_war_board = False
        chip = getattr(client, "war_chip_rect", None)
        if chip and chip.collidepoint(mx, my):
            return True
        return False
    chip = getattr(client, "war_chip_rect", None)
    if chip and chip.collidepoint(mx, my):
        client.show_war_board = True
        return True
    return False


def structure_scar_click(client, mx, my):
    """Click a damaged structure scar to examine HP / state. True if consumed."""
    rects = getattr(client, "siege_scar_rects", None) or {}
    if not isinstance(rects, dict) or not rects:
        return False
    structs = _siege_structures(client)
    # Prefer smaller / more specific scars first (tower over keep).
    hits = sorted(
        ((sid, r) for sid, r in rects.items() if r and r.collidepoint(mx, my)),
        key=lambda pair: pair[1].w * pair[1].h,
    )
    if not hits:
        return False
    sid, rect = hits[0]
    row = structs.get(sid) or {}
    name = row.get("name") or sid.replace("_", " ").title()
    state = str(row.get("state") or "intact").replace("_", " ")
    hp = int(row.get("hp") or 0)
    max_hp = int(row.get("max_hp") or 0)
    client.siege_examine = {
        "id": sid,
        "name": name,
        "state": state,
        "hp": hp,
        "max_hp": max_hp,
        "until": time.time() + 4.0,
        "x": mx,
        "y": my,
    }
    return True


def draw_siege_examine(client):
    """Floating label after clicking a damaged structure scar."""
    ex = getattr(client, "siege_examine", None)
    if not ex:
        return
    if time.time() > float(ex.get("until") or 0):
        client.siege_examine = None
        return
    font = getattr(client, "font_small", None)
    if font is None:
        return
    name = ex.get("name") or "Structure"
    state = ex.get("state") or "intact"
    hp = int(ex.get("hp") or 0)
    max_hp = int(ex.get("max_hp") or 0)
    pct = int(100 * hp / max(1, max_hp)) if max_hp else 0
    text = f"{name}: {state} ({hp}/{max_hp}, {pct}%)"
    label = font.render(text, True, (255, 230, 170))
    pad_x, pad_y = 10, 6
    box = pygame.Rect(0, 0, label.get_width() + pad_x * 2, label.get_height() + pad_y * 2)
    box.topleft = (int(ex.get("x") or 0) + 14, int(ex.get("y") or 0) + 14)
    screen = client.screen
    # Keep on screen.
    box.right = min(box.right, screen.get_width() - 8)
    box.bottom = min(box.bottom, screen.get_height() - 8)
    box.left = max(8, box.left)
    box.top = max(8, box.top)
    pygame.draw.rect(screen, (24, 18, 28), box, border_radius=6)
    pygame.draw.rect(screen, (200, 160, 70), box, 1, border_radius=6)
    screen.blit(label, (box.x + pad_x, box.y + pad_y))


def draw_overlay(client):
    if _realm(client):
        draw_capture_markers(client)
        draw_war_prompt(client)
        draw_siege_examine(client)
        draw_arena_prompt(client)
        return
    if not _interior(client):
        return
    draw_capture_markers(client)
    draw_war_prompt(client)
    draw_siege_examine(client)
    mx, my = pygame.mouse.get_pos()
    if mx >= 900 or my >= 640:
        return
    tile = client.screen_to_tile(mx, my)
    if not tile:
        return
    wx, wy = tile
    import castle_interiors_v2
    rooms = castle_interiors_v2.rooms(_plane(client))
    if rooms is None:
        rooms = FLOORS[_plane(client)].get("rooms", [])
    for room in rooms:
        x0, y0, x1, y1 = room["rect"]
        if x0 <= wx <= x1 and y0 <= wy <= y1:
            text = client.font_small.render(room.get("name", ""), True, (255, 230, 170))
            client.screen.blit(text, (mx + 12, my + 12))
            return