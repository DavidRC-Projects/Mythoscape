#!/usr/bin/env python3
"""Patch installed blend2bam for Blender 5.x preference API.

blend2bam 0.26.0 uses ``'allow_embedded_format' in addon_prefs``, which raises
TypeError on Blender 5. Safe to re-run; no-op if already patched or absent.
"""
from __future__ import annotations

import importlib.util
import os
import sys


_OLD = """    addon_prefs = bpy.context.preferences.addons['io_scene_gltf2'].preferences
    if addon_prefs is None:
        addon_prefs = []
    if 'allow_embedded_format' in addon_prefs:
        addon_prefs['allow_embedded_format'] = True
"""

_NEW = """    # Blender 5+: addon preferences may not support `in` / IDProperties checks
    # (see https://discourse.panda3d.org/t/blend2bam-error/31385). Use hasattr.
    addon_prefs = bpy.context.preferences.addons['io_scene_gltf2'].preferences
    if addon_prefs is not None and hasattr(addon_prefs, 'allow_embedded_format'):
        try:
            addon_prefs.allow_embedded_format = True
        except Exception:  # pylint: disable=broad-except
            pass
"""


def main() -> int:
    spec = importlib.util.find_spec("blend2bam")
    if spec is None or not spec.origin:
        print("blend2bam not installed; skip patch", file=sys.stderr)
        return 1
    path = os.path.join(
        os.path.dirname(spec.origin),
        "blender_scripts",
        "exportgltf.py",
    )
    if not os.path.isfile(path):
        print(f"missing {path}", file=sys.stderr)
        return 1
    text = open(path, encoding="utf-8").read()
    if "hasattr(addon_prefs, 'allow_embedded_format')" in text:
        print(f"already patched: {path}")
        return 0
    if _OLD not in text:
        print(
            f"unexpected exportgltf.py contents; not patching: {path}",
            file=sys.stderr,
        )
        return 1
    open(path, "w", encoding="utf-8").write(text.replace(_OLD, _NEW, 1))
    print(f"patched: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
