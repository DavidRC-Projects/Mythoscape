"""Thin shim: the real implementation now lives in game/assets/shared/tools/prop_loader.py
(single shared copy used by castle_pack, props_pack and any other asset pack).
All names are re-exported here so existing `from prop_loader import ...` calls keep working."""
import os
import sys

_SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "tools")
_SHARED = os.path.abspath(_SHARED)
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

from prop_loader import (  # noqa: E402,F401
    ENTRANCE_SUN_HPR,
    PROP_SUN_HPR,
    add_entrance_collision,
    add_prop_collision,
    find_meta,
    load_entrance,
    load_prop,
    point_in_box,
    setup_osrs_lighting,
)
