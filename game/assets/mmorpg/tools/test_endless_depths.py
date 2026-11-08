"""Endless Depths room loop, scaling, milestones. Run: python3 tools/test_endless_depths.py"""
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
import endless_depths as ED  # noqa: E402
from content import INTERACTABLES, VOID_SANCTUM_MOUTH  # noqa: E402
from world_map import FLOOR, WALL, is_walkable  # noqa: E402

W = server.WORLD
_N = [0]

ASSETS = os.path.join(ROOT, "client", "assets", "endless_depths")
THEMES_DIR = os.path.join(ASSETS, "themes")


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))


def _player(username=None):
    _N[0] += 1
    name = username or f"depth{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    s.inventory = {}
    s.bank = {}
    s.equipment = {"weapon": "bronze_sword"}
    W.sessions[s.player_id] = s
    return s


def _clear_room(session):
    for m in list(session.dungeon["monsters"].values()):
        m.alive = False
        m.hp = 0


def test_theme_assets_exist():
    assert os.path.isfile(os.path.join(ASSETS, "mouth.png")), "mouth.png missing"
    for theme in ED.THEMES:
        path = os.path.join(THEMES_DIR, f"{theme}.png")
        assert os.path.isfile(path), f"missing theme {theme}"
    assert len(ED.THEMES) == 10


def test_entrance_village_landmark():
    """Endless sits on the village NW fringe; Void mouth stays on the SE massif."""
    assert VOID_SANCTUM_MOUTH == (205, 128)
    void = next(s for s in INTERACTABLES if s.get("id") == "void_sanctum_portal")
    assert (void["x"], void["y"]) == (205, 128)
    assert void["dungeon_id"] == "sanctum"

    spot = next(s for s in INTERACTABLES if s.get("id") == "endless_depths_mouth")
    assert (spot["x"], spot["y"]) == ED.MOUTH == (11, 21)
    assert spot["stand"] == list(ED.STAND) == [11, 23]
    assert spot["dungeon_id"] == "endless_depths"
    assert spot.get("pack") == "endless_depths"
    assert is_walkable(W.grid, *ED.MOUTH)
    assert is_walkable(W.grid, *ED.STAND)

    from content import NPCS, BUILDINGS
    guide = next(n for n in NPCS if n.get("id") == "endless_chronicler")
    assert (guide["x"], guide["y"]) == (13, 23)
    assert is_walkable(W.grid, guide["x"], guide["y"])
    shell = next(b for b in BUILDINGS if b.get("id") == "endless_depths")
    assert shell["x0"] <= ED.MOUTH[0] <= shell["x1"]
    assert shell["y0"] <= ED.MOUTH[1] <= shell["y1"]
    # Not overlapping Elder Hall after the compact-layout slide.
    elder = next(b for b in BUILDINGS if b.get("id") == "cottage_nw")
    assert shell["y0"] > elder["y1"] or shell["x1"] < elder["x0"] or shell["x0"] > elder["x1"]
    # Castle Realm portal sits south of Endless so both fit on the west fringe.
    portal = next(s for s in INTERACTABLES if s.get("id") == "castle_realm_portal")
    assert portal["y"] >= ED.MOUTH[1] + 5
    pack = os.path.join(ROOT, "client", "assets", "dungeons", "front34", "endless_depths_512.png")
    assert os.path.isfile(pack)
    atlas = os.path.join(ROOT, "client", "assets", "map_atlas", "places", "endless.jpg")
    assert os.path.isfile(atlas)


def test_scaling_formulas_and_cap():
    assert ED.n_eff(1) == 1
    assert ED.n_eff(200) == 200
    assert ED.n_eff(999) == 200
    assert abs(ED.hp_mult(1) - (1 + 0.10 + 0.0005)) < 1e-9
    assert abs(ED.reward_mult(10) - (1 + 0.06 * 10 + 0.0002 * 100)) < 1e-9
    assert ED.hp_mult(300) == ED.hp_mult(200)
    assert ED.reward_mult(500) == ED.reward_mult(200)
    assert ED.theme_for(1) == "crypt"
    assert ED.theme_for(11) == "crypt"
    assert ED.theme_for(2) == "catacomb"


