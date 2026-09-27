"""castle_post.py - 1x sprites, metadata, concept composites, GIF, before/after.
Run with a Python that has Pillow:  python tools/castle_post.py [--root /workspace/castle]
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = sys.argv[sys.argv.index("--root") + 1] if "--root" in sys.argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = "/home/box/agent-data/agents/da220230-5691-4a53-a42f-eed226c0cf37/attachments/94e62c1ae6e4e8de1d7eb82388a733ea4ee68e10a708348c1053f44e82ad89eb.png"
SHOT_TILE_PX = 47.5         # measured flagstone period in David's screenshot
X0, Y0, NX, NY = 100, 31, 24, 24
TILE = 40
RI = json.load(open(os.path.join(ROOT, "json", "render_info.json")))
S2 = os.path.join(ROOT, "sprites", "2x")
S1 = os.path.join(ROOT, "sprites", "1x")
CON = os.path.join(ROOT, "concepts")
os.makedirs(S1, exist_ok=True)
os.makedirs(os.path.join(S1, "gate"), exist_ok=True)
os.makedirs(CON, exist_ok=True)
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(sz):
    try:
        return ImageFont.truetype(FONT_B, sz)
    except OSError:
        return ImageFont.load_default()


# ------------------------------------------------------------------ layout / walkability
TOWERS = [((2.9, 2.9), 1.6), ((21.1, 2.9), 1.6), ((2.9, 21.1), 1.65), ((21.1, 21.1), 1.65),
          ((2.6, 12.0), 1.3), ((21.4, 12.0), 1.3), ((9.25, 21.35), 1.45), ((14.75, 21.35), 1.45)]


def cell(lx, ly):
    if lx in (11, 12) and ly in (22, 23):
        return "B"
    if lx <= 1 or lx >= 22 or ly <= 1 or ly >= 22:
        return "M"
    if lx in (11, 12) and ly == 21:
        return "G"
    if lx in (11, 12) and ly == 20:
        return "P"
    if ly == 20 and (5 <= lx <= 7 or 16 <= lx <= 18):
        return "A"
    if lx in (2, 3, 20, 21) or ly in (2, 3, 20, 21):
        return "W"
    for (cx, cy), r in TOWERS:
        if math.hypot(lx + 0.5 - cx, ly + 0.5 - cy) <= r + 0.15:
            return "W"
    if 7 <= lx <= 16 and 4 <= ly <= 9:
        return "K"
    return "F"


ROWS = ["".join(cell(lx, ly) for lx in range(NX)) for ly in range(NY)]
LEGEND = {
    "M": {"what": "moat water", "walk": "never", "server_tile": "WATER"},
    "B": {"what": "drawbridge deck", "walk": "when gate open (visual); server keeps it walkable", "server_tile": "PATH"},
    "G": {"what": "portcullis tile (door tile of castle_gate / castle_gate_e)", "walk": "blocked until open (client pathing); server keeps it walkable", "server_tile": "PATH"},
    "P": {"what": "gate passage (under the gatehouse)", "walk": "always", "server_tile": "FLOOR"},
    "A": {"what": "south wall-walk (NPCs drawn lifted onto the wall top)", "walk": "always", "server_tile": "FLOOR"},
    "W": {"what": "curtain wall / tower", "walk": "never", "server_tile": "WALL"},
    "K": {"what": "central keep block", "walk": "never", "server_tile": "WALL"},
    "F": {"what": "inner bailey / keep floor (the old interior, shifted +3,-2)", "walk": "always", "server_tile": "FLOOR"},
}

INTERIOR_SHIFT = (3, -2)
OLD_SPOTS = {
    "castle_throne": (110, 45), "castle_rug": (110, 48), "castle_table": (106, 48), "castle_chair_a": (105, 48),
    "castle_chair_b": (107, 48), "castle_banner_w": (104, 45), "castle_banner_e": (116, 45),
    "castle_rack": (103, 50), "castle_chest": (115, 50), "castle_brazier_w": (103, 46),
    "castle_brazier_e": (115, 46), "castle_candle": (108, 46),
}
WALK_LIFT_PX = 118     # at TILE 40: feet of wall-walk entities drawn this much higher than their tile centre


def local(x, y):
    return x - X0, y - Y0


def check_walk(x, y):
    lx, ly = local(x, y)
    return ROWS[ly][lx] in "FAPBG"


NPC_SPOTS = [
    {"id": "herald_rowan", "kind": "npc", "old": [110, 47], "new": [107, 51], "where": "south wall-walk, west of the gatehouse (drawn lifted)", "lift_px": WALK_LIFT_PX},
    {"id": "quest_herald_rowan", "kind": "place label", "old": [110, 47], "new": [107, 51], "where": "follows Herald Rowan"},
    {"id": "mythos_champion", "kind": "monster spawn + place", "old": [110, 48], "new": [113, 46], "where": "inner bailey in front of the keep (quest text says courtyard)", "alt": [117, 51]},
    {"id": "knight#1", "kind": "monster spawn", "old": [108, 50], "new": [111, 48], "where": "bailey, inside the gate"},
    {"id": "knight#2", "kind": "monster spawn", "old": [112, 48], "new": [115, 46], "where": "bailey"},
    {"id": "knight#3", "kind": "monster spawn", "old": [106, 46], "new": [109, 44], "where": "bailey"},
    {"id": "knight#4", "kind": "monster spawn", "old": [110, 52], "new": [109, 55], "where": "gate guard, west of the bridge on the apron (outside)"},
    {"id": "knight#5", "kind": "monster spawn", "old": [114, 50], "new": [114, 55], "where": "gate guard, east of the bridge on the apron (outside)"},
    {"id": "knights (place)", "kind": "place label", "old": [108, 50], "new": [111, 48]},
    {"id": "stonehaven_castle (place)", "kind": "place label", "old": [108, 50], "new": [111, 45]},
    {"id": "wall_walk_extra_w", "kind": "optional ambient spot", "new": [105, 51], "lift_px": WALK_LIFT_PX},
    {"id": "wall_walk_extra_e", "kind": "optional ambient spot", "new": [117, 51], "lift_px": WALK_LIFT_PX},
]
for s in NPC_SPOTS:
    x, y = s["new"]
    if not (X0 <= x < X0 + NX and Y0 <= y < Y0 + NY + 2):
        raise SystemExit(f"spot outside footprint {s}")
    if y < Y0 + NY:
        assert check_walk(x, y), s
for k, (x, y) in OLD_SPOTS.items():
    assert check_walk(x + INTERIOR_SHIFT[0], y + INTERIOR_SHIFT[1]), k

# ------------------------------------------------------------------ 1x sprites
def half(src, dst):
    im = Image.open(src).convert("RGBA")
    im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(dst, optimize=True)
    return im.size


LAYERS = ["castle_ground", "castle_back", "castle_posts", "castle_front", "castle_cutaway"]
for n in LAYERS:
    half(os.path.join(S2, n + ".png"), os.path.join(S1, n + ".png"))
NF = len(RI["frames"])
for f in range(NF):
    half(os.path.join(S2, "gate", f"gate_{f:02d}.png"), os.path.join(S1, "gate", f"gate_{f:02d}.png"))
half(os.path.join(S2, "player_ref_1p8m.png"), os.path.join(S1, "player_ref_1p8m.png"))

W2, H2 = RI["size_2x"]
O2 = RI["origin_2x"]
gc2 = RI["gate_crop_2x"]
meta = {
    "id": "stonehaven_castle", "version": 2, "flag": "USE_NEW_CASTLE",
    "title": "Stonehaven Castle Keep v2 (moat, drawbridge, portcullis)",
    "footprint": {"x0": X0, "y0": Y0, "x1": X0 + NX - 1, "y1": Y0 + NY - 1, "w": NX, "h": NY,
                  "note": "includes the moat ring; old footprint was x100-118 y42-54 (19x13 = 247 tiles) -> 24x24 = 576 tiles (2.33x)"},
    "building_entry": {"id": "stonehaven_castle", "name": "Castle Keep", "kind": "castle", "style": 1, "material": "brick",
                       "x0": 100, "y0": 31, "x1": 123, "y1": 54,
                       "floor_x0": 104, "floor_y0": 35, "floor_x1": 119, "floor_y1": 51},
    "tile_px": TILE,
    "sprite_1x": {"size": [W2 // 2, H2 // 2], "origin_px": [O2[0] // 2, O2[1] // 2]},
    "sprite_2x": {"size": [W2, H2], "origin_px": O2},
    "anchor_note": "origin_px = pixel of the NW corner of world tile (x0,y0) inside every full-size layer. "
                   "Blit layer at (tile_screen_x(x0) - origin_px.x*TILE/40, tile_screen_y(y0) - origin_px.y*TILE/40), scaled by TILE/40. "
                   "Ground rows are exactly TILE px apart (tile-locked 3/4 projection), so tile (x,y) of the footprint sits at origin + ((x-x0)*TILE, (y-y0)*TILE).",
    "sprite_tiles": RI["tiles"],
    "layers": [
        {"name": "ground", "file": "castle_ground.png", "order": "after floor tiles, before any entity", "contains": "moat water (soft glow), banks, reeds, rocks, lilies, bridge abutment, apron lip"},
        {"name": "back", "file": "castle_back.png", "order": "in the entity pass: after entities with y < y0 (north of the castle), before entities with y >= y0", "contains": "walls, 8 towers, keep, gatehouse, bailey"},
        {"name": "gate", "file": "gate/gate_NN.png", "order": "immediately after back", "crop_1x": [c // 2 for c in gc2], "crop_2x": gc2,
         "note": "gate frames are cropped: blit at origin-relative offset crop[0..1] of the full layer"},
        {"name": "posts", "file": "castle_posts.png", "order": "y-sorted like an entity standing on world row 54 (after entities with y <= 54, before y >= 55)", "contains": "bridge abutment pillars + braziers"},
        {"name": "front", "file": "castle_front.png", "order": "after all entities", "contains": "south curtain parapets (wall-walk NPCs stand behind them)"},
        {"name": "cutaway", "file": "castle_cutaway.png", "order": "replaces back+front while the player is inside (floor rect or door tile); ground+gate+posts still drawn",
         "contains": "walls/towers/keep cut at 1.6 m so the interior tiles + interior spots show"},
    ],
    "gate": {
        "frames": [{"file": f"gate/gate_{f['frame']:02d}.png", "ms": f["ms"], "bridge_deg": f["bridge_deg"], "portcullis_up_m": round(f["portcullis_z_m"], 2)} for f in RI["frames"]],
        "sequence_open": "frames 0 -> 11 (0 = closed: bridge up, portcullis down; 1-6 bridge lowers; 7-11 portcullis rises)",
        "sequence_close": "frames 11 -> 0 (portcullis drops first, then the bridge rises), same per-frame ms",
        "parts_separable": "bridge (frames 0-6) and portcullis (frames 6-11) never move at the same time, so a split two-stage version is just two index ranges",
        "close_delay_ms": 1500, "open_ms_total": sum(f["ms"] for f in RI["frames"]),
    },
    "walkability": {"origin": [X0, Y0], "rows": ROWS, "legend": LEGEND,
                    "server_rule": "server grid: M->WATER, W/K->WALL, F/A/P->FLOOR, B/G->PATH (always walkable server-side, the server has no door logic)",
                    "client_rule": "optional: while the gate is not fully open, client pathing treats B and G as blocked (the trigger opens it long before the player arrives)"},
    "trigger_tiles": {
        "outer": [[x, 55] for x in range(110, 114)],
        "hold": [[x, y] for y in range(51, 55) for x in (111, 112)],
        "inner": [[x, y] for y in (49, 50) for x in (111, 112)],
        "rule": "gate opens while the LOCAL player stands on any outer/inner/hold tile; closes close_delay_ms after they are on none of them",
    },
    "doors": {
        "castle_gate": {"x": 111, "y": 52, "enter": [111, 50], "exit": [111, 55], "old": {"x": 108, "y": 54, "enter": [108, 52], "exit": [108, 56]}},
        "castle_gate_e": {"x": 112, "y": 52, "enter": [112, 50], "exit": [112, 55], "old": {"x": 109, "y": 54, "enter": [109, 52], "exit": [109, 56]}},
    },
    "interior_shift": {"dx": INTERIOR_SHIFT[0], "dy": INTERIOR_SHIFT[1],
                       "applies_to": "every castle interior spot, knights, champion (keeps the old interior layout intact)",
                       "spots_new": {k: [x + INTERIOR_SHIFT[0], y + INTERIOR_SHIFT[1]] for k, (x, y) in OLD_SPOTS.items()}},
    "npc_spots": NPC_SPOTS,
    "walkway_draw_lift_px": WALK_LIFT_PX,
    "camera": {"type": "orthographic", "azimuth_deg": 0, "elevation_deg": 32, "sun_rotation_deg": [40, 15, -30],
               "tile_locked": "scene Y pre-scaled by 1/sin(32) for the sprite renders so ground rows land exactly on the 40 px grid; heights project by cos(32)",
               "px_per_m_1x": 26.9, "tile_m": round(40 / 26.9, 3)},
    "triangles": {"per_part": RI["tris"], "total": RI["tris_total"]},
    "models": {"blend": "models/stonehaven_castle_v2.blend", "glb": "models/stonehaven_castle_v2.glb", "bam": "models/stonehaven_castle_v2.bam",
               "gate_nodes": ["castle_bridge", "castle_portcullis", "castle_chain_l", "castle_chain_r"],
               "animation": "glb/blend action 'gate_open_*' frames 1-12 @10 fps; bam: static + separable nodes, drive them from gate.frames[*] (json/render_info.json has the per-frame matrices)"},
}
# prop_loader meta (find_meta looks for json/<model key>.json): emissive glow + tris
with open(os.path.join(ROOT, "json", "stonehaven_castle_v2.json"), "w") as fh:
    json.dump({"key": "stonehaven_castle_v2", "title": meta["title"], "triangles": RI["tris_total"],
               "emissive": {"water": 0.45, "water_hi": 0.6, "fire": 6.0, "fire_core": 8.0, "ember": 3.0,
                            "window": 2.2, "candle": 6.0},
               "front": "-Y", "up": "+Z", "units": "metres", "colliders": [], "interact": None,
               "note": "COL_*/TRIGGER_* boxes live in the COLLISION collection of the .blend -> CollisionNodes in the .bam"}, fh, indent=1)
for d in (os.path.join(ROOT, "json"), os.path.join(ROOT, "sprites")):
    with open(os.path.join(d, "castle_v2.json"), "w") as fh:
        json.dump(meta, fh, indent=1)

# ------------------------------------------------------------------ composites
rng = random.Random(4)


def flag_bg(w_t, h_t, grass_rows=None):
    """Grey flagstone tile grid like the game (40 px)."""
    im = Image.new("RGBA", (w_t * TILE, h_t * TILE), (120, 120, 124, 255))
    d = ImageDraw.Draw(im)
    for ty in range(h_t):
        for tx in range(w_t):
            x, y = tx * TILE, ty * TILE
            if grass_rows and ty in grass_rows:
                g = rng.randint(-6, 6)
                d.rectangle([x, y, x + TILE - 1, y + TILE - 1], fill=(92 + g, 118 + g, 62 + g, 255))
                continue
            b = rng.randint(-8, 8)
            d.rectangle([x, y, x + TILE - 1, y + TILE - 1], fill=(126 + b, 126 + b, 130 + b, 255))
            d.rectangle([x, y, x + TILE - 1, y + TILE - 1], outline=(88, 88, 92, 255))
            if rng.random() < 0.5:
                d.line([x + TILE // 2, y + 2, x + TILE // 2, y + TILE - 3], fill=(100, 100, 104, 255))
            else:
                d.line([x + 2, y + TILE // 2, x + TILE - 3, y + TILE // 2], fill=(100, 100, 104, 255))
    return im


PLAYER = Image.open(os.path.join(S1, "player_ref_1p8m.png")).convert("RGBA")
PFEET = (RI["player_ref_2x"]["feet_px"][0] / 2, RI["player_ref_2x"]["feet_px"][1] / 2)


def recolour(im, rgb):
    px = im.load()
    out = im.copy()
    po = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and r > g + 25 and r > b + 25 and r > 60:     # shirt pixels
                f = r / 160
                po[x, y] = (min(255, int(rgb[0] * f)), min(255, int(rgb[1] * f)), min(255, int(rgb[2] * f)), a)
    return out


FIGS = {"player": PLAYER, "knight": recolour(PLAYER, (175, 180, 188)), "herald": recolour(PLAYER, (70, 110, 190)),
        "champion": recolour(PLAYER, (190, 40, 40))}


def label(d, cx, y, text, col=(255, 255, 255), sz=11):
    f = font(sz)
    tw = d.textlength(text, font=f)
    d.rectangle([cx - tw / 2 - 4, y - 2, cx + tw / 2 + 4, y + sz + 3], fill=(20, 18, 16, 215))
    d.text((cx - tw / 2, y), text, fill=col, font=f)


def compose(frame, ents, canvas_tiles=None, bg_grass=True, scale=1, labels=True, cutaway=False):
    """Return (image, (ox, oy)) with the castle composited on a tile background at 1x.
    ents: list of (kind, x, y, name, lifted)."""
    L, R, TOP, BOT = RI["tiles"]["left"], RI["tiles"]["right"], RI["tiles"]["top"], RI["tiles"]["bottom"]
    margin = 2
    w_t = (R - L) + 2 * margin
    h_t = (TOP - BOT) + 2 * margin
    grass = set(range(0, margin + TOP)) if bg_grass else None
    bg = flag_bg(w_t, h_t, grass)
    ox = (margin - L) * TILE          # px of world tile x0 left edge
    oy = (margin + TOP) * TILE        # px of world tile y0 top edge
    lay = {n: Image.open(os.path.join(S1, n + ".png")).convert("RGBA") for n in LAYERS}
    o1 = (O2[0] // 2, O2[1] // 2)
    at = (ox - o1[0], oy - o1[1])
    bg.alpha_composite(lay["castle_ground"], at)
    bg.alpha_composite(lay["castle_cutaway" if cutaway else "castle_back"], at)
    g = Image.open(os.path.join(S1, "gate", f"gate_{frame:02d}.png")).convert("RGBA")
    bg.alpha_composite(g, (at[0] + gc2[0] // 2, at[1] + gc2[1] // 2))
    d = ImageDraw.Draw(bg)
    ents = sorted(ents, key=lambda e: e[2])
    posts_done = False
    for kind, x, y, name, lifted in ents:
        if y >= 55 and not posts_done:
            bg.alpha_composite(lay["castle_posts"], at)
            posts_done = True
        fig = FIGS[kind]
        fx = ox + (x - X0) * TILE + TILE // 2 - PFEET[0]
        fy = oy + (y - Y0) * TILE + TILE // 2 - PFEET[1] - (WALK_LIFT_PX if lifted else 0)
        bg.alpha_composite(fig, (int(fx), int(fy)))
    if not posts_done:
        bg.alpha_composite(lay["castle_posts"], at)
    if not cutaway:
        bg.alpha_composite(lay["castle_front"], at)
    d = ImageDraw.Draw(bg)
    if labels:
        for kind, x, y, name, lifted in ents:
            if not name:
                continue
            cx = ox + (x - X0) * TILE + TILE // 2
            ty = oy + (y - Y0) * TILE + TILE // 2 - PFEET[1] - (WALK_LIFT_PX if lifted else 0) - 16
            label(d, cx, ty, name, (120, 230, 120) if kind == "knight" else (255, 255, 255))
    return bg, (ox, oy)


ENT_BASE = [("herald", 107, 51, "Herald Rowan", True), ("knight", 109, 55, "Castle Knight", False),
            ("knight", 114, 55, "Castle Knight", False), ("knight", 117, 51, "", True)]
closed, (ox, oy) = compose(0, ENT_BASE + [("player", 111, 58, "You", False)])
closed.convert("RGB").save(os.path.join(CON, "castle_closed_game_1x.png"))
openi, _ = compose(NF - 1, ENT_BASE + [("player", 111, 55, "You (on trigger)", False)])
openi.convert("RGB").save(os.path.join(CON, "castle_open_game_1x.png"))
cut, _ = compose(NF - 1, [("player", 112, 47, "You (inside)", False)], cutaway=True)
cut.convert("RGB").save(os.path.join(CON, "castle_inside_cutaway_1x.png"))


def overlay_grid(img, ox, oy):
    """Walkability overlay (debug concept)."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cols = {"M": (40, 120, 255, 90), "B": (255, 200, 0, 120), "G": (255, 60, 60, 140), "P": (0, 255, 120, 70),
            "A": (255, 0, 255, 110), "W": (0, 0, 0, 70), "K": (0, 0, 0, 110), "F": (0, 255, 0, 35)}
    for ly, row in enumerate(ROWS):
        for lx, c in enumerate(row):
            x, y = ox + lx * TILE, oy + ly * TILE
            d.rectangle([x, y, x + TILE - 1, y + TILE - 1], fill=cols[c], outline=(255, 255, 255, 40))
    for (x, y) in meta["trigger_tiles"]["outer"] + meta["trigger_tiles"]["inner"]:
        xx, yy = ox + (x - X0) * TILE, oy + (y - Y0) * TILE
        d.rectangle([xx + 3, yy + 3, xx + TILE - 4, yy + TILE - 4], outline=(255, 255, 0, 255), width=3)
    ox0, oy0 = ox + (100 - X0) * TILE, oy + (42 - Y0) * TILE
    d.rectangle([ox0, oy0, ox0 + 19 * TILE, oy0 + 13 * TILE], outline=(255, 255, 255, 255), width=3)
    out = img.copy()
    out.alpha_composite(ov)
    dd = ImageDraw.Draw(out)
    dd.text((ox0 + 6, oy0 + 6), "old footprint 19x13", fill=(255, 255, 255), font=font(14))
    return out


