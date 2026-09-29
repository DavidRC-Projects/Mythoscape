from render_common import *
import sys
out = sys.argv[1]
T = 40
W, Hh = 8 * 110, 2 * 170
S = pygame.Surface((W, Hh)); tiles(S)
dirs = [("front", "front"), (1, "right"), ("back", "back"), (-1, "left")]
for row, new in enumerate((False, True)):
    for i, (g) in enumerate(("male", "female")):
        for j, (f, nm) in enumerate(dirs):
            x = 55 + (i * 4 + j) * 110
            draw_char(S, x, 95 + row * 170, T, new, {}, g, f)
    label(S, "NEW" if new else "OLD", 4, 4 + row * 170)
big = pygame.transform.scale(S, (W * 2, Hh * 2))
pygame.image.save(big, out)
