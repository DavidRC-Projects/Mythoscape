"""King's Castle Siege server foundations (M30).

Standalone, box-only. Nothing here is imported by, or imports, the live game
(server.py, crown_siege, castle_realm, throne, castle_owners). The feature is
OFF unless USE_KINGS_CASTLE_SIEGE is set to a true value.
"""
from .flags import enabled, FLAG_NAME

__all__ = ["enabled", "FLAG_NAME"]
