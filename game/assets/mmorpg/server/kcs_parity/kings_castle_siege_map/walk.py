"""Isolated walking / pan / zoom preview helpers (not the live client)."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

from .layout import Battlefield, Coord, Plane, walkable

Step = Tuple[int, int]


def shortest_path(
    plane: Plane,
    start: Coord,
    goal: Coord,
    gate_states: Optional[Dict[str, str]] = None,
) -> Optional[List[Coord]]:
    if not walkable(plane, start[0], start[1], gate_states):
        return None
    parent: Dict[Coord, Optional[Coord]] = {start: None}
    q = deque([start])
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            path = [(x, y)]
            while parent[path[-1]] is not None:
                path.append(parent[path[-1]])  # type: ignore[arg-type]
            path.reverse()
            return path
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in parent:
                continue
            if walkable(plane, nx, ny, gate_states):
                parent[(nx, ny)] = (x, y)
                q.append((nx, ny))
    return None


def sample_path(path: Sequence[Coord], count: int) -> List[Coord]:
    if not path:
        return []
    if count <= 1:
        return [path[0]]
    if len(path) <= count:
        return list(path)
    out = []
    for i in range(count):
        idx = round(i * (len(path) - 1) / (count - 1))
        out.append(path[idx])
    return out


def tour_waypoints(bf: Battlefield) -> List[Tuple[str, Coord, Dict[str, str]]]:
    """Named destinations for the isolated walk preview."""
    intact = {k: "intact" for k in bf.plane.openings}
    open_main = dict(intact)
    open_main["main_gate"] = "destroyed"
    open_keep = dict(open_main)
    open_keep["keep_doors"] = "destroyed"
    sp = bf.plane.spawn
    return [
        ("south_staging", sp["attacker"], intact),
        ("west_ring", sp["ring_sw"], intact),
        ("north_via_west", sp["attacker_north"], intact),
        ("east_ring", sp["ring_ne"], intact),
        ("south_via_east", sp["ring_se"], intact),
        ("main_gate_approach", sp["main_gate_south"], intact),
        ("courtyard_via_gate", sp["courtyard"], open_main),
        ("north_inner_passage", sp["north_inner"], open_main),
        ("keep_doors", sp["keep_door"], open_keep),
    ]


def build_tour(bf: Battlefield) -> List[Tuple[str, List[Coord], Dict[str, str]]]:
    legs: List[Tuple[str, List[Coord], Dict[str, str]]] = []
    prev: Optional[Coord] = None
    prev_states: Optional[Dict[str, str]] = None
    for name, dest, states in tour_waypoints(bf):
        start = prev if prev is not None else dest
        use = states if prev is None else states
        # When transitioning to a more-open state, search with the open set.
        if prev_states and any(states[k] == "destroyed" and prev_states[k] != "destroyed" for k in states):
            use = states
        path = shortest_path(bf.plane, start, dest, use)
        if path is None:
            path = [dest]
        legs.append((name, path, use))
        prev = dest
        prev_states = use
    return legs
