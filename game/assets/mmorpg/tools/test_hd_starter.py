"""Starter outfit / HD look regressions (23 Oct 2026). Run: python3 tools/test_hd_starter.py
1 starter look: new accounts wear Villager / Village Lady, free, valid, hair kept
2 appearance kept on the self PLAYER_UPDATE mirror (walking flicker to the layered look)
3 stat screen layout never overlaps
4 HD idle strips hold one still pose and never reuse a walk frame"""
import glob, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import test_outfit_rules as R  # noqa: E402  (in-memory server + session helpers)
server, outfits = R.server, R.outfits
ART = os.path.join(ROOT, "..", "player_hd", "assets")
STARTER = {"male": "villager_coat", "female": "village_lady_gown"}


def test_starter_look_worn_free_and_valid():
    for sex, gown in STARTER.items():
        s = R.make(sex=sex)
        look = s.appearance_state()
        assert look.get("outfit") == gown, (sex, look)
        base = outfits.normalise(dict((outfits.catalogue().get("defaults") or {}).get(sex) or {}))
        assert look.get("hair") == base.get("hair"), "starter must keep the player's own hair (set hair is a shop item)"
        # saving the look you were given must pass ownership with nothing owned
        R.run(server.handle_update_appearance(s, {"appearance": look}))
        assert not R.errors(s), R.errors(s)
        assert s.appearance_state().get("outfit") == gown
        for pid in outfits.sets()[outfits.starter_set(sex)]["pieces"]:
            assert outfits.items()[pid].get("starter"), pid


def test_partial_armour_keeps_starter_outfit():
    s = R.make(sex="female")
    R.wear_kit(s, {"body": "mythos_body"})
    assert s.appearance_state().get("outfit") == STARTER["female"], "partial armour keeps the painted outfit"


def test_full_set_tier_and_never_layered():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import pygame, player_hd_client as P
    pygame.init(); pygame.display.set_mode((8, 8))
    T = P.full_armour_tier
    assert T({"helmet": "bronze_helmet", "body": "bronze_body", "legs": "bronze_legs"}) == "bronze"
    assert T({"helmet": "bronze_helmet", "body": "bronze_chainbody", "legs": "bronze_chainlegs", "shield": "iron_shield"}) == "bronze"
    assert T({"helmet": "bronze_helmet", "body": "iron_body", "legs": "bronze_legs"}) is None
    assert T({"helmet": "mythos_helmet", "body": "mythos_body", "legs": "mythos_legs"}) == "mythos"
    assert T({"body": "bronze_body", "legs": "bronze_legs"}) is None
    assert T({"helmet": "recruit_bronze_helmet", "body": "recruit_bronze_body", "legs": "recruit_bronze_legs"}) == "bronze"
    kits = [{"helmet": "iron_helmet"}, {"shield": "bronze_shield", "weapon": "bronze_sword"},
            {"helmet": "steel_helmet", "body": "iron_body", "legs": "mithril_legs"},
            {"helmet": "bronze_helmet", "body": "bronze_body", "legs": "bronze_legs"}]
    for sex in ("female", "male"):
        for eq in kits:
            for anim in ("idle", "walk", "melee", "chop"):
                surf = pygame.Surface((160, 160), pygame.SRCALPHA)
                P.draw_player(surf, sex, None, 80, 140, 48, 0.4, anim=anim, progress=0.5, facing=1, equipment=eq)
                w = P.last_draw.get("whole")
                assert w, (sex, eq, anim, "fell back to the layered doll")
                exp = P.armour_layer_for(sex, eq)   # body+legs set (bare-head art) or the helmeted full set
                if exp:
                    assert w == exp, (sex, eq, anim, w)
                else:
                    assert not w.startswith("armour_"), (sex, eq, anim, w)


def test_missing_action_strip_holds_idle_not_doll():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import pygame, player_hd_client as P
    pygame.init(); pygame.display.set_mode((8, 8))
    real = P._whole_anim_present
    P._whole_anim_present = lambda sex, layer, anim: anim in ("idle", "walk")
    try:
        for sex in ("female", "male"):
            for eq in ({}, {"shield": "bronze_shield", "weapon": "bronze_sword"},
                       {"helmet": "bronze_helmet", "body": "bronze_body", "legs": "bronze_legs", "weapon": "bronze_axe"}):
                for anim in ("melee", "chop", "mine"):
                    surf = pygame.Surface((160, 160), pygame.SRCALPHA)
                    P.draw_player(surf, sex, None, 80, 140, 48, 0.4, anim=anim, progress=0.5, facing=1, equipment=eq)
                    assert P.last_draw.get("whole"), (sex, eq, anim, "fell back to the layered doll")
    finally:
        P._whole_anim_present = real


