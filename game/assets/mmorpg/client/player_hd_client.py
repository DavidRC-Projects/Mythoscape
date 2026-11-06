"""
HD Player Asset Loader + Paper-Doll Renderer

Loads sprites from game/assets/player_hd/ and composites layers at runtime
based on appearance dict. Frame timing follows meta.json so walk, combat and
skilling stay on the same clock as the 2D figure.
"""
import json
import math
import os

import pygame

import slung_gear as _slung
import helmet_overlay as _helm

_BASE = os.path.join(
    os.path.dirname(__file__), "..", "..", "player_hd", "assets"
)
_META_PATH = os.path.join(_BASE, "meta.json")
_CATALOGUE_PATH = os.path.join(_BASE, "catalogue.json")

_IMAGES = {}
_FRAMES = {}
_IMAGE_MISS = object()
_META = None
_CATALOGUE = None

MELEE_PROGRESS = [0.0, 0.1, 0.22, 0.34, 0.48, 0.55, 0.62, 0.71, 0.8, 0.91]
RANGED_PROGRESS = [0.0, 0.12, 0.24, 0.36, 0.48, 0.55, 0.72, 0.86]
_BONE = (225, 215, 185)


def _load_meta():
    global _META
    if _META is None:
        if not os.path.isfile(_META_PATH):
            _META = {}
        else:
            import json
            with open(_META_PATH, encoding="utf-8") as f:
                _META = json.load(f)
    return _META


def _load_catalogue():
    global _CATALOGUE
    if _CATALOGUE is None:
        if not os.path.isfile(_CATALOGUE_PATH):
            _CATALOGUE = {}
        else:
            import json
            with open(_CATALOGUE_PATH, encoding="utf-8") as f:
                _CATALOGUE = json.load(f)
    return _CATALOGUE


def _load_image(path):
    hit = _IMAGES.get(path, _IMAGE_MISS)
    if hit is not _IMAGE_MISS and hit is not None:
        return hit
    # Retry when a prior miss was cached (e.g. hair masks landed after the shop opened).
    full = os.path.join(_BASE, path)
    if not os.path.isfile(full):
        _IMAGES[path] = None
        return None
    _IMAGES[path] = pygame.image.load(full).convert_alpha()
    return _IMAGES[path]


def _scale_for(tile, preview=False):
    """Source scale at or above the target, then smoothscale down.

    preview=True prefers 8x AI idle portraits when present (downscaled to tile);
    falls back to 4x via _resolve_scale if an 8x sheet is missing.
    """
    if tile <= 40:
        return "1x", 40
    if tile <= 80:
        return "2x", 80
    # 8x preview temporarily disabled — AI sheets shifted/clipped and broke the stage.
    # Re-enable when 8x assets are re-centered to meta feet_px.
    if False and (preview or tile > 160):
        return "8x", 320
    return "4x", 160


def _frame_surface(rel, frame_idx, scale_tag, tile, base):
    """One frame, cached by path, frame and pixel size."""
    strip = _load_image(rel)
    if strip is None:
        return None
    canvas = _load_meta().get("canvas", {}).get(scale_tag, [144, 144])
    cw, ch = int(canvas[0]), int(canvas[1])
    if cw <= 0 or strip.get_width() < cw:
        return None
    max_i = max(0, strip.get_width() // cw - 1)
    frame_idx = max(0, min(int(frame_idx), max_i))
    k = tile / float(base)
    tw = max(1, int(round(cw * k)))
    th = max(1, int(round(min(ch, strip.get_height()) * k)))
    key = (rel, frame_idx, tw, th)
    hit = _FRAMES.get(key)
    if hit is not None:
        return hit
    src_h = min(ch, strip.get_height())
    frame = strip.subsurface((frame_idx * cw, 0, cw, src_h))
    if (tw, th) != (cw, src_h):
        frame = pygame.transform.smoothscale(frame, (tw, th))
    else:
        frame = frame.copy()
    _FRAMES[key] = frame
    return frame


def _facing_str(face):
    if face in ("back", "n"):
        return "n"
    if face in (-1, "-1", "w"):
        return "w"
    if face in (1, "1", "e"):
        return "e"
    return "s"


# ---- gathering loops ---------------------------------------------------------------------------
# The server sends the skill; the strips are named by pose.
GATHER_ANIM_FOR_SKILL = {"woodcutting": "chop", "mining": "mine", "fishing": "fish"}
# Fishing tool -> its own strip once it exists (fish_net_e.png ...); until then the rod strip plays.
FISH_TOOL_ANIM = {"small_fishing_net": "fish_net", "harpoon": "fish_harpoon", "lobster_pot": "fish_pot"}
# One loop = 3 server ticks (1.8 s) so the impact lines up with the gather roll; rod 4 ticks, pot 5.
GATHER_LOOP_MS = {"chop": 1800, "mine": 1800, "fish": 2400, "fish_net": 2400, "fish_harpoon": 2400,
                  "fish_pot": 3000}
# 12-frame strips (COMBAT_SKILLING_SPEC part 2): frame i starts at this fraction of the loop.
GATHER_PROGRESS = {
    "mine": tuple(ms / 1800 for ms in (0, 150, 300, 450, 550, 650, 750, 883, 1017, 1150, 1367, 1583)),
    "chop": tuple(ms / 1800 for ms in (0, 167, 333, 500, 600, 700, 800, 933, 1067, 1200, 1400, 1600)),
    "fish": tuple(ms / 2400 for ms in (0, 167, 333, 500, 650, 800, 1000, 1250, 1500, 1750, 2000, 2200)),
}
# Today's 8-frame placeholder strips keep their original cadence.
_LEGACY_GATHER_SPEED = {"chop": 1.1, "mine": 1.05, "fish": 0.55}


def is_gather_anim(anim):
    return anim in ("chop", "mine") or str(anim or "").startswith("fish")


def gather_anim(anim, tool=None):
    """Skill or pose name -> the strip to play. A tool-specific fishing strip is used once it's in meta.json."""
    anim = GATHER_ANIM_FOR_SKILL.get(anim, anim)
    if anim == "fish" and tool in FISH_TOOL_ANIM:
        special = FISH_TOOL_ANIM[tool]
        if special in (_load_meta().get("anims") or {}):
            return special
    return anim


def _gather_frame(anim, t):
    info = (_load_meta().get("anims") or {}).get(anim) or {}
    frames = max(1, int(info.get("frames") or 8))
    if t is None:
        return 0
    base = "fish" if anim.startswith("fish") else anim
    if frames == 8 and not info.get("loop_ms") and base in _LEGACY_GATHER_SPEED and anim == base:
        return int(((t * _LEGACY_GATHER_SPEED[base]) % 1.0) * 8)
    loop = float(info.get("loop_ms") or GATHER_LOOP_MS.get(anim) or GATHER_LOOP_MS.get(base, 1800)) / 1000.0
    u = (t % loop) / loop
    table = info.get("progress") or GATHER_PROGRESS.get(base)
    if not table or len(table) != frames:
        return min(frames - 1, int(u * frames))
    frame = 0
    for i, p in enumerate(table):
        if p <= u:
            frame = i
    return frame


def _frame_for_anim(anim, t=None, progress=None, hit_t=-1.0, death_t=-1.0):
    if death_t >= 0:
        u = min(1.0, death_t / 1.2)
        return ("death", min(7, int(u * 8)))
    if hit_t >= 0 and anim in ("idle", "walk"):
        u = min(1.0, hit_t / 0.36)
        return ("hit", min(3, int(u * 4)))
    if anim == "melee":
        if progress is None:
            return ("idle", 0)
        frame = 0
        for i, p in enumerate(MELEE_PROGRESS):
            if p <= progress:
                frame = i
        return ("melee", frame)
    if anim == "ranged":
        if progress is None:
            return ("idle", 0)
        frame = 0
        for i, p in enumerate(RANGED_PROGRESS):
            if p <= progress:
                frame = i
        return ("ranged", frame)
    if is_gather_anim(anim):
        return (anim, _gather_frame(anim, t))
    if anim == "walk":
        ph = ((t * 1.15) % 1.0) if t is not None else 0.0
        return ("walk", int(ph * 8))
    ph = ((t / math.pi) % 1.0) if t is not None else 0.0
    return ("idle", int(ph * 8))


def _layer_parts(sex, scale_tag, layer, anim, facing, frame_idx, tile, base):
    """Base and tint independently. Either may be missing.

    Returns (main, tint, scale_tag, base) so skin/hair masks load at the same scale.
    """
    scale_tag, base = _resolve_scale(sex, layer, anim, facing, frame_idx, scale_tag, base)
    stem = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}"
    main = _frame_surface(stem + ".png", frame_idx, scale_tag, tile, base)
    tint = _frame_surface(stem + "_tint.png", frame_idx, scale_tag, tile, base)
    return main, tint, scale_tag, base


def _resolve_scale(sex, layer, anim, facing, frame_idx, scale_tag, base):
    """Fall back 8x→4x→2x when a preview sheet is missing or is a single-frame idle."""
    if scale_tag == "8x" and not _has_scale_frame(sex, "8x", layer, anim, facing, frame_idx):
        scale_tag, base = "4x", 160
    if scale_tag == "4x" and not _has_scale_frame(sex, "4x", layer, anim, facing, frame_idx):
        # Missing 4x strip (or a single-frame 4x portrait while animating): use 2x quietly.
        scale_tag, base = "2x", 80
    return scale_tag, base


def _has_4x_frame(sex, layer, anim, facing, frame_idx):
    return _has_scale_frame(sex, "4x", layer, anim, facing, frame_idx)


