"""Isolation, perimeter reachability, placement and scale tests (M2)."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kings_castle_siege_map.constants import (  # noqa: E402
    DESIGN_ATTACKERS,
    DESIGN_DEFENDERS,
    FORBIDDEN_IDS,
    HEIGHT,
    KEEP_RECT,
    MAP_ID,
    OWNERSHIP_KEY_RESERVED,
    WALL_N,
    WALL_S,
    WIDTH,
)
from kings_castle_siege_map.layout import (  # noqa: E402
    bfs,
    build_battlefield,
    future_integration_points,
    path_exists,
    scale_report,
    shortest_length,
    staging_capacity,
    walkable,
)
from kings_castle_siege_map.placement import (  # noqa: E402
    find_valid_on_side,
    place,
    ring_still_clear,
    sample_perimeter_layout,
    validate_placement,
)
from kings_castle_siege_map.walk import build_tour, shortest_path  # noqa: E402


def check(ok, msg):
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


def test_namespace_isolation():
    check(MAP_ID == "kings_castle_siege", f"map id {MAP_ID}")
    check(MAP_ID not in FORBIDDEN_IDS, "map id is not a live realm id")
    check(OWNERSHIP_KEY_RESERVED not in FORBIDDEN_IDS, "reserved ownership key is new")
    check(OWNERSHIP_KEY_RESERVED != "king", "must not reuse castle_ownership king row")
    check("castle_realm" in FORBIDDEN_IDS and "king" in FORBIDDEN_IDS, "forbidden set lists live ids")
    hooks = future_integration_points(build_battlefield())
    check(hooks["map_id"] == MAP_ID, "integration map_id")
    check(hooks["ownership_key_reserved"] != "king", "integration ownership key")


def test_no_live_imports():
    pkg = ROOT / "kings_castle_siege_map"
    banned = {"server", "client", "crown_siege", "castle_realm", "throne", "database", "castle_owners"}
    found = []
    for path in pkg.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in banned:
                    found.append(f"{path.name}:{n}")
    check(not found, f"no live-module imports ({found})")
    importlib.import_module("kings_castle_siege_map")


def test_bounds_and_grid():
    bf = build_battlefield()
    check(bf.plane.width == WIDTH and bf.plane.height == HEIGHT, "battlefield size")
    check(WIDTH == 280 and HEIGHT == 280, "M2 square-ish perimeter grid")
    check(len(bf.plane.grid) == HEIGHT, "row count")
    check(all(len(row) == WIDTH for row in bf.plane.grid), "row widths")
    check(bf.plane.in_bounds(0, 0) and bf.plane.in_bounds(WIDTH - 1, HEIGHT - 1), "corners in bounds")
    check(not bf.plane.in_bounds(-1, 0) and not bf.plane.in_bounds(WIDTH, 0), "out of bounds rejected")
    check(bf.throne.width == 72 and bf.throne.height == 44, "throne plane size")
    check(bf.throne.plane_id.endswith("throne_room"), "throne plane id namespaced")


def test_gate_widths_and_staging():
    bf = build_battlefield()
    check(bf.plane.openings["main_gate"].passage_tiles >= 12, "main gate wide enough for many abreast")
    check(bf.plane.openings["west_gate"].passage_tiles >= 8, "west postern passage width")
    check(bf.plane.openings["east_gate"].passage_tiles >= 8, "east postern passage width")
    check(bf.plane.openings["north_gate"].passage_tiles >= 8, "north postern passage width")
    cap = staging_capacity(bf)
    check(cap["attacker_design_slots"] >= DESIGN_ATTACKERS, f"attacker slots {cap}")
    check(cap["defender_design_slots"] >= DESIGN_DEFENDERS, f"defender slots {cap}")


def test_walls_block_until_breach():
    bf = build_battlefield()
    start = bf.plane.spawn["attacker"]
    court = bf.plane.spawn["courtyard"]
    intact = {k: "intact" for k in bf.plane.openings}
    check(walkable(bf.plane, start[0], start[1], intact), "attacker spawn walkable")
    check(walkable(bf.plane, court[0], court[1], intact), "courtyard spawn walkable (not inside the keep)")
    check(not path_exists(bf.plane, start, court, intact), "intact curtain blocks the courtyard")


def test_each_gate_is_a_viable_entry():
    bf = build_battlefield()
    start = bf.plane.spawn["attacker"]
    court = bf.plane.spawn["courtyard"]
    for oid in ("main_gate", "west_gate", "east_gate", "north_gate"):
        states = {k: "intact" for k in bf.plane.openings}
        states[oid] = "destroyed"
        check(path_exists(bf.plane, start, court, states), f"{oid} alone opens a path into the courtyard")
    for oid in ("west_wall_breach", "east_wall_breach", "north_west_breach", "south_east_breach"):
        states = {k: "intact" for k in bf.plane.openings}
        states[oid] = "destroyed"
        check(path_exists(bf.plane, start, court, states), f"{oid} is a meaningful perimeter breach")
    damaged = {k: "damaged" for k in bf.plane.openings}
    check(not path_exists(bf.plane, start, court, damaged), "damaged openings stay blocked")


def test_lanes_reach_their_gates():
    bf = build_battlefield()
    intact = {k: "intact" for k in bf.plane.openings}
    start = bf.plane.spawn["attacker"]
    north = bf.plane.spawn["attacker_north"]
    for oid, lane, origin in (
        ("main_gate", "center_lane", start),
        ("west_gate", "west_lane", start),
        ("east_gate", "east_lane", start),
        ("north_gate", "north_lane", north),
    ):
        gate = bf.plane.openings[oid].rect
        if oid == "main_gate":
            approach = ((gate[0] + gate[2]) // 2, gate[3] + 2)
        elif oid == "north_gate":
            approach = ((gate[0] + gate[2]) // 2, gate[1] - 2)
        elif oid == "west_gate":
            approach = (gate[0] - 2, (gate[1] + gate[3]) // 2)
        else:
            approach = (gate[2] + 2, (gate[1] + gate[3]) // 2)
        check(path_exists(bf.plane, origin, approach, intact), f"{lane} reaches {oid}")


def test_full_perimeter_routes():
    bf = build_battlefield()
    intact = {k: "intact" for k in bf.plane.openings}
    sp = bf.plane.spawn
    check(path_exists(bf.plane, sp["attacker"], sp["attacker_north"], intact), "south reaches north around the castle")
    check(path_exists(bf.plane, sp["attacker"], sp["ring_nw"], intact), "south reaches northwest ring")
    check(path_exists(bf.plane, sp["attacker"], sp["ring_ne"], intact), "south reaches northeast ring")
    check(path_exists(bf.plane, sp["ring_sw"], sp["ring_se"], intact), "south ring connects west to east")
    west_len = shortest_length(bf.plane, sp["attacker"], sp["attacker_north"], intact)
    check(west_len and west_len > 80, f"south-to-north ring travel is substantial ({west_len})")
    # Keep sits inside the courtyard: there is battlefield north of the north wall,
    # and the keep itself is south of WALL_N.
    check(KEEP_RECT[1] > WALL_N, "keep does not sit on the northern map edge")
    check(sp["attacker_north"][1] < WALL_N, "north staging is outside the north wall")
    check(walkable(bf.plane, sp["attacker_north"][0], sp["attacker_north"][1], intact), "north staging walkable")


def test_keep_does_not_seal_north():
    bf = build_battlefield()
    open_main = {k: "intact" for k in bf.plane.openings}
    open_main["main_gate"] = "destroyed"
    court = bf.plane.spawn["courtyard"]
    inner = bf.plane.spawn["north_inner"]
    check(walkable(bf.plane, inner[0], inner[1], open_main), "north inner passage walkable")
    check(path_exists(bf.plane, court, inner, open_main), "courtyard reaches north inner passage around the keep")
    check(inner[1] < KEEP_RECT[1], "north inner passage is north of the keep")
    check(court[1] > KEEP_RECT[3], "courtyard spawn is south of the keep")


def test_defender_wall_circuit():
    bf = build_battlefield()
    intact = {k: "intact" for k in bf.plane.openings}
    # A wall-walk tile near the northwest inner corner
    ww, wn, we, ws = bf.wall_box
    a = (ww + 5, wn + 5)
    b = (we - 5, wn + 5)
    c = (we - 5, ws - 5)
    check(bf.plane.cell(*a) == "H", f"NW wall-walk present ({bf.plane.cell(*a)})")
    check(path_exists(bf.plane, a, b, intact), "wall-walk reaches opposite north tower")
    check(path_exists(bf.plane, a, c, intact), "wall-walk circuits to the southeast despite intact gates")
    court = bf.plane.spawn["courtyard"]
    check(path_exists(bf.plane, court, a, intact), "courtyard stairs reach the wall-walk")


def test_courtyard_reaches_keep_and_stations():
    bf = build_battlefield()
    open_keep = {k: "intact" for k in bf.plane.openings}
    open_keep["keep_doors"] = "destroyed"
    court = bf.plane.spawn["courtyard"]
    keep = bf.plane.spawn["keep_door"]
    check(path_exists(bf.plane, court, keep, open_keep), "courtyard reaches opened keep doors")
    heal = bf.plane.landmarks["heal_defend"].rect
    hx, hy = (heal[0] + heal[2]) // 2, (heal[1] + heal[3]) // 2
    check(path_exists(bf.plane, court, (hx, hy), open_keep), "defender heal reachable")


def test_throne_nave():
    bf = build_battlefield()
    entrance = bf.throne.spawn["entrance"]
    dais = bf.throne.spawn["dais"]
    states = {"throne_doors": "destroyed"}
    check(path_exists(bf.throne, entrance, dais, states), "nave reaches the dais")
    blocked = {"throne_doors": "intact"}
    inner = (entrance[0], entrance[1] - 4)
    check(walkable(bf.throne, inner[0], inner[1], blocked), "hall interior walkable")


def test_scale_travel():
    bf = build_battlefield()
    report = scale_report(bf)
    check(report["attacker_to_gate_tiles"] and report["attacker_to_gate_tiles"] >= 40,
          f"approach has substantial length ({report})")
    check(report["attacker_to_gate_seconds"] >= 6, "travel time is not a hop")
    check(report["south_to_north_via_west_tiles"] and report["south_to_north_via_west_tiles"] >= 80,
          "south-to-north design distance is generous")
    print("scale_report", report)


def test_independent_load():
    bf = build_battlefield()
    reached = bfs(bf.plane, bf.plane.spawn["attacker"], {k: "destroyed" for k in bf.plane.openings})
    check(len(reached) > 5000, f"open map has a large reachable component ({len(reached)})")
    d = shortest_length(
        bf.plane, bf.plane.spawn["attacker"], bf.plane.spawn["courtyard"],
        {**{k: "intact" for k in bf.plane.openings}, "main_gate": "destroyed"},
    )
    check(d is not None and d > 0, f"shortest courtyard path {d}")


def test_engine_placement_all_sides_and_rejects():
    bf = build_battlefield()
    placed = sample_perimeter_layout(bf)
    kinds = {e.engine_type for e in placed}
    check(len(placed) >= 8, f"demo layout placed several independent engines ({len(placed)})")
    check({"ram", "trebuchet", "siege_tower", "ladder"} <= kinds, f"all four engine types present {kinds}")
    sides_hit = set()
    ww, wn, we, ws = bf.wall_box
    for e in placed:
        cx = e.x + e.size()[0] // 2
        cy = e.y + e.size()[1] // 2
        if cy > ws:
            sides_hit.add("south")
        elif cy < wn:
            sides_hit.add("north")
        elif cx < ww:
            sides_hit.add("west")
        elif cx > we:
            sides_hit.add("east")
    check(sides_hit == {"south", "north", "west", "east"}, f"engines on all four sides ({sides_hit}) {[(e.engine_type,e.x,e.y) for e in placed]}")

    keep = bf.keep_rect
    bad_keep = validate_placement(bf, "trebuchet", keep[0] + 2, keep[1] + 2, 0, placed)
    check(not bad_keep.ok, f"reject keep {bad_keep.reason}")
    interior = bf.interior_rect
    bad_court = validate_placement(bf, "ram", interior[0] + 4, interior[1] + 4, 0, placed)
    check(not bad_court.ok, f"reject courtyard {bad_court.reason}")
    bad_oob = validate_placement(bf, "ladder", -2, 10, 0, placed)
    check(not bad_oob.ok, "reject out of bounds")
    # Overlap the first engine
    first = placed[0]
    bad_overlap = validate_placement(bf, first.engine_type, first.x, first.y, first.rotation, placed)
    check(not bad_overlap.ok, f"reject overlap {bad_overlap.reason}")
    # Water if a ditch tile exists
    water = None
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if bf.plane.cell(x, y) == "~":
                water = (x, y)
                break
        if water:
            break
    check(water is not None, "flank ditches exist")
    bad_water = validate_placement(bf, "trebuchet", water[0], water[1], 0, placed)
    check(not bad_water.ok, f"reject water {bad_water.reason}")

    # Stations are examples, not exclusive slots: some engine should sit away from station rects
    stations = [bf.plane.landmarks[k].rect for k in ("heal_attack", "eng_attack", "res_attack")]
    def in_station(e):
        for rec in stations:
            if rec[0] <= e.x <= rec[2] and rec[1] <= e.y <= rec[3]:
                return True
        return False
    check(any(not in_station(e) for e in placed), "engines are not confined to station coordinates")

    # Ring remains circulable
    sp = bf.plane.spawn
    check(ring_still_clear(bf, placed, sp["ring_sw"], sp["ring_ne"], sp["ring_nw"]),
          "placed engines leave the ring route clear")


def test_variable_extra_placement():
    bf = build_battlefield()
    first = sample_perimeter_layout(bf)
    extra = find_valid_on_side(bf, "trebuchet", "south", first, rotation=0)
    check(extra is not None, "another trebuchet can still be placed — sample is not a cap")
    item, res = place(bf, "trebuchet", extra[0], extra[1], extra[2], first)
    check(item is not None and res.ok, f"extra placement ok {res.reason}")
    # A second independent layout size is allowed to differ; we only document counts
    print("sample_count", len(first), "with_extra", len(first) + 1)


def test_walk_tour():
    bf = build_battlefield()
    legs = build_tour(bf)
    names = [n for n, _, _ in legs]
    check("south_staging" in names and "north_via_west" in names, f"tour includes south-to-north {names}")
    check("courtyard_via_gate" in names and "north_inner_passage" in names, "tour includes gate to courtyard")
    for name, path, states in legs:
        check(len(path) >= 1, f"{name} has a path")
        if name != "south_staging":
            check(len(path) > 1 or path[0] == path[-1], f"{name} path recorded")
        check(walkable(bf.plane, path[-1][0], path[-1][1], states), f"{name} destination walkable")
    west = next(p for n, p, _ in legs if n == "north_via_west")
    check(len(west) > 40, f"south-to-north walk is a real route ({len(west)} steps)")
    court = next(p for n, p, _ in legs if n == "courtyard_via_gate")
    check(len(court) > 10, f"gate-to-courtyard walk exists ({len(court)} steps)")
    # Direct helper
    intact = {k: "intact" for k in bf.plane.openings}
    p = shortest_path(bf.plane, bf.plane.spawn["attacker"], bf.plane.spawn["ring_ne"], intact)
    check(p and len(p) > 40, "eastward ring path reconstructs")


def test_visual_anchors():
    from kings_castle_siege_map.world_view import camera_origin, visual_scale, world_to_screen
    scale = visual_scale()
    check(1.5 <= scale["player_h_tiles"] <= 2.2, f"player height in tiles {scale}")
    check(2.0 <= scale["ram_to_player_w"] <= 5.5, f"ram vs player width {scale}")
    check(scale["tex_tiles"] <= 8, "ground texture repeats over a few tiles, not a giant plate")
    sx, sy = world_to_screen((10.0, 20.0), 8, 10.0, 20.0)
    check((sx, sy) == (0, 0), "world_to_screen origin maps to 0,0")
    sx, sy = world_to_screen((10.0, 20.0), 8, 12.0, 21.0)
    check((sx, sy) == (16, 8), f"world_to_screen step {sx,sy}")
    origin = camera_origin((50, 60), 10, (200, 100))
    # player centered: origin.x = 50 - 10 + 0.5 = 40.5
    check(abs(origin[0] - 40.5) < 0.01 and abs(origin[1] - 55.5) < 0.01, f"camera origin {origin}")
    from kings_castle_siege_map.world_view import (
        _east_face_runs, _gate_tiles, _structure_tiles, _west_face_runs,
    )
    from kings_castle_siege_map.layout import build_battlefield
    bf = build_battlefield()
    skip = _structure_tiles(bf) | _gate_tiles(bf)
    west = _west_face_runs(bf, skip)
    east = _east_face_runs(bf, skip)
    check(len(west) >= 2, f"west curtain split around postern {len(west)}")
    check(len(east) >= 2, f"east curtain split around postern {len(east)}")
    check(min(r[0] for r in west) <= bf.wall_box[0] + 1, f"west face x {west[:3]}")
    check(max(r[0] for r in east) >= bf.wall_box[2] - 1, f"east face x {east[:3]}")


def test_chunk_projection_is_continuous():
    """Adjacent chunk corners must map to adjacent pixels for fractional origins."""
    from kings_castle_siege_map.world_view import CHUNK, world_to_screen
    for ox, oy, tp in ((41.93, 140.2, 28), (70.15, 148.4, 32), (0.3, 0.7, 20), (10.0, 20.0, 8)):
        for x in range(0, 128, CHUNK):
            a = world_to_screen((ox, oy), tp, x, 100)
            b = world_to_screen((ox, oy), tp, x + CHUNK, 100)
            check(b[0] - a[0] == CHUNK * int(tp), f"gap/overlap x={x} origin={ox} tp={tp} {b[0]-a[0]}")
        for y in range(0, 128, CHUNK):
            a = world_to_screen((ox, oy), tp, 80, y)
            b = world_to_screen((ox, oy), tp, 80, y + CHUNK)
            check(b[1] - a[1] == CHUNK * int(tp), f"gap/overlap y={y} origin={oy} tp={tp} {b[1]-a[1]}")


def test_m3_renderer_frame():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map.world_view import LAST_METRICS, render_world
    from kings_castle_siege_map.placement import sample_perimeter_layout
    bf = build_battlefield()
    engines = sample_perimeter_layout(bf)
    surf = render_world(
        bf, bf.plane.spawn["main_gate_south"], engines,
        "test", "test frame", size=(800, 450), tile_px=16, facing="n",
    )
    check(surf.get_size() == (800, 450), "m3 renderer surface size")
    check(LAST_METRICS.get("total_ms", 0) >= 0, f"metrics recorded {LAST_METRICS}")
    check(LAST_METRICS.get("draw_items", 0) > 10, f"layered draw items {LAST_METRICS}")


def test_angled_projection_roundtrip():
    from kings_castle_siege_map.angled_proj import project, unproject, pick_tile, depth_of
    origin = (40.0, 80.0)
    scale = 28.0
    so = (800.0, 450.0)
    for x, y, z in ((40.0, 80.0, 0.0), (55.5, 91.25, 0.0), (10.0, 200.0, 3.5), (139.4, 191.1, 0.0)):
        sx, sy, d = project(x, y, z, origin, scale, so)
        ux, uy = unproject(sx, sy, origin, scale, so, z)
        check(abs(ux - x) < 1e-6 and abs(uy - y) < 1e-6, f"roundtrip {(x,y,z)} -> {(ux,uy)}")
    # A tile south of the look-at is nearer the SSW camera (smaller depth).
    d_south = depth_of(40.0, 90.0, origin)
    d_north = depth_of(40.0, 70.0, origin)
    check(d_south < d_north, f"south closer than north {d_south} {d_north}")
    tx, ty = pick_tile(so[0], so[1], origin, scale, so, 0.0)
    check(tx == 40 and ty == 80, f"pick center {tx,ty}")


def test_angled_renderer_and_invalidation():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map.angled_view import LAST_METRICS, render_world, _face_cache, _view_cache
    from kings_castle_siege_map.placement import sample_perimeter_layout
    bf = build_battlefield()
    engines = sample_perimeter_layout(bf)
    intact = {k: "intact" for k in bf.plane.openings}
    destroyed = dict(intact)
    destroyed["main_gate"] = "destroyed"
    _face_cache.clear()
    _view_cache.clear()
    a = render_world(bf, (139, 191), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=intact)
    check(a.get_size() == (800, 450), "angled frame size")
    n_intact = LAST_METRICS.get("faces", 0)
    b = render_world(bf, (139, 188), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=destroyed)
    n_dest = LAST_METRICS.get("faces", 0)
    check(n_intact > 50 and n_dest > 50, f"faces intact={n_intact} dest={n_dest}")
    # Destroying the gate changes the cached static mesh.
    check(len(_face_cache) >= 2, f"gate state invalidates face cache {_face_cache.keys()}")
    # A second camera position at the same zoom still produces a frame.
    c = render_world(bf, (70, 148), engines, "t", "t", size=(800, 450), tile_px=18, facing="e", gate_states=intact)
    check(c.get_size() == (800, 450), "west camera frame")
    # Common-camera baked assets: feet inside the sprite, world widths sane.
    from kings_castle_siege_map.angled_view import load_baked, _px_per_tile
    expected = {
        "gatehouse": (18.0, 40.0),
        "tower": (8.0, 18.0),
        "keep": (28.0, 60.0),
        "keep_open": (28.0, 60.0),
        "gatehouse_destroyed": (18.0, 40.0),
        "ram": (2.0, 8.0),
        "trebuchet": (2.0, 10.0),
    }
    for name, (lo, hi) in expected.items():
        img, meta = load_baked(name)
        ppt = _px_per_tile(meta)
        check(ppt > 8, f"{name} px/tile {ppt}")
        fpx, fpy = meta["foot_px"]
        check(0 <= fpx <= img.get_width() and 0 <= fpy <= img.get_height(), f"{name} foot {fpx,fpy} img {img.get_size()}")
        world_w = img.get_width() / ppt
        check(lo <= world_w <= hi, f"{name} world width {world_w} not in {lo,hi}")
    # Sliding atlas: first look is a full build; nearby steps hit or incrementally
    # refill exposed strips — they must not allocate a new layer or full-rebuild.
    from kings_castle_siege_map.angled_view import _view_cache as vc
    vc.clear()
    render_world(bf, (139, 186), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=intact)
    check(LAST_METRICS.get("cache_mode", -1) == 2, f"first look should full-rebuild {LAST_METRICS}")
    n_keys = len(vc)
    render_world(bf, (139, 187), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=intact)
    check(LAST_METRICS.get("cache_mode", 2) in (0, 1), f"adjacent tile should hit or incr {LAST_METRICS}")
    check(len(vc) == n_keys, "near step must not allocate another static layer")
    modes = []
    for y in range(185, 150, -1):
        render_world(bf, (139, y), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=intact)
        modes.append(int(LAST_METRICS.get("cache_mode", 2)))
    check(all(m != 2 for m in modes), f"walking 35 tiles must not full-rebuild {modes}")
    check(any(m == 1 for m in modes), f"walk should exercise incremental strip fill {modes}")
    render_world(bf, (48, 48), engines, "t", "t", size=(800, 450), tile_px=18, facing="n", gate_states=intact)
    check(LAST_METRICS.get("cache_mode", 0) == 2, f"long teleport should full-rebuild {LAST_METRICS}")



def test_replace_baked_swaps_visible_tower():
    """Hot-swapping a baked tower must invalidate the static view cache.

    Buildings are painted into `_view_cache`. Clearing only `_scale_cache`
    (the M24/M25 compare-harness bug) leaves a bit-identical world.
    """
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import json
    import numpy as np
    import pygame
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map import angled_view as V
    from kings_castle_siege_map.placement import sample_perimeter_layout
    from kings_castle_siege_map import art
    art.warmup()
    bf = build_battlefield()
    engines = sample_perimeter_layout(bf)
    intact = {k: "intact" for k in bf.plane.openings}
    rec = bf.plane.landmarks["sw_tower"].rect
    player = (int((rec[0] + rec[2]) / 2 + 2), int((rec[1] + rec[3]) / 2 + 10))
    size, tp = (720, 800), 36

    def grab():
        surf = V.render_world(bf, player, engines, "t", "t", size=size, tile_px=tp,
                              facing="n", gate_states=intact, markers=False)
        raw = pygame.image.tostring(surf, "RGB")
        return np.frombuffer(raw, dtype=np.uint8).reshape(size[1], size[0], 3).copy()

    base = grab()
    img, meta = V.load_baked("tower")
    raw = pygame.image.tostring(img, "RGBA")
    from PIL import Image
    im = Image.frombytes("RGBA", img.get_size(), raw)
    arr = np.array(im)
    vis = arr[:, :, 3] > 12
    arr[vis, 0] = 255
    arr[vis, 1] = 0
    arr[vis, 2] = 220
    mag = pygame.image.fromstring(arr.tobytes(), img.get_size(), "RGBA").convert_alpha()

    # stale path: mutate cache only
    V._baked["tower"] = (mag, meta)
    V._scale_cache.clear()
    stale = grab()
    hud = slice(58, size[1] - 56)
    stale_mad = float(np.abs(base[hud].astype(np.int16) - stale[hud].astype(np.int16)).mean())
    check(stale_mad < 0.05, f"stale inject should reuse static layer, MAD={stale_mad}")

    V.replace_baked("tower", mag, meta)
    fixed = grab()
    fixed_mad = float(np.abs(base[hud].astype(np.int16) - fixed[hud].astype(np.int16)).mean())
    check(fixed_mad > 8.0, f"replace_baked must change visible world, MAD={fixed_mad}")
    check(V.LAST_METRICS.get("cache_mode") == 2, f"swap should full-rebuild {V.LAST_METRICS}")

    # restore shipped default so later tests see M17 tower
    def_img = pygame.image.load(str(V.BAKED_DIR / "tower.png")).convert_alpha()
    def_meta = json.loads((V.BAKED_DIR / "tower.json").read_text())
    V.replace_baked("tower", def_img, def_meta)



def test_face_patch_lut_and_sky_skip_exact():
    """M27 perf: LUT face shading must equal the float32 formula; the per-frame
    sky fill may be skipped only because the static layer covers the viewport."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import numpy as np
    import cv2
    import pygame
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map import angled_view as V
    from kings_castle_siege_map.layout import walkable
    from kings_castle_siege_map.placement import sample_perimeter_layout
    bf = build_battlefield()
    intact = {k: "intact" for k in bf.plane.openings}
    br = dict(intact)
    br["main_gate"] = "destroyed"
    br["west_wall_breach"] = "destroyed"
    combos = set()
    for st in (intact, br):
        for f in V._collect_static_faces(bf, st):
            combos.add((f.tex, tuple(f.shade)))
    rng = np.random.RandomState(3)
    for tex, shade in sorted(combos):
        src = V._tex(tex)
        y0 = int(rng.randint(0, max(1, src.shape[0] - 64)))
        x0 = int(rng.randint(0, max(1, src.shape[1] - 64)))
        raw = np.ascontiguousarray(src[y0:y0 + 64, x0:x0 + 64])
        ref = np.clip(raw.astype(np.float32) * np.array(shade, dtype=np.float32), 0, 255).astype(np.uint8)
        got = cv2.LUT(raw, V._shade_lut(shade))
        check(np.array_equal(ref, got), f"LUT shade mismatch {tex} {shade}")
    engines = sample_perimeter_layout(bf)
    V._view_cache.clear()
    size = (1280, 800)
    world = (size[0], size[1] - 58 - 56)
    pos = [(139, 205)]
    x, y = pos[0]
    for _ in range(24):
        if walkable(bf.plane, x, y - 1, br):
            y -= 1
            pos.append((x, y))
    uncovered = 0
    for p_ in pos:
        V.render_world(bf, p_, engines, "t", "t", size=size, tile_px=22, facing="n", gate_states=br, markers=False)
        origin, so = V.camera_look(p_, world, 22.0)
        layer, corigin, cso, _ = list(V._view_cache.values())[-1]
        dsx, dsy = V._blit_offset(corigin, cso, origin, so, 22.0)
        bx, by = int(round(dsx)), int(round(dsy))
        if not (bx <= 0 and by <= 0 and bx + layer.get_width() >= world[0] and by + layer.get_height() >= world[1]):
            uncovered += 1
    check(uncovered == 0, f"static layer must cover viewport on walk frames ({uncovered} uncovered)")



