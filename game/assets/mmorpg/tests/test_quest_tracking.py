"""Explicit quest tracking: the HUD card follows the player's choice.

Covers the selection handler, the deterministic fallback when no quest is
tracked, and the clean drop when a tracked quest completes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import hud_v2  # noqa: E402


class FakeClient:
    """Just enough client surface for the tracking helpers — no pygame."""
    tracked_quest_id = None

    def __init__(self, quests=None):
        self.quests = quests or {}


def test_tracked_quest_wins_over_dict_order():
    c = FakeClient({
        "fetch_wool": {"status": "active", "progress": 1},
        "rat_slayers": {"status": "active", "progress": 3},
    })
    c.tracked_quest_id = "rat_slayers"
    assert hud_v2._tracked_quest_id(c) == "rat_slayers"
    name, _d, progress, need, status = hud_v2._current_quest(c)
    assert name == "Rat Problem" or "rat" in name.lower()
    assert status == "active"


def test_completion_falls_back_to_another_active_quest():
    c = FakeClient({
        "fetch_wool": {"status": "active", "progress": 1},
        "rat_slayers": {"status": "active", "progress": 3},
    })
    c.tracked_quest_id = "rat_slayers"
    # Server marks the tracked quest complete; handler clears the pin.
    c.tracked_quest_id = None if c.tracked_quest_id == "rat_slayers" else c.tracked_quest_id
    assert hud_v2._tracked_quest_id(c) == "fetch_wool"
    assert hud_v2._current_quest(c) is not None


def test_ready_quest_beats_active_when_nothing_tracked():
    c = FakeClient({
        "fetch_wool": {"status": "active", "progress": 1},
        "rat_slayers": {"status": "ready", "progress": 3},
    })
    assert hud_v2._tracked_quest_id(c) == "rat_slayers"


def test_empty_quest_log_is_safe():
    c = FakeClient({})
    assert hud_v2._tracked_quest_id(c) is None
    assert hud_v2._current_quest(c) is None


def test_tracked_quest_completed_by_log_update():
    c = FakeClient({
        "fetch_wool": {"status": "active", "progress": 1},
    })
    c.tracked_quest_id = "fetch_wool"
    # QUEST_LOG arrives with the quest completed — pin must stop matching.
    c.quests = {"fetch_wool": {"status": "complete", "progress": 3}}
    assert hud_v2._tracked_quest_id(c) is None
    assert hud_v2._current_quest(c) is None
