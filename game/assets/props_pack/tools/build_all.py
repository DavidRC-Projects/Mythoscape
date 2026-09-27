"""tools/build_all.py - rebuild the whole interior-props pack.

    python3 tools/build_all.py                          # everything
    python3 tools/build_all.py --groups town            # one group script
    python3 tools/build_all.py --only furnace anvil     # individual props
    python3 tools/build_all.py --no-render              # skip Blender concept renders

Steps
  1. blender -b -P blender_scripts/props_<group>.py [-- --only ...]  -> blend/ glb/ json/ images/ ref/
  2. blend2bam -m legacy, COLLISION collection -> invisible CollisionBoxes  -> bam/
  3. tools/panda_render.py   (in-engine check, game camera + 3/4)          -> panda_renders/
  4. tools/render_sprites.py (pygame sprites + anchors, --yaws)            -> sprites/game, sprites/osrs
  5. tools/verify_props.py   (loads, budgets, emission, collision/interact)-> review/verify_report.txt
  6. tools/make_contact_sheets.py (one labelled sheet per group + scores)  -> review/contact_<group>.png
Env overrides: BLENDER, PANDA_PYTHON, BLEND2BAM.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GROUPS = ["town", "castle", "pets", "dungeons"]
ap = argparse.ArgumentParser()
ap.add_argument("--groups", nargs="*", default=GROUPS)
ap.add_argument("--only", nargs="*")
ap.add_argument("--no-render", action="store_true")
ap.add_argument("--skip-panda", action="store_true")
ap.add_argument("--skip-sprites", action="store_true")
args = ap.parse_args()

BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or os.path.expanduser("~/bin/blender")
PY = os.environ.get("PANDA_PYTHON") or "/workspace/monsters_venv/bin/python"
B2B = os.environ.get("BLEND2BAM") or os.path.join(os.path.dirname(PY), "blend2bam")
ENV = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":5"))


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(t in line for t in ("[osrs_kit] ", "Error", "Traceback", "loaded OK", "game 1x", "PASS", "FAIL")) \
                and "wrote" not in line and "/dev/input" not in line:
            print("   ", line)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(f"FAILED: {' '.join(cmd)}")


for g in args.groups:
    cmd = [BLENDER, "--background", "--factory-startup", "--python", os.path.join("blender_scripts", f"props_{g}.py")]
    extra = []
    if args.no_render:
        extra.append("--no-render")
    if args.only:
        extra += ["--only", ",".join(args.only)]
    run(cmd + (["--"] + extra if extra else []))

keys = []
for j in sorted(glob.glob(os.path.join(ROOT, "json", "*.json"))):
    m = json.load(open(j))
    if m.get("group") in args.groups and (not args.only or m["key"] in args.only):
        keys.append(m["key"])
if os.path.exists(B2B):
    os.makedirs(os.path.join(ROOT, "bam"), exist_ok=True)
    for key in keys:
        run([B2B, "-m", "legacy", "--blender-dir", os.path.dirname(os.path.realpath(BLENDER)),
             "--invisible-collisions-collection", "COLLISION",
             os.path.join("blend", key + ".blend"), os.path.join("bam", key + ".bam")])
else:
    print("   (blend2bam not found - skipping .bam; pip install panda3d-blend2bam)")
only = ["--only", *keys]
if not args.skip_panda:
    run([PY, os.path.join("tools", "panda_render.py"), *only])
if not args.skip_sprites:
    run([PY, os.path.join("tools", "render_sprites.py"), "--yaws", *only])
run([PY, os.path.join("tools", "verify_props.py")])
run([PY, os.path.join("tools", "make_contact_sheets.py")])
print("done")
