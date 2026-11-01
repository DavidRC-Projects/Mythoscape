"""Boss duel mechanics: parry/counter windows, momentum meter, finisher unlock, ranged focus,
kiting/charge, and that soldier battles are untouched by duel mode."""
import copy
import os
import random
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "server"))
import arena_duel as D  # noqa: E402


def _windup(d, atk_id):
    a = next(x for x in D._boss(d)["attacks"] if x["id"] == atk_id)
    d["b"].update(state="windup", atk=a, t=a["windup"], guard=0)
    return a


def _until_land(d):
    while d["b"]["state"] == "windup" and not d["done"]:
        D.step(d)


def test_tuning_table_single_source():
    t = D.tuning(reload=True)
    for k in ("stamina", "momentum", "finisher", "styles", "bosses"):
        assert k in t
    assert set(t["styles"]) == {"sword", "axe", "bow"}
    assert set(t["bosses"]) == {"varro", "brutus", "crixus", "sabina", "ignatius", "unbroken"}


def test_parry_window_perfect_and_late():
    for left, perfect in ((1, True), (3, False)):
        d = D.new_duel("unbroken", "sword", seed=1)
        d["gap"] = 2.0
        _windup(d, "sun_slash")
        while d["b"]["t"] > left:
            D.step(d)
        D.act(d, "parry")
        _until_land(d)
        assert d["stats"]["parries"] == 1, left
        assert d["stats"]["perfect_parries"] == (1 if perfect else 0), left
        assert d["b"]["state"] == "stagger" and d["p"]["hp"] == 1.0
        assert d["p"]["counter"] > 0


def test_parry_too_early_gets_hit():
    d = D.new_duel("unbroken", "sword", seed=1)
    d["gap"] = 2.0
    _windup(d, "sun_slash")
    D.act(d, "parry")  # 4 steps early; window is 3
    _until_land(d)
    assert d["stats"]["parries"] == 0 and d["p"]["hp"] < 1.0


def test_unparryable_needs_dodge():
    d = D.new_duel("unbroken", "sword", seed=2)
    d["gap"] = 2.0
    _windup(d, "sun_sweep")
    while d["b"]["t"] > 1:
        D.step(d)
    D.act(d, "parry")
    _until_land(d)
    assert d["p"]["hp"] < 1.0
    d = D.new_duel("unbroken", "sword", seed=2)
    d["gap"] = 2.0
    d["p"]["wall"] = 0.0  # no room: pure i-frames
    _windup(d, "sun_sweep")
    while d["b"]["t"] > 1:
        D.step(d)
    D.act(d, "dodge")
    _until_land(d)
    assert d["p"]["hp"] == 1.0 and d["stats"]["perfect_dodges"] == 1


def test_counter_multiplies_next_hit():
    base = D.new_duel("varro", "sword", seed=3)
    base["gap"] = 2.0
    base["b"].update(state="recover", t=20)
    D.act(base, "light")
    D.step(base)
    plain = 1.0 - base["b"]["hp"]
    d = D.new_duel("varro", "sword", seed=3)
    d["gap"] = 2.0
    d["b"].update(state="recover", t=20)
    d["p"]["counter"] = 3
    D.act(d, "light")
    D.step(d)
    mult = D.tuning()["styles"]["sword"]["counter"]["mult"]
    assert abs((1.0 - d["b"]["hp"]) - plain * mult) < 1e-6


def test_momentum_gain_loss_and_cap():
    M = D.tuning()["momentum"]
    d = D.new_duel("unbroken", "sword", seed=4)
    D._mom(d, "perfect_parry")
    assert d["momentum"] == M["perfect_parry"]
    D._mom(d, "taken_hit")
    assert d["momentum"] == max(0, M["perfect_parry"] + M["taken_hit"])
    for _ in range(20):
        D._mom(d, "perfect_parry")
    assert d["momentum"] == M["max"]


