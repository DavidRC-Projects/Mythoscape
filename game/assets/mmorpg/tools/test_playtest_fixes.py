"""Early-game playtest fixes (30 Oct 2026): one objective during the tour, equip hint after skip,
reading never idles out, CLICK HERE has no font-glyph arrow."""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "client")); sys.path.insert(0, os.path.join(ROOT, "server")); sys.path.insert(0, os.path.join(ROOT, "shared")); os.chdir(os.path.join(ROOT, "client"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import hud_v2, new_player_guide, idle_client


class C:
    def __init__(self, gt, equip=None, inv=None):
        self.player = {"guide_tour": gt, "equipment": equip or {}, "inventory": inv or {}}
        self.quests = {}; self.welcome = {"show_path": True}; self.state = "GAME"
        self.outfitters = None; self.dungeon = None; self.npcs = []
        self.dialogue = None; self.bank = None; self.show_shop_panel = False; self.housing_open = False
        self.needs_appearance = False


def test_tour_owns_objective():
    for gt in (0, 3, 11):
        c = C(gt)
        assert hud_v2._no_quest_step(c)["title"] == "Follow Seraphine's tour", gt
        assert not new_player_guide.visible(c)


def test_skip_with_kit_in_bag_says_equip():
    c = C(101, inv={"0": {"item_id": "bronze_sword", "qty": 1}})
    assert hud_v2._no_quest_step(c)["title"] == "Equip your weapon"
    c.player["equipment"] = {"weapon": "bronze_sword"}
    assert hud_v2._no_quest_step(c)["title"] != "Equip your weapon"


def test_reading_counts_as_input():
    sent = []
    c = C(100); c.net = type("N", (), {"send": lambda self, t, **k: sent.append(k)})()
    st = idle_client._state(c); st["last_input"] = time.time() - 400; st["last_ping"] = 0
    c.dialogue = {"npc": "x"}
    idle_client.tick(c)
    assert sent and sent[-1]["last_input_ms_ago"] < 1000


def test_click_here_no_glyph():
    src = open("ui_coach.py", encoding="utf-8").read()
    assert '"→ CLICK HERE"' not in src and '"CLICK HERE"' in src


def test_rat_problem_beats_optional_sewer():
    c = C(100)
    c.quests = {"below_the_village": {"status": "active", "progress": 1}, "rat_problem": {"status": "active", "progress": 0}}
    c.tracked_quest_id = None
    assert hud_v2._tracked_quest_id(c) == "rat_problem", hud_v2._tracked_quest_id(c)


def test_tour_panel_dim_is_light():
    import guide_tour
    assert guide_tour.DIM_PANEL_A <= 60


if __name__ == "__main__":
    ok = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try: f(); ok += 1; print("ok  ", n)
            except Exception as e: import traceback; traceback.print_exc(); print("FAIL", n)
    print(ok, "passed"); sys.exit(0 if ok == 6 else 1)
