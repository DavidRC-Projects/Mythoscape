"""Write assets/catalogue.json + assets/meta.json (pure python)."""
import json, os
CAT = json.load(open("/workspace/player_hd/work/catalog_raw.json"))
REP = json.load(open("/workspace/player_hd/work/post_report.json")) if os.path.exists("/workspace/player_hd/work/post_report.json") else {}
OUT = "/workspace/player_hd/assets"; os.makedirs(OUT, exist_ok=True)

# draw order per facing (s, e, n); west mirrors east. Low draws first.
ZF = {"shadow": (0, 0, 0), "cloak_back": (2, 2, 66), "shield": (92, 3, 92), "bow": (90, 3, 8), "body": (10, 10, 10), "brows": (12, 12, 12),
      "bottom_trousers": (20, 20, 20), "shoes": (24, 24, 24), "bottom_skirt": (28, 28, 28), "top": (40, 40, 40), "outfit": (45, 45, 45),
      "acc_mid": (50, 50, 50), "armour_legs": (52, 52, 52), "armour_feet": (54, 54, 54), "armour_body": (58, 58, 58), "armour_hands": (60, 60, 60),
      "acc_front": (62, 62, 62), "hair": (70, 70, 70), "armour_head": (80, 80, 80), "weapon": (90, 90, 8)}


def zdict(zc):
    s, e, n = ZF[zc]
    return {"s": s, "e": e, "w": e, "n": n}


def files(lid):
    out = {}
    for kind in ("male", "female"):
        r = REP.get(kind, {}).get(lid)
        if r:
            out[kind] = {"fixed": r["fixed"], "tint": r["tint"], "anims": r["anims"]}
    return out


HAIR_PALETTE = [  # sRGB multiply colours for the neutral-grey hair/brow layers (pygame BLEND_RGBA_MULT)
    ("black", (62, 54, 50)), ("dark_brown", (112, 76, 52)), ("chestnut", (150, 92, 52)), ("auburn", (168, 74, 44)),
    ("copper", (210, 112, 58)), ("honey", (226, 170, 96)), ("blonde", (250, 216, 150)), ("platinum", (255, 248, 228)),
    ("ash_grey", (200, 200, 204)), ("forest", (88, 140, 84)), ("azure", (92, 128, 214)), ("rose", (222, 116, 160))]
TIERS = {  # rs_style.metal_palette() base colours -> multiply onto *_tint layers (x1.25 gain, clamp 255)
    "bronze": (200, 150, 75), "iron": (140, 140, 150), "steel": (170, 175, 185), "mithril": (100, 160, 200), "adamant": (70, 180, 110),
    "mythos": (178, 28, 38), "eclipse": (48, 48, 55), "leather": (140, 95, 55), "wood": (150, 110, 70)}

items = []
for c in CAT["catalogue"]:
    if c["slot"] == "skin":
        items.append(dict(id=c["id"], slot="skin", name=c["name"], price=0, starter=True, tintable=False,
                          layer="body_" + c["id"].split("_", 1)[1], z=zdict("body"), files=files("body_" + c["id"].split("_", 1)[1])))
        continue
    items.append(dict(id=c["id"], slot=c["slot"], name=c["name"], price=c["price"], starter=c["starter"], tintable=c["tintable"],
                      layer=c["id"], z=zdict(c["z_class"]), files=files(c["id"])))
armour = [dict(a, layer=a["id"], z=zdict(a["z_class"]), tintable=True, files=files(a["id"])) for a in CAT["armour"]]
weapons = []
for w in CAT["weapons"]:
    zc = "bow" if w["id"] == "wpn_bow" else "weapon"
    weapons.append(dict(w, layer=w["id"], z=zdict(zc), tintable=True, files=files(w["id"])))