def test_finisher_unlock_and_execute_melee():
    F = dict(D.tuning()["finisher"])
    F["boss_hp_frac"] = D.tuning()["bosses"]["unbroken"].get("finisher_hp", F["boss_hp_frac"])
    d = D.new_duel("unbroken", "sword", seed=5)
    d["b"].update(state="recover", t=50, second_wind_used=True)
    d["gap"] = 2.0
    d["b"]["hp"] = F["boss_hp_frac"] + 0.05
    d["momentum"] = 100
    D.step(d)
    assert not d["finisher_ready"]          # boss not low enough
    d["b"]["hp"] = F["boss_hp_frac"] - 0.01
    d["momentum"] = 50
    D.step(d)
    assert not d["finisher_ready"]          # crowd not with you
    d["momentum"] = 100
    D.step(d)
    assert d["finisher_ready"]
    D.act(d, "finish")
    D.step(d)
    assert d["done"] and d["won"] and d["finisher"] == "blade"


def test_finisher_needs_melee_reach_but_not_for_bow():
    d = D.new_duel("unbroken", "sword", seed=6)
    d["b"].update(state="recover", t=50, hp=0.1, second_wind_used=True)
    d["gap"], d["momentum"] = 4.0, 100
    D.step(d)
    D.act(d, "finish")
    D.step(d)
    assert not d["done"]
    b = D.new_duel("unbroken", "bow", seed=6)
    b["b"].update(state="recover", t=50, hp=0.1, second_wind_used=True)
    b["gap"], b["momentum"] = 6.0, 100
    b["p"]["focus"] = 0.2          # unsteady: the finishing shot needs focus (hold still)
    D.step(b)
    D.act(b, "finish")
    D.step(b)
    assert not b["done"]
    b["p"]["focus"] = 1.0
    D.act(b, "finish")
    D.step(b)
    assert b["done"] and b["won"] and b["finisher"] == "arrow"


def test_second_wind_locks_finisher_until_it_fires():
    d = D.new_duel("unbroken", "sword", seed=9)
    d["b"].update(state="recover", t=50, hp=0.1)
    d["gap"], d["momentum"] = 2.0, 100
    D.step(d)
    assert not d["finisher_ready"]
    d["b"]["second_wind_used"] = True
    d["momentum"] = 100
    D.step(d)
    assert d["finisher_ready"]


def test_second_wind_once():
    d = D.new_duel("unbroken", "sword", seed=7)
    d["b"].update(state="recover", t=50, hp=0.001)
    d["gap"] = 2.0
    D.act(d, "light")
    D.step(d)
    assert not d["done"] and d["b"]["second_wind_used"] and d["b"]["hp"] >= D.tuning()["bosses"]["unbroken"]["second_wind"] - 1e-6
    d["b"]["hp"] = 0.001
    d["p"]["busy"] = 0
    D.act(d, "light")
    for _ in range(3):
        D.step(d)
    assert d["done"] and d["won"]


def test_ranged_focus_builds_and_charged_shot_uses_it():
    S = D.tuning()["styles"]["bow"]
    d = D.new_duel("varro", "bow", seed=8)
    d["b"].update(state="recover", t=200)
    d["gap"] = 6.0
    for _ in range(int(1 / S["focus"]["per_step"]) + 2):
        D.step(d)
    assert d["p"]["focus"] == S["focus"]["max"]
    D.act(d, "heavy")
    for _ in range(S["heavy"]["windup"] + 2):
        D.step(d)
    full = 1.0 - d["b"]["hp"]
    e = D.new_duel("varro", "bow", seed=8)
    e["b"].update(state="recover", t=200)
    e["gap"] = 6.0
    D.act(e, "heavy")
    for _ in range(S["heavy"]["windup"] + 2):
        D.step(e)
    assert full > (1.0 - e["b"]["hp"]) * 1.5   # focused shot hits much harder
    assert e["p"]["focus"] < 0.5


def test_ranged_point_blank_penalty_and_moving_breaks_focus():
    d = D.new_duel("varro", "bow", seed=9)
    d["b"].update(state="recover", t=200)
    d["gap"] = 1.0
    D.act(d, "light")
    D.step(d)
    close = 1.0 - d["b"]["hp"]
    e = D.new_duel("varro", "bow", seed=9)
    e["b"].update(state="recover", t=200)
    e["gap"] = 4.0
    D.act(e, "light")
    D.step(e)
    assert close < (1.0 - e["b"]["hp"])
    f = D.new_duel("varro", "bow", seed=9)
    f["p"]["focus"] = 1.0
    D.act(f, "back")
    D.step(f)
    assert f["p"]["focus"] < 0.8


