"""King's Realm castle-gate sellers draw as HD painted sheets (player proportions), standee as fallback."""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(R + "/client"); sys.path[:0] = [R + "/client", R, R + "/server"]
import pygame; pygame.init(); pygame.display.set_mode((10, 10))
import player_hd_client as P, npc_hd_client as N, castle_owners_client as C, castle_owners
FAILS = []
def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok: FAILS.append(name)
ids = [s["npc_id"] for s in castle_owners.sellers()]
check("4 sellers", len(ids) == 4)
for i in ids:
    check(i + " in OVERWORLD_HD", i in N.OVERWORLD_HD)
    files = [os.path.join(N._DIR, i, f"sprite_{r}", f, f"f{k:02d}.png") for r in ("1x", "2x", "4x") for f in "senw" for k in range(8)]
    check(i + " 96 frames", all(os.path.isfile(p) for p in files))
    check(i + " draw_scale ~1", 0.9 <= float(N._meta(i).get("draw_scale") or 1) <= 1.1)
T = 60
def height(draw):
    s = pygame.Surface((300, 300), pygame.SRCALPHA); draw(s)
    rs = pygame.mask.from_surface(s, 200).get_bounding_rects()
    return max(r.bottom for r in rs) - min(r.top for r in rs), s
ph, _ = height(lambda s: P.draw_player(s, "male", P.get_default_appearance("male", starter=True), 150, 250, T, 0.0, anim="idle", facing="s", equipment={}, starter=True, fx_seed=None, fx_ctx={"is_self": False, "preview": True}))
class F: pass
by = {s["npc_id"]: s for s in castle_owners.sellers()}
for i in ids:
    c = F(); c.dungeon = {"plane": "realm"}; c.blit_nameplate = lambda *a, **k: None
    c.world_to_view_offset = lambda x, y, cx, cy: (x - cx, y - cy)
    def d(s, i=i, c=c):
        c.screen = s; dl = []
        C._queue_standee(c, dl, -2, -3, T, by[i], 0, 0)
        for e in dl: e[2]()
    h, _ = height(d)
    check(f"{i} player-proportion height {h} vs player {ph}", 0.85 * ph <= h <= 1.12 * ph)
# fallback: remove from HD set -> standee drawn (shorter, 90/40 tile)
N.OVERWORLD_HD.discard(ids[0])
c = F(); c.blit_nameplate = lambda *a, **k: None; c.world_to_view_offset = lambda x, y, cx, cy: (x - cx, y - cy)
def d0(s):
    c.screen = s; dl = []; C._queue_standee(c, dl, -2, -3, T, by[ids[0]], 0, 0); [e[2]() for e in dl]
h0, _ = height(d0)
check(f"standee fallback draws ({h0}px)", h0 > 0)
src = open(os.path.join(R, "client", "castle_owners_client.py")).read()
check("renderer calls npc_hd_client.draw_npc", "npc_hd_client.draw_npc" in src)
print("FAILS:", FAILS); sys.exit(1 if FAILS else 0)
