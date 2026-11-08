"""King's Castle siege controls inside the real game client.

The picture is still the approved angled renderer. Engine sprites are drawn
again, on top, with a nose that shows the quarter-turn facing, because that
renderer does not rotate an engine.

1–4 select an engine and turn build mode on. They do not wait for F6.
Click the named buttons for the same choices. F8 or the Deploy button asks
the server to enter. The server still accepts or refuses every action.
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
    pygame.K_KP1: "ram",
    pygame.K_KP2: "trebuchet",
    pygame.K_KP3: "siege_tower",
    pygame.K_KP4: "ladder",
}
ENGINE_ORDER = ("ram", "trebuchet", "siege_tower", "ladder")
DEFENDER_KEYS = {
    pygame.K_1: "ballista",
    pygame.K_2: "cauldron",
    pygame.K_KP1: "ballista",
    pygame.K_KP2: "cauldron",
}
DEFENDER_ORDER = ("ballista", "cauldron")
ENGINE_SHORT = {
    "ram": "Ram", "trebuchet": "Trebuchet", "siege_tower": "Tower", "ladder": "Ladder",
    "ballista": "Ballista", "cauldron": "Cauldron",
}
SPRITE_ALIAS = {"ballista": "trebuchet"}


class SiegeView:
    def __init__(self):
        self.openings = []
        self.engines = []
        self.war_id = None
        self.your_side = None
        self.lobby = {}
        self.status = {}
        self.prep_side = {}
        self.build = False
        self.engine_type = "ram"
        self.rotation = 0
        self.view_quarter = 0
        self.request_n = 0
        self.notice = "Enlist, begin, then deploy. 1–4 select an engine."
        self.error = ""
        self.preview = ""
        self.origin = None
        self.screen_o = None
        self.scale = 28.0
        self.bf = None
        self.bf_key = None
        self.last_ms = None
        self.buttons = []


def active(client) -> bool:
    data = getattr(client, "dungeon", None) or {}
    return data.get("id") == DUNGEON_ID


def view_of(client) -> SiegeView:
    view = getattr(client, "kcs_view", None)
    if view is None:
        view = SiegeView()
        client.kcs_view = view
    return view


def note(client, text, error=False) -> None:
    view = view_of(client)
    view.notice = str(text or "")
    if error:
        view.error = view.notice


def on_enter(client) -> None:
    view = view_of(client)
    if view.your_side == "defend":
        view.engine_type = "ballista"
        view.notice = "Deployed. 1 Ballista, 2 Cauldron. Stand on the wall-walk and face them outward."
    else:
        view.notice = "Deployed. 1 Ram, 2 Trebuchet, 3 Tower, 4 Ladder. Rotate until the nose points at the wall."
    view.error = ""


def on_exit(client) -> None:
    view = getattr(client, "kcs_view", None)
    if view is not None:
        view.buttons = []
        view.build = False
        view.view_quarter = 0
    client.camera_yaw = 0
    apply_view_quarter(0)


def _take_status(view, msg) -> None:
    panel = msg.get("status_panel") if isinstance(msg.get("status_panel"), dict) else msg
    if not isinstance(panel, dict) or "status" not in panel:
        return
    view.status = dict(panel)
    view.lobby = dict(panel)
    if panel.get("your_side"):
        view.your_side = panel.get("your_side")
    if panel.get("war_id"):
        view.war_id = panel.get("war_id")
    known = set()
    for row in panel.get("sandbox_players") or []:
        if isinstance(row, dict) and row.get("player_id") is not None:
            known.add(int(row["player_id"]))
    side = dict(view.prep_side)
    for pid in list(side):
        if pid not in known:
            side.pop(pid, None)
    for pid in known:
        side.setdefault(pid, None)
    view.prep_side = side
    if panel.get("result") and panel.get("status") in ("resolved", "resolving"):
        view.build = False


def on_message(client, kind, msg) -> None:
    view = view_of(client)
    if kind in ("KCS_LOBBY", "KCS_STATUS", "KCS_RESULT"):
        _take_status(view, msg)
        view.notice = msg.get("text") or view.notice
        view.error = ""
        if kind != "KCS_STATUS" or msg.get("result"):
            _say(client, view.notice, (220, 200, 140) if kind == "KCS_RESULT" else (210, 190, 140))
        return
    if not active(client):
        return
    if kind == "KCS_SNAPSHOT":
        _take_status(view, msg)
        view.war_id = msg.get("war_id") or view.war_id
        view.your_side = msg.get("your_side") or view.your_side
        view.openings = [dict(row) for row in (msg.get("openings") or []) if isinstance(row, dict)]
        view.engines = [dict(row) for row in (msg.get("engines") or []) if isinstance(row, dict)]
        view.bf_key = None
        view.notice = "Siege state is the server's snapshot."
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "engine" and isinstance(msg.get("engine"), dict):
        _upsert_engine(view, msg["engine"])
        view.notice = "The server placed that engine."
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "engine_hp":
        _set_engine_hp(view, msg.get("engine_id"), msg.get("hp"), msg.get("cooldown_until"))
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "engine_removed":
        view.engines = [row for row in view.engines if row.get("engine_id") != msg.get("engine_id")]
        view.notice = "An engine was packed up."
        return
    if kind == "KCS_DELTA" and msg.get("kind") == "opening":
        _upsert_opening(view, msg)
        view.bf_key = None
        view.notice = f"{msg.get('opening_id') or msg.get('id')} is {msg.get('state')}."
        return
    if kind == "KCS_PLACE_OK" and isinstance(msg.get("engine"), dict):
        _upsert_engine(view, msg["engine"])
        eng = msg["engine"]
        facing = eng.get("facing") or _face_name(eng.get("rotation") or 0)
        view.notice = f"Placed {str(eng.get('engine_type') or 'engine').replace('_', ' ')} facing {facing}."
        view.error = ""
        _say(client, view.notice, (180, 220, 170))


def on_keydown(client, event) -> bool:
    """Select and deploy. Number keys work without turning build mode on first."""
    if not active(client):
        if event.key == pygame.K_F8 and not getattr(client, "dungeon", None) and getattr(client, "state", "") == "GAME":
            _send(client, "ENTER_DUNGEON", dungeon_id=DUNGEON_ID)
            note(client, "Asking to deploy to King's Castle…")
            return True
        return False
    view = view_of(client)
    if event.key in ENGINE_KEYS or event.key in DEFENDER_KEYS:
        _select_type(view, event.key)
        return True
    if event.key == pygame.K_F6:
        view.build = not view.build
        view.notice = "Build mode on." if view.build else "Build mode off."
        return True
    if event.key == pygame.K_ESCAPE and view.build:
        view.build = False
        view.notice = "Build cancelled."
        return True
    if event.key == pygame.K_F7:
        _rotate(client)
        return True
    if event.key == pygame.K_F9:
        _turn_view(client)
        return True
    return False


def on_mouse(client, pos) -> bool:
    view = view_of(client)
    point = (int(pos[0]), int(pos[1]))
    for rect, action in list(view.buttons):
        if rect.collidepoint(point):
            _button(client, action)
            return True
    if not active(client) or view.origin is None or view.screen_o is None:
        return False
    x, y = point
    import client as game
    if x < 0 or y < HUD_TOP or x >= game.MAP_W or y >= game.MAP_H - HUD_BOT:
        return False
    apply_view_quarter(view.view_quarter)
    from kings_castle_siege_map.angled_proj import pick_tile
    tx, ty = pick_tile(x, y - HUD_TOP, view.origin, view.scale, view.screen_o)
    placing = (
        view.build
        and view.your_side in ("attack", "defend")
        and (client.dungeon or {}).get("mode") != "spectator"
    )
    if view.build and not placing:
        note(client, "Spectators do not place engines.", error=True)
        return True
    if not placing:
        _queue_walk(client, int(tx), int(ty))
        return True
    _place(client, int(tx), int(ty))
    return True


def tile_to_screen(client, tx, ty):
    view = view_of(client)
    if view.origin is None or view.screen_o is None:
        return None
    apply_view_quarter(view.view_quarter)
    from kings_castle_siege_map.angled_proj import project
    sx, sy, _depth = project(tx + 0.5, ty + 0.5, 0.0, view.origin, view.scale, view.screen_o)
    return int(sx), int(sy + HUD_TOP)


def draw(client) -> None:
    import client as game
    size = (game.MAP_W, game.MAP_H)
    view = view_of(client)
    try:
        surf = _render(client, view, size)
        _paint_facing(surf, client, view)
    except Exception as exc:
        surf = pygame.Surface(size)
        surf.fill((24, 18, 16))
        font = pygame.font.Font(None, 24)
        surf.blit(font.render("King's Castle view unavailable.", True, (240, 210, 170)), (16, 28))
        surf.blit(font.render(str(exc)[:110], True, (210, 170, 140)), (16, 58))
        view.error = str(exc)
    _chrome(surf, view)
    client.screen.blit(surf, (0, 0))


def _clock(seconds):
    if not isinstance(seconds, int):
        return None
    return f"{max(0, seconds) // 60}:{max(0, seconds) % 60:02d}"


def _status_lines(st):
    if not st:
        return []
    phase = st.get("phase") or st.get("status") or "Siege"
    lines = [f"King's Castle Siege — {phase}"]
    rem = _clock(st.get("remaining"))
    if rem:
        lines.append(f"Time left {rem}")
    elif st.get("status") == "registration":
        lines.append("Registration is open. The battle clock starts at Begin.")
    elif st.get("status") == "resolved":
        lines.append("The battle clock has stopped.")
    atk = (
        f"Attackers: {st.get('attack_enlisted', 0)} enlisted, "
        f"{st.get('attack_deployed', 0)} on the field, "
        f"{st.get('attack_absent', 0)} not deployed, "
        f"{st.get('attack_eliminated', 0)} eliminated"
    )
    dfd = (
        f"Defenders: {st.get('defend_enlisted', 0)} enlisted, "
        f"{st.get('defend_deployed', 0)} on the field, "
        f"{st.get('defend_eliminated', 0)} eliminated"
    )
    lines.extend((atk, dfd))
    grace_left = st.get("grace_left")
    if st.get("status") == "active" and isinstance(grace_left, int):
        if grace_left > 0:
            lines.append(f"Deploy grace {_clock(grace_left)} left. Absent attackers still count.")
        else:
            lines.append("Deploy grace has ended. Attackers who never deployed are out, not eliminated.")
    rule = st.get("grace_rule")
    if rule:
        lines.append(str(rule))
    objectives = st.get("objectives") or []
    if objectives:
        lines.append(" · ".join(f"{row.get('label')} {row.get('state')}" for row in objectives))
    result = st.get("result") or {}
    if result.get("text"):
        lines.append(f"Result: {result.get('text')}")
    previous = st.get("previous") or {}
    if previous.get("text") and st.get("status") != "resolved":
        lines.append(f"Last finished siege stays closed: {previous.get('text')}")
    own = st.get("ownership") or {}
    if own.get("crown_line"):
        lines.append(own["crown_line"])
    if own.get("castle_line"):
        lines.append(own["castle_line"])
    if st.get("sandbox"):
        lines.append("SANDBOX ONLY. This control is not part of a normal game.")
    return lines


def _draw_status(client, view) -> None:
    st = view.status or {}
    lines = _status_lines(st)
    if not lines:
        return
    import client as game
    font = pygame.font.Font(None, 16)
    width = min(640, max(360, game.MAP_W - 24))
    wrapped = []
    for line in lines:
        text = str(line)
        while text:
            cut = text
            while font.size(cut)[0] > width - 16 and len(cut) > 8:
                cut = cut[:-1]
            if cut != text and " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            wrapped.append(cut)
            text = text[len(cut):].lstrip()
    sandbox = bool(st.get("sandbox")) and st.get("status") not in ("locking", "active", "resolving")
    extra = 0
    players = list(st.get("sandbox_players") or []) if sandbox else []
    if sandbox:
        extra = 28 + 22 * max(1, len(players))
    height = 8 + 16 * len(wrapped) + extra
    top = max(96, game.MAP_H - height - 8)
    box = pygame.Rect(8, top, width, height)
    pygame.draw.rect(client.screen, (12, 10, 8), box)
    pygame.draw.rect(client.screen, (196, 164, 84), box, 1)
    y = box.y + 4
    for line in wrapped:
        client.screen.blit(font.render(line, True, (236, 220, 180)), (box.x + 8, y))
        y += 16
    if not sandbox:
        return
    y += 4
    if not players:
        client.screen.blit(font.render("No existing characters to assign.", True, (220, 180, 140)), (box.x + 8, y))
        return
    for row in players:
        if not isinstance(row, dict):
            continue
        pid = int(row.get("player_id"))
        side = view.prep_side.get(pid)
        word = {"attack": "attacker", "defend": "defender"}.get(side, "not in the next siege")
        label = f"{row.get('name') or pid}: {word}"
        rect = pygame.Rect(box.x + 8, y, min(360, font.size(label)[0] + 16), 20)
        pygame.draw.rect(client.screen, (36, 28, 16), rect)
        pygame.draw.rect(client.screen, (160, 130, 70), rect, 1)
        client.screen.blit(font.render(label, True, (240, 220, 180)), (rect.x + 6, rect.y + 2))
        view.buttons.append((rect, f"side-{pid}"))
        y += 22
    prep = pygame.Rect(box.x + 8, y, 280, 22)
    pygame.draw.rect(client.screen, (64, 28, 18), prep)
    pygame.draw.rect(client.screen, (220, 140, 70), prep, 1)
    client.screen.blit(font.render("SANDBOX ONLY: Prepare next test siege", True, (255, 220, 180)), (prep.x + 6, prep.y + 3))
    view.buttons.append((prep, "prep"))


def draw_overlay(client) -> None:
    """Clickable controls above the chat. Number keys still work."""
    if getattr(client, "state", "") != "GAME":
        return
    dungeon = getattr(client, "dungeon", None)
    if dungeon and dungeon.get("id") not in (None, DUNGEON_ID):
        return
    view = view_of(client)
    view.buttons = []
    font = pygame.font.Font(None, 18)
    x, y = 150, 64
    specs = [
        ("enlist-attack", "Enlist attack"),
        ("enlist-defend", "Enlist defend"),
        ("begin", "Begin"),
        ("deploy", "Deploy"),
        ("watch", "Watch"),
    ]
    decided = (view.status or {}).get("status") in ("resolved", "resolving")
    if active(client) and not decided:
        order = DEFENDER_ORDER if view.your_side == "defend" else ENGINE_ORDER
        specs = [(f"type-{kind}", f"{n} {ENGINE_SHORT[kind]}") for n, kind in enumerate(order, 1)]
        specs += [("turn", "Turn"), ("view", "View"), ("face", "Face wall"), ("fire", "Fire"),
                  ("pack", "Pack"), ("repair", "Repair"), ("strike", "Strike"), ("claim", "Claim throne")]
    for action, label in specs:
        width = max(72, font.size(label)[0] + 16)
        rect = pygame.Rect(x, y, width, 24)
        if rect.right > 880:
            x, y = 150, y + 28
            rect = pygame.Rect(x, y, width, 24)
        selected = action == f"type-{view.engine_type}" and view.build
        pygame.draw.rect(client.screen, (48, 36, 18) if selected else (28, 24, 18), rect)
        pygame.draw.rect(client.screen, (220, 180, 90) if selected else (120, 100, 70), rect, 1)
        client.screen.blit(font.render(label, True, (240, 220, 180)), (rect.x + 8, rect.y + 4))
        view.buttons.append((rect, action))
        x = rect.right + 6
    banner = view.error or view.preview or view.notice
    if banner:
        bar = pygame.Rect(150, y + 28, 700, 22)
        pygame.draw.rect(client.screen, (16, 14, 12), bar)
        client.screen.blit(font.render(banner[:120], True, (255, 180, 120) if view.error else (210, 190, 150)), (156, bar.y + 3))
    _draw_status(client, view)


def ensure_assets():
    """Point the renderer's asset folder at the external fixture tree."""
    parity = Path(__file__).resolve().parents[1] / "server" / "kcs_parity"
    dest = parity / "assets"
    src = Path(os.environ.get("KCS_VISUAL_FIXTURES", "/tmp/kcs_visual_fixtures")) / "assets"
    if dest.is_symlink() or dest.exists():
        return dest
    if not (src / "baked_m9" / "gatehouse.png").is_file():
        return None
    dest.symlink_to(src, target_is_directory=True)
    return dest


