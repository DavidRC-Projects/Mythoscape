"""Castle Realm mercenaries / Command / Mythos gates. Run: python3 tools/test_mercenaries.py"""
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import combat  # noqa: E402
import mercenaries as merc  # noqa: E402
from content import CRAFT_RECIPES, ITEMS, XP_SKILLS, SKILL_DISPLAY_NAMES  # noqa: E402


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE players (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0, "
        "command_xp INTEGER DEFAULT 0, smithing_xp INTEGER DEFAULT 0)"
    )
    c.execute("INSERT INTO players (id, coins, command_xp) VALUES (1, 500000, 0)")
    merc.ensure_schema(c)
    return c


def _session(command_xp=0, coins=500000, smithing_xp=0, bank_coins=0):
    xp = {"command": command_xp, "smithing": smithing_xp}
    return types.SimpleNamespace(
        player_id=1,
        coins=coins,
        bank_coins=bank_coins,
        xp=xp,
        level=lambda skill: combat.level_from_xp(int(xp.get(skill) or 0)),
    )


def test_command_in_skills():
    assert "command" in XP_SKILLS
    assert SKILL_DISPLAY_NAMES["command"] == "Command"
    assert "command" not in ("attack", "strength", "defence", "archery")


def test_mythos_items_and_smelt_gate():
    assert "mythos_ore" in ITEMS and "mythos_bar" in ITEMS
    recipe = CRAFT_RECIPES["smelt_mythos"]
    assert recipe["level_req"] == 60
    assert recipe["command_req"] == 60
    assert recipe["inputs"]["mythos_ore"] == 4
    assert CRAFT_RECIPES["smith_mythos_body"]["command_req"] == 80


def test_mythos_guard_at_command_80():
    t = merc.TEMPLATES["mythos_guard"]
    assert t["command_req"] == 80
    assert t["default_gear"] == "mythos"
    assert merc.GEAR_KITS["mythos"]["command_req"] == 80
    low = merc.recruitable_templates(79)
    high = merc.recruitable_templates(80)
    assert next(r for r in low if r["id"] == "mythos_guard")["locked"] is True
    assert next(r for r in high if r["id"] == "mythos_guard")["locked"] is False


def test_roster_recruit_dismiss_kit():
    c = _conn()
    s = _session(command_xp=combat.xp_for_level(1), coins=10_000)
    ok, msg, soldier = merc.recruit(c, s, "levy")
    assert ok and soldier and soldier["gear_tier"] == "bronze"
    assert soldier["name"] in merc.SOLDIER_FIRST_NAMES or soldier["name"].split()[0] in merc.SOLDIER_FIRST_NAMES
    assert soldier["name"] != "Levy"
    assert soldier.get("template_name") == "Levy"
    assert len(merc.roster_public(c, 1)) == 1
    # Mythos kit locked
    ok2, msg2 = merc.outfit(c, s, soldier["id"], "mythos")
    assert not ok2 and "Command 80" in msg2
    ok3, msg3 = merc.outfit(c, s, soldier["id"], "iron")
    assert ok3
    assert merc.roster_public(c, 1)[0]["gear_tier"] == "iron"
    ok4, _ = merc.dismiss(c, s, soldier["id"])
    assert ok4 and merc.roster_public(c, 1) == []


def test_field_deploy_castle_realm_only(monkeypatch=None):
    c = _conn()
    s = _session(coins=50_000)
    merc.recruit(c, s, "levy")
    merc.recruit(c, s, "levy")
    s.deployed_soldiers = []
    s.dungeon = None
    s.arena_match = None
    s.x, s.y = 196, 140
    s.last_step = (0, -1)
    ok, msg = merc.deploy_soldiers(c, s)
    assert not ok and "Castle Realm" in msg
    s.dungeon = {"id": "castle_realm", "plane": "realm"}
    # Stub walkability so follow spots resolve in unit tests.
    import types as _types
    fake = _types.ModuleType("castle_realm")
    fake.walkable = lambda plane, x, y: True
    sys.modules["castle_realm"] = fake
    ok2, msg2 = merc.deploy_soldiers(c, s)
    assert ok2, msg2
    assert len(s.deployed_soldiers) == 2
    assert all(u.get("field_soldier") for u in s.deployed_soldiers)
    ids = merc.deployed_roster_ids(s)
    assert len(ids) == 2
    ok3, msg3 = merc.recall_soldiers(s)
    assert ok3 and s.deployed_soldiers == []
    # Redeploy one, then leave-realm clear
    merc.deploy_soldiers(c, s)
    assert merc.deployed_list(s)
    s.dungeon = None
    merc.tick_field_soldiers(s, [], resolve_monster=lambda _mid: None, tick=1)
    assert s.deployed_soldiers == []


