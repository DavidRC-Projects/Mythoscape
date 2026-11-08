"""Write milestone-3 gameplay-renderer previews (headless SDL dummy)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from .constants import WALL_S
from .layout import build_battlefield, scale_report
from .placement import find_valid_on_side, sample_perimeter_layout, validate_placement
from . import art
from . import angled_view as V

DEFAULT_OUT = Path("/workspace/uploads/kings_castle_siege_m21")


def _save(surf: pygame.Surface, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
    return path


def render_all(out_dir: Path | None = None) -> list:
    out_dir = Path(out_dir or DEFAULT_OUT)
    import shutil
    prev = Path("/workspace/uploads/kings_castle_siege_m17")
    out_dir.mkdir(parents=True, exist_ok=True)
    if prev.is_dir():
        for name in ("01_south_gate.png", "02_south_gate_breach.png", "03_west_flank.png",
                       "05_courtyard.png", "06_placement_ui.png", "07_overview.png"):
            src = prev / name
            if src.is_file():
                shutil.copy2(src, out_dir / f"before_{name}")
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    t0 = pygame.time.get_ticks()
    art.warmup()
    warmup_ms = pygame.time.get_ticks() - t0
    bf = build_battlefield()
    engines = sample_perimeter_layout(bf)
    intact = {k: "intact" for k in bf.plane.openings}
    open_main = dict(intact)
    open_main["main_gate"] = "destroyed"
    open_keep = dict(open_main)
    open_keep["keep_doors"] = "destroyed"

    # Placement ghosts near the south approach
    valid = None
    valid_kind = "ram"
    for y in range(WALL_S + 8, WALL_S + 28):
        for x in range(108, 136, 2):
            res = validate_placement(bf, "ram", x, y, 0, engines)
            if res.ok:
                valid = res
                valid_kind = "ram"
                break
        if valid is not None:
            break
    if valid is None:
        for x in range(100, 128, 2):
            res = validate_placement(bf, "ram", x, WALL_S + 1, 0, engines)
            if res.ok:
                valid = res
                break
    if valid is None:
        found = find_valid_on_side(bf, "ram", "south", engines, 0)
        valid = validate_placement(bf, "ram", found[0], found[1], found[2], engines)
        valid_kind = "ram"
    invalid = validate_placement(bf, "trebuchet", 139, 202, 0, engines)
    if invalid.ok:
        invalid = validate_placement(bf, "ram", 139, 185, 0, engines)

    jobs = []

    def shot(name, player, facing, title, subtitle, tp, states=None, ghosts=None, reason="", build=False):
        surf = V.render_world(
            bf, player, engines, title, subtitle,
            tile_px=tp, facing=facing, gate_states=states or intact,
            ghosts=ghosts, ghost_reason=reason, build_ui=build,
        )
        return name, surf, dict(V.LAST_METRICS)

    shots = [
        shot(
            "01_south_gate.png", (139, 212), "n",
            "King's Castle M21 — south gate (playable camera)",
            "Rounded gatehouse drums, articulated doors/portcullis and continuous south curtain. Same collision as the nav grid.",
            14,
        ),
        shot(
            "01b_south_gate_human.png", (139, 200), "n",
            "King's Castle M21 — south gate at approaching scale",
            "Closer gameplay zoom: player versus gate height, not a wooden cliff face.",
            18,
        ),
        shot(
            "02_south_gate_breach.png", (139, 212), "n",
            "King's Castle M21 — south gate destroyed",
            "The same camera after the main gate is destroyed — walkable breach with presentation fire, not a painted teleport.",
            14, open_main,
        ),
        shot(
            "03_west_flank.png", (70, 148), "e",
            "King's Castle M21 — west flank",
            "Western approach with baked west curtain and corner towers. Camera follows the player.",
            16,
        ),
        shot(
            "04_north_rear.png", (139, 84), "s",
            "King's Castle M21 — north rear",
            "Northern battlefield outside the north wall. The keep sits inside the courtyard.",
            14,
        ),
        shot(
            "05_courtyard.png", (140, 168), "n",
            "King's Castle M21 — courtyard and keep",
            "Inner bailey around a keep with corner turrets and a south door, not a lone giant cube.",
            14,
        ),
        shot(
            "06_placement_ui.png", (120, 214), "n",
            "King's Castle M21 — engine placement",
            "Independent engines (ram hide-roof, trebuchet frame) plus ghost footprints on the live grid.",
            14, intact,
            [
                (valid, True, valid_kind),
                (invalid, False, "trebuchet"),
            ],
            invalid.reason, True,
        ),
        shot(
            "07_overview.png", (140, 210), "n",
            "King's Castle M21 — battlefield overview",
            "Zoomed-out gameplay renderer showing castle volume. Not the painted UI mockup.",
            8,
        ),
        shot(
            "08_wallwalk.png", (118, 183), "w",
            "King's Castle M21 — defender wall-walk",
            "Player standing on walkable H tiles. Routes and stairs unchanged.",
            22, intact,
        ),
        shot(
            "10_south_close.png", (139, 198), "n",
            "King's Castle M21 — south close",
            "Closer south approach: recessed gatehouse arch and timber leaves, not a grey slab.",
            28,
        ),
        shot(
            "10a_gate_close.png", (139, 196), "n",
            "King's Castle M21 — main gate close intact",
            "Gameplay-scale recessed south doors, portcullis and warm jamb light.",
            36,
        ),
        shot(
            "10a2_gate_breach_close.png", (139, 196), "n",
            "King's Castle M21 — main gate close breached",
            "Destroyed main gate is an open stone passage, still aligned to the nav breach.",
            36, open_main,
        ),
        shot(
            "10b_keep_close.png", (140, 162), "n",
            "King's Castle M21 — keep door close intact",
            "Keep south entrance: recessed masonry and paneled timber, not a painted rectangle.",
            32,
        ),
        shot(
            "10b2_keep_open_close.png", (140, 162), "n",
            "King's Castle M21 — keep door close open",
            "Keep doors destroyed: deep opening with an opaque interior cap, not a film hole.",
            32, open_keep,
        ),
        shot(
            "10d_west_postern.png", (72, 139), "e",
            "King's Castle M21 — west postern intact",
            "West postern is a door-height recessed portal, not a full-height timber wall.",
            28,
        ),
        shot(
            "10d2_west_postern_open.png", (72, 139), "e",
            "King's Castle M21 — west postern open",
            "Destroyed west postern leaves the masonry recess and a walkable gap.",
            28, {**intact, "west_gate": "destroyed"},
        ),
        shot(
            "10e_east_postern.png", (208, 139), "w",
            "King's Castle M21 — east postern intact",
            "East postern matching the west door-height recess.",
            28,
        ),
        shot(
            "10f_north_postern.png", (139, 80), "s",
            "King's Castle M21 — north postern intact",
            "North postern at door height on the rear curtain.",
            26,
        ),
        shot(
            "05b_courtyard_keep_open.png", (140, 168), "n",
            "King's Castle M21 — courtyard with keep doors open",
            "Same courtyard camera after keep_doors is destroyed.",
            14, open_keep,
        ),
        shot(
            "13_breach_approach.png", (139, 208), "n",
            "King's Castle M21 — breach approach",
            "Walking toward the destroyed south gate: arch and courtyard beyond, not a painted cap.",
            18, open_main,
        ),
        shot(
            "13b_breach_threshold.png", (139, 190), "n",
            "King's Castle M21 — breach threshold",
            "At the threshold: round arch frames a real passage into the bailey.",
            28, open_main,
        ),
        shot(
            "13c_breach_inside.png", (139, 184), "n",
            "King's Castle M21 — inside the breach",
            "Camera standing in the gate tiles, looking through to the courtyard.",
            32, open_main,
        ),
        shot(
            "13d_breach_through.png", (139, 176), "n",
            "King's Castle M21 — through the breach",
            "Just north of the gate, in the courtyard. Path and collision unchanged.",
            24, open_main,
        ),
        shot(
            "13i_threshold_intact.png", (139, 190), "n",
            "King's Castle M21 — same threshold, gate intact",
            "Identical camera to the breach threshold with doors and portcullis restored.",
            28,
        ),
    ]

    written = []
    metrics = []
    for name, surf, met in shots:
        path = _save(surf, out_dir / name)
        written.append(path)
        metrics.append((name, met))
        print(f"WROTE {path} ({path.stat().st_size} bytes) metrics={met}")

    # Timed FX frames from the same close breach camera (elapsed-time animation).
    for label, sec in (("13e_fx_t0.png", 0.15), ("13f_fx_t1.png", 1.45), ("13g_fx_t2.png", 2.85)):
        V.FX_TIME_OVERRIDE = sec
        surf = V.render_world(
            bf, (139, 196), engines,
            "King's Castle M21 — breach fire/smoke",
            f"Actual renderer at t={sec:.2f}s — layered flames, wisps and embers, no disc.",
            tile_px=36, facing="n", gate_states=open_main,
        )
        path = _save(surf, out_dir / label)
        written.append(path)
        print(f"WROTE {path} ({path.stat().st_size} bytes) fx_t={sec} metrics={dict(V.LAST_METRICS)}")
    V.FX_TIME_OVERRIDE = None

    print("WARMUP_MS", warmup_ms)
    print("SCALE", scale_report(bf))
    print("ENGINES", [(e.engine_id, e.engine_type, e.x, e.y) for e in engines])
    print("INVALID_REASON", invalid.reason)
    print("VALID_TILES", len(valid.tiles) if valid else 0)

    # Steady-state walk at the south-gate gameplay zoom (same 1600x900 as shots).
    path = [(139, y) for y in range(210, 186, -1)]
    walk = V.profile_walk(bf, path, engines, tile_px=32, size=(1600, 900), facing="n")
    print("WALK_PROFILE_SOUTH", walk)
    path_c = [(139, y) for y in range(168, 150, -1)]
    walk_c = V.profile_walk(bf, path_c, engines, tile_px=20, size=(1600, 900), facing="n")
    print("WALK_PROFILE_COURT", walk_c)
    path_b = [(139, y) for y in range(210, 168, -2)]
    walk_b = V.profile_walk(bf, path_b, engines, tile_px=32, size=(1600, 900), facing="n", gate_states=open_main)
    print("WALK_PROFILE_BREACH_32", walk_b)
    # Cold (moving across cache quanta) vs warm (same 3-tile camera cell).
    from . import angled_view as AV
    AV._view_cache.clear()
    cold = []
    for y in range(214, 186, -4):
        V.render_world(bf, (139, y), engines, "cold", "cold", tile_px=14, size=(1600, 900), facing="n", markers=False)
        cold.append(float(V.LAST_METRICS["total_ms"]))
    # Stay inside one cache cell (player//3 constant)
    y0 = 201
    V.render_world(bf, (139, y0), engines, "warm", "seed", tile_px=14, size=(1600, 900), facing="n", markers=False)
    warm = []
    for xoff in range(3):
        V.render_world(bf, (139, y0 + 0), engines, "warm", "hit", tile_px=14, size=(1600, 900), facing="n", markers=False)
        warm.append(float(V.LAST_METRICS["total_ms"]))
    print("COLD_FRAMES_MS", {"n": len(cold), "mean": round(sum(cold)/len(cold),2), "max": round(max(cold),2), "min": round(min(cold),2), "samples": [round(v,1) for v in cold]})
    print("WARM_CACHED_MS", {"n": len(warm), "mean": round(sum(warm)/len(warm),2), "samples": [round(v,1) for v in warm]})

    _write_reference_composite(out_dir / "01_south_gate.png", out_dir / "09_reference_vs_runtime.png")
    _write_reference_composite(out_dir / "10a_gate_close.png", out_dir / "09b_reference_vs_runtime_close.png")
    return written


def _write_reference_composite(runtime_path: Path, dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    ref_candidates = [
        Path("/home/box/sand-data/agents/da220230-5691-4a53-a42f-eed226c0cf37/attachments/4a58ab1c426510fad31d4897f55d5fb9d3c85c805db532915ae6907beed65c05.png"),
        Path("/home/box/agent-data/agents/da220230-5691-4a58-a42f-eed226c0cf37/attachments/4a58ab1c426510fad31d4897f55d5fb9d3c85c805db532915ae6907beed65c05.png"),
        Path("/home/box/agent-data/agents/da220230-5691-4a53-a42f-eed226c0cf37/attachments/4a58ab1c426510fad31d4897f55d5fb9d3c85c805db532915ae6907beed65c05.png"),
        Path("/home/workdir/attachments/image.png"),
    ]
    ref_path = next((p for p in ref_candidates if p.is_file()), None)
    if ref_path is None or not Path(runtime_path).is_file():
        print("COMPOSITE_SKIP", ref_path, runtime_path)
        return
    ref = Image.open(ref_path).convert("RGB")
    rt = Image.open(runtime_path).convert("RGB")
    h = 720
    def fit(im):
        w = int(im.width * h / im.height)
        return im.resize((w, h), Image.Resampling.LANCZOS)
    ref, rt = fit(ref), fit(rt)
    pad, label_h = 16, 48
    canvas = Image.new("RGB", (ref.width + rt.width + pad * 3, h + label_h + pad * 2), (18, 16, 14))
    canvas.paste(ref, (pad, label_h + pad))
    canvas.paste(rt, (pad * 2 + ref.width, label_h + pad))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        small = font
    draw.text((pad, 12), "REFERENCE — painted mockup (not playable UI)", fill=(236, 214, 168), font=font)
    draw.text((pad * 2 + ref.width, 12), "RUNTIME M21 — playable Pygame camera (same angle family)", fill=(236, 214, 168), font=font)
    draw.text((pad, label_h + pad + h - 22), "Concept lighting, armies and HUD numbers are not gameplay.", fill=(200, 186, 160), font=small)
    canvas.save(dest)
    print("WROTE", dest, dest.stat().st_size)


def main() -> None:
    parser = argparse.ArgumentParser(description="King's Castle M21 angled previews")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    render_all(Path(args.out))


if __name__ == "__main__":
    main()
