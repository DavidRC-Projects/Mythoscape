"""Stepped quests + tracked_quest_id proofs. Run: python3 tools/test_quest_steps.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import quest_steps  # noqa: E402
from content import QUESTS  # noqa: E402

W = server.WORLD
_N = [0]


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))


def _player():
    _N[0] += 1
    name = f"qstep{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    W.sessions[s.player_id] = s
    return s


def test_quest_defs_present():
    for qid in ("north_road_warning", "moonpetal_hospitality", "misplaced_folio"):
        q = QUESTS[qid]
        assert q["type"] == "steps"
        assert len(q["steps"]) >= 7


def test_pack_unpack():
    p = quest_steps.pack_progress(3, 5)
    assert quest_steps.unpack_progress(p) == (3, 5)


def test_hale_accept_and_track():
    async def go():
        s = _player()
        await server.handle_quest_accept(s, {"quest_id": "north_road_warning"})
        assert s.quests["north_road_warning"]["status"] == "active"
        assert s.tracked_quest_id == "north_road_warning"
        row = W.db.get_player_by_id(s.player_id)
        assert (row["tracked_quest_id"] if "tracked_quest_id" in row.keys() else "") == "north_road_warning"
        logs = [m for m in s.ws.sent if m.get("type") == "QUEST_LOG"]
        assert logs and logs[-1].get("tracked_quest_id") == "north_road_warning"
        # Advance talk to Bren
        assert quest_steps.on_talk(s, "pass_scout")
        idx, _c = quest_steps.unpack_progress(s.quests["north_road_warning"]["progress"])
        assert idx == 1  # kill wolves
        obj = quest_steps.objective_text(QUESTS["north_road_warning"], s.quests["north_road_warning"], s)
        assert "Step 2/" in obj
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_track_survives_relog_sim():
    async def go():
        s = _player()
        await server.handle_quest_accept(s, {"quest_id": "moonpetal_hospitality"})
        pid = s.player_id
        tracked = s.tracked_quest_id
        W.sessions.pop(pid, None)
        row = W.db.get_player_by_id(pid)
        s2 = server.PlayerSession(_WS(), row)
        assert s2.tracked_quest_id == tracked == "moonpetal_hospitality"
    asyncio.run(go())


def test_folio_requires_hospitality():
    async def go():
        s = _player()
        await server.handle_quest_accept(s, {"quest_id": "misplaced_folio"})
        assert "misplaced_folio" not in s.quests  # prereq blocked
        await server.handle_quest_accept(s, {"quest_id": "moonpetal_hospitality"})
        s.quests["moonpetal_hospitality"] = {"status": "complete", "progress": 0}
        W.db.set_quest_progress(s.player_id, "moonpetal_hospitality", "complete", 0)
        await server.handle_quest_accept(s, {"quest_id": "misplaced_folio"})
        assert s.quests["misplaced_folio"]["status"] == "active"
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_goto_and_kill_steps():
    s = _player()
    s.quests["north_road_warning"] = {"status": "active", "progress": quest_steps.pack_progress(5, 0)}
    # step 5 is watchpost goto at 132,18
    s.x, s.y = 132, 18
    assert quest_steps.on_goto(s, s.x, s.y)
    idx, _ = quest_steps.unpack_progress(s.quests["north_road_warning"]["progress"])
    assert idx == 6  # clear_post kill
    for _ in range(3):
        quest_steps.on_kill(s, "wolf")
    idx, _ = quest_steps.unpack_progress(s.quests["north_road_warning"]["progress"])
    assert idx == 7  # take_cache
    W.sessions.pop(s.player_id, None)


if __name__ == "__main__":
    test_quest_defs_present()
    test_pack_unpack()
    test_hale_accept_and_track()
    test_track_survives_relog_sim()
    test_folio_requires_hospitality()
    test_goto_and_kill_steps()
    print("test_quest_steps: OK")
