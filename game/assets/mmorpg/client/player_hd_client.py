"""
HD Player Asset Loader + Paper-Doll Renderer

Loads sprites from game/assets/player_hd/ and composites layers at runtime
based on appearance dict. Matches meta.json frame timing to existing 2D rs_style.py
so walk cycle, combat and skilling remain byte-identical in timing and tile positioning.

Architecture: loads strip PNGs for male/female x 1x/2x/4x x layers x anims,
picks frame index using existing pose/t/progress values, tints cosmetic layers,
sorts by z[facing] and blits.

Combat: adds new hit (4 frames over 0.36s) and death (8 frames over 1.2s) anims
using facing from the moment the hitsplat/DEATH arrived. Overrides idle/walk during.
"""
import os
import math
import pygame

_BASE = os.path.join(
    os.path.dirname(__file__), "..", "..", "player_hd", "assets"
)
_META_PATH = os.path.join(_BASE, "meta.json")
_CATALOGUE_PATH = os.path.join(_BASE, "catalogue.json")

_IMAGES = {}  # (path) -> Surface
_SCALED = {}  # (path, w, h) -> Surface (runtime scale cache)
_META = None
_CATALOGUE = None

# Frame timing patterns (match meta.json sample_progress arrays for combat)
MELEE_PROGRESS = [0.0, 0.1, 0.22, 0.34, 0.48, 0.55, 0.62, 0.71, 0.8, 0.91]
RANGED_PROGRESS = [0.0, 0.12, 0.24, 0.36, 0.48, 0.55, 0.72, 0.86]


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
    """Load a PNG from disk; cache by path."""
    if path not in _IMAGES:
        full = os.path.join(_BASE, path)
        if not os.path.isfile(full):
            _IMAGES[path] = None
        else:
            _IMAGES[path] = pygame.image.load(full).convert_alpha()
    return _IMAGES[path]


def _scale_for(tile):
    """Pick 1x/2x/4x tag and base tile from runtime TILE."""
    if tile >= 160:
        return "4x", 160
    if tile >= 80:
        return "2x", 80
    return "1x", 40


def _scaled(surf, tile, base):
    """Scale surface to current tile size if needed."""
    if surf is None or tile == base:
        return surf
    w = max(1, int(round(surf.get_width() * tile / float(base))))
    h = max(1, int(round(surf.get_height() * tile / float(base))))
    key = (id(surf), w, h)
    if key not in _SCALED:
        _SCALED[key] = pygame.transform.smoothscale(surf, (w, h))
    return _SCALED[key]


def _facing_str(face):
    """Convert client facing to meta.json facing tag."""
    if face in ("back", "n"):
        return "n"
    if face in (-1, "-1", "w"):
        return "w"
    if face in (1, "1", "e"):
        return "e"
    return "s"


def _frame_for_anim(anim, t=None, progress=None, hit_t=-1.0, death_t=-1.0):
    """
    Return (anim_name, frame_index).
    
    Death overrides everything; hit overrides idle/walk; then combat/skilling.
    Uses same timing as existing 2D code.
    """
    # Death takes full priority
    if death_t >= 0:
        u = min(1.0, death_t / 1.2)
        frame = min(7, int(u * 8))
        return ("death", frame)
    
    # Hit reaction (only during idle/walk, not during swings/skilling)
    if hit_t >= 0 and anim in ("idle", "walk"):
        u = min(1.0, hit_t / 0.36)
        frame = min(3, int(u * 4))
        return ("hit", frame)
    
    # Combat / skilling from existing pose system
    if anim == "melee":
        if progress is None:
            return ("idle", 0)
        # Find last frame index where MELEE_PROGRESS[i] <= progress
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
    
    # idle
    ph = ((t / math.pi) % 1.0) if t is not None else 0.0
    return ("idle", int(ph * 8))


