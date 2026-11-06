"""Sidebars v2 (UI package 2): wood/gold materials, real-key keycaps, hotkey fix."""
import os, re, sys, io, contextlib
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "client"))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
import pygame
pygame.init()
pygame.display.set_mode((10, 10))  # convert()/skin need a video mode
import hud_skin, hud_v2

fails = []
def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)

S = pygame.Surface((400, 300))
def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    return buf.getvalue()

# materials draw without falling back
out = quiet(hud_v2._panel, S, pygame.Rect(10, 10, 200, 90), hud_v2.NAVY_CARD, hud_v2.GOLD, ornate=True)
check("panel uses skin (no fallback)", "fallback" not in out)
px = S.get_at((60, 50))
check("card body is warm wood (r > b)", px.r > px.b)
out = quiet(hud_v2._fill_bar, S, pygame.Rect(10, 120, 200, 10), 0.5, (52, 200, 98))
check("bar uses skin", "fallback" not in out)
px = S.get_at((60, 125))
check("hp bar fill is green", px.g > px.r and px.g > px.b)
for kind in ("idle", "active", "danger", "arcane", "safe", "primary"):
    try:
        hud_skin.button(S, pygame.Rect(10, 150, 120, 34), kind, inset=kind == "active", hover=True)
        ok = True
    except Exception as e:
        ok = False
    check(f"button {kind}", ok)
for ic in ("scroll", "pennant", "party", "guild", "map", "swords", "rune", "coin", "gem", "copper", "moon", "sun"):
    try:
        hud_skin.icon(S, ic, 50, 250, 9); ok = True
    except Exception:
        ok = False
    check(f"icon {ic}", ok)
for kind in ("safe", "pvp", "dungeon"):
    hud_skin.shield_badge(S, pygame.Rect(200, 10, 120, 54), kind, "Village", "Safe Zone")
inner = hud_skin.parchment(S, pygame.Rect(150, 100, 240, 108), "CURRENT QUEST")
check("quest scroll padding >= 11px (22px @2x)", inner.x - 150 >= 11 and 390 - inner.right >= 11)
check("rarity tiers", hud_skin.rarity_of("mythos_longsword") == "legendary" and hud_skin.rarity_of("bronze_sword") == "common"
      and hud_skin.rarity_of("rune_platebody") == "epic")
hud_skin.keycap(S, (40, 40), "[", small=True)

# keycaps: only real keys
check("nav keycaps are real keys only", hud_v2.NAV_KEYS == {"quests": "Q", "party": "P", "pvp": "K"})

# hotkey fix in client.py
src = open(os.path.join(HERE, "..", "client", "client.py")).read()
def branch(key):
    m = re.search(r"elif event\.key == pygame\.K_%s:\n(.*?)\n            elif" % key, src, re.S)
    return m.group(1) if m else ""
check("P -> Party", '_nav_click(self, "party")' in branch("p"))
check("L -> Coins+bones", "toggle_auto_pickup" in branch("l"))
check("K -> PvP single tap on and off", '_nav_click(self, "pvp")' in branch("k") and "_pk_key_arm" not in branch("k"))
check("B still Bank", "try_open_bank" in branch("b"))
check("no K_v binding yet (reserved for nameplates)", "pygame.K_v" not in src or "nameplate" in src)
for key in ("p", "l", "k", "b"):
    check(f"K_{key} bound once in world keys", len(re.findall(r"elif event\.key == pygame\.K_%s:" % key, src)) == 1)
drawn = open(os.path.join(HERE, "..", "client", "hud_drawn.py")).read()
check("Coins+bones label says (L)", "(L)" in drawn and "} (P)\"" not in drawn)
# no unicode arrows left in the inventory scroll
hv = open(os.path.join(HERE, "..", "client", "hud_v2.py")).read()
check("scroll arrows are shapes, not glyphs", '"▲"' not in hv and '"▼"' not in hv)
check("legacy fallbacks kept", "_panel_legacy" in hv and "_fill_bar_legacy" in hv and "_draw_left_nav_legacy" in hv)

print("FAILS:", fails)
sys.exit(1 if fails else 0)
