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
        self.sync_seq = None
        self.stale = False
        self.eliminated = set()
        self.removed = set()
        self.shots = []
        self.marks = []
        self.resync_at = 0.0
        self.guide_open = False
        self.guide_dismissed = False
        self.guide_page = 0
        self.guide_buttons = []
        self.inspect = None


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
        if kind == "KCS_RESULT":
            note = ((view.status or {}).get("result") or {}).get("ownership_note")
            if note:
                _say(client, note, (220, 200, 140))
        return
    if not active(client):
        return
    if kind == "KCS_SNAPSHOT":
        _take_status(view, msg)
        view.war_id = msg.get("war_id") or view.war_id
        view.your_side = msg.get("your_side") or view.your_side
        view.openings = [dict(row) for row in (msg.get("openings") or []) if isinstance(row, dict)]
        view.engines = [dict(row) for row in (msg.get("engines") or []) if isinstance(row, dict)]
        view.removed = set()
        view.eliminated = {int(pid) for pid in (msg.get("eliminated") or [])}
        view.shots = []
        seq = msg.get("sync_seq")
        if isinstance(seq, int):
            view.sync_seq = seq
        view.stale = False
        view.bf_key = None
        view.error = ""
        view.notice = "Siege state is the server's snapshot."
        _hide_eliminated(client, view)
        return
    if kind == "KCS_DELTA":
        decision = _accept_delta(view, msg)
        if decision == "gap":
            _request_snapshot(client, view)
            return
        if decision != "apply":
            return
        events = msg.get("events")
        if not isinstance(events, list) or not events:
            events = [msg]
        for ev in events:
            if isinstance(ev, dict):
                _apply_delta(client, view, ev)
        return
    if kind == "KCS_PLACE_OK" and isinstance(msg.get("engine"), dict):
        if msg["engine"].get("engine_id") not in view.removed:
            _upsert_engine(view, msg["engine"])
        eng = msg["engine"]
        facing = eng.get("facing") or _face_name(eng.get("rotation") or 0)
        view.notice = f"Placed {str(eng.get('engine_type') or 'engine').replace('_', ' ')} facing {facing}."
        view.error = ""
        _say(client, view.notice, (180, 220, 170))


def on_keydown(client, event) -> bool:
    """Select and deploy. Number keys work without turning build mode on first."""
    view = view_of(client)
    if view.guide_open and event.key == pygame.K_ESCAPE:
        _close_guide(view)
        return True
    if getattr(client, "chat_typing", False):
        return False
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
    if view.guide_open:
        for rect, action in list(view.guide_buttons):
            if rect.collidepoint(point):
                _guide_click(view, action)
                return True
        return True
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
        subject = _subject_at(client, view, int(tx), int(ty))
        if subject is not None:
            view.inspect = subject
            view.notice = subject.get("title") or view.notice
            view.error = ""
            return True
        view.inspect = None
        _queue_walk(client, int(tx), int(ty))
        return True
    if _combat_paused(client, view):
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
        _paint_battle(surf, client, view)
    except Exception as exc:
        surf = pygame.Surface(size)
        surf.fill((24, 18, 16))
        font = pygame.font.Font(None, 24)
        missing = ensure_assets() is None
        title = "Castle art was not found." if missing else "The castle picture could not be drawn."
        detail = "The buttons still work. The preview pictures can be supplied later."
        surf.blit(font.render(title, True, (240, 210, 170)), (16, 28))
        surf.blit(font.render(detail, True, (210, 170, 140)), (16, 58))
        view.error = title
    _chrome(surf, view)
    if view.stale or not getattr(getattr(client, "net", None), "connected", True):
        view.stale = True
        font = pygame.font.Font(None, 22)
        banner = "Connection lost. Reconnecting. Siege actions are paused."
        surf.blit(font.render(banner, True, (255, 214, 150)), (12, HUD_TOP + 8))
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
    if result.get("ownership_note"):
        lines.append(result["ownership_note"])
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


