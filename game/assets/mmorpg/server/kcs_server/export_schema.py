"""Frozen, versioned export of the standalone battlefield for server use.

The approved renderer and navigation keep using ``kings_castle_siege_map.layout``
directly. This export is a *copy* of that layout's data in a stable JSON shape so
a server can load it without importing pygame/numpy/renderer code. The frozen
file carries a content hash; tests fail if the layout drifts from the export, so
server walkability and client nav cannot silently disagree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

SCHEMA_ID = "kcs_map_export"
SCHEMA_VERSION = 1
FROZEN_PATH = Path(__file__).resolve().parent / "data" / "kcs_map_export_v1.json"

# Terrain vocabulary mirrored from layout.py (verified by tests).
CHAR_WALLWALK = "H"
CHAR_GATE = "G"
BLOCKING_CHARS = ("#", "~", "T", "P")
OPENING_STATES = ("intact", "damaged", "destroyed")
WALKABLE_WHEN = "destroyed"


class ExportError(ValueError):
    pass


def _plane_dict(plane) -> Dict[str, Any]:
    return {
        "plane_id": plane.plane_id,
        "name": plane.name,
        "width": plane.width,
        "height": plane.height,
        "rows": ["".join(row) for row in plane.grid],
        # Order matters: the first opening whose rect contains a gate tile wins.
        "openings": [
            {"id": op.opening_id, "name": op.name, "rect": list(op.rect),
             "default_state": op.default_state}
            for op in plane.openings.values()
        ],
        "landmarks": {
            lid: {"name": lm.name, "kind": lm.kind, "rect": list(lm.rect)}
            for lid, lm in plane.landmarks.items()
        },
        "spawn": {k: [int(v[0]), int(v[1])] for k, v in plane.spawn.items()},
    }


def canonical_bytes(body: Dict[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def content_hash(body: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def build_export() -> Dict[str, Any]:
    from kings_castle_siege_map import constants as C
    from kings_castle_siege_map.layout import build_battlefield

    bf = build_battlefield()
    body = {
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "map_id": C.MAP_ID,
        "ownership_key": C.OWNERSHIP_KEY_RESERVED,
        "forbidden_ids": sorted(C.FORBIDDEN_IDS),
        "tile_meters": C.TILE_METERS,
        "wall_box": list(bf.wall_box),
        "keep_rect": list(bf.keep_rect),
        "interior_rect": list(bf.interior_rect),
        "terrain": {
            "wallwalk": CHAR_WALLWALK,
            "gate": CHAR_GATE,
            "blocking": list(BLOCKING_CHARS),
            "opening_states": list(OPENING_STATES),
            "walkable_when": WALKABLE_WHEN,
        },
        "planes": [_plane_dict(bf.plane), _plane_dict(bf.throne)],
    }
    return {"body": body, "content_sha256": content_hash(body)}


def write_export(path: Path = FROZEN_PATH) -> str:
    doc = build_export()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True, indent=None, separators=(",", ":")) + "\n", encoding="ascii")
    tmp.replace(path)
    return doc["content_sha256"]


def load_export(path: Path = FROZEN_PATH) -> Dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="ascii"))
    body = doc.get("body")
    if not isinstance(body, dict):
        raise ExportError("export has no body")
    if body.get("schema") != SCHEMA_ID or body.get("schema_version") != SCHEMA_VERSION:
        raise ExportError(f"unsupported export schema {body.get('schema')}/{body.get('schema_version')}")
    if content_hash(body) != doc.get("content_sha256"):
        raise ExportError("export content hash mismatch")
    for plane in body["planes"]:
        rows = plane["rows"]
        if len(rows) != plane["height"] or any(len(r) != plane["width"] for r in rows):
            raise ExportError(f"plane {plane['plane_id']} has inconsistent dimensions")
        for op in plane["openings"]:
            if op["default_state"] not in OPENING_STATES:
                raise ExportError(f"bad default state for {op['id']}")
    if body["map_id"] in body["forbidden_ids"] or body["ownership_key"] in body["forbidden_ids"]:
        raise ExportError("namespace collision with live ids")
    return doc