def _has_scale_frame(sex, scale_tag, layer, anim, facing, frame_idx):
    strip = _load_image(f"{sex}/{scale_tag}/{layer}/{anim}_{facing}.png")
    if strip is None:
        strip = _load_image(f"{sex}/{scale_tag}/{layer}/{anim}_{facing}_tint.png")
    if strip is None:
        return False
    frames = max(1, strip.get_width() // max(1, strip.get_height()))
    if frames == 1 and scale_tag in ("4x", "8x"):
        # Single-frame portrait (creator / shop). Hold it only for frame 0 — if the 2x strip
        # animates, frames 1–7 must use 2x so the figure does not pop between scales.
        two = _load_image(f"{sex}/2x/{layer}/{anim}_{facing}.png")
        if two is not None and two.get_width() // max(1, two.get_height()) > 1 and int(frame_idx) > 0:
            return False
    return frame_idx < frames or frames > 1


_MASKS = None              # (sex, drawn layer) -> erase_mask layer
_MASK_INV = {}             # (id(frame), flip) -> inverted mask surface
_MASK_WARNED = set()


def _mask_index():
    """Catalogue layers with role erase_mask, keyed by the layer they hide under (mask_for)."""
    global _MASKS
    if _MASKS is None:
        _MASKS = {}
        cat = _load_catalogue()
        for group in ("armour_layers", "weapon_layers"):
            for entry in cat.get(group, []) or []:
                if entry.get("role") != "erase_mask" or not entry.get("mask_for"):
                    continue
                kinds = entry.get("kinds") or list((entry.get("files") or {}).keys())
                for sex in kinds:
                    _MASKS[(sex, entry["mask_for"])] = entry.get("layer") or entry["id"]
    return _MASKS


def mask_layer_for(sex, layer_name):
    return _mask_index().get((sex, layer_name))


def _inverted_mask(frame, flip):
    """RGB 255, alpha 255 - mask alpha. BLEND_RGBA_MULT with it erases under the mask."""
    key = (id(frame), bool(flip))
    hit = _MASK_INV.get(key)
    if hit is not None and hit[0] is frame:
        return hit[1]
    src = pygame.transform.flip(frame, True, False) if flip else frame
    alpha_only = src.copy()
    alpha_only.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    inv = pygame.Surface(src.get_size(), pygame.SRCALPHA)
    inv.fill((255, 255, 255, 255))
    inv.blit(alpha_only, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    _MASK_INV[key] = (frame, inv)
    return inv


def _build_item_map():
    items = {}
    for entry in _load_catalogue().get("items", []):
        items[entry["id"]] = entry
    return items


_MISSING_STRIPS = set()
last_draw = {}


def _warn_missing_strip(sex, anim, facing):
    key = (sex, anim, facing)
    if key in _MISSING_STRIPS:
        return
    _MISSING_STRIPS.add(key)
    import logging
    logging.getLogger("player_hd").warning(
        "missing %s %s_%s strip, using the east strip", sex, anim, facing,
    )


def _weapon_z_anim(layer_name, anim, facing_tag):
    """z override for one attack facing. melee_n / ranged_n draw the weapon on top."""
    for entry in _load_catalogue().get("weapon_layers") or []:
        if entry.get("layer") != layer_name and entry.get("id") != layer_name:
            continue
        table = (entry.get("z_anim") or {}).get(anim) or {}
        if facing_tag in table:
            return table[facing_tag]
    return None


def _effective_z(layer_name, zmap, anim, facing_tag):
    override = _weapon_z_anim(layer_name, anim, facing_tag)
    if override is not None:
        return override
    return (zmap or {}).get(facing_tag, 50)


def _layer_z(layer_name, fallback):
    cat = _load_catalogue()
    for group in ("armour_layers", "weapon_layers"):
        for entry in cat.get(group) or []:
            if entry.get("layer") == layer_name or entry.get("id") == layer_name:
                return entry.get("z") or fallback
    item = _build_item_map().get(layer_name)
    if item and item.get("layer") == layer_name:
        return item.get("z") or fallback
    for entry in _load_catalogue().get("items", []):
        if entry.get("layer") == layer_name:
            return entry.get("z") or fallback
    return fallback


def _parse_hair_colour(colour_id):
    for hc in _load_catalogue().get("hair_palette") or []:
        if hc.get("id") == colour_id:
            rgb = hc.get("mul") or [40, 32, 28]
            return tuple(int(c) for c in rgb[:3])
    return (112, 76, 52)


def _art_id(item_id):
    """Items drawn with another item's art (content ITEMS "art_as", e.g. the Recruit's Bronze kit)."""
    try:
        from content import ITEMS as _items
    except Exception:
        return str(item_id or "")
    return str((_items.get(str(item_id)) or {}).get("art_as") or item_id or "")


def _tier_rgb(item_id, named=None):
    item_id = _art_id(item_id) if item_id else item_id
    cat = _load_catalogue()
    tints = cat.get("tier_tints") or {}
    gain = float(cat.get("tier_tint_gain") or 1.0)
    if named:
        key = named
    else:
        key = (item_id or "steel").split("_", 1)[0]
        if key not in tints:
            key = "steel"
    rgb = tints.get(key) or tints.get("steel") or [170, 175, 185]
    return tuple(min(255, int(round(c * gain))) for c in rgb[:3])


def _slot_item(appearance, slot, sex, item_map):
    """Saved id, or the starter default when the slot is empty."""
    chosen = appearance.get(slot)
    if chosen and chosen in item_map:
        return item_map[chosen]
    defaults = (_load_catalogue().get("defaults") or {}).get(sex) or {}
    fallback = defaults.get(slot)
    if fallback and fallback in item_map:
        return item_map[fallback]
    return None


# Eclipse gear has its own untinted HD layers (art carries its own black + gold).
_ECLIPSE_WEAPONS = {
    "eclipse_cleaver": "wpn_axe_eclipse",
    "eclipse_sword": "wpn_sword_eclipse",
}
_ECLIPSE_BODY = {"eclipse_body": [("arm_platebody_eclipse", None), ("arm_gauntlets_eclipse", None)]}
_ECLIPSE_LEGS = {"eclipse_legs": [("arm_platelegs_eclipse", None), ("arm_sabatons_eclipse", None)]}
_ECLIPSE_HELMS = {"eclipse_helmet": ("arm_helm_eclipse", None)}


_GENERIC_LAYERS = (
    "wpn_sword", "wpn_axe", "wpn_pickaxe", "wpn_bow", "wpn_staff", "wpn_rod",
    "arm_helm", "arm_platebody", "arm_chainbody", "arm_platelegs", "arm_gauntlets", "arm_sabatons",
    "arm_kiteshield",
)


def base_layer(layer_name):
    """Generic layer a tier-specific layer derives from (wpn_axe_eclipse / wpn_axe_bronze -> wpn_axe).

    Anchors and swing smears are keyed by the generic weapon layer.
    """
    name = str(layer_name or "")
    for generic in _GENERIC_LAYERS:
        if name.startswith(generic + "_"):
            return generic
    return name


# ---- tier art from the catalogue ("matches": item id, or "shown with <item id>") ----------------
_TIER_INDEX = None          # item id -> [(layer, sexes)] in catalogue order, main layer first
_ART_PRESENT = {}           # (sex, layer) -> bool


def _tier_index():
    global _TIER_INDEX
    if _TIER_INDEX is None:
        idx = {}
        cat = _load_catalogue()
        for group in ("armour_layers", "weapon_layers"):
            for entry in cat.get(group) or []:
                if entry.get("role") == "erase_mask":
                    continue
                match = str(entry.get("matches") or "").strip()
                if match.startswith("shown with "):
                    item, main = match[len("shown with "):].strip(), False
                else:
                    item, main = match, True
                if not item:
                    continue
                layer = entry.get("layer") or entry.get("id")
                sexes = set((entry.get("files") or {}).keys()) or {"male", "female"}
                rows = idx.setdefault(item, [])
                rows.insert(sum(1 for r in rows if r[2]) if main else len(rows), (layer, sexes, main))
        _TIER_INDEX = {k: [(layer, sexes) for layer, sexes, _m in v] for k, v in idx.items()}
    return _TIER_INDEX


def _art_present(sex, layer):
    """True once that tier layer's strips are on disk (tiers arrive one at a time)."""
    key = (sex, layer)
    if key not in _ART_PRESENT:
        root = os.path.join(_BASE, sex, "1x", layer)
        _ART_PRESENT[key] = any(os.path.isfile(os.path.join(root, f"idle_{f}{v}.png"))
                                for f in ("s", "e") for v in ("", "_tint", "_mask"))
    return _ART_PRESENT[key]


def _tier_layers(item_id, sex):
    """[(layer, None)] when this item's own tier art is catalogued and present, else None."""
    if not item_id or not sex:
        return None
    rows = _tier_index().get(_art_id(item_id))
    if not rows:
        return None
    out = [(layer, None) for layer, sexes in rows if sex in sexes and _art_present(sex, layer)]
    if not out or len(out) != sum(1 for _l, sexes in rows if sex in sexes):
        return None      # half a set on disk: keep the tinted generic look until it is complete
    return out


def _weapon_spec(item_id, sex=None):
    if not item_id:
        return None, None
    iid = str(item_id)
    if iid in _ECLIPSE_WEAPONS:
        return _ECLIPSE_WEAPONS[iid], None
    tier = _tier_layers(iid, sex)
    if tier:
        return tier[0]
    if iid.endswith("_battleaxe") or iid.endswith("_axe"):
        return "wpn_axe", _tier_rgb(iid)
    if iid.endswith("_longsword") or iid.endswith("_sword"):
        return "wpn_sword", _tier_rgb(iid)
    if iid.endswith("_pickaxe"):
        return "wpn_pickaxe", _tier_rgb(iid)
    if "bow" in iid:
        return "wpn_bow", _tier_rgb(iid, "wood")
    if "staff" in iid or "wand" in iid:
        return "wpn_staff", _tier_rgb(iid)
    return None, None


def _body_spec(item_id, sex=None):
    if not item_id:
        return None
    iid = str(item_id)
    if iid in _ECLIPSE_BODY:
        return list(_ECLIPSE_BODY[iid])
    tier = _tier_layers(iid, sex)
    if tier:
        return tier
    if iid in ("leather_body",):
        return [("arm_chainbody", _tier_rgb(iid, "leather"))]
    if iid.endswith("_chainbody"):
        return [("arm_chainbody", _tier_rgb(iid))]
    if iid.endswith("_body"):
        tint = _tier_rgb(iid)
        return [("arm_platebody", tint), ("arm_gauntlets", tint)]
    return None


def _legs_spec(item_id, sex=None):
    if not item_id:
        return None
    iid = str(item_id)
    if iid in _ECLIPSE_LEGS:
        return list(_ECLIPSE_LEGS[iid])
    tier = _tier_layers(iid, sex)
    if tier:
        return tier
    if iid == "leather_chaps":
        return [("arm_platelegs", _tier_rgb(iid, "leather"))]
    if iid.endswith("_chainlegs"):
        return [("arm_platelegs", _tier_rgb(iid))]
    if iid.endswith("_legs"):
        tint = _tier_rgb(iid)
        return [("arm_platelegs", tint), ("arm_sabatons", tint)]
    return None


def _helm_spec(item_id, sex=None):
    if not item_id:
        return None
    iid = str(item_id)
    if iid in _ECLIPSE_HELMS:
        return _ECLIPSE_HELMS[iid]
    tier = _tier_layers(iid, sex)
    if tier:
        return tier[0]
    if iid == "leather_cowl":
        return ("arm_helm", _tier_rgb(iid, "leather"))
    if iid == "bone_crown":
        return ("arm_helm", _BONE)
    if iid.endswith("_helmet"):
        return ("arm_helm", _tier_rgb(iid))
    return None


def _shield_spec(item_id, sex=None):
    if not item_id:
        return None
    iid = str(item_id)
    tier = _tier_layers(iid, sex)
    if tier:
        return tier[0]
    if iid == "wooden_shield":
        return ("arm_kiteshield", _tier_rgb(iid, "wood"))
    if iid.endswith("_shield") or iid.endswith("_sq_shield"):
        return ("arm_kiteshield", _tier_rgb(iid))
    return None


def _hex_rgb(value, fallback=(200, 170, 150)):
    try:
        text = str(value).lstrip("#")
        return tuple(int(text[k:k + 2], 16) for k in (0, 2, 4))
    except (ValueError, TypeError):
        return fallback


def skin_tone_id(appearance):
    """Saved skin_tone, else the legacy skin_light/tan/deep alias, else the default tone."""
    cat = _load_catalogue()
    appearance = appearance or {}
    ids = [t.get("id") for t in cat.get("skin_palette") or []]
    tone = appearance.get("skin_tone")
    if tone in ids:
        return tone
    alias = (cat.get("skin_aliases") or {}).get(appearance.get("skin"))
    if alias in ids:
        return alias
    default = ((cat.get("defaults") or {}).get("male") or {}).get("skin_tone") or "tone_3"
    return default if default in ids or not ids else ids[0]


def skin_rgb(tone_id):
    for tone in _load_catalogue().get("skin_palette") or []:
        if tone.get("id") == tone_id:
            return _hex_rgb(tone.get("hex"))
    return (232, 192, 160)


def garment_rgb(item, palette_id=None):
    """(base, trim) for a set piece in the chosen palette (palette 1 when not offered)."""
    pals = list(item.get("palettes") or [])
    if not pals:
        return None
    if palette_id not in pals:
        palette_id = pals[0]
    entry = (_load_catalogue().get("garment_palettes") or {}).get(palette_id) or {}
    return _hex_rgb(entry.get("base"), (128, 128, 128)), _hex_rgb(entry.get("trim"), (201, 160, 62))


def resolve_layer(item, sex):
    """(layer, placeholder). art_layer once its strips are on disk; else "layer", which the catalogue
    keeps pointed at art that exists today (so older renderers never lose the HD body)."""
    art = item.get("art_layer")
    if art and _art_present(sex, art):
        return art, False
    layer = item.get("layer")
    if layer and _art_present(sex, layer):
        return layer, bool(art)
    return None, False


def _cosmetic_layers(appearance, sex, item_map):
    """Cloak back, body (skin tint), clothes, cloak, jewellery, hair, head, held. Armour hiding is the caller's."""
    layers = []
    skin = item_map.get("skin_base") or _slot_item(appearance, "skin", sex, item_map)
    if skin:
        layer, placeholder = resolve_layer(skin, sex)
        if layer:
            spec = {"skin": skin_rgb(skin_tone_id(appearance)), "placeholder": placeholder}
            layers.append((layer, spec, skin.get("z") or {"s": 10, "e": 10, "n": 10, "w": 10}, "body"))
        if _art_present(sex, "face_detail"):
            layers.append(("face_detail", None, {"s": 11, "e": 11, "n": 11, "w": 11}, "face"))
    hair_rgb = _parse_hair_colour(appearance.get("hair_colour", "dark_brown"))
    layers.append(("brows", hair_rgb, {"s": 12, "e": 12, "n": 12, "w": 12}, "brows"))
    hair = _slot_item(appearance, "hair", sex, item_map)
    if hair:
        layers.append((hair["layer"], hair_rgb, hair.get("z") or {"s": 40, "e": 40, "n": 40, "w": 40}, "hair"))
    palette = appearance.get("palette")
    outfit = appearance.get("outfit")
    outfit_item = item_map.get(outfit) if outfit else None
    if outfit_item and outfit_item.get("layer"):
        zmap = outfit_item.get("z") or {"s": 30, "e": 30, "n": 30, "w": 30}
        if outfit_item.get("set"):
            layer, placeholder = resolve_layer(outfit_item, sex)
            colours = garment_rgb(outfit_item, palette)
            if layer:
                layers.append((layer, {"garment": colours, "placeholder": placeholder}, zmap, "outfit"))
            level = int(appearance.get("outfit_level") or 1)
            overlays = (outfit_item.get("upgrade") or {}).get("overlays") or []
            for overlay in overlays[: max(0, level - 1)]:
                if not placeholder and _art_present(sex, overlay):
                    layers.append((overlay, {"garment": colours, "placeholder": False},
                                   {k: v + 0.5 for k, v in zmap.items()}, "outfit"))
        else:
            tint = tuple(outfit_item.get("tint") or [255, 255, 255]) if outfit_item.get("tintable") else None
            layers.append((outfit_item["layer"], tint, zmap, "outfit"))
    for slot, tag in (("top", "top"), ("bottom", "bottom"), ("shoes", "shoes")):
        item = _slot_item(appearance, slot, sex, item_map)
        if not item:
            continue
        tint = tuple(item.get("tint") or [255, 255, 255]) if item.get("tintable") else None
        layers.append((item["layer"], tint, item.get("z") or {"s": 20, "e": 20, "n": 20, "w": 20}, tag))
    for acc_id in appearance.get("accessories") or []:
        item = item_map.get(acc_id)
        if not item:
            continue
        tint = tuple(item.get("tint") or [255, 255, 255]) if item.get("tintable") else None
        layers.append((item["layer"], tint, item.get("z") or {"s": 45, "e": 45, "n": 45, "w": 45}, acc_id))
    wanted = [("cloak", appearance.get("cloak"))]
    wanted += [("jewellery", jid) for jid in (appearance.get("jewellery") or [])[:3]]
    wanted += [("head", appearance.get("head")), ("held", appearance.get("held"))]
    for tag, item_id in wanted:
        item = item_map.get(item_id) if item_id else None
        if not item or item.get("slot") != tag:
            continue
        layer, placeholder = resolve_layer(item, sex)
        if not layer:
            continue      # no art yet and no placeholder: shown in the shop, not on the model
        zmap = item.get("z") or {"s": 46, "e": 46, "n": 46, "w": 46}
        spec = {"garment": garment_rgb(item, palette), "placeholder": placeholder} if item.get("tintable") else None
        if tag == "cloak" and not placeholder and _art_present(sex, layer + "_back"):
            layers.append((layer + "_back", spec, {"s": 1, "e": 1, "n": 66, "w": 1}, tag))
        layers.append((layer, spec, zmap, tag))
    return layers


# ---- whole-figure HD outfits (tier art painted as one figure, skin tinted at runtime) -----------
_WHOLE_ANIMS = ("idle", "walk")


ARMOUR_TIERS = ("bronze", "iron", "steel", "mithril", "adamant", "mythos", "eclipse")
WHITE_TOP = "top_white_shirt"
WHITE_BOTTOM = "bottom_white_leggings"


def armour_slots_worn(equipment):
    """True when chest and/or legs are equipped (any tier)."""
    eq = equipment or {}
    return bool(eq.get("body") or eq.get("legs"))


def needs_armour_underlay(equipment):
    """Partial or mixed-tier body/legs: compose painted HD halves + white underclothes.
    Matching body+legs of one tier still use the painted set figure (set_tier)."""
    if not armour_slots_worn(equipment):
        return False
    return set_tier(equipment) is None


def armour_underlay_look(appearance, sex, equipment):
    """Keep skin/hair/face; clear outfit figure; put white shirt and/or leggings in open slots.
    Chest-only -> white leggings; legs-only -> white shirt; both (mixed tiers) -> neither underlay
    (each armour piece covers its slot)."""
    look = dict(appearance or {})
    sex = "female" if sex == "female" else "male"
    eq = equipment or {}
    has_body = bool(eq.get("body"))
    has_legs = bool(eq.get("legs"))
    # Drop whole-figure outfit/collection so layered cosmetics + armour pieces show.
    look["outfit"] = None
    look["set"] = None
    if has_body and not has_legs:
        look["top"] = None
        look["bottom"] = WHITE_BOTTOM
    elif has_legs and not has_body:
        look["top"] = WHITE_TOP
        look["bottom"] = None
    else:
        look["top"] = None
        look["bottom"] = None
    return look


def _armour_item_tier(item_id):
    """Tier stem for a body/legs item id (recruit_bronze_body -> bronze), else None."""
    if not item_id:
        return None
    s = str(item_id)
    if s.startswith("recruit_"):
        s = s[len("recruit_"):]
    for tier in ARMOUR_TIERS:
        if s == f"{tier}_body" or s == f"{tier}_legs" or s == f"{tier}_chainbody" or s == f"{tier}_chainlegs":
            return tier
        if s.startswith(tier + "_"):
            return tier
    return None


def _partial_waist_fracs(sex):
    """Canvas-height fractions for splitting painted armour figures (2x reference)."""
    if sex == "female":
        return dict(head_end=0.41, waist=0.56, skirt=0.75, feet=0.86)
    return dict(head_end=0.39, waist=0.54, skirt=0.74, feet=0.86)


def _y_keep_mask(height, width, y0, y1, soft=0.03):
    import numpy as np
    ys = np.arange(height, dtype=np.float32) / float(height)
    row = np.zeros(height, dtype=np.float32)
    for i, y in enumerate(ys):
        if y0 <= y <= y1:
            row[i] = 1.0
        elif y0 - soft < y < y0:
            row[i] = (y - (y0 - soft)) / soft
        elif y1 < y < y1 + soft:
            row[i] = (y1 + soft - y) / soft
    return np.broadcast_to(row, (width, height)).copy()


def _dilate_u8(alpha, radius=2):
    import numpy as np
    m = alpha.astype(np.uint8)
    for _ in range(max(0, int(radius))):
        acc = m.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc = np.maximum(acc, np.roll(np.roll(m, dx, axis=0), dy, axis=1))
        m = acc
    return m


def _apply_keep_alpha(surf, keep01):
    import numpy as np
    out = surf.copy()
    a = pygame.surfarray.pixels_alpha(out)
    a[:] = (a.astype(np.float32) * keep01).astype(np.uint8)
    del a
    return out


def _clip_alpha_to(surf, sil_u8):
    import numpy as np
    out = surf.copy()
    a = pygame.surfarray.pixels_alpha(out)
    a[:] = np.minimum(a, sil_u8)
    del a
    return out


def _painted_armour_skinned(sex, tier, appearance, anim, facing, frame_idx, scale_tag, tile, base):
    """Bare-head painted set for tier, skin/hair tinted; (surf, alpha_u8) or (None, None)."""
    import numpy as np
    layer = armour_bh_layer(tier)
    if not _art_present(sex, layer):
        layer = armour_hd_layer(tier)
    if not layer or not _art_present(sex, layer):
        return None, None
    main, _tint, ps, pb = _layer_parts(sex, scale_tag, layer, anim, facing, frame_idx, tile, base)
    if main is None:
        return None, None
    skin_surf = _layer_skin(sex, ps, layer, anim, facing, frame_idx, tile, pb)
    out = _skin_whole(main, skin_surf, skin_rgb(skin_tone_id(appearance)))
    hair_id = (appearance or {}).get("hair_colour") or ("chestnut" if sex == "female" else "dark_brown")
    hair_surf = _hair_without_skin(
        _layer_hair(sex, ps, layer, anim, facing, frame_idx, tile, pb), skin_surf)
    if hair_surf is not None and hair_surf.get_size() == out.get_size():
        out = _skin_whole(out, hair_surf, _parse_hair_colour(hair_id))
    return out, pygame.surfarray.array_alpha(out).copy()


def _gap_fill_seam(dest, ref_alpha, where01):
    """Fill thin waist/neck holes with soft white cloth using the painted silhouette."""
    import numpy as np
    da = pygame.surfarray.array_alpha(dest)
    holes = (ref_alpha > 60) & (da < 40) & (where01 > 0.35)
    if not holes.any():
        return dest
    px = pygame.surfarray.pixels3d(dest)
    aa = pygame.surfarray.pixels_alpha(dest)
    w, h = dest.get_size()
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[None, :]
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)[:, None]
    shade = 0.90 + 0.08 * np.sin(xs * np.pi * 4.0) + 0.04 * np.sin(ys * np.pi * 3.0)
    cloth = np.clip(np.array([228.0, 228.0, 224.0], dtype=np.float32) * shade[..., None], 0, 255)
    px[holes] = cloth[holes]
    aa[holes] = np.maximum(ref_alpha[holes], np.uint8(235))
    del px, aa
    return dest


def _box_blur_lum(lum, alpha, radius=2):
    """Alpha-weighted box blur of a luminance map (destroys metal ridge frequency)."""
    import numpy as np
    if radius <= 0:
        return lum
    a = np.clip(alpha.astype(np.float32) / 255.0, 0, 1)
    pad_l = np.pad(lum * a, radius, mode="edge")
    pad_a = np.pad(a, radius, mode="edge")
    out = np.zeros_like(lum)
    k = 2 * radius + 1
    # separable-ish dense box (small radius — fine for 288 canvases)
    acc_l = np.zeros_like(pad_l)
    acc_a = np.zeros_like(pad_a)
    for dy in range(k):
        for dx in range(k):
            acc_l += np.roll(np.roll(pad_l, dy, 0), dx, 1)
            acc_a += np.roll(np.roll(pad_a, dy, 0), dx, 1)
    # extract center
    acc_l = acc_l[radius:-radius, radius:-radius] if False else acc_l
    # The roll approach on padded array is messy; use direct windowing:
    h, w = lum.shape  # note: lum is (width,height) in surfarray layout — actually (w,h)
    # surfarray: shape (width, height)
    out = np.zeros_like(lum)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out += np.roll(np.roll(lum * a, dx, axis=0), dy, axis=1)
    wt = np.zeros_like(a)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            wt += np.roll(np.roll(a, dx, axis=0), dy, axis=1)
    return np.where(wt > 1e-3, out / np.maximum(wt, 1e-3), lum)


def _to_cloth_region(fig, region01, white_surf, protect_bool, garment_clip=True):
    """Replace region with convincing white cloth: blur metal ridges, remap, add cloth texture folds.
    Optionally clip alpha to the white garment silhouette so pauldrons don't become white plate."""
    import numpy as np
    out = fig.copy()
    pa = pygame.surfarray.array_alpha(out)
    rgb = pygame.surfarray.array3d(out).astype(np.float32)
    w, h = out.get_size()
    sel = (region01 > 0.35) & (~protect_bool) & (pa > 20)
    if not sel.any():
        return out
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    # Strong blur kills plate ridges / hard metal speculars → soft cloth shading.
    blurred = _box_blur_lum(lum, pa, radius=4)
    blurred = _box_blur_lum(blurred, pa, radius=3)
    lo, hi = np.percentile(blurred[sel], 8), np.percentile(blurred[sel], 92)
    t = np.clip((blurred - lo) / max(hi - lo, 1e-3), 0, 1)
    # Gentler contrast — cloth, not chalk-white plate remap.
    t = np.clip((t - 0.5) * 1.05 + 0.5, 0, 1)
    # Base cloth: warm off-white with deeper fold shade range.
    cloth = np.stack([168 + t * 62, 168 + t * 62, 164 + t * 58], axis=-1)
    # Synthetic vertical soft folds (pose-stable, cheap).
    xs = np.linspace(0, 1, w, dtype=np.float32)[:, None]
    ys = np.linspace(0, 1, h, dtype=np.float32)[None, :]
    folds = (0.55 * np.sin(xs * 9.5 * np.pi + ys * 1.2)
             + 0.30 * np.sin(xs * 17.0 * np.pi - ys * 2.4)
             + 0.15 * np.sin((xs + ys) * 11.0 * np.pi))
    folds = folds * (0.55 + 0.45 * t)  # stronger folds in lit areas
    cloth = np.clip(cloth + folds[..., None] * 18.0, 0, 255)
    # Prefer real white garment colour/folds wherever that art covers.
    if white_surf is not None and white_surf.get_size() == out.get_size():
        wrgb = pygame.surfarray.array3d(white_surf).astype(np.float32)
        wa = pygame.surfarray.array_alpha(white_surf)
        wlum = 0.299 * wrgb[:, :, 0] + 0.587 * wrgb[:, :, 1] + 0.114 * wrgb[:, :, 2]
        wblur = _box_blur_lum(wlum, wa, radius=2)
        detail = (wlum - wblur) * 2.2
        use = sel & (wa > 30)
        if use.any():
            shade = 0.82 + 0.34 * t
            woven = np.clip(wrgb * shade[..., None] + detail[..., None] * 0.55, 0, 255)
            # Pull woven whites down from chalk — cloth not light-plate.
            woven = np.clip(woven * 0.92 + 14.0, 0, 255)
            strong = use & (wa > 80)
            mild = use & (wa <= 80)
            cloth = cloth.copy()
            if strong.any():
                cloth[strong] = 0.85 * woven[strong] + 0.15 * cloth[strong]
            if mild.any():
                mix = (wa[mild].astype(np.float32) / 80.0)[:, None]
                cloth[mild] = (mix * woven[mild] + (1.0 - mix) * cloth[mild]).astype(np.float32)
        synth = sel & (wa <= 30)
        if synth.any():
            cloth[synth] = np.clip(cloth[synth] + detail[synth, None] * 0.2, 0, 255)
    # Kill dark plate-edge outlines that survive remapping.
    edge = sel.copy()
    outside = ~sel
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
        edge = edge | (sel & np.roll(np.roll(outside, dx, 0), dy, 1))
    edge = edge & sel
    if edge.any():
        mid = np.array([200.0, 200.0, 196.0])
        cloth[edge] = 0.60 * cloth[edge] + 0.40 * mid
        dark = sel & (cloth[:, :, 0] < 150)
        if dark.any():
            cloth[dark] = np.maximum(cloth[dark], mid * 0.92)
    soft = (region01 > 0.05) & (region01 <= 0.35) & (~protect_bool) & (pa > 20)
    px = pygame.surfarray.pixels3d(out)
    aa = pygame.surfarray.pixels_alpha(out)
    px[sel] = cloth[sel]
    if soft.any():
        a = region01
        px[soft] = ((1.0 - a[soft, None]) * px[soft].astype(np.float32) + a[soft, None] * cloth[soft]).astype(np.uint8)
    if garment_clip and white_surf is not None and white_surf.get_size() == out.get_size():
        wa = pygame.surfarray.array_alpha(white_surf)
        g = _dilate_u8(wa, 5)
        # Soften armour bulk outside garment — shrink pauldron wings toward shirt.
        outside = sel & (g < 20)
        if outside.any():
            aa[outside] = 0
        # Near-edge: keep but thin slightly for softer cloth silhouette
        near = sel & (g >= 20) & (g < 70)
        if near.any():
            aa[near] = np.minimum(aa[near], np.maximum(g[near] + 140, np.uint8(180)))
        inside = sel & (g >= 70)
        if inside.any():
            aa[inside] = np.maximum(aa[inside], np.uint8(245))
    else:
        aa[sel] = np.maximum(aa[sel], np.uint8(250))
    del px, aa
    return out


def _waist_band_centroid_y(alpha_u8, y0_frac, y1_frac):
    """Mean opaque Y in a waist band — used to align mixed-tier painted halves."""
    import numpy as np
    w, h = alpha_u8.shape
    y0, y1 = int(h * y0_frac), int(h * y1_frac)
    band = alpha_u8[:, y0:y1]
    ys = np.arange(y0, y1)
    weights = band.sum(axis=0).astype(np.float64)
    if weights.sum() < 1:
        return 0.5 * (y0 + y1)
    return float(np.average(ys, weights=weights))


def _shift_surface_y(surf, dy):
    """Integer vertical shift; positive dy moves content down."""
    import numpy as np
    dy = int(round(dy))
    if dy == 0:
        return surf
    out = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    out.blit(surf, (0, dy))
    return out


def _defringe_alpha(surf, weak=140, strong=200):
    """Drop ghost fringe pixels (mid-alpha glow) that read as white halos on dark ground."""
    import numpy as np
    out = surf.copy()
    a = pygame.surfarray.pixels_alpha(out)
    # Neighbour max alpha
    acc = a.astype(np.uint8).copy()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        acc = np.maximum(acc, np.roll(np.roll(a, dx, 0), dy, 1))
    fringe = (a > 0) & (a < weak) & (acc < strong)
    a[fringe] = 0
    # Boost nearly-solid content
    solidish = (a >= weak) & (a < 230)
    a[solidish] = 255
    del a
    return out


def compose_partial_armour_hd(sex, appearance, equipment, anim="idle", facing="s", frame_idx=0,
                              scale_tag="2x", tile=80, base=80):
    """Painted HD chest/legs with dedicated white cloth underlays (not plate remap).

    Chest-only: bronze (etc.) torso over clean white leggings + shoes.
    Legs-only: clean white shirt under painted leg armour.
    Mixed tiers: continuous white undersuit at waist, then registered body/legs halves.
    """
    import numpy as np
    sex = "female" if sex == "female" else "male"
    eq = equipment or {}
    bt = _armour_item_tier(eq.get("body"))
    lt = _armour_item_tier(eq.get("legs"))
    if not bt and not lt:
        return None
    facing = _facing_str(facing)
    if facing == "w":
        facing = "e"
    fr = _partial_waist_fracs(sex)
    canvas = tuple((_load_meta().get("canvas") or {}).get(scale_tag) or (288, 288))
    w, h = canvas

    def load_cloth(layer):
        main, _t, _ps, _pb = _layer_parts(sex, scale_tag, layer, anim, facing, frame_idx, tile, base)
        return main

    def solidify(surf):
        if surf is None:
            return None
        out = surf.copy()
        aa = pygame.surfarray.pixels_alpha(out)
        aa[aa > 24] = 255
        aa[aa <= 24] = 0
        del aa
        return _defringe_alpha(out)

    def y_band(y0, y1, soft=0.03):
        return _y_keep_mask(h, w, y0, y1, soft=soft)

    def blit_opaque(dest, src):
        if src is None:
            return dest
        dest.blit(solidify(src), (0, 0))
        return dest

    def keep_blit(dest, src, keep01):
        if src is None:
            return dest
        piece = _apply_keep_alpha(solidify(src), keep01)
        aa = pygame.surfarray.pixels_alpha(piece)
        aa[aa > 24] = 255
        del aa
        dest.blit(piece, (0, 0))
        return dest

    def rgb_waist_blend(dest, upper_src, lower_src, split, feather=0.04):
        """Opaque upper/lower with RGB-only blend in a thin waist band — no alpha feather ghosts."""
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        ys = np.arange(h, dtype=np.float32) / float(h)
        ys2 = np.broadcast_to(ys, (w, h))
        up = solidify(upper_src)
        lo = solidify(lower_src)
        ua = pygame.surfarray.array_alpha(up)
        la = pygame.surfarray.array_alpha(lo)
        ur = pygame.surfarray.array3d(up).astype(np.float32)
        lr = pygame.surfarray.array3d(lo).astype(np.float32)
        # lower first, then upper
        out.blit(lo, (0, 0))
        # hard upper above split-feather
        up_keep = (ys2 <= (split + feather)).astype(np.float32)
        piece = _apply_keep_alpha(up, up_keep)
        aa = pygame.surfarray.pixels_alpha(piece)
        aa[aa > 24] = 255
        del aa
        out.blit(piece, (0, 0))
        # RGB blend where both present in band
        band = (ys2 >= (split - feather)) & (ys2 <= (split + feather))
        both = band & (ua > 24) & (la > 24)
        if both.any():
            t = np.clip((ys2 - (split - feather)) / max(2 * feather, 1e-3), 0, 1)
            # t=0 upper, t=1 lower
            px = pygame.surfarray.pixels3d(out)
            aa = pygame.surfarray.pixels_alpha(out)
            blended = ((1.0 - t[..., None]) * ur + t[..., None] * lr).astype(np.uint8)
            px[both] = blended[both]
            aa[both] = 255
            del px, aa
        return _defringe_alpha(out)

    # --- Body only: white leggings + shoes under painted chest ---
    if bt and not lt:
        fig, ref_a = _painted_armour_skinned(sex, bt, appearance, anim, facing, frame_idx, scale_tag, tile, base)
        if fig is None:
            return None
        legs = load_cloth(WHITE_BOTTOM)
        shoes = load_cloth("shoes_leather")
        split = fr["waist"] + 0.01
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        # Head/skin only from painted figure (never paste lower plate)
        keep_blit(out, fig, y_band(0.0, fr["head_end"] + 0.02, soft=0.015))
        # Dedicated white leggings (pose-matched painted cloth) — not plate remap
        blit_opaque(out, legs)
        if shoes is not None:
            blit_opaque(out, shoes)
        undersuit = out.copy()
        # Chest armour strictly above waist
        upper = _apply_keep_alpha(fig, y_band(0.0, split + 0.04, soft=0.0))
        aa = pygame.surfarray.pixels_alpha(upper)
        # Zero anything in the lower band so no plate fauld ghosts into cloth
        lo = y_band(split + 0.01, 1.0, soft=0.0)
        aa[(lo > 0.5) & (aa > 0)] = 0
        aa[aa > 24] = 255
        del aa
        out = rgb_waist_blend(undersuit, upper, undersuit, split=split, feather=0.028)
        keep_blit(out, fig, y_band(0.0, split - 0.02, soft=0.01))
        _gap_fill_seam(out, ref_a, y_band(fr["waist"] - 0.04, split + 0.05, soft=0.02))
        return _defringe_alpha(out)

    # --- Legs only: white shirt under painted legs ---
    if lt and not bt:
        fig, ref_a = _painted_armour_skinned(sex, lt, appearance, anim, facing, frame_idx, scale_tag, tile, base)
        if fig is None:
            return None
        shirt = load_cloth(WHITE_TOP)
        split = fr["waist"] + 0.02
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        # Head only — never paste painted torso plate from the legs set
        keep_blit(out, fig, y_band(0.0, fr["head_end"] + 0.01, soft=0.01))
        blit_opaque(out, shirt)
        undersuit = out.copy()
        lower = _apply_keep_alpha(fig, y_band(split - 0.04, 1.0, soft=0.0))
        aa = pygame.surfarray.pixels_alpha(lower)
        # Zero any residual upper torso plate on the legs half
        up = y_band(0.0, split - 0.02, soft=0.0)
        aa[(up > 0.5) & (aa > 0)] = 0
        aa[aa > 24] = 255
        del aa
        out = rgb_waist_blend(undersuit, undersuit, lower, split=split, feather=0.028)
        keep_blit(out, fig, y_band(split + 0.015, 1.0, soft=0.01))
        keep_blit(out, fig, y_band(0.0, fr["head_end"], soft=0.008))
        _gap_fill_seam(out, ref_a, y_band(fr["head_end"] - 0.02, fr["head_end"] + 0.08, soft=0.02))
        _gap_fill_seam(out, ref_a, y_band(fr["waist"] - 0.05, fr["waist"] + 0.07, soft=0.02))
        return _defringe_alpha(out)

    # --- Mixed tiers: continuous white undersuit + registered halves ---
    fig_b, ref_b = (None, None)
    fig_l, ref_l = (None, None)
    if bt:
        fig_b, ref_b = _painted_armour_skinned(sex, bt, appearance, anim, facing, frame_idx, scale_tag, tile, base)
    if lt:
        fig_l, ref_l = _painted_armour_skinned(sex, lt, appearance, anim, facing, frame_idx, scale_tag, tile, base)
    if fig_b is None and fig_l is None:
        return None
    if fig_b is not None and fig_l is not None:
        cy_b = _waist_band_centroid_y(ref_b, fr["waist"] - 0.04, fr["waist"] + 0.08)
        cy_l = _waist_band_centroid_y(ref_l, fr["waist"] - 0.04, fr["waist"] + 0.08)
        dy = cy_b - cy_l
        if abs(dy) > 0.5 and abs(dy) < 18:
            fig_l = _shift_surface_y(fig_l, dy)
            ref_l = pygame.surfarray.array_alpha(fig_l).copy()
    split = fr["waist"] + 0.02
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    # Continuous undersuit (shirt + leggings) under the seam
    shirt = load_cloth(WHITE_TOP)
    legs = load_cloth(WHITE_BOTTOM)
    blit_opaque(out, legs)
    blit_opaque(out, shirt)
    if fig_b is not None and fig_l is not None:
        # Drop mismatched boots from body half
        upper = _apply_keep_alpha(fig_b, 1.0 - y_band(fr["feet"] - 0.03, 1.0, soft=0.02))
        out = rgb_waist_blend(out, upper, fig_l, split=split, feather=0.05)
        # Firm stamps
        keep_blit(out, fig_b, y_band(0.0, split - 0.025, soft=0.015))
        keep_blit(out, fig_l, y_band(split + 0.025, 1.0, soft=0.015))
    elif fig_b is not None:
        blit_opaque(out, fig_b)
    else:
        blit_opaque(out, fig_l)
    ref = np.zeros((w, h), dtype=np.uint8)
    if ref_b is not None:
        ref = np.maximum(ref, ref_b)
    if ref_l is not None:
        ref = np.maximum(ref, ref_l)
    _gap_fill_seam(out, ref, y_band(fr["waist"] - 0.08, fr["skirt"] + 0.02, soft=0.02))
    return _defringe_alpha(out)



def _blit_composed_player(surf, composed, cx, cy_feet, tile, facing, flip_x=False, scale_tag="2x", base=80):
    """Feet-anchor a canvas-sized composed figure like a whole-figure strip frame."""
    meta = _load_meta()
    feet = (meta.get("feet_px") or {}).get(scale_tag) or [144, 248]
    canvas = (meta.get("canvas") or {}).get(scale_tag) or [288, 288]
    k = tile / float(base)
    sw, sh = max(1, int(canvas[0] * k)), max(1, int(canvas[1] * k))
    scaled = pygame.transform.smoothscale(composed, (sw, sh))
    if flip_x:
        scaled = pygame.transform.flip(scaled, True, False)
        fx = (canvas[0] * k) - (feet[0] * k)
    else:
        fx = feet[0] * k
    fy = feet[1] * k
    surf.blit(scaled, (int(cx - fx), int(cy_feet - fy)))
    return True


_SET_SLOTS = {"helmet": ("helmet",), "body": ("body", "chainbody"), "legs": ("legs", "chainlegs")}


def full_armour_tier(equipment):
    """The tier of a full matching set (helmet + body + legs of one tier; plate or chain), else None.
    Gauntlets and sabatons are part of the body and legs pieces. A shield never counts and never matters."""
    eq = {k: (str(v)[len("recruit_"):] if str(v or "").startswith("recruit_") else v)   # welcome kit = bronze
          for k, v in (equipment or {}).items()}
    for tier in ARMOUR_TIERS:
        if all(eq.get(slot) in {f"{tier}_{n}" for n in names} for slot, names in _SET_SLOTS.items()):
            return tier
    return None


def armour_hd_layer(tier):
    return f"armour_{tier}_hd" if tier else None


def set_tier(equipment):
    """The tier of a matching body + legs pair (plate or chain), helmet ignored, else None."""
    eq = {k: (str(v)[len("recruit_"):] if str(v or "").startswith("recruit_") else v)
          for k, v in (equipment or {}).items()}
    for tier in ARMOUR_TIERS:
        if all(eq.get(slot) in {f"{tier}_{n}" for n in _SET_SLOTS[slot]} for slot in ("body", "legs")):
            return tier
    return None


def armour_bh_layer(tier):
    return f"armour_{tier}_bh_hd" if tier else None


def is_barehead_layer(layer):
    return bool(layer) and str(layer).startswith("armour_") and str(layer).endswith("_bh_hd")


def armour_layer_for(sex, equipment):
    """David, 23 Oct 2026: body + legs of one tier show that tier's set. Tiers with bare-head art draw the
    bare-head figure (hair tinted to the player's colour) and any worn helmet goes on as the overlay; tiers
    without it keep the helmeted full-set figure, which needs the matching helmet too."""
    t = set_tier(equipment)
    # David, 16 Oct rule (fully enclosed helm, grille visible): with the set's own helmet the painted
    # helmeted figure is drawn - the overlay on the bare-head figure left the chin and jaw showing.
    if t and _helm.helmet_tier(equipment) == t and _art_present(sex, armour_hd_layer(t)):
        return armour_hd_layer(t)
    if t and _art_present(sex, armour_bh_layer(t)):
        return armour_bh_layer(t)
    full = armour_hd_layer(full_armour_tier(equipment))
    return full if (full and _art_present(sex, full)) else None


def _whole_figure_layer(appearance, sex, anim, equipment, item_map):
    """The painted whole-figure layer for this frame, else None (None only means missing art).
    David, 23 Oct 2026: painted armour is for full sets only. A full matching tier set shows that tier's
    painted armour figure; partial armour and shields keep the outfit's painted figure (stats still apply,
    the gear isn't drawn). Weapons and tools appear only in the combat / skilling strips
    ({anim}_{facing}.png under the layer's folder); idle and walk never show them."""
    tier_layer = armour_layer_for(sex, equipment)
    if tier_layer and (anim in _WHOLE_ANIMS or _whole_anim_present(sex, tier_layer, anim)):
        return tier_layer
    # David, 6 Nov 2026: chest/legs alone or mixed tiers use layered white underclothes + the
    # equipped pieces — never keep the outfit whole-figure while armour is half-worn.
    if needs_armour_underlay(equipment):
        return None
    outfit = (appearance or {}).get("outfit")
    item = item_map.get(outfit) if outfit else None
    hd = (item or {}).get("hd_art")
    if not hd or not _art_present(sex, hd):
        hd = None
    if not hd:
        hd = collection_hd(appearance)
        if hd and not _art_present(sex, hd):
            hd = None
    if hd and (anim in _WHOLE_ANIMS or _whole_anim_present(sex, hd, anim)):
        return hd
    # a missing action strip holds the figure's idle (tier set first, else the outfit), never the layered doll
    return tier_layer or hd


def collection_entry(appearance):
    sid = (appearance or {}).get("set")
    if not sid:
        return None
    for e in _load_catalogue().get("collection") or []:
        if e.get("id") == sid:
            return e
    return None


def collection_hd(appearance):
    return (collection_entry(appearance) or {}).get("hd_art")


_FX_JSON = {}


def _fx_info(sex, layer):
    key = (sex, layer)
    if key not in _FX_JSON:
        try:
            with open(os.path.join(_BASE, sex, "2x", layer, "fx.json")) as f:
                _FX_JSON[key] = json.load(f)
        except (OSError, ValueError):
            _FX_JSON[key] = None
    return _FX_JSON[key]


def _draw_outfit_fx(dest, which, sex, appearance, layer, anim, facing, flip, pos_feet, tile, t, fx_ctx):
    """fx_ctx: dict(is_self, preview, full_armour, eclipse). which: back/front."""
    import outfit_fx
    if not layer or collection_hd(appearance) != layer:
        return
    info = _fx_info(sex, layer)
    if not info:
        return
    ctx = fx_ctx or {}
    eff = outfit_fx.effective(ctx.get("is_self", True), ctx.get("preview", False),
                              ctx.get("full_armour", False), ctx.get("eclipse", False))
    if not eff:
        return
    mode, alpha, front_on, tint_on = eff
    if which == "front" and (not front_on or anim not in ("idle", "walk")):
        return
    scale_tag, base = ("1x", 40) if tile <= 48 else ("2x", 80)
    frames = int(info.get("frames") or 16)
    idx = outfit_fx.frame_for(t, frames, mode, which == "front")
    strip = _load_image(f"{sex}/{scale_tag}/{layer}/fx_{which}_{facing}.png")
    if strip is None:
        return
    cw = strip.get_width() // frames
    k = tile / float(base)
    key = ("fx", id(strip), idx, tile)
    fr = _IMAGES.get(key)
    if fr is None:
        sub = strip.subsurface(pygame.Rect(idx * cw, 0, cw, strip.get_height()))
        fr = pygame.transform.smoothscale(sub, (max(1, int(cw * k)), max(1, int(strip.get_height() * k))))
        _IMAGES[key] = fr
    if flip:
        fr = pygame.transform.flip(fr, True, False)
    fr = outfit_fx._alpha(fr, alpha)
    meta = _load_meta()
    feet = (meta.get("feet_px") or {}).get(scale_tag, [72, 124])
    fx = (cw - feet[0]) if flip else feet[0]
    x, y = int(pos_feet[0] - fx * k), int(pos_feet[1] - feet[1] * k)
    if which == "back" and tint_on and info.get("tint"):
        tint = info["tint"]
        rgb = tint.get("rgb") if isinstance(tint, dict) else tint
        ts = outfit_fx.tint_surface(int(tile * 0.9), int(tile * 0.32), rgb)
        dest.blit(ts, (int(pos_feet[0] - ts.get_width() / 2), int(pos_feet[1] - ts.get_height() / 2)))
    if which == "back" and mode != "reduced":
        dest.blit(outfit_fx.glow_surface(fr), (x, y), special_flags=pygame.BLEND_RGB_ADD)
    dest.blit(fr, (x, y))
    if which == "front":
        dest.blit(outfit_fx.glow_surface(fr, 0.35 if mode == "reduced" else 0.6), (x, y),
                  special_flags=pygame.BLEND_RGB_ADD)


def _draw_jewellery(dest, which, sex, appearance, layer, anim, facing, frame_idx, flip, main_surf, pos, equipment, t, fx_ctx,
                    scale_tag="2x"):
    """HD jewellery overlays + Crown Jewels sparkle (client/jewellery.py, JEWELLERY_SPEC.md)."""
    look = appearance or {}
    if not (look.get("jewellery") or look.get("head")):
        return
    try:
        import jewellery as _jw
        if not any(_jw.item(j) for j in list(look.get("jewellery") or []) + [look.get("head")]):
            return
        coll = collection_entry(look) or {}
        ctx = dict(fx_ctx or {})
        ctx.setdefault("t", t)
        ctx["flags"] = dict(coll.get("painted") or {})
        ctx["equipment"] = {"head": _helm.helmet_tier(equipment), "body": set_tier(equipment), "hands": None}
        ctx["armour_glow"] = bool(ctx.get("armour_glow") or set_tier(equipment) in ("mithril", "adamant", "dragon", "eclipse")
                                  or ctx.get("eclipse"))
        ctx["elemental_full"] = bool(coll.get("fx"))
        # Prefer anchors that match the figure scale (shop idle can be 4x/8x); fall back to 2x.
        tag = scale_tag if scale_tag in ("1x", "2x", "4x", "8x") else "2x"
        layer_dir = os.path.join(_BASE, sex, tag, layer)
        if not os.path.isfile(os.path.join(layer_dir, "jw_anchors.json")):
            layer_dir = os.path.join(_BASE, sex, "2x", layer)
        rect = pygame.Rect(pos[0], pos[1], main_surf.get_width(), main_surf.get_height())
        _jw.draw(dest, main_surf, rect, layer_dir, anim, facing, frame_idx, flip, look, ctx, which=which)
    except Exception as exc:   # never break the figure for an accessory
        print("[jewellery]", exc)


def _whole_anim_for(final_anim, frame_idx, t, equipment):
    """Body-strip anim -> the whole-figure outfit strip name and frame.
    melee -> melee_sword / melee_axe (10 frames, same MELEE_PROGRESS timing; only swords and axes fight).
    chop / mine / fish* -> chop / mine / fish: 8 frames, one loop sampled evenly over GATHER_LOOP_MS."""
    if final_anim == "melee":
        w = str((equipment or {}).get("weapon") or "")
        axe = ("axe" in w or "cleaver" in w) and "pickaxe" not in w     # eclipse_cleaver is an axe
        return ("melee_axe" if axe else "melee_sword"), frame_idx
    if is_gather_anim(final_anim):
        base = "fish" if final_anim.startswith("fish") else final_anim
        loop = float(GATHER_LOOP_MS.get(final_anim) or GATHER_LOOP_MS.get(base) or 1800) / 1000.0
        u = ((t or 0.0) % loop) / loop
        return base, min(7, int(u * 8))
    return final_anim, frame_idx


def _whole_anim_present(sex, layer, anim):
    key = (sex, layer, anim)
    if key not in _ART_PRESENT:
        root = os.path.join(_BASE, sex, "2x", layer)
        _ART_PRESENT[key] = any(os.path.isfile(os.path.join(root, f"{anim}_{f}.png")) for f in ("s", "e", "n"))
    return _ART_PRESENT[key]


def starter_outfit_look(appearance, sex):
    """Everyone wears the new skins: a look without an HD outfit is shown in the free tier 1 set
    (catalogue starter_sets: Villager / Village Lady), keeping its skin tone and hair colour."""
    cat = _load_catalogue()
    set_id = (cat.get("starter_sets") or {}).get(sex)
    entry = (cat.get("sets") or {}).get(set_id or "") or {}
    item_map = _build_item_map()
    look = dict(appearance or get_default_appearance(sex, starter=False))
    if look.get("outfit") or not entry or collection_hd(look):   # any chosen outfit (HD or an older layered set) is kept
        return look
    pals = entry.get("palettes") or [None]
    try:
        import jewellery as _jw
        keep_jw = [j for j in look.get("jewellery") or [] if _jw.item(j)]
        keep_head = look.get("head") if _jw.item(look.get("head") or "") else None
    except Exception:
        keep_jw, keep_head = [], None
    look.update(outfit=None, cloak=None, head=None, held=None, jewellery=[], outfit_level=1,
                palette=look.get("palette") if look.get("palette") in pals else pals[0])
    for pid in entry.get("pieces") or []:
        slot = (item_map.get(pid) or {}).get("slot")
        if slot == "jewellery":
            look["jewellery"].append(pid)
        elif slot in ("outfit", "cloak", "head", "held"):
            look[slot] = pid
    look["jewellery"] = keep_jw + [j for j in look["jewellery"] if j not in keep_jw]
    if keep_head:
        look["head"] = keep_head
    # hair stays the player's own pick: the set's styled hair is a shop item, not part of the free starter
    return look


def _layer_skin(sex, scale_tag, layer, anim, facing, frame_idx, tile, base):
    """The _skin strip that pairs with a whole-figure frame (RGB = shade ratio*128, A = face/neck/hands)."""
    scale_tag, base = _resolve_scale(sex, layer, anim, facing, frame_idx, scale_tag, base)
    return _frame_surface(f"{sex}/{scale_tag}/{layer}/{anim}_{facing}_skin.png", frame_idx, scale_tag, tile, base)


def _layer_hair(sex, scale_tag, layer, anim, facing, frame_idx, tile, base):
    """The _hair strip of a whole figure (RGB = shade ratio*128, A = hair), else None.

    scale_tag/base should already match the body frame (caller passes part_scale).
    """
    path = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}_hair.png"
    if not os.path.isfile(os.path.join(_BASE, path)):
        # Fall back to 2x hair when a 4x/8x portrait has no hair mask yet.
        if scale_tag in ("4x", "8x"):
            path2 = f"{sex}/2x/{layer}/{anim}_{facing}_hair.png"
            if os.path.isfile(os.path.join(_BASE, path2)):
                return _frame_surface(path2, frame_idx, "2x", tile, 80)
        return None
    return _frame_surface(path, frame_idx, scale_tag, tile, base)


