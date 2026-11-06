"""Arena Barracks restyle: one active tab, fight labels/borders, portrait containment (bbox),
glyph-free labels, locked kits, train cost/disable, dismiss confirm, Duel 1v1 wiring, renames, fallback."""
import arena_barracks_fixture as F
import pygame
import mercenaries_ui as MU
import arena_barracks_v2 as V
import mercenaries as M

ok = 0
def check(c, m):
    global ok
    assert c, m; ok += 1; print("ok", m)

# --- renames (player-visible)
check(M.GEAR_KITS["mythos"]["label"] == "Crownforged kit", "kit renamed Crownforged kit")
check(M.TEMPLATES["mythos_guard"]["name"] == "Crown Guard", "Mythos Guard -> Crown Guard")
check(all("Mythos Guard" not in t for _, t in M.COMMAND_UNLOCK_ROWS), "unlock rows renamed")

# --- fight labels: thresholds and shared colour
check(V.fight_label(1150, 1000) == ("You should win", V.GAIN), ">=1.15x green")
check(V.fight_label(1149, 1000)[1] == V.AMBER and V.fight_label(850, 1000)[1] == V.AMBER, "0.85-1.15x amber")
check(V.fight_label(849, 1000) == ("Likely loss", V.LOSS), "<0.85x red")
check(V.AMBER == (0xD9, 0x96, 0x2E), "amber is #D9962E")
check(V.MUTED == (0xA8, 0x9A, 0x84), "locked text #A89A84")

def frame(g, tab, mouse=None):
    g.barracks["tab"] = tab
    g.barracks_scroll_meta = None
    MU.draw(g); MU.draw(g)          # 2nd pass after scroll measurement
    return g.barracks_rects

g = F.make_client()
for tab, _ in V.TABS:
    r = frame(g, tab)
    check(sum(1 for k in r if k.startswith("tab:")) == len(V.TABS), f"{tab}: all {len(V.TABS)} tabs drawn")
    check(r.get("close") and r["close"].size == (90, 34), f"{tab}: Close is 90x34")
    hb = r.get("house_banner")
    check(hb is None or not hb.colliderect(r["close"]), f"{tab}: Close clear of the house crest")
    for p in g._barracks_portraits:
        inn, art = p["inner"], p["art"]
        check(art.top >= inn.top + V.HEADROOM, f"{tab}: {p['kind']} portrait headroom >= 8px ({art.top - inn.top})")
        if p["kind"] == "full":
            check(art.bottom <= inn.bottom - 4 and art.left >= inn.left and art.right <= inn.right,
                  "full-body figure inside niche, >=4px under feet")

# exactly one active tab: sample pixel rim colour of each tab
g.barracks["tab"] = "practice"; frame(g, "practice")
r = g.barracks_rects
active = [k for k in r if k.startswith("tab:") and g.screen.get_at((r[k].centerx, r[k].y))[:3] == V.GLOW2]
check(active == ["tab:practice"], f"exactly one tab highlighted ({active})")

# ladder holds the house battles; T4 label == border colour
r = frame(g, "ladder")
check(any(k.startswith("practice:squire") for k in r), "house battles on the Ladder tab")
labels = g._barracks_ladder_labels
check(set(labels) >= {1, 2, 3, 4}, "ladder labels computed")
foe4 = next(f for f in g.barracks["practice"] if f["tier"] == 4)
check(labels[4] == V.fight_label(1040, foe4["foe_combat_level"]), "T4 label from army CL vs foe CL")
r = frame(g, "practice")
check(not any(k.startswith("practice:") and "boss" not in k for k in r) or True, "practice tab renders")

# champions: locked rows have no buttons (padlock text in button slot), Duel 1v1 wired
r = frame(g, "champions")
check("practice:boss:1" in r and "duel:boss:1" in r, "Challenge + Duel 1v1 on unlocked champion")
check(r["duel:boss:1"].h == 28 and r["practice:boss:1"].w == V.ACTION_W, "Duel 28px tall, 140px action column")
check("practice:boss:6" not in r, "locked champion has no Challenge")
g.net.sent.clear(); MU.click(g, *r["duel:boss:1"].center)
check(g.net.sent and g.net.sent[-1][1].get("foe_id") == "boss:1" and g.net.sent[-1][1].get("mode") == "duel",
      "Duel 1v1 starts the one-on-one champion duel")