def test_upgrade_keeps_xp_and_name():
    c = _conn()
    s = _session(command_xp=combat.xp_for_level(1), coins=500_000, bank_coins=0)
    ok, _, soldier = merc.recruit(c, s, "levy")
    assert ok
    sid = soldier["id"]
    name = soldier["name"]
    # Train Attack past man-at-arms base (12) so promote must keep the higher XP.
    for _ in range(8):
        merc.train(c, s, sid, "attack")
    before = merc.roster_public(c, 1, session=s)[0]
    before_att = before["levels"]["attack"]
    assert before_att >= 13
    coins_before = s.coins + s.bank_coins
    ok2, msg, promoted = merc.upgrade(c, s, sid)
    assert ok2 and promoted, msg
    assert promoted["name"] == name
    assert promoted["template_id"] == "man_at_arms"
    assert promoted["levels"]["attack"] == before_att  # battle/train XP kept
    assert promoted["levels"]["strength"] >= 12  # floored to new template base
    assert s.coins + s.bank_coins < coins_before
    assert "Man-at-arms" in msg
    # Full roster: can still promote without dismissing
    while len(merc.roster_rows(c, 1)) < merc.ROSTER_MAX:
        merc.recruit(c, s, "levy")
    assert len(merc.roster_rows(c, 1)) == merc.ROSTER_MAX
    ok3, msg3, _ = merc.recruit(c, s, "man_at_arms")
    assert not ok3 and "full" in msg3.lower()
    levy = next(r for r in merc.roster_rows(c, 1) if r["template_id"] == "levy")
    ok4, msg4, p2 = merc.upgrade(c, s, levy["id"])
    assert ok4 and p2["template_id"] == "man_at_arms", msg4


def test_spend_from_bank_for_train():
    c = _conn()
    s = _session(coins=0, bank_coins=50_000)
    ok, _, soldier = merc.recruit(c, s, "levy")
    assert ok and s.bank_coins < 50_000
    before_bank = s.bank_coins
    before_att = soldier["levels"]["attack"]
    ok2, msg, updated = merc.train(c, s, soldier["id"], "attack")
    assert ok2 and updated
    assert updated["levels"]["attack"] == before_att + 1
    assert s.coins == 0
    assert s.bank_coins < before_bank
    assert "bank" in msg.lower()


def test_train_daily_cap_and_bulk():
    c = _conn()
    s = _session(coins=0, bank_coins=5_000_000)
    for _ in range(3):
        merc.recruit(c, s, "levy")
    ok, msg = merc.train_all(c, s, "strength")
    assert ok and "3" in msg
    roster = merc.roster_public(c, 1, session=s)
    assert all(r["levels"]["strength"] == 6 for r in roster)  # levy base str 5
    assert all(r["trains_today"]["used"] == 1 for r in roster)
    # Burn remaining 9 slots on first soldier
    sid = roster[0]["id"]
    for _ in range(merc.DAILY_TRAIN_CAP - 1):
        ok, _, _ = merc.train(c, s, sid, "attack")
        assert ok
    ok, msg, _ = merc.train(c, s, sid, "attack")
    assert not ok and str(merc.DAILY_TRAIN_CAP) in msg
    ok2, msg2 = merc.outfit_all(c, s, "iron")
    assert ok2 and "3" in msg2
    assert all(r["gear_tier"] == "iron" for r in merc.roster_public(c, 1))


def test_recruit_mythos_guard_requires_80():
    c = _conn()
    s = _session(command_xp=combat.xp_for_level(79), coins=200_000)
    ok, msg, _ = merc.recruit(c, s, "mythos_guard")
    assert not ok and "80" in msg
    s80 = _session(command_xp=combat.xp_for_level(80), coins=200_000)
    ok2, msg2, soldier = merc.recruit(c, s80, "mythos_guard")
    assert ok2 and soldier["template_id"] == "mythos_guard"
    assert soldier["gear_tier"] == "mythos"
    assert soldier["equipment"]["body"] == "mythos_body"


