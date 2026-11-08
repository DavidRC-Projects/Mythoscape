"""Focused safety for this pass. Not the full siege suites.

Flag off keeps ordinary maps and does not create a siege database.
A durable elimination still refuses another deploy. Temporary databases only.
"""
from __future__ import annotations

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_kcs_integration as harness  # noqa: E402


async def elimination_denies_reentry():
    harness.flag(True)
    path, _journal = harness.use_store()
    store, war = harness.open_war()
    session = harness.player()
    harness.enlist(store, war, session, "attack")
    harness.arm_live(store, war)
    await harness.server.handle_enter_dungeon(session, {"dungeon_id": "kings_castle_siege"})
    harness.check(harness.kcs_siege.on_map(session), "deployed before a recorded death")
    session.hp = 0
    session.coins = 40
    await harness.server.resolve_player_death(session, [])
    harness.check(not harness.kcs_siege.on_map(session), "a recorded death leaves the siege map")
    harness.check(session.hp == session.max_hp(), "hit points return after the elimination is durable")
    harness.check(store.roster_status(war.war_id, session.player_id).eliminated,
                  "the elimination is in the siege database")
    await harness.server.handle_enter_dungeon(session, {"dungeon_id": "kings_castle_siege"})
    harness.check(not harness.kcs_siege.on_map(session), "an eliminated player cannot deploy again")
    text = (harness.errors(session.ws)[-1] or "").lower()
    harness.check("eliminated" in text, "the refusal says eliminated")
    harness.check(os.path.basename(path) != "world.db", "the siege database is not world.db")
    live = os.path.join(harness.ROOT, "server", "world.db")
    harness.check(not os.path.exists(live), "this check did not create server/world.db")
    default_kcs = os.path.join(harness.ROOT, "server", "kcs_siege.db")
    harness.check(not os.path.exists(default_kcs), "this check did not create server/kcs_siege.db")


def main():
    asyncio.run(harness.test_flag_off_and_ordinary_maps())
    asyncio.run(elimination_denies_reentry())
    print(f"kcs focused safety ok ({harness.CHECKS} checks)")


if __name__ == "__main__":
    main()
