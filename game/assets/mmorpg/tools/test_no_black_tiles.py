"""Render the whole overworld through the real client draw path and fail if any
visible tile comes out black / empty (no ground drawn).

Run on every map change:  python3 tools/test_no_black_tiles.py
Headless (SDL dummy). Builds the world exactly as the server does, feeds the
client a WORLD_STATE, then sweeps the camera across the map in view-sized steps
and checks each on-screen world tile: a tile whose pixels are almost all near
black is reported with its coordinates, tile id and zone.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(ROOT, "client")
SERVER = os.path.join(ROOT, "server")
BLACK = 48          # max channel value that counts as "black"/bare dark wall
FLAT = 9            # ...and the tile is flat (no texture): empty, not dark art
FRAC = 0.80
# Zones whose painted art is deliberately dark (lava-cave rock fill and crater,
# mountain crevice shading, the Shadow crypt void theme, the unlit mine shaft).
# Reviewed by eye 24 Oct 2026; everything else must never be black.
DARK_ART_ZONES = {"dungeon", "mountains", "shadow_crypt", "mine"}         # a tile is empty when this share of it is black


def build():
    sys.path.insert(0, SERVER)
    import world_map as wm
    import content
    g = wm.generate_world()
    grid = g[0] if isinstance(g, tuple) else g
    return wm, content, grid


def main(verbose=True):
    wm, content, grid = build()
    if os.environ.get("NBT_GRID"):
        # Optional: a grid saved from another (e.g. older, still-running) server,
        # to prove the client never draws black even when server and client
        # disagree about the map.
        import json
        grid = json.load(open(os.environ["NBT_GRID"]))
    os.chdir(CLIENT)
    sys.path.insert(0, CLIENT)
    sys.argv = ["client.py"]
    import pygame
    import client as C
    C.GameClient._connect_stub = True
    g = C.GameClient()
    H, W = len(grid), len(grid[0])
    player = {"id": 1, "name": "Scan", "char_name": "Scan", "x": 10, "y": 10, "hp": 10, "max_hp": 10,
              "level": 1, "skills": {}, "inventory": [], "equipment": {}, "appearance": {}}
    g.player = dict(player)
    g.players = {}
    g.process_message({"type": "WORLD_STATE", "width": W, "height": H, "tiles": [r[:] for r in grid],
                       "npcs": [], "resources": {}, "interactables": [], "craft_recipes": {},
                       "buildings": list(getattr(content, "BUILDINGS", []))})
    g.state = "GAME"
    g.needs_appearance = False
    g.set_zoom_pct(100)
    bad = {}
    # view size in tiles
    vw = max(4, g.screen.get_width() // C.TILE - 8)
    vh = max(4, g.screen.get_height() // C.TILE - 6)
    import numpy as np
    for cy in range(vh // 2, H + vh // 2, vh):
        for cx in range(vw // 2, W + vw // 2, vw):
            g.player["x"], g.player["y"] = min(cx, W - 1), min(cy, H - 1)
            try:
                g.draw()
            except Exception as exc:          # a draw crash is a failure too
                bad[("draw", cx, cy)] = repr(exc)[:120]
                continue
            cam_x, cam_y = g.camera_origin()
            arr = pygame.surfarray.array3d(g.screen)
            sw, sh = g.screen.get_size()
            T = C.TILE
            for wy in range(max(0, cy - vh), min(H, cy + vh)):
                for wx in range(max(0, cx - vw), min(W, cx + vw)):
                    sx, sy = g.world_to_view_offset(wx, wy, cam_x, cam_y)
                    x0, y0 = int(sx * T), int(sy * T)
                    if x0 < 0 or y0 < 0 or x0 + T > sw or y0 + T > sh:
                        continue
                    if g.screen_point_is_ui(x0 + T // 2, y0 + T // 2) if hasattr(g, "screen_point_is_ui") else False:
                        continue
                    blk = arr[x0:x0 + T, y0:y0 + T]
                    dark = (blk.max(axis=2) <= BLACK).mean()
                    if dark >= FRAC and float(blk.std()) < FLAT:
                        if wm.get_zone(wx, wy) in DARK_ART_ZONES:
                            continue
                        # Style B fort sprites are tall 2.5D blits that shade
                        # plaza tiles north of the curtain — not empty ground.
                        if wm.get_zone(wx, wy) == "city" and any(
                            wm.is_stonehaven_fort_wall(wx + dx, wy + dy)
                            for dy in range(-1, 4)
                            for dx in range(-3, 4)
                        ):
                            continue
                        bad[(wx, wy)] = (grid[wy][wx], wm.get_zone(wx, wy), round(float(dark), 2))
            del arr
    # Confirm each hit while standing *beside* the tile — the player sprite
    # covers the cell underfoot and was a false "black tile" (dark outfit).
    T = C.TILE
    for key in [k for k in bad if k[0] != "draw"]:
        wx, wy = key
        ok = False
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (3, 1), (-3, -1)):
            g.player["x"], g.player["y"] = wx + dx, wy + dy
            g.draw()
            cam_x, cam_y = g.camera_origin()
            rect = g.map_screen_rect(wx, wy, cam_x, cam_y)
            x0, y0 = rect.x, rect.y
            if x0 < 0 or y0 < 0 or x0 + T > g.screen.get_width() or y0 + T > g.screen.get_height():
                continue
            mm = getattr(g, "minimap_rect", None)
            if mm is not None and mm.inflate(8, 8).colliderect(rect):
                ok = True          # under the minimap panel, not the world
                break
            blk = pygame.surfarray.array3d(g.screen)[x0:x0 + T, y0:y0 + T]
            if blk.size == 0:
                continue
            if not ((blk.max(axis=2) <= BLACK).mean() >= FRAC and float(blk.std()) < FLAT):
                ok = True          # tile draws fine when not under the avatar
                break
        if ok:
            del bad[key]
            continue
        # Still dark beside the player — keep as a real hole unless it is only
        # shaded by tall 2.5D art (massif / fort / house sprites).
        g.player["x"], g.player["y"] = wx + 2, wy
        overlays = []
        for mod_name in ("wolf_pass_client", "stonehaven_walls_client", "house_sprites"):
            try:
                overlays.append(__import__(mod_name))
            except Exception:
                pass
        saved = [(m, getattr(m, "queue", None)) for m in overlays if hasattr(m, "queue")]
        for m, _q in saved:
            m.queue = lambda *a, **k: None
        try:
            g.draw()
            cam_x, cam_y = g.camera_origin()
            rect = g.map_screen_rect(wx, wy, cam_x, cam_y)
            b3 = pygame.surfarray.array3d(g.screen)[rect.x:rect.x + T, rect.y:rect.y + T]
        finally:
            for m, q in saved:
                if q is not None:
                    m.queue = q
        if b3.size and not ((b3.max(axis=2) <= BLACK).mean() >= FRAC and float(b3.std()) < FLAT):
            del bad[key]
            continue
        if grid[wy][wx] == wm.WALL:
            del bad[key]  # solid wall tiles are meant to read dark
    return bad


if __name__ == "__main__":
    bad = main()
    tiles = {k: v for k, v in bad.items() if k[0] != "draw"}
    crashes = {k: v for k, v in bad.items() if k[0] == "draw"}
    for k, v in sorted(tiles.items(), key=lambda kv: (kv[0][1], kv[0][0]))[:400]:
        print("BLACK", k, v)
    for k, v in crashes.items():
        print("CRASH", k, v)
    print(f"{len(tiles)} black tiles, {len(crashes)} draw crashes")
    if bad:
        sys.exit(1)
    print("NO BLACK TILES TEST PASSED")
