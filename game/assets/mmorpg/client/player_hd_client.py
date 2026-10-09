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
    if anim == "chop":
        ph = ((t * 1.1) % 1.0) if t is not None else 0.0
        return ("chop", int(ph * 8))
    if anim == "mine":
        ph = ((t * 1.05) % 1.0) if t is not None else 0.0
        return ("mine", int(ph * 8))
    if anim == "fish":
        ph = ((t * 0.55) % 1.0) if t is not None else 0.0
        return ("fish", int(ph * 8))
    if anim == "walk":
        ph = ((t * 1.15) % 1.0) if t is not None else 0.0
        return ("walk", int(ph * 8))
    ph = ((t / math.pi) % 1.0) if t is not None else 0.0
    return ("idle", int(ph * 8))


def _layer_parts(sex, scale_tag, layer, anim, facing, frame_idx, tile, base):
    """Base and tint independently. Either may be missing."""
    stem = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}"
    main = _frame_surface(stem + ".png", frame_idx, scale_tag, tile, base)
    tint = _frame_surface(stem + "_tint.png", frame_idx, scale_tag, tile, base)
    return main, tint


def _build_item_map():
    items = {}
    for entry in _load_catalogue().get("items", []):
        items[entry["id"]] = entry
    return items


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


def _tier_rgb(item_id, named=None):
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


def _weapon_spec(item_id):
    if not item_id:
        return None, None
    iid = str(item_id)
    if iid == "eclipse_cleaver" or iid.endswith("_battleaxe") or iid.endswith("_axe"):
        return "wpn_axe", _tier_rgb(iid)
    if iid.endswith("_longsword") or iid.endswith("_sword") or iid.endswith("_dagger"):
        return "wpn_sword", _tier_rgb(iid)
    if iid.endswith("_pickaxe"):
        return "wpn_pickaxe", _tier_rgb(iid)
    if "bow" in iid:
        return "wpn_bow", _tier_rgb(iid, "wood")
    if "staff" in iid or "wand" in iid:
        return "wpn_staff", _tier_rgb(iid)
    return None, None


def _body_spec(item_id):
    if not item_id:
        return None
    iid = str(item_id)
    if iid in ("leather_body", "goblin_mail"):
        return [("arm_chainbody", _tier_rgb(iid, "leather"))]
    if iid.endswith("_chainbody"):
        return [("arm_chainbody", _tier_rgb(iid))]
    if iid.endswith("_body"):
        tint = _tier_rgb(iid)
        return [("arm_platebody", tint), ("arm_gauntlets", tint)]
    return None


def _legs_spec(item_id):
    if not item_id:
        return None
    iid = str(item_id)
    if iid == "leather_chaps":
        return [("arm_platelegs", _tier_rgb(iid, "leather"))]
    if iid.endswith("_chainlegs"):
        return [("arm_platelegs", _tier_rgb(iid))]
    if iid.endswith("_legs"):
        tint = _tier_rgb(iid)
        return [("arm_platelegs", tint), ("arm_sabatons", tint)]
    return None


def _helm_spec(item_id):
    if not item_id:
        return None
    iid = str(item_id)
    if iid == "leather_cowl":
        return ("arm_helm", _tier_rgb(iid, "leather"))
    if iid == "bone_crown":
        return ("arm_helm", _BONE)
    if iid.endswith("_helmet"):
        return ("arm_helm", _tier_rgb(iid))
    return None


def _shield_spec(item_id):
    if not item_id:
        return None
    iid = str(item_id)
    if iid == "wooden_shield":
        return ("arm_kiteshield", _tier_rgb(iid, "wood"))
    if iid.endswith("_shield") or iid.endswith("_sq_shield"):
        return ("arm_kiteshield", _tier_rgb(iid))
    return None


def _cosmetic_layers(appearance, sex, item_map):
    """Clothes, hair, brows and shadow. Armour hiding is applied by the caller."""
    layers = []
    skin = _slot_item(appearance, "skin", sex, item_map)
    if skin:
        layers.append((skin["layer"], None, skin.get("z") or {"s": 10, "e": 10, "n": 10, "w": 10}, "body"))
    hair_rgb = _parse_hair_colour(appearance.get("hair_colour", "dark_brown"))
    layers.append(("brows", hair_rgb, {"s": 12, "e": 12, "n": 12, "w": 12}, "brows"))
    hair = _slot_item(appearance, "hair", sex, item_map)
    if hair:
        layers.append((hair["layer"], hair_rgb, hair.get("z") or {"s": 40, "e": 40, "n": 40, "w": 40}, "hair"))
    outfit = appearance.get("outfit")
    outfit_item = item_map.get(outfit) if outfit else None
    if outfit_item and outfit_item.get("layer"):
        tint = None
        if outfit_item.get("tintable"):
            tint = tuple(outfit_item.get("tint") or [255, 255, 255])
        layers.append((outfit_item["layer"], tint, outfit_item.get("z") or {"s": 30, "e": 30, "n": 30, "w": 30}, "outfit"))
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
    return layers