def _hair_without_skin(hair_surf, skin_surf):
    """Drop hair-mask pixels that sit on skin so colour changes never recolour the face."""
    if hair_surf is None:
        return None
    if skin_surf is None or skin_surf.get_size() != hair_surf.get_size():
        return hair_surf
    import numpy as np
    out = hair_surf.copy()
    ha = pygame.surfarray.pixels_alpha(out)
    sa = pygame.surfarray.pixels_alpha(skin_surf)
    # Where skin is opaque, hair must not tint (forehead / cheeks / hands bleed).
    ha[...] = np.where(sa > 60, 0, ha)
    del ha, sa
    return out


def _coif_jaw(main_surf, skin_surf, hair_surf=None):
    """Bare-head armour figure under a helmet of another tier: the overlay stops at the jaw, so the chin and
    neck skin below it read as an open face. Paint head-band skin as a dark mail coif (shading kept) so the
    face reads fully enclosed. Hands (below the shoulder band) are left alone."""
    import numpy as np
    out = main_surf.copy()
    if skin_surf is None or skin_surf.get_size() != out.get_size():
        return out
    a = pygame.surfarray.pixels_alpha(out)
    cols = np.nonzero(a.max(axis=0) > 128)[0]
    if not len(cols):
        del a
        return out
    top, bot = int(cols[0]), int(cols[-1])
    band = int(top + 0.24 * (bot - top))      # crown .. upper chest
    del a
    H = out.get_height()
    w = np.zeros(out.get_size(), np.float32)
    w[:, :band] = pygame.surfarray.pixels_alpha(skin_surf)[:, :band].astype(np.float32) / 255.0
    if hair_surf is not None and hair_surf.get_size() == out.get_size():
        # hair under a helmet (ponytail in profile, swinging in actions) reads as the same mail coif /
        # aventail; the hair mask only covers head hair, so it is used at every height (raised weapons
        # push the strip's top up and would otherwise leave the ponytail outside the band)
        hw = pygame.surfarray.pixels_alpha(hair_surf).astype(np.float32) / 255.0
        fa = pygame.surfarray.pixels_alpha(out)
        ch = out.get_height()
        for x0 in range(0, out.get_width(), ch):          # per frame: head/ponytail zone only (above the shoulders)
            rows = np.nonzero(fa[x0:x0 + ch].max(axis=0) > 128)[0]
            if not len(rows):
                hw[x0:x0 + ch] = 0
                continue
            hw[x0:x0 + ch, max(0, int(rows[-1] - 0.30 * ch)):] = 0
        del fa
        w = np.maximum(w, hw)
    if w.max() <= 0:
        return out
    px = pygame.surfarray.pixels3d(out)
    src = px.astype(np.float32)
    lum = src.mean(axis=2, keepdims=True) / 255.0
    mail = np.array([58.0, 60.0, 66.0]) * (0.55 + 0.9 * lum)
    w = w[..., None]
    px[:, :] = np.clip(src * (1.0 - w) + mail * w, 0, 255).astype(np.uint8)
    del px
    return out