def test_kiting_dodges_out_of_reach_and_wall_stops_it():
    d = D.new_duel("crixus", "bow", seed=10)
    d["gap"] = 2.0
    _windup(d, "cut")
    D.act(d, "back")
    D.step(d)
    D.act(d, "back")
    D.step(d)
    _until_land(d)
    assert d["p"]["hp"] == 1.0  # stepped out of reach
    w = D.new_duel("crixus", "bow", seed=10)
    w["p"]["wall"] = 0.0
    g = w["gap"]
    D.act(w, "back")
    D.step(w)
    assert w["gap"] <= g


def test_brutus_charge_rolled_past_gives_room():
    d = D.new_duel("brutus", "bow", seed=11)
    d["gap"], d["p"]["wall"] = 4.0, 0.0
    _windup(d, "charge")
    while d["b"]["t"] > 1:
        D.step(d)
    D.act(d, "dodge")
    _until_land(d)
    assert d["p"]["hp"] == 1.0 and d["p"]["wall"] > 0 and d["b"]["state"] == "recover"
    assert d["b"]["t"] >= 10    # long recovery after a whiffed charge


def test_brutus_takes_extra_from_far_shots():
    near = D.new_duel("brutus", "bow", seed=12)
    near["b"].update(state="recover", t=200)
    near["gap"] = 3.0
    D.act(near, "light")
    D.step(near)
    far = D.new_duel("brutus", "bow", seed=12)
    far["b"].update(state="recover", t=200)
    far["gap"] = 6.0
    D.act(far, "light")
    D.step(far)
    ratio = (1 - far["b"]["hp"]) / (1 - near["b"]["hp"])
    assert abs(ratio - D.tuning()["bosses"]["brutus"]["far_shot_taken"]) < 1e-6


def test_stamina_gates_actions():
    d = D.new_duel("varro", "sword", seed=13)
    d["gap"] = 2.0
    d["b"].update(state="recover", t=200)
    d["p"]["sta"] = 1
    d["p"]["since_spend"] = 0
    D.act(d, "heavy")
    D.step(d)
    assert d["p"]["wind"] is None and d["b"]["hp"] == 1.0


def test_style_for_weapon():
    assert D.style_for_weapon({"id": "oak_shortbow", "ranged_att": 10}) == "bow"
    assert D.style_for_weapon({"id": "steel_battleaxe"}) == "axe"
    assert D.style_for_weapon({"id": "iron_longsword"}) == "sword"
    assert D.style_for_weapon(None) == "sword"


def test_sim_runs_and_brutus_favours_bow():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import duel_sim
    def rate(style):
        return sum(duel_sim.duel("brutus", style, 0.7, 1.0, "steel", i)[0] for i in range(60)) / 60
    bow, sword, axe = rate("bow"), rate("sword"), rate("axe")
    assert bow > max(sword, axe), (bow, sword, axe)
    assert min(sword, axe) > 0.3


def test_soldier_battles_unaffected():
    """Practice / roster fights stay multi-unit with no duel state."""
    import sqlite3
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import test_arena_battles as tab
    import mercenaries as merc
    random.seed(1)
    c, s = tab._conn(), tab._session()
    tab._army(c, s, "levy", 10)
    merc.set_practice_highest(c, 1, 3)
    ok, msg, m = merc.start_live_practice(c, s, merc.PRACTICE_TIERS[0]["id"])
    assert ok, msg
    assert m.get("mode") != "duel" and "duel" not in m and "duel" not in merc.match_hud(m)
    assert len([u for u in m["units"] if u["side"] == "you"]) == 10
    merc.begin_live_fight(s)
    for _ in range(500):
        evs = merc.tick_live_match(m)
        assert not any(e.get("type") == "ARENA_DUEL" for e in evs)
        if m["phase"] == "done":
            break
    assert m["phase"] == "done"


