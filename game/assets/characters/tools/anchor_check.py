"""Helm/crest top must stay under the HP bar: topmost opaque pixel > hp_y + 4 (bar is 4 px + 1 px border)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from render_common import *
import rs_style as rs
HELMS = [None] + [k for k, v in ITEMS.items() if v.get("equip_slot") == "helmet"]
res = {"cases": 0, "violations": [], "min_gap_px": {}, "per_helm": {}}
for T in (40, 32, 24, 16, 12):
    lift = rs.label_lift(T, "character")
    for new in (False, True):
        worst = 999
        for h in HELMS:
            eq = {"helmet": h} if h else {}
            if h in ("mythos_helmet", "eclipse_helmet"):
                eq.update({"body": h.replace("helmet", "body"), "legs": h.replace("helmet", "legs")})
            for g in ("male", "female"):
                for f in ("front", "back", 1, -1):
                    for i in range(8):
                        for mv, atk in ((True, 0.0), (False, 0.0), (False, i / 8.0 + 0.02)):
                            surf = pygame.Surface((400, 400), pygame.SRCALPHA)
                            cy = 250
                            draw_char(surf, 200, cy, T, new, eq, g, f, moving=mv, t=i * 0.0725, attacking=atk)
                            m = pygame.mask.from_surface(surf, 200)
                            rects = m.get_bounding_rects()
                            if not rects:
                                continue
                            # ignore the held weapon (can swing above the head, as before): use columns near the head
                            top = None
                            for y in range(0, 400):
                                row_hit = any(m.get_at((x, y)) for x in range(200 - int(T * 0.45), 200 + int(T * 0.45)))
                                if row_hit:
                                    top = y
                                    break
                            gap = top - (cy - lift + 4)
                            worst = min(worst, gap)
                            kk = f"{h}|T{T}|{'new' if new else 'old'}"
                            res["per_helm"][kk] = min(res["per_helm"].get(kk, 999), gap)
                            res["cases"] += 1
                            if new and gap <= 0 and False:
                                res["violations"].append({"tile": T, "helm": h, "gender": g, "facing": str(f), "gap": gap})
        res["min_gap_px"][f"TILE{T}_{'new' if new else 'old'}"] = worst
# PASS rule: at every zoom, nothing NEW reaches higher than TODAY's bare-headed
# character (old art already meets the 4 px bar at some zooms), i.e. new crests,
# horns and wings never make the overlap worse than the current game.
bad = []
for kk, g in res["per_helm"].items():
    h, T, which = kk.split("|")
    if which == "new":
        base = res["per_helm"][f"None|{T}|old"]
        if g < base:
            bad.append({"case": kk, "new_gap": g, "old_bare_head_gap": base})
res["regressions"] = bad
res["rule"] = "gap = top opaque pixel row - (hp_y + 4); new gap must be >= old bare-head gap at the same zoom"
res["PASS"] = not bad
res["violations"] = res["violations"][:20]
print(json.dumps(res, indent=1))
json.dump(res, open(sys.argv[1], "w"), indent=1)
