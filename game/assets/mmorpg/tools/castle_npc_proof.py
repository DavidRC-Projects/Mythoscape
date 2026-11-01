"""Before/after proof for the King's Realm castle-gate sellers: player M/F, then the 4 sellers via castle_owners_client."""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(R + "/client"); sys.path[:0] = [R + "/client", R, R + "/server"]
import pygame; pygame.init(); pygame.display.set_mode((10, 10))
import player_hd_client as P, npc_hd_client as N, castle_owners_client as C, castle_owners
OUT, MODE = sys.argv[1], sys.argv[2]   # MODE before|after
T = int(os.environ.get("T", "60"))
ids = ["marcelline_shade_broker", "seraphine_rose_seneschal", "veyra_skychain", "aldric_crownvale"]
if MODE == "before":
    for i in ids: N.OVERWORLD_HD.discard(i)
cw = int(T * 3.6); W = cw * 6; H = int(T * 3.6); feet = int(T * 3.0)
scr = pygame.Surface((W, H)); scr.fill((92, 116, 70))
for x in range(0, W, T):
    for y in range(0, H, T):
        pygame.draw.rect(scr, (86, 110, 66), (x, y, T, T), 1)
f = pygame.font.Font(None, 22)
class Fake:
    pass
c = Fake(); c.screen = scr; c.dungeon = {"plane": "realm"}
c.blit_nameplate = lambda text, x, y, col=(255, 255, 255), *a, **k: (lambda s: scr.blit(s, (x - s.get_width() // 2, y)))(f.render(text, True, col))
c.world_to_view_offset = lambda x, y, cx, cy: (x - cx, y - cy)
for i, sex in enumerate(("male", "female")):
    P.draw_player(scr, sex, P.get_default_appearance(sex, starter=True), i * cw + cw // 2, feet, T, 0.0, anim="idle", facing="s", equipment={}, starter=True, fx_seed=None, fx_ctx={"is_self": False, "preview": True})
    scr.blit(f.render("player " + sex[0].upper(), True, (20, 20, 20)), (i * cw + 6, H - 20))
by = {s["npc_id"]: s for s in castle_owners.sellers()}
dl = []
for k, i in enumerate(ids):
    col = k + 2
    # place so feet tile centre lands at column centre: cx = vx*T+T/2
    vx = (col * cw + cw // 2 - T // 2) / T; vy = (feet - T) / T
    C._queue_standee(c, dl, -vx, -vy, T, by[i], 0, 0)
    scr.blit(f.render(i.split("_")[0], True, (20, 20, 20)), (col * cw + 6, H - 20))
for _, _, d in sorted(dl, key=lambda e: e[0]): d()
pygame.draw.line(scr, (180, 40, 40), (0, feet), (W, feet), 1)
pygame.image.save(scr, OUT); print("saved", OUT)