def test_self_mirror_keeps_appearance():
    sys.path.insert(0, os.path.join(ROOT, "client")); os.chdir(os.path.join(ROOT, "client"))
    import client
    g = client.GameClient()
    look = {"outfit": "village_lady_gown", "hair": "hair_bun"}
    g.players[7] = {"id": 7, "name": "Ann", "appearance": look, "hd_player": True, "x": 1, "y": 1}
    g.process_message({"type": "PLAYER_UPDATE", "player": {"id": 7, "name": "Ann", "x": 2, "y": 1, "hp": 10,
                                                           "max_hp": 10, "equipment": {}}})
    pub = g.players[7]
    assert pub.get("appearance") == look and pub.get("hd_player") is True, pub
    assert pub["x"] == 2


def test_stat_layout_no_overlap():
    import pygame
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import client_screens as cs
    for n in range(1, 5):
        L = cs.stat_alloc_layout(1200, n)
        rects = L["presets"] + [L["confirm"]]
        screen = pygame.Rect(0, 0, 1200, 800)
        for i, a in enumerate(rects):
            assert screen.contains(a), (n, a)
            for b in rects[i + 1:]:
                assert not a.colliderect(b), (n, a, b)
        assert L["hint_y"] + 16 <= L["tip_y"] and L["tip_y"] + 16 <= L["preset_y"]
        assert L["preset_y"] + 32 <= L["confirm"].top and L["confirm"].bottom <= L["err_y"] < L["login_err_y"] < 800


def test_idle_is_still_and_never_a_walk_frame():
    import pygame
    checked = 0
    for idle in glob.glob(os.path.join(ART, "*", "[12]x", "outfit_*_hd", "idle_[sen].png")):
        walk = idle.replace("idle_", "walk_")
        if not os.path.isfile(walk):
            continue
        a, w = pygame.image.load(idle), pygame.image.load(walk)
        fw = a.get_height()
        idle_f = [pygame.image.tostring(a.subsurface((i * fw, 0, fw, fw)), "RGBA") for i in range(a.get_width() // fw)]
        walk_f = {pygame.image.tostring(w.subsurface((i * fw, 0, fw, fw)), "RGBA") for i in range(w.get_width() // fw)}
        assert len(set(idle_f)) == 1, f"idle moves: {idle}"
        assert idle_f[0] not in walk_f, f"idle is a walk frame: {idle}"
        checked += 1
    assert checked >= 14 * 3 * 2, checked


def test_whole_figure_action_routing():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import player_hd_client as P
    assert P._whole_anim_for("melee", 3, 0, {"weapon": "bronze_axe"}) == ("melee_axe", 3)
    assert P._whole_anim_for("melee", 3, 0, {"weapon": "bronze_sword"}) == ("melee_sword", 3)
    assert P._whole_anim_for("melee", 0, 0, {"weapon": "bronze_pickaxe"})[0] == "melee_sword"
    seen = {P._whole_anim_for("chop", 0, i * 0.05, {})[1] for i in range(40)}
    assert seen == set(range(8)), seen
    assert P._whole_anim_for("fish_net", 0, 0.1, {})[0] == "fish"
    assert P._whole_anim_for("walk", 5, 0, {}) == ("walk", 5)


def test_starter_action_strips_present():
    want = ["melee_sword", "melee_axe", "chop", "mine", "fish"]
    for sex, layer in (("female", "outfit_village_lady_hd"), ("male", "outfit_villager_hd")):
        for res in ("1x", "2x"):
            for a in want:
                for f in "sen":
                    for suf in ("", "_skin"):
                        p = os.path.join(ART, sex, res, layer, f"{a}_{f}{suf}.png")
                        assert os.path.isfile(p), p


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for t in tests:
        try:
            t(); print("ok  ", t.__name__)
        except Exception as e:
            bad += 1; print("FAIL", t.__name__, repr(e)[:300])
    print(f"{len(tests) - bad}/{len(tests)} hd starter tests passed")
    sys.stdout.flush(); os._exit(1 if bad else 0)