flat = compose(NF - 1, [], labels=False, cutaway=True)[0]
overlay_grid(flat, ox, oy).convert("RGB").save(os.path.join(CON, "castle_walkability_overlay.png"))

# ------------------------------------------------------------------ before / after
shot = Image.open(SHOT).convert("RGBA")
sc = TILE / SHOT_TILE_PX
shot_s = shot.resize((int(shot.width * sc), int(shot.height * sc)), Image.LANCZOS)
after = openi
H = max(after.height, shot_s.height) + 90
W = shot_s.width + after.width + 60
ba = Image.new("RGB", (W, H), (34, 32, 30))
ba.paste(shot_s.convert("RGB"), (20, 70))
ba.paste(after.convert("RGB"), (shot_s.width + 40, 70))
d = ImageDraw.Draw(ba)
d.text((20, 18), "BEFORE - current Castle Keep (screenshot rescaled to 40 px tiles)", fill=(240, 230, 210), font=font(18))
d.text((20, 44), "footprint 19 x 13 tiles", fill=(200, 190, 170), font=font(14))
d.text((shot_s.width + 40, 18), "AFTER - v2 with moat, drawbridge + portcullis (same 40 px scale, gate open)", fill=(240, 230, 210), font=font(18))
d.text((shot_s.width + 40, 44), "footprint 24 x 24 tiles incl. moat (2.3x area)  |  red figure = 1.8 m player", fill=(200, 190, 170), font=font(14))
# player at the same scale beside the old screenshot
pf = FIGS["player"]
ba.paste(pf.convert("RGB"), (20 + shot_s.width - pf.width - 10, 70 + shot_s.height + 5), pf)
ba.save(os.path.join(CON, "before_after_game_scale.png"))
# a tighter before/after: same-height crops of the gate fronts
crop_after = openi.crop((ox - 1 * TILE, oy + 12 * TILE, ox + 25 * TILE, oy + 27 * TILE))
hh = max(crop_after.height, shot_s.height)
ba2 = Image.new("RGB", (shot_s.width + crop_after.width + 60, hh + 80), (34, 32, 30))
ba2.paste(shot_s.convert("RGB"), (20, 60))
ba2.paste(crop_after.convert("RGB"), (shot_s.width + 40, 60))
d = ImageDraw.Draw(ba2)
d.text((20, 16), "BEFORE (screenshot @40 px tiles)", fill=(240, 230, 210), font=font(18))
d.text((shot_s.width + 40, 16), "AFTER - south front of v2 at the same scale", fill=(240, 230, 210), font=font(18))
ba2.save(os.path.join(CON, "before_after_front_closeup.png"))