def _skin_whole(main_surf, skin_surf, rgb):
    """Recolour only the skin of a painted figure: lerp(src, tone * ratio, mask).

    Painted shade ratios span a wide range (~0.3–1.6). On brown / dark / deep tones that
    reads as pale patches on the face — compress ratios toward 1.0 as the tone darkens.
    """
    import numpy as np
    out = main_surf.copy()
    if skin_surf is None or skin_surf.get_size() != out.get_size():
        return out
    px = pygame.surfarray.pixels3d(out)
    src = px.astype(np.float32)
    ratio = pygame.surfarray.pixels3d(skin_surf).astype(np.float32) / 128.0
    tone = np.array(rgb, dtype=np.float32)
    # tone_7 olive ~ mid; tone_8–10 need stronger compression
    tone_lum = float(tone.mean())
    if tone_lum < 110.0:
        # 110 → 0, 55 → ~1 (deep brown). Soften painted highlight ratios so they
        # don't read as pale patches on brown / dark / deep tones.
        t = float(np.clip((110.0 - tone_lum) / 55.0, 0.0, 1.0))
        keep = 1.0 - 0.40 * t  # keep 60–100% of painted deviation from 1.0
        ratio = 1.0 + (ratio - 1.0) * keep
    w = (pygame.surfarray.pixels_alpha(skin_surf).astype(np.float32) / 255.0)[..., None]
    toned = np.clip(tone * ratio, 0, 255)
    px[...] = (src * (1.0 - w) + toned * w).astype(np.uint8)
    del px
    return out


