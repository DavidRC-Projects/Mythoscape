"""Title choice prefs. Run: python3 tools/test_titles.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import titles  # noqa: E402
import sewer_tutorial  # noqa: E402
import endless_depths as ED  # noqa: E402


class _WS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(raw)


def _player(name="title_hero"):
    W = server.WORLD
    W.db.create_account(name, "pw", name.title())
    s = server.PlayerSession(_WS(), W.db.get_player_by_username(name))
    s.stats_allocated = True
    W.sessions[s.player_id] = s
    titles.load(s)
    return s


def test_choose_and_clear_title():
    s = _player()
    assert titles.active_label(s) == ""
    # Grant sewer title the same way the reward path does.
    sewer_tutorial._set(
        server.WORLD.db.conn, s.player_id, rewarded=1, title="Ratcatcher", boost_until=0,
    )
    sewer_tutorial.load(s)
    ok, _ = titles.set_active(s, titles.SEWER_TITLE_ID)
    assert ok
    assert titles.active_label(s) == "Ratcatcher"
    assert s.full_state()["title_line"] == "Ratcatcher"
    assert s.public_state()["title_line"] == "Ratcatcher"

    ok, _ = titles.set_active(s, "none")
    assert ok
    assert titles.active_label(s) == ""
    assert s.full_state()["title_line"] == ""

    # Endless milestone unlock becomes choosable.
    ED.load(s)
    ED.note_theme_clear  # touch
    s.endless_milestones = [10]
    server.WORLD.db.conn.execute(
        "INSERT OR IGNORE INTO endless_depths (player_id) VALUES (?)", (s.player_id,),
    )
    ED._set(server.WORLD.db.conn, s.player_id, milestones_claimed=[10], title="Depthseeker")
    ED.load(s)
    ids = {t["id"] for t in titles.earned(s)}
    assert titles.SEWER_TITLE_ID in ids
    assert "endless_10" in ids
    ok, msg = titles.set_active(s, "endless_10")
    assert ok and "Depthseeker" in msg
    assert titles.active_label(s) == "Depthseeker"

    # Noble / house toggles shorten the plate.
    s.noble_rank = 2
    s.house_suffix = "of House Test"
    assert titles.show_noble(s) is True
    titles.set_show_noble(s, False)
    assert s.public_state()["noble_title"] == ""
    titles.set_show_house(s, False)
    assert s.public_state()["house_suffix"] == ""
    server.WORLD.sessions.pop(s.player_id, None)


def main():
    tests = [test_choose_and_clear_title]
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
        sys.exit(1)
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    main()
