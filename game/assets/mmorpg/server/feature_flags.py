"""Shared feature flags. Client and server both import this module."""
import os

def _on(name, default="1"):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")

# Bigger pre-rendered castle (moat, drawbridge, portcullis).
# Set USE_NEW_CASTLE=0 to keep today's volume castle and tile grid.
USE_NEW_CASTLE = _on("USE_NEW_CASTLE")