def _say(client, text, color) -> None:
    try:
        client.add_chat(text, color=color)
    except Exception:
        pass


def _send(client, kind, **fields) -> None:
    client.net.send(kind, **fields)


def _face_name(rotation: int) -> str:
    return {0: "north", 90: "east", 180: "south", 270: "west"}.get(int(rotation) % 360, "north")


VIEW_UP = ("north", "east", "south", "west")


def apply_view_quarter(quarter: int) -> None:
    """Turn the approved projection by a quarter. The art files stay as they are.

    The renderer keeps one yaw in module constants and does not take a camera
    argument. Setting those constants, and dropping its picture cache, is what
    makes the ground, the buildings, the click, and the gold nose agree.
    Quarter 0 is the original south-southwest view.
    """
    import math
    root = _parity_path()
    if root not in sys.path:
        sys.path.insert(0, root)
    import kings_castle_siege_map.angled_proj as proj
    quarter = int(quarter) % 4
    yaw = math.radians(26.0 + 90.0 * quarter)
    proj.YAW = yaw
    proj.COS_Y = math.cos(yaw)
    proj.SIN_Y = math.sin(yaw)
    proj.RIGHT = (proj.COS_Y, proj.SIN_Y)
    proj.LOOK = (proj.SIN_Y, -proj.COS_Y)


