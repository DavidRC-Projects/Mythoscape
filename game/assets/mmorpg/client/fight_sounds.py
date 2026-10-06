"""Short sounds for a monster fight. Area music keeps playing underneath.

Only the local player's own swings and the blows aimed at them are heard.
Set USE_FIGHT_SOUNDS=0 to silence them.
"""
from __future__ import annotations

import os

import pygame

import feature_flags
from content import MONSTERS

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "assets", "sounds",
))
_CACHE = {}
_HELD = []
_DRAGON = {"dragon", "emberdeep_wyrm"}


def play_combat(client, msg, did_hit):
    if not feature_flags.USE_FIGHT_SOUNDS:
        return
    if not _mine(client, msg):
        return
    name, volume = _cue(client, msg, did_hit)
    # A zero on the hitsplat is a graze, not a solid blow.
    if did_hit and not msg.get("dodged") and int(msg.get("damage") or 0) <= 0:
        volume = min(volume, 0.28)
    _play(name, volume)


def _same(a, b):
    return a == b or str(a) == str(b)


def _mine(client, msg):
    me = (getattr(client, "player", None) or {}).get("id")
    if me is None:
        return False
    atk = msg.get("attacker_id")
    defender = msg.get("defender_id")
    if _same(atk, me) or _same(defender, me):
        return True
    return atk == f"pet:{me}"


def _cue(client, msg, did_hit):
    kind = msg.get("kind") or ""
    ranged = bool(msg.get("ranged"))
    dodged = bool(msg.get("dodged"))
    landed = bool(did_hit) and not dodged
    volume = 0.85 if msg.get("crit") else 0.7
    if kind == "player_magic_monster" or msg.get("magic_effect"):
        return ("spell_hit" if landed else "blade_miss", 0.62 if landed else 0.4)
    if kind in ("player_hits_monster", "pet_hits_monster"):
        if not landed:
            return ("arrow_loose" if ranged else "blade_miss", 0.4)
        if ranged:
            return ("arrow_hit", volume)
        return ("blade_hit", volume)
    if kind == "monster_hits_player":
        family = _family(client, msg.get("attacker_id"))
        if not landed:
            miss = "dragon_miss" if family == "dragon" else "beast_miss"
            return (miss, 0.42)
        if family == "dragon":
            return ("dragon_hit", 0.8)
        if family == "humanoid":
            return ("humanoid_hit", volume)
        return ("beast_hit", volume)
    if not landed:
        return ("blade_miss", 0.35)
    return ("blade_hit", volume)


def _family(client, monster_id):
    monster = client._monster_by_id(monster_id) if monster_id is not None else None
    if not monster:
        return "beast"
    mtype = monster.get("type") or ""
    if mtype in _DRAGON or "dragon" in mtype or "wyrm" in mtype:
        return "dragon"
    if (MONSTERS.get(mtype) or {}).get("humanoid"):
        return "humanoid"
    return "beast"


def _play(name, volume):
    path = os.path.join(_DIR, name + ".wav")
    if not os.path.isfile(path):
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        snd = _CACHE.get(name)
        if snd is None:
            snd = pygame.mixer.Sound(path)
            _CACHE[name] = snd
        channel = snd.play()
        if channel is not None:
            channel.set_volume(max(0.0, min(1.0, volume)))
        _HELD.append(snd)
        if len(_HELD) > 12:
            del _HELD[:-12]
    except Exception:
        pass
