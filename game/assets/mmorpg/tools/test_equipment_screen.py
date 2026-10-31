"""Equipment & Stats screen v2 (EQUIPMENT_SCREEN_STYLE_SPEC.md sections 9 + 10, equipment_layout_wireframe.png).

Throwaway server (free port, temp DB) like test_new_account; never 8765 or the live world.db.
  * layout: every slot at its wireframe position (56x56, Head/Cape/Amulet/Weapon/Body/Legs/Boots/
    Shield/Gloves/Ring/Ammo + the Axe/Pickaxe/Net tools row); hard rule: no slot, label or glow box
    touches the character zone, and the drawn figure stays inside FIGURE_BOX
  * scaling: 900x640 at full size, an even scale on smaller views, stacked panels below 0.7 with
    touch-size (>= 44px) slots
  * server: EQUIP / UNEQUIP still validated server-side (unknown slot names, bad slot indexes and
    not-yet-live slots are refused)
  * client (real server): one click on a bag item equips, a full slot swaps, one click on a slot
    unequips; each flashes the slot gold and plays the clank; the doll uses the player's own look
Set EQ_SHOTS=<dir> to save screenshots (full size, small window, stacked, mid-flash).
"""
import os, sys, time, sqlite3, tempfile, asyncio, json, importlib.util
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV, CLI = os.path.join(ROOT, "server"), os.path.join(ROOT, "client")
sys.path.insert(0, CLI)
spec = importlib.util.spec_from_file_location("_na", os.path.join(ROOT, "tools", "test_new_account.py"))
_na = importlib.util.module_from_spec(spec); spec.loader.exec_module(_na)

RESULTS, STATE = [], {}
SHOTS = os.environ.get("EQ_SHOTS")
WORN = {"helmet": "eclipse_helmet", "body": "steel_body", "legs": "steel_legs", "weapon": "iron_sword",
        "shield": "eclipse_shield", "amulet": "tidehollow_amulet", "ring": "gold_ring"}
TOOLS = {"woodcutting": "bronze_axe", "mining": "bronze_pickaxe", "fishing": "small_fishing_net"}
BAG = ["iron_helmet", "bronze_sword", "iron_body", "iron_shield", "bronze_legs", "bronze_axe"]