# ------------------------------------------------------------------ GIF (2x crop around the gate)
def gif():
    frames, durs = [], []
    lay2 = {n: Image.open(os.path.join(S2, n + ".png")).convert("RGBA") for n in LAYERS}
    P2 = Image.open(os.path.join(S2, "player_ref_1p8m.png")).convert("RGBA")
    pfe = RI["player_ref_2x"]["feet_px"]
    T2 = 80
    # crop window in world tiles: x 105..119, y 44..58
    wx0, wy0, wx1, wy1 = 105, 45, 119, 58
    bgw = flag_bg((wx1 - wx0), (wy1 - wy0) + 12).resize(((wx1 - wx0) * T2, ((wy1 - wy0) + 12) * T2), Image.NEAREST)
    # full-res castle placed so world tile (wx0, wy0-12) is at 0,0
    base_ox = (X0 - wx0) * T2
    base_oy = (Y0 - (wy0 - 12)) * T2
    at = (base_ox - O2[0], base_oy - O2[1])

    def draw(frame, px, py, inside=False):
        im = bgw.copy()
        im.alpha_composite(lay2["castle_ground"], at)
        im.alpha_composite(lay2["castle_back"], at)
        g = Image.open(os.path.join(S2, "gate", f"gate_{frame:02d}.png")).convert("RGBA")
        im.alpha_composite(g, (at[0] + gc2[0], at[1] + gc2[1]))
        order = []
        if px is not None:
            order.append((py, px))
        drawn_posts = False
        for yy, xx in sorted(order):
            if yy >= 55 and not drawn_posts:
                im.alpha_composite(lay2["castle_posts"], at); drawn_posts = True
            fx = base_ox + (xx - X0) * T2 + T2 // 2 - pfe[0]
            fy = base_oy + (yy - Y0) * T2 + T2 // 2 - pfe[1]
            im.alpha_composite(P2, (int(fx), int(fy)))
        if not drawn_posts:
            im.alpha_composite(lay2["castle_posts"], at)
        im.alpha_composite(lay2["castle_front"], at)
        c = im.crop((0, 12 * T2 - 8 * T2, (wx1 - wx0) * T2, im.height - 2 * T2))
        c = c.resize((c.width // 2, c.height // 2), Image.LANCZOS)
        dd = ImageDraw.Draw(c)
        onT = (px, py) in [tuple(t) for t in meta["trigger_tiles"]["outer"] + meta["trigger_tiles"]["hold"] + meta["trigger_tiles"]["inner"]]
        label(dd, c.width // 2, 8, f"gate frame {frame:02d}  |  player {'ON' if onT else 'off'} trigger", sz=14)
        return c.convert("RGB")
    walk_in = [(111.0, 60), (111.0, 59), (111.0, 58), (111.0, 57), (111.0, 56)]
    for (x, y) in walk_in:
        frames.append(draw(0, x, y)); durs.append(260)
    frames.append(draw(0, 111, 55)); durs.append(200)
    for f in range(NF):
        frames.append(draw(f, 111, 55)); durs.append(RI["frames"][f]["ms"])
    for y in (54, 53, 52):
        frames.append(draw(NF - 1, 111, y)); durs.append(260)
    frames.append(draw(NF - 1, 111, 51)); durs.append(400)
    # walk back out, then close after the delay
    for y in (52, 53, 54, 55, 56, 57):
        frames.append(draw(NF - 1, 111, y)); durs.append(240)
    frames.append(draw(NF - 1, 111, 58)); durs.append(1500)
    for f in range(NF - 1, -1, -1):
        frames.append(draw(f, 111, 58)); durs.append(RI["frames"][f]["ms"])
    frames.append(draw(0, 111, 58)); durs.append(900)
    pal = [fr.quantize(colors=200, method=Image.MEDIANCUT, dither=Image.NONE) for fr in frames]
    pal[0].save(os.path.join(CON, "gate_open_close.gif"), save_all=True, append_images=pal[1:], duration=durs, loop=0, optimize=True)
    # frame strip
    strip_imgs = [Image.open(os.path.join(S1, "gate", f"gate_{f:02d}.png")).convert("RGBA") for f in range(NF)]
    gw, gh = strip_imgs[0].size
    cols = 6
    sheet = Image.new("RGB", (cols * (gw + 10) + 10, 2 * (gh + 34) + 10), (40, 38, 36))
    bgf = flag_bg(gw // TILE + 2, gh // TILE + 2)
    back1 = Image.open(os.path.join(S1, "castle_back.png")).convert("RGBA")
    gnd1 = Image.open(os.path.join(S1, "castle_ground.png")).convert("RGBA")
    for i, im in enumerate(strip_imgs):
        cx0, cy0 = gc2[0] // 2, gc2[1] // 2
        tile = bgf.crop((0, 0, gw, gh))
        tile.alpha_composite(gnd1.crop((cx0, cy0, cx0 + gw, cy0 + gh)))
        tile.alpha_composite(back1.crop((cx0, cy0, cx0 + gw, cy0 + gh)))
        tile.alpha_composite(im)
        x = 10 + (i % cols) * (gw + 10)
        y = 10 + (i // cols) * (gh + 34)
        sheet.paste(tile.convert("RGB"), (x, y + 24))
        ImageDraw.Draw(sheet).text((x, y + 4), f"frame {i:02d}  {RI['frames'][i]['ms']} ms", fill=(230, 220, 200), font=font(13))
    sheet.save(os.path.join(CON, "gate_frames_sheet.png"))


gif()
print("post done", meta["sprite_1x"], "tris", RI["tris_total"])