def test_strip_refill_partial_patch_exact():
    """M28: thin strip refills shade only the texels a clip can sample; output must
    equal the full-patch path for random thin clips, and the check must detect an
    unsafe (negative) sampling margin."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import numpy as np
    import pygame
    pygame.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map import angled_view as V
    bf = build_battlefield()
    st = {k: "intact" for k in bf.plane.openings}
    br = dict(st)
    br["main_gate"] = "destroyed"
    br["west_wall_breach"] = "destroyed"
    faces = V._collect_static_faces(bf, st) + V._collect_static_faces(bf, br)
    W, H = 1792, 960

    def run(pad, trials, seed):
        saved = V._PATCH_PAD
        rng = np.random.RandomState(seed)
        bad = 0
        try:
            for _ in range(trials):
                f = faces[rng.randint(len(faces))]
                cx = 0.5 * (f.pts[0][0] + f.pts[2][0])
                cy = 0.5 * (f.pts[0][1] + f.pts[2][1])
                tp = float(rng.choice([16, 22, 32, 48]))
                origin = (cx + rng.uniform(-3, 3), cy + rng.uniform(-3, 3))
                so = (W * 0.5, H * 0.7)
                w = int(rng.choice([2, 3, 5, 9, 17, 36, 60]))
                h = int(rng.choice([2, 3, 7, 40, H]))
                x = int(np.clip(W * 0.5 + rng.randint(-200, 200), 0, W - w))
                y = int(rng.randint(0, H - h + 1))
                ref = np.full((W, H, 3), 37, np.uint8)
                got = ref.copy()
                V._PATCH_PAD = 10 ** 6  # forces the full-patch path
                V._blit_face(ref, f, origin, tp, so, (x, y, w, h))
                V._PATCH_PAD = pad
                V._blit_face(got, f, origin, tp, so, (x, y, w, h))
                bad += int(not np.array_equal(ref, got))
        finally:
            V._PATCH_PAD = saved
        return bad

    bad = run(V._PATCH_PAD, 160, 11)
    check(bad == 0, f"partial patch must equal full patch ({bad} mismatches)")
    sens = run(-2, 160, 11)
    check(sens > 0, f"equality check must detect an unsafe margin ({sens})")


def test_portal_depth_and_gate_state():
    """Doorway film holes would composite terrain; posterns must not be full-height timber slabs."""
    from pathlib import Path
    import numpy as np
    from PIL import Image
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((16, 16))
    from kings_castle_siege_map.angled_view import _portal_faces, load_baked
    from kings_castle_siege_map.layout import build_battlefield

    baked = Path("/workspace/kings_castle_siege/assets/baked_m9")

    def patch(name, box):
        arr = np.array(Image.open(baked / f"{name}.png").convert("RGBA"))
        h, w = arr.shape[:2]
        x0, y0, x1, y1 = box
        return arr[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]

    def interior_holes(alpha):
        h, w = alpha.shape
        exterior = np.zeros((h, w), dtype=bool)
        stack = []
        for x in range(w):
            if alpha[0, x] < 12:
                exterior[0, x] = True
                stack.append((0, x))
            if alpha[h - 1, x] < 12:
                exterior[h - 1, x] = True
                stack.append((h - 1, x))
        for y in range(h):
            if alpha[y, 0] < 12:
                exterior[y, 0] = True
                stack.append((y, 0))
            if alpha[y, w - 1] < 12:
                exterior[y, w - 1] = True
                stack.append((y, w - 1))
        while stack:
            y, x = stack.pop()
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not exterior[ny, nx] and alpha[ny, nx] < 12:
                    exterior[ny, nx] = True
                    stack.append((ny, nx))
        return int(((alpha < 12) & ~exterior).sum())

    def assert_opaque_doorway(name, box, want_wood=False):
        p = patch(name, box)
        vis = p[p[..., 3] >= 200]
        check(vis.size > 200, f"{name} doorway patch empty")
        holes = interior_holes(p[..., 3])
        check(holes == 0, f"{name} doorway has interior film holes ({holes})")
        rgb = vis[..., :3].astype(np.float32)
        std = float(rgb.std())
        check(std > 10.0, f"{name} doorway too flat (std={std:.2f})")
        if want_wood:
            wood = int(((rgb[:, 0] > rgb[:, 2] + 12) & (rgb[:, 0] > 85)).sum())
            check(wood > 40, f"{name} doorway lacks warm timber pixels ({wood})")

    # Lower-center of the gatehouse (recessed portal) and lower-right of the keep.
    assert_opaque_doorway("gatehouse", (0.42, 0.50, 0.60, 0.82), want_wood=True)
    assert_opaque_doorway("keep", (0.55, 0.70, 0.78, 0.96), want_wood=True)
    assert_opaque_doorway("keep_open", (0.55, 0.70, 0.78, 0.96), want_wood=False)
    # Destroyed main gate must be a see-through arched passage, not an opaque back wall.
    dest = patch("gatehouse_destroyed", (0.42, 0.50, 0.60, 0.82))
    dest_holes = interior_holes(dest[..., 3])
    check(dest_holes > 400, f"destroyed gatehouse should open through (holes={dest_holes})")
    dest_vis = dest[dest[..., 3] >= 200]
    check(dest_vis.size > 200, "destroyed gatehouse lost surrounding arch masonry")

    img_k, meta_k = load_baked("keep")
    img_o, meta_o = load_baked("keep_open")
    check(img_k.get_size() == img_o.get_size(), "keep/keep_open crop size must match for blit swap")
    check(abs(meta_k["foot_px"][0] - meta_o["foot_px"][0]) < 2 and abs(meta_k["foot_px"][1] - meta_o["foot_px"][1]) < 2,
          f"keep feet should match {meta_k['foot_px']} vs {meta_o['foot_px']}")

    bf = build_battlefield()
    for oid, side in (("west_gate", "w"), ("east_gate", "e"), ("north_gate", "n")):
        rec = bf.plane.openings[oid].rect
        intact = _portal_faces(rec, side, False)
        opened = _portal_faces(rec, side, True)
        timber_i = [f for f in intact if f.tex in {"timber", "door_wood"}]
        timber_o = [f for f in opened if f.tex in {"timber", "door_wood"}]
        masonry_i = [f for f in intact if f.tex == "masonry"]
        check(len(timber_i) >= 2, f"{oid} intact needs timber leaves ({len(timber_i)})")
        check(len(timber_o) == 0, f"{oid} destroyed must drop timber leaves ({len(timber_o)})")
        check(len(masonry_i) >= 4, f"{oid} needs masonry jambs/lintel ({len(masonry_i)})")
        check(len(opened) < len(intact), f"{oid} destroyed portal should be a subset")
        # Door leaves stay door-height, not a full curtain extrusion.
        for f in timber_i:
            zs = [pt[2] for pt in f.pts]
            check(max(zs) <= 6.2, f"{oid} timber taller than a door ({max(zs)})")

    start = bf.plane.spawn["attacker"]
    court = bf.plane.spawn["courtyard"]
    all_open = {k: "destroyed" for k in bf.plane.openings}
    check(path_exists(bf.plane, start, court, all_open), "destroyed gates stay pathable")
    intact_states = {k: "intact" for k in bf.plane.openings}
    check(not path_exists(bf.plane, start, court, intact_states), "intact gates still block")


if __name__ == "__main__":
    test_namespace_isolation()
    test_no_live_imports()
    test_bounds_and_grid()
    test_gate_widths_and_staging()
    test_walls_block_until_breach()
    test_each_gate_is_a_viable_entry()
    test_lanes_reach_their_gates()
    test_full_perimeter_routes()
    test_keep_does_not_seal_north()
    test_defender_wall_circuit()
    test_courtyard_reaches_keep_and_stations()
    test_throne_nave()
    test_scale_travel()
    test_independent_load()
    test_engine_placement_all_sides_and_rejects()
    test_variable_extra_placement()
    test_walk_tour()
    test_visual_anchors()
    test_chunk_projection_is_continuous()
    test_m3_renderer_frame()
    test_angled_projection_roundtrip()
    test_angled_renderer_and_invalidation()
    test_replace_baked_swaps_visible_tower()
    test_face_patch_lut_and_sky_skip_exact()
    test_strip_refill_partial_patch_exact()
    test_portal_depth_and_gate_state()
    print("kings_castle_siege M28 map tests ok")