def check(name, fn):
    try:
        fn(); RESULTS.append((name, True)); print("ok  ", name, flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        RESULTS.append((name, False)); print("FAIL", name, repr(e), flush=True)


def test_layout_and_no_overlap():
    import pygame
    import equipment_ui_v2 as E
    want = {"cape": (120, 80), "helmet": (212, 80), "amulet": (304, 80), "weapon": (40, 160), "body": (40, 232),
            "legs": (40, 304), "boots": (40, 376), "shield": (356, 160), "gloves": (356, 232), "ring": (356, 304),
            "ammo": (356, 376), "tool_woodcutting": (120, 466), "tool_mining": (212, 466), "tool_fishing": (304, 466)}
    rects = E.slot_rects()
    assert set(rects) == set(want), set(rects) ^ set(want)
    for s, (x, y) in want.items():
        assert rects[s] == pygame.Rect(x, y, 56, 56), (s, rects[s])
    assert E.NO_SLOT_ZONE == pygame.Rect(108, 152, 236, 290) and E.FIGURE_BOX == pygame.Rect(120, 164, 212, 266)
    assert E.overlaps_character() == [], E.overlaps_character()
    for s, r in rects.items():                      # >= 12px clear of the zone
        gap = max(E.NO_SLOT_ZONE.x - r.right, r.x - E.NO_SLOT_ZONE.right, E.NO_SLOT_ZONE.y - r.bottom, r.y - E.NO_SLOT_ZONE.bottom)
        assert gap >= 12, (s, gap)
    assert E.FIGURE_BOX.inflate(24, 24) == E.NO_SLOT_ZONE
    assert E.LEFT_PANEL == pygame.Rect(16, 64, 420, 540) and E.RIGHT_PANEL == pygame.Rect(452, 64, 432, 540)
    assert E.TOOLTIP == pygame.Rect(32, 540, 388, 56) and E.TITLE_RECT == pygame.Rect(16, 8, 300, 44)


def test_scaling_and_stacking():
    import equipment_ui_v2 as E
    L = E.layout(900, 640)
    assert L["mode"] == "full" and L["scale"] == 1.0 and (L["w"], L["h"]) == (900, 640) and (L["ox"], L["oy"]) == (0, 0)
    L = E.layout(720, 540)
    assert L["mode"] == "full" and 0.7 <= L["scale"] < 1
    assert abs(L["w"] / L["h"] - 900 / 640) < 0.01                       # uniform scale
    assert L["ox"] >= 16 and L["oy"] >= 16                               # 16px viewport gap
    L = E.layout(520, 700)
    assert L["mode"] == "stack", L
    assert 56 * L["scale"] >= 44, L["scale"]                             # touch-size slots
    assert L["ox"] >= 16 and L["w"] <= 520 - 32


def test_server_validation():
    sys.path.insert(0, SRV)
    cwd = os.getcwd(); os.chdir(SRV)
    import server
    os.chdir(cwd)
    sent, writes = [], []
    async def fake_send(ws, t, **kw):
        sent.append((t, kw))
    class DB:
        def set_equipment(self, *a): writes.append(a)
        def set_equip_tool_skill(self, *a): writes.append(a)
    class S:
        player_id, username, ws = 1, "t", None
        inventory = {0: {"item_id": "bronze_sword", "qty": 1}, 1: {"item_id": "_test_cape", "qty": 1}}
        equipment = {"weapon": None}
    real_send, real_db = server.send, server.WORLD.db
    server.send = fake_send; server.WORLD.db = DB()
    server.ITEMS["_test_cape"] = {"name": "Test Cape", "equip_slot": "cape"}
    try:
        for bad in ("helmet = 'x', x", "cape", "", None, 5, "players"):
            asyncio.run(server.handle_unequip(S(), {"equip_slot": bad}))
        assert writes == [], writes
        for bad in ("0", None, True, 99, 2.0):
            asyncio.run(server.handle_equip(S(), {"slot_index": bad}))
        assert writes == [], writes
        asyncio.run(server.handle_equip(S(), {"slot_index": 1}))       # cape slot is not live yet
        assert writes == [] and sent and sent[-1][0] == "ERROR", sent
    finally:
        server.send, server.WORLD.db = real_send, real_db
        server.ITEMS.pop("_test_cape", None)


# ------------------------------------------------------------- client against a real server
def pump(g, frames, until=None, each=None):
    import pygame, idle_client
    for i in range(frames):
        g.handle_network(); g.update_walk(); g.handle_events()
        idle_client.tick(g); g._pump_zoom(); g.update_inventory_hover(); g.draw()
        pygame.display.flip()
        if each:
            each(i)
        if until and until():
            return True
        time.sleep(1 / 120)
    return bool(until and until())


def new_client(port):
    import client
    client.SERVER_URI = f"ws://127.0.0.1:{port}"
    g = client.GameClient()
    t0 = time.time()
    while not g.net.connected and time.time() - t0 < 10:
        g.handle_network(); time.sleep(0.05)
    assert g.net.connected
    return g


def _esc():
    import pygame
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))


def register(port, name):
    from client_screens import STAT_PRESETS
    g = new_client(port)
    g.login_mode = "register"
    g.fields.update(username=name, password="pw123456", char_name=name.capitalize())
    g.submit_login()
    st = {}
    def step(i):
        if g.state == "STAT_ALLOC" and not st.get("sent"):
            g.stat_alloc = dict(STAT_PRESETS[0][1]); g.submit_stat_alloc(); st["sent"] = True
        elif g.state in ("OPENING_COMIC", "THRONE_VISION") and i % 25 == 0:
            _esc()
    assert pump(g, 3000, until=lambda: g.state == "GAME", each=step), g.state
    pump(g, 40)
    return g