def test_practice_grants_progress_and_command_xp_fields():
    c = _conn()
    s = _session(coins=50_000)
    # Seed a strong roster so squire is beatable
    for _ in range(6):
        merc.recruit(c, s, "man_at_arms")
    ok, msg, summary = merc.practice_fight(c, s, "squire_alden")
    assert ok and summary is not None
    assert "command_xp" in summary and summary["command_xp"] > 0
    assert merc.practice_highest(c, 1) >= (1 if summary["won"] else 0)


def test_elo_underdog_swing():
    # Underdog win should be large; favourite win small
    upset = merc.elo_delta(900, 1200, True)
    stomp = merc.elo_delta(1200, 900, True)
    assert upset > stomp > 0
    pred = merc.predicted_elo(1000, 1000)
    assert pred["win"] == -pred["loss"]


def test_tier_equip_items_exist():
    for tier, eq in merc.TIER_EQUIP.items():
        for slot, item_id in eq.items():
            assert item_id in ITEMS, f"{tier}.{slot} missing {item_id}"


def test_barracks_payload_shape():
    c = _conn()
    s = _session(command_xp=combat.xp_for_level(80))
    merc.recruit(c, s, "mythos_guard")
    payload = merc.barracks_payload(c, s)
    assert payload["mythos_soldier_ready"] is True
    assert payload["roster_total_cl"] > 0
    assert payload["roster"][0]["equipment"]["body"] == "mythos_body"
    assert any(p["id"] == "king_crownfall" for p in payload["practice"])


def test_arena_map_stamped():
    import json
    from pathlib import Path
    path = Path(ROOT) / "client" / "assets" / "castle_realm" / "json" / "castle_realm_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    arena = data.get("arena") or {}
    assert arena.get("id") == "crownfall_arena"
    fp = arena["footprint"]
    assert (fp[2] - fp[0]) >= 50 and (fp[3] - fp[1]) >= 40
    assert data["rows"][128][196] == "s"
    art = Path(ROOT) / "client" / "assets" / "castle_realm" / "arena" / "sprites" / "1x" / "arena_campus.jpg"
    assert art.is_file()
    pit_floor = Path(ROOT) / "client" / "assets" / "castle_realm" / "arena" / "sprites" / "1x" / "arena_pit_floor.png"
    assert pit_floor.is_file()
    assert arena.get("pit_floor_1x") == "sprites/1x/arena_pit_floor.png"


def test_practice_armies_ten_and_formation():
    for entry in merc.PRACTICE_TIERS:
        army = merc._normalize_army(entry["army"])
        assert len(army) == merc.PRACTICE_ARMY_SIZE
    spots = merc._line_up(10, 178, 214, 113, 143, west=True)
    xs = sorted({s[0] for s in spots})
    assert len(xs) == 2
    assert sum(1 for s in spots if s[0] == max(xs)) == 5
    assert sum(1 for s in spots if s[0] == min(xs)) == 5
    # File gap ≥ 3 so sprites don't overlap.
    front = sorted(s[1] for s in spots if s[0] == max(xs))
    assert all(front[i + 1] - front[i] >= 3 for i in range(len(front) - 1))


