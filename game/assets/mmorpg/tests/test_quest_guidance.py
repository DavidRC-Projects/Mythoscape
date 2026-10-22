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
    assert step["npc"] is None


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
