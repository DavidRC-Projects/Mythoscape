"""Shared fixture for the arena barracks UI test + proofs (no server, no DB)."""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT + "/client"); sys.path.insert(0, ROOT + "/client"); sys.path.insert(0, ROOT + "/server")
sys.argv = ["client.py"]
import pygame  # noqa: E402
import client as C  # noqa: E402
import mercenaries as M  # noqa: E402
import arena_battles as AB  # noqa: E402


class Net:
    def __init__(self): self.sent = []
    def send(self, *a, **k): self.sent.append((a, k))


def soldier(sid, name, tid, gear, lv=(42, 36, 26, 28), cl=104, trains=10, deployed=False, up=None):
    t = M.TEMPLATES[tid]
    return {"id": sid, "template_id": tid, "template_name": t["name"], "name": name, "role": t["role"],
            "ability_label": M.ABILITY_LABELS.get(t.get("ability"), "—"),
            "levels": dict(zip(("attack", "strength", "defence", "hitpoints"), lv)), "combat_level": cl,
            "gear_tier": gear, "equipment": dict(M.TIER_EQUIP[gear]), "train_speed": t["train_speed"],
            "train_cost": 11275, "trains_today": {"cap": 10, "remaining": trains, "used": 10 - trains},
            "blurb": t.get("blurb") or "", "upgrade": up, "deployed": deployed}


def payload(cmd=15, army_cl=1040, highest=4, coins=5460, bank=68_741_833, tab="roster", fights_left=10):
    board = []
    for e in M.PRACTICE_TIERS:
        army = M._normalize_army(e["army"])
        foe = M._snapshot_army_cl(army)
        board.append({"id": e["id"], "name": e["name"], "tier": e["tier"], "unlocked": e["tier"] <= highest,
                      "recommend_cl": e["recommend_cl"], "foe_combat_level": foe, "foe_soldiers": len(army),
                      "your_combat_level": army_cl, "power_gap": army_cl - foe,
                      "command_xp_win": e["command_xp_win"], "command_xp_loss": e["command_xp_loss"],
                      "coin_win": e["coin_win"], "advice": ""})
    bosses = [{"id": f"boss:{t}", "tier": t, "name": b["name"], "title": b["title"], "boss_id": b["id"],
               "ability": b["ability_label"], "unlocked": highest >= t, "beaten": t == 1,
               "drop": AB.GLADIATOR_ITEMS[b["drop"]]["name"], "drop_id": b["drop"]}
              for t, b in AB.BOSSES.items()]
    up = {"to_id": "duelist", "to_name": "Duelist", "command_req": 30, "locked": True, "cost": 9000}
    roster = [soldier(1, "Ivar", "skirmisher", "bronze", up=up), soldier(2, "Garrick", "skirmisher", "iron", up=up),
              soldier(3, "Oona", "skirmisher", "mithril", up=up, deployed=True),
              soldier(4, "Yara", "skirmisher", "steel", up=up)]
    import time
    return {
        "tab": tab, "command_level": cmd, "command_xp": 0, "next_unlock": M.next_unlock(cmd),
        "roster": roster, "roster_total_cl": army_cl, "roster_max": 10,
        "recruit": M.recruitable_templates(cmd, None), "kits": M.kit_catalogue(cmd), "practice": board,
        "ladder": {"rating": 1000, "wins": 0, "losses": 0}, "coins": coins, "bank_coins": bank,
        "mythos_soldier_ready": cmd >= 80,
        "daily_fights": {"used": 10 - fights_left, "cap": 10, "remaining": fights_left},
        "daily_train_cap": 10, "in_castle_realm": True, "deployed_ids": [3], "deployed_count": 1,
        "personal_house": {"name": "House of the Creator", "banner": None},
        "arena": {"renown": 0, "renown_title": "Tiro", "bosses": bosses,
                  "ladder": {"season": 3, "ends_at": time.time() + 3 * 86400, "rating": 1000, "band": "Iron",
                             "wins": 0, "losses": 0},
                  "leaderboard": [{"rank": 1, "name": "Lady Morwen", "rating": 1284, "wins": 9, "losses": 2}],
                  "rivals": [{"id": "rival:7", "name": "Sir Bastian", "soldiers": 10, "roster_cl": 980,
                              "rating": 1040, "elo_win": 18, "elo_loss": -14}]},
    }


def make_client(size=(1200, 800), **kw):
    C.GameClient._connect_stub = True
    g = C.GameClient()
    g.net = Net(); g.dungeon = None
    g.screen = pygame.Surface(size)
    import mercenaries_ui as MU
    MU.open_state(g, payload(**kw))
    return g
