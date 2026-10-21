"""Thin shim: the real Kit implementation now lives in game/assets/shared/blender/osrs_kit.py
(one shared copy used by every asset pack instead of per-pack duplicates).
All names are re-exported here so existing `from osrs_kit import ...` calls keep working."""
import os
import sys

_SHARED = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "..", "..", "game", "assets", "shared", "blender"))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

from osrs_kit_core import *          # noqa: E402,F401,F403
from osrs_kit_core import GAME_PX_PER_M, GAME_TILE_M, Kit  # noqa: E402,F401  (explicit, for linters)
