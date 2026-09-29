"""houses_post.py - 1x sprites, per-building metadata, contact sheets, before/after sheets.

    python3 tools/houses_post.py [--repo /path/to/Mythoscape]    (repo only needed to copy door enter/exit)
"""
import argparse, glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blender_scripts"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ast
_tree = ast.parse(open(os.path.join(ROOT, "blender_scripts", "houses_designs.py")).read())
SPECS = [ast.literal_eval(n.value) for n in _tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "SPECS"][0]
import buildings_map_patch as bmp  # noqa: E402

ATT = "/home/box/agent-data/agents/da220230-5691-4a53-a42f-eed226c0cf37/attachments/"
OLD_SHOTS = {
    "farmhouse": "9e3b6d4bbe02fa838539d374afd0b9ae7a59744a842b1c64798ccbd92e40b15a.png",
    "resting_ox": "9d71c273916698ef5ea19e4fbc1a2543ce21ad963da93c333d292154715174cb.png",
    "elders_hall": "fd872bd667b7c219578a329dfe56c900591ad5b7292a0fabd68b72e4b3fd04b7.png",
    "general_store": "e1fbe75d667879f40efd10bb6feabc76ca8cb407a0414070e292c2df9af68da9.png",
    "village_bank": "3df0c2c80a1b2f0ccd9cf527aa854bfaa57cf46333da93b25d2e02a6c928dd70.png",
    "pet_emporium": "db4390521d50326458a12684bcc87fc024dc45fa541af34a346b6ced974e88be.png",
    "stonehaven_cottage": "5f86be6b205aeb2021842f88d5b789b0eba2cb15719ab29db573d7f91ed8808b.png",
    "stonehaven_house": "52125aead46f67ae5e02e0b9a21a802acbabf708849fcfeb4294e4c418354148.png",
    "city_barracks": "6e345971bacf28d2739423aa8da168d77ca78dbe5aa732bc0dc874013524a2cd.png",
    "kais_catch": "02b409a97e028f14b8b150caeb777f060e94fb9e3786e28ad630711469888c48.png",
    "harbour_tackle": "15e8a13377119f1466009555ec999956ea6e633249e93273c0145e03b65d39c4.png",
}
GROUPS = {"village": ["elders_hall", "resting_ox", "general_store", "farmhouse", "village_bank", "pet_emporium"],
          "stonehaven": ["stonehaven_cottage", "stonehaven_house", "city_barracks"],
          "harbour": ["kais_catch", "harbour_tackle"]}
BG = {"village": (94, 122, 60), "stonehaven": (132, 130, 124), "harbour": (94, 122, 60)}
SCREEN_PPT = 47.5          # David's screenshots: ~47.5 px per tile
PLAYER = "/workspace/castle/sprites/1x/player_ref_1p8m.png"


def font(sz):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def group_of(key):
    return [g for g, ks in GROUPS.items() if key in ks][0]