def _gather_tool_layer(tool, sex):
    """The tool's own layer (wpn_harpoon, wpn_net, wpn_pot ...) once it's on disk, else the rod."""
    named = {"small_fishing_net": "wpn_net", "harpoon": "wpn_harpoon", "lobster_pot": "wpn_pot"}.get(tool)
    if named and sex and _art_present(sex, named):
        return named
    return "wpn_rod"


def _apply_covers(layers, equipment, anim, sex=None, tool=None):
    """Drop clothes that armour or an outfit covers, then add gear layers."""
    eq = equipment or {}
    helm = _helm_spec(eq.get("helmet"), sex)
    body = _body_spec(eq.get("body"), sex) or []
    legs = _legs_spec(eq.get("legs"), sex) or []
    shield = _shield_spec(eq.get("shield"), sex)
    hide = set()
    if helm:
        hide.add("hair")
        hide.add("head")
    if eq.get("weapon") or shield or is_gather_anim(anim):
        hide.add("held")
    plate_body = any(base_layer(name) == "arm_platebody" for name, _tint in body)
    plate_legs = any(base_layer(name) == "arm_sabatons" for name, _tint in legs)
    if body:
        hide.add("top")
        hide.add("outfit")
    if legs:
        hide.add("bottom")
        hide.add("outfit")
    if plate_body:
        hide.add("acc_leather_gloves")
    if plate_legs:
        hide.add("shoes")
    has_outfit = any(tag == "outfit" for _layer, _tint, _z, tag in layers)
    if has_outfit and "outfit" not in hide:
        hide.add("top")
        hide.add("bottom")
    kept = []
    for layer_name, tint, z, tag in layers:
        if tag in hide:
            continue
        kept.append((layer_name, tint, z))
    z_fallback = {"s": 70, "e": 70, "n": 70, "w": 70}
    for name, tint in ([helm] if helm else []) + body + legs + ([shield] if shield else []):
        if not name:
            continue
        kept.append((name, tint, _layer_z(name, z_fallback)))
    weapon_id = eq.get("weapon")
    # Gathering shows the tool in use, tinted by the tool (bronze ... dragon), not the weapon.
    if anim == "chop":
        kept.append(("wpn_axe", _tier_rgb(tool) if tool else _tier_rgb(weapon_id, "wood"),
                     _layer_z("wpn_axe", z_fallback)))
        swing = "wpn_axe"
    elif anim == "mine":
        kept.append(("wpn_pickaxe", _tier_rgb(tool or weapon_id), _layer_z("wpn_pickaxe", z_fallback)))
        swing = "wpn_pickaxe"
    elif is_gather_anim(anim):
        rod = _gather_tool_layer(tool, sex)
        kept.append((rod, _tier_rgb(None, "wood"), _layer_z(rod, z_fallback)))
        swing = rod
    else:
        wlayer, wtint = _weapon_spec(weapon_id, sex)
        swing = wlayer
        if wlayer:
            kept.append((wlayer, wtint, _layer_z(wlayer, {"s": 90, "e": 90, "n": 8, "w": 90})))
    return kept, swing


