"""tools/render_icons.py - bake transparent 96px portrait icons for pygame UI.

    python tools/render_icons.py --out assets/ui/monster_icons --size 96
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from panda3d.core import loadPrcFileData  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="icons")
ap.add_argument("--size", type=int, default=96)
args = ap.parse_args()
loadPrcFileData("", "window-type offscreen\nwin-size 64 64\naudio-library-name null\n")

from direct.showbase.ShowBase import ShowBase  # noqa: E402

from monsters import registry  # noqa: E402
from monsters.portraits import save_portrait_png  # noqa: E402

base = ShowBase()
registry.load_all()
os.makedirs(args.out, exist_ok=True)
for key in registry.MONSTERS:
    path = os.path.join(args.out, f"{key}.png")
    save_portrait_png(base, key, path, size=args.size)
    print("wrote", path)