def test_room_layout_door_sealed_then_open():
    sealed = ED.build_tiles(door_open=False)
    opened = ED.build_tiles(door_open=True)
    assert len(sealed) == ED.H and len(sealed[0]) == ED.W
    # Door tiles stay FLOOR either way so the player can walk onto them;
    # advancement is gated by endless_depths.door_open, not WALL collision.
    for x, y in ED.DOOR:
        assert sealed[y][x] == FLOOR
        assert opened[y][x] == FLOOR
        assert ED.dungeon_walkable(sealed, x, y)
    assert sealed[ED.SPAWN[1]][ED.SPAWN[0]] == FLOOR
    assert sealed[ED.EXIT[1]][ED.EXIT[0]] == FLOOR
    # Outer rim stays solid.
    assert sealed[0][ED.CX] == WALL
    assert sealed[ED.H - 1][ED.CX] == WALL


def test_enter_clear_advance_theme_and_reward_once():
    async def go():
        s = _player()
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        assert s.dungeon and s.dungeon["id"] == "endless_depths"
        assert s.dungeon["explore"] is True
        assert s.dungeon["floor"] == 1
        assert s.dungeon["width"] == ED.W
        st = ED._state(s)
        assert st["theme"] == "crypt"
        assert st["door_open"] is False
        for x, y in ED.DOOR:
            assert s.dungeon["tiles"][y][x] == FLOOR  # walkable; sealed by flag only
        alive = [m for m in s.dungeon["monsters"].values() if m.alive]
        assert 3 <= len(alive) <= 6
        for m in alive:
            assert m.no_respawn is True
            assert m.stats and "hp" in m.stats

        _clear_room(s)
        await ED.on_kill(s, alive[0])
        st = ED._state(s)
        assert st["cleared"] and st["door_open"]
        for x, y in ED.DOOR:
            assert s.dungeon["tiles"][y][x] == FLOOR

        coins_before = s.coins
        s.x, s.y = ED.DOOR[1]
        assert await ED.on_step(s) is True
        assert s.dungeon["floor"] == 2
        assert ED._state(s)["theme"] == "catacomb"
        assert s.coins > coins_before
        # Floor 1 already rewarded — advancing again without a new clear is blocked.
        st = ED._state(s)
        assert st["floor_rewarded"] is False
        assert st["door_open"] is False

        # Duplicate reward block on same cleared floor.
        _clear_room(s)
        await ED.on_kill(s, next(iter(s.dungeon["monsters"].values())))
        first = await ED._grant_floor_clear(s, 2)
        assert first and first["coins"] > 0
        second = await ED._grant_floor_clear(s, 2)
        assert second is None

        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_milestone_claim_once_and_leave_updates_highest():
    async def go():
        s = _player()
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        # Jump state to floor 10 cleared and advance.
        ED._apply_floor(s, 10)
        _clear_room(s)
        await ED.on_kill(s, next(iter(s.dungeon["monsters"].values())))
        mile_a = ED.claim_milestone(s, 10)
        assert mile_a and mile_a["title"]
        mile_b = ED.claim_milestone(s, 10)
        assert mile_b is None
        assert 10 in ED.milestones_claimed(s)

        ED._apply_floor(s, 17)
        s.x, s.y = ED.EXIT
        await ED.on_step(s)
        assert s.dungeon is None
        assert ED.highest_floor(s) >= 17

        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_resume_does_not_regrant_floor():
    async def go():
        s = _player()
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        ED._apply_floor(s, 5)
        _clear_room(s)
        await ED.on_kill(s, next(iter(s.dungeon["monsters"].values())))
        await ED.advance_floor(s)
        assert s.dungeon["floor"] == 6
        coins = s.coins
        resume = {"id": "endless_depths", "floor": 6, "x": ED.SPAWN[0], "y": ED.SPAWN[1],
                  "return_x": ED.STAND[0], "return_y": ED.STAND[1]}
        await ED.resume(s, resume)
        assert s.dungeon["floor"] == 6
        assert ED._state(s)["floor_rewarded"] is True
        # Simulate trying to re-grant floor 5/6 clear — blocked.
        assert await ED._grant_floor_clear(s, 6) is None
        assert s.coins == coins
        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_monster_pool_excludes_passive_pk():
    roster = ED._eligible_types()
    ids = {t[0] for t in roster}
    assert "adamant_duelist" not in ids
    assert "eclipse_champion" not in ids
    assert "goblin" in ids or "skeleton" in ids
    picks = ED.pick_types(10)
    assert 3 <= len(picks) <= 6


def test_hazards_on_selected_floors():
    assert ED.hazard_for(1, "toxic") is None  # too early
    assert ED.hazard_for(3, "toxic") == "poison"
    assert ED.hazard_for(4, "frozen") == "freeze"
    assert ED.hazard_for(5, "volcanic") == "fire"
    assert ED.hazard_for(6, "shadow") == "darkness"
    assert ED.hazard_for(7, "forest") == "roots"
    assert ED.hazard_for(8, "crypt") is None
    assert ED.hazard_intensity(10) > ED.hazard_intensity(3)


