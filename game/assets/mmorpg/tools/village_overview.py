"""Stitch a full-village overview from area-view shots (box-only proof tool).
usage: python3 tools/village_overview.py OUT.png [x0 y0 x1 y1] [step]"""
import os, sys
args = sys.argv[1:]
os.environ["VSHOTS"] = ""
sys.argv = [sys.argv[0]]
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "village_shot.py")).read())
out = args[0]
x0, y0, x1, y1 = (int(a) for a in (args[1:5] if len(args) >= 5 else (0, 0, 112, 60)))
g._set_area_view(True); g._pump_zoom(); g.draw(); g.draw_minimap = lambda *a, **k: None
T = C.TILE
canvas = pygame.Surface(((x1 - x0 + 1) * T, (y1 - y0 + 1) * T))
best = {}
SAFE = pygame.Rect(130, 60, 660, 520)   # world area clear of HUD panels (1200x800 screen)
BIG = pygame.Rect(0, 0, 900, 800)
step = int(args[5]) if len(args) > 5 else 8
for cy in range(y0, y1 + step, step):
    for cx in range(x0, x1 + step, step):
        g.player["x"], g.player["y"] = cx, cy
        g.draw_map()
        cam_x, cam_y = g.camera_origin()
        for wy in range(y0, y1 + 1):
            for wx in range(x0, x1 + 1):
                r = g.map_screen_rect(wx, wy, cam_x, cam_y)
                if SAFE.contains(r):
                    d = abs(r.centerx - SAFE.centerx) + abs(r.centery - SAFE.centery)
                elif BIG.contains(r):
                    d = 5000 + abs(r.centerx - SAFE.centerx) + abs(r.centery - SAFE.centery)
                else:
                    continue
                if d < best.get((wx, wy), 1e9):
                    best[(wx, wy)] = d
                    canvas.blit(g.screen, ((wx - x0) * T, (wy - y0) * T), r)
pygame.image.save(canvas, out)
print("overview", out, canvas.get_size(), "T", T, "missing", (x1-x0+1)*(y1-y0+1)-len(best))