_RECOLOURED = {}


def _recolour(spec, main_surf, tint_surf):
    """Skin tone or garment palette on one frame. Cached per frame surface and colour."""
    if len(_RECOLOURED) > 6000:
        _RECOLOURED.clear()
    if "skin" in spec:
        rgb = tuple(spec["skin"])
        if tint_surf is not None:          # real body_base: grey render + _tint mask
            return main_surf, _cached(("mul", id(tint_surf), rgb), lambda: _multiplied(tint_surf, rgb))
        if main_surf is None:
            return None, None
        return _cached(("skin", id(main_surf), rgb), lambda: _skin_placeholder(main_surf, rgb)), None
    colours = spec.get("garment")
    if not colours:
        return main_surf, tint_surf
    base, trim = tuple(colours[0]), tuple(colours[1])
    if tint_surf is not None:              # real set art: R = cloth, G = trim
        return main_surf, _cached(("two", id(tint_surf), base, trim), lambda: _two_channel(tint_surf, base, trim))
    if spec.get("placeholder") and main_surf is not None:
        return _cached(("gar", id(main_surf), base), lambda: _garment_placeholder(main_surf, base)), None
    return main_surf, tint_surf


def _cached(key, build):
    hit = _RECOLOURED.get(key)
    if hit is None:
        hit = build()
        _RECOLOURED[key] = hit
    return hit


