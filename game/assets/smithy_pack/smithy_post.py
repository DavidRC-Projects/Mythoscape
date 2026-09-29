"""smithy_post.py - 1x sprites, meta JSON (buildings-pack format + fx frames), game view, before/after, GIF."""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
KEY = "smithy"
X0, Y0, W, D, DX = 78, 4, 17, 15, 8
FLOOR = (79, 5, 93, 17)
DOOR = {"id": "smithy_door", "x": 86, "y": 18, "enter": [86, 16], "exit": [86, 19]}
OLD = "/home/box/agent-data/agents/da220230-5691-4a53-a42f-eed226c0cf37/attachments/b7cb7b9d2a9254b131ee49c1698363bc58f8ec6dad441d70e7ba4cb6417b8fd7.png"
PLAYER = "/workspace/castle/sprites/1x/player_ref_1p8m.png"
BG = (94, 122, 60)
SCREEN_PPT = 47.5
LAYERS = ["ground", "body", "cutaway", "body_glow0", "body_glow1", "body_glow2", "smoke0", "smoke1", "smoke2", "smoke3"]


def font(sz):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", sz)


def main():
    ri = json.load(open(os.path.join(ROOT, "json", "render", KEY + ".json")))
    d1 = os.path.join(ROOT, "sprites", "1x", KEY); os.makedirs(d1, exist_ok=True)
    for l in LAYERS:
        im = Image.open(os.path.join(ROOT, "sprites", "2x", KEY, l + ".png")).convert("RGBA")
        if l.startswith("smoke"):
            a = im.getchannel("A").point(lambda v: int(v * 0.85)); im.putalpha(a)
            im.save(os.path.join(ROOT, "sprites", "2x", KEY, l + ".png"), optimize=True)
        im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(os.path.join(d1, l + ".png"), optimize=True)
    rows = []
    for ly in range(D):
        r = ""
        for lx in range(W):
            x, y = X0 + lx, Y0 + ly
            if FLOOR[0] <= x <= FLOOR[2] and FLOOR[1] <= y <= FLOOR[3]:
                r += "F"
            elif abs(x - DOOR["x"]) <= 1 and y > FLOOR[3]:
                r += "D"
            elif y == Y0 and X0 < x < X0 + W - 1:
                r += "G"
            elif y > FLOOR[3]:
                r += "P"
            else:
                r += "W"
        rows.append(r)
    x1, y1 = X0 + W - 1, Y0 + D - 1
    meta = {
        "key": KEY, "building_id": "smithy", "name": "Gareth's Smithy", "flag": "USE_NEW_BUILDINGS", "version": 2,
        "footprint": {"x0": X0, "y0": Y0, "x1": x1, "y1": y1, "w": W, "h": D},
        "floor": {"floor_x0": FLOOR[0], "floor_y0": FLOOR[1], "floor_x1": FLOOR[2], "floor_y1": FLOOR[3]},
        "old": {"x0": X0, "y0": Y0, "x1": x1, "y1": y1, "floor_x0": FLOOR[0], "floor_y0": FLOOR[1],
                "floor_x1": FLOOR[2], "floor_y1": FLOOR[3]},
        "footprint_unchanged": True,
        "door": {"id": DOOR["id"], "x": DOOR["x"], "y": DOOR["y"], "enter": DOOR["enter"], "exit": DOOR["exit"],
                 "unchanged": True, "doorway_path_tiles": [[DOOR["x"] + dx_, y1] for dx_ in (-1, 0, 1)], "door_gap_width": 3},
        "tile_px": 40,
        "sprite_1x": {"size": [ri["size_2x"][0] // 2, ri["size_2x"][1] // 2], "origin_px": [ri["origin_2x"][0] / 2, ri["origin_2x"][1] / 2]},
        "sprite_2x": {"size": ri["size_2x"], "origin_px": ri["origin_2x"]},
        "anchor_note": "origin_px = pixel of the NW corner of world tile (x0,y0) in every layer. Blit at "
                       "(tile_screen_x(x0) - origin_px.x*TILE/40, tile_screen_y(y0) - origin_px.y*TILE/40), scaled by TILE/40.",
        "layers": [
            {"name": "ground", "file": f"{KEY}/ground.png", "order": "after floor tiles, before entities (cobble apron, yard floor, soot under the lean-to)"},
            {"name": "body", "file": f"{KEY}/body.png", "order": f"y-sorted like an entity standing on world row {y1}: after entities with y <= {y1}, before entities with y > {y1}"},
            {"name": "cutaway", "file": f"{KEY}/cutaway.png", "order": "replaces body while the local player is inside (floor rect or doorway tiles); walls cut at 1.6 m"},
        ],
        "fx": {
            "optional": True,
            "glow": {"files": [f"{KEY}/body_glow{i}.png" for i in range(3)], "sequence": [0, 1, 2, 1], "fps": 4,
                     "note": "drop-in replacements for body.png (forge coals, windows and forge light pulse). body.png == body_glow1 look. Same size/origin."},
            "smoke": {"files": [f"{KEY}/smoke{i}.png" for i in range(4)], "sequence": [0, 1, 2, 3], "fps": 5,
                      "order": "draw right after body (outside view only; skip with cutaway). Already masked behind the chimney. Same size/origin."},
        },
        "walkability": {"origin": [X0, Y0], "rows": rows,
                        "legend": {"W": "WALL (walls/roof mass)", "F": "FLOOR (interior)", "D": "PATH 3-wide south door gap (85-87,18) as stamped by _punch_south_door",
                                   "G": "GRASS walkable strip behind the building (north row, unchanged)",
                                   "P": "WALL south wall row (props stand here)"},
                        "note": "identical to today's _building(78, 4, 94, 18, door_x=86) stamp: no collision change"},
        "entity_moves": {},
        "camera": {"type": "ortho", "azimuth_deg": 0, "elevation_deg": 32, "y_prestretch": "1/sin(32)", "sun_euler_deg": [40, 15, -30]},
        "triangles": ri["tris"], "tris_total": ri["tris_total"],
        "models": {"blend": f"models/{KEY}.blend", "glb": f"models/{KEY}.glb"},
    }
    os.makedirs(os.path.join(ROOT, "json"), exist_ok=True)
    json.dump(meta, open(os.path.join(ROOT, "json", KEY + ".json"), "w"), indent=1)
    json.dump(meta, open(os.path.join(d1, "meta.json"), "w"), indent=1)

    ox, oy = ri["origin_2x"][0] / 2, ri["origin_2x"][1] / 2

    def comp(layers, grid=True, player=True):
        ims = [Image.open(os.path.join(d1, l + ".png")).convert("RGBA") for l in layers]
        w, h = ims[0].size
        bg = Image.new("RGBA", (w, h), BG + (255,))
        dr = ImageDraw.Draw(bg)
        if grid:
            c = tuple(v - 14 for v in BG) + (255,)
            x = ox % 40
            while x < w:
                dr.line([(x, 0), (x, h)], fill=c); x += 40
            y = oy % 40
            while y < h:
                dr.line([(0, y), (w, y)], fill=c); y += 40
        for im in ims:
            bg.alpha_composite(im)
        if player and os.path.exists(PLAYER):
            p = Image.open(PLAYER).convert("RGBA")
            fx, fy = ox + (DX + 0.5) * 40, oy + (D + 0.6) * 40
            bg.alpha_composite(p, (int(fx - p.width / 2), int(fy - p.height + 6)))
        return bg

    cd = os.path.join(ROOT, "concepts"); os.makedirs(cd, exist_ok=True)
    g = comp(["ground", "body", "smoke1"]).convert("RGB"); g.save(os.path.join(cd, "smithy_game_1x.png"))
    comp(["ground", "cutaway"]).convert("RGB").save(os.path.join(cd, "smithy_inside_1x.png"))
    # walkability overlay
    ov = comp(["ground", "body", "smoke1"], player=False)
    dr = ImageDraw.Draw(ov, "RGBA")
    colr = {"G": (255, 255, 255, 50), "W": (220, 40, 40, 70), "F": (40, 200, 60, 60), "D": (40, 120, 255, 120), "P": (240, 180, 30, 80)}
    for ly, r in enumerate(rows):
        for lx, ch in enumerate(r):
            x, y = ox + lx * 40, oy + ly * 40
            dr.rectangle([x + 1, y + 1, x + 39, y + 39], fill=colr[ch])
    ov.convert("RGB").save(os.path.join(cd, "smithy_walkability_1x.png"))
    # animated preview
    frames = []
    for i in range(8):
        f = comp(["ground", f"body_glow{[0, 1, 2, 1][i % 4]}", f"smoke{i % 4}"], grid=False)
        frames.append(f.convert("RGB").resize((f.width // 2, f.height // 2), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE))
    frames[0].save(os.path.join(cd, "smithy_fx_preview.gif"), save_all=True, append_images=frames[1:], duration=200, loop=0)
    # before / after
    old = Image.open(OLD).convert("RGB")
    new = comp(["ground", "body", "smoke1"], grid=False).convert("RGB")
    s = SCREEN_PPT / 40
    new = new.resize((int(new.width * s), int(new.height * s)), Image.LANCZOS)
    hero = Image.open(os.path.join(cd, "hero", KEY + ".png")).convert("RGB")
    H = max(old.height, new.height)
    hero = hero.resize((int(hero.width * H / hero.height * 0.62), int(H * 0.62)), Image.LANCZOS)
    cell = Image.new("RGB", (old.width + new.width + hero.width + 40, H + 70), (28, 28, 30))
    cell.paste(old, (10, 60 + H - old.height)); cell.paste(new, (old.width + 20, 60 + H - new.height))
    cell.paste(hero, (old.width + new.width + 30, 60 + H - hero.height))
    dr = ImageDraw.Draw(cell); F = font(20)
    dr.text((10, 10), "Gareth's Smithy: BEFORE (David's screenshot)", fill=(230, 150, 150), font=F)
    dr.text((10, 36), "generic brick house, roof ~60% of the image", fill=(200, 200, 200), font=font(15))
    dr.text((old.width + 20, 10), f"AFTER (new sprite, ~{SCREEN_PPT:.1f} px/tile, 1.8 m player at the door)", fill=(150, 230, 150), font=F)
    dr.text((old.width + 20, 36), "same 17x15 footprint, same door (86,18); facade + forge dominate", fill=(200, 200, 200), font=font(15))
    dr.text((old.width + new.width + 30, 10), "3/4 view (model)", fill=(200, 200, 230), font=F)
    cell.save(os.path.join(ROOT, "smithy_before_after.png"), optimize=True)
    print("post done", meta["sprite_1x"], meta["tris_total"])


if __name__ == "__main__":
    main()
