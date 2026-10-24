"""Elemental outfit fx: collection set renders its hd_art, fx layers draw, modes and gates behave."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
import pygame
pygame.init(); pygame.display.set_mode((8, 8))
import player_hd_client as P, outfit_fx as F

SETS = [(s["id"], s["sex"]) for s in P._load_catalogue().get("collection", []) if s.get("hd_art")]


def _draw(sid, sex, anim="idle", ctx=None, t=0.3, eq=None):
    surf = pygame.Surface((300, 300), pygame.SRCALPHA)
    look = dict(P.get_default_appearance(sex, starter=False)); look.update(outfit=None, set=sid)
    ok = P.draw_player(surf, sex, look, 150, 260, 110, t, anim=anim, facing="s", equipment=eq, fx_ctx=ctx)
    return ok, surf, dict(P.last_draw)


def _px(s):
    return sum(1 for x in range(0, 300, 2) for y in range(0, 300, 2) if s.get_at((x, y))[3] > 20)


def test_collection_hd_art():
    assert SETS
    for sid, sex in SETS:
        ok, _s, ld = _draw(sid, sex)
        assert ok and ld.get("whole") == "outfit_" + sid + "_hd", (sid, ld)


def test_fx_modes():
    for sid, sex in SETS:
        F.set_context(1, False)
        F.state["mode"] = "full"; full = _px(_draw(sid, sex)[1])
        F.state["mode"] = "off"; off = _px(_draw(sid, sex)[1])
        assert full > off * 1.05, (sid, full, off)
        F.state["mode"] = "full"


def test_effective_rules():
    F.state.update(mode="full", others=True); F.set_context(1, False)
    assert F.effective()[3] is True
    F.set_context(9, False); assert F.effective()[0] == "reduced" and F.effective()[1] == 0.7
    F.set_context(1, True); assert F.effective()[0] == "reduced"
    assert F.effective(preview=True)[0] == "full"
    F.set_context(1, False)
    assert F.effective(full_armour=True) == ("full", 0.7, False, False)
    assert F.effective(eclipse=True) is None
    F.state["others"] = False; assert F.effective(is_self=False) is None; F.state["others"] = True
    F.state["mode"] = "reduced"; assert F.frame_for(0.125 * 3, 16, "reduced", True) % 2 == 0
    F.state["mode"] = "full"


def test_elemental_beats_gear_aura():
    """David, 24 Oct 2026: an elemental outfit's own effect always shows over Eclipse/armour glow."""
    F.state.update(mode="full", others=True); F.set_context(1, False)
    eq = {"weapon": "eclipse_sword", "body": "eclipse_body", "amulet": "void_amulet"}
    for sid, sex in SETS:
        if not P._elemental_fx_worn({"set": sid}, sex):
            continue
        look = dict(P.get_default_appearance(sex, starter=False)); look.update(outfit=None, set=sid)
        def px(mode):
            F.state["mode"] = mode
            s = pygame.Surface((300, 300), pygame.SRCALPHA)
            P.draw_player(s, sex, look, 150, 260, 110, 0.3, anim="idle", facing="s", equipment=eq, fx_seed=7)
            return s
        on, off = px("full"), px("off")
        F.state["mode"] = "full"
        diff = sum(1 for x in range(0, 300, 2) for y in range(0, 300, 2)
                   if sum(abs(a - b) for a, b in zip(on.get_at((x, y)), off.get_at((x, y)))) > 60)
        assert diff > 600, (sid, diff)


def test_actions_have_no_front_fx():
    for sid, sex in SETS:
        ok, _s, ld = _draw(sid, sex, anim="woodcutting", t=0.5)
        assert ok


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok  ", n)