def _multiplied(surf, rgb):
    out = surf.copy()
    overlay = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    overlay.fill((*rgb, 255))
    out.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _luma(arr):
    return arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114


def _skin_placeholder(surf, rgb):
    """Placeholder until body_base exists: recolour the light body's skin pixels to the tone.
    Shading comes from luminance; the dark underclothes (low luminance) are left alone."""
    import numpy as np
    out = surf.copy()
    px = pygame.surfarray.pixels3d(out)
    src = px.astype(np.float32)
    lum = _luma(src)
    weight = np.clip((lum - 112.0) / 28.0, 0.0, 1.0)[..., None]
    shade = np.clip(0.45 + 0.55 * lum / 178.0, 0.0, 1.12)[..., None]
    toned = np.clip(np.array(rgb, dtype=np.float32) * shade, 0, 255)
    px[...] = (src * (1.0 - weight) + toned * weight).astype(np.uint8)
    del px
    return out


def _garment_placeholder(surf, base):
    """Placeholder set garment: the generic outfit, recoloured to the set palette by luminance."""
    import numpy as np
    out = surf.copy()
    px = pygame.surfarray.pixels3d(out)
    src = px.astype(np.float32)
    lum = _luma(src) / 255.0
    colour = np.maximum(np.array(base, dtype=np.float32), 34.0)
    shade = (0.35 + 1.15 * lum)[..., None]
    px[...] = np.clip(colour * shade, 0, 255).astype(np.uint8)
    del px
    return out


def _two_channel(mask, base, trim):
    import numpy as np
    out = mask.copy()
    px = pygame.surfarray.pixels3d(out)
    src = px.astype(np.float32) / 255.0
    col = src[..., 0:1] * np.array(base, dtype=np.float32) + src[..., 1:2] * np.array(trim, dtype=np.float32)
    px[...] = np.clip(col, 0, 255).astype(np.uint8)
    del px
    return out


def _blit_tinted(dest, tint_surf, rgb, pos):
    tinted = tint_surf.copy()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    overlay.fill((*rgb, 255))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    dest.blit(tinted, pos)


def draw_player(
    surf, sex, appearance, cx, cy_feet, tile, t,
    anim="idle", progress=None, facing=1,
    hit_t=-1.0, death_t=-1.0, equipment=None, fx_seed=None, tool=None, starter=True, fx_ctx=None,
):
    """Draw the HD villager paper doll. starter=False skips the free-outfit default (creator item thumbnails).

    Returns False only if body art is missing after retries. Callers must not use the
    old 2D humanoid for players — retry with get_default_appearance instead.

    fx_seed (players only): enables the worn-gear sparkle overlay (eclipse_fx)
    when the equipment qualifies. NPCs, monsters and pets leave it None.
    anim may be a gathering skill (woodcutting/mining/fishing); tool is the gather tool item id.
    """
    anim = gather_anim(anim, tool)
    if fx_seed is not None:
        import eclipse_fx
        tier = eclipse_fx.fx_tier(equipment)
        if tier:
            return _draw_player_fx(
                surf, sex, appearance, cx, cy_feet, tile, t, anim, progress, facing,
                hit_t, death_t, equipment, fx_seed, tier, tool=tool, fx_ctx=fx_ctx,
            )
    sex = "female" if sex == "female" else "male"
    # Matching body+legs of one tier: painted set figure. Partial / mixed tiers: painted HD
    # halves + white underclothes (David, 6 Nov 2026 t453u). No armour: outfit whole-figure.
    try:
        hd_look = starter_outfit_look(appearance, sex) if starter else (appearance or {})
        if needs_armour_underlay(equipment):
            # David, 6 Nov 2026 (t453u): painted HD halves + white underclothes (no paper-doll pieces).
            final_anim, frame_idx = _frame_for_anim(anim, t, progress, hit_t, death_t)
            facing_tag = _facing_str(facing)
            flip_x = False
            compose_facing = facing_tag
            if compose_facing == "w":
                compose_facing, flip_x = "e", True
            preview = bool((fx_ctx or {}).get("preview"))
            scale_tag, base = _scale_for(tile, preview=preview)
            if scale_tag in ("4x", "8x") and final_anim != "idle":
                scale_tag, base = "2x", 80
            # Compose at 2x then scale — painted halves and white clothes live there.
            comp_scale, comp_base = "2x", 80
            composed = compose_partial_armour_hd(
                sex, hd_look, equipment, anim=final_anim, facing=compose_facing,
                frame_idx=frame_idx, scale_tag=comp_scale, tile=comp_base, base=comp_base)
            if composed is not None:
                return _blit_composed_player(
                    surf, composed, cx, cy_feet, tile, facing_tag, flip_x=flip_x,
                    scale_tag=comp_scale, base=comp_base)
            # Fallback: layered white + piece overlays when painted art is missing.
            under = armour_underlay_look(hd_look, sex, equipment)
            ctx = dict(fx_ctx or {})
            ctx["full_armour"] = False
            return _draw_player_core(surf, sex, under, cx, cy_feet, tile, t, anim, progress, facing,
                                     hit_t, death_t, equipment, tool, fx_ctx=ctx)
        probe = _whole_anim_for(*_frame_for_anim(anim, t, progress, -1.0, -1.0), t, equipment)[0]
        if _whole_figure_layer(hd_look, sex, probe, equipment, _build_item_map()):
            ctx = dict(fx_ctx or {})
            ctx.setdefault("full_armour", bool(armour_layer_for(sex, equipment)))
            if _elemental_fx_worn(hd_look, sex):
                # David, 24 Oct 2026: an elemental outfit's own effect always shows; gear auras never suppress it.
                ctx["eclipse"] = False
                ctx["full_armour"] = False
            return _draw_player_core(surf, sex, hd_look, cx, cy_feet, tile, t, anim, progress, facing,
                                     hit_t, death_t, equipment, tool, fx_ctx=ctx)
    except Exception:
        import logging
        logging.getLogger("player_hd").exception("HD outfit draw failed; retrying villager default")
        appearance = get_default_appearance(sex, starter=True)
    default = get_default_appearance(sex, starter=True)
    ok = _draw_player_core(
        surf, sex, appearance or default, cx, cy_feet, tile, t, anim, progress, facing,
        hit_t, death_t, equipment, tool, layered=False,
    )
    if ok:
        return True
    return _draw_player_core(
        surf, sex, default, cx, cy_feet, tile, t, anim, progress, facing,
        hit_t, death_t, equipment, tool, layered=False,
    )