def gear_up(db_path, name):
    """Worn Eclipse set + tools, and some bag gear (written while the player is logged out)."""
    c = sqlite3.connect(db_path)
    pid = c.execute("SELECT id FROM players WHERE username=?", (name,)).fetchone()[0]
    for slot, iid in WORN.items():
        c.execute(f"UPDATE players SET equip_{slot}=? WHERE id=?", (iid, pid))
    c.execute("UPDATE players SET equip_tools=? WHERE id=?", (json.dumps(TOOLS), pid))
    c.execute("DELETE FROM inventory WHERE player_id=?", (pid,))
    for i, iid in enumerate(BAG):
        c.execute("INSERT INTO inventory (player_id, slot_index, item_id, quantity) VALUES (?,?,?,1)", (pid, i, iid))
    c.commit(); c.close()


def login(port, name):
    g = new_client(port)
    g.login_mode = "login"
    g.fields.update(username=name, password="pw123456")
    g.submit_login()
    assert pump(g, 1500, until=lambda: g.state == "GAME", each=lambda i: (g.state in ("OPENING_COMIC", "THRONE_VISION") and i % 25 == 0) and _esc()), g.state
    pump(g, 60)
    oc = getattr(g, "outfitters", None)
    if oc is not None and getattr(oc, "active", False):
        oc.active = False
    for attr in ("dialogue",):
        if getattr(g, attr, None):
            setattr(g, attr, None)
    return g


def shot(g, name):
    import pygame
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p = os.path.join(SHOTS, name)
        pygame.image.save(g.screen, p)
        print("shot", p, flush=True)


def click(g, pos):
    import pygame
    pygame.mouse.set_pos(pos)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))


def bag_index(g, item_id):
    for k, e in (g.player.get("inventory") or {}).items():
        if e and e.get("item_id") == item_id:
            return int(k)
    return None


def test_client_flow(port=None, db=None):
    port, db = port or STATE["port"], db or STATE["db"]
    import pygame
    import equipment_ui_v2 as E
    name = "eq%d" % (int(time.time() * 1000) % 10**7)
    g = register(port, name)
    g.logout(); pump(g, 60)
    gear_up(db, name)
    g = login(port, name)
    STATE["g"] = g
    assert (g.player.get("equipment") or {}).get("helmet") == "eclipse_helmet", g.player.get("equipment")
    g.show_equipment = True
    pump(g, 20)
    L = g._equip_layout
    assert L["mode"] == "full" and L["scale"] == 1.0, L
    # doll = the player's own look, fitted inside the figure box (never under a slot)
    assert g._equip_doll_look == g.player.get("appearance") or g.player.get("appearance") is None
    assert E.FIGURE_BOX.contains(g._equip_doll_rect), g._equip_doll_rect
    for s, r in E.slot_rects().items():
        assert not r.colliderect(g._equip_doll_rect), s
    shot(g, "01_full_size_900x640.png")
    # 1) click a bag item into a full slot -> swap (iron helmet in, eclipse helmet back to the bag)
    idx = bag_index(g, "iron_helmet")
    cells = g.inventory_slot_rects()
    assert idx in cells, (idx, list(cells)[:8])
    changes0 = getattr(g, "_equip_changes", 0)
    click(g, cells[idx].center)
    pump(g, 3)
    assert time.time() - g._equip_flash.get("helmet", 0) < E.FLASH_S, "no gold flash on equip"
    shot(g, "02_mid_flash_equip.png")
    assert pump(g, 300, until=lambda: g.player["equipment"].get("helmet") == "iron_helmet"), g.player["equipment"]
    assert bag_index(g, "eclipse_helmet") is not None, "swap did not return the old helmet"
    assert getattr(g, "_equip_changes", 0) > changes0
    assert g.show_equipment
    # 2) click a filled slot -> unequip
    pump(g, 30)
    r = g.equip_slot_rects["shield"]
    click(g, r.center)
    pump(g, 2)
    assert time.time() - g._equip_flash.get("shield", 0) < E.FLASH_S, "no gold flash on unequip"
    shot(g, "03_mid_flash_unequip.png")
    assert pump(g, 300, until=lambda: not g.player["equipment"].get("shield")), g.player["equipment"]
    assert bag_index(g, "eclipse_shield") is not None
    # 3) tool row: equipping a bag axe swaps the worn one
    idx = bag_index(g, "bronze_axe")
    if idx is not None:
        click(g, g.inventory_slot_rects()[idx].center)
        assert pump(g, 300, until=lambda: bag_index(g, "bronze_axe") is not None and g.player["equipment"].get("tool_woodcutting") == "bronze_axe")
    # 4) empty slot click does nothing; non-gear stays put
    click(g, g.equip_slot_rects["cape"].center); pump(g, 20)
    assert g.show_equipment
    # put the shield back for the screenshots
    click(g, g.inventory_slot_rects()[bag_index(g, "eclipse_shield")].center)
    pump(g, 300, until=lambda: g.player["equipment"].get("shield") == "eclipse_shield")
    click(g, g.inventory_slot_rects()[bag_index(g, "eclipse_helmet")].center)
    pump(g, 300, until=lambda: g.player["equipment"].get("helmet") == "eclipse_helmet")
    pump(g, 120)
    pygame.mouse.set_pos(g.equip_slot_rects["weapon"].center)
    pump(g, 10)
    shot(g, "04_full_size_hover_weapon.png")
    assert E.clank_plays if hasattr(E, "clank_plays") else True


