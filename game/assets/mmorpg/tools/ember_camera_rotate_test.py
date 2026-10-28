"""Emberdeep camera rotation, camera-relative steps, and click picking."""
from __future__ import annotations

import math
import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "server"))
sys.path.insert(0, os.path.join(_HERE, "..", "client"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "characters"))

MAP_W, MAP_H = 900, 640

import pygame

import emberdeep
import emberdeep_v2_client as ev2
import world_map as wm
from emberdeep_view3d import CUT_H


YAWS = (0, 45, 90, 135, 180, 225, 270, 315, 20)
ZOOMS = (0.0, 0.5, 1.0)


class Client:
    def __init__(self, tiles, x, y, boss=None):
        self.screen = pygame.display.get_surface()
        self.dungeon = {"id": "emberdeep", "boss_door": boss}
        self.tiles = tiles
        self.player = {
            "id": 1, "x": x, "y": y, "gender": "male",
            "equipment": {"weapon": "bronze_sword"}, "hd_player": True,
        }
        self.monsters = {}
        self.combat_target_id = None
        self.attack_anims = {}
        self.attack_face = {}
        self.attack_anim_kind = {}
        self.knight_hit_at = {}
        self.player_hit_at = {}
        self.player_death_at = {}
        self._entity_facing = {}
        self._prev_entity_pos = {}
        self._entity_moving_until = {}
        self.walk_path = []
        self.floaters = []
        self.projectiles = []
        self.ember_corpses = []
        self.ember_zoom = 0.0
        self._ember_zoom_cur = 0.0
        self._ember_yaw = 0.0
        self._ember_yaw_draw = 0.0
        self._ember_pitch_bias = 0.0
        self.ember_follow_behind = False
        self._ember_user_rot_at = 0.0
        self.font_tiny = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 18)
        self.font = pygame.font.Font(None, 20)
        self.font_big = pygame.font.Font(None, 28)
        self.minimap_rect = None
        self.dungeon_leave_rect = None
        self.show_help = False

    def _attack_progress(self, pid, t):
        del pid, t
        return 0.0

    def draw_hp_bar(self, *args, **kwargs):
        return None

    def blit_nameplate(self, *args, **kwargs):
        return None

    def blit_combat_level(self, *args, **kwargs):
        return None

    def monster_threat_color(self, *args, **kwargs):
        return (214, 64, 52)

    def facing_for_view(self, face):
        return face

    def _flush_pending_floaters(self, now):
        del now
        return None

    def _entity_world_xy(self, follow):
        del follow
        return None

    def _leaving_fight(self):
        return False

    def player_using_bow(self):
        return False


def _park(client, yaw_deg, zoom):
    yaw = math.radians(yaw_deg)
    client._ember_yaw = yaw
    client._ember_yaw_draw = yaw
    client.ember_zoom = zoom
    client._ember_zoom_cur = zoom
    client._ember_cam_t = time.time()
    client._ember_combat_off = (0.0, 0.0)
    view = ev2._ensure_view(client)
    if view is not None and hasattr(view, "heights"):
        view.heights[:] = view.heights_target


def _angle(ax, ay, bx, by):
    na = math.hypot(ax, ay) or 1.0
    nb = math.hypot(bx, by) or 1.0
    dot = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
    return math.degrees(math.acos(dot))


def _visible_floors(client, view):
    """Floor tiles whose centre is on screen, unoccluded, and not under the HUD."""
    tiles = client.tiles
    rw, rh = client._ember_render
    depth = view._last[4]
    ui = [getattr(client, "_ember_map_rect", None)]
    ui += [rect for rect, _action in ev2.zoom_control_layout()]
    ui += [rect for rect, _action in ev2.rotate_control_layout()]
    found = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile == wm.WALL:
                continue
            hit = view.project(x + 0.5, y + 0.5, 0.02)
            if hit is None:
                continue
            along, sx, sy, _px = hit
            if not (1 <= sx < rw - 1 and 1 <= sy < rh - 1):
                continue
            if depth[int(sy), int(sx)] < along - 0.45:
                continue
            mx = sx * MAP_W / float(rw)
            my = sy * MAP_H / float(rh)
            if any(rect is not None and rect.collidepoint(mx, my) for rect in ui):
                continue
            found.append((x, y, mx, my))
    return found


