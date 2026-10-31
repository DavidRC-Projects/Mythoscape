"""Export player_hd hero reference renders (one per duel style) for the painted duel sprites.
Re-run on the Mac against the latest player_hd art:  python tools/duel_hero_ref.py OUTDIR
Then regenerate the hero pose sheets from these refs (prompts: tools/duel_sprite_prompts.md)
and cut them with tools/duel_sprites.py."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client")); os.chdir(os.path.join(HERE, "..", "client"))
import pygame; pygame.init(); pygame.display.set_mode((10, 10))
import player_hd_client as P, arena_duel_ui as U
out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(out, exist_ok=True)
for style in ("sword", "axe", "bow"):
    s = pygame.Surface((520, 620)); s.fill((235, 228, 215))
    look = P.get_default_appearance("male", starter=False); look["outfit"] = None
    anim, prog = ("ranged", 0.2) if style == "bow" else ("idle", None)
    P.draw_player(s, "male", look, 260, 590, 300, 0.0, anim=anim, progress=prog, facing=1,
                  equipment=dict(U._STYLE_GEAR[style]), starter=False)
    pygame.image.save(s, os.path.join(out, f"hero_{style}_ref.png")); print("ref", style)
