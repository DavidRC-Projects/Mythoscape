"""Every armour/weapon has a new 256px transparent icon; old icons load only as a fallback. Run: python3 tools/test_equip_icons.py"""
import os, sys, shutil, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server")); sys.path.insert(0, os.path.join(ROOT, "client"))
import pygame
pygame.display.init(); pygame.display.set_mode((8, 8))
from content import ITEMS
import realistic_item_icons as rii

SLOTS = {"helmet", "body", "legs", "weapon", "shield"}


def _equip():
    return [i for i, d in ITEMS.items() if d.get("equip_slot") in SLOTS]


def test_all_equippables_have_new_icons():
    bad = []
    for item in _equip():
        img = rii._raw(item)
        if img is None or img.get_size() != (256, 256):
            bad.append((item, None if img is None else img.get_size()))
        elif img.get_at((0, 0)).a != 0:
            bad.append((item, "opaque corner"))
    assert not bad, bad


def test_legacy_fallback_on_broken_file():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "legacy"))
        open(os.path.join(tmp, "bronze_sword.png"), "wb").write(b"not a png")
        shutil.copy(os.path.join(rii._LEGACY, "bronze_sword.png"), os.path.join(tmp, "legacy", "bronze_sword.png"))
        old = (rii._DIR, rii._LEGACY); rii._DIR, rii._LEGACY = tmp, os.path.join(tmp, "legacy"); rii._RAW.clear()
        img = rii._raw("bronze_sword")
        assert img is not None and img.get_size() == (128, 128), img
    finally:
        rii._DIR, rii._LEGACY = old; rii._RAW.clear(); shutil.rmtree(tmp)


def test_draw_in_slot_sizes():
    for size in (32, 36, 48, 64):
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for item in _equip():
            assert rii.draw_icon(s, s.get_rect(), item), item


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); n += 1; print("ok", name)
    print(f"{n}/{n} passed")
