"""Dialogue-box proofs for NPC portraits. usage: portrait_proofs.py out.png npc_id[,npc_id..] [alt_npc_dir]"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__)); CLI = os.path.normpath(os.path.join(HERE, "..", "client"))
sys.path.insert(0, CLI); os.chdir(CLI)
import client, pygame, npc_hd_client
if len(sys.argv) > 3:
    npc_hd_client._DIR = sys.argv[3]
g = client.GameClient()
ids = sys.argv[2].split(",")
shots = []
for nid in ids:
    g.screen.fill((40, 52, 38))
    g.dialogue = {"npc_id": nid, "npc_name": nid.replace("_", " ").title(), "text": "Well met, traveller. The pit opens at dawn.",
                  "pages": [], "options": []}
    g.draw_dialogue()
    box = g._dialogue_box()
    shots.append(g.screen.subsurface(box.inflate(8, 8)).copy())
W = max(s.get_width() for s in shots); H = sum(s.get_height() for s in shots)
out = pygame.Surface((W, H)); y = 0
for s in shots:
    out.blit(s, (0, y)); y += s.get_height()
pygame.image.save(out, sys.argv[1]); print("saved", sys.argv[1]); os._exit(0)
