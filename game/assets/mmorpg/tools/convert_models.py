#!/usr/bin/env python3
"""Convert Blender .blend sources under assets/models/src/ to .bam via blend2bam.

Requires:
  - panda3d-blend2bam (see requirements-dev.txt)
  - Blender on PATH

Usage (from game/assets/mmorpg, with .venv active):
    python tools/convert_models.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_SRC = os.path.join(_ROOT, "assets", "models", "src")
_OUT = os.path.join(_ROOT, "assets", "models")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--src",
        default=_SRC,
        help="directory of .blend files (default: assets/models/src)",
    )
    ap.add_argument(
        "--out",
        default=_OUT,
        help="output directory for .bam files (default: assets/models)",
    )
    args = ap.parse_args()

    if shutil.which("blender") is None:
        print(
            "ERROR: Blender is not on PATH. Install Blender and ensure "
            "`blender` is available, then re-run.",
            file=sys.stderr,
        )
        return 1

    if shutil.which("blend2bam") is None:
        print(
            "ERROR: blend2bam not found. Install with:\n"
            "  pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1

    # blend2bam 0.26 + Blender 5: preference API workaround (no-op if patched)
    patch = os.path.join(_HERE, "patch_blend2bam_blender5.py")
    if os.path.isfile(patch):
        subprocess.run([sys.executable, patch], check=False)

    os.makedirs(args.src, exist_ok=True)
    os.makedirs(args.out, exist_ok=True)

    blends = sorted(
        f for f in os.listdir(args.src) if f.lower().endswith(".blend")
    )
    if not blends:
        print(f"No .blend files in {args.src}")
        return 0

    ok = 0
    for name in blends:
        src = os.path.join(args.src, name)
        dest = os.path.join(args.out, os.path.splitext(name)[0] + ".bam")
        print(f"blend2bam {src} -> {dest}")
        try:
            # -m legacy: flat/non-PBR materials (matches monster art style)
            subprocess.run(
                ["blend2bam", "-m", "legacy", src, dest],
                check=True,
            )
            ok += 1
        except subprocess.CalledProcessError as e:
            print(f"FAIL: {name}: {e}", file=sys.stderr)

    print(f"Converted {ok}/{len(blends)} model(s)")
    return 0 if ok == len(blends) else 1


if __name__ == "__main__":
    raise SystemExit(main())
