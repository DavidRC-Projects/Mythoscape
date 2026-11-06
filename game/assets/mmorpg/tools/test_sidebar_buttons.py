"""Click every right-sidebar / chat chrome control and assert state changes."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [
    os.path.join(ROOT, "client"),
    os.path.join(ROOT, "server"),
    os.path.join(ROOT, "..", "characters"),
]

import pygame

pygame.init()
screen = pygame.display.set_mode((1200, 800))

import equipment_ui_v2
import guide_tour
import hud_drawn
import hud_v2
from content import ITEMS


class Net:
    def __init__(self):
        self.sent = []

    def send(self, kind, **kw):
        self.sent.append((kind, kw))


class C:
    def __init__(self):
        self.screen = screen
        self.state = "GAME"
        skills = (
            "attack", "strength", "defence", "archery", "woodcutting",
            "mining", "fishing", "cooking", "smithing", "fletching",
        )
        self.player = {
            "name": "T", "x": 1, "y": 1, "hp": 10, "max_hp": 10, "coins": 1, "mythos": 0,
            "inventory": {
                "0": {"item_id": "bronze_sword", "qty": 1},
                "1": {"item_id": "bread", "qty": 2},
            },
            "equipment": {},
            "skills": {k: {"level": 1, "xp": 0} for k in skills},
            "quests": {}, "guide_tour": 100, "clan": None, "pet": None, "owned_pets": [],
            "karma": 0, "gender": "male", "appearance_saved": True, "has_food_bag": False,
        }
        self.net = Net()
        for n, s in (("font", 20), ("font_small", 18), ("font_tiny", 15), ("font_big", 30)):
            setattr(self, n, pygame.font.SysFont(None, s))
        self.font_login = self.font
        for k in (
            "show_inventory", "show_equipment", "show_help", "show_skills", "show_pets",
            "show_travel", "show_forge", "show_cook", "show_fletch", "show_bank",
            "show_shop_panel", "show_world_map", "show_teleport",
        ):
            setattr(self, k, False)
        self.show_inventory = True
        for k in (
            "dialogue", "dungeon", "context_menu", "examine_target", "minimap_rect",
            "teleport_btn_rect", "royal_panel", "shop", "arena_cinematic", "outfitters",
            "resting_ox", "moon_petal", "guild_prompt", "fire_prompt", "drop_prompt",
            "arrow_prompt", "tip_prompt", "food_prompt", "raw_prompt", "food_bag_prompt",
            "storage_bag_prompt", "pack_prompt", "log_prompt", "potion_prompt",
            "cook_prompt", "combat_style_prompt", "dungeon_prompt", "show_wish",
            "wish_stat_choice", "loot_prompt", "floor_loot_prompt", "bone_prompt",
            "monster_drops_panel", "inv_drag", "trade_state", "trade_incoming",
        ):
            setattr(self, k, None)
        self.quests = {}
        self.npcs = []
        self.interactables = []
        self.resources = {}
        self.chat_log = []
        self.chat_typing = False
        self.chat_text = ""
        self.hud_channel = "world"
        self.housing_open = False
        self.needs_appearance = False
        self.help_scroll = 0
        self.skills_scroll = 0
        self.tracked_quest_id = None
        self._nameplate_queue = []
        self._logged_out = False
        self.hud_focus = None
        self.hud_system = "crafting"
        self.hud_filter = "all"
        self.hud_selected = None
        self.hud_inv_scroll = 0
        self.hud_menu = False
        self._inv_clicked = None

    def player_combat_level(self):
        return 3

    def player_total_level(self):
        return 30

    def player_xy(self):
        return 1, 1

    def hp_tone(self, hp, mh):
        return (80, 180, 80), (hp / mh if mh else 0)

    def add_chat(self, *a, **k):
        pass

    def logout(self):
        self._logged_out = True

    def toggle_skills_modal(self):
        self.show_skills = not self.show_skills

    def toggle_pets_modal(self):
        self.show_pets = not self.show_pets

    def toggle_auto_pickup(self):
        pass

    def near_forge(self):
        return False

    def open_forge_at(self):
        pass

    def open_fletch(self):
        pass

    def open_cook(self):
        pass

    def open_drop_prompt(self, *a):
        pass

    def travel_to_destination(self, *a):
        pass

    def walk_and_act(self, *a):
        pass

    def adjacent_goals(self, *a):
        return []

    def inventory_slot_rects(self):
        return (getattr(self, "hud_rects", None) or {}).get("slots") or {}

    def handle_inventory_click(self, mx, my, button):
        self._inv_clicked = (mx, my, button)

    def open_bag_browser(self, *a, **k):
        pass

    def track_quest(self, qid):
        self.tracked_quest_id = qid

    def try_open_bank(self):
        pass

    def _begin_chat_typing(self):
        self.chat_typing = True


def main():
    c = C()
    results = []

    def redraw(system="inventory", focus=None):
        # ensure() only initializes once; set system/focus after the first paint.
        if not getattr(c, "_hud_ready", False):
            hud_v2.draw_sidebar(c)
        c.hud_system = system
        c.hud_focus = focus
        hud_v2.draw_sidebar(c)
        hud_drawn.draw_chat(c)
        return c.hud_rects or {}

    def must(label, rect, prepare, check):
        if rect is None:
            results.append((label, "MISSING"))
            return
        prepare()
        c.net.sent.clear()
        c._inv_clicked = None
        c._logged_out = False
        hud_v2.handle_sidebar_click(c, rect.centerx, rect.centery, 1)
        ok = bool(check())
        detail = ""
        if not ok:
            detail = (
                f"sys={c.hud_system} eq={c.show_equipment} sk={c.show_skills} "
                f"help={c.show_help} filt={c.hud_filter} focus={c.hud_focus} "
                f"ch={c.hud_channel} type={c.chat_typing} sel={c.hud_selected} "
                f"out={c._logged_out} sent={c.net.sent} inv={c._inv_clicked}"
            )
        results.append((label, "OK" if ok else f"DEAD {detail}"))

    rects = redraw("crafting")
    must(
        "system:inventory",
        (rects.get("systems") or {}).get("inventory"),
        lambda: setattr(c, "hud_system", "crafting"),
        lambda: c.hud_system == "inventory",
    )
    for key in ("crafting", "gathering", "bags"):
        rects = redraw("inventory")
        must(
            f"system:{key}",
            (rects.get("systems") or {}).get(key),
            lambda: setattr(c, "hud_system", "inventory"),
            lambda k=key: c.hud_system == k,
        )

    rects = redraw("inventory")
    for key, r in (rects.get("filters") or {}).items():
        must(
            f"filter:{key}",
            r,
            lambda: setattr(c, "hud_filter", "quest" if key != "quest" else "all"),
            lambda k=key: c.hud_filter == k,
        )

    rects = redraw("inventory")
    must("equipment", rects.get("equipment"), lambda: setattr(c, "show_equipment", False), lambda: c.show_equipment)
    must("skills", rects.get("skills"), lambda: setattr(c, "show_skills", False), lambda: c.show_skills)
    must("settings", rects.get("settings"), lambda: setattr(c, "show_help", False), lambda: c.show_help)
    must("logout", rects.get("header_logout"), lambda: setattr(c, "_logged_out", False), lambda: c._logged_out)

    c.hud_filter = "all"
    rects = redraw("inventory")
    slots = list((rects.get("slots") or {}).items())
    if not slots:
        results.append(("slots", "MISSING — inventory grid empty"))
    for slot, r in slots[:3]:
        must(
            f"slot:{slot}",
            r,
            lambda: setattr(c, "hud_selected", None),
            lambda s=slot: c.hud_selected == s or c._inv_clicked is not None,
        )

    rects = redraw("inventory")
    must("utility:pets", (rects.get("utility") or {}).get("pets"), lambda: setattr(c, "show_pets", False), lambda: c.show_pets)
    must("utility:lore", (rects.get("utility") or {}).get("lore"), lambda: setattr(c, "hud_focus", None), lambda: c.hud_focus == "lore")
    must(
        "utility:achievements",
        (rects.get("utility") or {}).get("achievements"),
        lambda: setattr(c, "hud_focus", None),
        lambda: c.hud_focus == "achievements",
    )
    must("utility:menu", (rects.get("utility") or {}).get("menu"), lambda: setattr(c, "hud_menu", False), lambda: c.hud_menu)
    must("utility:mounts", (rects.get("utility") or {}).get("mounts"), lambda: setattr(c, "hud_focus", None), lambda: c.hud_focus == "mounts")

    rects = redraw("inventory")
    for key, r in (rects.get("channels") or {}).items():
        must(
            f"channel:{key}",
            r,
            lambda: setattr(c, "hud_channel", "__other__"),
            lambda k=key: c.hud_channel == k,
        )
    for key, r in (rects.get("quick") or {}).items():
        must(
            f"quick:{key}",
            r,
            lambda: c.net.sent.clear(),
            lambda: any(s[0] == "CHAT" for s in c.net.sent),
        )
    must("chat_input", rects.get("chat_input"), lambda: setattr(c, "chat_typing", False), lambda: c.chat_typing)

    print("=== RESULTS ===")
    fail = []
    for label, status in results:
        print(f"{status:6} {label}" if status == "OK" else f"{status} :: {label}")
        if status != "OK":
            fail.append(label)
    print(f"{len(results) - len(fail)}/{len(results)} OK")
    if fail:
        raise SystemExit("FAILED: " + ", ".join(fail))

    rects = redraw("inventory")
    eq = rects["equipment"]
    c.show_equipment = True
    c._equip_layout = None
    assert equipment_ui_v2.handle_click(c, eq.centerx, eq.centery, ITEMS) == "outside"
    hud_v2.handle_sidebar_click(c, eq.centerx, eq.centery, 1)
    assert c.show_equipment is False
    assert guide_tour.handle_click(
        c, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=eq.center)
    ) is False
    # Real mouse order: combat-bar handler runs BEFORE the sidebar.
    # A mis-indented `return True` used to swallow Logout / Equipment / Skills
    # while bag-slot drags still worked.
    def dispatch(mx, my):
        if hud_drawn.handle_click(c, mx, my, 1):
            return "drawn"
        if hud_v2.handle_world_chrome_click(c, mx, my, 1):
            return "world"
        hud_v2.handle_sidebar_click(c, mx, my, 1)
        return "sidebar"

    gate = [
        ("gate:logout", rects["header_logout"], lambda: setattr(c, "_logged_out", False), lambda: c._logged_out),
        ("gate:settings", rects["settings"], lambda: setattr(c, "show_help", False), lambda: c.show_help),
        ("gate:equipment", rects["equipment"], lambda: setattr(c, "show_equipment", False), lambda: c.show_equipment),
        ("gate:skills", rects["skills"], lambda: setattr(c, "show_skills", False), lambda: c.show_skills),
        ("gate:filter", rects["filters"]["weapons"], lambda: setattr(c, "hud_filter", "all"), lambda: c.hud_filter == "weapons"),
        ("gate:system", rects["systems"]["bags"], lambda: setattr(c, "hud_system", "inventory"), lambda: c.hud_system == "bags"),
    ]
    for label, rect, prepare, check in gate:
        prepare()
        who = dispatch(rect.centerx, rect.centery)
        ok = who == "sidebar" and check()
        results.append((label, "OK" if ok else f"DEAD via {who}"))
        print(("OK" if ok else "DEAD"), label, "via", who)
        if not ok:
            fail.append(label)
    pets = (c.hud_world_rects or {}).get("utility", {}).get("pets")
    c.show_pets = False
    who = dispatch(pets.centerx, pets.centery) if pets else "missing"
    ok = who in ("drawn", "world") and c.show_pets
    print(("OK" if ok else "DEAD"), "gate:pets", "via", who)
    if not ok:
        fail.append("gate:pets")
    who = dispatch(120, 200)
    print("world miss via", who)
    if who != "sidebar":
        fail.append("gate:world-miss")
    if fail:
        raise SystemExit("FAILED: " + ", ".join(fail))
    print("ALL BUTTON TESTS PASSED")


if __name__ == "__main__":
    main()
