"""Daggers are gone from content; old saves migrate to the same-tier sword."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

import content  # noqa: E402
from item_migrations import DAGGER_TO_SWORD, migrate_daggers  # noqa: E402


def test_no_dagger_items_or_recipes():
    assert not [i for i in content.ITEMS if "dagger" in i]
    assert "dagger" not in repr(vars(content)).lower()
    for sword in DAGGER_TO_SWORD.values():
        assert sword in content.ITEMS


def test_fake_save_migrates_everything():
    daggers = list(DAGGER_TO_SWORD)
    inv = {i: {"item_id": d, "qty": i + 1} for i, d in enumerate(daggers)}
    bank = {i + 10: {"item_id": d, "qty": 3} for i, d in enumerate(daggers)}
    eq = {"weapon": "mythos_dagger", "shield": None, "body": "steel_body"}
    a = migrate_daggers(inv, bank, eq)
    assert len(a[0]) == 6 and len(a[1]) == 6 and a[2] == ["weapon"]
    for i, d in enumerate(daggers):
        assert inv[i] == {"item_id": DAGGER_TO_SWORD[d], "qty": i + 1}
        assert bank[i + 10] == {"item_id": DAGGER_TO_SWORD[d], "qty": 3}
    assert eq == {"weapon": "mythos_longsword", "shield": None, "body": "steel_body"}
    assert migrate_daggers(inv, bank, eq) == ([], [], [])  # idempotent


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