def game_composite(key, ri, layers=("ground", "body"), grid=True, player=True):
    """1x layers over a tiled background, player standing on the apron tile below the door."""
    d = os.path.join(ROOT, "sprites", "1x", key)
    ims = [Image.open(os.path.join(d, f"{l}.png")).convert("RGBA") for l in layers]
    w, h = ims[0].size
    bg = Image.new("RGBA", (w, h), BG[group_of(key)] + (255,))
    dr = ImageDraw.Draw(bg)
    ox, oy = ri["origin_2x"][0] / 2, ri["origin_2x"][1] / 2
    if grid:
        c = tuple(max(0, v - 14) for v in BG[group_of(key)]) + (255,)
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
        _, _, _, _, W, D, DX, _ = SPECS[key]
        fx, fy = ox + (DX + 1.5) * 40, oy + (D + 0.6) * 40
        bg.alpha_composite(p, (int(fx - 0.7 * 26.9), int(fy - 2.1 * 26.9)))
    return bg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", default="/workspace/scratch/Mythoscape")
    a = ap.parse_args()
    doors = {}
    try:
        sys.path.insert(0, os.path.join(a.repo, "game/assets/mmorpg/server"))
        import content as c
        doors = {i["building"]: i for i in c.INTERACTABLES if i.get("kind") == "door" and i.get("building")}
    except Exception as exc:
        print("repo not available, door enter/exit taken from the pattern", exc)
    allmeta = {}
    for key, (bid, name, X0, Y0, W, D, DX, FLR) in SPECS.items():
        rp = os.path.join(ROOT, "json", "render", key + ".json")
        if not os.path.exists(rp):
            print("missing render", key); continue
        ri = json.load(open(rp))
        for l in ("ground", "body", "cutaway"):
            s2 = os.path.join(ROOT, "sprites", "2x", key, l + ".png")
            im = Image.open(s2)
            os.makedirs(os.path.join(ROOT, "sprites", "1x", key), exist_ok=True)
            im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(os.path.join(ROOT, "sprites", "1x", key, l + ".png"), optimize=True)
        n = bmp.NEW[bid]; o = bmp.OLD[bid]
        rows = []
        for ly in range(D):
            r = ""
            for lx in range(W):
                x, y = X0 + lx, Y0 + ly
                if n[4] <= x <= n[6] and n[5] <= y <= n[7]:
                    r += "F"
                elif x == n[8] and y > n[7]:
                    r += "D"
                elif y > n[7]:
                    r += "P"
                else:
                    r += "W"
            rows.append(r)
        dr = doors.get(bid, {})
        if not dr and os.path.exists(os.path.join(ROOT, "json", key + ".json")):     # repo absent: keep previous door data
            od = json.load(open(os.path.join(ROOT, "json", key + ".json")))["door"]
            dr = {"id": od["id"], "enter_x": od["enter"][0], "enter_y": od["enter"][1], "exit_x": od["exit"][0], "exit_y": od["exit"][1]}
        meta = {
            "key": key, "building_id": bid, "name": name, "flag": "USE_NEW_BUILDINGS", "version": 2,
            "footprint": {"x0": n[0], "y0": n[1], "x1": n[2], "y1": n[3], "w": W, "h": D},
            "floor": {"floor_x0": n[4], "floor_y0": n[5], "floor_x1": n[6], "floor_y1": n[7]},
            "old": {"x0": o[0], "y0": o[1], "x1": o[2], "y1": o[3], "floor_x0": o[4], "floor_y0": o[5],
                    "floor_x1": o[6], "floor_y1": o[7]},
            "door": {"id": dr.get("id"), "x": n[8], "y": n[3], "enter": [dr.get("enter_x", n[8]), dr.get("enter_y", n[3] - 2)],
                     "exit": [dr.get("exit_x", n[8]), dr.get("exit_y", n[3] + 1)], "unchanged": True,
                     "doorway_path_tiles": [[n[8], y] for y in range(n[7] + 1, n[3] + 1)]},
            "tile_px": 40,
            "sprite_1x": {"size": [ri["size_2x"][0] // 2, ri["size_2x"][1] // 2], "origin_px": [ri["origin_2x"][0] / 2, ri["origin_2x"][1] / 2]},
            "sprite_2x": {"size": ri["size_2x"], "origin_px": ri["origin_2x"]},
            "anchor_note": "origin_px = pixel of the NW corner of world tile (x0,y0) in every layer. Blit at "
                           "(tile_screen_x(x0) - origin_px.x*TILE/40, tile_screen_y(y0) - origin_px.y*TILE/40), scaled by TILE/40.",
            "layers": [
                {"name": "ground", "file": f"{key}/ground.png", "order": "after floor tiles, before entities (porch boards, steps, yard soil/grass, dock water)"},
                {"name": "body", "file": f"{key}/body.png", "order": f"y-sorted like an entity standing on world row {n[3]}: after entities with y <= {n[3]}, before entities with y > {n[3]}"},
                {"name": "cutaway", "file": f"{key}/cutaway.png", "order": "replaces body while the local player is inside (floor rect or doorway tiles); walls cut at 1.6 m"},
            ],
            "walkability": {"origin": [X0, Y0], "rows": rows,
                            "legend": {"W": "WALL (walls/roof mass)", "F": "FLOOR (interior)", "D": "PATH doorway column (door tile at the bottom)",
                                       "P": "WALL porch/yard (props stand here)"}},
            "entity_moves": ({"jeweler_lira": {"npc": [33, 8], "new": [35, 8], "also": "PLACES 'jeweler' label (33,8) -> (35,8)"}}
                             if bid == "cottage_ne" else {}),
            "camera": {"type": "ortho", "azimuth_deg": 0, "elevation_deg": 32, "y_prestretch": "1/sin(32)", "sun_euler_deg": [40, 15, -30]},
            "triangles": ri["tris"], "tris_total": ri["tris_total"],
            "models": {"blend": f"models/{key}.blend", "glb": f"models/{key}.glb", "bam": f"models/{key}.bam"},
        }
        allmeta[key] = meta
        os.makedirs(os.path.join(ROOT, "json"), exist_ok=True)
        json.dump(meta, open(os.path.join(ROOT, "json", key + ".json"), "w"), indent=1)
        json.dump(meta, open(os.path.join(ROOT, "sprites", "1x", key, "meta.json"), "w"), indent=1)
        # game view concept
        os.makedirs(os.path.join(ROOT, "concepts", "game"), exist_ok=True)
        game_composite(key, ri).convert("RGB").save(os.path.join(ROOT, "concepts", "game", key + "_game_1x.png"))
        game_composite(key, ri, layers=("ground", "cutaway")).convert("RGB").save(os.path.join(ROOT, "concepts", "game", key + "_inside_1x.png"))
    json.dump(allmeta, open(os.path.join(ROOT, "json", "buildings_v2.json"), "w"), indent=1)

    # ---------------- contact sheets per group + all
    F, Fs = font(26), font(17)
    def contact(keys, path, title):
        cells = []
        for key in keys:
            ri = json.load(open(os.path.join(ROOT, "json", "render", key + ".json")))
            g = game_composite(key, ri).convert("RGB")
            hero = Image.open(os.path.join(ROOT, "concepts", "hero", key + ".png")).convert("RGB")
            H = 520
            g = g.resize((int(g.width * H / g.height), H), Image.LANCZOS)
            hero = hero.resize((int(hero.width * H / hero.height), H), Image.LANCZOS)
            cell = Image.new("RGB", (g.width + hero.width + 30, H + 70), (28, 28, 30))
            cell.paste(g, (10, 60)); cell.paste(hero, (g.width + 20, 60))
            m = allmeta[key]
            ImageDraw.Draw(cell).text((10, 8), SPECS[key][1], fill=(240, 220, 150), font=F)
            ImageDraw.Draw(cell).text((10, 38), f"{m['footprint']['w']}x{m['footprint']['h']} tiles  |  {m['tris_total']} tris  |  game view (1x) + 3/4 view",
                                      fill=(200, 200, 200), font=Fs)
            cells.append(cell)
        cols = 2 if len(cells) > 2 else len(cells)
        cw = max(c.width for c in cells); ch = max(c.height for c in cells)
        rows_ = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw + 20, rows_ * ch + 70), (18, 18, 20))
        ImageDraw.Draw(sheet).text((12, 14), title, fill=(255, 255, 255), font=font(32))
        for i, c_ in enumerate(cells):
            sheet.paste(c_, (10 + (i % cols) * cw, 60 + (i // cols) * ch))
        sheet.save(path, optimize=True)
        print("wrote", path)
    for g, ks in GROUPS.items():
        contact(ks, os.path.join(ROOT, "concepts", f"contact_{g}.png"), f"Mythoscape buildings v2 - {g}")
    # all 11, game view only, side by side at the same scale
    ims = []
    for key in sum(GROUPS.values(), []):
        ri = json.load(open(os.path.join(ROOT, "json", "render", key + ".json")))
        ims.append((key, game_composite(key, ri).convert("RGB")))
    Hm = max(i.height for _, i in ims)
    tw = sum(i.width for _, i in ims) + 10 * (len(ims) + 1)
    half = len(ims) // 2 + 1
    r1, r2 = ims[:half], ims[half:]
    w1 = sum(i.width for _, i in r1) + 10 * (len(r1) + 1); w2 = sum(i.width for _, i in r2) + 10 * (len(r2) + 1)
    sheet = Image.new("RGB", (max(w1, w2), 2 * (Hm + 50) + 60), (18, 18, 20))
    ImageDraw.Draw(sheet).text((12, 12), "All 11 new buildings, game view at 1x (40 px tiles, same scale, 1.8 m player at each door)", fill=(255, 255, 255), font=font(28))
    for row, items in ((0, r1), (1, r2)):
        x = 10
        for key, im in items:
            y = 60 + row * (Hm + 50) + (Hm - im.height)
            sheet.paste(im, (x, y + 36))
            ImageDraw.Draw(sheet).text((x, 60 + row * (Hm + 50) + 4), SPECS[key][1], fill=(240, 220, 150), font=Fs)
            x += im.width + 10
    sheet.save(os.path.join(ROOT, "concepts", "contact_all_game_1x.png"), optimize=True)

    # ---------------- before / after at the screenshot scale
    for g, ks in GROUPS.items():
        cells = []
        for key in ks:
            old = Image.open(ATT + OLD_SHOTS[key]).convert("RGB")
            ri = json.load(open(os.path.join(ROOT, "json", "render", key + ".json")))
            new = game_composite(key, ri, grid=False).convert("RGB")
            s = SCREEN_PPT / 40
            new = new.resize((int(new.width * s), int(new.height * s)), Image.LANCZOS)
            H = max(old.height, new.height)
            cell = Image.new("RGB", (old.width + new.width + 30, H + 60), (28, 28, 30))
            cell.paste(old, (10, 50 + H - old.height)); cell.paste(new, (old.width + 20, 50 + H - new.height))
            dr_ = ImageDraw.Draw(cell)
            dr_.text((10, 10), f"{SPECS[key][1]}: BEFORE (David's screenshot)", fill=(230, 150, 150), font=Fs)
            dr_.text((old.width + 20, 10), f"AFTER (new sprite, same ~{SCREEN_PPT:.1f} px/tile, 1.8 m player)", fill=(150, 230, 150), font=Fs)
            cells.append(cell)
        W_ = max(c.width for c in cells)
        sheet = Image.new("RGB", (W_ + 20, sum(c.height for c in cells) + 20 + 10 * len(cells)), (18, 18, 20))
        y = 10
        for c_ in cells:
            sheet.paste(c_, (10, y)); y += c_.height + 10
        sheet.save(os.path.join(ROOT, "concepts", f"before_after_{g}.png"), optimize=True)
        print("wrote before/after", g)


if __name__ == "__main__":
    main()
