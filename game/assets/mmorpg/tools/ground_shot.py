"""Headless ground shots, overworld or King's Realm (VREALM=1) (box-only tool, copy of village_shot).
usage: python3 tools/village_shot.py OUT.png X Y [zoom_pct] [W H]   (several triples via VSHOTS env: "out,x,y,zoom;...")"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import world_map as wm, content
grid = wm.generate_world(); grid = grid[0] if isinstance(grid, tuple) else grid
os.chdir(os.path.join(ROOT, "client")); sys.path.insert(0, os.getcwd()); sys.argv = ["client.py"]
import pygame, client as C
C.GameClient._connect_stub = True
g = C.GameClient()
g.player = {"id": 1, "name": "Scan", "char_name": "Scan", "x": 28, "y": 24, "hp": 10, "max_hp": 10, "level": 1,
            "skills": {}, "inventory": [], "equipment": {}, "appearance": {}}
g.players = {}
g.process_message({"type": "WORLD_STATE", "width": len(grid[0]), "height": len(grid), "tiles": [r[:] for r in grid],
                   "npcs": [], "resources": {}, "interactables": [dict(s) for s in getattr(content, "INTERACTABLES", [])], "craft_recipes": {},
                   "buildings": list(getattr(content, "BUILDINGS", []))})
g.state = "GAME"; g.needs_appearance = False
if os.environ.get("VREALM"):
    import castle_realm as CR
    pl = CR.build_plane("realm")
    from content import NPCS
    g.process_message({"type": "DUNGEON_ENTER", "id": "castle_realm", "plane": "realm", "label": "King's Realm",
                       "name": "King's Realm", "tiles": [r[:] for r in pl["tiles"]], "width": pl["width"], "height": pl["height"],
                       "monsters": [], "npcs": [n for n in NPCS if n.get("plane") == "realm"], "player_x": 150, "player_y": 182,
                       "floor": 0, "floors": 1, "realm": True})
if os.environ.get("VPHASE"):
    g.env = dict(getattr(g, "env", None) or {}, phase=os.environ["VPHASE"])
jobs = os.environ.get("VSHOTS") or ",".join(sys.argv_orig[1:5]) if False else os.environ.get("VSHOTS", "")
for job in [j for j in jobs.split(";") if j]:
    out, x, y, z = job.split(",")
    if int(z) == 0:
        g._set_area_view(True); g._pump_zoom()
    else:
        if getattr(g, "_area_view", False):
            g._set_area_view(False)
        g.set_zoom_pct(int(z)); g._pump_zoom()
    g.player["x"], g.player["y"] = int(x), int(y)
    for _ in range(2):
        g.draw()
    if os.environ.get("VDEBUG"):   # tile-coordinate grid for locating art problems
        cx, cy = g.camera_origin(); T = C.TILE; f = pygame.font.SysFont("arial", 11, bold=True)
        for ty in range(int(cy), int(cy) + 40):
            for tx in range(int(cx), int(cx) + 60):
                if tx % 3 == 0 and ty % 2 == 0:
                    ox, oy = g.world_to_view_offset(tx, ty, cx, cy)
                    g.screen.blit(f.render("%d,%d" % (tx, ty), True, (255, 0, 0)), (ox * T, oy * T))
    pygame.image.save(g.screen, out); print("saved", out, g.screen.get_size())
