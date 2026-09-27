"""tools/build_all.py - rebuild the whole dungeon-entrance pack in one go.

    python3 tools/build_all.py                      # everything
    python3 tools/build_all.py --only wolf_den      # one entrance
    python3 tools/build_all.py --no-render          # geometry/exports only (fast)

Steps per entrance:
  1. blender --background --python blender_scripts/<key>.py   -> blend/, glb/, json/, images/, ref/
  2. blend2bam (legacy materials, COLLISION collection -> invisible CollisionBoxes) -> bam/
  3. Panda3D check render (tools/panda_render.py)             -> panda_renders/
  4. 2D sprites (tools/render_sprites.py)                     -> sprites/<view>/
  5. contact sheet (tools/make_contact_sheet.py)              -> images/contact_sheet.png
Paths can be overridden with env vars BLENDER, PANDA_PYTHON, BLEND2BAM.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*")
ap.add_argument("--no-render", action="store_true", help="skip Blender concept renders")
ap.add_argument("--skip-panda", action="store_true")
ap.add_argument("--skip-sprites", action="store_true")
args = ap.parse_args()

BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or os.path.expanduser("~/apps/blender/blender")
PY = os.environ.get("PANDA_PYTHON") or "/workspace/monsters_venv/bin/python"
B2B = os.environ.get("BLEND2BAM") or os.path.join(os.path.dirname(PY), "blend2bam")
ENV = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":5"))


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(t in line for t in ("[osrs_kit]", "Error", "Traceback", "loaded OK", " px", "wrote", "tris")):
            print("   ", line)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(f"FAILED: {' '.join(cmd)}")


keys = sorted(os.path.splitext(os.path.basename(p))[0]
              for p in glob.glob(os.path.join(ROOT, "blender_scripts", "*.py"))
              if not os.path.basename(p).startswith(("osrs_kit", "_")))
if args.only:
    keys = [k for k in keys if k in args.only]
for key in keys:
    cmd = [BLENDER, "--background", "--python", os.path.join("blender_scripts", key + ".py")]
    if args.no_render:
        cmd += ["--", "--no-render"]
    run(cmd)
    if os.path.exists(B2B):
        run([B2B, "-m", "legacy", "--blender-dir", os.path.dirname(os.path.realpath(BLENDER)),
             "--invisible-collisions-collection", "COLLISION",
             os.path.join("blend", key + ".blend"), os.path.join("bam", key + ".bam")])
    else:
        print("   (blend2bam not found - skipping .bam; `pip install panda3d-blend2bam`)")
only = ["--only", *keys] if args.only else []
if not args.skip_panda:
    run([PY, os.path.join("tools", "panda_render.py"), *only])
if not args.skip_sprites:
    run([PY, os.path.join("tools", "render_sprites.py"), *only])
run([PY, os.path.join("tools", "make_contact_sheet.py")])
print("done")
