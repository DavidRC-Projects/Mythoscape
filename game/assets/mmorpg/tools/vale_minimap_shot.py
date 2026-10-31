"""Offscreen minimap proof for the Crownfall Vale ring (box-only tool).
usage: python3 tools/vale_minimap_shot.py OUT.png [crop x0 y0 x1 y1 in tiles]"""
import os, sys
__file__ = os.path.abspath(__file__); ARGV = list(sys.argv)
_src = open(os.path.join(os.path.dirname(__file__), "village_shot.py")).read().split("jobs =")[0]
exec(compile(_src, os.path.join(os.path.dirname(__file__), "village_shot.py"), "exec"))
out = ARGV[1]
g.rebuild_minimap_base()
surf = g._minimap_base
mw, mh = g._minimap_size
W, H = len(g.tiles[0]), len(g.tiles)
crop = [int(v) for v in ARGV[2:6]] if len(ARGV) >= 6 else [0, 0, W, H]
x0, y0, x1, y1 = crop
r = pygame.Rect(int(x0 * mw / W), int(y0 * mh / H), int((x1 - x0) * mw / W), int((y1 - y0) * mh / H))
sub = surf.subsurface(r.clip(surf.get_rect())).copy()
sub = pygame.transform.scale(sub, (sub.get_width() * 4, sub.get_height() * 4))
pygame.image.save(sub, out); print("saved", out, surf.get_size(), sub.get_size())