def _apply_covers(layers, equipment, anim):
    """Drop clothes that armour or an outfit covers, then add gear layers."""
    eq = equipment or {}
    helm = _helm_spec(eq.get("helmet"))
    body = _body_spec(eq.get("body")) or []
    legs = _legs_spec(eq.get("legs")) or []
    shield = _shield_spec(eq.get("shield"))
    hide = set()
    if helm:
        hide.add("hair")
    plate_body = any(name == "arm_platebody" for name, _tint in body)
    plate_legs = any(name == "arm_sabatons" for name, _tint in legs)
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
    if anim == "chop":
        kept.append(("wpn_axe", _tier_rgb(weapon_id, "wood"), _layer_z("wpn_axe", z_fallback)))
        swing = "wpn_axe"
    elif anim == "mine":
        kept.append(("wpn_pickaxe", _tier_rgb(weapon_id), _layer_z("wpn_pickaxe", z_fallback)))
        swing = "wpn_pickaxe"
    elif anim == "fish":
        kept.append(("wpn_rod", _tier_rgb(weapon_id, "wood"), _layer_z("wpn_rod", z_fallback)))
        swing = None
    else:
        wlayer, wtint = _weapon_spec(weapon_id)
        swing = wlayer
        if wlayer:
            kept.append((wlayer, wtint, _layer_z(wlayer, {"s": 90, "e": 90, "n": 8, "w": 90})))
    return kept, swing


def _blit_tinted(dest, tint_surf, rgb, pos):
    tinted = tint_surf.copy()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    overlay.fill((*rgb, 255))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    dest.blit(tinted, pos)


def draw_player(
    surf, sex, appearance, cx, cy_feet, tile, t,
    anim="idle", progress=None, facing=1,
    hit_t=-1.0, death_t=-1.0, equipment=None,
):
    """Draw the HD paper doll. False means the body art is missing, so use 2D."""
    sex = "female" if sex == "female" else "male"
    appearance = appearance or get_default_appearance(sex)
    scale_tag, base = _scale_for(tile)
    final_anim, frame_idx = _frame_for_anim(anim, t, progress, hit_t, death_t)
    facing_tag = _facing_str(facing)
    meta = _load_meta()
    anim_facings = (meta.get("anims") or {}).get(final_anim, {}).get("facings", ["s", "e", "n"])
    flip_x = False
    if facing_tag not in anim_facings:
        if facing_tag == "w" and "e" in anim_facings:
            facing_tag = "e"
            flip_x = True
        else:
            facing_tag = "s"
    item_map = _build_item_map()
    cosmetic = _cosmetic_layers(appearance, sex, item_map)
    visible, swing_layer = _apply_covers(cosmetic, equipment, final_anim)
    visible.insert(0, ("shadow", None, {"s": 0, "e": 0, "n": 0, "w": 0}))
    if final_anim == "melee" and frame_idx in (4, 5) and swing_layer:
        visible.append((
            f"fx_swing_{swing_layer}", None,
            {"s": 91, "e": 91, "n": 91, "w": 91},
        ))
    visible.sort(key=lambda row: (row[2] or {}).get(facing_tag, 50))

    feet_px = (meta.get("feet_px") or {}).get(scale_tag, [72, 124])
    k = tile / float(base)
    canvas = (meta.get("canvas") or {}).get(scale_tag, [144, 144])
    feet_x = feet_px[0] * k
    feet_y = feet_px[1] * k
    if flip_x:
        feet_x = (canvas[0] * k) - feet_x

    body_ok = False
    for layer_name, tint_rgb, _z in visible:
        use_facing = facing_tag
        layer_flip = flip_x
        main_surf, tint_surf = _layer_parts(
            sex, scale_tag, layer_name, final_anim, use_facing, frame_idx, tile, base,
        )
        if main_surf is None and tint_surf is None and use_facing != "e":
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
        anchor_x = feet_x
        if layer_flip and not flip_x:
            width = (main_surf or tint_surf).get_width()
            anchor_x = width - feet_x
        if layer_flip:
            if main_surf is not None:
                main_surf = pygame.transform.flip(main_surf, True, False)
            if tint_surf is not None:
                tint_surf = pygame.transform.flip(tint_surf, True, False)
        pos = (int(cx - anchor_x), int(cy_feet - feet_y))
        if main_surf is not None:
            surf.blit(main_surf, pos)
        if tint_surf is not None and tint_rgb:
            _blit_tinted(surf, tint_surf, tint_rgb, pos)
    return body_ok


def head_top_dy(sex, tile):
    return -int(tile * 4.5)


def get_default_appearance(sex):
    cat = _load_catalogue()
    defaults = (cat.get("defaults") or {}).get(sex) or {}
    female = sex == "female"
    return {
        "skin": defaults.get("skin", "skin_light"),
        "hair": defaults.get("hair", "hair_ponytail" if female else "hair_side_part"),
        "hair_colour": defaults.get("hair_colour", "chestnut" if female else "dark_brown"),
        "top": defaults.get("top", "top_linen_shirt"),
        "bottom": defaults.get("bottom", "bottom_long_skirt" if female else "bottom_work_trousers"),
        "shoes": defaults.get("shoes", "shoes_leather"),
        "outfit": defaults.get("outfit"),
        "accessories": list(defaults.get("accessories") or []),
    }