def pick_world_tile(client, mx, my):
    """Screen pixel to world tile under the current siege view. None off the map."""
    if not active(client):
        return None
    view = view_of(client)
    if view.origin is None or view.screen_o is None:
        return None
    import client as game
    if mx < 0 or my < HUD_TOP or mx >= game.MAP_W or my >= game.MAP_H - HUD_BOT:
        return None
    apply_view_quarter(view.view_quarter)
    from kings_castle_siege_map.angled_proj import pick_tile
    tx, ty = pick_tile(mx, my - HUD_TOP, view.origin, view.scale, view.screen_o)
    return int(tx), int(ty)


def _drop_view_cache() -> None:
    try:
        root = _parity_path()
        if root not in sys.path:
            sys.path.insert(0, root)
        from kings_castle_siege_map import angled_view
        angled_view._view_cache.clear()
    except Exception:
        pass


def _turn_view(client) -> None:
    view = view_of(client)
    view.view_quarter = (int(view.view_quarter) + 1) % 4
    client.camera_yaw = view.view_quarter
    apply_view_quarter(view.view_quarter)
    _drop_view_cache()
    view.error = ""
    view.notice = (
        f"View turned. Up the screen is {VIEW_UP[view.view_quarter]}. "
        f"The {ENGINE_SHORT.get(view.engine_type, view.engine_type)} still faces {_face_name(view.rotation)}."
    )


