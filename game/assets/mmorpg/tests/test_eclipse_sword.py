"""eclipse_sword item exists with sword-class stats and maps to its HD layer."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
sys.path.insert(0, os.path.join(ROOT, "client"))

from content import ITEMS  # noqa: E402
import player_hd_client as hd  # noqa: E402


def test_eclipse_sword_stats():
    sword, cleaver, mythos = ITEMS["eclipse_sword"], ITEMS["eclipse_cleaver"], ITEMS["mythos_longsword"]
    assert sword["equip_slot"] == "weapon" and sword["name"] == "Eclipse Sword"
    assert sword["att_bonus"] == cleaver["att_bonus"] + 6
    assert sword["str_bonus"] == cleaver["str_bonus"] - 6
    assert sword["str_bonus"] >= mythos["str_bonus"] and sword["att_bonus"] >= mythos["att_bonus"]
    assert sword.get("def_bonus") == cleaver.get("def_bonus")
    assert sword["bound_username"] == cleaver["bound_username"]
    assert sword["tradeable"] is False and sword["sellable"] is False


def test_eclipse_sword_layer():
    assert hd._weapon_spec("eclipse_sword")[0] == "wpn_sword_eclipse"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
