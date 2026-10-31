"""Regression: Equipment screen with a high-level, fully equipped account (David's live bug, 30 Oct 2026).

On a real macOS (cocoa) window the display format has an alpha mask, so a flagless pygame.Surface((w, h))
inherited it and the window drew see-through: empty slots, no doll, no text, only outlines and bars.
Throwaway server (free port, temp DB); never 8765 or the live world.db.
  * cocoa_alpha_format: flagless Surfaces are forced to carry an alpha mask (what cocoa does); the panel
    must still be opaque, show the doll, the item icons and the title text
  * font_missing: the bundled fonts are unreachable (other cwd / app bundle); text still draws
  * section_failure: one section raising is logged and the rest of the panel still draws
Set EQ_SHOTS=<dir> to save screenshots.
"""
import os, sys, json, sqlite3, tempfile, importlib.util, logging
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("_eqs", os.path.join(ROOT, "tools", "test_equipment_screen.py"))
EQ = importlib.util.module_from_spec(spec); spec.loader.exec_module(EQ)
check, RESULTS = EQ.check, EQ.RESULTS
GEAR = {"weapon": "mythos_longsword", "shield": "mythos_shield", "body": "mythos_body", "legs": "mythos_legs",
        "helmet": "mythos_helmet", "amulet": "void_amulet", "ammo": "arrow_quiver", "ring": "onyx_ring"}
XP = {"attack_xp": 294322, "strength_xp": 905876, "defence_xp": 307618, "karma_xp": 4680, "archery_xp": 820}
ST = {}


def make_account():
    port = EQ._na.free_port()
    db = os.path.join(tempfile.mkdtemp(prefix="eqhl_srv_"), "world.db")
    EQ._na.start_server(port, db)
    os.chdir(EQ.CLI)
    g = EQ.register(port, "eqhigh"); g.logout(); EQ.pump(g, 60)
    c = sqlite3.connect(db)
    pid = c.execute("SELECT id FROM players WHERE username='eqhigh'").fetchone()[0]
    for k, v in GEAR.items():
        c.execute(f"UPDATE players SET equip_{k}=? WHERE id=?", (v, pid))
    for k, v in XP.items():
        c.execute(f"UPDATE players SET {k}=? WHERE id=?", (v, pid))
    c.execute("UPDATE players SET quiver_contents=? WHERE id=?", (json.dumps({"bronze_arrow": 176}), pid))
    c.commit(); c.close()
    g = EQ.login(port, "eqhigh")
    assert all(g.player["equipment"].get(k) == v for k, v in GEAR.items()), g.player["equipment"]
    assert g.player_combat_level() >= 100, g.player_combat_level()
    ST["g"] = g


class _AlphaSurface:
    """Patch pygame.Surface so flagless surfaces carry an alpha mask, exactly like a cocoa display."""
    def __enter__(self):
        import pygame
        self.orig = pygame.Surface
        orig = self.orig
        def S(size, flags=0, depth=0, masks=None):
            if masks is None and depth == 0 and not (flags & pygame.SRCALPHA):
                return orig(size, flags, 32, (0xFF0000, 0xFF00, 0xFF, 0xFF000000))
            return orig(size, flags, depth, masks) if masks is not None else (orig(size, flags, depth) if depth else orig(size, flags))
        pygame.Surface = S
        return self
    def __exit__(self, *a):
        import pygame
        pygame.Surface = self.orig


def _render(g, tag):
    import pygame, equipment_ui_v2 as E
    g.show_equipment = True
    g.__dict__.pop("_equip_canvas", None)
    g.screen.fill((0, 255, 0))                       # loud backdrop: any see-through pixel shows green
    from content import ITEMS, karma_slot_bonus
    E.draw(g, ITEMS, karma_slot_bonus)
    if EQ.SHOTS:
        os.makedirs(EQ.SHOTS, exist_ok=True); pygame.image.save(g.screen, os.path.join(EQ.SHOTS, f"hl_{tag}.png"))
    return E, E._equip_layout if hasattr(E, "_equip_layout") else g._equip_layout