def test_focus_fire_surrounds_lonely_foe():
    """When one foe remains, several allies should get adjacent and keep swinging."""
    foe = {
        "id": 1, "side": "foe", "x": 200, "y": 128, "hp": 200, "max_hp": 200,
        "alive": True, "levels": {"attack": 10, "strength": 10, "defence": 5, "hitpoints": 40},
        "gear_tier": "bronze", "ability": None, "attack_cd": 0, "attacking": 0.0,
        "name": "Lonely", "first_strike": False, "guard_left": 0, "medic_left": 0,
        "target_id": None, "level": 10, "equipment": {}, "ability_label": "—",
    }
    allies = []
    for i, (x, y) in enumerate(((190, 120), (190, 128), (190, 136), (188, 124), (188, 132))):
        allies.append({
            "id": 10 + i, "side": "you", "x": x, "y": y, "hp": 40, "max_hp": 40,
            "alive": True, "levels": {"attack": 20, "strength": 20, "defence": 10, "hitpoints": 40},
            "gear_tier": "steel", "ability": None, "attack_cd": 0, "attacking": 0.0,
            "name": f"Ally{i}", "first_strike": False, "guard_left": 0, "medic_left": 0,
            "target_id": None, "level": 20, "equipment": {}, "ability_label": "—",
        })
    match = {
        "phase": "fight", "tick": 0, "units": allies + [foe],
        "pit": list(merc.ARENA_PIT), "log": [],
    }
    for _ in range(12):
        merc.tick_live_match(match)
        if match.get("phase") == "done":
            break
    adjacent = [
        a for a in allies
        if a["alive"] and a["hp"] > 0 and merc._chebyshev(a["x"], a["y"], foe["x"], foe["y"]) <= 1
    ]
    # At least 2–3 should have closed to sword range (or foe already dead from pile-on).
    in_range = [
        a for a in allies
        if a["alive"] and a["hp"] > 0
        and merc._chebyshev(a["x"], a["y"], foe["x"], foe["y"]) == merc.MATCH_MELEE_RANGE
    ]
    assert len(in_range) >= 2 or len(adjacent) >= 2 or foe["hp"] <= 0 or not foe["alive"]


def test_surplus_hold_dressing_line():
    """When 3 allies already surround a foe, extras park 4–5 tiles back."""
    foe = {
        "id": 1, "side": "foe", "x": 200, "y": 128, "hp": 500, "max_hp": 500,
        "alive": True, "levels": {"attack": 5, "strength": 5, "defence": 40, "hitpoints": 80},
        "gear_tier": "bronze", "ability": None, "attack_cd": 0, "attacking": 0.0,
        "name": "Tank", "first_strike": False, "guard_left": 0, "medic_left": 0,
        "target_id": None, "level": 5, "equipment": {}, "ability_label": "—",
        "rank": "front", "file": 2, "held_reserve": False,
    }
    # Three already adjacent; two far west should dress, not crowd radius 2–3.
    allies = []
    for i, (x, y) in enumerate(((199, 128), (200, 127), (200, 129), (185, 124), (185, 132))):
        allies.append({
            "id": 10 + i, "side": "you", "x": x, "y": y, "hp": 40, "max_hp": 40,
            "alive": True, "levels": {"attack": 20, "strength": 20, "defence": 10, "hitpoints": 40},
            "gear_tier": "steel", "ability": None, "attack_cd": 0, "attacking": 0.0,
            "name": f"Ally{i}", "first_strike": False, "guard_left": 0, "medic_left": 0,
            "target_id": 1, "level": 20, "equipment": {}, "ability_label": "—",
            "rank": "front", "file": i, "held_reserve": False,
        })
    match = {
        "phase": "fight", "tick": 0, "units": allies + [foe],
        "pit": list(merc.ARENA_PIT), "log": [], "reserves_released": True,
    }
    for _ in range(8):
        merc.tick_live_match(match)
    surplus = [a for a in allies if a["id"] in (13, 14) and a["alive"]]
    for a in surplus:
        d = merc._chebyshev(a["x"], a["y"], foe["x"], foe["y"])
        assert d >= 3, (a["id"], a["x"], a["y"], d)


def test_melee_stand_off_spacing():
    """Fighters stop at MATCH_MELEE_RANGE — not stacked on the same tile."""
    c = _conn()
    s = _session(coins=500_000)
    for _ in range(5):
        merc.recruit(c, s, "man_at_arms")
    ok, err, match = merc.start_live_practice(c, s, "squire_alden")
    assert ok, err
    merc.begin_live_fight(s)
    saw_swing = False
    for _ in range(24):
        merc.tick_live_match(match)
        for u in match["units"]:
            if u["side"] != "you" or not u["alive"] or u.get("held_reserve"):
                continue
            tid = u.get("target_id")
            tgt = next((f for f in match["units"] if f["id"] == tid), None) if tid else None
            if not tgt or not tgt["alive"]:
                continue
            d = merc._chebyshev(u["x"], u["y"], tgt["x"], tgt["y"])
            # Never closer than sword range while fighting that foe.
            assert d >= merc.MATCH_MELEE_RANGE, (u["x"], u["y"], tgt["x"], tgt["y"], d)
            if d == merc.MATCH_MELEE_RANGE and float(u.get("attacking") or 0) > 0.5:
                saw_swing = True
        if match.get("phase") == "done":
            break
    assert saw_swing or match.get("phase") == "done"