def test_solo_hiscores_not_group():
    async def go():
        s = _player("solo_hs")
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        assert ED._state(s).get("group_size") == 1
        ED.note_highest(s, 12, solo=True)
        assert ED.solo_highest_floor(s) == 12
        # Group progress bumps personal highest but not solo hiscores.
        ED._state(s)["group_size"] = 2
        ED.note_highest(s, 20)  # auto-detects group
        assert ED.highest_floor(s) == 20
        assert ED.solo_highest_floor(s) == 12
        rows = ED.leaderboard_rows(W.db.conn, limit=50)
        mine = next(r for r in rows if r["name"] == s.char_name)
        assert mine["level"] == 12
        boards = W.db.get_leaderboards(limit=20)
        assert "endless_depths" in boards
        assert any(r["name"] == s.char_name and r["level"] == 12 for r in boards["endless_depths"])
        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_entry_prompt_continue_vs_fresh():
    async def go():
        s = _player("cont_prompt")
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        assert s.dungeon and s.dungeon["floor"] == 1
        # Clear floor 1 and advance — continue checkpoint becomes 2.
        _clear_room(s)
        await ED.on_kill(s, next(iter(s.dungeon["monsters"].values())))
        s.x, s.y = ED.DOOR[1]
        assert await ED.on_step(s) is True
        assert s.dungeon["floor"] == 2
        assert ED.continue_floor(s) == 2

        # Leave and walk back to the mouth — should prompt, not enter.
        s.x, s.y = ED.EXIT
        await ED.on_step(s)
        assert s.dungeon is None
        assert ED.continue_floor(s) == 2
        s.ws.sent.clear()
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        assert s.dungeon is None
        types = [m.get("type") for m in s.ws.sent]
        assert "ENDLESS_ENTRY_PROMPT" in types
        prompt = next(m for m in s.ws.sent if m.get("type") == "ENDLESS_ENTRY_PROMPT")
        assert int(prompt["continue_floor"]) == 2

        # Continue — enter on floor 2.
        await server.handle_enter_dungeon(s, {
            "dungeon_id": "endless_depths", "endless_mode": "continue",
        })
        assert s.dungeon and s.dungeon["floor"] == 2
        assert ED._state(s)["theme"] == "catacomb"

        # Leave again, then start over — floor 1.
        s.x, s.y = ED.EXIT
        await ED.on_step(s)
        assert s.dungeon is None
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {
            "dungeon_id": "endless_depths", "endless_mode": "fresh",
        })
        assert s.dungeon and s.dungeon["floor"] == 1
        assert ED.continue_floor(s) == 1
        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_group_scaling_and_shared_enter():
    solo = ED.scale_stats("goblin", 10, group_size=1)
    duo = ED.scale_stats("goblin", 10, group_size=2)
    assert duo["hp"] > solo["hp"]
    assert duo["attack"] >= solo["attack"]
    assert ED.group_reward_mult(2) > 1.0
    assert ED.group_hp_mult(4) > ED.group_hp_mult(2)

    async def go():
        import party as party_mod
        a = _player("grp_a")
        b = _player("grp_b")
        a.x, a.y = ED.MOUTH
        b.x, b.y = ED.MOUTH[0], ED.MOUTH[1] + 1
        ok, _ = await party_mod.invite(a, b.player_id)
        assert ok
        ok, _ = await party_mod.accept(b)
        assert ok
        assert party_mod.size(a.player_id) == 2
        await server.handle_enter_dungeon(a, {"dungeon_id": "endless_depths"})
        assert a.dungeon and a.dungeon["id"] == "endless_depths"
        assert b.dungeon and b.dungeon["id"] == "endless_depths"
        assert ED._state(a).get("group_size") == 2
        assert ED._state(b).get("run_id") == ED._state(a).get("run_id")
        # Shared monster dict
        assert a.dungeon["monsters"] is b.dungeon["monsters"]
        alive = [m for m in a.dungeon["monsters"].values() if m.alive]
        assert alive
        # Group HP bump applied
        assert alive[0].max_hp >= ED.scale_stats(alive[0].type, 1, group_size=1)["hp"]
        W.sessions.pop(a.player_id, None)
        W.sessions.pop(b.player_id, None)

    asyncio.run(go())


