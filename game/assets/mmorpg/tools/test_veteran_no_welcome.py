"""Old new-player guide (banner + Next step) is hidden once Seraphine's tour is done (guide_tour >= 100),
and has no Warden Tamsin step any more (her kit was removed)."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "client")); sys.path.insert(0, os.path.join(ROOT, "server")); sys.path.insert(0, os.path.join(ROOT, "shared"))
import pygame
pygame.init(); pygame.display.set_mode((8, 8))
import new_player_guide as G
import hud_v2


class C:
    state = "GAME"; dungeon = None; outfitters = None
    def __init__(self, tour, claimed=False):
        self.player = {"x": 30, "y": 30, "guide_tour": tour, "equipment": {"weapon": "bronze_sword"}, "inventory": {}}
        self.welcome = {"show_path": True, "claimed": claimed, "eat_done": False, "guide": {"x": 36, "y": 22}}
        self.npcs = [{"id": "innkeeper_sarah", "x": 20, "y": 40}, {"id": "elder_miriam", "x": 10, "y": 10}]
        self.quests = {}


def main():
    fails = []
    vet = C(100)
    if G.visible(vet): fails.append("banner visible for guide_tour=100")
    if G.guide_target_npc_id(vet): fails.append("talk target for veteran")
    st = hud_v2._no_quest_step(vet)
    if "Tamsin" in str(st) or st.get("npc") in ("elder_miriam", "warden_tamsin") or st.get("title") == "Learn food & HP": fails.append(f"veteran next step {st}")
    import inspect, re
    src = open(os.path.join(ROOT, "server", "server.py")).read()
    if "Follow the golden trail to me" in src: fails.append("server still sends Tamsin's trail greeting")
    # playtest 30 Oct: during Seraphine's tour (0..11) she is the only objective - no banner on top of her
    if G.visible(C(5)): fails.append("welcome banner drawn over Seraphine's tour")
    new = C(None, claimed=False)      # no tour state (pre-tour client) still gets the guide
    if not G.visible(new): fails.append("new player lost the guide")
    if G._stage(new)[0] != "sarah": fails.append(f"new stage {G._stage(new)[0]}")
    for c in (new, C(0)):
        if "Tamsin" in G._banner_line(c) or "Tamsin" in str(hud_v2._no_quest_step(c)) or G.guide_target_npc_id(c) == "warden_tamsin":
            fails.append("Tamsin still referenced")
    try:
        test_veteran_sidebar_has_no_starter_step()
    except AssertionError as e:
        fails.append(f"sidebar starter step {e}")
    print("FAILS", fails, flush=True) if fails else print("veteran no-welcome tests passed", flush=True)
    os._exit(1 if fails else 0)



def test_veteran_sidebar_has_no_starter_step():
    import types, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
    import hud_v2
    c = types.SimpleNamespace(welcome={"show_path": True}, quests={},
        player={"guide_tour": 100, "equipment": {"weapon": "bronze_sword"}, "inventory": {"1": {"item_id": "cooked_shrimp"}}}, npcs=[])
    step = hud_v2._no_quest_step(c)
    assert step["npc"] not in ("elder_miriam", "innkeeper_sarah", "warden_tamsin"), step
    assert "rat" not in step["title"].lower(), step



main()

