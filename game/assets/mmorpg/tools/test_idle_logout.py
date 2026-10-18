"""Idle logout and combat linger (COMBAT_SKILLING_SPEC part 4). Run: python3 tools/test_idle_logout.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402

W = server.WORLD
_N = [0]


class _WS:
    def __init__(self):
        self.sent, self.closed = [], False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self, *a, **k):
        self.closed = True

    def types(self):
        return [m.get("type") for m in self.sent]


def _player(pk=False):
    _N[0] += 1
    name = f"idler{_N[0]}"
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    s.player_killer = pk
    W.sessions[s.player_id] = s
    return s


async def _tick_to(target):
    while W.tick_count < target:
        W.tick_count += 1
        await server.process_idle()
        await asyncio.sleep(0)


def _go(coro):
    asyncio.run(coro)


def test_constants():
    assert server.IDLE_WARN_TICKS * server.TICK_SECONDS == 270        # 4:30
    assert server.IDLE_LOGOUT_TICKS * server.TICK_SECONDS == 300      # 5:00
    assert round(server.COMBAT_LINGER_TICKS * server.TICK_SECONDS) == 10
    assert server.PK_LINGER_TICKS * server.TICK_SECONDS == 60


def test_warning_clear_and_logout():
    async def go():
        s = _player()
        t0 = W.tick_count
        await server.note_real_input(s)
        await _tick_to(t0 + 449)
        assert "IDLE_WARNING" not in s.ws.types()
        await _tick_to(t0 + 450)
        warn = [m for m in s.ws.sent if m["type"] == "IDLE_WARNING"]
        assert len(warn) == 1 and warn[0]["seconds"] == 30
        await server.note_real_input(s)                         # any action cancels it
        assert s.ws.types()[-1] == "IDLE_CLEAR" and not s.idle_warned
        t1 = W.tick_count
        await _tick_to(t1 + 499)
        assert "LOGGED_OUT" not in s.ws.types()
        await _tick_to(t1 + 500)
        assert s.ws.sent[-1] == {"type": "LOGGED_OUT", "reason": "idle"} and s.ws.closed
        assert not server._should_linger(s)
        await server.logout_session(s, "disconnect")            # what the handler's finally does next
        assert s.player_id not in W.sessions
    _go(go())


def test_combat_defers_logout():
    async def go():
        s = _player()
        t0 = W.tick_count
        await server.note_real_input(s)
        s.in_combat_with = ("monster", 1)
        await _tick_to(t0 + 520)
        assert "LOGGED_OUT" not in s.ws.types()
        s.in_combat_with = None                                 # last combat tick = t0 + 520
        await _tick_to(t0 + 536)
        assert "LOGGED_OUT" not in s.ws.types()
        await _tick_to(t0 + 537)                                # 10 s after the fight
        assert "LOGGED_OUT" in s.ws.types()
        await server.logout_session(s)
        # taking damage counts as combat too
        s2 = _player()
        t0 = W.tick_count
        await server.note_real_input(s2)
        await _tick_to(t0 + 495)
        s2.hp -= 3
        await _tick_to(t0 + 511)
        assert "LOGGED_OUT" not in s2.ws.types()
        await _tick_to(t0 + 513)
        assert "LOGGED_OUT" in s2.ws.types()
        await server.logout_session(s2)
    _go(go())


def test_pings_alone_cannot_keep_you_on():
    async def go():
        s = _player()
        t0 = W.tick_count
        await server.note_real_input(s)
        for k in range(1, 40):
            await _tick_to(t0 + 50 * k)
            await server.idle_input_ping(s, {"last_input_ms_ago": 0})
            if "LOGGED_OUT" in s.ws.types():
                break
        assert "LOGGED_OUT" in s.ws.types()
        assert W.tick_count - t0 <= server.IDLE_LOGOUT_TICKS + server.INPUT_PING_GRACE_TICKS
        await server.logout_session(s)
        # a ping can't claim input in the future, and garbage is ignored
        s2 = _player()
        await server.note_real_input(s2)
        await server.idle_input_ping(s2, {"last_input_ms_ago": -99999})
        assert s2.last_input_tick <= W.tick_count
        await server.idle_input_ping(s2, {"last_input_ms_ago": "lots"})
        await server.logout_session(s2)
    _go(go())


def test_disconnect_mid_fight_leaves_body():
    async def go():
        for pk, ticks in ((False, 17), (True, 100)):
            s = _player(pk)
            await server.note_real_input(s)
            s.in_combat_with = ("monster", 7)
            await _tick_to(W.tick_count + 1)
            assert server._should_linger(s)
            await server.begin_linger(s)                        # alt-F4 mid-fight
            assert isinstance(s.ws, server._GhostSocket) and W.sessions.get(s.player_id) is s
            s.in_combat_with = None
            t_last = W.tick_count
            await _tick_to(t_last + 5)
            s.hp -= 2                                           # still attackable: a hit resets the clock
            await _tick_to(W.tick_count + 1)
            t_last = W.tick_count
            await _tick_to(t_last + ticks - 1)
            assert W.sessions.get(s.player_id) is s
            await _tick_to(t_last + ticks)
            assert s.player_id not in W.sessions, (pk, ticks)
    _go(go())


def test_login_refused_while_body_lingers():
    async def go():
        s = _player()
        s.in_combat_with = ("monster", 9)
        await server.begin_linger(s)
        ws = _WS()
        await server.handle_login(ws, {"username": s.username, "password": "pw"}, is_register=False)
        assert ws.sent[-1]["type"] == "LOGIN_FAIL" and "still in a fight" in ws.sent[-1]["reason"]
        await server.logout_session(s)
    _go(go())


def test_idle_dev_toggle():
    async def go():
        s = _player()
        s.idle_exempt = True
        t0 = W.tick_count
        await server.note_real_input(s)
        await _tick_to(t0 + 600)
        assert "IDLE_WARNING" not in s.ws.types() and "LOGGED_OUT" not in s.ws.types()
        await server.logout_session(s)
    _go(go())


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"ALL {len(tests)} IDLE LOGOUT TESTS PASSED")
