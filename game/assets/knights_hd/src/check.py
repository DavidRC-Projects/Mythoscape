import json, glob, sys
from PIL import Image
for k in sys.argv[1:]:
    m = json.load(open(f"/workspace/knights_hd/assets/{k}/meta.json"))
    print(k, "complete", m["complete"], "hit_point", m.get("hit_point_4x"), "hb", m.get("healthbar_y_offset_1x"), "reach", m.get("impact_reach_tiles"))
    bad = []
    for p in sorted(glob.glob(f"/workspace/knights_hd/assets/{k}/sprite_4x/*/*/f*.png")):
        al = Image.open(p).getchannel("A"); w, h = al.size
        e = [al.crop(b).getextrema()[1] for b in [(0, h - 2, w, h), (0, 0, 2, h), (w - 2, 0, w, h), (0, 0, w, 2)]]
        if max(e) > 60: bad.append((p.split("sprite_4x/")[1], e))
    print(" edge-clipped:", bad)
