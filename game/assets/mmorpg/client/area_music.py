"""One looping tune per place.

Old School RuneScape keeps a song going until you enter a new region,
then interrupts it so the new place is heard at once. A boss does the
same. Login uses the main theme. The opening comic stays silent so the
narration is alone.

Set USE_AREA_MUSIC=0 to disable this. Missing files are skipped.
"""
from __future__ import annotations

import os

import pygame

import feature_flags
import world_map as wm

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "music",
))
_VOLUME = 0.72
_current = None

_ZONE = {
    "village": "village",
    "fairy_village": "village",
    "city": "city",
    "fishing_village": "harbour",
    "forest": "forest",
    "mountains": "mountains",
    "mine": "mine",
    "dungeon": "dungeon",
    "volcano": "emberdeep",
    "shadow_crypt": "void",
    "wilderness": "wilderness",
}


def tick(client):
    if not feature_flags.USE_AREA_MUSIC:
        stop()
        return
    if getattr(client, "state", "") == "OPENING_COMIC":
        stop()
        return
    key = _key(client)
    if key == _current:
        return
    _play(key)


def stop():
    global _current
    if _current is None:
        return
    _current = None
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def _key(client):
    state = getattr(client, "state", "")
    if state in ("LOGIN", "STAT_ALLOC"):
        return "theme"
    if state != "GAME" or not getattr(client, "player", None):
        return None
    dungeon = getattr(client, "dungeon", None) or {}
    if dungeon.get("id") == "emberdeep":
        if _near_wyrm(client):
            return "wyrm"
        return "emberdeep"
    if dungeon.get("id") == "castle_realm":
        return "castle"
    if dungeon.get("v2") == "depths":
        return "depths"
    if dungeon.get("v2"):
        return "void"
    if dungeon:
        return "dungeon"
    for building in getattr(client, "buildings", None) or []:
        if building.get("kind") == "castle" and client.player_inside_building(building):
            return "castle"
    x, y = client.player_xy()
    return _ZONE.get(wm.get_zone(int(x), int(y)), "wilderness")


def _near_wyrm(client):
    px, py = client.player_xy()
    for monster in (getattr(client, "monsters", None) or {}).values():
        if monster.get("type") != "emberdeep_wyrm":
            continue
        if max(abs(int(monster.get("x", 0)) - int(px)), abs(int(monster.get("y", 0)) - int(py))) <= 6:
            return True
    return False


def _play(key):
    global _current
    if not key:
        stop()
        return
    _current = key
    path = os.path.join(_DIR, key + ".wav")
    if not os.path.isfile(path):
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.set_volume(_VOLUME)
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)
    except Exception:
        pass
