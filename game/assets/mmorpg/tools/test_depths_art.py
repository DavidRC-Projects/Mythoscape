"""Depths crypt AI zone plates — whole-room floors + merges. Run: python3 tools/test_depths_art.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

# Zone rects match depths_map / depths_v2 payload styles.
_DEPTHS_ZONES = [
    ("chapel", "chapel", (13, 2, 45, 16)),
    ("ossuary", "ossuary", (5, 17, 59, 34)),
    ("catacombs", "catacomb", (1, 35, 59, 51)),
    ("tomb", "tomb", (0, 52, 59, 67)),
    ("mausoleum", "mausoleum", (12, 68, 52, 80)),
    ("wyrm", "wyrm", (1, 68, 11, 78)),
    ("arena", "arena", (13, 89, 53, 105)),
]


def test_zone_art_files_exist():
    zones = os.path.join(ROOT, "client", "assets", "depths", "zones")
    needed = (
        "chapel", "ossuary", "catacomb", "tomb", "mausoleum", "wyrm", "arena",
        "wall", "abyss", "bridge_deck", "bridge_rail",
    )
    for style in needed:
        path = os.path.join(zones, f"{style}.png")
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 10_000, path


def test_whole_room_floor_uv_and_merge():
    """Each room plate maps 1:1 across its zone; neighbours dissolve at the lip."""
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import depths_v2_client as dc

    zones = [
        {"id": zid, "name": zid, "band": "", "rect": list(rect), "style": style}
        for zid, style, rect in _DEPTHS_ZONES
    ]
    d = {"zones": zones, "v2": "depths"}
    assert dc._zone_bounds(d, "chapel") == (13, 2, 45, 16)
    sheet = dc._area_sheet("chapel", 32, dc._zone_bounds(d, "chapel"))
    assert sheet is not None
    assert sheet.get_width() == 33 * 32
    assert sheet.get_height() == 15 * 32

    assert dc.floor_style(d, 30, 16) == "chapel"
    assert dc.floor_style(d, 30, 17) == "ossuary"
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    assert dc._blit_area(surf, surf.get_rect(), "chapel", 30, 16, d=d)
    # Clamp: tile just south of chapel still reads chapel plate edge for dissolve.
    assert dc._blit_area(surf, surf.get_rect(), "chapel", 30, 17, d=d)
    dc._merge_areas(surf, surf.get_rect(), 30, 16, d, "chapel")


if __name__ == "__main__":
    test_zone_art_files_exist()
    test_whole_room_floor_uv_and_merge()
    print("test_depths_art: OK")