def _load_layer_frame(sex, scale_tag, layer, anim, facing, frame_idx):
    """
    Load one frame from a strip: path = {sex}/{scale}/{layer}/{anim}_{facing}.png
    Returns (main_surf, tint_surf) where tint_surf may be None.
    """
    # Build path
    path = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}.png"
    strip = _load_image(path)
    if strip is None:
        return (None, None)
    
    # Calculate canvas width (meta.json canvas field)
    meta = _load_meta()
    canvas = meta.get("canvas", {}).get(scale_tag, [144, 144])
    canvas_w = canvas[0]
    
    # Extract frame
    x = frame_idx * canvas_w
    surf = strip.subsurface((x, 0, canvas_w, strip.get_height())).copy()
    
    # Try loading tint mask
    tint_path = f"{sex}/{scale_tag}/{layer}/{anim}_{facing}_tint.png"
    tint_strip = _load_image(tint_path)
    tint_surf = None
    if tint_strip is not None:
        tint_surf = tint_strip.subsurface((x, 0, canvas_w, tint_strip.get_height())).copy()
    
    return (surf, tint_surf)


def _build_item_map():
    """Index catalogue items by id."""
    cat = _load_catalogue()
    items = {}
    for entry in cat.get("items", []):
        items[entry["id"]] = entry
    return items


def _parse_hair_colour(colour_id):
    """Return (r, g, b) from catalogue hair_colours."""
    cat = _load_catalogue()
    for hc in cat.get("hair_colours", []):
        if hc["id"] == colour_id:
            rgb = hc.get("rgb", [0, 0, 0])
            return tuple(rgb)
    return (0, 0, 0)


def _visible_layers(appearance, item_map):
    """
    Return list of (layer_name, tint_rgb_or_None, z_dict).
    
    appearance = {skin, hair, hair_colour, top, bottom, shoes, outfit, accessories:[...]}
    Outfit overrides top/bottom/shoes if present.
    """
    layers = []
    
    # Always: body (skin)
    skin_id = appearance.get("skin", "skin_light")
    skin_item = item_map.get(skin_id)
    if skin_item:
        layers.append((skin_item["layer"], None, skin_item["z"]))
    
    # Brows (always, not tintable in this version)
    layers.append(("brows", None, {"s": 12, "e": 12, "w": 12, "n": 12}))
    
    # Outfit overrides top/bottom/shoes
    outfit_id = appearance.get("outfit")
    if outfit_id and outfit_id in item_map:
        outfit_item = item_map[outfit_id]
        for layer_name in outfit_item.get("layers", []):
            tint = None
            if outfit_item.get("tintable"):
                # Use tier colour if present
                tint = tuple(outfit_item.get("tint", [255, 255, 255]))
            layers.append((layer_name, tint, outfit_item["z"]))
    else:
        # Top
        top_id = appearance.get("top")
        if top_id and top_id in item_map:
            item = item_map[top_id]
            tint = tuple(item.get("tint", [255, 255, 255])) if item.get("tintable") else None
            layers.append((item["layer"], tint, item["z"]))
        
        # Bottom
        bottom_id = appearance.get("bottom")
        if bottom_id and bottom_id in item_map:
            item = item_map[bottom_id]
            tint = tuple(item.get("tint", [255, 255, 255])) if item.get("tintable") else None
            layers.append((item["layer"], tint, item["z"]))
        
        # Shoes
        shoes_id = appearance.get("shoes")
        if shoes_id and shoes_id in item_map:
            item = item_map[shoes_id]
            tint = tuple(item.get("tint", [255, 255, 255])) if item.get("tintable") else None
            layers.append((item["layer"], tint, item["z"]))
    
    # Hair
    hair_id = appearance.get("hair")
    if hair_id and hair_id in item_map:
        item = item_map[hair_id]
        hair_colour = _parse_hair_colour(appearance.get("hair_colour", "dark_brown"))
        layers.append((item["layer"], hair_colour, item["z"]))
    
    # Accessories
    for acc_id in appearance.get("accessories", []):
        if acc_id in item_map:
            item = item_map[acc_id]
            tint = tuple(item.get("tint", [255, 255, 255])) if item.get("tintable") else None
            layers.append((item["layer"], tint, item["z"]))
    
    return layers


