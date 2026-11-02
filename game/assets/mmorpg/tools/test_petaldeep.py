"""Petaldeep five halls, trust key, and the Queen. Run: python3 tools/test_petaldeep.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import petaldeep  # noqa: E402
import fairy_friendship as FF  # noqa: E402
import combat  # noqa: E402
from content import MONSTERS, INTERACTABLES, ITEMS  # noqa: E402
from world_map import FLOOR, WALL, is_walkable, get_zone  # noqa: E402

W = server.WORLD
_N = [0]


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))


def _player(username=None):
    _N[0] += 1
    name = username or f"petal{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    s.inventory = {}
    s.bank = {}
    s.equipment = {"weapon": "bronze_sword"}
    W.sessions[s.player_id] = s
    return s


def _texts(session):
    return [m.get("text") for m in session.ws.sent if m.get("type") == "CHAT_MSG"]


def _clear_room(session):
    for m in list(session.dungeon["monsters"].values()):
        m.alive = False
        m.hp = 0


def test_mouth_is_open_grass():
    x, y = petaldeep.MOUTH
    sx, sy = petaldeep.STAND
    spot = next(s for s in INTERACTABLES if s.get("id") == "petaldeep_mouth")
    assert (spot["x"], spot["y"]) == (x, y)
    assert spot["dungeon_id"] == "petaldeep"
    assert is_walkable(W.grid, x, y)
    assert is_walkable(W.grid, sx, sy)
    assert get_zone(x, y) == "fairy_village"
    assert x < 21 and y < 70


def test_level_curve_and_boss():
    assert combat.monster_combat_level(MONSTERS["petal_thrall"], "petal_thrall") == 200
    assert combat.monster_combat_level(MONSTERS["petal_thrall_thorn"], "petal_thrall_thorn") == 500
    assert combat.monster_combat_level(MONSTERS["petal_thrall_mirror"], "petal_thrall_mirror") == 900
    assert combat.monster_combat_level(MONSTERS["petal_thrall_night"], "petal_thrall_night") == 1400
    assert combat.monster_combat_level(MONSTERS["petaldeep_queen"], "petaldeep_queen") == 2000
    assert MONSTERS["petaldeep_queen"].get("boss") is True
    assert "petaldeep_crown" in ITEMS
    assert len(petaldeep.HALLS) == 5
    assert [h["level"] for h in petaldeep.HALLS] == [200, 500, 900, 1400, 2000]
    assert petaldeep.FUTURE_BOSS_LEVEL == 2000
    # Default map panel is 22×16 tiles at TILE=40 — halls fill the screen.
    assert petaldeep.W >= 22 and petaldeep.H >= 16


def test_halls_fill_screen_and_doors_stay_open():
    tiles = petaldeep.build_tiles()
    assert len(tiles) == petaldeep.H
    assert len(tiles[0]) == petaldeep.W
    for ax, ay in petaldeep.DOOR:
        assert tiles[ay][ax] == FLOOR
    # Interior is walkable (not a sealed box).
    assert tiles[petaldeep.SPAWN[1]][petaldeep.SPAWN[0]] == FLOOR
    assert tiles[petaldeep.EXIT[1]][petaldeep.EXIT[0]] == FLOOR


def test_refuses_without_key():
    async def go():
        s = _player()
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        assert s.dungeon is None
        assert petaldeep.WARN in _texts(s)
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_key_enters_orchard_and_leaves():
    async def go():
        s = _player()
        assert W.add_item_to_inventory(s, petaldeep.KEY_ID, 1)
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        assert s.dungeon and s.dungeon["id"] == "petaldeep"
        assert s.dungeon["floors"] == 5
        assert s.dungeon["width"] == petaldeep.W
        assert s.dungeon["height"] == petaldeep.H
        alive = [m for m in s.dungeon["monsters"].values() if m.alive]
        assert len(alive) == 3
        assert all(m.def_stats().get("level_override") == 200 for m in alive)
        tiles = s.dungeon["tiles"]
        assert tiles[petaldeep.EXIT[1]][petaldeep.EXIT[0]] == FLOOR
        # North arch is open on entry — player can move through without clearing.
        for ax, ay in petaldeep.DOOR:
            assert tiles[ay][ax] == FLOOR
        assert s.dungeon["petaldeep"]["door_open"] is True
        await server.handle_leave_dungeon(s, {})
        assert s.dungeon is None
        assert is_walkable(W.grid, s.x, s.y)
        assert max(abs(s.x - petaldeep.STAND[0]), abs(s.y - petaldeep.STAND[1])) <= 3
        assert petaldeep.has_key(s)
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_walk_through_all_halls_without_clearing():
    """UX: halls are not sealed — north arch advances even with thralls alive."""
    async def go():
        s = _player()
        assert W.add_item_to_inventory(s, petaldeep.KEY_ID, 1)
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        for expect_level in (200, 500, 900, 1400):
            st = s.dungeon["petaldeep"]
            hall = petaldeep.HALLS[st["room"]]
            assert hall["level"] == expect_level
            assert st["door_open"] is True
            for ax, ay in petaldeep.DOOR:
                assert s.dungeon["tiles"][ay][ax] == FLOOR
            # Advance without killing.
            s.x, s.y = petaldeep.DOOR[1]
            assert await petaldeep.on_step(s) is True
        assert s.dungeon["petaldeep"]["room"] == 4
        assert petaldeep.HALLS[4]["level"] == 2000
        bosses = [m for m in s.dungeon["monsters"].values() if m.alive]
        assert len(bosses) == 1
        assert bosses[0].type == "petaldeep_queen"
        # Interact also advances from earlier halls.
        await server.handle_leave_dungeon(s, silent=True)
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_clear_and_advance_to_boss():
    async def go():
        s = _player()
        assert W.add_item_to_inventory(s, petaldeep.KEY_ID, 1)
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        for expect_level in (200, 500, 900, 1400):
            st = s.dungeon["petaldeep"]
            hall = petaldeep.HALLS[st["room"]]
            assert hall["level"] == expect_level
            alive = [m for m in s.dungeon["monsters"].values() if m.alive]
            assert alive
            assert all(m.def_stats().get("level_override") == expect_level for m in alive)
            _clear_room(s)
            await petaldeep.on_kill(s, None)
            assert s.dungeon["petaldeep"]["door_open"] is True
            assert s.dungeon["petaldeep"]["cleared"] is True
            s.x, s.y = petaldeep.DOOR[1]
            assert await petaldeep.on_step(s) is True
        st = s.dungeon["petaldeep"]
        assert st["room"] == 4
        bosses = [m for m in s.dungeon["monsters"].values() if m.alive]
        assert len(bosses) == 1
        assert bosses[0].type == "petaldeep_queen"
        _clear_room(s)
        await petaldeep.on_kill(s, bosses[0])
        assert any("Queen" in (t or "") for t in _texts(s))
        s.x, s.y = petaldeep.EXIT
        assert await petaldeep.on_step(s) is True
        assert s.dungeon["petaldeep"]["room"] == 3
        while s.dungeon and s.dungeon["petaldeep"]["room"] > 0:
            s.x, s.y = petaldeep.EXIT
            await petaldeep.on_step(s)
        s.x, s.y = petaldeep.EXIT
        await petaldeep.on_step(s)
        assert s.dungeon is None
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_death_parks_at_stand():
    """Death leaves the instance the same way leave does — grass at STAND."""
    async def go():
        s = _player()
        assert W.add_item_to_inventory(s, petaldeep.KEY_ID, 1)
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        assert s.dungeon and s.dungeon["id"] == "petaldeep"
        # Advance into a deeper hall so death must not leave us mid-dungeon.
        _clear_room(s)
        await petaldeep.on_kill(s, None)
        s.x, s.y = petaldeep.DOOR[1]
        await petaldeep.on_step(s)
        assert s.dungeon["petaldeep"]["room"] == 1
        await server.handle_leave_dungeon(s, silent=True)
        assert s.dungeon is None
        assert (s.x, s.y) == petaldeep.STAND
        assert is_walkable(W.grid, s.x, s.y)
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_resume_after_logout_does_not_crash():
    """Stale petaldeep resume must not call floor_info (broke LOGIN)."""
    async def go():
        s = _player()
        assert W.add_item_to_inventory(s, petaldeep.KEY_ID, 1)
        s.x, s.y = petaldeep.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "petaldeep"})
        _clear_room(s)
        await petaldeep.on_kill(s, None)
        s.x, s.y = petaldeep.DOOR[1]
        await petaldeep.on_step(s)
        assert s.dungeon["petaldeep"]["room"] == 1
        server._save_dungeon_resume(s)
        blob = W.db.get_player_by_id(s.player_id)
        # Simulate logout: drop session dungeon, then resume.
        resume = json.loads(blob["dungeon_resume"])
        assert resume["id"] == "petaldeep"
        s.dungeon = None
        s.ws.sent.clear()
        await server._resume_dungeon(s, resume)
        assert s.dungeon and s.dungeon["id"] == "petaldeep"
        assert s.dungeon["petaldeep"]["room"] == 1
        assert s.dungeon["label"] == "Thorn Choir"
        W.sessions.pop(s.player_id, None)
    asyncio.run(go())


def test_david_is_trusted_and_gets_the_key():
    s = _player("David")
    assert petaldeep.prepare_account(s) is True
    d = FF.load(W.db.conn, s.player_id)
    assert FF.all_maxed(d)
    assert all(int(d["friendship"][fid]) == 100 for fid in FF.FAIRY_IDS)
    assert petaldeep.has_key(s)
    assert petaldeep.prepare_account(s) is False
    W.sessions.pop(s.player_id, None)


def test_partial_trust_gets_no_key():
    s = _player()
    FF.grant_full_trust(W.db.conn, s.player_id)
    d = FF.load(W.db.conn, s.player_id)
    d["friendship"]["nyx"] = 40
    FF.save(W.db.conn, s.player_id, d)
    assert petaldeep.try_grant_key(s) is False
    assert not petaldeep.has_key(s)
    W.sessions.pop(s.player_id, None)


def test_music_only_inside():
    import area_music

    class Inside:
        state = "GAME"
        player = True
        dungeon = {"id": "petaldeep"}
        arena_match = None

        def player_xy(self):
            return petaldeep.MOUTH

    class Glade:
        state = "GAME"
        player = True
        dungeon = None
        arena_match = None

        def player_xy(self):
            return (20, 70)

    assert area_music._key(Inside()) == "petaldeep"
    assert area_music._key(Glade()) != "petaldeep"
    path = area_music._track_path("petaldeep")
    assert path and path.endswith("Untitled.wav") and os.path.isfile(path)


def test_room_art_files_exist():
    rooms = os.path.join(ROOT, "client", "assets", "petaldeep", "rooms")
    for hall in petaldeep.HALLS:
        path = os.path.join(rooms, f"{hall['art']}.png")
        assert os.path.isfile(path), path


if __name__ == "__main__":
    test_mouth_is_open_grass()
    test_level_curve_and_boss()
    test_refuses_without_key()
    test_halls_fill_screen_and_doors_stay_open()
    test_key_enters_orchard_and_leaves()
    test_walk_through_all_halls_without_clearing()
    test_clear_and_advance_to_boss()
    test_death_parks_at_stand()
    test_resume_after_logout_does_not_crash()
    test_david_is_trusted_and_gets_the_key()
    test_partial_trust_gets_no_key()
    test_music_only_inside()
    test_room_art_files_exist()
    print("test_petaldeep: OK")
