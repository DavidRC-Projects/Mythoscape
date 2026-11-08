"""Authoritative server map: walkability with independent opening states.

Semantics are identical to ``kings_castle_siege_map.layout.walkable`` (verified
tile-for-tile by tests): wall-walk tiles are walkable, blocking terrain is not,
and a gate/breach tile is walkable only when *its own* opening is destroyed.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .export_schema import FROZEN_PATH, OPENING_STATES, WALKABLE_WHEN, ExportError, load_export

Coord = Tuple[int, int]


class UnknownOpening(KeyError):
    pass


class BadOpeningState(ValueError):
    pass


@dataclass(frozen=True)
class PlaneData:
    plane_id: str
    width: int
    height: int
    rows: Tuple[str, ...]
    opening_ids: Tuple[str, ...]
    opening_rects: Dict[str, Tuple[int, int, int, int]]
    defaults: Dict[str, str]
    opening_at: Dict[Coord, str]
    spawn: Dict[str, Coord]
    landmarks: Dict[str, Tuple[int, int, int, int]]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height


class SiegeMap:
    def __init__(self, doc: Mapping):
        body = doc["body"]
        terrain = body["terrain"]
        self.content_sha256 = doc["content_sha256"]
        self.schema_version = body["schema_version"]
        self.map_id = body["map_id"]
        self.ownership_key = body["ownership_key"]
        self._wallwalk = terrain["wallwalk"]
        self._gate = terrain["gate"]
        self._blocking = frozenset(terrain["blocking"])
        self.planes: Dict[str, PlaneData] = {}
        for p in body["planes"]:
            rows = tuple(p["rows"])
            ids = tuple(op["id"] for op in p["openings"])
            rects = {op["id"]: tuple(op["rect"]) for op in p["openings"]}
            opening_at: Dict[Coord, str] = {}
            for oid in ids:
                x0, y0, x1, y1 = rects[oid]
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        if 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] == self._gate:
                            if (x, y) in opening_at:
                                # Independent breaches require disjoint openings.
                                raise ExportError(
                                    f"openings {opening_at[(x, y)]} and {oid} overlap at {(x, y)}")
                            opening_at[(x, y)] = oid
            self.planes[p["plane_id"]] = PlaneData(
                plane_id=p["plane_id"], width=p["width"], height=p["height"], rows=rows,
                opening_ids=ids, opening_rects=rects,
                defaults={op["id"]: op["default_state"] for op in p["openings"]},
                opening_at=opening_at,
                spawn={k: (int(v[0]), int(v[1])) for k, v in p["spawn"].items()},
                landmarks={k: tuple(v["rect"]) for k, v in p["landmarks"].items()},
            )

    @classmethod
    def load(cls, path=FROZEN_PATH) -> "SiegeMap":
        return cls(load_export(path))

    def plane(self, plane_id: str) -> PlaneData:
        try:
            return self.planes[plane_id]
        except KeyError:
            raise KeyError(f"unknown kings_castle_siege plane: {plane_id}") from None

    def new_states(self, plane_id: str) -> "OpeningStates":
        return OpeningStates(self.plane(plane_id))

    def walkable(self, plane_id: str, x: int, y: int, states: Optional[Mapping[str, str]] = None) -> bool:
        p = self.plane(plane_id)
        if not p.in_bounds(x, y):
            return False
        ch = p.rows[y][x]
        if ch == self._wallwalk:
            return True
        if ch != self._gate:
            return ch not in self._blocking
        oid = p.opening_at.get((x, y))
        if oid is None:
            return False
        st = (states or {}).get(oid, p.defaults[oid])
        return st == WALKABLE_WHEN

    def reachable(self, plane_id: str, start: Coord, states: Optional[Mapping[str, str]] = None) -> set:
        p = self.plane(plane_id)
        if not self.walkable(plane_id, *start, states):
            return set()
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in seen and self.walkable(plane_id, nx, ny, states):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen


@dataclass
class OpeningStates:
    """Per-war state of every opening on one plane. Each opening is independent."""

    plane: PlaneData
    states: Dict[str, str] = field(default_factory=dict)
    rev: int = 0

    def __post_init__(self):
        if not self.states:
            self.states = dict(self.plane.defaults)

    def get(self, opening_id: str) -> str:
        if opening_id not in self.states:
            raise UnknownOpening(opening_id)
        return self.states[opening_id]

    def as_dict(self) -> Dict[str, str]:
        return dict(self.states)

    def set(self, opening_id: str, state: str) -> List[Coord]:
        """Set one opening's state. Returns the tiles whose walkability changed."""
        if opening_id not in self.states:
            raise UnknownOpening(opening_id)
        if state not in OPENING_STATES:
            raise BadOpeningState(state)
        before = self.states[opening_id] == WALKABLE_WHEN
        self.states[opening_id] = state
        after = state == WALKABLE_WHEN
        self.rev += 1
        if before == after:
            return []
        return sorted(t for t, oid in self.plane.opening_at.items() if oid == opening_id)


def tiles_of(plane: PlaneData, opening_id: str) -> Iterable[Coord]:
    return sorted(t for t, oid in plane.opening_at.items() if oid == opening_id)
