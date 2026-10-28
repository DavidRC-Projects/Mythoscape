"""One tune (or short playlist) per place.

Old School RuneScape keeps a song going until you enter a new region,
then interrupts it so the new place is heard at once. A boss does the
same. Login uses the main theme. The opening comic stays silent so the
narration is alone.

Village plays Rising Theme once, then The Narrow Way, then cycles.
Places without their own Suno track use Rising Theme until one is added.
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
_END_EVENT = pygame.USEREVENT + 31

# Zone name -> region key (file stem, or "village" for the playlist).
# Anything not listed falls back to Rising Theme ("theme").
_ZONE = {
    "village": "village",
    "fairy_village": "fairy_glade",
    "city": "city",
    "fishing_village": "harbour",
    "mountains": "cautious_march",
    # Emberdeep overworld + Void Sanctum share crypt so the track keeps playing
    # when you walk between the volcano field and the sanctum approach.
    "volcano": "crypt",
    "shadow_crypt": "crypt",
}

# Places that play a sequence (each track once), then wrap. Login "theme" loops alone.
_PLAYLISTS = {
    # Rising Theme → The Narrow Way → … (village only)
    "village": ("theme", "narrow_way"),
}

_current = None          # region key currently selected
_track = None            # file stem currently playing
_playlist_index = 0


def end_event_type():
    return _END_EVENT


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
    _play_region(key)


def on_track_ended(client):
    """Advance village (etc.) playlist when a non-looping track finishes."""
    global _playlist_index, _track
    if not feature_flags.USE_AREA_MUSIC:
        return
    if _current is None:
        return
    # Still in the same region?
    if _key(client) != _current:
        return
    playlist = _PLAYLISTS.get(_current)
    if not playlist:
        return
    _playlist_index = (_playlist_index + 1) % len(playlist)
    _start_track(playlist[_playlist_index], loop=False)


def stop():
    global _current, _track, _playlist_index
    if _current is None and _track is None:
        return
    _current = None
    _track = None
    _playlist_index = 0
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
    if dungeon.get("id") == "castle_realm":
        return "castle"
    # Void Sanctum + Emberdeep (inside or on the approach) share crypt music.
    if dungeon.get("id") == "emberdeep":
        return "crypt"
    if dungeon.get("v2") or dungeon.get("id") in ("void", "sanctum", "shadow_crypt"):
        return "crypt"
    # Other private dungeons — Rising Theme until they get their own track
    if dungeon:
        return "theme"
    for building in getattr(client, "buildings", None) or []:
        if building.get("kind") == "castle" and client.player_inside_building(building):
            return "castle"
    x, y = client.player_xy()
    x, y = int(x), int(y)
    if _in_fairy_music(x, y):
        return "fairy_glade"
    if _in_wolf_pass(x, y):
        return "cautious_march"
    if _in_emberdeep_music(x, y):
        return "crypt"
    return _ZONE.get(wm.get_zone(x, y), "theme")


def _in_emberdeep_music(x, y):
    """Crypt track covers the Emberdeep scorched field even if zone edges clip it."""
    if wm.get_zone(x, y) == "volcano":
        return True
    try:
        return bool(wm.is_emberdeep_volcano_field(x, y))
    except Exception:
        return False


def _in_fairy_music(x, y):
    """Fairy glade tune covers the village, entrance/exit lanes, and approach roads.

    get_zone('fairy_village') stops at the box edge, so the north arch approach
    (still village) and the south exit lane (wilderness) would otherwise cut the
    music short.
    """
    if wm.get_zone(x, y) == "fairy_village":
        return True
    try:
        import fairy_glade as fg
    except Exception:
        return False
    if fg.is_lane(x, y):
        return True
    # North approach: village road → arch (mouth is y=52; lane starts there).
    if 27 <= x <= 36 and 43 <= y <= 55:
        return True
    # Just past the south arch onto the meadow.
    if 11 <= x <= 16 and 97 <= y <= 102:
        return True
    return False


def _in_wolf_pass(x, y):
    """Cautious March for the Wolf Pass massif (overlaps the forest zone box)."""
    try:
        import wolf_pass
    except Exception:
        return False
    if not wolf_pass.enabled():
        return wm.get_zone(x, y) == "mountains"
    return bool(wolf_pass.in_massif(x, y))


def _play_region(key):
    global _current, _playlist_index
    if not key:
        stop()
        return
    _current = key
    _playlist_index = 0
    playlist = _PLAYLISTS.get(key)
    if playlist:
        _start_track(playlist[0], loop=False)
        return
    # Login theme and single-track regions loop forever
    _start_track(key, loop=True)


def _start_track(stem, loop=True):
    global _track
    _track = stem
    path = os.path.join(_DIR, stem + ".wav")
    if not os.path.isfile(path):
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.set_endevent(_END_EVENT)
        pygame.mixer.music.set_volume(_VOLUME)
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1 if loop else 0)
    except Exception:
        pass