catalogue = {
    "version": 1,
    "currency": "coins",
    "slots": ["skin", "hair", "hair_colour", "top", "bottom", "shoes", "outfit", "accessory"],
    "accessory_max": 2,
    "hair_colour_change_price": 20,
    "defaults": {
        "male": {"skin": "skin_light", "hair": "hair_side_part", "hair_colour": "dark_brown", "top": "top_linen_shirt",
                 "bottom": "bottom_work_trousers", "shoes": "shoes_leather", "outfit": None, "accessories": []},
        "female": {"skin": "skin_light", "hair": "hair_ponytail", "hair_colour": "chestnut", "top": "top_linen_shirt",
                   "bottom": "bottom_long_skirt", "shoes": "shoes_leather", "outfit": None, "accessories": []}},
    "items": items,
    "hair_palette": [dict(id=i, mul=list(c)) for i, c in HAIR_PALETTE],
    "armour_layers": armour,
    "weapon_layers": weapons,
    "tier_tints": {k: list(v) for k, v in TIERS.items()},
    "tier_tint_gain": 1.25,
    "tier_from_item_id": "prefix before the first '_' (bronze_sword -> bronze); unknown prefixes use rs_style.metal_palette(item_id) rgb",
    "override_rules": [
        "outfit hides top+bottom while worn",
        "helmet equipped (any *_helmet / leather_cowl): hide hair layer; brows stay visible (open-face helm)",
        "body armour (*_body plate, *_chainbody, goblin_mail, leather_body): hide top AND outfit; plate *_body also draws arm_gauntlets (hides acc_leather_gloves)",
        "leg armour (*_legs, *_chainlegs, leather_chaps): hide bottom AND outfit; plate *_legs also draws arm_sabatons (hides shoes)",
        "if an outfit is hidden by armour on one half only, draw the player's saved top/bottom (or the starter top/bottom) on the uncovered half",
        "shield slot -> arm_kiteshield (kite/sq/wooden all use it, tinted by tier; wooden uses 'wood')",
        "weapon slot -> weapon layer by rs_style weapon kind: sword/dagger/longsword->wpn_sword, axe/battleaxe->wpn_axe, pickaxe->wpn_pickaxe, bow->wpn_bow, staff/wand->wpn_staff (carried head-up; swung head-first in melee)",
        "skilling: chop shows wpn_axe, mine shows wpn_pickaxe, fish shows wpn_rod (replacing the wielded weapon for that anim only)",
        "leather_cowl / leather_body / leather_chaps / goblin_mail: use the matching steel layer tinted 'leather' until bespoke leather layers exist (documented gap)"],
}
meta = {
    "version": 1,
    "look": "Cycles, AgX Medium High Contrast, ortho camera 30 deg elevation; matches assets/npc_hd",
    "px_per_m": {"1x": 43.9, "2x": 87.8, "4x": 175.6},
    "tile_px_1x": 40,
    "canvas": {"1x": [144, 144], "2x": [288, 288], "4x": [576, 576]},
    "feet_px": {"1x": [72, 124], "2x": [144, 248], "4x": [288, 496]},
    "canvas_note": "same px-per-metre, 30 deg camera and feet-anchor convention as assets/npc_hd (NPC 2x canvas 192x256 feet 96,236). The player canvas is wider/taller only so weapon reach, bow, rod and the death fall are not clipped; blit with feet_px exactly like NPCs and the figure lands on the same ground point / tile footprint (1 tile = 40 px at 1x = 0.91 m).",
    "anchors_file": "anchors.json (per sex/anim/facing/frame: head_top, chest, hand_R, hand_L, weapon tip; 2x px, 1x = /2, 4x = x2, w: x' = canvas_w - x)",
    "path": "{sex}/{scale}/{layer}/{anim}_{facing}.png  (+ {anim}_{facing}_tint.png for tintable parts)",
    "strip": "frames laid left->right, each frame = canvas width; 4x holds idle frame 0 only (creator / shop / wardrobe preview)",
    "facings": {"s": "front (game facing 'front')", "e": "game facing 1", "w": "game facing -1 = horizontal flip of e", "n": "back (game facing 'back')"},
    "anims": CAT["anims"],
    "sample_progress": {"melee": [0.0, 0.10, 0.22, 0.34, 0.48, 0.55, 0.62, 0.71, 0.80, 0.91], "ranged": [0.0, 0.12, 0.24, 0.36, 0.48, 0.55, 0.72, 0.86]},
    "combat_sync": {"melee_contact_frame": 4, "melee_contact_progress": 0.48, "client_strike_t_melee": 0.48,
                    "ranged_release_frame": 5, "ranged_release_progress": 0.55, "client_arrow_spawn": 0.55, "client_strike_t_ranged": 0.58,
                    "server_swing_interval_s": 1.2, "attack_anim_s": 1.05, "ranged_anim_s": 0.72, "tick_s": 0.6,
                    "rule": "frame = last index i with sample_progress[i] <= progress, so the contact / release frame is on screen exactly when the client releases the hitsplat / spawns the arrow. Timing values are read from the client; nothing here changes them."},
    "anim_notes": "frames are chosen from the SAME t / progress the 2D code uses (rs_style.resolve_pose inputs). Movement, speed, tile stepping and timing are untouched; HD only swaps the drawing. melee/ranged/chop/mine/fish exist for e only because the 2D game always shows combat & skilling in side profile.",
    "compose": "sort the player's visible layers by z[facing] and blit at (cx - feet_x, cy_feet - feet_y). For a tintable layer blit '<name>.png' then a copy of '<name>_tint.png' multiplied by the colour (hair palette / tier tint).",
    "shadow_layer": "shadow (draw first; same frame index as the body)",
    "body_layers": ["body_light", "body_tan", "body_deep"],
    "always": ["shadow", "body_<skin>", "brows"],
    "fx_swing": {"path": "{sex}/{scale}/fx_swing_{weapon_layer}/melee_e.png", "z": {"e": 91, "w": 91}, "frames": "10, same index as melee; only frame 4 (contact) and 5 (trail) have pixels",
                 "note": "optional additive-looking motion highlight drawn just above the weapon; mirror for w like every e strip. Purely visual."},
    "hair_sway": "long hair, ponytail and braid carry a baked follow-through offset per frame (walk bounce, melee lag/whip, hit snap). Nothing to do at runtime.",
}
json.dump(catalogue, open(f"{OUT}/catalogue.json", "w"), indent=1)
json.dump(meta, open(f"{OUT}/meta.json", "w"), indent=1)
print("meta ok", len(items), len(armour), len(weapons))
