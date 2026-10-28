"""Onboarding guidance: the no-quest card and the quest-card Go targets.

Unit tests over quest/inventory state — no game launch required.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import hud_v2  # noqa: E402
from content import is_food  # noqa: E402


class FakeClient:
    tracked_quest_id = None

    def __init__(self, quests=None, player=None):
        self.quests = quests or {}
        self.player = player or {}
        self.welcome = {}


def _mk(quests=None, inv=None):
    # weapon equipped so the bare-handed step doesn't preempt quest/food advice
    return FakeClient(quests=quests, player={"equipment": {"weapon": "knife"}, "inventory": inv or {}})


def test_empty_log_recommends_starter_quest():
    # No QUEST_LOG yet (quests == {}) — the character is brand new.
    step = hud_v2._no_quest_step(_mk())
    assert step["npc"] == "elder_miriam"
    assert "Miriam" in step["title"]


def test_unrelated_completion_does_not_skip_starter_quest():
    # Completing guild_basics does not satisfy the rat_problem milestone.
    step = hud_v2._no_quest_step(_mk(quests={"guild_basics": {"status": "complete"}}))
    assert step["npc"] == "elder_miriam"


def test_rat_problem_complete_moves_past_starter():
    step = hud_v2._no_quest_step(_mk(quests={"rat_problem": {"status": "complete"}}))
    assert step["npc"] != "elder_miriam"


def test_bread_counts_as_food():
    assert is_food("bread") is True
    assert is_food("health_potion") is True
    assert is_food("burnt_shrimp") is False  # typed food but heals 0
    assert is_food("cooked_shrimp") is True
    assert is_food("raw_swordfish") is False  # resource, not food
    assert is_food("coins") is False


def test_food_advice_respects_bread_in_inventory():
    c = _mk(
        quests={"rat_problem": {"status": "complete"}},
        inv={"0": {"item_id": "bread", "qty": 3}},
    )
    step = hud_v2._no_quest_step(c)
    assert "food" not in step["title"].lower()
    # With food sorted, point at the next open quest — not Elowen yet.
    assert step["npc"] is not None
    assert step["npc"] != "elowen_moonwhisper"


def test_no_food_advises_when_only_raw_fish():
    c = _mk(
        quests={"rat_problem": {"status": "complete"}},
        inv={"0": {"item_id": "raw_swordfish", "qty": 2}},
    )
    step = hud_v2._no_quest_step(c)
    assert "food" in step["title"].lower()


def test_rat_problem_has_a_kill_camp_destination():
    qdef = hud_v2.QUESTS.get("rat_problem") or {}
    camp = next((d for d in hud_v2.TRAVEL_DESTINATIONS
                 if d.get("kind") == "monster" and d.get("monster") == qdef.get("target")), None)
    assert camp is not None, "rat_problem kill target should map to a travel camp"
    assert camp["id"] == "rats"


def test_quest_objective_dest_points_at_rat_mine():
    import new_player_guide as g
    c = _mk(quests={"rat_problem": {"status": "active", "progress": 0}})
    dest = g.quest_objective_dest(c, "rat_problem")
    assert dest is not None
    x, y, label = dest
    assert (x, y) == (67, 107)
    assert "Rat" in label


def test_silk_harvest_guides_to_crypt_not_iron_mine():
    import new_player_guide as g
    c = _mk(quests={"silk_harvest": {"status": "active", "progress": 0}})
    dest = g.quest_objective_dest(c, "silk_harvest")
    assert dest is not None
    x, y, label = dest
    # Overworld pin is the Crypt mouth — never the volcano iron rocks at (72,101).
    assert (x, y) == (64, 16), f"expected Crypt gate, got {(x, y)} {label}"
    assert (x, y) != (72, 101)


def test_silk_harvest_circles_live_spider():
    import new_player_guide as g
    c = _mk(quests={"silk_harvest": {"status": "active", "progress": 0}})
    c.player = {"x": 40, "y": 30, "equipment": {"weapon": "knife"}, "inventory": {}}
    c.monsters = {
        "1": {"id": "1", "type": "spider", "name": "Giant Spider", "x": 49, "y": 29, "hp": 40},
        "2": {"id": "2", "type": "skeleton", "name": "Skeleton", "x": 10, "y": 10, "hp": 20},
    }
    dest = g.quest_objective_dest(c, "silk_harvest")
    assert dest is not None, dest
    assert dest[0:2] == (49, 29), dest
    assert "Spider" in dest[2], dest


def test_ore_quest_circles_copper_rock():
    import new_player_guide as g
    c = _mk(quests={"ore_for_the_forge": {
        "status": "active", "progress": {"copper_ore": 0, "tin_ore": 0},
    }})
    c.resources = {"61,101": "copper_rock", "59,105": "tin_rock", "71,101": "iron_rock"}
    dest = g.quest_objective_dest(c, "ore_for_the_forge")
    assert dest is not None
    assert dest[0:2] in ((61, 101), (59, 105))
    assert "iron" not in dest[2].lower()


def test_wolves_travel_near_mountain_pack():
    from content import TRAVEL_DESTINATIONS
    wolves = next(d for d in TRAVEL_DESTINATIONS if d["id"] == "wolves")
    # Mountain pack sits around x122–131, y14–17 — not the old far pin at 147,16.
    assert abs(wolves["x"] - 126) <= 4
    assert abs(wolves["y"] - 16) <= 3


def test_quest_objective_dest_ready_points_at_giver():
    import new_player_guide as g
    c = _mk(quests={"rat_problem": {"status": "ready", "progress": 5}})
    dest = g.quest_objective_dest(c, "rat_problem")
    assert dest is not None
    miriam = next(n for n in g.NPCS if n["id"] == "elder_miriam")
    assert (dest[0], dest[1]) == (miriam["x"], miriam["y"])


def test_royal_challenge_not_guided_until_other_quests_done():
    import new_player_guide as g
    from content import QUESTS
    # Fairy oath active early — must not steal the trail / NEXT ACTION card.
    partial = {"fairy_oath": {"status": "active", "progress": 0},
               "rat_problem": {"status": "complete"}}
    c = _mk(quests=partial)
    assert g.quest_objective_dest(c, "fairy_oath") is None
    assert hud_v2._tracked_quest_id(c) is None
    step = hud_v2._no_quest_step(c)
    assert step["npc"] != "elowen_moonwhisper"
    assert step["npc"] is not None

    # Once every other quest is complete, Elowen becomes the next direction.
    done = {qid: {"status": "complete"} for qid in QUESTS if qid != "fairy_oath"}
    done["fairy_oath"] = {"status": "active", "progress": 0}
    c2 = _mk(quests=done)
    assert hud_v2.all_other_quests_complete(c2)
    assert hud_v2._tracked_quest_id(c2) == "fairy_oath"
    dest = g.quest_objective_dest(c2, "fairy_oath")
    assert dest is not None
    elowen = next(n for n in g.NPCS if n["id"] == "elowen_moonwhisper")
    assert (dest[0], dest[1]) == (elowen["x"], elowen["y"])
