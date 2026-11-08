"""Feature flag for the standalone King's Castle Siege server path.

Default OFF. Separate from the live USE_CASTLE_REALM / USE_CASTLE_OWNERS flags.
"""
from __future__ import annotations

import os
from typing import Mapping, Optional

FLAG_NAME = "USE_KINGS_CASTLE_SIEGE"
_TRUE = ("1", "true", "yes", "on")


def enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(FLAG_NAME, "0")).strip().lower() in _TRUE