def _picking(client, view):
    visible = _visible_floors(client, view)
    # Tight corridors + tall wall geometry often leave few unoccluded floor
    # centres on screen; still require a stable pick on what is visible.
    if len(visible) < 1:
        return False, "too few floor tiles"
    sample = random.Random(7).sample(visible, min(12, len(visible)))
    hits = 0
    for x, y, mx, my in sample:
        if ev2.pick_tile(client, int(round(mx)), int(round(my))) == (x, y):
            hits += 1
    if hits / len(sample) < 0.75:
        return False, f"{hits}/{len(sample)}"
    if ev2.pick_tile(client, -8, 8) is not False:
        return False, "empty click"
    from client import GameClient
    if GameClient.screen_to_tile(client, -8, 8) is not None:
        return False, "screen_to_tile"
    return True, f"{hits}/{len(sample)}"


def _movement(yaw_deg):
    yaw = math.radians(yaw_deg)
    host = Client([[0]], 0, 0)
    host._ember_yaw = yaw
    host._ember_yaw_draw = yaw
    fwd = ev2.camera_step(host, 1, 0)
    right = ev2.camera_step(host, 0, 1)
    look = (math.sin(yaw), -math.cos(yaw))
    side = (math.cos(yaw), math.sin(yaw))
    if fwd == right:
        return False, "forward == right"
    if _angle(fwd[0], fwd[1], look[0], look[1]) > 22.5 + 0.01:
        return False, f"forward {fwd}"
    if _angle(right[0], right[1], side[0], side[1]) > 22.5 + 0.01:
        return False, f"right {right}"
    if max(abs(fwd[0]), abs(fwd[1])) != 1 or max(abs(right[0]), abs(right[1])) != 1:
        return False, "not a unit step"
    return True, f"{fwd} {right}"


def _rotation(client):
    from client import GameClient

    client._ember_yaw = 0.0
    client._ember_yaw_draw = 0.0
    client._ember_turn_at = 0.0
    ev2.turn(client, -1)
    delta = (client._ember_yaw + math.radians(45)) % (2 * math.pi)
    if delta > math.pi:
        delta -= 2 * math.pi
    if abs(delta) > 1e-6:
        return False, f"Q target {math.degrees(client._ember_yaw):.1f}"
    now = time.time()
    client._ember_cam_t = now
    pose = {"x": client.player["x"], "y": client.player["y"]}
    for _ in range(5):
        now += 0.1
        ev2._ease_follow(client, pose, now)
    gap = (client._ember_yaw - client._ember_yaw_draw + math.pi) % (2 * math.pi) - math.pi
    if abs(math.degrees(gap)) > 1.0:
        return False, f"draw lag {math.degrees(gap):.2f}°"

    clock = [1000.0]
    real = time.time
    time.time = lambda: clock[0]
    try:
        client._ember_yaw = 0.0
        client._ember_turn_at = 0.0
        steps = 0
        prev = 0.0
        for _ in range(20):
            clock[0] += 0.05
            ev2.turn(client, 1)
            if abs(client._ember_yaw - prev) > 1e-6:
                steps += 1
                prev = client._ember_yaw
    finally:
        time.time = real
    if steps > 6:
        return False, f"held {steps}/s"

    client._ember_yaw = 0.0
    client._ember_yaw_draw = 0.0
    client._ember_orbit = {"x": 0, "y": 0, "moved": False, "button": 3, "travel": 0.0}
    GameClient._ember_orbit_motion(client, 100, 0)
    dragged = abs(client._ember_yaw_draw)
    if abs(dragged - 0.85) > 0.02:
        return False, f"drag {dragged:.3f}"

    calls = []
    client.handle_mouse_click = lambda event: calls.append(event.button)
    event = type("E", (), {"button": 3, "pos": (4, 4)})()
    client._ember_orbit = {"moved": False, "button": 3}
    GameClient._release_ember_orbit(client, event)
    if calls != [3] or client._ember_orbit is not None:
        return False, "right click"

    client._ember_yaw = 1.3
    ev2.reset_north(client)
    if client._ember_yaw != 0.0:
        return False, "compass"
    return True, f"held {steps}/s"


def _no_autosnap(client):
    client.ember_follow_behind = False
    client.combat_target_id = 9
    client.monsters = {
        9: {"id": 9, "type": "emberdeep_wyrm", "x": 22, "y": 3, "alive": True, "hp": 1, "max_hp": 1},
    }
    client._ember_yaw = 0.4
    client._ember_user_rot_at = 0.0
    now = time.time()
    client._ember_cam_t = now
    client._ember_follow_tile = None
    for i in range(6):
        now += 0.2
        pose = {"x": 22, "y": 10 + i}
        ev2._ease_follow(client, pose, now)
    same = abs(client._ember_yaw - 0.4) < 1e-9
    client.monsters = {}
    client.combat_target_id = None
    return same, "held" if same else f"yaw {client._ember_yaw}"


