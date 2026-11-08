"""Standalone King's Castle siege battlefield prototype.

Namespace: kings_castle_siege
This package is intentionally independent of castle_realm, crown_siege,
throne, server.py and client.py. Nothing here is wired into the live game.
"""

from .constants import (
    MAP_ID,
    MAP_TITLE,
    OWNERSHIP_KEY_RESERVED,
    FORBIDDEN_IDS,
    WIDTH,
    HEIGHT,
    TILE_METERS,
    STEP_SECONDS,
)
from .layout import build_battlefield, build_throne_room
from .placement import sample_perimeter_layout, validate_placement

__all__ = [
    "MAP_ID",
    "MAP_TITLE",
    "OWNERSHIP_KEY_RESERVED",
    "FORBIDDEN_IDS",
    "WIDTH",
    "HEIGHT",
    "TILE_METERS",
    "STEP_SECONDS",
    "build_battlefield",
    "build_throne_room",
    "sample_perimeter_layout",
    "validate_placement",
]
