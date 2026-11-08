"""Void Sanctum AI zone plates + Narrow Way bridge. Run: python3 tools/test_void_art.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

import void_v2  # noqa: E402


def test_zone_art_files_exist():
    zones = os.path.join(ROOT, "client", "assets", "void", "zones")
    needed = (
        "entry", "gallery", "barracks", "crystal", "rift", "arena", "bridge",
        "wall", "abyss", "bridge_deck", "bridge_rail",
    )
    for style in needed:
        path = os.path.join(zones, f"{style}.png")
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 10_000, path


def test_zone_styles_match_plates():
    styles = {z[4] for z in void_v2.ZONES}
    zones = os.path.join(ROOT, "client", "assets", "void", "zones")
    for style in styles:
        path = os.path.join(zones, f"{style}.png")
        assert os.path.isfile(path), f"missing plate for zone style {style}: {path}"


def test_narrow_way_bridge_geometry():
    """Walkable Narrow Way is 3-wide; visual deck is a little wider still."""
    b = void_v2.BRIDGE
    assert b["x"] == 32
    assert b.get("x0", 31) == 31 and b.get("x1", 33) == 33
    assert b["y0"] == 72 and b["y1"] == 84
    g = void_v2.build_grid()
    for y in range(b["y0"], b["y1"] + 1):
        for x in (31, 32, 33):
            assert g[y][x] in ("=", "a"), (x, y, g[y][x])
        # Just outside the span is abyss.
        for x in (29, 35):
            assert g[y][x] == "~", (x, y, g[y][x])


def test_client_extra_chasm_and_art():
    class Sess:
        dungeon = {
            "decor": {}, "zones": [], "lore": {}, "ground": {}, "tiles": [],
        }

    extra = void_v2.client_extra(Sess())
    assert extra.get("art_style") is True
    assert extra["chasm"]["pit"] == [12, 72, 52, 84]
    assert extra["chasm"]["deck"] == [30, 72, 34, 84]
    # Visual deck frames the walkable columns.
    assert extra["chasm"]["deck"][0] < void_v2.BRIDGE["x"] < extra["chasm"]["deck"][2]


def test_whole_room_floor_uv_and_merge():
    """Each room plate maps 1:1 across its zone; neighbours dissolve at the lip."""
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import void_v2_client as vc

    zones = [
        {"id": zid, "name": name, "band": band, "rect": list(rect), "style": style}
        for zid, name, band, rect, style in void_v2.ZONES
        if zid not in ("whisper", "bridge")
    ]
    d = {"zones": zones, "v2": True}
    # Entry hall UV origin
    assert vc._zone_bounds(d, "entry") == (12, 2, 41, 14)
    sheet = vc._area_sheet("entry", 32, vc._zone_bounds(d, "entry"))
    assert sheet is not None
    assert sheet.get_width() == 30 * 32
    assert sheet.get_height() == 13 * 32

    # Adjacent galleries tile samples a different plate; merge finds neighbour style.
    assert vc.floor_style(d, 32, 14) == "entry"
    assert vc.floor_style(d, 32, 15) == "gallery"
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    assert vc._blit_area(surf, surf.get_rect(), "entry", 32, 14, d=d)
    # Clamp: tile just south of entry still reads entry plate edge for dissolve.
    assert vc._blit_area(surf, surf.get_rect(), "entry", 32, 15, d=d)
    vc._merge_areas(surf, surf.get_rect(), 32, 14, d, "entry")


if __name__ == "__main__":
    test_zone_art_files_exist()
    test_zone_styles_match_plates()
    test_narrow_way_bridge_geometry()
    test_client_extra_chasm_and_art()
    test_whole_room_floor_uv_and_merge()
    print("test_void_art: OK")
