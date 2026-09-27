"""
Panda3D single-building test scene (standalone — does not replace the live client).

Launch:
  python client.py --panda-building-proto
  python client.py --panda-building-proto --qa-shots

Original geometry only. Techniques learned from open-source references
(licenses checked — no vendored code / no copied assets):

  - Panda3D procedural-cube (Modified BSD): GeomVertexData, UHStatic, CCW faces
  - Epihaius procedural primitives (BSD-3): maker-pattern idea only
  - RTS_pygame: buildings as data + grid footprint separate from art (pattern only)

See README section "Panda3D building prototype" and coords.py for axes/yaw.
"""

from .app import main

__all__ = ["main"]
