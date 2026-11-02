"""Depths crypt doors + keys. Run: python3 tools/test_depths_doors.py"""
import asyncio
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import depths_v2  # noqa: E402
from world_map import FLOOR, WALL  # noqa: E402

W = server.WORLD
_N = [0]


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))


def _player(name=None):
    _N[0] += 1
    username = name or f"crypt{_N[0]}"
    W.db.create_account(username, "pw", username.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(username))
    s.stats_allocated = True
    s.inventory = {}
    s.bank = {}
    s.equipment = {"weapon": "bronze_sword"}
    W.sessions[s.player_id] = s
    return s


def _has(session, item_id):
    return any((e or {}).get("item_id") == item_id for e in (session.inventory or {}).values())


def _texts(session):
    return [m.get("text") for m in session.ws.sent if m.get("type") == "CHAT_MSG"]


def test_zone_art_files_exist():
    zones = os.path.join(ROOT, "client", "assets", "depths", "zones")
    for style in ("chapel", "ossuary", "catacomb", "tomb", "arena", "mausoleum", "bridge", "wyrm"):
        path = os.path.join(zones, f"{style}.png")
        assert os.path.isfile(path), path


def test_all_doors_and_keys():
    async def go():
        s = _player()
        depths_v2.build(s, server.next_id, server.MonsterInstance)
        d = s.dungeon
        doors = d["pack"]["doors"]
        assert set(doors) == {"A", "B", "C"}

        # --- Door A: Bone Key from Ossuary Keeper ---
        assert any(m.type == "ossuary_keeper" and m.alive for m in d["monsters"].values())
        ax, ay, key_a, name_a = doors["A"]
        assert d["tiles"][ay][ax] == WALL
        s.x, s.y = ax, ay + 1
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, ax, ay) == "blocked"
        assert any("Bone" in (t or "") for t in _texts(s))
        # Immediate retry with key must work (cooldown must not swallow unlocks).
        assert W.add_item_to_inventory(s, key_a, 1)
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, ax, ay) == "opened"
        assert "A" in d["opened"]
        assert d["tiles"][ay][ax] == FLOOR
        assert not _has(s, key_a)
        assert any("grinds open" in (t or "").lower() for t in _texts(s))

        # --- Door B: Tide Key from reliquary skull niche + pedestal ---
        bx, by, key_b, name_b = doors["B"]
        assert d["tiles"][by][bx] == WALL
        s.x, s.y = bx, by + 1
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, bx, by) == "blocked"
        assert any("Tide" in (t or "") or "Drowned" in (t or "") for t in _texts(s))
        rel = d["pack"]["secrets"]["reliquary"]
        wx, wy = rel["wall"]
        s.x, s.y = wx + 1, wy
        await depths_v2.handle_interact(s, {"x": wx, "y": wy})
        assert "reliquary" in d["secrets"]
        px, py = 3, 38
        assert d["tiles"][py][px] == FLOOR
        s.x, s.y = px + 1, py
        await depths_v2.handle_interact(s, {"x": px, "y": py})
        assert _has(s, key_b)
        s.x, s.y = bx, by + 1
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, bx, by) == "opened"
        assert "B" in d["opened"]
        assert d["tiles"][by][bx] == FLOOR
        assert not _has(s, key_b)

        # --- Door C: Knights' Seal from Sir Aldric ---
        cx, cy, key_c, name_c = doors["C"]
        assert any(m.type == "sir_aldric" and m.alive for m in d["monsters"].values())
        assert d["tiles"][cy][cx] == WALL
        s.x, s.y = cx, cy + 1
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, cx, cy) == "blocked"
        assert W.add_item_to_inventory(s, key_c, 1)
        # Cooldown after failed bump — key unlock must still succeed.
        time.sleep(0.05)
        s.ws.sent.clear()
        assert await depths_v2.try_blocked_step(s, cx, cy) == "opened"
        assert "C" in d["opened"]
        assert d["tiles"][cy][cx] == FLOOR
        assert not _has(s, key_c)
        assert set(d["opened"]) == {"A", "B", "C"}

        # Tile change payloads must be list triples (client KeyError otherwise).
        tile_msgs = [m for m in s.ws.sent if m.get("type") == "DUNGEON_TILES"]
        assert tile_msgs
        for ch in tile_msgs[-1].get("changes") or []:
            assert isinstance(ch, (list, tuple)) and len(ch) >= 3

        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_key_sources_documented():
    pack, _ = depths_v2.map_pack()
    keys = pack["keys"]
    assert keys["depths_bone_key"]["monster"] == "ossuary_keeper"
    assert keys["depths_tide_key"]["secret"] == "reliquary"
    assert keys["depths_knight_seal"]["monster"] == "sir_aldric"
    for ch, hint in depths_v2.DOOR_HINTS.items():
        assert len(hint) > 20


if __name__ == "__main__":
    test_zone_art_files_exist()
    test_key_sources_documented()
    test_all_doors_and_keys()
    print("test_depths_doors: OK")