def test_front_clash_no_cross_and_reserves_on_death():
    """Fronts meet enemy fronts; rear stays put until someone dies."""
    c = _conn()
    s = _session(coins=500_000)
    for _ in range(10):
        merc.recruit(c, s, "man_at_arms")
    ok, err, match = merc.start_live_practice(c, s, "squire_alden")
    assert ok, err
    merc.begin_live_fight(s)
    you = [u for u in match["units"] if u["side"] == "you"]
    foe = [u for u in match["units"] if u["side"] == "foe"]
    rear_you = [u for u in you if u["rank"] == "rear"]
    rear_pos = {(u["id"], u["x"], u["y"]) for u in rear_you}
    # Before any death, front should only ever target enemy front.
    for _ in range(8):
        merc.tick_live_match(match)
        if match.get("reserves_released") or match.get("phase") == "done":
            break
        for u in you:
            if u.get("held_reserve") or not u["alive"]:
                continue
            tid = u.get("target_id")
            if not tid:
                continue
            tgt = next(f for f in foe if f["id"] == tid)
            assert tgt.get("rank") == "front", (u["name"], tgt.get("rank"), tgt["name"])
        # Rear still parked
        assert {(u["id"], u["x"], u["y"]) for u in rear_you} == rear_pos
    # Force a front death to release reserves
    victim = next(u for u in foe if u["rank"] == "front" and u["alive"])
    victim["hp"] = 0
    victim["alive"] = False
    merc._release_reserves(match, [])
    assert match["reserves_released"]
    assert all(not u.get("held_reserve") for u in match["units"])
    # After release, rear should be free to move on subsequent ticks
    before = {(u["id"], u["x"], u["y"]) for u in rear_you if u["alive"]}
    for _ in range(6):
        merc.tick_live_match(match)
    after = {(u["id"], u["x"], u["y"]) for u in rear_you if u["alive"]}
    assert after != before or match.get("phase") == "done"


def test_preview_then_begin_fight():
    c = _conn()
    s = _session(coins=500_000)
    for _ in range(3):
        merc.recruit(c, s, "man_at_arms")
    ok, err, match = merc.start_live_practice(c, s, "squire_alden")
    assert ok, err
    assert match["phase"] == "preview"
    ok2, err2 = merc.begin_live_fight(s)
    assert ok2, err2
    assert s.arena_match["phase"] == "fight"


def test_survivor_xp_levels_roster():
    c = _conn()
    s = _session(coins=500_000)
    merc.recruit(c, s, "man_at_arms")
    row = merc.roster_rows(c, 1)[0]
    before = int(row["attack_xp"])
    match = {
        "tier": 2,
        "won": True,
        "units": [{
            "side": "you", "alive": True, "hp": 10, "roster_id": row["id"],
            "name": row["name"],
        }],
        "foe_id": "squire_alden",
        "foe_name": "Squire Alden",
        "entry": merc.PRACTICE_TIERS[0],
        "your_alive": 1, "foe_alive": 0, "rounds": 20,
        "your_hp_left": 10, "foe_hp_left": 0, "log": [],
        "roster_cl": 10, "foe_cl": 10,
    }
    _text, summary = merc.settle_live_practice(c, s, match)
    assert summary.get("survivor_xp")
    row2 = merc.roster_rows(c, 1)[0]
    assert int(row2["attack_xp"]) > before


def test_daily_fight_cap():
    c = _conn()
    s = _session(coins=500_000)
    for _ in range(10):
        merc.recruit(c, s, "man_at_arms")
    for i in range(merc.DAILY_FIGHT_CAP):
        ok, err, match = merc.start_live_practice(c, s, "squire_alden")
        assert ok, (i, err)
        s.arena_match = None
    ok, err, _ = merc.start_live_practice(c, s, "squire_alden")
    assert not ok and str(merc.DAILY_FIGHT_CAP) in err
    info = merc.daily_fights(c, 1)
    assert info["remaining"] == 0 and info["used"] == merc.DAILY_FIGHT_CAP


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except Exception as exc:
                failed += 1
                print("FAIL", name, exc)
    if failed:
        raise SystemExit(1)
    print("all passed")
