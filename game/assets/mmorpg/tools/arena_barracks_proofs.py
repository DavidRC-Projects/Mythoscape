"""Render the restyled barracks per tab to ~/grokbot_tmp/arena_proofs/ (run from tools/)."""
import os, sys
_ARGS = list(sys.argv)
import arena_barracks_fixture as F
import pygame
import mercenaries_ui as MU
out = os.path.expanduser(_ARGS[1] if len(_ARGS) > 1 else "~/grokbot_tmp/arena_proofs")
os.makedirs(out, exist_ok=True)
mode = _ARGS[2] if len(_ARGS) > 2 else "v2"
if mode == "legacy":
    MU.draw = MU._draw_legacy
def shot(g, name):
    MU.draw(g); MU.draw(g)
    pygame.image.save(g.screen, os.path.join(out, f"{mode}_{name}.png"))
g = F.make_client()
for tab in ("roster", "recruit", "practice", "champions", "ladder"):
    g.barracks["tab"] = tab; g.barracks_scroll = 0; g.screen.fill((60, 80, 60)); shot(g, tab)
g.barracks["tab"] = "ladder"; g.barracks_scroll = 99999; g.screen.fill((60, 80, 60)); shot(g, "ladder_bottom")
g.barracks["tab"] = "roster"; g.barracks_scroll = 0; g.barracks_selected = 4; g.screen.fill((60, 80, 60)); shot(g, "soldier")
if mode == "v2":
    g.barracks_confirm = 4; shot(g, "dismiss_confirm"); g.barracks_confirm = None
    g.barracks_selected = None
    r = g.barracks_rects
    MU.draw(g); nu = g.barracks_rects.get("next_unlock")
    if nu:
        pygame.mouse.get_pos = lambda: nu.center; shot(g, "roster_tooltip")
    h = F.make_client(size=(700, 600)); h.barracks["tab"] = "ladder"; shot(h, "narrow_ladder")
print("saved", out)
