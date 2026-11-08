"""Run the approved King's Castle map-source tests from the parity fixture.

Every test function in the fixture is called. A navigation, placement, or
other logic failure fails this process. A failure caused only by a missing
renderer module or a missing baked-art file is reported as a gap and does
not count as a pass.

Asset bytes stay outside the repo. The approved sources resolve
``kcs_parity/assets`` and one test opens ``/workspace/kings_castle_siege/assets/baked_m9``.
This harness points both at ``KCS_VISUAL_FIXTURES`` (default ``/tmp/kcs_visual_fixtures``)
without editing those sources. Runtime names are used as extracted; historical
plates and sprites are not copied over them.
"""
from __future__ import annotations

import importlib.util
import os
import traceback
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "server" / "kcs_parity"
EXTERNAL = Path(os.environ.get("KCS_VISUAL_FIXTURES", "/tmp/kcs_visual_fixtures"))
SOURCE = FIXTURE / "tests" / "test_kings_castle_siege_map.py"

ORDER = [
    "test_namespace_isolation",
    "test_no_live_imports",
    "test_bounds_and_grid",
    "test_gate_widths_and_staging",
    "test_walls_block_until_breach",
    "test_each_gate_is_a_viable_entry",
    "test_lanes_reach_their_gates",
    "test_full_perimeter_routes",
    "test_keep_does_not_seal_north",
    "test_defender_wall_circuit",
    "test_courtyard_reaches_keep_and_stations",
    "test_throne_nave",
    "test_scale_travel",
    "test_independent_load",
    "test_engine_placement_all_sides_and_rejects",
    "test_variable_extra_placement",
    "test_walk_tour",
    "test_visual_anchors",
    "test_chunk_projection_is_continuous",
    "test_m3_renderer_frame",
    "test_angled_projection_roundtrip",
    "test_angled_renderer_and_invalidation",
    "test_replace_baked_swaps_visible_tower",
    "test_face_patch_lut_and_sky_skip_exact",
    "test_strip_refill_partial_patch_exact",
    "test_portal_depth_and_gate_state",
]


def _gap_reason(exc: BaseException) -> str:
    seen = []
    current = exc
    while current is not None and current not in seen:
        seen.append(current)
        name = type(current).__name__
        if name in {"ModuleNotFoundError", "FileNotFoundError", "ImportError"}:
            return f"{name}: {current}"
        text = str(current).lower()
        if "no such file" in text or "couldn't open" in text or "could not open" in text:
            return f"{name}: {current}"
        if name == "error" and "pygame" in type(current).__module__:
            return f"pygame.error: {current}"
        current = current.__cause__ or current.__context__
    return ""


def _link(path: Path, target: Path) -> None:
    if path.is_symlink():
        if path.resolve() != target.resolve():
            path.unlink()
            path.symlink_to(target, target_is_directory=True)
        return
    if path.exists():
        raise SystemExit(f"{path} exists and is not a link to the external fixtures")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target, target_is_directory=True)


def _stage_external_assets() -> None:
    assets = EXTERNAL / "assets"
    if not (assets / "baked_m9" / "gatehouse.png").is_file():
        raise SystemExit(f"external visual fixtures missing at {assets}")
    if not (assets / "sprites" / "grass_fine.png").is_file():
        raise SystemExit(f"external sprites missing at {assets / 'sprites'}")
    _link(FIXTURE / "assets", assets)
    # The approved portal test hardcodes this path. The file is hash-locked, so
    # the harness materializes the path instead of editing the test.
    _link(Path("/workspace/kings_castle_siege/assets/baked_m9"), assets / "baked_m9")


def _save_samples() -> None:
    out = Path("/opt/cursor/artifacts")
    if not out.is_dir():
        return
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import sample_perimeter_layout
    from kings_castle_siege_map.angled_view import render_world as render_angled
    from kings_castle_siege_map.world_view import render_world as render_top
    bf = build_battlefield()
    engines = sample_perimeter_layout(bf)
    states = {k: "intact" for k in bf.plane.openings}
    angled = render_angled(bf, (139, 191), engines, "sample", "angled", size=(800, 450), tile_px=18, facing="n", gate_states=states)
    top = render_top(bf, (139, 191), engines, "sample", "top", size=(800, 450), tile_px=22, facing="s", gate_states=states)
    pygame.image.save(angled, str(out / "kcs-angled-frame.png"))
    pygame.image.save(top, str(out / "kcs-topdown-frame.png"))
    print(f"saved sample frames under {out}")


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"missing map source fixture: {SOURCE}")
    _stage_external_assets()
    spec = importlib.util.spec_from_file_location("kcs_map_source_tests", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = [name for name in ORDER if callable(getattr(module, name, None))]
    missing = [name for name in ORDER if name not in names]
    if missing:
        raise SystemExit(f"fixture is missing tests: {missing}")
    extra = sorted(
        name for name in dir(module)
        if name.startswith("test_") and callable(getattr(module, name)) and name not in names
    )
    if extra:
        raise SystemExit(f"fixture has tests the runner does not list: {extra}")
    passed = []
    gaps = []
    for name in names:
        try:
            getattr(module, name)()
        except Exception as exc:
            reason = _gap_reason(exc)
            if reason:
                gaps.append((name, reason.splitlines()[0]))
                print(f"GAP {name}: {reason.splitlines()[0]}")
                continue
            print(f"FAIL {name}")
            traceback.print_exc()
            raise SystemExit(f"map source test failed: {name}") from exc
        passed.append(name)
        print(f"PASS {name}")
    if not gaps:
        try:
            _save_samples()
        except Exception:
            traceback.print_exc()
            raise SystemExit("map sources passed but sample frames failed") from None
    print(
        f"kings_castle_siege map sources: {len(passed)} passed, {len(gaps)} asset/dependency gaps, "
        f"0 skipped, {len(names)} total"
    )
    for name, reason in gaps:
        print(f"  gap {name}: {reason}")
    if gaps:
        raise SystemExit(f"{len(gaps)} map source tests still missing assets or modules")


if __name__ == "__main__":
    main()