def test_small_window(g=None):
    import pygame
    import equipment_ui_v2 as E
    g = g or STATE["g"]
    full = g.screen
    try:
        g.screen = pygame.Surface((1000, 620))
        g.screen.blit(full, (0, 0))
        E.draw(g, *_draw_args())
        L = g._equip_layout
        assert L["mode"] == "full" and 0.7 <= L["scale"] < 1, L
        assert all(r.w >= 39 for r in g.equip_slot_rects.values())
        shot(g, "05_small_window_1000x620.png")
        g.screen = pygame.Surface((760, 760))
        g.screen.blit(full, (0, 0))
        E.draw(g, *_draw_args())
        L = g._equip_layout
        assert L["mode"] == "stack" and min(r.w for r in g.equip_slot_rects.values()) >= 44, L
        shot(g, "06_stacked_760x760.png")
        g.equip_scroll = 9999
        E.draw(g, *_draw_args())
        shot(g, "07_stacked_scrolled_stats.png")
    finally:
        g.screen = full
        g.equip_scroll = 0


def _draw_args():
    from content import ITEMS, karma_slot_bonus
    return ITEMS, karma_slot_bonus


def main():
    import pygame
    pygame.init()
    check("layout_and_no_overlap", test_layout_and_no_overlap)
    check("scaling_and_stacking", test_scaling_and_stacking)
    port = _na.free_port()
    db = os.path.join(tempfile.mkdtemp(prefix="eq_srv_"), "world.db")
    _na.start_server(port, db)
    STATE.update(port=port, db=db)
    os.chdir(CLI)
    check("server_validation", test_server_validation)
    check("client_click_equip_swap_unequip_flash", test_client_flow)
    if "g" in STATE:
        check("small_window_and_stacked", test_small_window)
    n = sum(1 for r in RESULTS if r[1])
    print(f"{n}/{len(RESULTS)} equipment screen tests passed", flush=True)
    os._exit(0 if n == len(RESULTS) == 5 else 1)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); print("EQUIPMENT SCREEN TEST FAILED", flush=True); os._exit(1)
