"""Hiscores proofs: login screen + modal with the mockup's data (no server needed).
usage: python3 tools/hiscores_proofs.py <out_dir> [legacy]"""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); CLI = os.path.normpath(os.path.join(HERE, "..", "client"))
if len(sys.argv) > 2 and sys.argv[2] == "legacy":
    sys.modules["hiscores_ui"] = None
sys.path.insert(0, CLI); os.chdir(CLI)
import client, pygame
ROWS = [("The Creator", "First Guild", 447, 2074986), ("Bigaboys", "First Guild", 346, 1589156),
        ("Esteph", "First Guild", 228, 182939), ("Testing", "", 225, 138302), ("noob1", "", 119, 34117),
        ("Fireclaws10", "", 52, 4726), ("Muhahahahaha", "", 45, 3902), ("Alchemon", "", 41, 3871),
        ("Noob", "", 40, 3643), ("Luna Meow", "", 40, 3033), ("Luna Meow2", "", 39, 3092),
        ("dsddsddssd", "", 38, 3076), ("Josh", "", 38, 2966), ("Maximilian Aurelius Thornbury the Third", "", 37, 2800)]


def boards(n_extra=0):
    tot = [{"name": a, "guild": g, "level": l, "xp": x} for a, g, l, x in ROWS]
    for i in range(n_extra):
        tot.append({"name": f"Player{i:04d}", "guild": "", "level": 36 - i // 60, "xp": 2700 - i})
    att = sorted([{"name": a, "guild": g, "level": max(1, l // 14), "xp": x // 15} for a, g, l, x in ROWS], key=lambda e: -e["xp"])
    b = {"total": tot, "guild": [{"name": "First Guild", "guild": "First Guild", "members": 3, "level": 1021, "xp": 3847081},
                                 {"name": "Night Watch", "guild": "Night Watch", "members": 2, "level": 76, "xp": 6969}],
         "attack": att}
    for s in client.XP_SKILLS if hasattr(client, "XP_SKILLS") else []:
        b.setdefault(s, att)
    return b


def shot(g, path, frames=2):
    for _ in range(frames):
        g.draw(); time.sleep(0.01)
    pygame.image.save(g.screen, path); print("saved", path)


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    legacy = len(sys.argv) > 2
    g = client.GameClient()
    g.state = "LOGIN"; g.fields["username"] = "creator"; g.fields["char_name"] = "The Creator"
    b = boards(); g.leaderboard = b
    g.leaderboard_skills = ["total", "guild", "attack", "strength", "defence", "archery", "woodcutting", "mining",
                            "fishing", "cooking", "smithing", "fletching", "karma", "charisma", "etiquette", "command"]
    for s in g.leaderboard_skills:
        b.setdefault(s, b["attack"])
    g.show_leaderboard = True; g.leaderboard_skill = "total"
    pre = "before" if legacy else "after"
    shot(g, f"{out}/{pre}_total.png")
    if legacy:
        os._exit(0)
    import hiscores_ui as H
    pygame.mouse.set_pos((700, 300))
    g.leaderboard_skill = "guild"; shot(g, f"{out}/after_guilds.png")
    g.leaderboard_skill = "woodcutting"; shot(g, f"{out}/after_woodcutting.png")
    g.leaderboard_skill = "total"; g.hs_search = "luna"; g.hs_search_focus = True; shot(g, f"{out}/after_search.png")
    g.hs_search = ""; g.hs_search_focus = False
    g.leaderboard = b = boards(1200); [b.setdefault(s, b["attack"]) for s in g.leaderboard_skills]
    g.fields["char_name"] = "Player0900"; g.draw(); H.jump_to_me(g); shot(g, f"{out}/after_jump_1200rows.png")
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); os._exit(1)
