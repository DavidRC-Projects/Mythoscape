"""Overworld HD NPC sheets from game/assets/npc_hd.

Same blit as the fairy villagers: feet on the tile, idle facing the camera.
King court and the fairy NPCs are not drawn here. If a sheet is missing,
draw_npc returns False and the caller keeps the existing figure.
"""
from __future__ import annotations

import os

import pygame

_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "npc_hd", "assets", "npcs",
))

OVERWORLD_HD = {
    "shopkeeper_joe",
    "jeweler_lira",
    "fletcher_elena",
    "blacksmith_gareth",
    "banker_iris",
    "elder_miriam",
    "farmer_tom",
    "innkeeper_sarah",
    "wizard_elowen",
    "guard_marcus",
    "guard_aldric",
    "village_kid_timmy",
    "village_idiot_bob",
    "priest_cedric",
    "monk_healer",
    "pet_keeper_luna",
    "old_fisherman_pete",
    "mia",
    "mysterious_traveler",
    "merchant_wanderer",
    "mine_scout",
    "dungeon_hermit",
    "mad_scientist",
    "pass_scout",
    "king",
    "mythos_knight_1",
    "mythos_knight_2",
    "mythos_knight_3",
    "mythos_knight_4",
    "tackle_merchant",
    "fishmonger_kai",
    "harbour_cook",
    "herald_rowan",
    "city_vendor_mira",
    "packer_nell",
}

_IMAGES = {}
_META = {}


def _load(path):
    if path in _IMAGES:
        return _IMAGES[path]
    if not os.path.isfile(path):
        _IMAGES[path] = None
        return None
    image = pygame.image.load(path).convert_alpha()
    _IMAGES[path] = image
    return image


def _meta(npc_id):
    path = os.path.join(_DIR, npc_id, "meta.json")
    if path not in _META:
        if not os.path.isfile(path):
            _META[path] = {}
        else:
            import json
            with open(path, encoding="utf-8") as handle:
                _META[path] = json.load(handle)
    return _META[path]


def _scale_for(tile):
    if tile >= 80:
        return "2x", 80
    return "1x", 40


def _scaled(path, tile, base):
    image = _load(path)
    if image is None or tile == base:
        return image
    cache = (path, tile)
    if cache not in _IMAGES:
        w = max(1, int(round(image.get_width() * tile / float(base))))
        h = max(1, int(round(image.get_height() * tile / float(base))))
        _IMAGES[cache] = pygame.transform.smoothscale(image, (w, h))
    return _IMAGES[cache]


def _px(meta, tile, fallback):
    tag, base = _scale_for(tile)
    point = (meta.get("feet_px") or {}).get(tag) or fallback
    scale = tile / float(base)
    return point[0] * scale, point[1] * scale


def _sheet_facing(face, moving):
    if not moving:
        return "s"
    if face in ("back", "n"):
        return "n"
    if face in (-1, "-1", "w"):
        return "w"
    if face in (1, "1", "e"):
        return "e"
    return "s"


def draw_npc(client, n, cx, cy, tile, t, face="s", moving=False):
    """Blit the HD sheet. False means this id has no pack art yet."""
    npc_id = n.get("id")
    if npc_id not in OVERWORLD_HD:
        return False
    meta = _meta(npc_id)
    tag, base = _scale_for(tile)
    frames = max(1, int(meta.get("frames") or 8))
    fps = float(meta.get("fps") or 8)
    idx = int(t * fps) % frames
    facing = _sheet_facing(face, moving)
    path = os.path.join(_DIR, npc_id, f"sprite_{tag}", facing, f"f{idx:02d}.png")
    image = _scaled(path, tile, base)
    if image is None:
        return False
    fx, fy = _px(meta, tile, [48, 118])
    foot_y = cy + tile // 2
    left = cx - fx
    top = foot_y - fy
    client.screen.blit(image, (left, top))
    client.blit_nameplate(n.get("name") or npc_id, cx, int(top) - 2, (255, 230, 160))
    return True


def portrait(client, npc_id, height=96):
    if npc_id not in OVERWORLD_HD:
        return None
    path = os.path.join(_DIR, npc_id, "portrait_bust_512.png")
    image = _load(path)
    if image is None:
        return None
    cache = (path, "portrait", height)
    if cache not in _IMAGES:
        w = max(1, int(round(image.get_width() * height / float(image.get_height()))))
        _IMAGES[cache] = pygame.transform.smoothscale(image, (w, height))
    return _IMAGES[cache]
