"""Write manifest.json and build fairy_village_pack.zip (Python zipfile)."""
import os, json, zipfile, hashlib, time
F = "/workspace/fairy_village"
INCLUDE = ["assets", "json", "dialogue", "previews", "src", "NOTES.md", "FAIRY_VILLAGE_CURSOR_PROMPT.md", "manifest.json"]
def files():
    for inc in INCLUDE:
        p = f"{F}/{inc}"
        if os.path.isfile(p):
            yield inc
        elif os.path.isdir(p):
            for r, ds, fs in os.walk(p):
                ds[:] = [d for d in ds if d not in ("__pycache__", "basemesh")]
                for f in sorted(fs):
                    yield os.path.relpath(os.path.join(r, f), F)
groups = {}
for rel in files():
    if rel == "manifest.json":
        continue
    top = "/".join(rel.split("/")[:3]) if rel.startswith("assets/") else rel.split("/")[0]
    g = groups.setdefault(top, {"files": 0, "bytes": 0}); g["files"] += 1; g["bytes"] += os.path.getsize(f"{F}/{rel}")
man = {
    "pack": "Mythoscape Fairy Village (Moonpetal Glade)",
    "built": time.strftime("%Y-%m-%d %H:%M %Z"),
    "target_branch": "castle-interiors-v2 (work on a new local branch 'fairy-village')",
    "art_install_dir": "game/assets/mmorpg/assets/fairy_village/",
    "copy_map": {"assets/*": "game/assets/mmorpg/assets/fairy_village/", "json/*": "game/assets/mmorpg/assets/fairy_village/data/",
                 "dialogue/*": "game/assets/mmorpg/assets/fairy_village/dialogue/"},
    "tile_px": {"1x": 40, "2x": 80, "4x": 160},
    "feature_flag": None,
    "npc_name": "Lady Elowen Moonwhisper",
    "quest": {"id": "fairy_oath", "objectives": ["combat_100", "buy_castle", "all_quests", "clan_25"]},
    "start_here": ["FAIRY_VILLAGE_CURSOR_PROMPT.md", "NOTES.md", "previews/contact_sheet.png", "previews/village_layout.png"],
    "contents": groups,
}
json.dump(man, open(f"{F}/manifest.json", "w"), indent=1)
out = f"{F}/fairy_village_pack.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for rel in files():
        z.write(f"{F}/{rel}", f"fairy_village/{rel}")
with zipfile.ZipFile(out) as z:
    bad = z.testzip(); n = len(z.namelist())
print("zip", out, round(os.path.getsize(out) / 1e6, 1), "MB", n, "files", "testzip:", bad)
