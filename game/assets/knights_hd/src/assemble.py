"""renders/ -> assets/<id>/ (sprite 4x/2x/1x per state/facing, hero, portrait, meta.json) + manifest.json."""
import json, os, glob, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import backdrop

R = "/workspace/knights_hd/renders"; A = "/workspace/knights_hd/assets"; ROOT = "/workspace/knights_hd"
KEYS = ["knight", "shadow_knight", "knight_captain_vorn", "barrow_knight", "sir_aldric", "magma_knight"]
INFO = {
    "knight": dict(name="Castle Knight", level=48, sex="M", region="Stonehaven Keep patrols", boss=False, content_scale=1.0,
                   look="polished Stonehaven steel plate, blue tabard + cape with silver tower heraldry, plumed great helm, longsword + heater shield"),
    "shadow_knight": dict(name="Shadow Knight", level=88, sex="F", region="Void Sanctum", boss=False, content_scale=1.0,
                          look="void-black lacquered plate with violet runes, jagged pauldrons, horned sallet with glowing slit, silver braid, torn cape, serrated void blade + void flame in off hand"),
    "knight_captain_vorn": dict(name="Knight-Captain Vorn", level=92, sex="M", region="Void Sanctum (boss)", boss=True, content_scale=1.2,
                                look="crimson-black captain's plate with blackened-gold trim, spiked pauldrons + neck guards, hounskull helm with red transverse crest and crown spikes, falchion + void-sigil tower shield"),
    "barrow_knight": dict(name="Barrow Knight", level=44, sex="M", region="The Depths", boss=False, content_scale=1.0,
                          look="rusted grave-iron plate with moss and verdigris bronze, open bascinet + mail aventail, gaunt undead face with green eyes, tattered shroud, notched sword + broken round shield"),
    "sir_aldric": dict(name="Sir Aldric the Unquiet", level=52, sex="M", region="The Depths (boss)", boss=True, content_scale=1.3,
                       look="tarnished silver-gilt lord's plate with sun emblem, broken crown on a winged open helm, spectral white beard + ember eyes, faded teal surcoat/cape, spectral ember longsword + battered heater"),
    "magma_knight": dict(name="Magma Knight", level=78, sex="F", region="Emberdeep", boss=False, content_scale=1.0,
                         look="cracked obsidian plate with glowing lava seams, ram-horned helm with molten T-visor, fiery braid, charred skirt with ember hem, obsidian lava-core greatblade + dripping molten fist"),
}
COMBAT = {  # read from server/content.py @ d693040 - unchanged by this pack
    "knight": dict(attack_range=1, side_by_side=False, attack_cooldown=None, aggro_range=0, scale=1.0),
    "shadow_knight": dict(attack_range=1, side_by_side=False, attack_cooldown=None, aggro_range=8, scale=1.0),
    "knight_captain_vorn": dict(attack_range=1, side_by_side=False, attack_cooldown=None, aggro_range=7, scale=1.2, force_retaliate=True),
    "barrow_knight": dict(attack_range=2, side_by_side=True, side_gap=2, attack_cooldown=1.1, aggro_range=6, scale=1.0, force_retaliate=True),
    "sir_aldric": dict(attack_range=2, side_by_side=True, side_gap=2, attack_cooldown=1.1, aggro_range=8, scale=1.3, force_retaliate=True),
    "magma_knight": dict(attack_range=1, side_by_side=False, attack_cooldown=None, aggro_range=8, scale=1.0),
}
ATTACK_FRAME_STARTS = [0.0, 0.14, 0.30, 0.42, 0.60, 0.80]
STATES = {
    "idle": dict(frames=4, loop=True, runtime="frame = int(((t * 1.5) % 1.0) * 4)"),
    "walk": dict(frames=8, loop=True, runtime="frame = int(((t * 1.15) % 1.0) * 8)   # same cadence as the HD player walk"),
    "attack": dict(frames=6, loop=False, frame_starts=ATTACK_FRAME_STARTS, impact_frame=3, impact_progress=0.48,
                   phases={"windup": [0, 1], "strike": [2], "impact": [3], "follow_through": [4], "recovery": [5]},
                   runtime="progress = client._attack_progress(mid) (0..1 over ATTACK_ANIM_SECS=1.05); "
                           "frame = max(i for i, s in enumerate(frame_starts) if progress >= s)  -> f03 spans 0.42-0.60 so the "
                           "hitsplat released at strike_t=0.48 lands on the impact frame"),
    "hit": dict(frames=3, loop=False, duration_s=0.36,
                runtime="start when the queued hitsplat for a player_hits_monster hit (damage>0) on this knight is released "
                        "(event time + 0.48*ATTACK_ANIM_SECS melee / 0.58*RANGED_ANIM_SECS ranged); frame = min(2, int(elapsed/0.12)); "
                        "attack frames win if the knight is mid-swing; keep the red hurt tint on top"),
    "death": dict(frames=6, loop=False, duration_s=0.9, hold_fade_s=0.6,
                  runtime="on DEATH (entity_kind monster) snapshot type/x/y/facing into a client corpse list (the server drops the "
                          "monster from state); frame = min(5, int(elapsed/0.15)); after 0.9 s hold f05 and fade alpha to 0 over 0.6 s"),
}