def _queue_walk(client, tx, ty) -> None:
    """Walk in world tiles toward the clicked tile. Arrows use the same yaw."""
    try:
        px, py = client.player_xy()
    except Exception:
        return
    x, y = int(px), int(py)
    path = []
    for _ in range(80):
        if x == tx and y == ty:
            break
        if abs(tx - x) >= abs(ty - y) and x != tx:
            x += 1 if tx > x else -1
        elif y != ty:
            y += 1 if ty > y else -1
        else:
            break
        path.append((x, y))
    client.walk_path = path
    client.walk_goal = path[-1] if path else None
    client.pending_action = None
    client._next_walk_at = 0


def _rotate(client) -> None:
    view = view_of(client)
    view.rotation = (int(view.rotation) + 90) % 360
    view.build = True
    view.error = ""
    view.notice = f"{ENGINE_SHORT.get(view.engine_type, view.engine_type)} now faces {_face_name(view.rotation)}."


def _button(client, action: str) -> None:
    view = view_of(client)
    if action.startswith("type-"):
        view.engine_type = action.split("-", 1)[1]
        view.build = True
        view.error = ""
        view.notice = f"Selected {ENGINE_SHORT.get(view.engine_type, view.engine_type)}. Nose faces {_face_name(view.rotation)}."
        return
    if action == "turn":
        _rotate(client)
        return
    if action == "view":
        _turn_view(client)
        return
    if action == "pack":
        _send(client, "KCS_PACK", engine_type=view.engine_type)
        note(client, f"Asking to pack the {ENGINE_SHORT.get(view.engine_type, view.engine_type)}…")
        return
    if action == "watch":
        _send(client, "ENTER_DUNGEON", dungeon_id=DUNGEON_ID, watch=True)
        note(client, "Asking to watch the siege…")
        return
    if action == "face":
        px, py = _player_tile(client)
        if view.bf is not None:
            import kcs_balance
            if view.your_side == "defend":
                view.rotation = kcs_balance.outward_rotation(px, py, view.bf.wall_box)
            else:
                view.rotation = kcs_balance.rotation_toward_wall(px, py, view.bf.wall_box)
        view.build = True
        view.error = ""
        if view.your_side == "defend":
            view.notice = f"Nose faces {_face_name(view.rotation)}, out from the wall."
        else:
            view.notice = f"Nose faces {_face_name(view.rotation)}, toward the nearest wall."
        return
    if action == "deploy":
        _send(client, "ENTER_DUNGEON", dungeon_id=DUNGEON_ID)
        note(client, "Asking to deploy…")
        return
    if action == "enlist-attack":
        _send(client, "KCS_ENLIST", side="attack")
        note(client, "Asking to enlist as an attacker…")
        return
    if action == "enlist-defend":
        _send(client, "KCS_ENLIST", side="defend")
        note(client, "Asking to enlist as a defender…")
        return
    if action == "begin":
        _send(client, "KCS_BEGIN")
        note(client, "Asking to begin the siege…")
        return
    if action == "fire":
        _send(client, "KCS_ACT", engine_type=view.engine_type)
        note(client, f"Asking the {ENGINE_SHORT.get(view.engine_type, view.engine_type)} to fire…")
        return
    if action == "repair":
        _send(client, "KCS_REPAIR")
        return
    if action == "strike":
        _send(client, "KCS_STRIKE")
        return
    if action.startswith("side-"):
        try:
            pid = int(action.split("-", 1)[1])
        except ValueError:
            return
        order = (None, "attack", "defend")
        current = view.prep_side.get(pid)
        view.prep_side[pid] = order[(order.index(current) + 1) % len(order)] if current in order else "attack"
        word = {"attack": "attacker", "defend": "defender"}.get(view.prep_side[pid], "left out")
        view.notice = f"Sandbox assignment: {word}."
        return
    if action == "prep":
        chosen = [
            {"player_id": int(pid), "side": side}
            for pid, side in view.prep_side.items()
            if side in ("attack", "defend")
        ]
        _send(client, "KCS_PREP", assignments=chosen)
        note(client, "SANDBOX ONLY: asking to prepare the next test siege…")
        return
    if action == "claim":
        _send(client, "KCS_CLAIM")
        note(client, "Asking to claim the throne…")