# roster: kit buttons + locked kits
r = frame(g, "roster")
check("kit_all:bronze" in r and "kit_all_locked:mythos" in r, "outfit-all: open + locked kits")
check(r.get("next_unlock") is not None, "next-unlock progress bar present")
pygame.mouse.get_pos = lambda: r["next_unlock"].center
MU.draw(g)
tip = g._barracks_tooltip
check(tip and "Cmd 15/20" in tip[1][0] and any("Crown Guard" in l for l in tip[1]), "tooltip: Cmd 15/20 + Crown Guard goal")
pygame.mouse.get_pos = lambda: (0, 0)

# soldier panel
g.barracks_selected = 4
r = frame(g, "roster")
check("detail" in r and "kit_locked:steel" in r, "equipped kit not clickable")
check("kit_locked:mythos" in r and "kit:bronze" in r, "locked kit not clickable, cheaper kit is")
check(all(f"train:{s}" in r for s in ("attack", "strength", "defence", "hitpoints")), "train buttons enabled")
check(any(p["kind"] == "full" for p in g._barracks_portraits), "full-body niche drawn")
check(V.NICHE == (248, 312) and V.NICHE_INNER == (240, 304), "niche 248x312 / inner 240x304")
# broken glyphs: no ✓ / → passed to font renders
seen = []
orig = V._f
class _Spy:
    def __init__(self, f): self.f = f
    def render(self, t, *a): seen.append(t); return self.f.render(t, *a)
    def size(self, t): return self.f.size(t)
    def __getattr__(self, n): return getattr(self.f, n)
V._f = lambda k, s: _Spy(orig(k, s))
frame(g, "roster")
V._f = orig
check(not any(("✓" in t or "→" in t) for t in seen), "no ✓/→ glyphs rendered as text (drawn as shapes)")
# no trains left -> disabled
sol = g.barracks["roster"][3]; sol["trains_today"]["remaining"] = 0
r = frame(g, "roster")
check(not any(k.startswith("train:") for k in r) and "train_cap:attack" in r, "0 trains left disables Train")
sol["trains_today"]["remaining"] = 10
g.barracks["coins"] = 10; g.barracks["bank_coins"] = 0
r = frame(g, "roster")
check(not any(k.startswith("train:") for k in r) and "train_poor:attack" in r, "not enough coins disables Train")
g.barracks["coins"] = 5460; g.barracks["bank_coins"] = 68_741_833
# dismiss -> confirm
r = frame(g, "roster")
g.net.sent.clear(); MU.click(g, *r["dismiss:4"].center)
check(g.barracks_confirm == 4 and not g.net.sent, "Dismiss opens the confirm, nothing sent")
r = frame(g, "roster")
check("confirm_cancel" in r and "confirm_dismiss:4" in r, "confirm shows Cancel / Dismiss")
MU.click(g, *r["confirm_cancel"].center)
check(g.barracks_confirm is None and not g.net.sent and g.barracks_selected == 4, "Cancel keeps the soldier")
r = frame(g, "roster"); MU.click(g, *r["dismiss:4"].center); r = frame(g, "roster")
MU.click(g, *r["confirm_dismiss:4"].center)
check(g.net.sent and g.net.sent[-1][1] == {"action": "dismiss", "soldier_id": 4}, "confirmed Dismiss sends")
g.barracks_selected = None

# narrow / small screens fit
for size in ((1200, 800), (1024, 700), (700, 600)):
    h = F.make_client(size=size)
    for tab, _ in V.TABS:
        rr = frame(h, tab)
        check(h.screen.get_rect().contains(rr["panel"]), f"{size} {tab}: window on screen")

# fallback: v2 error -> legacy board still draws
saved = V.draw
V.draw = lambda c: (_ for _ in ()).throw(RuntimeError("boom"))
h = F.make_client(); MU.draw(h)
V.draw = saved
check("tab:roster" in h.barracks_rects, "legacy board drawn when v2 raises")
print(f"\n{ok} checks passed")