import numpy as np


def fade_shadow_edges(im, mb=44, ms=34):
    """Feather shadow-catcher pixels (near-black, semi-transparent) toward the canvas edges so no shadow is cut hard."""
    a = np.asarray(im).copy(); h, w = a.shape[:2]
    rgbmax = a[..., :3].max(axis=2); sh = (rgbmax < 14) & (a[..., 3] < 200)
    yy = np.arange(h)[:, None]; xx = np.arange(w)[None, :]
    ramp = np.minimum.reduce([np.clip((h - 1 - yy) / mb, 0, 1) + 0 * xx, np.clip(xx / ms, 0, 1) + 0 * yy,
                              np.clip((w - 1 - xx) / ms, 0, 1) + 0 * yy, np.clip(yy / ms, 0, 1) + 0 * xx])
    a[..., 3] = np.where(sh, (a[..., 3] * ramp).astype(np.uint8), a[..., 3])
    return Image.fromarray(a, "RGBA")


def head_top(im, hx):
    """Topmost opaque pixel near the projected head column (4x px)."""
    a = im.getchannel("A"); w, h = im.size
    x0, x1 = max(0, int(hx) - 70), min(w, int(hx) + 70)
    box = a.crop((x0, 0, x1, h)).point(lambda v: 255 if v > 140 else 0).getbbox()
    return box[1] if box else None


def save(im, p):
    os.makedirs(os.path.dirname(p), exist_ok=True); im.save(p, compress_level=7)


SPR = "sprite_4x_fix"   # corrected-camera renders (true 175.6 px/m, feet at 256,528)


SPR_BY = {"magma_knight": "sprite_4x_fix2"}   # magma v2 materials (brighter obsidian, bronze trim, fewer/larger lava seams)


