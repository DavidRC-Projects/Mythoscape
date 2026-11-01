"""Stats screen v2 proofs -> /workspace/proofs/ui/stats_screen/ (box or Mac; SS_OUT sets the folder)."""
import os, sys, shutil
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame
import stats_screen_v2 as S
from client_screens import STAT_PRESETS
import client as C
OUT = os.environ.get("SS_OUT", "/workspace/proofs/ui/stats_screen"); os.makedirs(OUT, exist_ok=True)
_before = "/workspace/crownfall/ONBOARDING/stats_screen/stats_current.png"
if os.path.isfile(_before):                       # box only; the Mac run skips it
    shutil.copy(_before, OUT + "/before_current.png")
C.GameClient._connect_stub = True
g = C.GameClient()
g.player = {"id": 1, "name": "54545454455"}
g.state = "STAT_ALLOC"; g.stat_gender = "male"; g.stat_alloc_error = ""; g.login_error = ""
g.stat_alloc_base = {"attack": 5, "strength": 5, "defence": 5, "archery": 1}
Z = lambda: {"attack": 0, "strength": 0, "defence": 0, "archery": 0}
def shot(name, w=1200, h=800):
    g.screen = pygame.Surface((w, h)); S.draw(g); pygame.image.save(g.screen, f"{OUT}/{name}.png"); print("saved", name)
g.stat_alloc = Z(); shot("after_fresh_10_left")
S.apply_preset(g, STAT_PRESETS[1][0]); shot("after_warrior_ready")
S.edit(g, "attack", "minus"); g.stat_gender = "female"; shot("after_custom_female")
S.apply_preset(g, STAT_PRESETS[0][0]); shot("after_stacked_600x900", 600, 900)