def _draw_player_core(surf, sex, appearance, cx, cy_feet, tile, t, anim, progress, facing,
                      hit_t, death_t, equipment, tool, layered=False, fx_ctx=None):
    """layered=True is the old paper doll (backup for missing art / errors / armour)."""
    final_anim, frame_idx = _frame_for_anim(anim, t, progress, hit_t, death_t)
    if not layered and final_anim in ("hit", "death") and anim in _WHOLE_ANIMS:
        # outfits have no hit/death strips: hold the outfit's own frame instead of flashing the doll
        final_anim, frame_idx = _frame_for_anim(anim, t, progress, -1.0, -1.0)
    preview = bool((fx_ctx or {}).get("preview"))
    scale_tag, base = _scale_for(tile, preview=preview)
    meta = _load_meta()
    # 8x/4x sheets are idle previews for the creator and shop. Walk and combat
    # live at 2x, so a close camera scales those up instead of dropping to 2D.
    if scale_tag in ("4x", "8x") and final_anim != "idle":
        scale_tag, base = "2x", 80
    # Outfitters stage: hold the AI/portrait idle (frame 0) so we never mix 8x with 2x breath frames.
    if preview and scale_tag in ("4x", "8x") and final_anim == "idle":
        frame_idx = 0
    facing_tag = _facing_str(facing)
    flip_x = False
    if final_anim in ("melee", "ranged"):
        # s and n have their own strips. w is the east strip, mirrored.
        if facing_tag == "w":
            facing_tag = "e"
            flip_x = True
    else:
        anim_facings = (meta.get("anims") or {}).get(final_anim, {}).get("facings", ["s", "e", "n"])
        if facing_tag not in anim_facings:
            if facing_tag == "w" and "e" in anim_facings:
                facing_tag = "e"
                flip_x = True
            elif facing_tag not in anim_facings:
                # gather loops ship east-only today: use the strip that exists rather than drop to 2D
                facing_tag = "s" if "s" in anim_facings or not anim_facings else anim_facings[0]
    item_map = _build_item_map()
    whole = None
    if not layered:
        w_anim, w_frame = _whole_anim_for(final_anim, frame_idx, t, equipment)
        whole = _whole_figure_layer(appearance, sex, w_anim, equipment, item_map)
        if whole and w_anim not in _WHOLE_ANIMS and not _whole_anim_present(sex, whole, w_anim):
            w_anim, w_frame = _frame_for_anim("idle", t, None, -1.0, -1.0)
            final_anim = None   # force the whole-figure branch below to take the idle strip
        if whole and w_anim != final_anim:
            # the outfit's own combat / skilling strip (weapon or tool painted in), s/e/n with w = e mirrored
            final_anim, frame_idx = w_anim, w_frame
            facing_tag, flip_x = _facing_str(facing), False
            if facing_tag == "w":
                facing_tag, flip_x = "e", True
            if scale_tag in ("4x", "8x"):
                scale_tag, base = "2x", 80
    if whole:
        hair_id = (appearance or {}).get("hair_colour") or ("chestnut" if sex == "female" else "dark_brown")
        visible = [(whole, {"skin_whole": skin_rgb(skin_tone_id(appearance)), "hair_whole": _parse_hair_colour(hair_id)},
                    {"s": 50, "e": 50, "n": 50, "w": 50})]
        swing_layer = None
    else:
        cosmetic = _cosmetic_layers(appearance, sex, item_map)
        visible, swing_layer = _apply_covers(cosmetic, equipment, final_anim, sex, tool=tool)
    visible.insert(0, ("shadow", None, {"s": 0, "e": 0, "n": 0, "w": 0}))
    if final_anim == "melee" and frame_idx in (4, 5) and swing_layer:
        visible.append((
            f"fx_swing_{base_layer(swing_layer)}", None,
            {"s": 91, "e": 91, "n": 91, "w": 91},
        ))
    visible.sort(key=lambda row: _effective_z(row[0], row[2], final_anim, facing_tag))

    feet_px = (meta.get("feet_px") or {}).get(scale_tag, [72, 124])
    k = tile / float(base)
    canvas = (meta.get("canvas") or {}).get(scale_tag, [144, 144])
    feet_x = feet_px[0] * k
    feet_y = feet_px[1] * k
    if flip_x:
        feet_x = (canvas[0] * k) - feet_x

    # Layers that hide the head under them (catalogue role erase_mask, e.g. the female
    # Eclipse helmet) need an offscreen composite so the erase only touches this sprite.
    masked = {name for name, _t, _z in visible if mask_layer_for(sex, name)}
    dest, off_dx, off_dy = surf, 0, 0
    if masked:
        cw, ch = int(canvas[0] * k), int(canvas[1] * k)
        dest = pygame.Surface((cw * 2, ch * 2), pygame.SRCALPHA)
        off_dx, off_dy = cw - int(cx), ch - int(cy_feet)

    body_ok = False
    for layer_name, tint_rgb, _z in visible:
        use_facing = facing_tag
        layer_flip = flip_x
        main_surf, tint_surf, part_scale, part_base = _layer_parts(
            sex, scale_tag, layer_name, final_anim, use_facing, frame_idx, tile, base,
        )
        if main_surf is None and tint_surf is None and use_facing != "e":
            if final_anim in ("melee", "ranged") and use_facing in ("s", "n"):
                _warn_missing_strip(sex, final_anim, use_facing)
            main_surf, tint_surf, part_scale, part_base = _layer_parts(
                sex, scale_tag, layer_name, final_anim, "e", frame_idx, tile, base,
            )
            layer_flip = True
        if main_surf is None and tint_surf is None:
            if layer_name.startswith("body_"):
                return False
            continue
        if layer_name.startswith("body_") and (main_surf is not None or tint_surf is not None):
            body_ok = True
            file_facing = "e" if (layer_flip and not flip_x) else use_facing
            last_draw.clear()
            last_draw.update({
                "anim": final_anim,
                "facing": file_facing,
                "strip": f"{final_anim}_{file_facing}.png",
                "frame": frame_idx,
                "flip": bool(layer_flip),
            })
            _store_combat_anchors(sex, final_anim, file_facing, frame_idx, tile, equipment)
        if layer_name == whole and main_surf is not None:
            body_ok = True
            file_facing = "e" if (layer_flip and not flip_x) else use_facing
            last_draw.clear()
            last_draw.update({"anim": final_anim, "facing": file_facing, "strip": f"{final_anim}_{file_facing}.png",
                              "frame": frame_idx, "flip": bool(layer_flip), "whole": layer_name})
            # Load skin/hair at the same resolved scale as the body (shop 4x portraits).
            skin_surf = _layer_skin(sex, part_scale, layer_name, final_anim, file_facing, frame_idx, tile, part_base)
            rgb = tuple(tint_rgb["skin_whole"])
            main_surf = _cached(("whole", id(main_surf), rgb), lambda: _skin_whole(main_surf, skin_surf, rgb))
            # Hair tint whenever a ratio mask exists (bare-head armour, fire/water, starters, …).
            # Missing mask → leave painted hair alone (avoids walk/idle colour flash).
            # Never let hair tint touch skin pixels (face / neck / hands).
            hair_surf = _hair_without_skin(
                _layer_hair(sex, part_scale, layer_name, final_anim, file_facing, frame_idx, tile, part_base),
                skin_surf,
            )
            hrgb = tuple(tint_rgb.get("hair_whole") or (112, 76, 52))
            if hair_surf is not None and hair_surf.get_size() == main_surf.get_size():
                main_surf = _cached(("hair", id(main_surf), id(hair_surf), hrgb),
                                    lambda: _skin_whole(main_surf, hair_surf, hrgb))
            if is_barehead_layer(layer_name) and layer_name.startswith("armour_") and _helm.helmet_tier(equipment):
                main_surf = _cached(("coif", id(main_surf), id(skin_surf), id(hair_surf)),
                                    lambda: _coif_jaw(main_surf, skin_surf, hair_surf))
            tint_rgb = None
        if isinstance(tint_rgb, dict):
            main_surf, tint_surf = _recolour(tint_rgb, main_surf, tint_surf)
            tint_rgb = None
        anchor_x = feet_x
        if layer_flip and not flip_x:
            width = (main_surf or tint_surf).get_width()
            anchor_x = width - feet_x
        if layer_flip:
            if main_surf is not None:
                main_surf = pygame.transform.flip(main_surf, True, False)
            if tint_surf is not None:
                tint_surf = pygame.transform.flip(tint_surf, True, False)
        pos = (int(cx - anchor_x) + off_dx, int(cy_feet - feet_y) + off_dy)
        if layer_name in masked:
            mask_facing = "e" if (layer_flip and not flip_x) else use_facing
            _erase_under(dest, sex, scale_tag, layer_name, final_anim, mask_facing, frame_idx, tile, base,
                         layer_flip, pos)
        slung = layer_name == whole and main_surf is not None and final_anim in _slung.SLUNG_ANIMS
        if slung:
            vis_facing = "w" if (file_facing == "e" and layer_flip) else file_facing
            _slung.draw(dest, main_surf, pos, vis_facing, equipment, "under")
        fx_here = layer_name == whole and main_surf is not None and not layered
        if fx_here:
            _vf = "e" if (layer_flip and not flip_x) else use_facing
            _draw_outfit_fx(dest, "back", sex, appearance, whole, final_anim, _vf, layer_flip,
                            (cx + off_dx, cy_feet + off_dy), tile, t, fx_ctx)
        if main_surf is not None:
            dest.blit(main_surf, pos)
        if fx_here:
            _draw_jewellery(dest, "jewellery", sex, appearance, whole, final_anim, _vf, frame_idx, layer_flip,
                            main_surf, pos, equipment, t, fx_ctx, scale_tag=scale_tag)
        if fx_here:
            _draw_outfit_fx(dest, "front", sex, appearance, whole, final_anim, _vf, layer_flip,
                            (cx + off_dx, cy_feet + off_dy), tile, t, fx_ctx)
        if slung:
            _slung.draw(dest, main_surf, pos, vis_facing, equipment, "over")
        if fx_here:
            _draw_jewellery(dest, "head", sex, appearance, whole, final_anim, _vf, frame_idx, layer_flip,
                            main_surf, pos, equipment, t, fx_ctx, scale_tag=scale_tag)
        if (layer_name == whole and main_surf is not None and (str(whole).startswith("outfit_") or is_barehead_layer(whole))
                and final_anim in _helm.HELMET_ANIMS):
            _helm.draw(dest, main_surf, pos, sex, "w" if (file_facing == "e" and layer_flip) else file_facing,
                       equipment)
        elif (layer_name == whole and main_surf is not None and (str(whole).startswith("outfit_") or is_barehead_layer(whole))
                and _helm.helmet_tier(equipment)):
            # actions: per-frame head anchors (tools/helm_anchors.py); raised weapons break the head-top
            _helm.draw_action(dest, pos, sex, "w" if (file_facing == "e" and layer_flip) else file_facing, equipment,
                              layer_name, final_anim, file_facing, frame_idx, main_surf, layer_flip)
        if tint_surf is not None and tint_rgb:
            _blit_tinted(dest, tint_surf, tint_rgb, pos)
    if dest is not surf:
        surf.blit(dest, (-off_dx, -off_dy))
    return body_ok


def _erase_under(dest, sex, scale_tag, layer_name, anim, facing, frame_idx, tile, base, flip, pos):
    """Multiply everything drawn so far by (1 - mask alpha), using the same frame, facing and flip."""
    mask_name = mask_layer_for(sex, layer_name)
    m_main, m_tint, _ps, _pb = _layer_parts(sex, scale_tag, mask_name, anim, facing, frame_idx, tile, base)
    frame = m_main or m_tint
    if frame is None:
        key = (sex, mask_name, anim, facing)
        if key not in _MASK_WARNED:
            _MASK_WARNED.add(key)
            print(f"[player_hd] warning: erase mask missing: {sex}/{scale_tag}/{mask_name}/{anim}_{facing}")
        return
    dest.blit(_inverted_mask(frame, flip), pos, special_flags=pygame.BLEND_RGBA_MULT)


def _soft(s, a):
    out = s.copy()
    out.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _elemental_fx_worn(appearance, sex):
    """True when the look wears a collection outfit that ships fx layers (fire, water, ...)."""
    layer = collection_hd(appearance or {})
    return bool(layer and _fx_info("female" if sex == "female" else "male", layer))


def _draw_player_fx(surf, sex, appearance, cx, cy_feet, tile, t, anim, progress, facing,
                    hit_t, death_t, equipment, fx_seed, tier, tool=None, fx_ctx=None):
    """Composite offscreen, then the tier glow behind the sprite."""
    import eclipse_fx
    scale_tag, base = _scale_for(tile)
    canvas = (_load_meta().get("canvas") or {}).get(scale_tag, [144, 144])
    k = tile / float(base)
    cw, ch = int(canvas[0] * k), int(canvas[1] * k)
    pad = max(8, int(tile * 0.4))
    w, h = cw * 2 + pad * 2, ch + pad * 2
    off = pygame.Surface((w, h), pygame.SRCALPHA)
    ox = w // 2
    feet_y = ((_load_meta().get("feet_px") or {}).get(scale_tag, [72, 124])[1]) * k
    oy = int(pad + feet_y)
    ok = draw_player(
        off, sex, appearance, ox, oy, tile, t, anim=anim, progress=progress, facing=facing,
        hit_t=hit_t, death_t=death_t, equipment=equipment, tool=tool, fx_ctx=dict(fx_ctx or {}, eclipse=True),
    )
    elemental = _elemental_fx_worn(appearance, sex)
    if not ok:
        return ok
    zoom = tile / 40.0
    key = (
        sex, tile, last_draw.get("anim"), last_draw.get("facing"), last_draw.get("frame"),
        bool(last_draw.get("flip")), repr(sorted((equipment or {}).items(), key=str)),
        repr(sorted((appearance or {}).items(), key=str)), hit_t >= 0, death_t >= 0,
    )
    aura = eclipse_fx.aura_surface(off, zoom, tier, key=key)
    dest = (int(cx - ox), int(cy_feet - oy))
    if elemental:
        # the gear aura stays only as a faint outline under the elemental effect
        aura = _cached(("aura_soft", tier, key), lambda: _soft(aura, 0.3))
    surf.blit(aura, dest)
    surf.blit(off, dest)
    return ok


def head_top_dy(sex, tile):
    """Pixels from feet to head-top. Matches idle anchors (~ay 110 on 248 feet)."""
    return -int(round(float(tile) * 1.7))


def _load_anchors():
    path = os.path.join(_BASE, "assets", "anchors.json")
    key = ("anchors", path)
    if key not in _META:
        if not os.path.isfile(path):
            _META[key] = {}
        else:
            import json
            with open(path, encoding="utf-8") as handle:
                _META[key] = json.load(handle)
    return _META[key]


def anchor_offset(sex, anim, facing, frame, name, tile, weapon=None):
    """Screen offset from the feet for one anchors.json point. None if absent."""
    sex = "female" if sex == "female" else "male"
    tag = facing if facing in ("s", "e", "n") else "e"
    frames = (
        (((_load_anchors().get("anchors") or {}).get(sex) or {}).get(anim) or {}).get(tag) or []
    )
    if not frames:
        return None
    sample = frames[max(0, min(int(frame), len(frames) - 1))]
    point = sample.get(name)
    if isinstance(point, dict):
        point = point.get(weapon) or None
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    # Anchors are 2x canvas pixels. Feet sit at (144, 248) on the 288 canvas.
    ax, ay = float(point[0]), float(point[1])
    if facing == "w":
        ax = 288.0 - ax
    scale = float(tile) / 80.0
    return (ax - 144.0) * scale, (ay - 248.0) * scale


def _store_combat_anchors(sex, anim, facing, frame, tile, equipment):
    weapon = None
    if equipment:
        weapon, _tint = _weapon_spec(equipment.get("weapon"), sex)
        weapon = base_layer(weapon) if weapon else None
    for name in ("head_top", "chest", "hand_L", "hand_R"):
        off = anchor_offset(sex, anim, facing, frame, name, tile, weapon)
        if off is not None:
            last_draw[name] = off
        elif name == "head_top":
            # Idle/walk sheets may omit the point — keep a consistent head line.
            last_draw[name] = (0.0, float(head_top_dy(sex, tile)))
    if anim not in ("melee", "ranged"):
        return
    if weapon:
        tip = anchor_offset(sex, anim, facing, frame, "tip", tile, weapon)
        if tip is not None:
            last_draw["tip"] = tip


def get_default_appearance(sex, starter=True):
    """Default look: the free starter outfit (starter=False gives the bare base clothes under it)."""
    if starter:
        return starter_outfit_look(get_default_appearance(sex, starter=False), sex)
    cat = _load_catalogue()
    defaults = (cat.get("defaults") or {}).get(sex) or {}
    female = sex == "female"
    return {
        "skin": defaults.get("skin", "skin_base"),
        "skin_tone": defaults.get("skin_tone", "tone_3"),
        "hair": defaults.get("hair", "hair_ponytail" if female else "hair_side_part"),
        "hair_colour": defaults.get("hair_colour", "chestnut" if female else "dark_brown"),
        "top": defaults.get("top", "top_linen_shirt"),
        "bottom": defaults.get("bottom", "bottom_long_skirt" if female else "bottom_work_trousers"),
        "shoes": defaults.get("shoes", "shoes_leather"),
        "outfit": defaults.get("outfit"),
        "accessories": list(defaults.get("accessories") or []),
        "cloak": defaults.get("cloak"),
        "head": defaults.get("head"),
        "held": defaults.get("held"),
        "jewellery": list(defaults.get("jewellery") or []),
        "palette": defaults.get("palette"),
        "outfit_level": int(defaults.get("outfit_level") or 1),
    }
