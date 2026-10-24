"""tools/jw_catalogue_merge.py - add the HD jewellery (free starters + Crown Jewels) as overlay items to catalogue.json,
plus the ear_l/ear_r/head_back anchors and hair_covers_ears / painted.sleeves_long flags. Idempotent."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CAT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "player_hd", "assets", "catalogue.json")
JW = os.path.join(os.path.dirname(CAT), "jewellery", "jewellery.json")
c = json.load(open(CAT)); jw = json.load(open(JW))["jewellery"]
items = c.setdefault("items", []); have = {i["id"]: n for n, i in enumerate(items)}
SEX = {"f": "female", "m": "male", "u": None}
for e in jw:
    it = {"id": e["id"], "slot": "head" if e.get("slot") == "headwear" else ("bundle" if "bundle" in e else "jewellery"), "name": e["name"],
          "price": e["price"], "starter": bool(e.get("free_starter")), "free_starter": bool(e.get("free_starter")), "overlay": True, "hd_jewellery": True,
          "tintable": False, "layer": None, "art_layer": None, "card": f"jewellery/cards/{e['id']}.png", "sex": SEX.get(e.get("sex"), "female"),
          "tier": None, "set": None, "anchor": e.get("anchor"), "regalia": False, "fx": e.get("fx"), "release": e.get("release"),
          "review_score": e.get("review_score"), "row": e.get("row"), "z": {k: 47 for k in "sewn"}}
    if "bundle" in e: it["bundle"] = e["bundle"]
    if e["id"] in have: items[have[e["id"]]].update(it)
    else: items.append(it)
anc = c.setdefault("anchors", {})
anc.update({"ear_l": "jw_anchors.json:ear_l", "ear_r": "jw_anchors.json:ear_r", "head_back": "jw_anchors.json:head_back"})
flags = c.setdefault("painting_flags", {})
flags.setdefault("hair_covers_ears", "Earrings hidden when the painted hair covers the ears")
flags.setdefault("painted.sleeves_long", "Bracelets/bangles hidden under long painted sleeves")
json.dump(c, open(CAT, "w"), indent=1)
print("merged", len(jw), "jewellery entries")
