"""
HD Player Asset Loader + Paper-Doll Renderer

Loads sprites from game/assets/player_hd/ and composites layers at runtime
based on appearance dict. Frame timing follows meta.json so walk, combat and
skilling stay on the same clock as the 2D figure.
"""
import math
import os

import pygame

_BASE = os.path.join(
    os.path.dirname(__file__), "..", "..", "player_hd", "assets"
)
_META_PATH = os.path.join(_BASE, "meta.json")
_CATALOGUE_PATH = os.path.join(_BASE, "catalogue.json")

_IMAGES = {}
_FRAMES = {}
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
    if path not in _IMAGES:
        full = os.path.join(_BASE, path)
        if not os.path.isfile(full):
            _IMAGES[path] = None
        else:
            _IMAGES[path] = pygame.image.load(full).convert_alpha()
    return _IMAGES[path]


def _scale_for(tile):
    """Source scale at or above the target, then smoothscale down."""
    if tile <= 40:
        return "1x", 40
    if tile <= 80:
        return "2x", 80
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
    """Base and tint independently. Either may be missing."""
    if scale_tag == "4x" and not _has_4x_frame(sex, layer, anim, facing, frame_idx):
        # Missing 4x strip (or a single-frame 4x portrait while animating): use 2x quietly.
        scale_tag, base = "2x", 80
    stem = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}"
    main = _frame_surface(stem + ".png", frame_idx, scale_tag, tile, base)
    tint = _frame_surface(stem + "_tint.png", frame_idx, scale_tag, tile, base)
    return main, tint


def _has_4x_frame(sex, layer, anim, facing, frame_idx):
    strip = _load_image(f"{sex}/4x/{layer}/{anim}_{facing}.png")
    if strip is None:
        strip = _load_image(f"{sex}/4x/{layer}/{anim}_{facing}_tint.png")
    if strip is None:
        return False
    frames = max(1, strip.get_width() // max(1, strip.get_height()))
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
    if iid in ("leather_body", "goblin_mail"):
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
    hit_t=-1.0, death_t=-1.0, equipment=None, fx_seed=None, tool=None,
):
    """Draw the HD paper doll. False means the body art is missing, so use 2D.

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
                hit_t, death_t, equipment, fx_seed, tier, tool=tool,
            )
    sex = "female" if sex == "female" else "male"
    appearance = appearance or get_default_appearance(sex)
    final_anim, frame_idx = _frame_for_anim(anim, t, progress, hit_t, death_t)
    scale_tag, base = _scale_for(tile)
    meta = _load_meta()
    # 4x sheets are idle previews for the creator and shop. Walk and combat
    # live at 2x, so a close camera scales those up instead of dropping to 2D.
    if scale_tag == "4x" and final_anim != "idle":
        scale_tag, base = "2x", 80
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
        main_surf, tint_surf = _layer_parts(
            sex, scale_tag, layer_name, final_anim, use_facing, frame_idx, tile, base,
        )
        if main_surf is None and tint_surf is None and use_facing != "e":
            if final_anim in ("melee", "ranged") and use_facing in ("s", "n"):
                _warn_missing_strip(sex, final_anim, use_facing)
            main_surf, tint_surf = _layer_parts(
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
        if main_surf is not None:
            dest.blit(main_surf, pos)
        if tint_surf is not None and tint_rgb:
            _blit_tinted(dest, tint_surf, tint_rgb, pos)
    if dest is not surf:
        surf.blit(dest, (-off_dx, -off_dy))
    return body_ok


def _erase_under(dest, sex, scale_tag, layer_name, anim, facing, frame_idx, tile, base, flip, pos):
    """Multiply everything drawn so far by (1 - mask alpha), using the same frame, facing and flip."""
    mask_name = mask_layer_for(sex, layer_name)
    m_main, m_tint = _layer_parts(sex, scale_tag, mask_name, anim, facing, frame_idx, tile, base)
    frame = m_main or m_tint
    if frame is None:
        key = (sex, mask_name, anim, facing)
        if key not in _MASK_WARNED:
            _MASK_WARNED.add(key)
            print(f"[player_hd] warning: erase mask missing: {sex}/{scale_tag}/{mask_name}/{anim}_{facing}")
        return
    dest.blit(_inverted_mask(frame, flip), pos, special_flags=pygame.BLEND_RGBA_MULT)


def _draw_player_fx(surf, sex, appearance, cx, cy_feet, tile, t, anim, progress, facing,
                    hit_t, death_t, equipment, fx_seed, tier, tool=None):
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
        hit_t=hit_t, death_t=death_t, equipment=equipment, tool=tool,
    )
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
    surf.blit(aura, dest)
    surf.blit(off, dest)
    return ok


def head_top_dy(sex, tile):
    return -int(tile * 4.5)


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
    if anim not in ("melee", "ranged"):
        return
    weapon = None
    if equipment:
        weapon, _tint = _weapon_spec(equipment.get("weapon"), sex)
        weapon = base_layer(weapon) if weapon else None
    for name in ("head_top", "chest", "hand_L", "hand_R"):
        off = anchor_offset(sex, anim, facing, frame, name, tile, weapon)
        if off is not None:
            last_draw[name] = off
    if weapon:
        tip = anchor_offset(sex, anim, facing, frame, "tip", tile, weapon)
        if tip is not None:
            last_draw["tip"] = tip


def get_default_appearance(sex):
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