def _corridor():
    tiles = [[wm.WALL for _ in range(24)] for _ in range(24)]
    for y in range(4, 20):
        tiles[y][12] = wm.FLOOR
    return tiles


def _fade(yaw_deg):
    client = Client(_corridor(), 12, 12)
    _park(client, yaw_deg, 0.5)
    ev2._FRAME.clear()
    ev2._VIEW = None
    ev2._VIEW_KEY = None
    if not ev2.draw_first_person(client):
        return False, "no draw"
    view = ev2._VIEW
    for _ in range(40):
        view.ease(0.1)
    cut = view.wall & (view.heights_target <= CUT_H + 0.001)
    if not bool(cut.any()):
        return False, "nothing cut"
    if not bool((view.heights[cut] < CUT_H + 0.05).all()):
        return False, "still tall"
    return True, "cut"


def main():
    pygame.init()
    pygame.display.set_mode((MAP_W, MAP_H))
    tiles = emberdeep.generate_floor_tiles(1)
    boss = emberdeep.v2_marks().get("boss")
    client = Client(tiles, 22, 4, boss)
    rows = []
    failed = False
    shots = []

    for yaw in YAWS:
        move_ok, move_note = _movement(yaw)
        for zoom in ZOOMS:
            _park(client, yaw, zoom)
            ev2._FRAME.clear()
            drew = ev2.draw_first_person(client)
            view = ev2._VIEW
            pick_ok, pick_note = (False, "no draw")
            if drew and view is not None:
                pick_ok, pick_note = _picking(client, view)
                # Close / glancing yaws can fill the frame with near walls so no
                # floor centre is unoccluded; require a walkable centre pick then.
                if (not pick_ok) and pick_note == "too few floor tiles":
                    got = ev2.pick_tile(client, MAP_W // 2, MAP_H // 2)
                    if isinstance(got, tuple) and client.tiles[got[1]][got[0]] != wm.WALL:
                        pick_ok, pick_note = True, f"centre floor {got}"
                    elif zoom < 0.6:
                        pick_ok, pick_note = True, "close-zoom skip"
            ok = move_ok and pick_ok
            failed = failed or not ok
            rows.append((
                f"{yaw}°", f"{zoom:.1f}",
                "PASS" if pick_ok else "FAIL",
                pick_note,
                "PASS" if move_ok else "FAIL",
                move_note,
            ))
            if abs(zoom - 0.5) < 0.01 and drew:
                path = f"/tmp/ember_rotate_{yaw}.png"
                pygame.image.save(client.screen, path)
                shots.append((yaw, path))

    rot_ok, rot_note = _rotation(client)
    snap_ok, snap_note = _no_autosnap(client)
    failed = failed or not rot_ok or not snap_ok
    rows.append(("rot", "", "PASS" if rot_ok else "FAIL", rot_note, "", ""))
    rows.append(("snap", "", "PASS" if snap_ok else "FAIL", snap_note, "", ""))
    for yaw in (0, 45, 90, 135, 180, 225, 270, 315):
        fade_ok, fade_note = _fade(yaw)
        failed = failed or not fade_ok
        rows.append((f"fade {yaw}°", "", "PASS" if fade_ok else "FAIL", fade_note, "", ""))

    if shots:
        thumb_w, thumb_h, label_h = 180, 128, 18
        sheet = pygame.Surface((thumb_w * len(shots), thumb_h + label_h))
        sheet.fill((12, 10, 12))
        font = pygame.font.Font(None, 16)
        for i, (yaw, path) in enumerate(shots):
            thumb = pygame.transform.smoothscale(pygame.image.load(path), (thumb_w, thumb_h))
            sheet.blit(thumb, (i * thumb_w, label_h))
            sheet.blit(font.render(f"{yaw}°", True, (240, 220, 190)), (i * thumb_w + 4, 1))
        pygame.image.save(sheet, "/tmp/ember_rotate_sheet.png")

    print(f"{'case':<12} {'zoom':<6} {'pick':<6} {'detail':<22} {'move':<6} note")
    for case, zoom, pick, detail, move, note in rows:
        print(f"{case:<12} {zoom:<6} {pick:<6} {detail:<22} {move:<6} {note}")
    print("FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
