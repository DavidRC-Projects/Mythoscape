"""Monster combat level on the player scale (COMBAT_SKILLING_SPEC part 1). Run: python3 tools/test_monster_levels.py"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import combat  # noqa: E402
import content  # noqa: E402

# "new" column of the spec table (bandits are listed there but don't exist in content yet)
SPEC = {
    "giant_rat": 21, "goblin": 32, "skeleton": 47, "giant": 72, "big_skeleton": 76, "spider": 130, "dragon": 377,
    "wolf": 116, "guard": 90, "knight": 146, "adamant_duelist": 199, "mythos_champion": 328, "shade": 157,
    "crypt_ghoul": 182, "void_imp": 205, "obsidian_colossus": 259, "shadow_knight": 309, "void_horror": 375,
    "gallery_warden": 208, "void_crawler": 253, "knight_captain_vorn": 337, "rift_wraith": 310, "nyxarath": 1100,
    "ossuary_keeper": 78, "drowned_dead": 93, "barrow_knight": 114, "sir_aldric": 143, "morvath": 196,
    "magma_slug": 72, "ash_imp": 107, "ember_wolf": 157, "magma_knight": 241, "crucible_beast": 301,
    "bandit_archer": 52, "bandit_thug": 75, "bandit_leader": 109,
}


def test_spec_table():
    present = {k: v for k, v in SPEC.items() if k in content.MONSTERS}
    assert len(present) >= 33, sorted(set(SPEC) - set(present))
    for mid, want in present.items():
        mdef = content.MONSTERS[mid]
        assert mdef["level"] == want, (mid, mdef["level"], want)
        assert combat.monster_combat_level(mdef, mid) == want, mid
    for mid, mdef in content.MONSTERS.items():          # every monster is computed, none hand-typed
        assert mdef["level"] == combat.monster_combat_level(mdef, mid), mid
        assert "tier" in mdef, mid


def test_same_scale_as_players():
    for n in (5, 20, 33, 60, 99):
        mdef = {"attack": n, "strength": n, "defence": n, "hp": 3 * n, "def_bonus": 0, "attack_cooldown": 1.0}
        player = combat.combat_level(n, n, n, 3 * n) + 1          # karma level 1
        assert abs(combat.monster_combat_level(mdef) - player) <= 1, (n, combat.monster_combat_level(mdef), player)


def test_modifiers():
    base = {"attack": 50, "strength": 50, "defence": 50, "hp": 150, "def_bonus": 0, "attack_cooldown": 1.0}
    assert combat.monster_combat_level(base) == 150
    assert combat.monster_combat_level(dict(base, hp=250)) == 160                 # +100 hp -> +10
    assert combat.monster_combat_level(dict(base, def_bonus=40)) == 160           # natural armour /4
    assert combat.monster_combat_level(dict(base, attack_cooldown=1.2)) == 125    # slower swings
    assert combat.monster_combat_level(dict(base, attack_cooldown=0.8)) == 150    # faster never inflates
    assert combat.monster_combat_level(dict(base, boss=True)) == 165              # boss / dragonfire +10%
    assert combat.monster_combat_level(base, "dragon") == 165
    assert combat.monster_combat_level(dict(base, level_override=7)) == 7
    # gear never counts: weapon/armour fields a player would have are ignored
    assert combat.monster_combat_level(dict(base, weapon="rune_sword", armour_bonus=500)) == 150


def test_threat_colours_for_level_100():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import client
    lvl = content.MONSTERS
    assert client.threat_color(lvl["knight_captain_vorn"]["level"], 100) == client.THREAT_RED
    assert client.threat_color(lvl["giant"]["level"], 100) == client.THREAT_GREEN
    assert client.threat_color(lvl["shade"]["level"], 100) == client.THREAT_RED
    assert client.threat_color(100, 100) == client.THREAT_YELLOW
    assert client.threat_color(120, 100) == client.THREAT_ORANGE
    assert client.threat_color(90, 100) == client.THREAT_GREEN


def test_dungeon_labels_match_stats():
    import dungeon
    import emberdeep
    for mod in (dungeon, emberdeep):
        for lv in (10, 50, 90):
            st = mod.scaled_monster_stats(lv)
            assert st["tier"] == lv
            assert st["level"] == combat.monster_combat_level(st)
            assert f"(lvl {st['level']})" in st["name"], st["name"]
    assert dungeon.scaled_monster_stats(50)["level"] == 125


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} MONSTER LEVEL TESTS PASSED")
