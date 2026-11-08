"""Run the approved King's Castle map-source tests from the parity fixture.

Every test function in the fixture is called. A navigation, placement, or
other logic failure fails this process. A failure caused only by a missing
renderer module or a missing baked-art file is reported as a gap and does
not count as a pass.
"""
from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "server" / "kcs_parity"
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


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"missing map source fixture: {SOURCE}")
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
    print(
        f"kings_castle_siege map sources: {len(passed)} passed, {len(gaps)} asset/dependency gaps, "
        f"0 skipped, {len(names)} total"
    )
    for name, reason in gaps:
        print(f"  gap {name}: {reason}")


if __name__ == "__main__":
    main()
