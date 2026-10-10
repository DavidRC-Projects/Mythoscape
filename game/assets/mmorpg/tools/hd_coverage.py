#!/usr/bin/env python3
"""Read-only HD coverage audit. Does not start the game.

Run from anywhere:

    python game/assets/mmorpg/tools/hd_coverage.py

Prints one row per NPC and monster, plus the non-character HD packs.
Exit 1 when MISSING is greater than 0.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ASSETS = ROOT / "game" / "assets"
MMORPG = ASSETS / "mmorpg"
CLIENT = MMORPG / "client"

# Stay as they are. No HD folder, so they are excluded rather than missing.
NAMED_EXCLUDED = {
    "goblin",
    "skeleton",
    "spider",
    "dragon",
    "shade",
    "crypt_ghoul",
    "void_imp",
    "obsidian_colossus",
    "void_horror",
    "gallery_warden",
    "void_crawler",
    "rift_wraith",
    "nyxarath",
    "ossuary_keeper",
    "drowned_dead",
    "morvath",
    "magma_slug",
    "ash_imp",
    "ember_wolf",
    "crucible_beast",
}


def _assign_value(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise SystemExit(f"{path} has no {name}")


def _string_set(path: Path, name: str) -> set[str]:
    value = _assign_value(path, name)
    if isinstance(value, dict):
        return set(value)
    return set(value)


def _drawer_keys(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MONSTER_DRAWERS":
                    if isinstance(node.value, ast.Dict):
                        keys.update(_dict_keys(node.value))
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "MONSTER_DRAWERS"
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                ):
                    keys.add(target.slice.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                node.func.attr == "update"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "MONSTER_DRAWERS"
                and node.args
                and isinstance(node.args[0], ast.Dict)
            ):
                keys.update(_dict_keys(node.args[0]))
    return keys


def _dict_keys(node: ast.Dict) -> set[str]:
    found = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found.add(key.value)
    return found


def _folder_for(entity_id: str) -> str:
    candidates = [
        ASSETS / "npc_hd" / "assets" / "npcs" / entity_id,
        ASSETS / "fairy_village" / "assets" / "npcs" / entity_id,
        ASSETS / "knights_hd" / "assets" / entity_id,
        ASSETS / "monsters_hd" / entity_id,
    ]
    if entity_id == "emberdeep_wyrm":
        candidates.append(ASSETS / "emberdeep_hd" / "dragon")
    for folder in candidates:
        if folder.is_dir() and (any(folder.glob("meta.json")) or any(folder.glob("sprite_*")) or any(folder.glob("*.png"))):
            try:
                return str(folder.relative_to(ROOT))
            except ValueError:
                return str(folder)
    return ""


def _source_has(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8")


def _pack_rows() -> list[tuple]:
    checks = [
        (
            "player_hd",
            "pack",
            ASSETS / "player_hd",
            (CLIENT / "player_hd_client.py").is_file()
            and _source_has(CLIENT / "client.py", "TOGGLE_HD_PLAYER"),
        ),
        (
            "emberdeep_hd/textures",
            "pack",
            ASSETS / "emberdeep_hd" / "textures",
            _source_has(CLIENT / "emberdeep_v2_client.py", "emberdeep_hd"),
        ),
        (
            "emberdeep_hd/dragon",
            "pack",
            ASSETS / "emberdeep_hd" / "dragon",
            _source_has(CLIENT / "emberdeep_creatures_client.py", "emberdeep_hd")
            and _source_has(CLIENT / "emberdeep_creatures_client.py", "def draw_wyrm"),
        ),
        (
            "fairy_village",
            "pack",
            ASSETS / "mmorpg" / "assets" / "fairy_village",
            _source_has(CLIENT / "fairy_village_client.py", '"tiles"')
            and _source_has(CLIENT / "fairy_village_client.py", '"buildings"')
            and _source_has(CLIENT / "fairy_village_client.py", '"fountains"'),
        ),
    ]
    rows = []
    for name, kind, folder, wired in checks:
        rel = ""
        if folder.is_dir():
            rel = str(folder.relative_to(ROOT))
        drawn = "yes" if folder.is_dir() and wired else "no"
        rows.append((name, kind, rel or "-", drawn, "no", drawn != "yes"))
    return rows


def _complete_meta_ids() -> dict[str, str]:
    """Ids whose meta.json says complete: true, mapped to their folder."""
    found = {}
    roots = [
        ASSETS / "npc_hd" / "assets" / "npcs",
        ASSETS / "fairy_village" / "assets" / "npcs",
        ASSETS / "knights_hd" / "assets",
        ASSETS / "monsters_hd",
        ASSETS / "emberdeep_hd" / "dragon",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        metas = [root / "meta.json"] if (root / "meta.json").is_file() else root.glob("*/meta.json")
        for meta in metas:
            text = meta.read_text(encoding="utf-8")
            if '"complete"' not in text:
                continue
            try:
                data = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                import json
                data = json.loads(text)
            if not data.get("complete"):
                continue
            entity_id = str(data.get("id") or meta.parent.name)
            if entity_id == "dragon":
                entity_id = "emberdeep_wyrm"
            found[entity_id] = str(meta.parent.relative_to(ROOT))
    return found


def main() -> int:
    sys.path.insert(0, str(MMORPG / "server"))
    import content  # noqa: E402

    overworld = _string_set(CLIENT / "npc_hd_client.py", "OVERWORLD_HD")
    fairy = _string_set(CLIENT / "fairy_village_client.py", "FAIRY_NPCS")
    knights = _string_set(CLIENT / "knights_hd_client.py", "KNIGHTS_HD")
    monsters_hd = _string_set(CLIENT / "knights_hd_client.py", "MONSTERS_HD")
    handled = knights | monsters_hd
    legacy = _string_set(CLIENT / "legacy_creature_sprites.py", "_MONSTER_PREVIEW")
    strips = _string_set(CLIENT / "anim_strip_sprites.py", "TYPE_MAP")
    drawers = _drawer_keys(ASSETS / "characters" / "procedural_sprites_finished.py")
    wyrm_drawn = _source_has(CLIENT / "emberdeep_creatures_client.py", "def draw_wyrm") and _source_has(
        CLIENT / "emberdeep_v2_client.py", "draw_wyrm"
    )

    rows = []
    seen = set()

    def add(entity_id: str, kind: str) -> None:
        if entity_id in seen:
            return
        seen.add(entity_id)
        folder = _folder_for(entity_id)
        if kind == "npc":
            drawn = entity_id in overworld or entity_id in fairy
        elif entity_id == "emberdeep_wyrm":
            drawn = wyrm_drawn
        else:
            drawn = entity_id in handled
        old = "yes" if entity_id in legacy or entity_id in strips or entity_id in drawers else "no"
        if not folder:
            status = "excluded"
            missing = False
        elif drawn:
            status = "yes"
            missing = False
        else:
            status = "no"
            missing = True
        rows.append((entity_id, kind, folder or "-", status, old, missing))

    for npc in content.NPCS:
        add(str(npc["id"]), "npc")
    for monster_id in content.MONSTERS:
        add(str(monster_id), "monster")
    add("emberdeep_wyrm", "monster")

    for entity_id, folder in _complete_meta_ids().items():
        if entity_id in seen:
            continue
        drawn = entity_id in overworld or entity_id in fairy or entity_id in handled or (
            entity_id == "emberdeep_wyrm" and wyrm_drawn
        )
        rows.append((entity_id, "meta", folder, "yes" if drawn else "no", "no", not drawn))
        seen.add(entity_id)

    rows.extend(_pack_rows())

    headers = ("id", "kind", "hd_folder", "drawn_hd", "old_2d_path_still_present")
    widths = [len(h) for h in headers]
    printable = []
    missing_n = 0
    for entity_id, kind, folder, status, old, missing in rows:
        if missing:
            missing_n += 1
        cells = (entity_id, kind, folder, status, old)
        printable.append(cells)
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))

    line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-+-".join("-" * w for w in widths))
    for cells in printable:
        print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)))
    print(f"MISSING: {missing_n}")
    return 1 if missing_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