def _place(client, tx, ty) -> None:
    view = view_of(client)
    view.request_n += 1
    pid = int((getattr(client, "player", None) or {}).get("id") or 0)
    request_id = f"kcs-{pid}-{view.request_n}-{int(time.time() * 1000)}"
    try:
        _send(
            client, "KCS_PLACE",
            engine_type=view.engine_type,
            x=int(tx), y=int(ty),
            rotation=int(view.rotation) % 360,
            request_id=request_id[:64],
        )
        view.notice = (
            f"Asking to place a {ENGINE_SHORT.get(view.engine_type, view.engine_type)} "
            f"at {tx}, {ty} facing {_face_name(view.rotation)}."
        )
        _say(client, view.notice, (210, 190, 140))
    except Exception:
        view.error = "Could not send the placement."


def _select_type(view, key) -> None:
    table = DEFENDER_KEYS if view.your_side == "defend" else ENGINE_KEYS
    kind = table.get(key)
    if kind is None and view.your_side == "defend":
        view.notice = "Defenders build a ballista (1) or a cauldron (2)."
        view.error = ""
        return
    if kind is None:
        return
    view.engine_type = kind
    view.build = True
    view.error = ""
    view.notice = f"Selected {ENGINE_SHORT.get(kind, kind)}. Nose faces {_face_name(view.rotation)}."


