#!/usr/bin/env python3
"""Smoke-test panda3d-gltf: load a minimal .glb and print its node tree.

Usage (from game/assets/mmorpg, with .venv active):
    python tools/check_gltf.py
"""
from __future__ import annotations

import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CUBE_GLB = os.path.join(_HERE, "_fixtures", "cube.glb")


def _write_minimal_cube_glb(path: str) -> None:
    """Write a tiny valid glTF 2.0 binary cube (no Blender required)."""
    # 8 vertices of a unit cube centered at origin, float32 XYZ
    positions = [
        -0.5, -0.5, -0.5,  0.5, -0.5, -0.5,  0.5,  0.5, -0.5, -0.5,  0.5, -0.5,
        -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,  0.5,  0.5,  0.5, -0.5,  0.5,  0.5,
    ]
    # 12 triangles (uint16 indices)
    indices = [
        0, 1, 2, 0, 2, 3,  # -Z
        4, 6, 5, 4, 7, 6,  # +Z
        0, 4, 5, 0, 5, 1,  # -Y
        2, 6, 7, 2, 7, 3,  # +Y
        0, 3, 7, 0, 7, 4,  # -X
        1, 5, 6, 1, 6, 2,  # +X
    ]
    pos_bytes = struct.pack(f"<{len(positions)}f", *positions)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)
    # Pad index buffer to 4-byte alignment
    if len(idx_bytes) % 4:
        idx_bytes += b"\x00" * (4 - (len(idx_bytes) % 4))

    bin_blob = pos_bytes + idx_bytes
    pos_len = len(pos_bytes)
    idx_byte_len = len(indices) * 2  # unpadded accessor length

    gltf = {
        "asset": {"version": "2.0", "generator": "Mythoscape check_gltf"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "Cube"}],
        "meshes": [{
            "name": "CubeMesh",
            "primitives": [{
                "attributes": {"POSITION": 0},
                "indices": 1,
                "mode": 4,
            }],
        }],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 8,
                "type": "VEC3",
                "max": [0.5, 0.5, 0.5],
                "min": [-0.5, -0.5, -0.5],
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": pos_len, "target": 34962},
            {"buffer": 0, "byteOffset": pos_len, "byteLength": idx_byte_len, "target": 34963},
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
    }

    json_bytes = json_dumps_compact(gltf)
    # JSON chunk must be 4-byte aligned (pad with spaces)
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad

    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    bin_chunk = bin_blob + (b"\x00" * bin_pad)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    json_chunk_header = struct.pack("<I4s", len(json_bytes), b"JSON")
    bin_chunk_header = struct.pack("<I4s", len(bin_chunk), b"BIN\x00")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(json_chunk_header)
        f.write(json_bytes)
        f.write(bin_chunk_header)
        f.write(bin_chunk)


def json_dumps_compact(obj) -> bytes:
    import json
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def main() -> int:
    if not os.path.isfile(_CUBE_GLB):
        print(f"Generating {_CUBE_GLB}")
        _write_minimal_cube_glb(_CUBE_GLB)

    from panda3d.core import loadPrcFileData

    # Flat-colour / non-PBR materials (matches our monster style).
    # Must be set before ShowBase starts. Panda3D 1.10.4+ auto-loads glTF
    # once panda3d-gltf is installed — no manual loader registration.
    loadPrcFileData("", "gltf-legacy-materials true")
    loadPrcFileData("", "window-type none\naudio-library-name null\n")

    from direct.showbase.ShowBase import ShowBase

    base = ShowBase()
    model = base.loader.loadModel(_CUBE_GLB)
    if model is None or model.is_empty():
        print("FAIL: loader.loadModel returned empty model", file=sys.stderr)
        return 1

    print(f"OK: loaded {_CUBE_GLB}", flush=True)
    print("--- node tree ---", flush=True)

    def _walk(np, depth: int = 0) -> None:
        n = np.node()
        print(
            f"{'  ' * depth}{n.get_type().get_name()} {np.get_name()}",
            flush=True,
        )
        for i in range(np.get_num_children()):
            _walk(np.get_child(i), depth + 1)

    _walk(model)
    print("--- end ---", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
