"""Full in-game frame for HUD proofs (throwaway server on a free port, scratch DB copy).
usage: python3 tools/hud_proof_shot.py <out.png> [scale_w scale_h]
Env HUD_PROOF_PATCH=1 fills the pack / coins so the sidebar shows a busy state."""
import os, sys, time, shutil, tempfile
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T


def main():
    if os.environ.get("HUD_PROOF_NO_NP"):  # proof "before": force the legacy tag path
        sys.modules["nameplates"] = None
    out = sys.argv[1]
    src = os.environ.get("CROWNFALL_DB_PATH") or "/workspace/crownfall_mirror/testdb/world.db"
    db = os.path.join(tempfile.mkdtemp(prefix="hudproof_"), "world.db")
    if os.environ.get("HUD_PROOF_COPYDB"):
        shutil.copy(src, db)
    port = T.free_port(); T.start_server(port, db)
    sys.path.insert(0, T.CLI); os.chdir(T.CLI)
    import client, pygame, idle_client
    client.SERVER_URI = f"ws://127.0.0.1:{port}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    name = "hp%d" % (int(time.time() * 1000) % 10**7)
    g.login_mode = "register"; g.fields.update(username=name, password="pw1234567", confirm="pw1234567", password2="pw1234567", char_name="Aldric")
    g.submit_login()

    def frame():
        g.handle_network(); g.update_walk(); g.handle_events()
        idle_client.tick(g); g._pump_zoom(); g.update_inventory_hover(); g.draw()
    sent = False
    for i in range(1600):
        frame()
        if g.state == "STAT_ALLOC" and not sent and getattr(g, "stat_preset_rects", None):
            g.stat_alloc = dict(g.stat_preset_rects[0][1]); g.submit_stat_alloc(); sent = True
        elif g.state in ("OPENING_COMIC", "THRONE_VISION") and i % 15 == 0:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        elif g.state == "GAME" and i > 200:
            break
        if i % 200 == 0:
            print("state", i, g.state, repr(g.login_error), g.net.connected, flush=True)
        time.sleep(1 / 120)
    for _ in range(int(os.environ.get('HUD_PROOF_SETTLE', '60'))):
        frame(); time.sleep(1 / 60)
    for attr in ("guide_tour_state",):
        pass
    try:
        import guide_tour; guide_tour.stop(g)
    except Exception:
        pass
    g.needs_appearance = False
    g.player["guide_tour"] = 100
    try:
        g.outfitters.active = False
    except Exception:
        pass
    if os.environ.get("HUD_PROOF_PATCH"):
        p = g.player
        p["coins"] = 5516; p["bank_coins"] = 68741833
        inv = p.get("inventory") or {}
        ids = ["bones", "iron_ore", "mythos_longsword", "adamant_battleaxe", "shrimp", "logs", "bronze_helmet", "big_bones"]
        for k, iid in enumerate(ids):
            inv[str(10 + k)] = {"item_id": iid, "qty": (k * 7) % 23 + 1}
        p["inventory"] = inv
    if os.environ.get("HUD_PROOF_HP"):
        g.player["hp"] = max(1, int(g.player.get("max_hp", 10) * float(os.environ["HUD_PROOF_HP"])))
    scene = os.environ.get("HUD_PROOF_SCENE")
    if scene:  # client-side units only, for nameplate proofs
        px, py = g.player_xy()
        specs = {
            "crowd": [("giant_rat", "Giant Rat", 2, 1, 6, 10, 3), ("giant_rat", "Giant Rat", 2, 1, 10, 10, 3),
                      ("giant_rat", "Giant Rat", 3, 1, 10, 10, 3), ("giant_rat", "Giant Rat", 2, 2, 4, 10, 3),
                      ("wolf", "Grey Wolf", -2, 1, 20, 34, 18), ("wolf", "Grey Wolf", -3, 1, 34, 34, 18),
                      ("adamant_duelist", "Adamant Duelist", 0, -2, 27, 191, 40)],
        }[scene]
        g.monsters = {}
        for i, (mt, nm, dx, dy, hp, mx, lv) in enumerate(specs):
            mid = f"proof{i}"
            g.monsters[mid] = {"id": mid, "type": mt, "name": nm, "x": px + dx, "y": py + dy, "hp": hp,
                               "max_hp": mx, "alive": True, "level": lv, "attacking": 0}
        g.combat_target_id = os.environ.get("HUD_PROOF_TARGET", "proof6")
    if os.environ.get("HUD_PROOF_NP_MODE"):
        g.np_mode_override = os.environ["HUD_PROOF_NP_MODE"]
    for _ in range(int(os.environ.get("HUD_PROOF_DRAWS", "3"))):
        g.draw(); time.sleep(0.02)
    pygame.image.save(g.screen, out)
    print("saved", out, g.state, flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); os._exit(1)