GUIDE_PAGES = (
    (
        "King's Castle Siege",
        "Enlist as Attack or Defend, press Begin, then Deploy. "
        "Watch lets you spectate without fighting. Buttons do the same work as the keys.",
    ),
    (
        "Building",
        "Pick an engine with 1–4 or the buttons. Green preview = valid. Red shows the refusal. "
        "Turn engine (or Fn+F7) rotates the nose. Face wall aims at the wall. "
        "Turn camera (or Fn+F9) only changes the view.",
    ),
    (
        "Fighting and defence",
        "Stand beside your engine to Fire or Pack. Defenders also Repair and Strike. "
        "Click an engine, gate, or fighter to inspect health, range, and cooldown. "
        "Death eliminates you; Watch remains until the war ends.",
    ),
    (
        "Victory and reconnect",
        "Attackers win by claiming the throne after the keep doors fall. Defenders win on time "
        "or when attackers are gone. The crown is announced only after it is recorded. "
        "If the link drops, actions pause until a fresh snapshot arrives. Esc dismisses this guide.",
    ),
)


def control_specs(client, view):
    specs = [
        ("guide", "Guide"),
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
        specs += [
            ("turn", "Turn engine"),
            ("view", "Turn camera"),
            ("face", "Face wall"),
            ("fire", "Fire"),
            ("pack", "Pack"),
            ("repair", "Repair"),
            ("strike", "Strike"),
            ("claim", "Claim throne"),
            ("guide", "Guide"),
        ]
    elif decided:
        specs = [("guide", "Guide")]
    return specs


def control_rects(labels, font, map_w, reserve_right=0):
    """Wrap the control row so buttons stay on the map at the usual window size."""
    x, y = 150, 64
    right = max(220, int(map_w) - 8 - int(reserve_right or 0))
    out = []
    for label in labels:
        width = max(72, font.size(label)[0] + 16)
        if x + width > right and out:
            x, y = 150, y + 28
        out.append(pygame.Rect(x, y, width, 24))
        x += width + 6
    return out


def preview_at(view, tx, ty, existing=None):
    from kings_castle_siege_map.placement import PlacedEngine, validate_placement
    if existing is None:
        existing = []
        for row in view.engines:
            try:
                existing.append(PlacedEngine(
                    str(row.get("engine_id")), str(row.get("engine_type")),
                    int(row.get("x")), int(row.get("y")), int(row.get("rotation") or 0),
                ))
            except Exception:
                continue
    result = validate_placement(view.bf, view.engine_type, int(tx), int(ty), int(view.rotation), existing)
    if result.ok and view.your_side == "defend":
        import kcs_balance
        px = int(getattr(view, "_preview_px", tx))
        py = int(getattr(view, "_preview_py", ty))
        if not kcs_balance.beside(px, py, result.tiles or [(tx, ty)]):
            class _Refuse:
                ok = False
                reason = "Stand on the wall to build that."
                tiles = result.tiles or [(tx, ty)]
            result = _Refuse()
    if result.ok:
        view.preview = (
            f"{ENGINE_SHORT.get(view.engine_type, view.engine_type)} faces "
            f"{_face_name(view.rotation)}. Click to place."
        )
        view.error = ""
    else:
        view.preview = result.reason or "That placement is refused."
    return result


def _subject_at(client, view, tx, ty):
    for row in view.engines:
        tiles = row.get("tiles") or [[row.get("x") or 0, row.get("y") or 0]]
        if any(int(t[0]) == tx and int(t[1]) == ty for t in tiles):
            return _engine_inspect(row)
    for row in view.openings:
        for tile in row.get("tiles") or []:
            if int(tile[0]) == tx and int(tile[1]) == ty:
                return _opening_inspect(row)
        if int(row.get("x") or -1) == tx and int(row.get("y") or -1) == ty:
            return _opening_inspect(row)
    for person in (getattr(client, "players", None) or {}).values():
        if int(person.get("x") or -1) == tx and int(person.get("y") or -1) == ty:
            return _fighter_inspect(person)
    me = getattr(client, "player", None) or {}
    if int(me.get("x") or -1) == tx and int(me.get("y") or -1) == ty:
        return _fighter_inspect({**me, "kcs_side": view.your_side, "kcs_mode": (client.dungeon or {}).get("mode")})
    return None


def _engine_inspect(row):
    kind = row.get("engine_type") or "engine"
    import kcs_balance
    spec = dict(kcs_balance.ENGINES.get(kind) or kcs_balance.DEFENDER_ENGINES.get(kind) or {})
    ready = row.get("cooldown_until")
    wait = ""
    if isinstance(ready, (int, float)) and ready > time.time():
        wait = f" Reloading {max(0, int(ready - time.time()))}s."
    return {
        "kind": "engine",
        "title": f"{ENGINE_SHORT.get(kind, kind)} · {_face_name(row.get('rotation') or 0)}",
        "lines": [
            f"Side {row.get('side') or '?'}",
            f"HP {row.get('hp') if row.get('hp') is not None else '?'}"
            + (f"/{spec['hp']}" if spec.get("hp") else ""),
            f"Range {spec.get('range', '?')} · cooldown {spec.get('cooldown', '?')}s." + wait,
            "Fire / Pack while standing beside it.",
        ],
        "engine_id": row.get("engine_id"),
    }


def _opening_inspect(row):
    oid = row.get("id") or row.get("opening_id") or "opening"
    label = str(oid).replace("_", " ")
    return {
        "kind": "opening",
        "title": label.title(),
        "lines": [
            f"State {row.get('state') or 'intact'}",
            f"HP {row.get('hp') if row.get('hp') is not None else '?'}",
            "Breaches open crossings. Keep doors lead to the throne room.",
        ],
        "opening_id": oid,
    }


def _fighter_inspect(person):
    side = person.get("kcs_side") or "?"
    mode = person.get("kcs_mode") or ""
    role = "spectator" if mode == "spectator" else side
    return {
        "kind": "fighter",
        "title": f"{person.get('name') or 'Fighter'} · {role}",
        "lines": [
            f"HP {person.get('hp', '?')}/{person.get('max_hp', '?')}",
            "Attackers wear red marks. Defenders wear blue. Spectators are grey.",
        ],
        "player_id": person.get("id"),
    }


def _close_guide(view) -> None:
    view.guide_open = False
    view.guide_dismissed = True
    view.guide_buttons = []


def _guide_click(view, action: str) -> None:
    if action == "guide-close":
        _close_guide(view)
        return
    if action == "guide-next":
        view.guide_page = min(len(GUIDE_PAGES) - 1, int(view.guide_page) + 1)
        return
    if action == "guide-prev":
        view.guide_page = max(0, int(view.guide_page) - 1)


def _wrap(font, text, width):
    words = str(text or "").split()
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if font.size(trial)[0] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _draw_role(client, view, font) -> None:
    mode = (getattr(client, "dungeon", None) or {}).get("mode") or ""
    side = view.your_side or (view.status or {}).get("your_side")
    if mode == "spectator":
        label, color = "Spectator", (170, 170, 170)
    elif side == "attack":
        label, color = "Attacker", (210, 90, 70)
    elif side == "defend":
        label, color = "Defender", (80, 140, 210)
    else:
        label, color = "Not enlisted", (180, 160, 120)
    rect = pygame.Rect(8, 64, max(110, font.size(label)[0] + 16), 24)
    pygame.draw.rect(client.screen, (18, 16, 14), rect)
    pygame.draw.rect(client.screen, color, rect, 1)
    client.screen.blit(font.render(label, True, color), (rect.x + 8, rect.y + 4))


def _draw_objectives(client, view, top) -> None:
    st = view.status or {}
    objectives = st.get("objectives") or []
    result = st.get("result") or {}
    if not objectives and not result:
        return
    font = pygame.font.Font(None, 16)
    lines = ["Objectives"]
    for row in objectives:
        lines.append(f"{row.get('label')}: {row.get('state')}")
    if result.get("text"):
        lines.append(result.get("text"))
    if result.get("ownership_note"):
        lines.append(result.get("ownership_note"))
    width = 250
    height = 8 + 15 * len(lines)
    box = pygame.Rect(8, int(top), width, height)
    pygame.draw.rect(client.screen, (12, 10, 8), box)
    pygame.draw.rect(client.screen, (140, 120, 70), box, 1)
    y = box.y + 4
    for line in lines:
        client.screen.blit(font.render(str(line)[:42], True, (230, 210, 170)), (box.x + 6, y))
        y += 15


def _draw_inspect(client, view) -> None:
    info = view.inspect
    if not info:
        return
    import client as game
    font = pygame.font.Font(None, 16)
    lines = [info.get("title") or "Selected"] + list(info.get("lines") or [])
    width = 260
    height = 8 + 15 * len(lines)
    box = pygame.Rect(game.MAP_W - width - 8, 96, width, height)
    pygame.draw.rect(client.screen, (12, 10, 8), box)
    pygame.draw.rect(client.screen, (196, 164, 84), box, 1)
    y = box.y + 4
    for line in lines:
        client.screen.blit(font.render(str(line)[:44], True, (236, 220, 180)), (box.x + 6, y))
        y += 15


def _draw_guide(client, view) -> None:
    view.guide_buttons = []
    if not view.guide_open:
        return
    import client as game
    page = max(0, min(len(GUIDE_PAGES) - 1, int(view.guide_page)))
    title, body = GUIDE_PAGES[page]
    font = pygame.font.Font(None, 20)
    small = pygame.font.Font(None, 17)
    box = pygame.Rect(70, 90, min(760, game.MAP_W - 100), 280)
    pygame.draw.rect(client.screen, (18, 14, 12), box)
    pygame.draw.rect(client.screen, (210, 170, 90), box, 2)
    client.screen.blit(font.render(title, True, (250, 220, 160)), (box.x + 16, box.y + 14))
    y = box.y + 44
    for line in _wrap(small, body, box.width - 32):
        client.screen.blit(small.render(line, True, (230, 210, 180)), (box.x + 16, y))
        y += 18
    note = "Mac: hold Fn with F6 build, F7 turn engine, F8 deploy, F9 turn camera."
    client.screen.blit(small.render(note, True, (190, 160, 120)), (box.x + 16, box.bottom - 70))
    client.screen.blit(
        small.render(f"Page {page + 1}/{len(GUIDE_PAGES)}. Esc or Done closes.", True, (170, 150, 120)),
        (box.x + 16, box.bottom - 50),
    )
    buttons = []
    if page > 0:
        buttons.append(("guide-prev", "Back"))
    if page < len(GUIDE_PAGES) - 1:
        buttons.append(("guide-next", "Next"))
    buttons.append(("guide-close", "Done"))
    x = box.right - 16
    for action, label in reversed(buttons):
        width = max(64, small.size(label)[0] + 18)
        x -= width
        rect = pygame.Rect(x, box.bottom - 34, width, 24)
        pygame.draw.rect(client.screen, (40, 30, 18), rect)
        pygame.draw.rect(client.screen, (210, 170, 90), rect, 1)
        client.screen.blit(small.render(label, True, (250, 220, 160)), (rect.x + 8, rect.y + 4))
        view.guide_buttons.append((rect, action))
        x -= 8


def draw_overlay(client) -> None:
    """Clickable controls above the chat. Number keys still work."""
    import client as game
    if getattr(client, "state", "") != "GAME":
        return
    dungeon = getattr(client, "dungeon", None)
    if dungeon and dungeon.get("id") not in (None, DUNGEON_ID):
        return
    view = view_of(client)
    if not view.guide_dismissed and not view.guide_open:
        view.guide_open = True
        view.guide_page = 0
    view.buttons = []
    font = pygame.font.Font(None, 18)
    specs = control_specs(client, view)
    reserve = 230 if active(client) else 0
    rects = control_rects([label for _action, label in specs], font, game.MAP_W, reserve_right=reserve)
    row_bottom = 64
    for (action, label), rect in zip(specs, rects):
        selected = action == f"type-{view.engine_type}" and view.build
        pygame.draw.rect(client.screen, (48, 36, 18) if selected else (28, 24, 18), rect)
        pygame.draw.rect(client.screen, (220, 180, 90) if selected else (120, 100, 70), rect, 1)
        client.screen.blit(font.render(label, True, (240, 220, 180)), (rect.x + 8, rect.y + 4))
        view.buttons.append((rect, action))
        row_bottom = max(row_bottom, rect.bottom)
    banner = view.error or view.preview or view.notice
    banner_bottom = row_bottom
    if banner:
        bar = pygame.Rect(150, row_bottom + 4, min(520, game.MAP_W - 160), 22)
        pygame.draw.rect(client.screen, (16, 14, 12), bar)
        client.screen.blit(font.render(banner[:90], True, (255, 180, 120) if view.error else (210, 190, 150)), (bar.x + 6, bar.y + 3))
        banner_bottom = bar.bottom
    _draw_role(client, view, font)
    _draw_objectives(client, view, banner_bottom + 4)
    _draw_inspect(client, view)
    _draw_status(client, view)
    _draw_guide(client, view)


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
    if action == "guide":
        view.guide_open = True
        view.guide_page = 0
        view.guide_dismissed = False
        return
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
        if _combat_paused(client, view):
            return
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
        if _combat_paused(client, view):
            return
        _send(client, "KCS_ACT", engine_type=view.engine_type)
        note(client, f"Asking the {ENGINE_SHORT.get(view.engine_type, view.engine_type)} to fire…")
        return
    if action == "repair":
        if _combat_paused(client, view):
            return
        _send(client, "KCS_REPAIR")
        return
    if action == "strike":
        if _combat_paused(client, view):
            return
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
        if _combat_paused(client, view):
            return
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


def _combat_paused(client, view) -> bool:
    """Block combat until this connection has a snapshot of the live battle."""
    connected = getattr(getattr(client, "net", None), "connected", True)
    if not connected:
        view.stale = True
    if (client.dungeon or {}).get("mode") == "spectator":
        view.notice = "Spectators cannot affect the battle."
        view.error = view.notice
        return True
    if view.stale or view.sync_seq is None:
        view.stale = True
        view.notice = "Reconnecting. Siege actions are paused until the battle snapshot arrives."
        view.error = view.notice
        return True
    return False


def _accept_delta(view, msg):
    seq = msg.get("seq")
    if not isinstance(seq, int):
        return "drop"
    war = msg.get("war_id")
    if war is not None and view.war_id is not None and int(war) != int(view.war_id):
        return "drop"
    if view.sync_seq is None or seq > view.sync_seq + 1:
        view.stale = True
        view.notice = "Siege updates fell behind. Waiting for a fresh snapshot."
        view.error = view.notice
        return "gap"
    if seq <= view.sync_seq:
        return "drop"
    view.sync_seq = seq
    view.stale = False
    view.error = ""
    return "apply"


def _request_snapshot(client, view) -> None:
    now = time.time()
    if now - view.resync_at < 1.0:
        return
    view.resync_at = now
    if getattr(getattr(client, "net", None), "connected", False):
        _send(client, "KCS_SNAPSHOT")


def _hide_eliminated(client, view) -> None:
    players = getattr(client, "players", None)
    if not isinstance(players, dict):
        return
    for pid in list(view.eliminated):
        players.pop(pid, None)


def _apply_delta(client, view, msg) -> None:
    kind = msg.get("kind")
    if kind == "engine" and isinstance(msg.get("engine"), dict):
        eid = msg["engine"].get("engine_id")
        if eid in view.removed:
            return
        _upsert_engine(view, msg["engine"])
        view.notice = "The server placed that engine."
        return
    if kind == "engine_hp":
        _set_engine_hp(view, msg.get("engine_id"), msg.get("hp"), msg.get("cooldown_until"))
        for row in view.engines:
            if row.get("engine_id") == msg.get("engine_id"):
                tiles = row.get("tiles") or [[row.get("x") or 0, row.get("y") or 0]]
                view.marks.append({"x": tiles[0][0], "y": tiles[0][1], "until": time.time() + 0.6, "color": (240, 120, 70)})
                break
        return
    if kind == "engine_state":
        for row in msg.get("engines") or []:
            if not isinstance(row, dict) or row.get("engine_id") in view.removed:
                continue
            if any(existing.get("engine_id") == row.get("engine_id") for existing in view.engines):
                _set_engine_hp(view, row.get("engine_id"), row.get("hp"), row.get("cooldown_until"))
                for existing in view.engines:
                    if existing.get("engine_id") == row.get("engine_id") and row.get("rotation") is not None:
                        existing["rotation"] = row.get("rotation")
            else:
                _upsert_engine(view, row)
        return
    if kind == "engine_removed":
        eid = msg.get("engine_id")
        view.removed.add(eid)
        view.engines = [row for row in view.engines if row.get("engine_id") != eid]
        view.notice = "An engine was packed up."
        return
    if kind == "opening":
        _upsert_opening(view, msg)
        view.bf_key = None
        oid = msg.get("opening_id") or msg.get("id")
        state = msg.get("state")
        view.notice = f"{oid} is {state}."
        if state == "destroyed":
            _say(client, f"{str(oid).replace('_', ' ').title()} is breached.", (240, 180, 120))
        for row in view.openings:
            if (row.get("id") == oid or row.get("opening_id") == oid) and row.get("tiles"):
                tile = row["tiles"][0]
                view.marks.append({"x": tile[0], "y": tile[1], "until": time.time() + 0.9, "color": (255, 160, 80)})
                break
        return
    if kind == "shot":
        shot = dict(msg)
        shot["until"] = time.time() + 0.45
        view.shots.append(shot)
        view.shots = view.shots[-8:]
        view.marks.append({"x": shot.get("tx"), "y": shot.get("ty"), "until": time.time() + 0.5, "color": (250, 220, 120)})
        return
    if kind == "player_hp":
        pid = msg.get("player_id")
        if pid in view.eliminated:
            return
        players = getattr(client, "players", None)
        if isinstance(players, dict) and pid in players and msg.get("hp") is not None:
            players[pid]["hp"] = msg.get("hp")
        return
    if kind == "eliminated":
        pid = msg.get("player_id")
        if pid is None:
            return
        view.eliminated.add(int(pid))
        _hide_eliminated(client, view)


def _set_engine_hp(view, engine_id, hp, cooldown) -> None:
    if engine_id in view.removed:
        return
    for row in view.engines:
        if row.get("engine_id") == engine_id:
            if hp is not None:
                row["hp"] = hp
            if cooldown is not None:
                row["cooldown_until"] = cooldown
            return


def _upsert_engine(view, engine) -> None:
    eid = engine.get("engine_id")
    if eid in view.removed:
        return
    view.engines = [row for row in view.engines if row.get("engine_id") != eid]
    view.engines.append(dict(engine))


def _upsert_opening(view, msg) -> None:
    oid = msg.get("opening_id") or msg.get("id")
    new_rev = msg.get("rev")
    found = False
    for row in view.openings:
        if row.get("id") == oid or row.get("opening_id") == oid:
            old = row.get("rev")
            if isinstance(new_rev, int) and isinstance(old, int) and new_rev < old:
                return
            row["state"] = msg.get("state", row.get("state"))
            if new_rev is not None:
                row["rev"] = new_rev
            if msg.get("hp") is not None:
                row["hp"] = msg.get("hp")
            found = True
    if not found and oid:
        view.openings.append({
            "id": oid,
            "plane": msg.get("plane") or "",
            "state": msg.get("state") or "intact",
            "rev": new_rev or 0,
            "hp": msg.get("hp"),
        })


def _paint_battle(surf, client, view) -> None:
    """Marks for nearby fighters and a short line for a shot. Not a new renderer."""
    now = time.time()
    view.shots = [shot for shot in view.shots if shot.get("until", 0) > now]
    view.marks = [mark for mark in view.marks if mark.get("until", 0) > now]
    me = (getattr(client, "player", None) or {}).get("id")
    font = pygame.font.Font(None, 16)
    for person in (getattr(client, "players", None) or {}).values():
        if person.get("id") == me or person.get("id") in view.eliminated:
            continue
        spot = tile_to_screen(client, person.get("x", 0), person.get("y", 0))
        if spot is None:
            continue
        side = person.get("kcs_side")
        mode = person.get("kcs_mode")
        if mode == "spectator":
            color = (170, 170, 170)
        elif side == "attack":
            color = (190, 70, 60)
        elif side == "defend":
            color = (70, 130, 200)
        else:
            color = (170, 170, 170)
        pygame.draw.circle(surf, color, spot, 5)
        label = f"{person.get('hp', '')}"
        if label:
            surf.blit(font.render(str(label), True, color), (spot[0] + 7, spot[1] - 8))
    for shot in view.shots:
        start = tile_to_screen(client, shot.get("x", 0), shot.get("y", 0))
        end = tile_to_screen(client, shot.get("tx", 0), shot.get("ty", 0))
        if start is None or end is None:
            continue
        pygame.draw.line(surf, (240, 220, 140), start, end, 2)
    for mark in view.marks:
        spot = tile_to_screen(client, mark.get("x", 0), mark.get("y", 0))
        if spot is None:
            continue
        pygame.draw.circle(surf, mark.get("color") or (240, 180, 80), spot, 10, 2)


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
        for tx, ty in tiles:
            px, py, _z = project(tx + 0.5, ty + 0.5, 0, view.origin, view.scale, view.screen_o)
            pygame.draw.circle(surf, color, (int(px), int(py + HUD_TOP)), 7, 1)
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
    try:
        view._preview_px, view._preview_py = _player_tile(client)
    except Exception:
        view._preview_px, view._preview_py = int(tx), int(ty)
    result = preview_at(view, int(tx), int(ty), existing)
    tiles = result.tiles or [(int(tx), int(ty))]
    _mark(tiles, view.rotation, (80, 220, 90) if result.ok else (230, 70, 60), view.engine_type)


def _chrome(surf, view) -> None:
    width, height = surf.get_size()
    small = pygame.font.Font(None, 18)
    pygame.draw.rect(surf, (18, 16, 14), (0, 0, width, HUD_TOP))
    pygame.draw.rect(surf, (18, 16, 14), (0, height - HUD_BOT, width, HUD_BOT))
    camera = VIEW_UP[int(view.view_quarter) % 4]
    nose = _face_name(view.rotation)
    line = f"Camera up: {camera}.  Engine nose: {nose}.  Face wall aims the engine, not the camera."
    surf.blit(small.render(line[:120], True, (168, 150, 130)), (12, height - 40))
    surf.blit(small.render("Turn engine and Turn camera are different. Gold is not spent.", True, (168, 150, 130)), (12, height - 22))
