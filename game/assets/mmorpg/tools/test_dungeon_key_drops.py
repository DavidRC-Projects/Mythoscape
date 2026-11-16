"""Dungeon keys only auto-drop in their home dungeon; players may drop keys."""
from __future__ import annotations

import asyncio
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server")
sys.path.insert(0, SERVER)

os.environ.setdefault("CROWNFALL_DB_PATH", ":memory:")

import content
import server


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(raw)

    def last(self, kind=None):
        import json
        for raw in reversed(self.sent):
            msg = json.loads(raw) if isinstance(raw, str) else raw
            if kind is None or msg.get("type") == kind:
                return msg
        return None


def _session(dungeon=None):
    s = types.SimpleNamespace(
        dungeon=dungeon,
        inventory={},
        equipment={},
        bank={},
        player_id=1,
        username="tester",
        x=10,
        y=10,
        coins=0,
        ws=FakeWS(),
        trade_partner_id=None,
    )
    return s


def check(ok, msg):
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


def test_home_tags():
    check(server.session_dungeon_bound_tag(_session(None)) is None, "overworld has no key home")
    check(
        server.session_dungeon_bound_tag(_session({"id": "endless_depths", "explore": True})) is None,
        "endless depths has no key home",
    )
    check(
        server.session_dungeon_bound_tag(_session({"id": "sanctum", "v2": True})) == "sanctum_v2",
        "sanctum maps to sanctum_v2",
    )
    check(
        server.session_dungeon_bound_tag(_session({"id": "depths", "v2": "depths"})) == "depths_v2",
        "depths maps to depths_v2",
    )


def test_monster_drop_gate():
    endless = _session({"id": "endless_depths", "explore": True})
    sanctum = _session({"id": "sanctum", "v2": True})
    depths = _session({"id": "depths", "v2": "depths"})
    overworld = _session(None)

    check(not server.item_may_monster_drop(endless, "void_key_amethyst"),
          "void key blocked in endless")
    check(not server.item_may_monster_drop(endless, "depths_bone_key"),
          "depths key blocked in endless")
    check(not server.item_may_monster_drop(overworld, "void_key_amethyst"),
          "void key blocked on overworld")
    check(server.item_may_monster_drop(sanctum, "void_key_amethyst"),
          "void key allowed in sanctum")
    check(server.item_may_monster_drop(depths, "depths_bone_key"),
          "bone key allowed in depths")
    check(not server.item_may_monster_drop(sanctum, "depths_bone_key"),
          "depths key blocked in sanctum")
    check(server.item_may_monster_drop(endless, "coins"),
          "normal loot still allowed in endless")


def test_grant_table_skips_foreign_keys():
    # Force the always-drop key row through _grant_monster_table in endless.
    monster = types.SimpleNamespace(type="ossuary_keeper")
    s = _session({"id": "endless_depths", "explore": True})
    s.full_state = lambda: {"inventory": s.inventory}
    added = []

    def _add(session, item_id, qty):
        added.append(item_id)
        return True

    old_add = server.WORLD.add_item_to_inventory
    old_coins = server.WORLD.add_coins
    server.WORLD.add_item_to_inventory = _add
    server.WORLD.add_coins = lambda session, qty: (qty, 0)
    try:
        asyncio.run(server._grant_monster_table(s, monster))
    finally:
        server.WORLD.add_item_to_inventory = old_add
        server.WORLD.add_coins = old_coins
    check("depths_bone_key" not in added, "bone key not granted in endless kill loot")


def test_player_may_drop_keys():
    for key_id in (
        "void_key_amethyst", "void_key_obsidian", "void_rift_sigil",
        "depths_bone_key", "depths_tide_key", "depths_knight_seal", "petaldeep_key",
    ):
        check(server.item_is_droppable(key_id), f"{key_id} is droppable")
    # David-held Rift Sigil must be discardable (not blocked as untradeable).
    check(server.item_is_droppable("void_rift_sigil"), "rift sigil droppable for any account")
    bag = next(
        (iid for iid, it in content.ITEMS.items()
         if it.get("unique") and it.get("type") != "key"),
        None,
    )
    if bag:
        check(not server.item_is_droppable(bag), f"unique non-key {bag} still locked")


def test_handle_drop_key():
    s = _session({"id": "endless_depths", "explore": True})
    s.inventory[0] = {"item_id": "depths_bone_key", "qty": 1}
    s.full_state = lambda: {"inventory": s.inventory}
    removed = []

    def _remove(session, item_id, qty):
        removed.append((item_id, qty))
        session.inventory.pop(0, None)

    old_remove = server.WORLD.remove_item_qty
    server.WORLD.remove_item_qty = _remove
    try:
        asyncio.run(server.handle_drop(s, {"slot_index": 0, "qty": 1}))
    finally:
        server.WORLD.remove_item_qty = old_remove
    check(removed == [("depths_bone_key", 1)], "key left the inventory on drop")
    pile = server.WORLD.ground_items.get((s.x, s.y)) or []
    check(any(e.get("item_id") == "depths_bone_key" for e in pile), "key landed on the ground")


def main():
    test_home_tags()
    test_monster_drop_gate()
    test_grant_table_skips_foreign_keys()
    test_player_may_drop_keys()
    test_handle_drop_key()
    print("dungeon key drop tests ok")


if __name__ == "__main__":
    main()
