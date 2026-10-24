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
                        bad[(wx, wy)] = (grid[wy][wx], wm.get_zone(wx, wy), round(float(dark), 2))
            del arr
    # Confirm each hit with the camera centred on it: a tile caught at the very
    # edge of a frame (half-drawn overlay, minimap border) is not a real hole.
    T = C.TILE
    for key in [k for k in bad if k[0] != "draw"]:
        wx, wy = key
        g.player["x"], g.player["y"] = wx, wy
        g.draw()
        cam_x, cam_y = g.camera_origin()
        sx, sy = g.world_to_view_offset(wx, wy, cam_x, cam_y)
        x0, y0 = int(sx * T), int(sy * T)
        blk = pygame.surfarray.array3d(g.screen)[x0:x0 + T, y0:y0 + T]
        mm = getattr(g, "minimap_rect", None)
        if mm is not None and mm.inflate(8, 8).colliderect(pygame.Rect(x0, y0, T, T)):
            del bad[key]          # under the minimap panel, not the world
            continue
        # UI panels stay put on screen while the world scrolls: re-render with
        # the camera nudged and, if this tile moved, check its new spot too.
        ui = False
        for dx, dy in ((-3, 0), (3, 0), (0, 3), (0, -3)):
            g.player["x"], g.player["y"] = wx + dx, wy + dy
            g.draw()
            cx2, cy2 = g.camera_origin()
            if (cx2, cy2) != (cam_x, cam_y):
                sx2, sy2 = g.world_to_view_offset(wx, wy, cx2, cy2)
                a, b = int(sx2 * T), int(sy2 * T)
                b2 = pygame.surfarray.array3d(g.screen)[a:a + T, b:b + T]
                if b2.size and not ((b2.max(axis=2) <= BLACK).mean() >= FRAC and float(b2.std()) < FLAT):
                    ui = True       # the same world tile draws fine elsewhere on screen
                break
        if ui:
            del bad[key]
            continue
        if blk.size == 0 or not ((blk.max(axis=2) <= BLACK).mean() >= FRAC and float(blk.std()) < FLAT):
            del bad[key]
            continue
        # Painted overlays (Wolf Pass massif) have deliberately dark shaded
        # rock faces. Re-render without the painting: if the ground under it
        # is fine, the dark pixels are the art, not a hole in the map.
        try:
            import wolf_pass_client as _wpc
        except Exception:
            _wpc = None
        if _wpc is not None:
            _q = _wpc.queue
            _wpc.queue = lambda *a, **k: None
            try:
                g.player["x"], g.player["y"] = wx, wy
                g.draw()
                b3 = pygame.surfarray.array3d(g.screen)[x0:x0 + T, y0:y0 + T]
            finally:
                _wpc.queue = _q
            if b3.size and not ((b3.max(axis=2) <= BLACK).mean() >= FRAC and float(b3.std()) < FLAT):
                del bad[key]
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
