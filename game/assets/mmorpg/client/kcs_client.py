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
import math
import sys
import time
from pathlib import Path

import pygame

# Main game: the siege art ships in-tree (fixtures/kcs_visual_gear_anim_v1); an explicit env still wins.
os.environ.setdefault("KCS_VISUAL_FIXTURES", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                          "fixtures", "kcs_visual_gear_anim_v1"))

DUNGEON_ID = "kings_castle_siege"
HUD_TOP = 0
HUD_BOT = 0
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
# Plain-name fallback only; directional plates remove the need to alias ballista.
SPRITE_ALIAS = {}


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
        self.selected_engine_id = None
        self.engine_pick_rects = {}
        self.engine_ready_state = {}
        self.engine_ready_flash = {}
        self.rotation = 0
        self.view_quarter = 0
        self.request_n = 0
        self.notice = "Enlist, begin, then deploy. 1–4 select an engine."
        self.error = ""
        self.preview = ""
        self.origin = None
        self.screen_o = None
        self.scale = 28.0
        self.zoom = 1.0
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
        self.details_open = False
        self.ui_regions = []
        self.motion = {}
        self.actor_anims = {}
        self.actor_hits = {}
        self.actor_melee = {}
        self.actor_actions = {}
        self.engine_actions = {}
        self.action_seen = {}
        self.corpses = {}


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


def _game(client):
    """Use the running entry module, not a second import of client.py.

    The Mac launcher runs __main__; importing client used to expand a different
    module's viewport, leaving the real game clipped to its overworld layout.
    """
    module = sys.modules.get(type(client).__module__)
    if module is not None and hasattr(module, "MAP_W"):
        return module
    import client as game
    return game


def _apply_siege_layout(client) -> None:
    """Hide both sidebars and expand the map to the full window while in siege."""
    game = _game(client)
    if not getattr(client, "_kcs_layout_saved", None):
        client._kcs_layout_saved = {
            "MAP_W": game.MAP_W,
            "MAP_H": game.MAP_H,
            "SIDEBAR_X": game.SIDEBAR_X,
            "show_equipment": bool(getattr(client, "show_equipment", False)),
        }
    width, height = client.screen.get_size()
    game.MAP_W, game.MAP_H = width, height
    game.SIDEBAR_X = width
    if not (view_of(client).status or {}).get("economy"):client.show_equipment = False


def _restore_siege_layout(client) -> None:
    game = _game(client)
    saved = getattr(client, "_kcs_layout_saved", None)
    if not saved:
        return
    game.MAP_W = int(saved["MAP_W"])
    game.MAP_H = int(saved["MAP_H"])
    client.show_equipment = saved["show_equipment"]
    game.SIDEBAR_X = int(saved["SIDEBAR_X"])
    client._kcs_layout_saved = None


def on_enter(client) -> None:
    view = view_of(client)
    _apply_siege_layout(client)
    client.show_equipment=False
    if view.your_side == "defend":
        view.engine_type = "ballista"
        view.notice = "Deployed. 1 Ballista, 2 Cauldron. Stand on the wall-walk and face them outward."
    else:
        view.notice = "Deployed. 1 Ram, 2 Trebuchet, 3 Tower, 4 Ladder. Rotate until the nose points at the wall."
    view.error = ""
    client.chat_typing = False
    client.context_menu = None


def on_exit(client) -> None:
    import player_interactions
    player_interactions.on_disconnect(client)
    view = getattr(client, "kcs_view", None)
    if view is not None:
        view.buttons = []
        view.build = False
        view.view_quarter = 0
    client.camera_yaw = 0
    apply_view_quarter(0)
    _restore_siege_layout(client)


def _take_status(view, msg) -> None:
    panel = msg.get("status_panel") if isinstance(msg.get("status_panel"), dict) else msg
    if not isinstance(panel, dict) or "status" not in panel:
        return
    if panel.get('war_id') and view.war_id and panel['war_id']!=view.war_id:
        view.selected_engine_id=None
        view.engine_pick_rects={};view.engine_ready_state={};view.engine_ready_flash={}
    view.status = dict(panel)
    view.status_received_at = time.monotonic()
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
            _maybe_victory_scene(client, view, msg)
        return
    if not active(client):
        return
    if kind == "KCS_MERCS":
        view.mercs = {int(m["id"]): dict(m) for m in (msg.get("mercs") or []) if isinstance(m, dict) and m.get("id") is not None}
        return
    if kind == "KCS_SNAPSHOT":
        _take_status(view, msg)
        incoming_war = msg.get("war_id") or view.war_id
        if view.war_id is not None and incoming_war != view.war_id:
            view.corpses.clear()
            view.motion.clear()
        view.war_id = incoming_war
        view.your_side = msg.get("your_side") or view.your_side
        view.openings = [dict(row) for row in (msg.get("openings") or []) if isinstance(row, dict)]
        view.engines = [dict(row) for row in (msg.get("engines") or []) if isinstance(row, dict)]
        view.removed = set()
        view.eliminated = {int(pid) for pid in (msg.get("eliminated") or [])}
        view.shots = []
        view.engine_actions.clear()
        view.actor_actions.clear()
        view.actor_melee.clear()
        view.actor_hits.clear()
        view.actor_anims.clear()
        view.action_seen.clear()
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


def _maybe_victory_scene(client, view, msg) -> None:
    """Attackers won: play the throne-room victory cutscene once per war (flag USE_KCS_VICTORY_SCENE)."""
    try:
        import kcs_victory_scene as scene
    except Exception:
        return
    result = (msg.get("result") if isinstance(msg.get("result"), dict) else None) or (view.status or {}).get("result") or {}
    if not scene.enabled() or result.get("winner") != "attack":
        return
    war = result.get("war_id") or msg.get("war_id")
    seen = getattr(client, "_kcs_victory_seen", set())
    if war in seen:
        return
    seen.add(war)
    client._kcs_victory_seen = seen
    info = dict(msg.get("victory_scene") or {})
    info.setdefault("monarch_player_id", result.get("monarch_player_id"))
    scene.start(client, info, war)


