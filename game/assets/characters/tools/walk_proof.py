"""
Walk proof: the NEW drawer must place every limb on exactly the joints the OLD
drawer uses, for every sampled frame, in all 4 directions, male + female.

Method: monkeypatch rs_style.draw_volume_limb while the OLD code draws, record
every limb segment it is handed (these ARE the animation: hip/knee/foot,
shoulder/elbow/hand per frame incl. bob, stride, lift, hand_shift), then compute
the NEW rig (rs_humanoid_v2.rig_side / rig_ortho) for the same inputs and
require bit-identical floats. Also checks resolve_pose output is identical,
and renders a side-by-side sheet + GIF.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from render_common import *
import rs_style as rs
import rs_humanoid_v2 as V2
from PIL import Image

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "/workspace/characters"
T = 40
PERIOD = 1.0 / 1.15            # pose_walk cadence = TAU*1.15 rad/s
N = 8                          # sheet frames per cycle
DIRS = [("front", "down (front)"), ("back", "up (back)"), (-1, "left"), (1, "right")]

captured = []
_orig = rs.draw_volume_limb


def _spy(surf, ax, ay, bx, by, half_w, *a, **k):
    captured.append((ax, ay, bx, by))
    return _orig(surf, ax, ay, bx, by, half_w, *a, **k)


def old_segments(facing, gender, t, eq, atk=0.0):
    captured.clear()
    rs.draw_volume_limb = _spy
    try:
        tmp = pygame.Surface((300, 300), pygame.SRCALPHA)
        draw_char(tmp, 150, 150, T, False, eq, gender, facing, moving=atk <= 0, t=t, attacking=atk)
    finally:
        rs.draw_volume_limb = _orig
    return list(captured)


def new_segments(facing, gender, t, eq, atk=0.0):
    view, f = H._parse_facing(facing)
    fem = gender == "female"
    s = rs.unit(T, "character") * (0.96 if fem else 1.0)
    pad = max(72, int(T * 2.7))
    if atk > 0.02 and view != "side":
        view, f = "side", 1
    cx, cy = (150, 150) if not (view == "side" and f < 0) else (pad, pad)
    mv = atk <= 0
    pose, wk = V2.resolve(mv, t, atk, 1 if view == "side" else f, None, weapon_style(eq.get("weapon")), eq)
    if view == "side":
        R = V2.rig_side(cx, cy, s, pose, fem, 1, mv, atk)
        segs = []
        for foot, knee, hip in (R["far_leg"], R["near_leg"]):
            segs += [(*hip, *knee), (*knee, *foot)]
        segs += [(*R["sh_far"], *R["el_far"]), (*R["el_far"], *R["hand_far"]),
                 (*R["sh_near"], *R["el_near"]), (*R["el_near"], *R["hand_near"])]
    else:
        R = V2.rig_ortho(cx, cy, s, view, True, t, pose, fem)
        segs = []
        for foot, knee, hip in R["legs"]:
            segs += [(*hip, *knee), (*knee, *foot)]
        for hand, el, sh in R["arms"]:
            segs += [(*sh, *el), (*el, *hand)]
    return segs, pose, R["bob"]


def main():
    report = {"frames_checked": 0, "segments_checked": 0, "max_abs_diff": 0.0, "mismatches": 0,
              "pose_identical": True, "cases": []}
    samples = [i * PERIOD / 48.0 for i in range(96)] + [0.123, 1.7, 13.37, 1e5 + 0.41]
    for eq_name, eq in (("unarmed", {}), ("steel_set", {"weapon": "steel_longsword", "shield": "steel_shield",
                                                          "body": "steel_body", "legs": "steel_legs", "helmet": "steel_helmet"}),
                        ("eclipse_set", {"weapon": "eclipse_cleaver", "shield": "eclipse_shield", "body": "eclipse_body",
                                         "legs": "eclipse_legs", "helmet": "eclipse_helmet"}),
                        ("mythos_set", {"weapon": "mythos_longsword", "shield": "mythos_shield", "body": "mythos_body",
                                        "legs": "mythos_legs", "helmet": "mythos_helmet"})):
        for gender in ("male", "female"):
            for facing, dname in DIRS:
                worst = 0.0
                for t in samples:
                    old = old_segments(facing, gender, t, eq)
                    new, pose, bob = new_segments(facing, gender, t, eq)
                    # every new segment must be present, exactly, in the old draw calls (in order)
                    it = iter(old)
                    for sg in new:
                        for o in it:
                            if o == sg:
                                break
                        else:
                            report["mismatches"] += 1
                            best = min(max(abs(a - b) for a, b in zip(o2, sg)) for o2 in old)
                            worst = max(worst, best)
                            it = iter(old)
                    report["segments_checked"] += len(new)
                    report["frames_checked"] += 1
                    p_old = rs.resolve_pose(True, t, 0.0, 1 if not isinstance(facing, str) else 1, action=None, weapon_kind=None)
                    if p_old != pose:
                        report["pose_identical"] = False
                report["max_abs_diff"] = max(report["max_abs_diff"], worst)
                report["cases"].append({"gear": eq_name, "gender": gender, "dir": dname, "max_abs_diff": worst})
    # ---- combat: melee + archery swings (side view, both facings) use the same rig
    report["attack_frames_checked"] = 0
    report["attack_mismatches"] = 0
    for eq in ({"weapon": "steel_longsword", "shield": "steel_shield"}, {"weapon": "eclipse_cleaver", "body": "eclipse_body", "legs": "eclipse_legs"},
               {"weapon": "mythos_longsword", "body": "mythos_body", "legs": "mythos_legs", "shield": "mythos_shield"},
               {"weapon": "iron_dagger"}, {"weapon": "yew_shortbow"}, {"weapon": "mithril_battleaxe"}):
        for gender in ("male", "female"):
            for facing in (1, -1):
                for i in range(1, 50):
                    atk = i / 50.0
                    old = old_segments(facing, gender, 2.0, eq, atk)
                    new, _, _ = new_segments(facing, gender, 2.0, eq, atk)
                    if not all(sg in old for sg in new):
                        report["attack_mismatches"] += 1
                    report["attack_frames_checked"] += 1
    report["walk_timing"] = {
        "cadence_rad_per_s": rs.TAU * 1.15, "cycle_seconds": PERIOD,
        "frame_source": "continuous t=time.time() (client.py:4924) -> rs.resolve_pose -> pose_walk; unchanged",
        "directions": "client facing_for()/facing_for_view() -> _parse_facing(); unchanged",
        "moving_flag": "client moving_for(): 0.55 s hold after each tile step; unchanged",
        "bob": "side root_bob*s, ortho root_bob*s*0.55 (copied verbatim, verified via hip joints)",
    }
    report["PASS"] = report["mismatches"] == 0 and report["pose_identical"] and report["attack_mismatches"] == 0
    json.dump(report, open(os.path.join(OUTDIR, "walk_proof.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=1))

    # ---- sheet: rows = dir x (old,new), cols = N frames
    cw, ch = 96, 132
    sheet = pygame.Surface((150 + N * cw, 60 + len(DIRS) * 2 * ch))
    tiles(sheet)
    for i in range(N):
        label(sheet, f"f{i}", 150 + i * cw + 38, 6)
    for d, (facing, dname) in enumerate(DIRS):
        for k, new in enumerate((False, True)):
            y0 = 30 + (d * 2 + k) * ch
            label(sheet, f"{dname}", 6, y0 + 40)
            label(sheet, "NEW" if new else "OLD", 6, y0 + 60, (255, 220, 120) if new else (200, 200, 200))
            for i in range(N):
                draw_char(sheet, 150 + i * cw + cw // 2, y0 + 82, T, new, {}, "male", facing, True, i * PERIOD / N)
    big = pygame.transform.scale(sheet, (sheet.get_width() * 2, sheet.get_height() * 2))
    pygame.image.save(big, os.path.join(OUTDIR, "walk_compare_sheet.png"))

    # ---- GIF: real-time (25 fps) walk, old top row vs new bottom row, 4 dirs
    frames = []
    fps = 25
    for fi in range(int(PERIOD * 2 * fps)):
        t = fi / fps
        fr = pygame.Surface((4 * 110 + 60, 2 * 150 + 20))
        tiles(fr)
        for k, new in enumerate((False, True)):
            label(fr, "NEW" if new else "OLD", 4, 20 + k * 150)
            for d, (facing, dname) in enumerate(DIRS):
                draw_char(fr, 60 + 55 + d * 110, 100 + k * 150, T, new, {"weapon": "iron_sword", "shield": "wooden_shield"} if k < 9 else {}, "male", facing, True, t)
        big = pygame.transform.scale(fr, (fr.get_width() * 2, fr.get_height() * 2))
        frames.append(Image.frombytes("RGB", big.get_size(), pygame.image.tobytes(big, "RGB")))
    frames[0].save(os.path.join(OUTDIR, "walk_compare.gif"), save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps), loop=0, optimize=True)


if __name__ == "__main__":
    main()
