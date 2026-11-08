"""Nearby-player index for interest management (M30).

``GridIndex`` gives exactly the same answer as ``all_pairs_nearby`` (verified by
parity tests): players within Chebyshev ``radius`` of the origin, excluding the
origin, ordered by (distance, player_id), truncated to ``cap``.

This is a CPU-side building block only. It is not evidence of 200-player
network or server-tick capacity.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Player = Tuple[int, int, int]  # (player_id, x, y)


def chebyshev(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def all_pairs_nearby(players: Sequence[Player], origin: Player, radius: int,
                     cap: Optional[int] = None) -> List[int]:
    oid, ox, oy = origin
    hits = []
    for pid, x, y in players:
        if pid == oid:
            continue
        d = chebyshev(ox, oy, x, y)
        if d <= radius:
            hits.append((d, pid))
    hits.sort()
    if cap is not None:
        hits = hits[:max(0, cap)]
    return [pid for _, pid in hits]


class GridIndex:
    """Uniform-grid bucket index, rebuilt once per tick from positions."""

    def __init__(self, cell: int):
        if cell <= 0:
            raise ValueError("cell must be positive")
        self.cell = int(cell)
        self._buckets: Dict[Tuple[int, int], List[Player]] = {}

    def build(self, players: Iterable[Player]) -> "GridIndex":
        buckets: Dict[Tuple[int, int], List[Player]] = {}
        c = self.cell
        for p in players:
            buckets.setdefault((p[1] // c, p[2] // c), []).append(p)
        self._buckets = buckets
        return self

    def query(self, origin: Player, radius: int, cap: Optional[int] = None) -> List[int]:
        oid, ox, oy = origin
        c = self.cell
        cx0, cx1 = (ox - radius) // c, (ox + radius) // c
        cy0, cy1 = (oy - radius) // c, (oy + radius) // c
        hits = []
        buckets = self._buckets
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                bucket = buckets.get((cx, cy))
                if not bucket:
                    continue
                for pid, x, y in bucket:
                    if pid == oid:
                        continue
                    d = max(abs(ox - x), abs(oy - y))
                    if d <= radius:
                        hits.append((d, pid))
        hits.sort()
        if cap is not None:
            hits = hits[:max(0, cap)]
        return [pid for _, pid in hits]


def nearby_for_all(players: Sequence[Player], radius: int, cap: Optional[int] = None,
                   method: str = "grid", cell: Optional[int] = None) -> Dict[int, List[int]]:
    if method == "all_pairs":
        return {p[0]: all_pairs_nearby(players, p, radius, cap) for p in players}
    index = GridIndex(cell or max(1, radius)).build(players)
    return {p[0]: index.query(p, radius, cap) for p in players}
