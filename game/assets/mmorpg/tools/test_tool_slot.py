"""Per-skill gather tools (David, 25 Oct 2026). Run: python3 tools/test_tool_slot.py

Axe, pickaxe and fishing net each have their own equip slot. New accounts start with all three
worn. The weapon stays equipped while gathering — the tool for that skill drives the animation.
"""
import asyncio, json, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import server  # noqa: E402
import welcome_kit  # noqa: E402
W, ITEMS = server.WORLD, server.ITEMS
GATHER_TOOLS = ("bronze_axe", "bronze_pickaxe", "small_fishing_net", "fishing_rod", "fly_fishing_rod",
                "lobster_pot", "harpoon")
_N = [0]


class WS:
    def __init__(self):
        self.out = []

    async def send(self, raw):
        self.out.append(json.loads(raw))


def run(c):
    return asyncio.run(c)


def make(clear_tools=True):
    _N[0] += 1
    user = f"ts{_N[0]}"
    W.db.create_account(user, "pw", f"Tool{_N[0]}")
    row = W.db.get_player_by_username(user)
    W.db.save_player_stats(row["id"], stats_allocated=1)
    s = server.PlayerSession(WS(), W.db.get_player_by_username(user))
    s.inventory = W.db.get_inventory(row["id"])
    if clear_tools:
        for skill in ("woodcutting", "mining", "fishing"):
            s.equipment[f"tool_{skill}"] = None
        s.equipment["tool"] = None
        W.db.set_equip_tools(s.player_id, {})
        s.inventory.clear()
    return s


def errors(s):
    return [m["message"] for m in s.ws.out if m.get("type") == "ERROR"]


def bag(s):
    return [e["item_id"] for e in s.inventory.values()]


def equip(s, item_id):
    W.add_item_to_inventory(s, item_id, 1)
    idx = next(i for i, e in s.inventory.items() if e["item_id"] == item_id)
    run(server.handle_equip(s, {"slot_index": idx}))


def node_for(skill, tools=None):
    for (x, y), n in W.resource_nodes.items():
        y_def = server.RESOURCE_YIELDS[n["type"]]
        if y_def["skill"] == skill and not n["depleted"] and y_def["level_req"] <= 1:
            if tools is None or (y_def.get("tools") or [None])[0] in tools or not y_def.get("tools"):
                return x, y, y_def
    raise AssertionError(f"no level-1 {skill} node")


def gather(s, skill):
    x, y, ydef = node_for(skill)
    s.x, s.y, s.dungeon = x, y, None
    W.tick_count += 1
    s.gathering_node = None
    run(server.handle_gather(s, {"x": x, "y": y}))
    return ydef


def test_tools_live_in_tool_slot():
    for t in GATHER_TOOLS:
        assert ITEMS[t]["equip_slot"] == "tool", t
        assert not ITEMS[t].get("att_bonus") and not ITEMS[t].get("str_bonus"), t


def test_new_account_starts_with_all_gather_tools_equipped():
    s = make(clear_tools=False)
    assert s.equipment["tool_woodcutting"] == "bronze_axe"
    assert s.equipment["tool_mining"] == "bronze_pickaxe"
    assert s.equipment["tool_fishing"] == "small_fishing_net"
    assert "bronze_axe" not in bag(s) and "bronze_pickaxe" not in bag(s)
    assert "small_fishing_net" not in bag(s)
    # Weapon slot is free for the Recruit sword — tools don't occupy it.
    assert s.equipment.get("weapon") in (None, "recruit_bronze_sword", "bronze_sword")


def test_equip_per_skill_keeps_other_tools_and_weapon():
    s = make()
    s.equipment["weapon"] = "bronze_sword"
    equip(s, "bronze_pickaxe")
    equip(s, "bronze_axe")
    equip(s, "small_fishing_net")
    assert s.equipment["tool_mining"] == "bronze_pickaxe"
    assert s.equipment["tool_woodcutting"] == "bronze_axe"
    assert s.equipment["tool_fishing"] == "small_fishing_net"
    assert s.equipment["weapon"] == "bronze_sword"
    assert bag(s) == []
    tools = W.db.get_equip_tools(s.player_id)
    assert tools["mining"] == "bronze_pickaxe" and tools["woodcutting"] == "bronze_axe"
    run(server.handle_unequip(s, {"equip_slot": "tool_mining"}))
    assert s.equipment["tool_mining"] is None and "bronze_pickaxe" in bag(s)
    assert s.equipment["tool_woodcutting"] == "bronze_axe"


def test_gathering_uses_per_skill_tool_without_swapping():
    s = make()
    for t in ("bronze_axe", "bronze_pickaxe", "small_fishing_net"):
        equip(s, t)
    s.equipment["weapon"] = "bronze_sword"
    gather(s, "woodcutting")
    assert s.gathering_node is not None and W.gather_tool_id(s, "woodcutting") == "bronze_axe"
    s.gathering_node = None
    gather(s, "mining")
    assert s.gathering_node is not None and W.gather_tool_id(s, "mining") == "bronze_pickaxe"
    assert s.equipment["weapon"] == "bronze_sword"


def test_bag_only_tool_is_not_enough():
    s = make()
    W.add_item_to_inventory(s, "bronze_axe", 1)
    gather(s, "woodcutting")
    assert s.gathering_node is None and "Equip an axe" in errors(s)[-1], errors(s)


def test_tool_slot_carries_no_combat():
    s = make()
    s.equipment["tool_woodcutting"] = "bronze_axe"
    s._sync_legacy_tool_slot()
    assert s.weapon_bonuses()["att_bonus"] == 0 and s.weapon_bonuses()["str_bonus"] == 0


def test_legacy_weapon_slot_tool_migrates():
    s = make()
    W.db.set_equipment(s.player_id, "weapon", "bronze_pickaxe")
    t = server.PlayerSession(WS(), W.db.get_player_by_id(s.player_id))
    assert t.equipment["tool_mining"] == "bronze_pickaxe" and t.equipment["weapon"] is None
    tools = W.db.get_equip_tools(s.player_id)
    assert tools.get("mining") == "bronze_pickaxe"


def test_tutorial_teaches_tools():
    flat = " ".join(" ".join(p) for p in welcome_kit.TOUR)
    assert welcome_kit.TOOLS_STEP in welcome_kit.TOUR
    for word in ("equipped", "Equipment", "axe", "pickaxe", "Crypt"):
        assert word in flat, word


def test_equipment_screen_has_tool_slots():
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import pygame
    pygame.init()
    import equipment_ui_v2 as ui
    for key in ("tool_woodcutting", "tool_mining", "tool_fishing"):
        assert key in ui.DOLL and key in ui.ANCHOR
    surf = pygame.Surface((46, 46))
    ui._silhouette(surf, "tool_mining", surf.get_rect())


def test_crypt_is_early_quest():
    from content import QUESTS, NPCS
    q = QUESTS["crypt_first_delve"]
    assert q["requires"] == "rat_problem" and q["target"] == "skeleton"
    miriam = next(n for n in NPCS if n["id"] == "elder_miriam")
    assert "crypt_first_delve" in miriam["quest_ids"]
    assert "Crypt" in q["description"] and "Tidehollow" in q["description"]


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok  ", name)
        except Exception:
            failed += 1
            import traceback
            traceback.print_exc()
            print("FAIL", name)
    print(f"{len(tests) - failed}/{len(tests)} tool slot tests passed")
    sys.exit(1 if failed else 0)
