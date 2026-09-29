"""panda_buildings_check.py - load every building (.glb and .bam) in Panda3D offscreen, count nodes/tris,
render a 3/4 view of each into panda_renders/ and a sheet.   DISPLAY=:5 python tools/panda_buildings_check.py"""
import glob, json, os, sys
from panda3d.core import loadPrcFileData
loadPrcFileData("", "window-type offscreen\nwin-size 640 480\naudio-library-name null\nframebuffer-multisample 1\nmultisamples 4")
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, Vec4, Filename, GeomNode, CardMaker
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = ShowBase()
b.setBackgroundColor(0.55, 0.62, 0.72, 1)
al = b.render.attachNewNode(AmbientLight("a")); al.node().setColor(Vec4(0.45, 0.45, 0.45, 1)); b.render.setLight(al)
dl = b.render.attachNewNode(DirectionalLight("d")); dl.node().setColor(Vec4(0.9, 0.86, 0.78, 1)); dl.setHpr(-30, -40, 0); b.render.setLight(dl)
cm = CardMaker("g"); cm.setFrame(-80, 80, -80, 80); g = b.render.attachNewNode(cm.generate()); g.setP(-90); g.setZ(-0.02); g.setColor(0.37, 0.48, 0.24, 1)
os.makedirs(os.path.join(ROOT, "panda_renders"), exist_ok=True)
report = {}
for glb in sorted(glob.glob(os.path.join(ROOT, "models", "*.glb"))):
    key = os.path.basename(glb)[:-4]
    for ext in ("glb", "bam"):
        path = os.path.join(ROOT, "models", f"{key}.{ext}")
        m = b.loader.loadModel(Filename.fromOsSpecific(path), noCache=True)
        m.reparentTo(b.render)
        tris = 0
        for gn in m.findAllMatches("**/+GeomNode"):
            for gi in range(gn.node().getNumGeoms()):
                tris += gn.node().getGeom(gi).getNumPrimitives() if False else sum(p.getNumPrimitives() for p in [gn.node().getGeom(gi).getPrimitive(j).decompose() for j in range(gn.node().getGeom(gi).getNumPrimitives())])
        lo, hi = m.getTightBounds()
        c = (lo + hi) / 2
        size = (hi - lo).length()
        b.camera.setPos(c.x + size * 0.55, c.y - size * 0.95, c.z + size * 0.6)
        b.camera.lookAt(c)
        b.graphicsEngine.renderFrame(); b.graphicsEngine.renderFrame()
        out = os.path.join(ROOT, "panda_renders", f"{key}_{ext}.png")
        b.win.saveScreenshot(Filename.fromOsSpecific(out))
        report.setdefault(key, {})[ext] = {"loaded": True, "geomnodes": m.findAllMatches("**/+GeomNode").getNumPaths(),
                                           "tris": tris, "size_m": [round(v, 2) for v in (hi - lo)]}
        m.removeNode()
json.dump(report, open(os.path.join(ROOT, "panda_renders", "panda_report.json"), "w"), indent=1)
from PIL import Image
keys = sorted(report)
sheet = Image.new("RGB", (4 * 320, ((len(keys) + 3) // 4) * 240), (20, 20, 20))
for i, k in enumerate(keys):
    sheet.paste(Image.open(os.path.join(ROOT, "panda_renders", f"{k}_bam.png")).convert("RGB").resize((320, 240)), ((i % 4) * 320, (i // 4) * 240))
sheet.save(os.path.join(ROOT, "panda_renders", "panda_check_sheet.png"))
print(json.dumps({k: (v["glb"]["tris"], v["bam"]["tris"], v["bam"]["size_m"]) for k, v in report.items()}))
