import sys, json
sys.path.insert(0, "/workspace/player_hd/src")
import pl_scene  # sets paths
import pl_items as I, pl_rig as R
out = {"catalogue": [], "armour": [], "weapons": [], "z_classes": I.Z_S, "anims": {}}
for cid, slot, name, price, starter, tint, b, zc in I.CATALOGUE:
    out["catalogue"].append(dict(id=cid, slot=slot, name=name, price=price, starter=starter, tintable=tint, z_class=zc))
for lid, slot, b, zc, covers, match in I.ARMOUR:
    out["armour"].append(dict(id=lid, equip_slot=slot, z_class=zc, covers=covers, matches=match))
for lid, b, match, anims in I.WEAPONS:
    out["weapons"].append(dict(id=lid, matches=match, anims=list(anims)))
for a, (n, f, loop, doc) in R.ANIMS.items():
    out["anims"][a] = dict(frames=n, facings=list(f), loop=loop, runtime=doc)
json.dump(out, open("/workspace/player_hd/work/catalog_raw.json", "w"), indent=1)
print("ok")