def on_keydown(client, event) -> bool:
    """Select and deploy. Number keys work without turning build mode on first."""
    view = view_of(client)
    if view.guide_open and event.key == pygame.K_ESCAPE:
        _close_guide(view)
        return True
    if getattr(client, "chat_typing", False):
        return False
    if event.key == pygame.K_F11 and os.environ.get("KCS_SANDBOX_PREP") == "1":
        # sandbox preview of the victory cutscene (you on the throne)
        import kcs_victory_scene as scene
        if scene.enabled():
            me = getattr(client, "player", None) or {}
            scene.start(client, {"monarch_player_id": me.get("id")}, None)
            return True
    if active(client):
        import kcs_merc_ui
        if kcs_merc_ui.key(client, view, event):
            return True
    import kcs_hud
    if kcs_hud.enabled(client, view):
        if event.key == pygame.K_F10:
            kcs_hud.toggle(client, view, "hud-all")
            return True
        if event.key == pygame.K_TAB:
            view.details_open = not view.details_open
            view.hud_collapsed.discard("info") if hasattr(view, "hud_collapsed") else None
            kcs_hud.draw(client, view, paint=False)
            return True
    if not active(client):
        if event.key == pygame.K_F8 and not getattr(client, "dungeon", None) and getattr(client, "state", "") == "GAME":
            _send(client, "ENTER_DUNGEON", dungeon_id=DUNGEON_ID)
            note(client, "Asking to deploy to King's Castle…")
            return True
        return False
    view = view_of(client)
    if (view.status or {}).get('decor') and event.key in (pygame.K_EQUALS,pygame.K_PLUS,pygame.K_KP_PLUS,pygame.K_MINUS,pygame.K_KP_MINUS):
        change_zoom(client,-1 if event.key in (pygame.K_MINUS,pygame.K_KP_MINUS) else 1);return True
    if event.key in ENGINE_KEYS or event.key in DEFENDER_KEYS:
        _select_type(view, event.key)
        return True
    if event.key == pygame.K_TAB:
        view.details_open = not view.details_open
        return True
    if event.key == pygame.K_SPACE:
        _button(client, "strike")
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
    if quarters_on(view) and event.key in (pygame.K_q, pygame.K_e, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
        _turn_view(client, -1 if event.key in (pygame.K_q, pygame.K_LEFTBRACKET) else 1)
        return True
    return False


def on_mouse(client, pos) -> bool:
    view = view_of(client)
    point = (int(pos[0]), int(pos[1]))
    import kcs_merc_ui
    if active(client) and kcs_merc_ui.click(client, view, point):
        return True
    button = getattr(view, "throne_button", None)
    if active(client) and button is not None and button.collidepoint(point) and throne_ready(client, view):
        import kcs_victory_scene
        kcs_victory_scene.start_throne_sequence(client)   # single hook; later the throne-room entry
        return True
    import kcs_hud
    if not kcs_hud.enabled(client, view):
        return False
    if view.guide_open:
        for rect, action in list(view.guide_buttons):
            if rect.collidepoint(point):
                _guide_click(view, action)
                return True
        return True
    for rect, action in list(view.buttons):
        if rect.collidepoint(point):
            reason = getattr(view, "hud_disabled", {}).get(action)
            if reason:
                note(client, reason, error=True)
                return True
            _button(client, action)
            return True
    if blocks_world(client, point):
        return True
    if not active(client) or view.origin is None or view.screen_o is None:
        return False
    x, y = point
    game = _game(client)
    if x < 0 or y < HUD_TOP or x >= game.MAP_W or y >= game.MAP_H - HUD_BOT:
        return False
    cancel_strikes(client)   # t664u: every map click ends a running gate/engine/player strike first;
                             # the handlers below start a new one only if this click is an attack
    apply_view_quarter(view.view_quarter)
    from kings_castle_siege_map.angled_proj import pick_tile
    tx, ty = pick_tile(x, y - HUD_TOP, view.origin, view.scale, view.screen_o)
    placing = (
        view.build
        and view.your_side in ("attack", "defend")
        and (client.dungeon or {}).get("mode") != "spectator"
    )
    if (view.status or {}).get('economy'):
        picked=None
        if not placing:
            import player_interactions
            if player_interactions.on_click(client,point,1):return True
        for engine_id,rect in reversed(list(getattr(view,'engine_pick_rects',{}).items())):
            if rect.collidepoint(point):
                picked=next((row for row in view.engines if row.get('engine_id')==engine_id),None);break
        if picked is None:
            picked=next((row for row in view.engines if any(int(a)==int(tx) and int(b)==int(ty) for a,b in row.get('tiles',[]))),None)
        if picked is not None:
            # Enemy engine: walk into reach and keep striking it (defenders vs the attackers'
            # siege gear and the other way round; t652u). Same KCS_STRIKE hit code as Space.
            if (picked.get('side') in ('attack','defend') and picked.get('side')!=view.your_side
                    and view.your_side in ('attack','defend') and (client.dungeon or {}).get('mode')=='combatant'
                    and int(picked.get('hp',1) or 0)>0):
                if (view.status or {}).get('preparing'):
                    note(client,'Preparation: no fighting until the countdown ends.',error=True)
                else:
                    start_engine_attack(client,view,picked)
                    note(client,'Attacking the '+str(picked.get('engine_type','engine')).replace('_',' ')+'.')
                return True
            previous=view.selected_engine_id
            _select_engine(view,picked)
            if picked.get('engine_type') in ('ladder','siege_tower') and view.your_side=='attack':
                if previous==picked.get('engine_id'):
                    _send(client,'KCS_CLIMB',selected_engine_id=previous)
                else:note(client,'Ladder/tower selected. Click again nearby to climb up or back down.')
            return True
    if view.build and not placing:
        note(client, "Spectators do not place engines.", error=True)
        return True
    if not placing:
        import player_interactions
        if player_interactions.on_click(client, point, 1):
            return True
        if (view.status or {}).get('economy'):
            rows=(client.dungeon or {}).get('workshops',[])
            hits=[r for r in rows if getattr(view,'workshop_rects',{}).get((r['x'],r['y']),pygame.Rect(0,0,0,0)).collidepoint(point)]
            # Nearest drawn station under the cursor; else the clicked tile itself.
            picked=min(hits,key=lambda r:(pygame.Vector2(view.workshop_rects[(r['x'],r['y'])].center)-point).length_squared()) if hits else None
            picked=picked or next((r for r in rows if (r['x'],r['y'])==(int(tx),int(ty))),None)
            if picked:
                goals=client.adjacent_goals(picked['x'],picked['y'])
                if picked['kind']=='fletching':
                    # Walk to the bench; the bench panel opens on arrival.
                    view.fletch_pending=(picked['x'],picked['y']);view.fletch_open=None
                    client.walk_and_act(goals);return True
                action={'type':'FORGE','kind':picked['kind']} if picked['kind'] in ('furnace','anvil') else {'type':'GATHER','x':picked['x'],'y':picked['y']}
                client.walk_and_act(goals,action);return True
        subject = _subject_at(client, view, int(tx), int(ty))
        if subject is not None:
            if subject.get('kind')=='opening':
                view.selected_engine_id=None
                if view.your_side=='attack' and not (view.status or {}).get('preparing'):
                    start_opening_attack(client, view, subject)
            view.inspect = subject
            view.notice = subject.get("title") or view.notice
            view.error = ""
            return True
        view.inspect = None
        _queue_walk(client, int(tx), int(ty))
        return True
    if _combat_paused(client, view):
        return True
    _auto_face(view, int(tx), int(ty))
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
    game = _game(client)
    size = (game.MAP_W, game.MAP_H)
    view = view_of(client)
    client.walk_step_seconds = SIEGE_WALK_STEP
    _opening_attack_tick(client, view)
    _apply_siege_layout(client)
    size = client.screen.get_size()
    _update_motion(client, view)
    view.reload_label_rects = []
    try:
        for attempt in (0, 1):
            surf = _render(client, view, size)
            import kcs_decor_client
            kcs_decor_client.paint(surf,client,view)
            _paint_facing(surf, client, view)
            _paint_battle(surf, client, view)
            _paint_workshops(surf,client,view)
            try:
                _paint_objective_guides(surf, client, view)
            except Exception as exc:
                view.objective_guides = {"error": type(exc).__name__}
            kcs_decor_client.foreground(surf,client,view)
            try:
                # after the foreground pass so walls / towers in front never cover them (t642u)
                _paint_opening_bars(surf, client, view)
            except Exception as exc:
                view.objective_guides = {"error": type(exc).__name__}
            # macOS Cocoa displays are ARGB: any surface made in display format
            # carries per-pixel alpha, and pixels left below alpha 255 vanish
            # (black) when blitted onto the BLACK-filled screen. The frame is
            # always meant to be opaque, so pin alpha to 255 before presenting.
            _force_opaque(surf)
            # Never present a frame with unfilled (black) world chunks: record
            # what produced it, drop every cached layer and draw it again.
            if not _frame_black(client, view, surf, attempt):
                break
        _prewarm_turns(view)
    except Exception as exc:
        surf = pygame.Surface(size)
        surf.fill((24, 18, 16))
        font = pygame.font.Font(None, 24)
        missing = ensure_assets() is None
        title = "Castle art was not found." if missing else "The castle picture could not be drawn."
        detail = str(exc)[:120]
        view.render_error = repr(exc)
        surf.blit(font.render(title, True, (240, 210, 170)), (16, 28))
        surf.blit(font.render(detail, True, (210, 170, 140)), (16, 58))
        view.error = title
    _chrome(surf, view)
    try:
        _paint_throne_button(surf, client, view)
    except Exception:
        view.throne_button = None
    if view.stale or not getattr(getattr(client, "net", None), "connected", True):
        view.stale = True
        font = pygame.font.Font(None, 22)
        banner = "Connection lost. Reconnecting. Siege actions are paused."
        surf.blit(font.render(banner, True, (255, 214, 150)), (12, HUD_TOP + 8))
    client.screen.blit(surf, (0, 0))


def throne_ready(client, view) -> bool:
    """t664u: the last barrier (keep doors) is down and you are a fighting attacker."""
    if view.your_side != "attack" or (client.dungeon or {}).get("mode") != "combatant":
        return False
    if (view.status or {}).get("result"):
        return False
    row = next((r for r in view.openings if (r.get("id") or r.get("opening_id")) == "keep_doors"), None)
    return bool(row) and (row.get("state") == "destroyed" or int(row.get("hp", 1) or 0) <= 0)


def _paint_throne_button(surf, client, view):
    view.throne_button = None
    if not throne_ready(client, view):
        return
    sw = _game(client).MAP_W
    font = pygame.font.Font(None, 54)
    label = font.render("Take the Throne", True, (40, 24, 6))
    r = pygame.Rect(0, 0, label.get_width() + 80, label.get_height() + 34)
    r.midtop = (sw // 2, HUD_TOP + 54)
    pulse = (math.sin(time.time() * 3.0) + 1) / 2 if "math" in globals() else .5
    glow = pygame.Surface((r.w + 24, r.h + 24), pygame.SRCALPHA)
    pygame.draw.rect(glow, (255, 210, 90, int(60 + 80 * pulse)), glow.get_rect(), border_radius=22)
    surf.blit(glow, (r.x - 12, r.y - 12))
    pygame.draw.rect(surf, (236, 190, 84), r, border_radius=16)
    pygame.draw.rect(surf, (120, 70, 20), r, 3, border_radius=16)
    surf.blit(label, label.get_rect(center=r.center))
    view.throne_button = r


BLACK_DIAG_LIMIT = 6


def _force_opaque(surf):
    if surf.get_masks()[3]:
        surf.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MAX)
    return surf


def _frame_black(client, view, surf, attempt) -> bool:
    """True when the composed world still has (near-)pure-black 64 px cells.
    Writes a diagnostic PNG+JSON (first few per session) to KCS_BLACK_DIAG_DIR
    (default /tmp/kcs_black_diag) and logs KCS_FRAME_BLACK to stderr, then
    clears the static/prewarm caches so the retry is a clean synchronous draw."""
    av = sys.modules.get("kings_castle_siege_map.angled_view")
    if av is None or not hasattr(av, "dark_cells"):
        return False
    cells = av.dark_cells(surf)
    if not cells:
        return False
    n = getattr(view, "black_frames", 0) + 1
    view.black_frames = n
    info = dict(attempt=attempt, cells=len(cells), first=cells[:6], quarter=int(view.view_quarter or 0),
                scale=view.scale, origin=view.origin, screen_o=view.screen_o, size=surf.get_size(),
                metrics=dict(av.LAST_METRICS), blank=list(av.static_blank_events[-4:]),
                cache_keys=len(av._view_cache), prewarm_jobs=len(getattr(av, "_prewarm_jobs", {})),
                plate_worker=bool(getattr(av, "_plate_worker", None) and av._plate_worker.is_alive()),
                status_phase=(view.status or {}).get("phase"), t=time.time())
    print("KCS_FRAME_BLACK", info, file=sys.stderr, flush=True)
    if n <= BLACK_DIAG_LIMIT:
        try:
            import json
            out = Path(os.environ.get("KCS_BLACK_DIAG_DIR", "/tmp/kcs_black_diag"))
            out.mkdir(parents=True, exist_ok=True)
            stem = out / f"black_{os.getpid()}_{n:02d}_a{attempt}"
            pygame.image.save(surf, str(stem) + ".png")
            stem.with_suffix(".json").write_text(json.dumps(info, default=str, indent=1))
        except Exception:
            pass
    av._view_cache.clear()
    getattr(av, "_prewarm_jobs", {}).clear()
    return True


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
    game = _game(client)
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
        "The camera stays aligned with the castle. Fn+F7 turns your engine.",
    ),
    (
        "Preparation and camp",
        "Attackers deploy at the tent camp. Both sides have equal copper, tin, iron and coal nodes. "
        "Mine ore, smelt at furnaces, smith at anvils. The forges stand away from the mining fields. "
        "Nearby names and hover labels identify everything; F walks to a forge. "
        "Use the mouse wheel or +/- to zoom; walking never changes your zoom. Ten minutes to prepare, then no new builds.",
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
    decided = (view.status or {}).get("status") in ("resolved", "resolving")
    if decided:
        return [("guide", "Guide")]
    if active(client):
        if (getattr(client, "dungeon", None) or {}).get("mode") == "spectator":
            return [("view", "Fixed camera / F9"), ("guide", "Guide")]
        order = DEFENDER_ORDER if view.your_side == "defend" else ENGINE_ORDER
        specs = [(f"type-{kind}", f"{n} {ENGINE_SHORT[kind]}") for n, kind in enumerate(order, 1)]
        specs += [
            ("build", "Build F6"),
            ("turn", "Turn engine F7"),
            ("deploy", "Deploy F8"),
            ("view", "Fixed camera / F9"),
            ("face", "Face wall"),
            ("fire", "Fire"),
            ("pack", "Pack"),
            ("repair", "Repair"),
            ("strike", "Strike"),
            ("claim", "Claim throne"),
            ("guide", "Guide"),
        ]
        return specs
    return [
        ("guide", "Guide"),
        ("enlist-attack", "Enlist attack"),
        ("enlist-defend", "Enlist defend"),
        ("begin", "Begin"),
        ("deploy", "Deploy F8"),
        ("watch", "Watch"),
    ]


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


def _existing_engines(view):
    from kings_castle_siege_map.placement import PlacedEngine
    existing = []
    for row in view.engines:
        try:
            existing.append(PlacedEngine(
                str(row.get("engine_id")), str(row.get("engine_type")),
                int(row.get("x")), int(row.get("y")), int(row.get("rotation") or 0),
            ))
        except Exception:
            continue
    return existing


def _live_opening_cells(view):
    states = _gate_states(view)
    cells = {}
    for oid, op in view.bf.plane.openings.items():
        if states.get(oid, "intact") == "destroyed" or oid == "keep_doors":
            continue
        r = op.rect
        cells[oid] = [(x, y) for x in range(r[0], r[2] + 1) for y in range(r[1], r[3] + 1)]
    return cells


def _aim_score(view, kind, tiles, rotation, live_cells):
    """How well an engine at ``tiles`` facing ``rotation`` aims at its target."""
    import kcs_balance
    if kind not in kcs_balance.ENGINES:
        return 0.0
    fdx, fdy = kcs_balance.FACE[int(rotation) % 360]
    fx, fy = kcs_balance.front_point(tiles, rotation)
    cx = sum(t[0] for t in tiles) / len(tiles)
    cy = sum(t[1] for t in tiles) / len(tiles)
    best_cos = -1.0
    for cells in live_cells.values():
        n = min(cells, key=lambda t: (t[0]-cx)**2 + (t[1]-cy)**2)
        vx, vy = n[0]-cx, n[1]-cy
        d = (vx*vx + vy*vy) ** .5 or 1
        best_cos = max(best_cos, (vx*fdx + vy*fdy) / d - d / 400.0)
    hit = kcs_balance.shot_target(tiles, rotation, kind, live_cells)
    if hit:
        return 1000.0 + best_cos
    plane = view.bf.plane
    for n in range(1, 15):
        if plane.cell(int(fx + fdx*n), int(fy + fdy*n)) in ("#", "H", "G"):
            return 500.0 - n + best_cos
    return best_cos


def auto_rotation(view, tx, ty, existing=None, kind=None):
    """(rotation, ok): the valid facing that points at the wall/gate it attacks."""
    from kings_castle_siege_map.placement import validate_placement
    kind = kind or view.engine_type
    existing = _existing_engines(view) if existing is None else existing
    live = _live_opening_cells(view)
    best = None
    for rot in (0, 90, 180, 270):
        result = validate_placement(view.bf, kind, int(tx), int(ty), rot, existing)
        tiles = result.tiles or [(int(tx), int(ty))]
        score = _aim_score(view, kind, tiles, rot, live) + (10000 if result.ok else 0)
        if best is None or score > best[0]:
            best = (score, rot, bool(result.ok))
    return best[1], best[2]


def _auto_face(view, tx, ty, existing=None):
    """Point the preview at its target unless the player pressed Turn."""
    if getattr(view, "rotation_manual", None) == view.engine_type or view.bf is None:
        return
    try:
        view.rotation = auto_rotation(view, tx, ty, existing)[0]
    except Exception:
        pass


def valid_spots(client, view, radius=9, far=36):
    """Valid anchors near the player for the selected engine (cached per tile)."""
    from kings_castle_siege_map.placement import validate_placement
    try:
        px, py = _player_tile(client)
    except Exception:
        return [], None
    manual = getattr(view, "rotation_manual", None) == view.engine_type
    key = (int(px), int(py), view.engine_type, view.your_side, manual, int(view.rotation) if manual else None,
           tuple(sorted(str(r.get("engine_id")) for r in view.engines)), tuple(sorted(_gate_states(view).items())))
    cache = getattr(view, "_spot_cache", None)
    if cache and cache[0] == key:
        return cache[1], cache[2]
    existing = _existing_engines(view)
    rots = (int(view.rotation) % 360,) if manual else (0, 90, 180, 270)

    def ok(x, y):
        for rot in rots:
            r = validate_placement(view.bf, view.engine_type, x, y, rot, existing)
            if r.ok and (int(px), int(py)) not in (r.tiles or []):
                return True
        return False
    near = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if (dx or dy) and ok(px + dx, py + dy):
                near.append((dx*dx + dy*dy, px + dx, py + dy))
    near.sort()
    nearest = (near[0][1], near[0][2]) if near else None
    if nearest is None:
        found = []
        for dy in range(-far, far + 1, 2):
            for dx in range(-far, far + 1, 2):
                if max(abs(dx), abs(dy)) > radius and ok(px + dx, py + dy):
                    found.append((dx*dx + dy*dy, px + dx, py + dy))
        if found:
            nearest = min(found)[1:]
    spots = [(x, y) for _d, x, y in near[:40]]
    view._spot_cache = (key, spots, nearest)
    return spots, nearest


def _paint_placement_guides(surf, client, view):
    """Bouncing arrows over valid placement anchors; an edge arrow to the nearest."""
    if not view.build or view.bf is None or view.origin is None or not view.engine_type:
        return None
    if view.your_side not in ("attack", "defend"):
        return None
    spots, nearest = valid_spots(client, view)
    game = _game(client)
    area = pygame.Rect(0, HUD_TOP, game.MAP_W, game.MAP_H - HUD_TOP - HUD_BOT)
    bob = int(4 * math.sin(time.time() * 6.0))
    color, edge = (96, 232, 104), (14, 40, 16)
    # HUD panels are painted after the world, so a guide under one would be
    # drawn across its buttons. ui_regions holds the panels from the last
    # frame; keep every guide element clear of them.
    panels = [pygame.Rect(r) for r in (getattr(view, "ui_regions", None) or [])]

    def _clear(rect):
        return area.contains(rect) and not any(rect.colliderect(p) for p in panels)

    shown = 0
    hidden = 0
    for x, y in spots[:16]:
        spot = tile_to_screen(client, x, y)
        if spot is None or not area.collidepoint(spot):
            continue
        if not _clear(pygame.Rect(spot[0] - 10, spot[1] - 30, 20, 34)):
            hidden += 1
            continue
        tip = (spot[0], spot[1] - 6 + bob)
        tri = [tip, (tip[0] - 7, tip[1] - 11), (tip[0] + 7, tip[1] - 11)]
        pygame.draw.ellipse(surf, color, (spot[0] - 8, spot[1] - 3, 16, 6), 1)
        pygame.draw.polygon(surf, color, tri)
        pygame.draw.polygon(surf, edge, tri, 1)
        pygame.draw.rect(surf, color, (tip[0] - 2, tip[1] - 19, 5, 9))
        shown += 1
    pointer = None
    if not shown and nearest is not None:
        target = tile_to_screen(client, *nearest)
        me = tile_to_screen(client, *_player_tile(client))
        if target is not None and me is not None:
            vx, vy = target[0] - me[0], target[1] - me[1]
            d = max(1.0, math.hypot(vx, vy))
            ux, uy = vx / d, vy / d
            inner = area.inflate(-60, -60)
            t = min(abs((inner.right - me[0]) / ux) if ux > 0 else abs((inner.left - me[0]) / ux) if ux < 0 else 1e9,
                    abs((inner.bottom - me[1]) / uy) if uy > 0 else abs((inner.top - me[1]) / uy) if uy < 0 else 1e9,
                    d if area.collidepoint(target) else 1e9)
            t = max(30.0, min(t, d))
            # Pull the arrow back toward the player until it sits clear of panels.
            while t > 30.0 and not _clear(pygame.Rect(int(me[0] + ux * t) - 30, int(me[1] + uy * t) - 30, 60, 60)):
                t -= 8.0
            t = max(30.0, t)
            cx, cy = me[0] + ux * t, me[1] + uy * t
            tip = (int(cx + ux * 14), int(cy + uy * 14))
            back = (cx - ux * 10, cy - uy * 10)
            wing = (-uy * 10, ux * 10)
            tri = [tip, (int(back[0] + wing[0]), int(back[1] + wing[1])), (int(back[0] - wing[0]), int(back[1] - wing[1]))]
            pygame.draw.line(surf, color, (int(cx - ux * 26), int(cy - uy * 26)), (int(cx), int(cy)), 5)
            pygame.draw.polygon(surf, color, tri)
            pygame.draw.polygon(surf, edge, tri, 2)
            px, py = _player_tile(client)
            tiles = int(round(math.hypot(nearest[0] - px, nearest[1] - py)))
            label = pygame.font.Font(None, 18).render(f"Nearest valid spot: {tiles} tiles", True, (238, 250, 226))
            box = label.get_rect(center=(int(cx - ux * 44), int(cy - uy * 44 - 4)))
            box.clamp_ip(area)
            for _ in range(12):
                hit = next((p for p in panels if box.inflate(8, 4).colliderect(p)), None)
                if hit is None:
                    break
                box.top = hit.bottom + 4 if hit.centery < area.centery else box.top
                box.bottom = hit.top - 4 if hit.centery >= area.centery else box.bottom
                box.clamp_ip(area)
            pygame.draw.rect(surf, (18, 34, 18), box.inflate(8, 4), border_radius=3)
            surf.blit(label, box)
            pointer = (int(cx), int(cy))
    elif not shown:
        label = pygame.font.Font(None, 18).render("No valid spot nearby for this engine.", True, (255, 214, 190))
        box = label.get_rect(midtop=(area.centerx, area.top + 54))
        for p in panels:
            if box.inflate(8, 4).colliderect(p) and p.centery < area.centery:
                box.top = p.bottom + 6
        pygame.draw.rect(surf, (48, 22, 18), box.inflate(8, 4), border_radius=3)
        surf.blit(label, box)
    view.placement_guides = {"markers": shown, "pointer": pointer, "nearest": nearest, "spots": len(spots),
                             "under_panels": hidden, "pointer_clear": pointer is None or _clear(pygame.Rect(pointer[0] - 6, pointer[1] - 6, 12, 12))}
    return view.placement_guides

GATE_DOWN_PROMPT = "Gate down! Break the keep door"
PREP_STEPS = (
    ("mine", "Mine ore at the rocks"),
    ("smelt", "Smelt ore at the furnace"),
    ("smith", "Smith full body armour at the anvil"),
    ("build", "Build siege equipment"),
)
SIEGE_WALK_STEP = 0.16  # 25% faster than the 0.2s path step; matches keyboard walking
_STARTER_ARMOUR = {"bronze_body", "bronze_helmet", "bronze_shield", "bronze_sword", "bronze_legs"}


def _guide_panels(view, game=None):
    panels = [__import__("pygame").Rect(r) for r in (getattr(view, "ui_regions", None) or [])]
    if game is not None:
        # Fallback so arrows stay clear of the Actions strip even on the first frame.
        aw, ah = min(520, game.MAP_W - 24), 86
        panels.append(__import__("pygame").Rect((game.MAP_W - aw)//2, game.MAP_H - ah - 8, aw, ah))
    return panels


def _bag_ids(client):
    inv = (getattr(client, "player", None) or {}).get("inventory") or {}
    ids = set()
    for entry in inv.values():
        if entry and entry.get("item_id"):
            ids.add(entry["item_id"])
    return ids


def _is_ore(item):
    return str(item).endswith("_ore") or str(item) == "coal"


def _is_bar(item):
    return str(item).endswith("_bar")


def _has_smithed(client, ids):
    eq = (getattr(client, "player", None) or {}).get("equipment") or {}
    for slot in ("body", "helmet", "shield", "weapon"):
        item = eq.get(slot)
        if item and item not in _STARTER_ARMOUR and not str(item).endswith("bow"):
            return True
    return any(
        (i.endswith("_body") or i.endswith("_helmet") or i.endswith("_chainbody") or i.endswith("_shield"))
        and not i.startswith("bronze_") for i in ids
    )


def prep_guide(client, view):
    """First unfinished preparation step, or None once the player has built an engine."""
    if not (view.status or {}).get("preparing"):
        return None
    ids = _bag_ids(client)
    mined = any(_is_ore(i) for i in ids) or any(_is_bar(i) for i in ids) or _has_smithed(client, ids)
    smelted = any(_is_bar(i) for i in ids) or _has_smithed(client, ids)
    smithed = _has_smithed(client, ids)
    pid = (getattr(client, "player", None) or {}).get("id")
    built = any(e.get("player_id") == pid for e in (view.engines or []))
    done = {"mine": mined, "smelt": smelted, "smith": smithed, "build": built}
    for key, prompt in PREP_STEPS:
        if not done[key]:
            return {"step": key, "prompt": prompt, "target": _prep_target(client, view, key), "done": done}
    return None


def _prep_target(client, view, step):
    rows = (getattr(client, "dungeon", None) or {}).get("workshops") or []
    side = view.your_side
    kind = {"mine": None, "smelt": "furnace", "smith": "anvil"}.get(step)
    if step == "mine":
        row = next((r for r in rows if r.get("side") == side and str(r.get("kind") or "").endswith("_rock")), None)
    elif kind:
        row = next((r for r in rows if r.get("side") == side and r.get("kind") == kind), None)
    else:
        row = None
    if row:
        return (int(row["x"]), int(row["y"]))
    return None


def gate_down_guide(client, view):
    if (view.status or {}).get("preparing"):
        return None
    if view.your_side != "attack":
        return None
    import kcs_hud
    gate = kcs_hud._opening(view, "main_gate")
    keep = kcs_hud._opening(view, "keep_doors")
    if not kcs_hud._breached(gate) or kcs_hud._breached(keep):
        return None
    tiles = keep.get("tiles") or []
    target = (int(tiles[0][0]), int(tiles[0][1])) if tiles else None
    if target is None and view.bf is not None:
        opening = (view.bf.plane.openings or {}).get("keep_doors")
        if opening is not None:
            rect = opening.rect
            target = (int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2))
    return {"prompt": GATE_DOWN_PROMPT, "target": target, "step": "keep"}


def _paint_objective_guides(surf, client, view):
    guide = gate_down_guide(client, view) or prep_guide(client, view)
    view.objective_guides = guide
    if not guide:
        return None
    return _paint_world_arrow(surf, client, view, guide.get("target"), guide["prompt"])


def _paint_world_arrow(surf, client, view, target, prompt):
    """Reuse the placement-guide arrow, kept clear of HUD panels."""
    import pygame, math
    game = _game(client)
    area = pygame.Rect(0, HUD_TOP, game.MAP_W, game.MAP_H - HUD_TOP - HUD_BOT)
    panels = _guide_panels(view, game)
    bob = int(4 * math.sin(time.time() * 6.0))
    color, edge = (255, 214, 96), (60, 36, 8)

    def _clear(rect):
        return area.contains(rect) and not any(rect.colliderect(p) for p in panels)

    me = tile_to_screen(client, *_player_tile(client))
    spot = tile_to_screen(client, *target) if target is not None else None
    # The player's head (t652u): the arrow and its label sit above the sprite, never over the body.
    head = None
    if me is not None:
        tall = max(28, int(100 * max(.38, min(1.15, float(view.scale or 28) / 28.))))
        head = (me[0], me[1] - tall)
    px_, py_ = map(int, _player_tile(client))
    on_me = target is not None and max(abs(int(target[0]) - px_), abs(int(target[1]) - py_)) <= 1
    if (spot is not None and not on_me and area.collidepoint(spot)
            and _clear(pygame.Rect(spot[0] - 12, spot[1] - 36, 24, 40))):
        tip = (spot[0], spot[1] - 6 + bob)
        tri = [tip, (tip[0] - 8, tip[1] - 12), (tip[0] + 8, tip[1] - 12)]
        pygame.draw.polygon(surf, color, tri)
        pygame.draw.polygon(surf, edge, tri, 1)
        pygame.draw.rect(surf, color, (tip[0] - 2, tip[1] - 20, 5, 10))
        anchor = (spot[0], tip[1] - 28)
    elif head is None:
        anchor = (area.centerx, area.top + 64)
    elif on_me or spot is None:
        # Down arrow just above the head, label above the arrow.
        tip = (head[0], head[1] - 6 + bob)
        tri = [tip, (tip[0] - 9, tip[1] - 13), (tip[0] + 9, tip[1] - 13)]
        pygame.draw.rect(surf, color, (tip[0] - 2, tip[1] - 24, 5, 12))
        pygame.draw.polygon(surf, color, tri)
        pygame.draw.polygon(surf, edge, tri, 2)
        anchor = (head[0], tip[1] - 38)
    else:
        # Off-screen target: a pointer hovering above the head, aimed at it; label above that.
        vx, vy = spot[0] - head[0], spot[1] - head[1]
        d = max(1.0, math.hypot(vx, vy))
        ux, uy = vx / d, vy / d
        cx, cy = head[0] + ux * 16, head[1] - 30 + uy * 10
        tip = (int(cx + ux * 14), int(cy + uy * 14))
        back = (cx - ux * 10, cy - uy * 10)
        wing = (-uy * 10, ux * 10)
        tri = [tip, (int(back[0] + wing[0]), int(back[1] + wing[1])), (int(back[0] - wing[0]), int(back[1] - wing[1]))]
        pygame.draw.line(surf, color, (int(cx - ux * 22), int(cy - uy * 22)), (int(cx), int(cy)), 5)
        pygame.draw.polygon(surf, color, tri)
        pygame.draw.polygon(surf, edge, tri, 2)
        anchor = (head[0], head[1] - 66)
    label = pygame.font.Font(None, 20).render(prompt, True, (255, 244, 210))
    box = label.get_rect(center=(anchor[0], max(area.top + 20, anchor[1])))
    if head is not None and box.bottom > head[1] - 4 and anchor[1] < head[1]:
        box.bottom = head[1] - 4
    box.clamp_ip(area)
    for _ in range(10):
        hit = next((p for p in panels if box.inflate(8, 4).colliderect(p)), None)
        if hit is None:
            break
        box.top = hit.bottom + 4 if hit.centery < area.centery else box.top
        box.bottom = hit.top - 4 if hit.centery >= area.centery else box.bottom
        box.clamp_ip(area)
    pygame.draw.rect(surf, (42, 26, 10), box.inflate(10, 6), border_radius=3)
    pygame.draw.rect(surf, color, box.inflate(10, 6), 1, border_radius=3)
    surf.blit(label, box)
    view.objective_guides = {**(getattr(view, "objective_guides", None) or {}), "prompt_box": tuple(box), "prompt": prompt}
    return view.objective_guides


def _paint_opening_bars(surf, client, view):
    import pygame
    try:
        import kcs_balance
    except Exception:
        kcs_balance = None
    view.opening_bar_rects = {}
    if view.origin is None or view.screen_o is None:
        return
    from kings_castle_siege_map.angled_proj import project
    W, H = surf.get_size()
    for oid, title in (("main_gate", "Gate"), ("keep_doors", "Keep")):
        # openings packet first, status objectives as the fallback (either may arrive first / lack tiles)
        rows = [r for r in list(view.openings) + list((view.status or {}).get("objectives") or [])
                if (r.get("id") or r.get("opening_id")) == oid]
        if not rows:
            continue
        row = dict(rows[-1]); row.update(rows[0])
        tiles = next((r.get("tiles") for r in rows if r.get("tiles")), None) or []
        if not tiles:
            continue
        tx = sum(int(t[0]) for t in tiles) / len(tiles)
        ty = sum(int(t[1]) for t in tiles) / len(tiles)
        apply_view_quarter(view.view_quarter)
        sx, sy, _d = project(tx + 0.5, ty + 0.5, 2.8, view.origin, view.scale, view.screen_o)   # above the arch
        spot = (int(sx), int(sy + HUD_TOP))
        # on screen (or just past an edge with the gate still in view): pin the bar inside the frame
        if not (-160 < spot[0] < W + 160 and HUD_TOP - 200 < spot[1] < H + 60):
            continue
        spot = (max(48, min(W - 48, spot[0])), max(HUD_TOP + 52, min(H - 20, spot[1] + 36)))
        hp = row.get("hp")
        top = row.get("max_hp")
        if top is None and kcs_balance is not None:
            top = kcs_balance.opening_max_hp(oid)
        if row.get("state") in ("destroyed", "open", "breached") or hp == 0:
            hp, top = 0, top or 1
        if not isinstance(hp, (int, float)) or not isinstance(top, (int, float)) or top <= 0:
            continue
        bar = pygame.Rect(int(spot[0]) - 42, int(spot[1]) - 36, 84, 9)
        pygame.draw.rect(surf, (28, 16, 12), bar.inflate(2, 2), border_radius=2)
        fill = pygame.Rect(bar.x, bar.y, round(bar.w * max(0, min(1, hp / top))), bar.h)
        color = (90, 200, 70) if hp * 2 > top else (225, 186, 101) if hp > 0 else (174, 108, 94)
        pygame.draw.rect(surf, color, fill, border_radius=2)
        pygame.draw.rect(surf, (230, 210, 150), bar, 1, border_radius=2)
        label = pygame.font.Font(None, 16).render(f"{title} {int(hp)}/{int(top)}", True, (255, 244, 214))
        lrect = label.get_rect(midbottom=(bar.centerx, bar.y - 2))
        pygame.draw.rect(surf, (28, 20, 14), lrect.inflate(6, 2), border_radius=2)
        surf.blit(label, lrect)
        view.opening_bar_rects[oid] = bar


def cancel_strikes(client):
    """Stop walking-to-strike loops (gate, keep door, engine, player) so the player is free to move."""
    hadone = bool(getattr(client, "_opening_attack_id", None) or getattr(client, "_engine_attack_id", None)
                  or getattr(client, "_player_attack_target", None) is not None)
    client._opening_attack_id = None
    client._engine_attack_id = None
    client._player_attack_target = None
    client._strike_goals_for = None
    if hadone:
        client.walk_path = []
        client.walk_goal = None
    return hadone


def start_opening_attack(client, view, subject):
    oid = subject.get("opening_id") or subject.get("id")
    if not oid or subject.get("state") in ("destroyed", "open", "breached"):
        return
    client._opening_attack_id = oid
    client._engine_attack_id = None
    client._player_attack_target = None
    client._opening_attack_next = 0
    tiles = subject.get("tiles") or []
    client._opening_attack_tiles = [(int(t[0]), int(t[1])) for t in tiles]


def start_engine_attack(client, view, engine):
    client._opening_attack_id = None
    client._engine_attack_id = engine.get("engine_id")
    client._player_attack_target = None
    client._opening_attack_next = 0


def _engine_attack_tick(client, view):
    eid = getattr(client, "_engine_attack_id", None)
    if eid is None:
        return False
    row = next((r for r in view.engines if r.get("engine_id") == eid), None)
    if (row is None or int(row.get("hp", 1) or 0) <= 0 or (view.status or {}).get("preparing")
            or (client.dungeon or {}).get("mode") != "combatant"):
        client._engine_attack_id = None
        return True
    _walk_and_strike(client, [(int(t[0]), int(t[1])) for t in (row.get("tiles") or [(row["x"], row["y"])])],
                     target_engine_id=eid)
    return True


def _walk_and_strike(client, tiles, **target):
    if not tiles:
        return
    px, py = map(int, _player_tile(client))
    from content import is_bow, bow_attack_range
    import kcs_balance
    weapon = ((getattr(client, "player", None) or {}).get("equipment") or {}).get("weapon")
    reach = bow_attack_range(weapon) if is_bow(weapon) else kcs_balance.player_range()
    dist = min(max(abs(px - t[0]), abs(py - t[1])) for t in tiles)
    if dist <= reach:
        client.walk_path = []
        client.walk_goal = None
        now = time.time()
        if now >= float(getattr(client, "_opening_attack_next", 0) or 0):
            _send(client, "KCS_STRIKE", **target)
            client._opening_attack_next = now + 1.3
        return
    if client.walk_path and getattr(client, "_strike_goals_for", None) == (tuple(tiles), reach):
        return                                   # already walking there; do not re-path every frame
    goals = set()
    for tx, ty in tiles:
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                gx, gy = tx + dx, ty + dy
                try:
                    if client.tile_walkable(gx, gy):
                        goals.add((gx, gy))
                except Exception:
                    pass
    now = time.time()
    if now < float(getattr(client, "_strike_repath_at", 0) or 0):
        return
    client._strike_repath_at = now + 0.6         # an unreachable target re-paths at most twice a second
    path = client.find_path(px, py, goals) if goals else None
    if path:
        client.walk_path = path
        client.walk_goal = path[-1]
        client._strike_goals_for = (tuple(tiles), reach)
    else:
        # t660u: say so instead of silently doing nothing (e.g. the target is behind a wall/gate).
        what = "That siege engine" if target.get("target_engine_id") is not None else "That target"
        client._engine_attack_id = None
        client._opening_attack_id = None
        note(client, what + " is out of reach: there is no path to within striking distance from here.", error=True)


def _opening_attack_tick(client, view):
    if _engine_attack_tick(client, view):
        return
    oid = getattr(client, "_opening_attack_id", None)
    if not oid:
        return
    if (view.status or {}).get("preparing") or view.your_side != "attack":
        client._opening_attack_id = None
        return
    import kcs_hud
    row = kcs_hud._opening(view, oid)
    if kcs_hud._breached(row):
        client._opening_attack_id = None
        return
    tiles = [(int(t[0]), int(t[1])) for t in (row.get("tiles") or getattr(client, "_opening_attack_tiles", None) or [])]
    _walk_and_strike(client, tiles, target_opening_id=oid)


def preview_at(view, tx, ty, existing=None):
    from kings_castle_siege_map.placement import PlacedEngine, validate_placement
    if existing is None:
        existing = _existing_engines(view)
    _auto_face(view, tx, ty, existing)
    result = validate_placement(view.bf, view.engine_type, int(tx), int(ty), int(view.rotation), existing)
    if result.ok and view.engine_type not in ("ladder", "siege_tower") and hasattr(view, "_preview_px"):
        position = (int(view._preview_px), int(view._preview_py))
        if position in result.tiles:
            from kings_castle_siege_map.placement import PlacementResult
            result = PlacementResult(False, "Stand beside the footprint before building, not inside it.", result.tiles)
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


def _select_engine(view,row):
    view.selected_engine_id=row.get('engine_id')
    if row.get('engine_type') in ENGINE_ORDER+DEFENDER_ORDER:view.engine_type=row['engine_type']
    view.build=False;view.inspect=_engine_inspect(row);view.error=''
    view.notice='Selected '+(ENGINE_SHORT.get(view.engine_type,view.engine_type))+'. Fire uses it if ready and eligible, otherwise the nearest ready teammate engine.'


def engine_reload(row,now=None):
    now=time.time() if now is None else now
    remaining=max(0.,float(row.get('cooldown_until') or 0)-now)
    total=max(.001,float(row.get('reload_seconds') or 1))
    return remaining,max(0.,min(1.,1-remaining/total))


def fire_feedback(client,view):
    if not (view.status or {}).get('economy'):return None
    selected=next((r for r in view.engines if r.get('engine_id')==getattr(view,'selected_engine_id',None) and r.get('side')==view.your_side),None)
    if selected:return selected
    px,py=_player_tile(client)
    costs=((view.status or {}).get('economy') or {}).get('costs') or {}
    level=((view.status or {}).get('economy') or {}).get('engineering_level',1)
    candidates=[r for r in view.engines if r.get('side')==view.your_side and r.get('hp',1)>0 and level>=costs.get(r.get('engine_type'),{}).get('level',99) and any(max(abs(px-x),abs(py-y))<=2 for x,y in r.get('tiles',[]))]
    if not candidates:return None
    return min(candidates,key=lambda r:(engine_reload(r)[0]>0,min(max(abs(px-x),abs(py-y)) for x,y in r['tiles']),r.get('engine_id',0)))


def refresh_engine_inspect(view):
    selected=getattr(view,'selected_engine_id',None)
    if (view.inspect or {}).get('kind')!='engine':return
    eid=(view.inspect or {}).get('engine_id',selected)
    row=next((r for r in view.engines if r.get('engine_id')==eid),None)
    if row:view.inspect=_engine_inspect(row)
    else:
        view.inspect={'kind':'engine','engine_id':eid,'title':'Engine removed','lines':['Packed or no longer on the battlefield.']}


def _engine_inspect(row):
    kind = row.get("engine_type") or "engine"
    import kcs_balance
    spec = dict(kcs_balance.ENGINES.get(kind) or kcs_balance.DEFENDER_ENGINES.get(kind) or {})
    ready = row.get("cooldown_until")
    wait = ""
    if isinstance(ready, (int, float)) and ready > time.time():
        wait = f" Reloading {max(1, math.ceil(ready - time.time()))}s."
    if row.get("hp",1)<=0:wait=" Wrecked — cannot fire or repair."
    elif not wait:wait=" Ready."
    return {
        "kind": "engine",
        "title": f"{ENGINE_SHORT.get(kind, kind)} · {_face_name(row.get('rotation') or 0)}",
        "lines": [
            f"Side {row.get('side') or '?'}",
            f"HP {row.get('hp') if row.get('hp') is not None else '?'}"
            + (f"/{row.get('max_hp',spec.get('hp'))}" if row.get("max_hp",spec.get("hp")) else ""),
            f"Range {spec.get('range', '?')} · cooldown {spec.get('cooldown', '?')}s." + wait,
            "Auto-fires when reloaded. Fire: manual shot, trained teammates within 2 tiles. Pack: builder only." if row.get("damage_multiplier") is not None else "Fire / Pack while standing beside it.",
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


def _draw_battle_hud(client, view, top) -> int:
    """Compact left HUD: timer, gates/walls, selected engine. Returns bottom y."""
    if not active(client):
        return int(top)
    st = view.status or {}
    if st.get("status") in ("resolved", "resolving"):
        return int(top)
    font = pygame.font.Font(None, 16)
    lines = []
    rem = st.get("remaining")
    if isinstance(rem, int):
        lines.append(f"Siege timer {_clock(rem)}")
    elif st.get("phase"):
        lines.append(str(st.get("phase")))
    for row in (st.get("objectives") or [])[:6]:
        lines.append(f"{row.get('label')}: {row.get('state')}")
    for row in view.openings[:6]:
        oid = str(row.get("id") or row.get("opening_id") or "gate").replace("_", " ")
        hp = row.get("hp")
        state = row.get("state") or "intact"
        lines.append(f"{oid}: {state}" + (f" HP {hp}" if hp is not None else ""))
    mine = None
    me = (getattr(client, "player", None) or {}).get("id")
    for row in view.engines:
        if row.get("owner_id") == me or row.get("player_id") == me:
            if row.get("engine_type") == view.engine_type or mine is None:
                mine = row
    if mine is None and view.engines:
        mine = view.engines[0]
    if mine:
        kind = mine.get("engine_type") or "engine"
        ready = mine.get("cooldown_until")
        wait = ""
        if isinstance(ready, (int, float)) and ready > time.time():
            wait = f" · reload {max(0, int(ready - time.time()))}s"
        lines.append(
            f"Your {ENGINE_SHORT.get(kind, kind)}: HP {mine.get('hp', '?')} · "
            f"{_face_name(mine.get('rotation') or 0)}{wait}"
        )
    if not lines:
        return int(top)
    width = 270
    height = 8 + 15 * len(lines)
    box = pygame.Rect(8, int(top), width, height)
    pygame.draw.rect(client.screen, (12, 10, 8), box)
    pygame.draw.rect(client.screen, (140, 120, 70), box, 1)
    y = box.y + 4
    for line in lines:
        client.screen.blit(font.render(str(line)[:46], True, (230, 210, 170)), (box.x + 6, y))
        y += 15
    return box.bottom


def _draw_outcome(client, view) -> bool:
    """Full win/lose card when the siege is finished. Returns True when shown."""
    st = view.status or {}
    if st.get("status") not in ("resolved", "resolving"):
        return False
    result = st.get("result") or {}
    winner = result.get("winner") or st.get("winner")
    side = view.your_side or st.get("your_side")
    if winner and side:
        if side == winner:
            title, color = "Victory", (120, 200, 120)
        else:
            title, color = "Defeat", (220, 110, 90)
    else:
        title, color = "Siege finished", (220, 200, 150)
    game = _game(client)
    font = pygame.font.Font(None, 36)
    small = pygame.font.Font(None, 18)
    box = pygame.Rect(120, 120, min(640, game.MAP_W - 160), 220)
    pygame.draw.rect(client.screen, (16, 12, 10), box)
    pygame.draw.rect(client.screen, color, box, 3)
    client.screen.blit(font.render(title, True, color), (box.x + 20, box.y + 18))
    y = box.y + 64
    for line in (
        result.get("text") or st.get("text") or "",
        result.get("ownership_note") or "",
        (st.get("ownership") or {}).get("crown_line") or "",
        (st.get("ownership") or {}).get("castle_line") or "",
    ):
        if not line:
            continue
        for wrapped in _wrap(small, str(line), box.width - 40):
            client.screen.blit(small.render(wrapped, True, (236, 220, 180)), (box.x + 20, y))
            y += 18
    tip = "Esc or Guide closes help. Prepare next test siege appears below when sandbox prep is on."
    client.screen.blit(small.render(tip[:90], True, (180, 160, 120)), (box.x + 20, box.bottom - 28))
    return True


def _draw_inspect(client, view) -> None:
    info = view.inspect
    if not info:
        return
    game = _game(client)
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
    game = _game(client)
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
    note = "Mac: hold Fn with F6 build, F7 turn engine, F8 deploy, F9 fixed view. Wheel or +/- zoom."
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


def blocks_world(client, pos) -> bool:
    import kcs_hud
    return kcs_hud.blocks_world(client, pos)


def draw_overlay(client) -> None:
    """Four compact, translucent panels in battle and the pre-siege lobby."""
    import kcs_hud
    view = view_of(client)
    kcs_hud.draw(client, view)
    try:
        import kcs_merc_ui
        kcs_merc_ui.draw(client, view)
    except Exception:
        pass
    if not kcs_hud.enabled(client, view) or getattr(view, "hud_hidden", False):
        return
    if view.guide_open:
        _draw_guide(client, view)
        # Guide is modal, including its backdrop; never click through it.
        width, height = client.screen.get_size()
        view.ui_regions.append(pygame.Rect(0, 0, width, height))


def ensure_assets():
    """Point the renderer's asset folder at the external fixture tree."""
    parity = Path(__file__).resolve().parents[1] / "server" / "kcs_parity"
    dest = parity / "assets"
    src = Path(os.environ.get("KCS_VISUAL_FIXTURES", "/tmp/kcs_visual_fixtures")) / "assets"
    linked = None
    src_ok = (src / "baked_m9" / "gatehouse.png").is_file()
    if src_ok:
        try:
            if dest.is_symlink() and dest.resolve() != src.resolve():
                dest.unlink()
            if not dest.exists():
                dest.symlink_to(src, target_is_directory=True)
            linked = dest
        except Exception:
            linked = dest if dest.exists() else None
    elif dest.is_symlink() or dest.exists():
        linked = dest
    if linked is not None:
        try:
            import kcs_siege_players
            # Prefer the versioned overlay when it ships siege_players.
            players_root = src if (src / "siege_players").is_dir() else Path(linked)
            kcs_siege_players.configure(players_root)
        except Exception:
            pass
    return linked


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
    av = sys.modules.get("kings_castle_siege_map.angled_view")
    # Castle walls/gate/keep need a baked plate per quarter. Without the
    # round 3g four-angle bakes (or with decor off) stay fail-closed at 0.
    quarter = int(quarter) % 4 if getattr(av, "QUARTERS", False) else 0
    yaw = math.radians(26.0 + 90.0 * quarter)
    proj.YAW = yaw
    proj.COS_Y = math.cos(yaw)
    proj.SIN_Y = math.sin(yaw)
    proj.RIGHT = (proj.COS_Y, proj.SIN_Y)
    proj.LOOK = (proj.SIN_Y, -proj.COS_Y)


def screen_step(client, dx, dy):
    """t664u: arrow keys / move pad are screen-relative in the siege for every camera quarter.
    Picks the world step whose on-screen direction (current quarter) best matches the direction the
    same key gives in the original quarter-0 view (where screen up = world north)."""
    import math
    view = view_of(client)
    apply_view_quarter(getattr(view, "view_quarter", 0) or 0)
    import kings_castle_siege_map.angled_proj as proj
    def scr(wx, wy, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        return wx * c + wy * s, -(wx * s - wy * c) * proj.SIN_P
    tx, ty = scr(dx, dy, math.radians(26.0))
    return max(((1, 0), (-1, 0), (0, 1), (0, -1)),
               key=lambda w: scr(w[0], w[1], proj.YAW)[0] * tx + scr(w[0], w[1], proj.YAW)[1] * ty)


def pick_world_tile(client, mx, my):
    """Screen pixel to world tile under the current siege view. None off the map."""
    if not active(client):
        return None
    view = view_of(client)
    if view.origin is None or view.screen_o is None:
        return None
    game = _game(client)
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


VIEW_FROM = ("south-west", "north-west", "north-east", "south-east")


def quarters_on(view) -> bool:
    """Four-angle castle view: decor flag on and the quarter bakes present."""
    if not (view.status or {}).get("decor"):
        return False
    try:
        root = _parity_path()
        if root not in sys.path:
            sys.path.insert(0, root)
        from kings_castle_siege_map import angled_view as av
        return av.quarter_plates_ready()
    except Exception:
        return False


def _turn_view(client, step: int = 1) -> None:
    view = view_of(client)
    if quarters_on(view):
        view.view_quarter = (int(view.view_quarter or 0) + int(step)) % 4
        client.camera_yaw = 0
        view.error = ""
        view.notice = f"Camera: from the {VIEW_FROM[view.view_quarter]} (Q / E or [ / ] to rotate)."
        return
    view.view_quarter = 0
    client.camera_yaw = 0
    apply_view_quarter(0)
    _drop_view_cache()
    view.error = "Camera fixed to the castle's aligned view. Engine turning (F7) still works."
    view.notice = view.error


def _queue_walk(client, tx, ty) -> None:
    """Walk in world tiles toward the clicked tile. Arrows use the same yaw."""
    client._opening_attack_id = None      # a plain walk click cancels gate / engine strikes
    client._engine_attack_id = None
    try:
        px, py = client.player_xy()
    except Exception:
        return
    client.clear_walk()
    path = client.find_path(int(px), int(py), {(int(tx), int(ty))})
    if path is None:
        note(client, "Can't walk there. A wall or closed gate is in the way.", error=True)
        return
    client.walk_path = path
    client.walk_goal = path[-1] if path else None
    client.pending_action = None
    client._next_walk_at = 0


def _rotate(client) -> None:
    view = view_of(client)
    view.rotation = (int(view.rotation) + 90) % 360
    view.rotation_manual = view.engine_type
    view.build = True
    view.error = ""
    view.notice = f"{ENGINE_SHORT.get(view.engine_type, view.engine_type)} now faces {_face_name(view.rotation)}."


def _button(client, action: str) -> None:
    view = view_of(client)
    import kcs_hud
    if kcs_hud.toggle(client, view, action):
        return
    if kcs_hud.bag_click(client, view, action):
        return
    if kcs_hud.fletch_click(client, view, action):
        return
    if action == "details":
        view.details_open = not view.details_open
        view.hud_collapsed.discard("info")
        kcs_hud.draw(client, view, paint=False)
        return
    if action == "leave":
        client.clear_walk()
        _send(client, "LEAVE_DUNGEON")
        return
    if action == "guide":
        view.guide_open = True
        view.guide_page = 0
        view.guide_dismissed = False
        return
    if action == "build":
        view.build = not view.build
        view.error = ""
        view.notice = "Build mode on. Click a valid tile." if view.build else "Build mode off."
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
    if action in ("view", "view-right"):
        _turn_view(client, 1)
        return
    if action == "view-left":
        _turn_view(client, -1)
        return
    if action == "deploy":
        _send(client, "ENTER_DUNGEON", dungeon_id=DUNGEON_ID)
        note(client, "Asking to deploy…")
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
        extra={'selected_engine_id':view.selected_engine_id} if (view.status or {}).get('economy') and view.selected_engine_id is not None else {}
        _send(client, "KCS_ACT", engine_type=view.engine_type,**extra)
        note(client, f"Asking the {ENGINE_SHORT.get(view.engine_type, view.engine_type)} to fire…")
        return
    if action == "repair":
        if _combat_paused(client, view):
            return
        import uuid
        _send(client, "KCS_REPAIR",request_id=uuid.uuid4().hex,selected_engine_id=view.selected_engine_id)
        return
    if action == "strike":
        if _combat_paused(client, view):
            return
        extra={}
        if (view.status or {}).get('economy'):
            row=next((r for r in view.engines if r.get('engine_id')==view.selected_engine_id and r.get('side')!=view.your_side),None)
            if row:extra['target_engine_id']=row['engine_id']
            elif view.inspect and view.inspect.get('kind')=='opening':extra['target_opening_id']=view.inspect['opening_id']
        _send(client, "KCS_STRIKE",**extra)
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
    if kind == "combat_facing":
        facings = getattr(view, "combat_facings", None)
        if facings is None:
            view.combat_facings = facings = {}
        pid = msg.get("player_id")
        if msg.get("active"):
            facings[pid] = msg.get("facing")
        else:
            facings.pop(pid, None)
        for person in [getattr(client, "player", None), *(getattr(client, "players", {}) or {}).values()]:
            if person and person.get("id") == pid:
                person["combat_facing"] = msg.get("facing") if msg.get("active") else None
                person["combat_target_player_id"] = msg.get("target_id") if msg.get("active") else None
        return
    if kind == "engine" and isinstance(msg.get("engine"), dict):
        eid = msg["engine"].get("engine_id")
        if eid in view.removed:
            return
        is_new = not any(e.get("engine_id") == eid for e in view.engines)
        _upsert_engine(view, msg["engine"])
        if is_new:
            view.engine_actions[eid] = {"action": "deploy", "start": time.time(), "duration": 2.0}
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
        view.engine_actions.pop(eid, None)
        view.shots = [shot for shot in view.shots if shot.get("engine_id") != eid]
        view.engines = [row for row in view.engines if row.get("engine_id") != eid]
        view.notice = "An engine was packed up."
        return
    if kind == "rock":
        try:
            spot = (int(msg.get("x")), int(msg.get("y")))
        except (TypeError, ValueError):
            return
        depleted = getattr(view, "rock_depleted", None)
        if depleted is None:
            depleted = view.rock_depleted = {}
        if msg.get("depleted"):
            depleted[spot] = time.time() + float(msg.get("back_in") or 4.0)
        else:
            depleted.pop(spot, None)
        return
    if kind == "opening":
        before = _gate_states(view)
        _upsert_opening(view, msg)
        if _gate_states(view) != before:
            # Only a real state change (intact/damaged/destroyed) rebuilds the castle. An HP tick
            # used to rebuild it on every gate hit: a ~0.5 s freeze per swing (t652u gate crash).
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
    if kind in ("shot", "attack", "melee"):
        client._combat_active_until = time.time()+10
        action_id = msg.get("action_id")
        if action_id and action_id in view.action_seen:
            return
        if action_id:
            view.action_seen[action_id] = True
            if len(view.action_seen) > 256:
                view.action_seen.pop(next(iter(view.action_seen)))
        now = time.time()
        action = dict(msg)
        action["start"] = now
        action["duration"] = max(.2, min(4., float(msg.get("duration") or 1.05)))
        if kind == "shot":
            action["action"] = "fire"
            view.engine_actions[msg.get("engine_id")] = action
        else:
            view.actor_actions[msg.get("player_id")] = action
            view.actor_melee[msg.get("player_id")] = now + action["duration"]
            dx = float(msg.get("tx", 0)) - float(msg.get("x", 0))
            dy = float(msg.get("ty", 0)) - float(msg.get("y", 0))
            if dx or dy:
                face = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("front" if dy > 0 else "back")
                getattr(client, "_entity_facing", {})[("p", msg.get("player_id"))] = face
        impact = action["duration"] * float(action.get("release", .48)) + float(action.get("flight_seconds", 0))
        action["until"] = now + max(action["duration"], impact + (2.3 if msg.get("weapon")=="bow" else .65))
        if kind == "shot" or msg.get("weapon") == "bow":
            view.shots.append(action)
            view.shots = view.shots[-64:]
        return
    if kind == "strike_miss":
        _note_splat(client, view, msg, time.time(), 0)
        return
    if kind in ("player_hp", "projectile_contact"):
        if kind == "player_hp" and "damage" in msg:
            _note_splat(client, view, msg, time.time(), int(msg.get("damage") or 0))
        elif kind == "projectile_contact" and not msg.get("hit", True) and msg.get("player_id") is not None:
            _note_splat(client, view, msg, time.time(), 0)
        import kcs_siege_fx as fx
        if fx.record_arrow_contact(client, view, msg, time.time()):
            return
        if kind == "projectile_contact":
            return
        client._combat_active_until = time.time()+10
        pid = msg.get("player_id")
        if pid in view.eliminated:
            return
        players = getattr(client, "players", None)
        hp = msg.get("hp")
        if hp is not None:
            now = time.time()
            contact_at = now
            if msg.get("action_id"):
                for action in view.actor_actions.values():
                    if action.get("action_id") == msg["action_id"] and action.get("target_id") == pid:
                        contact_at = max(now, action["start"] + float(action.get("impact_seconds", 0)))
                        break
            # TCP can deliver wind-up and contact together after a stall. Do not
            # play recoil/death ahead of the locally presented strike/release.
            if msg.get("hit", True):
                view.actor_hits[pid] = contact_at + .36
            if pid == (getattr(client, "player", None) or {}).get("id"):
                client.player["hp"] = hp
            if isinstance(players, dict) and pid in players:
                players[pid]["hp"] = hp
            mercs = getattr(view, "mercs", None) or {}
            if pid in mercs:
                mercs[pid]["hp"] = hp
        return
    if kind == "eliminated":
        pid = msg.get("player_id")
        if pid is None:
            return
        person = (getattr(client, "players", {}) or {}).get(int(pid)) or (getattr(view, "mercs", None) or {}).get(int(pid))
        if int(pid) == (getattr(client, "player", None) or {}).get("id"):
            person = {**client.player, "x": _player_tile(client)[0], "y": _player_tile(client)[1]}
        if person:
            now = max(time.time(), view.actor_hits.get(int(pid), 0) - .36)
            # Presentation only: never add this record to players, occupancy,
            # pathfinding, targeting or server death/respawn state.
            body = {**person, "hp": 0, "_siege_dead_since": now,
                    "_siege_facing": _actor_facing(client, view, person, int(pid) == (getattr(client, "player", None) or {}).get("id"))}
            view.corpses[int(pid)] = {"person": body, "start": now, "until": now + 45.0}
            while len(view.corpses) > 64:
                view.corpses.pop(next(iter(view.corpses)))
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


def _actor_facing(client, view, person, local=False):
    explicit = getattr(view, "combat_facings", {}).get(person.get("id")) or person.get("combat_facing") or person.get("_siege_facing")
    if explicit in ("n", "s", "e", "w"):
        return explicit
    action = view.actor_actions.get(person.get("id"), {})
    if time.time() < action.get("start", 0) + action.get("duration", 0):
        dx = action.get("tx", person.get("x", 0)) - action.get("x", person.get("x", 0))
        dy = action.get("ty", person.get("y", 0)) - action.get("y", person.get("y", 0))
        if dx or dy:
            return ("e" if dx > 0 else "w") if abs(dx) > abs(dy) else ("s" if dy > 0 else "n")
    return _facing(client) if local else {"front": "s", "back": "n", "left": "w", "right": "e"}.get(
        str((getattr(client, "_entity_facing", {}) or {}).get(("p", person.get("id")), "front")), "s")


def _actor_floor_spot(client, view, position):
    spot = tile_to_screen(client, *position)
    if spot is None:
        return None
    from kings_castle_siege_map.angled_proj import project
    from kings_castle_siege_map.angled_view import WALL_H,TOWER_H
    high=bool(view.bf and view.bf.plane.cell(int(position[0]),int(position[1]))=='H')
    if high and (view.status or {}).get('economy'):
        for oid,op in view.bf.plane.openings.items():
            r=op.rect
            if r[0]<=position[0]<=r[2] and r[1]<=position[1]<=r[3] and _gate_states(view).get(oid)=='destroyed':high=False
    z=WALL_H if high else 0
    if high and (view.status or {}).get('economy'):
        if any(name.endswith('_tower') and obj.rect[0]<=position[0]<=obj.rect[2]+1 and obj.rect[1]<=position[1]<=obj.rect[3]+1 for name,obj in view.bf.plane.landmarks.items()):z=TOWER_H
    if z:
        sx, sy, _ = project(position[0]+.5, position[1]+.5, z, view.origin, view.scale, view.screen_o)
        spot = (int(sx), int(sy+HUD_TOP))
    return spot


SPLAT_LIFE = 1.3
COMBAT_BAR_SECONDS = 8.0


def _note_splat(client, view, msg, now, damage):
    """Queue a hitsplat (0 = miss) on the struck player, timed to contact."""
    pid = msg.get("player_id")
    if pid is None:
        return
    aid = msg.get("action_id")
    splats = getattr(view, "splats", None)
    if splats is None:
        splats = view.splats = []
    if aid and any(s.get("action_id") == aid for s in splats):
        return
    at = now
    for action in list(view.actor_actions.values()) + list(view.shots):
        if aid and action.get("action_id") == aid:
            at = max(now, float(action.get("start", now)) + float(action.get("impact_seconds", 0) or 0))
            if action.get("player_id") is not None:
                _combat_seen(view, action.get("player_id"), at)
            break
    splats.append({"pid": pid, "damage": int(damage), "at": at, "until": at + SPLAT_LIFE, "action_id": aid})
    view.splats = splats[-48:]
    _combat_seen(view, pid, at)


def _combat_seen(view, pid, at):
    seen = getattr(view, "combat_seen", None)
    if seen is None:
        seen = view.combat_seen = {}
    seen[pid] = max(seen.get(pid, 0), at + COMBAT_BAR_SECONDS)


def _actor_head(client, view, person, local=False):
    pid = person.get("id")
    position = view.motion.get(pid, {}).get("draw", (person.get("x", 0), person.get("y", 0)))
    spot = _actor_floor_spot(client, view, position)
    if spot is None:
        return None
    scale = max(0.38, min(1.15, view.scale / 28.0))
    return spot[0], spot[1] - int(96 * scale)


def _paint_combat_overlays(surf, client, view):
    """Main-game HP bar over each fighter in combat, plus hitsplats (0 = miss)."""
    now = time.time()
    me = (getattr(client, "player", None) or {}).get("id")
    seen = getattr(view, "combat_seen", {}) or {}
    for action in view.actor_actions.values():
        if now < float(action.get("start", 0)) + float(action.get("duration", 0)) + 1:
            for key in ("player_id", "target_id"):
                if action.get(key) is not None:
                    _combat_seen(view, action[key], now)
    if getattr(client, "_player_fight", None) and me is not None:
        _combat_seen(view, me, now)
        opp = (client._player_fight or {}).get("opponent_id")
        if opp is not None:
            _combat_seen(view, opp, now)
    seen = getattr(view, "combat_seen", {}) or {}
    people = {}
    local = getattr(client, "player", None) or {}
    if local and me is not None:
        tx, ty = _player_tile(client)
        people[me] = ({**local, "x": tx, "y": ty}, True)
    for person in (getattr(client, "players", None) or {}).values():
        if person.get("id") != me:
            people[person.get("id")] = (person, False)
    for person in (getattr(view, "mercs", None) or {}).values():   # t656u: mercenary HP bars + hitsplats
        if int(person.get("hp", 1) or 0) > 0:
            people[person.get("id")] = (person, False)
    view.splats = [s for s in (getattr(view, "splats", None) or []) if s["until"] > now]
    drawn = {"bars": 0, "splats": 0}
    old_screen = getattr(client, "screen", None)
    client.screen = surf
    try:
        for pid, (person, is_local) in people.items():
            if pid in view.eliminated:
                continue
            show = seen.get(pid, 0) > now
            mine = [s for s in view.splats if s["pid"] == pid and s["at"] <= now]
            if not show and not mine:
                continue
            head = _actor_head(client, view, person, is_local)
            if head is None:
                continue
            hp = person.get("hp"); top = person.get("max_hp") or (local.get("max_hp") if is_local else None)
            if show and isinstance(hp, (int, float)) and isinstance(top, (int, float)) and top > 0:
                if hasattr(client, "draw_hp_bar"):
                    client.draw_hp_bar(head[0], head[1] - 10, hp, top)
                else:
                    bar = pygame.Rect(head[0]-19, head[1]-10, 38, 7)
                    pygame.draw.rect(surf, (36, 14, 16), bar)
                    pygame.draw.rect(surf, (90, 200, 70), (bar.x, bar.y, round(bar.w*max(0, min(1, hp/top))), bar.h))
                drawn["bars"] += 1
            for slot, splat in enumerate(mine[-3:]):
                age = now - splat["at"]
                lift = int(min(1.0, age / SPLAT_LIFE) * 30) + slot * 22
                dmg = splat["damage"]
                text, kind, color = (str(dmg), "hit_red", (220, 40, 40)) if dmg > 0 else ("0", "hit_zero", (150, 150, 145))
                cx, cy = head[0], head[1] + 18 - lift
                if hasattr(client, "draw_hit_star"):
                    client.draw_hit_star(cx, cy, text, color, kind=kind)
                else:
                    pygame.draw.circle(surf, color, (cx, cy), 12)
                    label = pygame.font.Font(None, 20).render(text, True, (255, 255, 255))
                    surf.blit(label, label.get_rect(center=(cx, cy)))
                drawn["splats"] += 1
    finally:
        client.screen = old_screen
    view.combat_overlay_counts = drawn
    return drawn


SIEGE_WALK_SPEED = 1.25      # siege walk is ~25% faster; the walk cycle steps faster to match (t627u)
_HD_FACING = {"s": "front", "n": "back", "e": 1, "w": -1}


def _baked_set_matches(equipment, tier):
    """Baked siege strips have the set's own helmet painted in, so use them only for helmet + body of
    one tier; anything else (mixed helmet, no helmet, no armour) goes through the HD paper doll."""
    if not tier:
        return False
    try:
        import helmet_overlay
        return helmet_overlay.helmet_tier(equipment) == tier
    except Exception:
        return True


def _actor_appearance(client, person, local):
    if local:
        p = getattr(client, "player", None) or {}
        return p.get("appearance") or person.get("appearance")
    return person.get("appearance")


_HD_SCRATCH = {}
_SHIELD_FIT = {}


def _upper_fit(alpha, foot):
    """(torso centre x, head top y) relative to the feet, from an alpha array (x, y)."""
    import numpy as np
    xs, ys = np.nonzero(alpha > 96)
    if not len(ys):
        return None
    top, bot = ys.min(), ys.max()
    H = bot - top
    band = (ys > top + 0.20 * H) & (ys < top + 0.55 * H)
    return float(np.median(xs[band])) - foot[0], float(top) - foot[1], float(H)


def _hd_shield(dest, kind, equipment, shield, anim, facing, progress, foot_screen, scale, tile):
    """Siege shield on the painted HD figure (David t644u). The shield strips are rendered for the baked siege
    body, so the cell is shifted by how far this painted pose's torso / head sits from the baked body's in
    the same frame. In the melee swing the baked strip hides the shield behind the sword arm (holdout);
    the HD figure keeps it up, so a hidden frame uses the guard (idle) shield instead."""
    import kcs_siege_players as actors
    fam = actors.weapon_family(equipment)
    if fam not in ("sword", "axe"):
        return
    prog = max(0.0, min(1.0, progress))
    # east: the strips carry the shield on the far arm (only a sliver shows). Use the west cell mirrored, so
    # the shield is on the near side and reads clearly (David t646u).
    want = facing
    facing = "w" if want == "e" else facing
    got = actors.shield_cell(kind, fam, shield, anim, facing, prog, scale)
    if got is None:
        return
    cell, foot, frame, n = got
    use_anim, use_frame = anim, frame
    if anim == "melee":
        counts = _SHIELD_FIT.get(("n", kind, fam, shield, facing, round(scale, 3)))
        if counts is None:
            counts = []
            for i in range(n):
                c = actors.shield_cell(kind, fam, shield, "melee", facing, 0.0, scale, frame=i)
                counts.append(pygame.mask.from_surface(c[0], 40).count() if c else 0)
            _SHIELD_FIT[("n", kind, fam, shield, facing, round(scale, 3))] = counts
        if counts and counts[frame] < 0.45 * max(counts):
            # this frame's shield is held out behind the baked sword arm; keep the raised guard frame instead
            use_frame = int(max(range(n), key=lambda i: counts[i]))
            c = actors.shield_cell(kind, fam, shield, "melee", facing, 0.0, scale, frame=use_frame)
            if c is not None:
                cell, foot = c[0], c[1]
    scratch = _HD_SCRATCH.pop("last", None)
    dx = dy = 0.0
    tier = actors.full_tier(equipment) or "bronze"
    body = actors.frame_surface(kind, tier, use_anim, facing, use_frame, fam)
    if scratch is not None and body is not None:
        hd = _upper_fit(pygame.surfarray.array_alpha(scratch), (128, 220))
        bk = _upper_fit(pygame.surfarray.array_alpha(body), (72, 124))
        if hd and bk:
            k = scale            # baked body cell is at scale 1
            dx = hd[0] - bk[0] * k if want != "e" else hd[0] + bk[0] * k   # east: baked west body, mirrored
            dy = hd[1] - bk[1] * k
            lim = 0.12 * cell.get_width()
            dx, dy = max(-lim, min(lim, dx)), max(-lim, min(lim, dy))
    if want == "e":
        cell = pygame.transform.flip(cell, True, False)
        foot = (cell.get_width() - foot[0], foot[1])
    dest.blit(cell, (int(foot_screen[0] - foot[0] + dx), int(foot_screen[1] - foot[1] + dy)))


def _hd_actor_draw(dest, *, foot_screen, kind, equipment, appearance, facing, anim, progress, started,
                   duration, now, scale, tool=None):
    """One siege actor through player_hd_client.draw_player (same feet anchor as the baked strips:
    baked cells are 1x-canvas sized, so tile = 40 px * scale)."""
    import player_hd_client as phd
    tile = max(12, int(round(40 * scale)))
    kw = {}
    if anim in ("melee", "ranged"):
        kw["progress"] = max(0.0, min(1.0, progress))
    elif anim == "hit":
        kw["hit_t"] = max(0.0, now - started)
    elif anim == "death":
        kw["death_t"] = max(0.0, now - started)
    prev = phd._WALK_SPEED
    phd.set_walk_speed_scale(SIEGE_WALK_SPEED)
    try:
        ok = bool(phd.draw_player(
            dest, kind, appearance or phd.get_default_appearance(kind), int(foot_screen[0]), int(foot_screen[1]),
            tile, now, anim=anim if anim not in ("hit", "death") else "idle", facing=_HD_FACING.get(facing, "front"),
            equipment=equipment, tool=tool, **kw))
        if ok and (equipment or {}).get("shield"):
            # same figure on a scratch canvas, so the shield can be fitted to this painted pose
            scratch = pygame.Surface((256, 256), pygame.SRCALPHA)
            phd.draw_player(scratch, kind, appearance or phd.get_default_appearance(kind), 128, 220, tile, now,
                            anim=anim if anim not in ("hit", "death") else "idle",
                            facing=_HD_FACING.get(facing, "front"), equipment=equipment, tool=tool, **kw)
            _HD_SCRATCH["last"] = scratch
    finally:
        phd.set_walk_speed_scale(prev)
    shield = (equipment or {}).get("shield")
    if ok and shield and anim in ("idle", "walk", "melee", "hit", "death"):
        try:
            _hd_shield(dest, kind, equipment, shield, anim, facing, progress, foot_screen, scale, tile)
        except Exception:
            pass
    return ok


_RINGS = {}


def _team_ring(dest, foot, scale, colour):
    """Semi-transparent team ellipse on the ground under an actor (David t650u)."""
    w, h = max(12, int(46 * scale)), max(5, int(17 * scale))
    key = (w, h, colour)
    ring = _RINGS.get(key)
    if ring is None:
        ring = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(ring, (*colour, 70), ring.get_rect())
        pygame.draw.ellipse(ring, (*colour, 190), ring.get_rect(), max(1, int(2 * scale + .5)))
        if len(_RINGS) > 64:
            _RINGS.clear()
        _RINGS[key] = ring
    dest.blit(ring, (int(foot[0] - w / 2), int(foot[1] - h / 2)))


def _ringed(draw, colour):
    """Wrap an actor draw so the team ring goes down first, under the sprite (also on occlusion scratch)."""
    if colour is None:
        return draw

    def go(dest, **kw):
        try:
            _team_ring(dest, kw["foot_screen"], float(kw.get("scale") or 1.0), colour)
        except Exception:
            pass
        return draw(dest, **kw)
    return go


def _ring_colour(client, view, person, local):
    mine = view.your_side or (view.status or {}).get("your_side")
    side = mine if local else person.get("kcs_side")
    if side not in ("attack", "defend") or mine not in ("attack", "defend"):
        return None
    return (70, 140, 255) if side == mine else (235, 60, 50)


def _paint_actor(surf, client, view, person, *, local=False) -> bool:
    """Draw a full-set actor, using authoritative action start/weapon/target."""
    try:
        import kcs_siege_players as actors
    except Exception:
        return False
    equipment = person.get("equipment") or {}
    if local:
        equipment = (getattr(client, "player", None) or {}).get("equipment") or equipment
    tier = actors.full_tier(equipment)
    gender = str(person.get("gender") or (getattr(client, "player", None) or {}).get("gender") or "male").lower()
    kind = "female" if gender.startswith("f") else "male"
    facing = _actor_facing(client, view, person, local)
    pid = person.get("id")
    now = time.time()
    moving = now < view.motion.get(pid, {}).get("moving_until", 0)
    action = view.actor_actions.get(pid, {})
    weapon = action.get("weapon") if now < action.get("start", 0) + action.get("duration", 0) else None
    weapon = weapon or actors.weapon_family(equipment)
    pending_contact = now < person.get("_siege_dead_since", 0)
    dead = not pending_contact and (pid in view.eliminated or int(person.get("hp", 1)) <= 0)
    hit_until = view.actor_hits.get(pid, 0)
    previous, started = view.actor_anims.get(pid, (None, now))
    if dead:
        anim, duration = "death", actors.DEATH_S
        started = person.get("_siege_dead_since", started if previous == "death" else now)
    elif hit_until - actors.HIT_S <= now < hit_until:
        anim, duration, started = "hit", actors.HIT_S, hit_until - actors.HIT_S
    elif now < action.get("start", 0) + action.get("duration", 0):
        anim = "ranged" if weapon == "bow" else "melee"
        duration, started = action["duration"], action["start"]
    else:
        anim, duration = ("walk", 1.0/(actors.WALK_HZ*SIEGE_WALK_SPEED)) if moving else ("idle", .8)
        if previous != anim:
            started = now
    view.actor_anims[pid] = (anim, started)
    elapsed = max(0, now - started) / max(.01, duration)
    progress = elapsed % 1.0 if anim in ("walk", "idle") else min(1., elapsed)
    position = view.motion.get(pid, {}).get("draw", (person.get("x", 0), person.get("y", 0)))
    spot = _actor_floor_spot(client, view, position)
    if spot is None:
        return False
    directions = ("n", "e", "s", "w")
    facing = directions[(directions.index(facing) - int(view.view_quarter)) % 4]
    import kcs_decor_client
    gather = person.get("gathering") if not local else ((getattr(client, "player", None) or {}).get("gathering") or person.get("gathering"))
    mining = (isinstance(gather, dict) and gather.get("skill") == "mining" and anim in ("idle", "walk"))
    scale = max(0.38, min(1.15, view.scale / 28.0))
    ring = None if dead else _ring_colour(client, view, person, local)
    if mining or not _baked_set_matches(equipment, tier):
        # HD paper-doll path (player_hd_client): mixed-tier helmets, body-only, no armour, mining.
        return kcs_decor_client.actor_blit(
            surf, view, position, spot, _ringed(_hd_actor_draw, ring), kind=kind, equipment=equipment,
            appearance=_actor_appearance(client, person, local), facing=facing,
            anim="mine" if mining else anim, progress=progress, started=started, duration=duration,
            now=now, scale=scale, tool=(gather or {}).get("tool") if mining else None)
    return kcs_decor_client.actor_blit(
        surf,view,position,spot,_ringed(actors.actor_blit, ring),kind=kind, tier=tier, facing=facing, anim=anim, progress=progress,
        scale=max(0.38, min(1.15, view.scale / 28.0)), weapon=weapon, shield=equipment.get("shield"),
    )


def _paint_battle(surf, client, view) -> None:
    """Marks for nearby fighters and a short line for a shot. Not a new renderer."""
    now = time.time()
    import kcs_siege_fx as fx
    fx.present_contacts(client, view, now)
    view.shots = [shot for shot in view.shots if shot.get("until", 0) > now]
    view.marks = [mark for mark in view.marks if mark.get("until", 0) > now]
    me = (getattr(client, "player", None) or {}).get("id")
    font = pygame.font.Font(None, 16)
    import kcs_siege_fx as fx
    root = ensure_assets()
    for pid, corpse in list(view.corpses.items()):
        if corpse["until"] <= now:
            del view.corpses[pid]
            continue
        if now - corpse["start"] < 1.2:
            _paint_actor(surf, client, view, corpse["person"], local=False)
        elif root:
            spot = _actor_floor_spot(client, view, (corpse["person"].get("x", 0), corpse["person"].get("y", 0)))
            if spot:
                fade = min(1., (corpse["until"]-now)/8.)
                fx.decal_blit(surf, root, "bones", 0, spot, view.scale, alpha=255*fade, rotation=((pid%4-int(view.view_quarter))*90)%360)
    # Local player: replace the angled_view placeholder billboard with gear art when available.
    local = getattr(client, "player", None) or {}
    if local and me not in view.eliminated:
        _paint_actor(surf, client, view, {**local, "x": _player_tile(client)[0], "y": _player_tile(client)[1]}, local=True)
    for person in (getattr(client, "players", None) or {}).values():
        if person.get("id") == me or person.get("id") in view.eliminated:
            continue
        if _paint_actor(surf, client, view, person):
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
    for person in list((getattr(view, "mercs", None) or {}).values()):
        if person.get("id") in view.eliminated or int(person.get("hp", 1)) <= 0 and person.get("id") not in view.corpses:
            continue
        _paint_actor(surf, client, view, person)
    import kcs_siege_fx as fx
    root = ensure_assets()
    def position(pid):
        person = (getattr(client,"player",{}) or {}) if pid==me else (getattr(client,"players",{}) or {}).get(pid)
        if person is None:return None
        return view.motion.get(pid,{}).get("draw",(person.get("x",0),person.get("y",0)))
    fx.draw_player_arrows(surf, view, now, lambda x,y:_actor_floor_spot(client,view,(x,y)), position, max(.38,min(1.15,view.scale/28.)))
    for shot in view.shots:
        if shot.get("weapon")=="bow" and shot.get("target_id") is not None:
            continue
        start = _actor_floor_spot(client, view, (shot.get("x", 0), shot.get("y", 0)))
        end = _actor_floor_spot(client, view, (shot.get("tx", 0), shot.get("ty", 0)))
        if start is None or end is None:
            continue
        age = now - shot["start"]
        release = shot["duration"] * float(shot.get("release", .5))
        flight = float(shot.get("flight_seconds", 0))
        family = shot.get("engine_type") or shot.get("weapon") or "bow"
        if flight > 0 and release <= age < release + flight:
            height = {"trebuchet": 58, "ballista": 25, "cauldron": 36}.get(family, 36)
            start = (start[0], start[1] - height * view.scale/28.)
            if family == "bow": end = (end[0], end[1] - 30*view.scale/28.)
            fx.projectile(surf, start, end, (age-release)/flight, family, view.scale/28.)
        impact_age = age-release-flight
        if root and family != "bow" and shot.get("target_kind") != "player" and 0 <= impact_age < .65:
            effect = "oil_impact" if family == "cauldron" else "impact"
            fx.decal_blit(surf, root, effect, impact_age/.65, end, view.scale, alpha=255*(1-impact_age/.65))
    for mark in view.marks:
        spot = tile_to_screen(client, mark.get("x", 0), mark.get("y", 0))
        if spot is None:
            continue
        pygame.draw.circle(surf, mark.get("color") or (240, 180, 80), spot, 10, 2)
    try:
        _paint_combat_overlays(surf, client, view)
    except Exception:
        pass


def _parity_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "server" / "kcs_parity")


def _load_renderer():
    linked = ensure_assets()
    root = _parity_path()
    if root not in sys.path:
        sys.path.insert(0, root)
    from kings_castle_siege_map import angled_view as av
    if linked is not None and av.BAKED_DIR != Path(linked) / "baked_m9":
        av.BAKED_DIR = Path(linked) / "baked_m9"
        av._baked.clear()
        av.invalidate_static_visuals()
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
    if raw in (1, "e", "right"):
        return "e"
    if raw in (-1, "w", "left"):
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


def manual_scale(view,size):
    base=min(28.,(size[1]-HUD_TOP-HUD_BOT)/686.*28.)
    return round(max(6.,min(36.,base*getattr(view,'zoom',1.))),1)

def _legacy_scale(view,size,px,py):
    """Flags-off behaviour kept exactly: attackers far from the gate auto-zoom out."""
    scale = min(28.0, (size[1] - HUD_TOP - HUD_BOT) / 686.0 * 28.0)
    gate = view.bf.plane.openings["main_gate"].rect
    gx, gy = (gate[0] + gate[2]) / 2, gate[3]
    from kings_castle_siege_map import angled_proj as proj
    dx, dy = gx - px, gy - py
    if view.your_side == "attack" and max(abs(dx), abs(dy)) > 22:
        depth = abs(dx * proj.SIN_Y - dy * proj.COS_Y) * proj.SIN_P
        across = abs(dx * proj.COS_Y + dy * proj.SIN_Y)
        scale = max(7.0, min(scale, (size[1] - HUD_TOP - HUD_BOT) * .48 / max(1, depth), size[0] * .42 / max(1, across)))
    return round(scale, 1)

def change_zoom(client,steps):
    view=view_of(client);view.zoom=max(.15,min(6.,getattr(view,'zoom',1.)*(1.15**float(steps))))
    base=min(28.,(client.screen.get_height()-HUD_TOP-HUD_BOT)/686.*28.)
    view.zoom=max(6./base,min(36./base,view.zoom));view.notice=f"Zoom {manual_scale(view,client.screen.get_size()):g} / wheel or +/-"

SALLY_HOLD_S = 1.6


def _note_sally(client, view):
    """Open the main gate while a defender (player or defender mercenary) is in or right beside the
    gate passage, i.e. leaving or re-entering the castle; it closes SALLY_HOLD_S after they are clear."""
    try:
        rect = view.bf.plane.openings["main_gate"].rect
    except Exception:
        return
    x0, y0, x1, y1 = rect[0] - 1, rect[1] - 2, rect[2] + 1, rect[3] + 2
    spots = []
    if view.your_side == "defend":
        spots.append(_player_tile(client))
    me = (getattr(client, "player", None) or {}).get("id")
    for row in list((getattr(client, "players", None) or {}).values()) + list((getattr(view, "mercs", None) or {}).values()):
        if row.get("id") != me and row.get("kcs_side") == "defend" and int(row.get("hp", 1) or 0) > 0:
            spots.append(view.motion.get(row.get("id"), {}).get("draw", (row.get("x"), row.get("y"))))
    for sx, sy in spots:
        try:
            if x0 <= float(sx) <= x1 + 1 and y0 <= float(sy) <= y1 + 1:
                view.gate_sally_until = time.time() + SALLY_HOLD_S
                return
        except (TypeError, ValueError):
            continue


def _render(client, view, size):
    linked, camera_look, render_world, build_battlefield, _placed = _load_renderer()
    if linked is None:
        raise RuntimeError("Set KCS_VISUAL_FIXTURES to the extracted siege art.")
    states = _gate_states(view)
    key = tuple(sorted(states.items()))
    large = bool((view.status or {}).get('decor'))
    bkey = (key, True) if large else key  # flag-off key unchanged
    if view.bf is None or view.bf_key != bkey:
        view.bf = build_battlefield(states or None, large=True) if large else build_battlefield(states or None)
        view.bf_key = bkey
    quarters = quarters_on(view)
    if not quarters:
        view.view_quarter = 0  # clamp even a stale saved/programmatic yaw
    _note_sally(client, view)
    _av = sys.modules.get("kings_castle_siege_map.angled_view")
    if _av is not None:
        import kcs_decor_client
        _av.QUARTERS = quarters
        _av.GATE_GRILLE = kcs_decor_client.gate_state(view) if quarters else 0
    apply_view_quarter(view.view_quarter)
    client.camera_yaw = 0
    px, py = _player_tile(client)
    motion = view.motion.get((getattr(client, "player", None) or {}).get("id"))
    if motion:
        px, py = motion["draw"]
    scale=manual_scale(view,size) if (view.status or {}).get('decor') else _legacy_scale(view,size,px,py)
    world_size = (size[0], size[1] - HUD_TOP - HUD_BOT)
    origin, screen_o = camera_look((px, py), world_size, scale)
    view.origin = origin
    view.screen_o = screen_o
    view.scale = scale
    import kcs_decor_client
    cr=getattr(view.bf,"interior_rect",(0,0,-1,-1))
    inside=bool((view.status or {}).get('decor') and cr[0]<=px<=cr[2] and cr[1]<=py<=cr[3] and view.bf.plane.cell(int(px),int(py))!='H')
    view.cutaway=(inside,inside and kcs_decor_client._ray_hits(px+.5,py+.5,view.bf.keep_rect))
    started = time.perf_counter()
    # Skip the stock billboard when full-set sword art will paint the local actor.
    draw_player = True
    try:
        import kcs_siege_players as actors
        eq = (getattr(client, "player", None) or {}).get("equipment") or {}
        import player_hd_client  # noqa: F401  (HD fallback paints every loadout now)
        draw_player = False
    except Exception:
        draw_player = True
    # Engines are omitted here and painted afterwards so their nose can rotate.
    # The reused preview renderer reserves its own 58/56px stock caption bands.
    # Ask for a larger surface, then take ONLY its world area. That gives the
    # world the exact same size/origin as picking, actors and build previews.
    stock_top, stock_bottom = 58, 56
    surf = render_world(
        view.bf, (px, py) if not draw_player else (int(px), int(py)), [], "King's Castle", "",
        size=(size[0], size[1] + stock_top + stock_bottom), tile_px=scale, facing=_facing(client),
        gate_states=states or None, markers=False,
        view_quarter=int(view.view_quarter or 0),
        draw_player=draw_player, draw_minimap=False,cutaway=view.cutaway,
    )
    view.last_ms = (time.perf_counter() - started) * 1000.0
    view.prewarm_args = ((px, py) if not draw_player else (int(px), int(py)), states or view.bf.gate_states, scale, tuple(size), tuple(view.cutaway)) if quarters else None
    return surf.subsurface(pygame.Rect(0, stock_top, *size)).copy()


PREWARM_BUDGET_MS = 3.0


def _prewarm_turns(view) -> None:
    """Between frames, build the neighbouring camera angles a slice at a time
    (static layer bands + plate/prop decode), so Q/E is a cache hit instead of
    a one-off 80-160 ms rebuild. Decor + four-angle art only; never raises."""
    args = getattr(view, 'prewarm_args', None)
    if not args or view.bf is None:
        return
    started = time.perf_counter()
    try:
        from kings_castle_siege_map import angled_view as av
        import kcs_decor_client
        deadline = started + PREWARM_BUDGET_MS / 1000.0
        player, states, scale, size, cutaway = args
        cur = int(view.view_quarter or 0)
        ready = []
        for q in ((cur + 1) % 4, (cur - 1) % 4, (cur + 2) % 4):
            with av.quarter_context(q):
                ok = av.prewarm_static_step(view.bf, player, states, scale, size, cutaway, deadline)
                ok = kcs_decor_client.prewarm_assets(view, deadline) and ok
            ready.append(ok)
            if time.perf_counter() >= deadline:
                break
        view.prewarm_done = len(ready) == 3 and all(ready)
    except Exception as exc:  # prewarm is an optimisation only
        if getattr(view, 'prewarm_error', None) != repr(exc):
            print('KCS_PREWARM_ERROR', repr(exc), file=sys.stderr, flush=True)
        view.prewarm_error = repr(exc)
    finally:
        apply_view_quarter(view.view_quarter)
        view.prewarm_ms = (time.perf_counter() - started) * 1000.0


def _engine_fire_frame(view, engine_id) -> int | None:
    action = view.engine_actions.get(engine_id, {})
    age = time.time() - action.get("start", 0)
    duration = action.get("duration", 0)
    if action.get("action") == "fire" and 0 <= age < duration:
        return min(3, int(age/duration*4))
    return None


def _paint_engine_hp(surf,view,row,x,y):
    """Small non-interactive world health bar, readable even at far zoom."""
    if not (view.status or {}).get('economy'):return None
    hp,maximum=row.get('hp'),row.get('max_hp')
    if not isinstance(hp,(int,float)) or not isinstance(maximum,(int,float)) or maximum<=0:return None
    bar=pygame.Rect(int(x)-26,int(y)+7,52,6)
    pygame.draw.rect(surf,(33,25,18),bar)
    amount=max(0,min(1,hp/maximum))
    color=(138,181,85) if row.get('side')==view.your_side else (190,86,69)
    if amount:pygame.draw.rect(surf,color,(bar.x+1,bar.y+1,round((bar.w-2)*amount),bar.h-2))
    pygame.draw.rect(surf,(192,157,91),bar,1)
    label=pygame.font.Font(None,17).render(f'{int(hp)}/{int(maximum)} HP',True,(248,221,168))
    back=label.get_rect(midtop=(int(x),bar.bottom+2));pygame.draw.rect(surf,(34,27,18),back.inflate(6,2),border_radius=2);surf.blit(label,back)
    return bar


def _paint_engine_reload(surf,view,row,point):
    if not (view.status or {}).get('economy') or row.get('hp',1)<=0:return None
    engine_id=row.get('engine_id');remaining,progress=engine_reload(row)
    ready=remaining<=0
    if ready and getattr(view,'engine_ready_state',{}).get(engine_id) is not True:
        view.engine_ready_flash[engine_id]=time.monotonic()+.65
    view.engine_ready_state[engine_id]=ready
    flash=view.engine_ready_flash.get(engine_id,0)>time.monotonic()
    x,y=map(int,point);bar=pygame.Rect(x-26,max(HUD_TOP+3,y),52,5)
    pygame.draw.rect(surf,(36,28,18),bar)
    if progress:pygame.draw.rect(surf,(255,234,150) if flash else (121,182,102) if ready else (192,157,84),(bar.x+1,bar.y+1,round(50*progress),3))
    pygame.draw.rect(surf,(255,228,138) if flash else (164,137,83),bar,1)
    text='READY' if ready else f'{remaining:.1f}s'
    font=pygame.font.Font(None,17);label=font.render(text,True,(255,232,170))
    back=label.get_rect(midbottom=(x,bar.y-1))
    if (view.status or {}).get('decor'):
        # Keep READY clear of map labels (stair 'Steps' tags) painted this frame.
        for other in getattr(view,'map_label_rects',[]):
            if back.inflate(6,2).colliderect(other):back.bottom=other.top-3
        view.reload_label_rects=getattr(view,'reload_label_rects',[])+[back.inflate(6,2)]
    pygame.draw.rect(surf,(34,27,18),back.inflate(6,2),border_radius=2);surf.blit(label,back)
    return bar


def _paint_facing(surf, client, view) -> None:
    import kcs_balance
    from kings_castle_siege_map.angled_proj import project
    from kings_castle_siege_map import angled_view as av
    from kings_castle_siege_map.angled_view import blit_baked
    from kings_castle_siege_map.placement import PlacedEngine, validate_placement

    view.engine_pick_rects={}
    view.engine_visibility={}
    def _mark(tiles, rotation, color, sprite, row=None):
        tiles = [(int(t[0]), int(t[1])) for t in tiles]
        if not tiles:
            return
        cx = sum(t[0] for t in tiles) / len(tiles) + 0.5
        cy = sum(t[1] for t in tiles) / len(tiles) + 0.5
        fx, fy = kcs_balance.front_point(tiles, rotation)
        z = av.WALL_H if sprite in ("ballista", "cauldron") else 0
        scx, scy, _z = project(cx, cy, z, view.origin, view.scale, view.screen_o)
        sfx, sfy, _z = project(fx + 0.5, fy + 0.5, z, view.origin, view.scale, view.screen_o)
        scx, scy = int(scx), int(scy + HUD_TOP)
        sfx, sfy = int(sfx), int(sfy + HUD_TOP)
        state = "intact"
        fire = None
        if row is not None:
            fire = _engine_fire_frame(view, row.get("engine_id"))
            hp = row.get("hp")
            max_hp = row.get("max_hp")
            if isinstance(hp, (int, float)) and hp <= 0:
                state = "destroyed"
            elif fire is not None:
                state = f"fire_{int(fire):02d}"
            elif isinstance(hp, (int, float)) and isinstance(max_hp, (int, float)) and max_hp > 0 and hp < max_hp * 0.5:
                state = "damaged"
        motion_drawn = False
        body_rect=None
        body_cell=None
        # Use the same full-height art for the placement preview as for the
        # placed engine; otherwise the tall tower/ladder ghost is misleading.
        if row is not None or sprite:
            import kcs_siege_fx as fx
            motion = view.engine_actions.get(row.get("engine_id"), {}) if row is not None else {}
            age = time.time() - motion.get("start", 0)
            duration = motion.get("duration", 0)
            active_action = state != "destroyed" and 0 <= age < duration
            action = motion.get("action", "idle") if active_action else (state if state in ("damaged", "destroyed") else "idle")
            progress = max(0., min(1., age/max(.01, duration))) if active_action else 0
            root = ensure_assets()
            if root:
                motion_drawn = fx.engine_blit(surf, root, sprite,
                    (int(rotation)-int(view.view_quarter)*90)%360, action, progress,
                    (scx, scy), view.scale)
                if motion_drawn and row is not None:
                    meta=fx._meta('engine_motion_v2',sprite)
                    frame=fx._frame('engine_motion_v2',sprite,action,(int(rotation)-int(view.view_quarter)*90)%360,progress,view.scale/meta['px_per_tile']) if meta else None
                    if frame:
                        cell,anchor=frame
                        body_rect=cell.get_bounding_rect(min_alpha=20).move(int(scx-anchor[0]),int(scy-anchor[1]))
                        body_cell=(cell,(int(scx-anchor[0]),int(scy-anchor[1])))
        name = None if motion_drawn else av._baked_name(sprite, rotation, state, view.view_quarter)
        if name:
            try:
                # blit onto the map strip (without HUD_TOP), then we already offset circles.
                world = surf.subsurface(pygame.Rect(0, HUD_TOP, surf.get_width(), max(1, surf.get_height() - HUD_TOP - HUD_BOT)))
                blit_baked(world, name, cx, cy, view.origin, view.scale, view.screen_o, z=z)
            except Exception as exc:
                view.error = f"Engine art unavailable: {sprite} ({type(exc).__name__})"
        elif not motion_drawn:
            view.error = f"Missing engine sprite: {sprite}. Check KCS_VISUAL_FIXTURES."
        if z == 0 and (view.status or {}).get('decor'):
            import kcs_decor_client
            s = view.scale
            kcs_decor_client.restore_castle(surf, view, cx, cy, pygame.Rect(int(scx - s * 7), int(scy - s * 14), int(s * 14), int(s * 16)))
        if row is not None:
            body_rect=body_rect or pygame.Rect(scx-26,scy-38,52,45)
            if not surf.get_rect().colliderect(body_rect):return
            view.engine_pick_rects[row.get('engine_id')]=body_rect
            # An engine standing behind the curtain/gatehouse is hidden by the
            # restored stone; its ring, HP bar and READY tag must not float on
            # the wall either. The details panel still reports it.
            visible = 1.0
            if z == 0 and (view.status or {}).get('decor'):
                import kcs_decor_client
                if body_cell:
                    visible = kcs_decor_client.engine_visibility(view, cx, cy, body_cell[0], body_cell[1])
                else:
                    visible = kcs_decor_client.engine_visibility(view, cx, cy, None, body_rect.topleft, body_rect.size)
            hidden = visible < 0.5
            view.engine_visibility = getattr(view, 'engine_visibility', {})
            view.engine_visibility[row.get('engine_id')] = round(visible, 3)
            if hidden:
                return
            if (view.status or {}).get('economy') and row.get('engine_id')==getattr(view,'selected_engine_id',None):
                color=(255,211,105) if row.get('side')==view.your_side else (219,112,86)
                pygame.draw.ellipse(surf,color,(scx-max(22,min(70,body_rect.w//2)),scy-9,max(44,min(140,body_rect.w)),18),2)
                pygame.draw.rect(surf,color,body_rect.inflate(4,4),1,border_radius=4)
            _paint_engine_hp(surf,view,row,scx,scy)
            _paint_engine_reload(surf,view,row,(body_rect.centerx,body_rect.top-4))
            return
        for tx, ty in tiles:
            px, py, _z = project(tx + 0.5, ty + 0.5, 0, view.origin, view.scale, view.screen_o)
            pygame.draw.circle(surf, color, (int(px), int(py + HUD_TOP)), 7, 1)
        pygame.draw.line(surf, color, (scx, scy), (sfx, sfy), 3)
        pygame.draw.circle(surf, color, (sfx, sfy), 5)

    for row in view.engines:
        # Destroyed rows with HP 0 still show debris art when the server kept them.
        tiles = row.get("tiles") or [[row.get("x") or 0, row.get("y") or 0]]
        _mark(tiles, int(row.get("rotation") or 0), (255, 214, 90), row.get("engine_type"), row=row)
    if not view.build:
        view.rotation_manual = None
    if not view.build or view.bf is None or view.origin is None:
        return
    try:
        _paint_placement_guides(surf, client, view)
    except Exception as exc:
        view.placement_guides = {"error": type(exc).__name__}
    mx, my = pygame.mouse.get_pos()
    game = _game(client)
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
    # The world now fills the viewport. HUD plates composite over it instead
    # of reserving opaque top/bottom bands, including when folded/hidden.
    pass


def handle_battle_event(client, event) -> None:
    """Siege owns input; hidden overworld panels never keep invisible hitboxes."""
    view = view_of(client)
    economy=bool((view.status or {}).get('economy'))
    if economy and getattr(client,'chat_typing',False):
        if event.type==pygame.KEYDOWN:client.handle_chat_typing(event)
        return
    if economy and (getattr(client,'show_equipment',False) or getattr(client,'show_forge',False)):
        if event.type==pygame.KEYDOWN and event.key in (pygame.K_ESCAPE,pygame.K_e,pygame.K_f):
            client.show_equipment=False;client.show_forge=False
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if client.show_equipment:client.handle_equipment_click(*event.pos)
            else:client.handle_forge_click(*event.pos)
        elif event.type==pygame.MOUSEWHEEL:
            if client.show_equipment:
                import equipment_ui_v2
                equipment_ui_v2.handle_wheel(client,float(getattr(event,'precise_y',event.y)))
            else:client.forge_scroll=max(0,client.forge_scroll-event.y*36)
        return
    if economy and event.type==pygame.KEYDOWN:
        if event.key==pygame.K_RETURN:client._begin_chat_typing();return
        if event.key==pygame.K_e:
            client.context_menu=None;client.clear_walk();client.show_equipment=True;return
        if event.key==pygame.K_i:
            import kcs_hud
            kcs_hud.toggle(client,view,'hud-bag');return
        if event.key==pygame.K_f:
            if client.near_forge():client.open_forge_at()
            else:
                rows=[r for r in (client.dungeon or {}).get('workshops',[]) if r['kind'] in ('furnace','anvil') and r.get('side')==view.your_side]
                if rows:
                    px,py=client.player_xy();r=min(rows,key=lambda r:max(abs(px-r['x']),abs(py-r['y'])))
                    client.walk_and_act(client.adjacent_goals(r['x'],r['y']),{'type':'FORGE','kind':r['kind']})
            return
    if getattr(client, "context_menu", None):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            client.context_menu = None
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                client._click_context_menu(*event.pos)
                return
            client.context_menu = None
    if event.type == pygame.KEYDOWN:
        if view.guide_open:
            if event.key == pygame.K_ESCAPE:
                _close_guide(view)
            return
        if on_keydown(client, event):
            return
        if view.guide_open:
            return
        if event.key == pygame.K_ESCAPE:
            view.inspect = None
            view.details_open = False
            cancel_strikes(client)
            client.clear_walk()
            return
        step = client._arrow_step(event)
        if step is not None and client._begin_key_step():
            client.clear_walk()
            dx, dy = client.rotate_move_delta(*step)   # siege: screen_step via camera_yaw (t664u)
            client.try_move(dx, dy)
    elif event.type == pygame.MOUSEWHEEL:
        import kcs_hud
        if not kcs_hud.on_wheel(client, pygame.mouse.get_pos(), event.y) and not view.guide_open and (view.status or {}).get('decor'):change_zoom(client,event.y)
    elif event.type == pygame.MOUSEBUTTONDOWN:
        if event.button in (4, 5):
            import kcs_hud
            amount=1 if event.button==4 else -1
            if not kcs_hud.on_wheel(client,event.pos,amount) and not view.guide_open and (view.status or {}).get('decor'):change_zoom(client,amount)
        elif event.button == 1:
            on_mouse(client, event.pos)
        elif event.button == 3:
            if blocks_world(client, event.pos):
                return
            view.build = False
            view.inspect = None
            client.clear_walk()
            if not view.guide_open and not any(r.collidepoint(event.pos) for r in view.ui_regions):
                import player_interactions
                player_interactions.on_click(client, event.pos, 3)


def _update_motion(client, view):
    """Interpolate authoritative tile changes; never send invented movement."""
    now = time.time()
    people = dict(getattr(client, "players", {}) or {})
    me = getattr(client, "player", None) or {}
    if me:
        people[me.get("id")] = {**me, "x": _player_tile(client)[0], "y": _player_tile(client)[1]}
    people.update(getattr(view, "mercs", None) or {})
    for pid, person in people.items():
        merc = isinstance(pid, int) and pid < 0
        target = (float(person.get("x", 0)), float(person.get("y", 0)))
        row = view.motion.get(pid)
        if row is None:
            row = {"target": target, "from": target, "draw": target, "at": now, "moving_until": 0}
            view.motion[pid] = row
        if row["target"] != target:
            old = row["target"]
            distance = max(abs(target[0] - old[0]), abs(target[1] - old[1]))
            row.update({"from": row["draw"] if distance <= 2 else target, "target": target, "at": now,
                        "moving_until": (now + (.62 if merc else .28)) if distance <= 2 else 0})
            if distance <= 2:
                dx, dy = target[0] - old[0], target[1] - old[1]
                face = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("front" if dy > 0 else "back")
                getattr(client, "_entity_facing", {})[("p", pid)] = face
        t = min(1.0, max(0.0, (now - row["at"]) / (.5 if merc else .18)))
        row["draw"] = tuple(row["from"][i] + (target[i] - row["from"][i]) * t for i in (0, 1))
    keep = set(people) | set(view.corpses)
    for cache in (view.motion, view.actor_anims, view.actor_hits, view.actor_melee, view.actor_actions):
        for pid in list(cache):
            if pid not in keep:
                cache.pop(pid, None)


def _placement_hint(text):
    if "circulation" in str(text).lower():
        return "Keep the path around the castle and gate clear. Move your engine a few tiles out."
    return str(text or "")


def _draw_battle_overlay(client, view):
    # Compatibility entry point for existing tools; one shared layout per mode.
    draw_overlay(client)


def _ore_art(surf, kind, x, y, size, depleted=False):
    """Main-game mine rock art (client/assets/mine/ores: coal, iron, mithril, adamantite, and the
    depleted rock), sized to the siege rock footprint. False falls back to the procedural rock."""
    try:
        import deepdelve_client as dd
        name = "depleted" if depleted else dd.ORE_ART.get(kind)
        img = dd._by_width(f"ores/{name}.png", size * 1.75) if name else None
    except Exception:
        img = None
    if img is None:
        return False
    surf.blit(img, img.get_rect(midbottom=(int(x), int(y + size * 0.55))))
    return True


def _paint_workshops(surf,client,view):
    """Existing rock/furnace/anvil drawers, projected at the fixed siege camera."""
    view.workshop_rects={}
    view.workshop_labels=[]
    view.workshop_label_rects=[]
    view.map_label_rects=[]  # READY tags (painted earlier this frame) dodge last frame's
    px,py=_player_tile(client);mouse=pygame.mouse.get_pos()
    if not (view.status or {}).get('economy'):return
    import procedural_sprites_finished as sprites
    size=max(14,round(view.scale*1.5));font=pygame.font.Font(None,17)
    import types,kcs_engineering
    p=view.bf.plane
    proxy=types.SimpleNamespace(width=p.width,height=p.height,rows=p.grid,in_bounds=p.in_bounds,landmarks={key:obj.rect for key,obj in p.landmarks.items()})
    highs=[t for t in kcs_engineering.stair_points(proxy) if p.cell(*t)=='H']
    shown=[]
    for tx,ty in sorted(highs):
        if any(max(abs(tx-x),abs(ty-y))<=6 for x,y in shown):continue
        shown.append((tx,ty))
        point=_actor_floor_spot(client,view,(tx,ty))
        if point and surf.get_rect().collidepoint(point):
            x,y=map(int,point)
            for n in range(4):pygame.draw.line(surf,(234,200,133),(x-8+n*3,y-3*n),(x+4+n*3,y-3*n),2)
            text=font.render('Steps',True,(248,221,168));back=text.get_rect(midtop=(x,y+6))
            if (view.status or {}).get('decor'):
                for other in getattr(view,'reload_label_rects',[]):
                    if back.inflate(6,2).colliderect(other):back.top=other.bottom+3
                view.map_label_rects.append(back.inflate(6,2))
            pygame.draw.rect(surf,(34,27,18),back.inflate(6,2),border_radius=2);surf.blit(text,back)

    for row in (client.dungeon or {}).get('workshops',[]):
        point=tile_to_screen(client,row['x'],row['y'])
        if not point:continue
        x,y=map(int,point)
        if not surf.get_rect().inflate(100,100).collidepoint(point):continue
        kind=row['kind']
        rect=None
        if (view.status or {}).get('decor') and kind in ('furnace','anvil'):
            import kcs_decor_client
            rect=kcs_decor_client.station(surf,view,row)
        elif kind=='fletching':
            sprites.draw_workbench(surf,x,y,max(24,round(view.scale*1.6)))
            pygame.draw.arc(surf,(150,104,52),pygame.Rect(x-size//2,y-size,size,size),1.9,4.4,3)  # a bow on the bench
            rect=pygame.Rect(x-size,y-size,size*2,size+10)
        elif kind=='furnace':sprites.draw_furnace(surf,x,y,size,time.time())
        elif kind=='anvil':sprites.draw_anvil(surf,x,y,size,time.time())
        elif (view.status or {}).get('decor'):
            import kcs_decor_client
            spent=(getattr(view,'rock_depleted',None) or {}).get((row['x'],row['y']),0)>time.time()
            rect=kcs_decor_client.rock(surf,view,row,lambda img,ax,ay,sz,kind=kind,spent=spent:_ore_art(img,kind,ax,ay,sz,spent) or sprites.draw_rock_detailed(img,ax,ay,sz,variant=0,ore_type=kind),size)
        else:
            spent=(getattr(view,'rock_depleted',None) or {}).get((row['x'],row['y']),0)>time.time()
            _ore_art(surf,kind,x,y,size,spent) or sprites.draw_rock_detailed(surf,x,y,size,variant=0,ore_type=kind)
        if rect is None and kind.endswith('_rock'):
            import kcs_decor_client
            rect=kcs_decor_client.rock_rect(x,y,size)
        rect=rect or pygame.Rect(x-size//2,y-size,size,size+8);view.workshop_rects[(row['x'],row['y'])]=rect
        # Hover reveals a distant label only for a station actually on the map
        # view (its foot on screen, cursor below the top HUD); a station whose
        # foot sits just off the top edge must not catch a cursor parked at 0,0.
        over_ui=any(r.collidepoint(mouse) for r in getattr(view,'ui_regions',[]) or [])
        hover=rect.collidepoint(mouse) and surf.get_rect().collidepoint(point) and mouse[1]>=HUD_TOP and not over_ui
        if max(abs(px-row['x']),abs(py-row['y']))>8 and not hover:continue
        label=kind.replace('_rock',' ore').replace('_',' ').title()
        text=font.render(label,True,(246,218,164));back=text.get_rect(midtop=(x,y+3))
        if (view.status or {}).get('decor'):
            # Keep the tag out from under the Actions/info panels (1024 layout).
            import kcs_decor_client
            plate=kcs_decor_client.clear_of_ui(back.inflate(6,3),view,surf.get_rect(),anchor_top=rect.top)
            if plate is None:continue
            back=text.get_rect(center=plate.center)
        view.workshop_labels.append((row['x'],row['y'],kind))
        view.workshop_label_rects=getattr(view,'workshop_label_rects',[])+[back.inflate(6,3)]
        pygame.draw.rect(surf,(34,27,18),back.inflate(6,3),border_radius=2);surf.blit(text,back)

    # Fletching bench panel: opens on arrival, closes when you walk away.
    bench=getattr(view,'fletch_pending',None) or getattr(view,'fletch_open',None)
    if bench:
        d=max(abs(px-bench[0]),abs(py-bench[1]))
        if getattr(view,'fletch_pending',None) and d<=1:view.fletch_open,view.fletch_pending=bench,None
        elif getattr(view,'fletch_open',None) and d>3:view.fletch_open=None
    camp=(client.dungeon or {}).get('camp')
    if camp:
        point=tile_to_screen(client,camp['x'],camp['y'])
        if point:
            label=font.render('⚑ Attacker camp' if font.size('⚑')[0] else 'Attacker camp',True,(248,221,168));rect=label.get_rect(midbottom=(point[0],point[1]-18))
            view.camp_label_rect=rect
            if max(abs(px-camp['x']),abs(py-camp['y']))<=16 or rect.collidepoint(mouse):
                pygame.draw.rect(surf,(34,27,18),rect.inflate(10,6),border_radius=3);surf.blit(label,rect)


def draw_siege_modals(client):
    """Reuse the actual gear/bag, recipe and chat panels; no parallel systems."""
    if not (view_of(client).status or {}).get('economy'):return
    game=_game(client);saved=(game.MAP_W,game.MAP_H,game.SIDEBAR_X)
    try:
        if getattr(client,'show_equipment',False):
            game.MAP_W=game.SIDEBAR_X=client.screen.get_width()-300
            client.hud_focus=None;client.hud_system='inventory'
            client.draw_sidebar();client.draw_equipment_modal()
        elif getattr(client,'show_forge',False):client.draw_forge_modal()
        if getattr(client,'chat_typing',False):
            game.MAP_H=client.screen.get_height()-140;client.draw_chat()
    finally:game.MAP_W,game.MAP_H,game.SIDEBAR_X=saved
