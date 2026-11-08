"""King's Castle siege view inside the real game client.

Active only after the server admits the player to ``kings_castle_siege``.
The picture is the approved angled renderer. This module does not copy its
collision rules and does not invent engine firing, gate damage, or ownership.

Runtime art is a symlink from ``KCS_VISUAL_FIXTURES`` (default
``/tmp/kcs_visual_fixtures``) onto ``server/kcs_parity/assets``. Those files
stay outside git. If they or OpenCV are missing, the map shows an error
instead of crashing the client.

Keys, only while this view is up: F6 build, 1–4 ram / trebuchet / tower /
ladder, F7 rotate, click to place, Esc cancels build. F8 from the overworld
asks the server to deploy. The server can refuse.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pygame

DUNGEON_ID = "kings_castle_siege"
HUD_TOP = 58
HUD_BOT = 56
ENGINE_KEYS = {
    pygame.K_1: "ram",
    pygame.K_2: "trebuchet",
    pygame.K_3: "siege_tower",
    pygame.K_4: "ladder",
}
ENGINE_LABELS = (
    ("1", "ram"),
    ("2", "trebuchet"),
    ("3", "siege tower"),
    ("4", "ladder"),
)


class SiegeView:
    def __init__(self):
        self.openings = []
        self.engines = []
        self.war_id = None
        self.build = False
        self.engine_type = "ram"
        self.rotation = 0
        self.request_n = 0
        self.notice = "Engines do not fire. Combat and ownership are not in this build."
        self.error = ""
        self.origin = None
        self.screen_o = None
        self.scale = 28.0
        self.bf = None
        self.bf_key = None
        self.last_ms = None


def active(client) -> bool:
    data = getattr(client, "dungeon", None) or {}
    return data.get("id") == DUNGEON_ID


def view_of(client) -> SiegeView:
    view = getattr(client, "kcs_view", None)
    if view is None:
        view = SiegeView()
        client.kcs_view = view
    return view


def on_enter(client) -> None:
    view = view_of(client)
    view.notice = "Deployed. F6 places an engine. Engines do not fire."
    view.error = ""


def on_exit(client) -> None:
    client.kcs_view = None


def on_message(client, kind, msg) -> None:
    if not active(client):
        return
    view = view_of(client)
    if kind == "KCS_SNAPSHOT":
        view.war_id = msg.get("war_id")
        view.openings = [dict(row) for row in (msg.get("openings") or []) if isinstance(row, dict)]
        view.engines = [dict(row) for row in (msg.get("engines") or []) if isinstance(row, dict)]
        view.bf_key = None
        view.notice = "Siege state is the server's snapshot. Engines do not fire."
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "engine" and isinstance(msg.get("engine"), dict):
        _upsert_engine(view, msg["engine"])
        view.notice = "An engine was placed. It does not fire."
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "opening":
        _upsert_opening(view, msg)
        view.bf_key = None
        view.notice = "The server changed a gate. The client cannot."
        return
    if kind == "KCS_PLACE_OK" and isinstance(msg.get("engine"), dict):
        _upsert_engine(view, msg["engine"])
        view.notice = "The server accepted that engine. It does not fire."
        try:
            client.add_chat("Siege engine placed. It does not fire.", color=(180, 220, 170))
        except Exception:
            pass


def on_keydown(client, event) -> bool:
    """Consume a key when it belongs to the siege. Otherwise leave it alone."""
    if not active(client):
        if event.key == pygame.K_F8 and not getattr(client, "dungeon", None) and getattr(client, "state", "") == "GAME":
            try:
                client.net.send("ENTER_DUNGEON", dungeon_id=DUNGEON_ID)
                client.add_chat("Asking to deploy to King's Castle…", color=(210, 190, 140))
            except Exception:
                pass
            return True
        return False
    view = view_of(client)
    if event.key == pygame.K_F6:
        view.build = not view.build
        view.notice = "Build mode on. Click the field." if view.build else "Build mode off."
        return True
    if event.key == pygame.K_ESCAPE and view.build:
        view.build = False
        view.notice = "Build cancelled."
        return True
    if event.key == pygame.K_F7 and view.build:
        view.rotation = (int(view.rotation) + 90) % 360
        view.notice = f"Rotation {view.rotation}."
        return True
    if view.build and event.key in ENGINE_KEYS:
        view.engine_type = ENGINE_KEYS[event.key]
        view.notice = f"Selected {view.engine_type}."
        return True
    return False


def on_mouse(client, pos) -> bool:
    if not active(client):
        return False
    view = view_of(client)
    if not view.build or view.origin is None or view.screen_o is None:
        return False
    x, y = int(pos[0]), int(pos[1])
    import client as game
    if x < 0 or y < HUD_TOP or x >= game.MAP_W or y >= game.MAP_H - HUD_BOT:
        return False
    from kings_castle_siege_map.angled_proj import pick_tile
    tx, ty = pick_tile(x, y - HUD_TOP, view.origin, view.scale, view.screen_o)
    view.request_n += 1
    pid = int((getattr(client, "player", None) or {}).get("id") or 0)
    request_id = f"kcs-{pid}-{view.request_n}-{int(time.time() * 1000)}"
    try:
        client.net.send(
            "KCS_PLACE",
            engine_type=view.engine_type,
            x=int(tx),
            y=int(ty),
            rotation=int(view.rotation),
            request_id=request_id[:64],
        )
        client.add_chat(
            f"Asking to place a {view.engine_type} at {int(tx)}, {int(ty)}.",
            color=(210, 190, 140),
        )
    except Exception:
        view.error = "Could not send the placement."
    return True


def tile_to_screen(client, tx, ty):
    """Map a tile into the window, matching the last draw. None before the first draw."""
    view = view_of(client)
    if view.origin is None or view.screen_o is None:
        return None
    from kings_castle_siege_map.angled_proj import project
    sx, sy, _depth = project(tx + 0.5, ty + 0.5, 0.0, view.origin, view.scale, view.screen_o)
    return int(sx), int(sy + HUD_TOP)


def draw(client) -> None:
    import client as game
    size = (game.MAP_W, game.MAP_H)
    view = view_of(client)
    try:
        surf = _render(client, view, size)
    except Exception as exc:
        surf = pygame.Surface(size)
        surf.fill((24, 18, 16))
        font = pygame.font.Font(None, 24)
        surf.blit(font.render("King's Castle view unavailable.", True, (240, 210, 170)), (16, 28))
        detail = font.render(str(exc)[:110], True, (210, 170, 140))
        surf.blit(detail, (16, 58))
        view.error = str(exc)
    _chrome(surf, view)
    client.screen.blit(surf, (0, 0))


def ensure_assets():
    """Point the renderer's asset folder at the external fixture tree.

    Does not copy historical plates into the repo. Returns the linked
    directory, or None when the fixture is not on this machine.
    """
    parity = Path(__file__).resolve().parents[1] / "server" / "kcs_parity"
    dest = parity / "assets"
    src = Path(os.environ.get("KCS_VISUAL_FIXTURES", "/tmp/kcs_visual_fixtures")) / "assets"
    if dest.is_symlink() or dest.exists():
        return dest
    if not (src / "baked_m9" / "gatehouse.png").is_file():
        return None
    dest.symlink_to(src, target_is_directory=True)
    return dest


def _upsert_engine(view, engine) -> None:
    eid = engine.get("engine_id")
    view.engines = [row for row in view.engines if row.get("engine_id") != eid]
    view.engines.append(dict(engine))


def _upsert_opening(view, msg) -> None:
    oid = msg.get("opening_id") or msg.get("id")
    found = False
    for row in view.openings:
        if row.get("id") == oid or row.get("opening_id") == oid:
            row["state"] = msg.get("state", row.get("state"))
            if msg.get("rev") is not None:
                row["rev"] = msg.get("rev")
            found = True
    if not found and oid:
        view.openings.append({
            "id": oid,
            "plane": msg.get("plane") or "",
            "state": msg.get("state") or "intact",
            "rev": msg.get("rev") or 0,
        })


def _parity_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "server" / "kcs_parity")


def _load_renderer():
    linked = ensure_assets()
    root = _parity_path()
    if root not in sys.path:
        sys.path.insert(0, root)
    from kings_castle_siege_map.angled_view import camera_look, render_world
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import PlacedEngine
    return linked, camera_look, render_world, build_battlefield, PlacedEngine


def _player_tile(client):
    player = getattr(client, "player", None) or {}
    try:
        x, y = client.player_xy()
        return int(x), int(y)
    except Exception:
        return int(player.get("x") or 0), int(player.get("y") or 0)


def _facing(client) -> str:
    player = getattr(client, "player", None) or {}
    raw = (getattr(client, "_entity_facing", {}) or {}).get(("p", player.get("id")), "front")
    if raw == "back":
        return "n"
    if raw in (1, "e"):
        return "e"
    if raw in (-1, "w"):
        return "w"
    return "s"


def _gate_states(view):
    states = {}
    for row in view.openings:
        plane = str(row.get("plane") or "")
        if plane and not plane.endswith("battlefield"):
            continue
        oid = row.get("id") or row.get("opening_id")
        if oid:
            states[str(oid)] = str(row.get("state") or "intact")
    return states


def _render(client, view, size):
    linked, camera_look, render_world, build_battlefield, PlacedEngine = _load_renderer()
    if linked is None:
        raise RuntimeError("Set KCS_VISUAL_FIXTURES to the extracted siege art.")
    states = _gate_states(view)
    key = tuple(sorted(states.items()))
    if view.bf is None or view.bf_key != key:
        view.bf = build_battlefield(states or None)
        view.bf_key = key
    placed = []
    for row in view.engines:
        try:
            placed.append(PlacedEngine(
                str(row.get("engine_id")),
                str(row.get("engine_type")),
                int(row.get("x")),
                int(row.get("y")),
                int(row.get("rotation") or 0),
            ))
        except Exception:
            continue
    px, py = _player_tile(client)
    scale = 28.0
    world_size = (size[0], size[1] - HUD_TOP - HUD_BOT)
    origin, screen_o = camera_look((px, py), world_size, scale)
    view.origin = origin
    view.screen_o = screen_o
    view.scale = scale
    started = time.perf_counter()
    surf = render_world(
        view.bf,
        (px, py),
        placed,
        "King's Castle",
        "",
        size=size,
        tile_px=scale,
        facing=_facing(client),
        gate_states=states or None,
        markers=False,
    )
    view.last_ms = (time.perf_counter() - started) * 1000.0
    return surf


def _chrome(surf, view) -> None:
    """Cover the renderer's own dummy caption. The game HUD owns the top of the map."""
    width, height = surf.get_size()
    small = pygame.font.Font(None, 18)
    pygame.draw.rect(surf, (18, 16, 14), (0, 0, width, HUD_TOP))
    pygame.draw.rect(surf, (18, 16, 14), (0, height - HUD_BOT, width, HUD_BOT))
    note = view.error or view.notice
    surf.blit(small.render(note[:110], True, (220, 186, 140)), (12, height - HUD_BOT + 8))
    mode = "BUILD" if view.build else "move"
    surf.blit(small.render(
        f"Unfinished: engines do not fire, no gate HP, no ownership. {mode}, F6 build, F7 rotate, F8 deploy.",
        True, (168, 150, 130)), (12, height - 26))