def _ui_client():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import types
    import pygame
    pygame.init()
    scr = pygame.display.set_mode((900, 640))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import arena_duel_ui as U
    d = D.new_duel("brutus", "axe")
    c = types.SimpleNamespace(screen=scr, player={"char_name": "T"}, chat=[],
                              arena_match={"active": True, "phase": "fight", "duel": D.public(d),
                                           "foe_name": "Brutus", "hud": {"log": ["The champion salutes — duel!"]}})
    c.add_chat = lambda text, color=None: c.chat.append(text)
    return U, c, d


def test_sprite_load_failure_falls_back_to_rig():
    U, c, _ = _ui_client()
    calls = []
    real_rig = U._draw_rig
    U._draw_rig = lambda *a, **k: (calls.append(1), real_rig(*a, **k))[1]
    old_dir, U._SPR_DIR = U._SPR_DIR, "/nonexistent/duel_sprites"
    U._SPR.clear()
    try:
        assert U.draw_stage(c, 900, 640) is True
        assert calls, "fallback rig should have drawn"
    finally:
        U._SPR_DIR, U._draw_rig = old_dir, real_rig
        U._SPR.clear()


def test_commentary_follows_exchange():
    U, c, d = _ui_client()
    U.on_message(c, {"duel": D.public(d), "events": [{"kind": "boss_hit", "dmg": 0.05, "tag": "light"}]})
    log = c.arena_match["hud"]["log"]
    assert not any("salutes" in l for l in log)
    assert "hit Brutus for 5%" in log[-1] and "hit Brutus" in c.chat[-1]
    assert D.exchange_line({"kind": "parried", "perfect": True}, "Brutus").startswith("Perfect parry")


def test_fighters_always_face_each_other():
    """Every champion and every hero weapon/gender faces the opponent in every animation state
    (idle, wind-up, strike, parry, dodge, hit reaction / knockback, stagger, KO)."""
    U, c, _ = _ui_client()
    import json
    import pygame
    import numpy as np
    U._SPR.clear(); U._MIRRORED.clear(); U._FACING = None
    with open(os.path.join(U._SPR_DIR, "facing.json")) as fh:
        man = json.load(fh)
    cids = sorted(x for x in os.listdir(U._SPR_DIR) if os.path.isdir(os.path.join(U._SPR_DIR, x)))
    assert {"varro", "brutus", "crixus", "sabina", "ignatius", "unbroken"} <= set(cids)
    for h in ("hero_sword", "hero_axe", "hero_bow"):
        assert h in cids and h + "_f" in cids
    acts = [("idle", 0), ("charge", 400), ("strike", 300), ("heavy", 500), ("parry", 300), ("parry_ok", 300),
            ("dodge", 430), ("hit", 360), ("stagger", 600), ("ko", 0)]
    for cid in cids:
        side = "hero" if cid.startswith("hero") else "boss"
        want = "r" if side == "hero" else "l"
        assert cid in man, cid
        for state in ("idle", "attack", "block", "dodge", "hit"):
            img = U._frame(cid, state, 380)
            assert U.drawn_facing(cid, state) == want, (cid, state)
            raw = pygame.image.load(os.path.join(U._SPR_DIR, cid, state + ".png")).convert_alpha()
            a = pygame.surfarray.array_alpha(img) > 128
            r = pygame.surfarray.array_alpha(raw) > 128
            if a.shape == r.shape:
                mirrored = man[cid][state] != want
                ref = r[::-1, :] if mirrored else r
                assert (a == ref).mean() > 0.97, (cid, state, "mirror mismatch")
        for style in ("sword", "axe", "bow"):
            for act, dur in acts:
                F = U.Fighter(side)
                F.update(100.0, 0.016)
                if act == "ko":
                    F.ko = 0
                else:
                    F.play(act, 0, max(1, dur))
                for now in (1, dur * 0.3 + 1, dur * 0.6 + 1, 800):
                    pose = F.transform(now, style)[0]
                    U._frame(cid, pose, 380)
                    assert U.drawn_facing(cid, pose) == want, (cid, style, act, now, pose)
    U._SPR.clear()


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                print("FAIL", name, e)
                fails += 1
    print("ALL PASSED" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
