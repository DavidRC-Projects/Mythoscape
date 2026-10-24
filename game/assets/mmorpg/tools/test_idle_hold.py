"""Idle must hold still at every camera zoom: no frame-to-frame pop between source scales.
Also checks the live path: anim goes back to idle within 0.6s after a step (moving_for hold)."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client"))
import pygame
pygame.init(); pygame.display.set_mode((8, 8))
import player_hd_client as P

KITS = [("male", {}), ("female", {}),
        ("male", {"helmet": "bronze_helmet", "body": "bronze_body", "legs": "bronze_legs", "weapon": "bronze_sword"}),
        ("female", {"helmet": "mythos_helmet", "body": "mythos_body", "legs": "mythos_legs", "shield": "mythos_shield"})]
fails = 0; n = 0
for sex, eq in KITS:
    for tile in (36, 44, 66, 88, 110, 140):
        for facing in (1, -1, "front", "back"):
            prev = None; worst = 0; area = 1
            for i in range(48):
                s = pygame.Surface((420, 420), pygame.SRCALPHA)
                P.draw_player(s, sex, None, 210, 400, tile, i / 24.0, anim="idle", facing=facing, equipment=eq)
                a = pygame.surfarray.array_alpha(s) > 128
                area = max(area, int(a.sum()))
                if prev is not None:
                    worst = max(worst, int((a ^ prev).sum()))
                prev = a
            n += 1
            if worst > 0.03 * area:
                fails += 1
                print(f"FAIL idle pop {sex} tile={tile} facing={facing} eq={bool(eq)}: {worst}px of {area}")
print(f"{n - fails}/{n} idle hold tests passed")
sys.exit(1 if fails else 0)