def _assert_full_panel(g):
    import equipment_ui_v2 as E
    L = g._equip_layout; vp = L["vp"]
    box = pygame_rect(vp.x + L["ox"], vp.y + L["oy"], L["w"], L["h"])
    scr = g.screen
    green = sum(1 for x in range(box.x + 4, box.right - 4, 6) for y in range(box.y + 4, box.bottom - 4, 6)
                if scr.get_at((x, y))[:3] == (0, 255, 0))
    assert green == 0, f"{green} see-through pixels inside the equipment window"
    s = L["scale"]
    def region(r):
        return pygame_rect(box.x + int(r.x * s), box.y + int(r.y * s), max(1, int(r.w * s)), max(1, int(r.h * s)))
    def distinct(r):
        rr = region(r); cols = set()
        for x in range(rr.x, rr.right, 2):
            for y in range(rr.y, rr.bottom, 2):
                cols.add(tuple(scr.get_at((x, y))[:3]))
        return len(cols)
    assert distinct(E.FIGURE_BOX) > 60, ("no paper doll", distinct(E.FIGURE_BOX))
    assert distinct(E.TITLE_RECT) > 25, ("no title text", distinct(E.TITLE_RECT))
    for slot in ("helmet", "body", "weapon", "shield"):
        assert distinct(E.slot_rects()[slot]) > 25, ("empty-looking slot", slot)


def pygame_rect(*a):
    import pygame
    return pygame.Rect(*a)


def test_cocoa_alpha_format():
    g = ST["g"]
    with _AlphaSurface():
        _render(g, "cocoa_alpha")
        assert g._equip_canvas.get_masks()[3] == 0, "canvas must be opaque RGB"
        _assert_full_panel(g)


def test_font_missing():
    import equipment_ui_v2 as E
    g = ST["g"]; saved = (E._FONT_DIR, dict(E._FONTS))
    try:
        E._FONT_DIR = os.path.join(tempfile.mkdtemp(), "no_fonts_here"); E._FONTS.clear()
        cwd = os.getcwd(); os.chdir(tempfile.gettempdir())   # launched from somewhere else
        try:
            with _AlphaSurface():
                _render(g, "font_missing")
                _assert_full_panel(g)
        finally:
            os.chdir(cwd)
    finally:
        E._FONT_DIR = saved[0]; E._FONTS.clear(); E._FONTS.update(saved[1])


def test_section_failure_logged():
    import equipment_ui_v2 as E
    g = ST["g"]; orig = E._draw_right; seen = []
    h = logging.Handler(); h.emit = lambda rec: seen.append(rec.getMessage())
    E.LOG.addHandler(h)
    def boom(*a, **k):
        raise KeyError("unmapped_item_xyz")
    E._draw_right = boom
    try:
        _render(g, "section_failure")
        _assert_full_panel(g)                         # left side, title, doll still drawn; nothing see-through
        assert any("right failed" in m and "unmapped_item_xyz" in m for m in seen), seen
    finally:
        E._draw_right = orig; E.LOG.removeHandler(h)


def main():
    import pygame
    pygame.init()
    check("high_level_account_logged_in", make_account)
    if "g" in ST:
        check("cocoa_alpha_format_opaque_full_panel", test_cocoa_alpha_format)
        check("font_missing_falls_back", test_font_missing)
        check("section_failure_logged_rest_drawn", test_section_failure_logged)
    n = sum(1 for r in RESULTS if r[1])
    print(f"{n}/{len(RESULTS)} equipment high-level tests passed", flush=True)
    os._exit(0 if n == len(RESULTS) == 4 else 1)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("EQUIPMENT HIGH-LEVEL TEST FAILED", flush=True); os._exit(1)