def _set_engine_hp(view, engine_id, hp, cooldown) -> None:
    for row in view.engines:
        if row.get("engine_id") == engine_id:
            if hp is not None:
                row["hp"] = hp
            if cooldown is not None:
                row["cooldown_until"] = cooldown
            return


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
            if msg.get("hp") is not None:
                row["hp"] = msg.get("hp")
            found = True
    if not found and oid:
        view.openings.append({
            "id": oid,
            "plane": msg.get("plane") or "",
            "state": msg.get("state") or "intact",
            "rev": msg.get("rev") or 0,
            "hp": msg.get("hp"),
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
    linked, camera_look, render_world, build_battlefield, _placed = _load_renderer()
    if linked is None:
        raise RuntimeError("Set KCS_VISUAL_FIXTURES to the extracted siege art.")
    states = _gate_states(view)
    key = tuple(sorted(states.items()))
    if view.bf is None or view.bf_key != key:
        view.bf = build_battlefield(states or None)
        view.bf_key = key
    apply_view_quarter(view.view_quarter)
    client.camera_yaw = int(view.view_quarter) % 4
    px, py = _player_tile(client)
    scale = 28.0
    world_size = (size[0], size[1] - HUD_TOP - HUD_BOT)
    origin, screen_o = camera_look((px, py), world_size, scale)
    view.origin = origin
    view.screen_o = screen_o
    view.scale = scale
    started = time.perf_counter()
    # Engines are omitted here and painted afterwards so their nose can rotate.
    surf = render_world(
        view.bf, (px, py), [], "King's Castle", "",
        size=size, tile_px=scale, facing=_facing(client),
        gate_states=states or None, markers=False,
    )
    view.last_ms = (time.perf_counter() - started) * 1000.0
    return surf


def _paint_facing(surf, client, view) -> None:
    import kcs_balance
    from kings_castle_siege_map.angled_proj import project
    from kings_castle_siege_map.angled_view import load_baked
    from kings_castle_siege_map.placement import PlacedEngine, validate_placement

    def _mark(tiles, rotation, color, sprite):
        tiles = [(int(t[0]), int(t[1])) for t in tiles]
        if not tiles:
            return
        cx = sum(t[0] for t in tiles) / len(tiles)
        cy = sum(t[1] for t in tiles) / len(tiles)
        fx, fy = kcs_balance.front_point(tiles, rotation)
        scx, scy, _z = project(cx + 0.5, cy + 0.5, 0, view.origin, view.scale, view.screen_o)
        sfx, sfy, _z = project(fx + 0.5, fy + 0.5, 0, view.origin, view.scale, view.screen_o)
        scx, scy = int(scx), int(scy + HUD_TOP)
        sfx, sfy = int(sfx), int(sfy + HUD_TOP)
        if sprite == "cauldron":
            pygame.draw.circle(surf, (92, 56, 36), (scx, scy), 12)
            pygame.draw.circle(surf, (186, 112, 58), (scx, scy), 8)
        art = SPRITE_ALIAS.get(sprite, sprite)
        if sprite != "cauldron" and art:
            try:
                img, _meta = load_baked(art)
                angle = {0: 0, 90: -90, 180: 180, 270: 90}.get(int(rotation) % 360, 0)
                if angle:
                    img = pygame.transform.rotate(img, angle)
                longest = max(img.get_width(), img.get_height())
                scale = 56 / max(1, longest)
                spr = pygame.transform.smoothscale(img, (max(8, int(img.get_width() * scale)), max(8, int(img.get_height() * scale))))
                surf.blit(spr, (scx - spr.get_width() // 2, scy - spr.get_height() // 2))
            except Exception:
                pass
        pygame.draw.line(surf, color, (scx, scy), (sfx, sfy), 3)
        pygame.draw.circle(surf, color, (sfx, sfy), 5)

    for row in view.engines:
        if int(row.get("hp") if row.get("hp") is not None else 1) <= 0:
            continue
        tiles = row.get("tiles") or [[row.get("x") or 0, row.get("y") or 0]]
        _mark(tiles, int(row.get("rotation") or 0), (255, 214, 90), row.get("engine_type"))
    if not view.build or view.bf is None or view.origin is None:
        return
    mx, my = pygame.mouse.get_pos()
    import client as game
    if not (HUD_TOP <= my < game.MAP_H - HUD_BOT and 0 <= mx < game.MAP_W):
        return
    from kings_castle_siege_map.angled_proj import pick_tile
    tx, ty = pick_tile(mx, my - HUD_TOP, view.origin, view.scale, view.screen_o)
    existing = []
    for row in view.engines:
        try:
            existing.append(PlacedEngine(str(row.get("engine_id")), str(row.get("engine_type")),
                                         int(row.get("x")), int(row.get("y")), int(row.get("rotation") or 0)))
        except Exception:
            continue
    result = validate_placement(view.bf, view.engine_type, int(tx), int(ty), int(view.rotation), existing)
    tiles = result.tiles or [(int(tx), int(ty))]
    _mark(tiles, view.rotation, (80, 220, 90) if result.ok else (230, 70, 60), view.engine_type)
    view.preview = "" if result.ok else result.reason


def _chrome(surf, view) -> None:
    width, height = surf.get_size()
    small = pygame.font.Font(None, 18)
    pygame.draw.rect(surf, (18, 16, 14), (0, 0, width, HUD_TOP))
    pygame.draw.rect(surf, (18, 16, 14), (0, height - HUD_BOT, width, HUD_BOT))
    small_note = (
        f"View up is {VIEW_UP[int(view.view_quarter) % 4]}. "
        f"{ENGINE_SHORT.get(view.engine_type, view.engine_type)} faces {_face_name(view.rotation)}. "
        "Gold is not spent."
    )
    surf.blit(small.render(small_note[:110], True, (168, 150, 130)), (12, height - 26))