def one(key):
    global SPR
    SPR = SPR_BY.get(key, "sprite_4x_fix")
    src = f"{R}/{key}"; d = f"{A}/{key}"; os.makedirs(d, exist_ok=True)
    counts = {}
    for st in STATES:
        for f in "senw":
            fs = sorted(glob.glob(f"{src}/{SPR}/{st}/{f}/f*.png"))
            counts[(st, f)] = len(fs)
            for fp in fs:
                o1 = f"{d}/sprite_1x/{st}/{f}/{os.path.basename(fp)}"
                if os.path.exists(o1) and os.path.getmtime(o1) > os.path.getmtime(fp):
                    continue
                im = fade_shadow_edges(Image.open(fp).convert("RGBA")); w, h = im.size
                for tag, sc in (("4x", 1), ("2x", 2), ("1x", 4)):
                    out = im if sc == 1 else im.resize((w // sc, h // sc), Image.LANCZOS)
                    save(out, f"{d}/sprite_{tag}/{st}/{f}/{os.path.basename(fp)}")
    anch = {}
    af = f"{src}/anchors_{SPR}.json"
    if os.path.exists(af):
        raw = json.load(open(af))
        for kk, v in raw.items():
            st, f, n = kk.split("/")
            fp = f"{src}/{SPR}/{st}/{f}/f{n}.png"
            ht = None
            if os.path.exists(fp):
                ht = head_top(Image.open(fp).convert("RGBA"), v["head"][0])
            top = [v["head"][0], float(ht if ht is not None else v["head"][1] - 20)]
            anch[kk] = {"head_top": top, "weapon_tip": v["weapon_tip"], "weapon_hand": v["weapon_hand"]}
    i = INFO[key]
    meta = {"id": key, "name": i["name"], "level": i["level"], "sex": i["sex"], "region": i["region"], "boss": i["boss"], "look": i["look"],
            "content_scale": i["content_scale"],
            "scale_note": "constant 175.6 px per metre at 4x (43.9 at 1x) - same as npc_hd; draw at (TILE/40) x content.py 'scale' (bosses keep 1.2 / 1.3)",
            "canvas": {"1x": [128, 144], "2x": [256, 288], "4x": [512, 576]},
            "feet_px": {"1x": [64, 132], "2x": [128, 264], "4x": [256, 528]},
            "facings": {"s": "front / toward camera", "e": "screen right (game facing 1)", "n": "back / away", "w": "screen left (game facing -1)"},
            "game_facing_map": {"front": "s", "back": "n", "1": "e", "-1": "w"},
            "combat": dict(COMBAT[key], attack_facing="client face_toward_target forces +-1 while swinging -> e/w frames; s/n attack frames exist for completeness"),
            "states": STATES,
            "files": "sprite_{1x,2x,4x}/{idle,walk,attack,hit,death}/{s,e,n,w}/fNN.png",
            "anchors_note": "per-frame pixel anchors in the 4x canvas (divide by 2 for 2x, 4 for 1x). head_top = top of the "
                            "silhouette above the head (health bar / hitsplat), weapon_tip = blade tip (hit point), weapon_hand = sword grip. "
                            "Screen pos = (cx - feet_x + ax) * draw_scale, same as the sprite blit.",
            "shadow": "soft contact shadow baked into every frame (semi-transparent, no dark block)"}
    if os.path.exists(f"{src}/hero.png"):
        im = Image.open(f"{src}/hero.png").convert("RGBA"); save(im, f"{d}/{key}_hero_2048.png")
        backdrop.comp(f"{src}/hero.png", f"{d}/{key}_hero_2048_bg.jpg", 31 + KEYS.index(key), "twilight")
        meta["hero"] = f"{key}_hero_2048.png (+ _bg.jpg)"
    if os.path.exists(f"{src}/portrait_bust.png"):
        p = Image.open(f"{src}/portrait_bust.png").convert("RGBA")
        save(p, f"{d}/portrait_bust.png"); save(p.resize((512, 512), Image.LANCZOS), f"{d}/portrait_bust_512.png")
        backdrop.comp(f"{src}/portrait_bust.png", f"{d}/portrait_bust_bg.jpg", 41 + KEYS.index(key), "twilight")
        meta["portrait"] = "portrait_bust.png (1024, transparent) + portrait_bust_512.png + portrait_bust_bg.jpg"
    if anch:
        meta["anchors_4x"] = anch
        imp = {f: anch.get(f"attack/{f}/03") for f in "senw"}
        meta["hit_point_4x"] = {f: (v or {}).get("weapon_tip") for f, v in imp.items()}
        tops = [v["head_top"][1] for kk, v in anch.items() if kk.startswith("idle/s/")]
        if tops:
            meta["head_top_idle_4x"] = min(tops)
            meta["healthbar_y_offset_1x"] = round((min(tops) - 528) / 4 - 4, 1)
        e = imp.get("e")
        if e:
            meta["impact_reach_tiles"] = round((e["weapon_tip"][0] - 256) / 4 / 40 * i["content_scale"], 2)
    missing = [f"{st}/{f}:{n}/{STATES[st]['frames']}" for (st, f), n in counts.items() if n != STATES[st]["frames"]]
    meta["complete"] = not missing
    json.dump(meta, open(f"{d}/meta.json", "w"), indent=1)
    return key, missing


def manifest():
    m = {"pack": "Mythoscape HD attackable knights", "built": "2026-10-08 (Europe/London)", "target_branch": "main",
         "install_dir": "game/assets/knights_hd/", "monsters": KEYS, "feature_flag": None,
         "feature_flag_policy": "NO feature flags - always on; remove old tint/visual sharing + old knight sprite/procedural code for these ids",
         "start_here": ["KNIGHTS_HD_CURSOR_PROMPT.md", "NOTES_KNIGHTS_HD.md", "previews/knights_hd_contact_sheet.png", "previews/knights_hd_lineup_grey.png"],
         "protect_never_edit": ["pose_walk", "rs_style.py", "rs_humanoid.py", "rs_humanoid_v2.py", "tools/walk_proof.py", "draw_humanoid", "draw_humanoid_detailed"],
         "tile_px": {"1x": 40, "2x": 80, "4x": 160}}
    json.dump(m, open(f"{ROOT}/manifest.json", "w"), indent=1)


if __name__ == "__main__":
    for k in (sys.argv[1:] or KEYS):
        print("assembled", one(k), flush=True)
    manifest()