def draw_player(
    surf, sex, appearance, cx, cy_feet, tile, t,
    anim="idle", progress=None, facing=1,
    hit_t=-1.0, death_t=-1.0,
):
    """
    Draw HD player at (cx, cy_feet) where cy_feet is the ground/feet position.
    
    Args:
        surf: pygame surface to blit to
        sex: "male" or "female"
        appearance: dict {skin, hair, hair_colour, top, bottom, shoes, outfit, accessories}
        cx, cy_feet: screen position (feet anchor)
        tile: TILE size (40 at 1x, 80 at 2x, etc)
        t: game time for idle/walk/skilling loops
        anim: base animation ("idle", "walk", "melee", "ranged", "chop", "mine", "fish")
        progress: combat progress 0..1 (for melee/ranged frame selection)
        facing: 1, -1, "front", "back" (client facing)
        hit_t: seconds since hit (>=0 triggers hit anim)
        death_t: seconds since death (>=0 triggers death anim)
    
    Returns: True if drawn (for client to skip old draw_humanoid_detailed).
    """
    scale_tag, base = _scale_for(tile)
    
    # Resolve final anim + frame
    final_anim, frame_idx = _frame_for_anim(anim, t, progress, hit_t, death_t)
    
    # Facing string
    facing_tag = _facing_str(facing)
    
    # If anim doesn't support this facing, fall back to 'e' and maybe flip
    meta = _load_meta()
    anim_facings = meta.get("anims", {}).get(final_anim, {}).get("facings", ["s", "e", "n"])
    
    flip_x = False
    if facing_tag not in anim_facings:
        if facing_tag == "w" and "e" in anim_facings:
            facing_tag = "e"
            flip_x = True
        else:
            # Fall back to 's' for unknown
            facing_tag = "s"
    
    # Load item map
    item_map = _build_item_map()
    
    # Build visible layers
    visible = _visible_layers(appearance, item_map)
    
    # Sort by z[facing_tag]
    visible.sort(key=lambda x: x[2].get(facing_tag, 50))
    
    # Feet anchor from meta
    feet_px = meta.get("feet_px", {}).get(scale_tag, [72, 124])
    k = tile / float(base)
    feet_x, feet_y = feet_px[0] * k, feet_px[1] * k
    
    # Blit each layer
    for layer_name, tint_rgb, z_dict in visible:
        main_surf, tint_surf = _load_layer_frame(sex, scale_tag, layer_name, final_anim, facing_tag, frame_idx)
        
        if main_surf is None:
            continue
        
        # Scale to tile if needed
        main_surf = _scaled(main_surf, tile, base)
        if tint_surf:
            tint_surf = _scaled(tint_surf, tile, base)
        
        # Flip for 'w'
        if flip_x:
            main_surf = pygame.transform.flip(main_surf, True, False)
            if tint_surf:
                tint_surf = pygame.transform.flip(tint_surf, True, False)
            # Mirror feet anchor
            feet_x = main_surf.get_width() - feet_x
        
        # Position
        bx = int(cx - feet_x)
        by = int(cy_feet - feet_y)
        
        # Blit main
        surf.blit(main_surf, (bx, by))
        
        # Blit tint mask if needed
        if tint_surf and tint_rgb:
            # Multiply blend: create a copy, fill with colour, multiply
            tinted = tint_surf.copy()
            color_overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
            color_overlay.fill((*tint_rgb, 255))
            tinted.blit(color_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(tinted, (bx, by))
    
    return True


def head_top_dy(sex, tile):
    """
    Return vertical offset from cy_feet to head top (for HP bar, nameplate).
    Approximation: ~4.5 tiles height for player.
    """
    return -int(tile * 4.5)


def get_default_appearance(sex):
    """Return starter appearance dict for new/existing players without saved look."""
    cat = _load_catalogue()
    defaults = cat.get("defaults", {}).get(sex, {})
    return {
        "skin": defaults.get("skin", "skin_light"),
        "hair": defaults.get("hair", "hair_side_part" if sex == "male" else "hair_ponytail"),
        "hair_colour": defaults.get("hair_colour", "dark_brown"),
        "top": defaults.get("top", "top_linen_shirt"),
        "bottom": defaults.get("bottom", "bottom_work_trousers" if sex == "male" else "bottom_long_skirt"),
        "shoes": defaults.get("shoes", "shoes_leather"),
        "outfit": defaults.get("outfit"),
        "accessories": defaults.get("accessories", []),
    }
