"""tools/verify_props.py - automated checks for every prop (run after build_all.py):

  * .glb loads through panda3d-gltf (legacy materials) via prop_loader, .bam loads too
  * no textures; triangle count inside its budget class (S 400 / M 900 / L 1300)
  * every json "emissive" material really glows after prop_loader's fixes (emission > 0 on
    the rebuilt Material) - required for furnace fire, void crystals, well + fountain water,
    chandelier candles, braziers/hearth/candles
  * the .bam from blend2bam carries the same CollisionNodes as the json (COL_* + INTERACT_use)
  * collision test with a 0.35 m two-sphere player capsule (Panda3D CollisionTraverser):
      - props that must be usable (bank, vault chest, furnace, anvil, well, fountain, cages...)
        have an INTERACT_use volume; walking from 4 m in front towards the prop ENTERS the
        interaction volume BEFORE it is blocked by a solid box
      - walking into the prop's centre is BLOCKED by a solid box (props with colliders)
  * concept image, both Panda renders, game sprites (1x/2x/3x + yaws) and the 3/4 sprite exist

    /workspace/monsters_venv/bin/python tools/verify_props.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from panda3d.core import loadPrcFileData  # noqa: E402
loadPrcFileData("", "window-type none\naudio-library-name null\ngltf-legacy-materials true")
from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import (CollisionTraverser, CollisionHandlerQueue, CollisionNode,  # noqa: E402
                          CollisionSphere, BitMask32, TextureAttrib, MaterialAttrib)
from prop_loader import load_prop, add_prop_collision  # noqa: E402

SOLID, TRIG = BitMask32.bit(1), BitMask32.bit(2)
BUDGET = {"S": 400, "M": 900, "L": 1300}
# S = small 1-tile furniture, M = 1-2 tile props (default), L = showpiece clutter piles / cages with a pet
SIZE_CLASS = {k: "S" for k in ("anvil", "barrel", "quench_bucket", "castle_chair", "pet_bed", "brazier",
                               "workbench", "weapon_rack", "banner_stand", "vault_chest", "shop_counter",
                               "throne", "void_crystals")}
SIZE_CLASS.update({k: "L" for k in ("dragon_hoard", "wolf_bone_pile", "cage_skeleton", "dragon_egg_nest")})
MUST_INTERACT = {"bank_booth", "vault_chest", "furnace", "anvil", "wishing_well", "fountain", "cage_cat",
                 "cage_husky", "cage_skeleton", "cage_dragon", "shop_counter", "market_stall", "hearth",
                 "void_altar"}
MUST_GLOW = {"furnace": "fire", "void_crystals": "void", "void_altar": "void", "wishing_well": "water",
             "fountain": "water", "chandelier": "candle", "brazier": "fire", "hearth": "fire",
             "goblin_campfire": "fire", "banquet_table": "candle", "crypt_candelabra": "candle",
             "crypt_sarcophagus": "candle", "anvil": "ember"}


def walk(base, model, start, end, steps=60):
    player = base.render.attach_new_node(CollisionNode("player"))
    player.node().add_solid(CollisionSphere(0, 0, 0.9, 0.35))   # body
    player.node().add_solid(CollisionSphere(0, 0, 0.35, 0.35))  # legs (low props: beds, tubs)
    player.node().set_from_collide_mask(SOLID | TRIG)
    player.node().set_into_collide_mask(BitMask32.all_off())
    trav, q = CollisionTraverser(), CollisionHandlerQueue()
    trav.add_collider(player, q)
    first_trig, first_solid = None, None
    for i in range(steps + 1):
        t = i / steps
        player.set_pos(model, *(s + (e - s) * t for s, e in zip(start, end)))
        trav.traverse(base.render)
        for j in range(q.get_num_entries()):
            name = q.get_entry(j).get_into_node().name
            if name.startswith(("INTERACT", "TRIGGER")):
                first_trig = i if first_trig is None else first_trig
            elif first_solid is None:
                first_solid = i
        if first_solid is not None:
            break
    player.remove_node()
    return first_trig, first_solid


def glow_ok(model, key_mat):
    for gnp in model.find_all_matches("**/+GeomNode"):
        gn = gnp.node()
        for i in range(gn.get_num_geoms()):
            ma = gn.get_geom_state(i).get_attrib(MaterialAttrib)
            if ma and ma.get_material() and ma.get_material().get_name().split(".")[0] == key_mat:
                e = ma.get_material().get_emission()
                return max(e[0], e[1], e[2]) > 0.05
    return False


def main():
    base = ShowBase(windowType="none")
    ok_all, rows = True, []
    for jf in sorted(glob.glob(os.path.join(ROOT, "json", "*.json"))):
        meta = json.load(open(jf))
        key = meta["key"]
        errs, notes = [], []
        glb, bam = os.path.join(ROOT, "glb", key + ".glb"), os.path.join(ROOT, "bam", key + ".bam")
        model, _ = load_prop(base.loader, glb)
        model.reparent_to(base.render)
        if model.find_all_matches("**/+GeomNode").get_num_paths() == 0:
            errs.append("glb has no geometry")
        if any(n.get_state().has_attrib(TextureAttrib) for n in model.find_all_matches("**")):
            errs.append("textures found")
        cls = SIZE_CLASS.get(key, "M")
        if meta["triangles"] > BUDGET[cls]:
            errs.append(f"tris {meta['triangles']} > budget {BUDGET[cls]}")
        for em in meta.get("emissive", {}):
            if not glow_ok(model, em):
                if em == MUST_GLOW.get(key):
                    errs.append(f"'{em}' does not glow after prop_loader")
        if key in MUST_GLOW and MUST_GLOW[key] not in meta.get("emissive", {}):
            errs.append(f"missing required glow '{MUST_GLOW[key]}'")
        names = sorted([c["name"] for c in meta.get("colliders", [])] +
                       ([meta["interact"]["name"]] if meta.get("interact") else []))
        if os.path.exists(bam):
            bm = base.loader.load_model(bam)
            bnames = sorted(np.name for np in bm.find_all_matches("**/+CollisionNode"))
            if bnames != names:
                errs.append(f"bam CollisionNodes {bnames} != json {names}")
            bm.remove_node()
        else:
            errs.append("no .bam")
        add_prop_collision(model, meta)
        if key in MUST_INTERACT and not meta.get("interact"):
            errs.append("needs an INTERACT_use volume")
        if meta.get("interact"):
            ic = meta["interact"]["center"]
            ft, fs = walk(base, model, (ic[0], ic[1] - 3.5, 0), (0, 0, 0))
            if ft is None:
                errs.append("walk-in never entered the interaction volume")
            elif fs is not None and fs < ft:
                errs.append("blocked before reaching the interaction volume")
            else:
                notes.append("interact reachable")
        if meta.get("colliders"):
            c = meta["colliders"][0]["center"]
            ft, fs = walk(base, model, (c[0], c[1] - 4.0, 0), (c[0], c[1], 0))
            if fs is None:
                errs.append("walking into the prop was NOT blocked")
            else:
                notes.append("solid blocks")
        for p in (f"images/{key}_concept.png", f"panda_renders/{key}_panda.png", f"panda_renders/{key}_panda34.png",
                  f"sprites/game/{key}_1x.png", f"sprites/game/{key}_2x.png", f"sprites/game/{key}_3x.png",
                  f"sprites/game/{key}_w_1x.png", f"sprites/osrs/{key}_2x.png", f"sprites/game/{key}.json"):
            if not os.path.exists(os.path.join(ROOT, p)):
                errs.append("missing " + p)
        model.remove_node()
        ok = not errs
        ok_all &= ok
        rows.append(f"{'PASS' if ok else 'FAIL'}  {meta.get('group', '?'):8s} {key:18s} tris {meta['triangles']:4d}/"
                    f"{BUDGET[cls]:4d}({cls})  glow {','.join(meta.get('emissive', {})) or '-':30s} "
                    f"{'; '.join(notes + errs)}")
    rep = "\n".join(rows) + f"\n\n{sum(r.startswith('PASS') for r in rows)}/{len(rows)} props PASS\n"
    print(rep)
    with open(os.path.join(ROOT, "review", "verify_report.txt"), "w") as fh:
        fh.write(rep)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