def test_flavor_tips_theme_clear_cashout_and_banners():
    assert ED.is_boss_floor(10) and not ED.is_boss_floor(9)
    assert ED.is_milestone_floor(25)
    assert "Poison" in (ED.HAZARD_TIP.get("poison") or "")
    assert ED.ambient_line("crypt", 1)

    async def go():
        s = _player("flavor")
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        # Floor 1 enter should emit ambient chat (and crypt has no hazard tip).
        chats = [
            m for m in s.ws.sent
            if m.get("type") == "CHAT_MSG" and m.get("from") == ED.SPEAKER
        ]
        assert chats, "expected Endless Depths ambient on enter"
        # Clear floor 1 — theme first-clear banner + door unlock.
        s.ws.sent.clear()
        _clear_room(s)
        await ED.on_kill(s, next(iter(s.dungeon["monsters"].values())))
        types = [m.get("type") for m in s.ws.sent]
        assert "ENDLESS_BANNER" in types
        theme_banner = next(
            m for m in s.ws.sent
            if m.get("type") == "ENDLESS_BANNER" and m.get("kind") == "theme"
        )
        assert "Crypt" in (theme_banner.get("title") or "")
        assert ED.themes_cleared(s) == ["crypt"]
        # Second clear of crypt theme does not re-grant.
        assert ED.note_theme_clear(s, "crypt") is False

        # Advance — run depth meter bumps; floor 2 ambient/tip.
        s.x, s.y = ED.DOOR[1]
        await ED.on_step(s)
        run = ED._run_of(s)
        assert run and int(run["floors_cleared"]) == 1
        assert int(run["coins_earned"]) > 0
        extra = ED.client_extra(s)
        assert extra["run_cleared"] == 1
        assert extra["run_coins"] == run["coins_earned"]
        assert extra.get("hazard_tip") or extra.get("theme") == "catacomb"

        # Leave — cash-out chat.
        s.ws.sent.clear()
        s.x, s.y = ED.EXIT
        await ED.on_step(s)
        cash = [
            m for m in s.ws.sent
            if m.get("type") == "CHAT_MSG" and "Cash out" in (m.get("text") or "")
        ]
        assert cash, "expected cash-out summary on leave"

        # Continue prompt carries hazard polish when resume floor has one.
        ED.note_continue(s, 5)  # volcanic + fire hazard
        s.ws.sent.clear()
        s.x, s.y = ED.MOUTH
        await server.handle_enter_dungeon(s, {"dungeon_id": "endless_depths"})
        prompt = next(m for m in s.ws.sent if m.get("type") == "ENDLESS_ENTRY_PROMPT")
        assert int(prompt["continue_floor"]) == 5
        assert prompt.get("hazard") == "fire"
        assert prompt.get("hazard_tip")
        W.sessions.pop(s.player_id, None)

    asyncio.run(go())


def test_client_door_labels_and_banner_helpers():
    import endless_depths_client as EDC
    assert EDC._door_label_text(False, remaining=3) == "Clear foes"
    assert EDC._door_label_text(True, boss=False) == "Next level"
    assert EDC._door_label_text(True, boss=True) == "Boss next"
    # Banner open stores until.
    class _C:
        pass
    c = _C()
    EDC.open_banner(c, {"kind": "pb", "title": "New solo best!", "subtitle": "Floor 12", "until": 1e12})
    assert c.endless_banner["kind"] == "pb"
    EDC.open_entry_prompt(c, {
        "continue_floor": 5, "theme": "volcanic", "hazard_label": "Searing heat",
        "hazard_tip": "don't linger", "boss_floor": False, "highest": 12,
    })
    assert c.endless_entry_prompt["hazard_label"] == "Searing heat"
    assert c.endless_entry_prompt["highest"] == 12


def main():
    tests = [
        test_theme_assets_exist,
        test_entrance_village_landmark,
        test_scaling_formulas_and_cap,
        test_room_layout_door_sealed_then_open,
        test_enter_clear_advance_theme_and_reward_once,
        test_milestone_claim_once_and_leave_updates_highest,
        test_resume_does_not_regrant_floor,
        test_monster_pool_excludes_passive_pk,
        test_hazards_on_selected_floors,
        test_solo_hiscores_not_group,
        test_entry_prompt_continue_vs_fresh,
        test_group_scaling_and_shared_enter,
        test_flavor_tips_theme_clear_cashout_and_banners,
        test_client_door_labels_and_banner_helpers,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
    if failed:
        print(f"\n{failed} failed")
        sys.exit(1)
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    main()
