"""Arena soldier plates: side marks drawn as diamond shapes (no '◆◇' glyphs). Saves a proof."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); CLI = os.path.normpath(os.path.join(HERE, "..", "client"))
sys.path.insert(0, CLI); os.chdir(CLI)
import client, pygame
src = open(os.path.join(CLI, "client.py"), encoding="utf-8").read()
fails = []
def check(ok, m):
    print(("PASS " if ok else "FAIL ") + m); ok or fails.append(m)
check("◆" not in src and "◇" not in src, "no diamond glyphs left in client.py")
g = client.GameClient(); g.screen.fill((60, 70, 50))
g._defer_nameplates = False
a = g._draw_nameplate_now("\x00AArena Swordsman", 300, 100, (110, 200, 255))
e = g._draw_nameplate_now("\x00EArena Archer", 300, 150, (255, 110, 95))
old = g._draw_nameplate_now("◆ Arena Swordsman", 700, 100, (110, 200, 255))
g._draw_nameplate_now("◇ Arena Archer", 700, 150, (255, 110, 95))
px = g.screen.get_at((a.x + 13, a.centery))[:3]
check(px == (110, 200, 255), f"ally diamond filled in side colour {px}")
pe = g._draw_nameplate_now  # hollow: centre is panel colour, edge is side colour
c_in = g.screen.get_at((e.x + 13, e.centery))[:3]; c_edge = g.screen.get_at((e.x + 13, e.centery - 4))[:3]
check(c_in != (255, 110, 95) and c_edge == (255, 110, 95), f"enemy diamond hollow {c_in} {c_edge}")
check(abs(a.w - old.w) < 14, "plate width close to the old tag")
out = "/workspace/proofs/ui/arena_plates"
if os.path.isdir(out):
    shot = g.screen.subsurface((180, 70, 700, 110)).copy()
    pygame.image.save(pygame.transform.scale2x(shot), out + "/after_left_vs_old_glyph_right.png")
print("RESULT", "FAIL" if fails else "PASS"); os._exit(1 if fails else 0)
