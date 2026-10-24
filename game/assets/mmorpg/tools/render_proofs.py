"""Headless proof renders for the new-account / HD outfit fixes (throwaway server; live world.db untouched).
usage: python3 tools/render_proofs.py <female|male> <out_dir>
Saves stat.png (stat screen), creator.png, idle_XX.png crops, walk_XX.png crops and draws.json:
one row per self-player draw: requested anim, drawn strip, and which layer drew it (HD outfit vs layered)."""
import os, sys, json, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_new_account as T


def main():
    gender, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    import tempfile
    port = T.free_port(); T.start_server(port, os.path.join(tempfile.mkdtemp(prefix="proof_"), "world.db"))
    sys.path.insert(0, T.CLI); os.chdir(T.CLI)
    import client, pygame, idle_client, player_hd_client as phc
    client.SERVER_URI = f"ws://127.0.0.1:{port}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    name = "pf%d" % (int(time.time() * 1000) % 10**7)
    g.login_mode = "register"; g.fields.update(username=name, password="pw12345", char_name=name.capitalize())
    g.submit_login()
    rows, phase = [], {"name": "pre"}
    real = phc.draw_player

    def spy(surf, sex, appearance, cx, cy_feet, tile, t, anim="idle", *a, **k):
        r = real(surf, sex, appearance, cx, cy_feet, tile, t, anim, *a, **k)
        if surf is g.screen and phase["name"] in ("idle", "walk"):
            rows.append({"phase": phase["name"], "anim": anim, "drawn": phc.last_draw.get("strip"),
                         "frame": phc.last_draw.get("frame"), "layer": phc.last_draw.get("whole") or "LAYERED",
                         "outfit": (appearance or {}).get("outfit"), "pos": [int(cx), int(cy_feet)]})
        return r
    phc.draw_player = spy

    def frame():
        g.handle_network(); g.update_walk(); g.handle_events()
        idle_client.tick(g); g._pump_zoom(); g.update_inventory_hover(); g.draw()

    def crop(fn):
        r = [x for x in rows if x["pos"]][-1]["pos"] if rows else [600, 400]
        rect = pygame.Rect(r[0] - 90, r[1] - 200, 180, 230).clip(g.screen.get_rect())
        pygame.image.save(g.screen.subsurface(rect).copy(), os.path.join(out, fn))

    stat_shot = sent = creator_shot = False
    for i in range(1500):
        frame()
        if g.state == "STAT_ALLOC":
            if gender == "female" and g.stat_gender != "female":
                g.stat_gender = "female"
            if not stat_shot and getattr(g, "stat_preset_rects", None):
                rect, pts = g.stat_preset_rects[0]
                g.stat_alloc = dict(pts); frame(); frame()
                pygame.image.save(g.screen, os.path.join(out, "stat.png")); stat_shot = True
            elif stat_shot and not sent:
                g.submit_stat_alloc(); sent = True
        elif g.state == "OPENING_COMIC" and i % 15 == 0:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
        elif g.state == "GAME":
            if g.outfitters.active and not creator_shot:
                for _ in range(5): frame()
                pygame.image.save(g.screen, os.path.join(out, "creator.png")); creator_shot = True
                g.outfitters.close() if hasattr(g.outfitters, "close") else setattr(g.outfitters, "active", False)
            elif creator_shot or i > 900:
                break
        time.sleep(1 / 120)
    print("state", g.state, "stat", stat_shot, "creator", creator_shot, flush=True)
    print("payload outfit:", ((g.player or {}).get("appearance") or {}).get("outfit"), flush=True)
    phase["name"] = "idle"
    for i in range(240):            # 2 s standing
        frame()
        if i in (20, 120, 230): crop(f"idle_{i:03d}.png")
        time.sleep(1 / 120)
    phase["name"] = "walk"
    last = 0
    for i in range(480):            # ~4 s walking east/west in steps
        if time.time() - last > 0.4:
            g.net.send("MOVE", dx=1 if (i // 120) % 2 == 0 else -1, dy=0); last = time.time()
        frame()
        if i % 40 == 0: crop(f"walk_{i:03d}.png")
        time.sleep(1 / 120)
    phase["name"] = "after"
    json.dump(rows, open(os.path.join(out, "draws.json"), "w"))
    from collections import Counter
    for ph in ("idle", "walk"):
        sub = [r for r in rows if r["phase"] == ph]
        print(ph, len(sub), "draws; layers", dict(Counter(r["layer"] for r in sub)), "anims",
              dict(Counter(r["drawn"] for r in sub)), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stderr.flush(); os._exit(1)
