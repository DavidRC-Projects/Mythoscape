"""Draw the Emberdeep dragon fight from eight camera yaws and check the swing."""
from __future__ import annotations

import math
import os
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
import player_hd_client


YAWS = (0, 45, 90, 135, 180, 225, 270, 315)
PROGRESSES = (0.0, 0.34, 0.48, 0.62)


class Client:
    def __init__(self, tiles, boss):
        self.screen = pygame.display.get_surface()
        self.dungeon = {"id": "emberdeep", "boss_door": boss}
        self.tiles = tiles
        self.player = {
            "id": 1,
            "x": 22,
            "y": 5,
            "gender": "male",
            "equipment": {"weapon": "bronze_sword"},
            "hd_player": True,
        }
        self.monsters = {
            9: {
                "id": 9,
                "type": "emberdeep_wyrm",
                "x": 22,
                "y": 3,
                "hp": 100,
                "max_hp": 100,
                "alive": True,
                "facing": "s",
                "name": "Emberdeep Wyrm",
            }
        }
        self.combat_target_id = 9
        self.progress = 0.0
        self.attack_anims = {1: 1e12}
        self.attack_face = {}
        self.attack_anim_kind = {1: "melee"}
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
        self.ember_zoom = 0.35
        self._ember_zoom_cur = 0.35
        self._ember_yaw = 0.0
        self._ember_yaw_draw = 0.0
        self.font_tiny = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 18)
        self.font = pygame.font.Font(None, 20)
        self.font_big = pygame.font.Font(None, 28)

    def _attack_progress(self, pid, t):
        del pid, t
        return self.progress

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


def _snap_camera(client):
    """Park the follow camera on this swing so a short frame does not ease away."""
    p = client.player
    foe = client.monsters[9]
    fx = (p["x"] + 0.5) * 0.65 + (foe["x"] + 0.5) * 0.35
    fy = (p["y"] + 0.5) * 0.65 + (foe["y"] + 0.5) * 0.35
    client._ember_focus = (fx, fy)
    client._ember_yaw_draw = float(client._ember_yaw)
    client._ember_cam_t = time.time()
    client.ember_zoom = 0.35
    client._ember_zoom_cur = 0.35
    view = ev2._ensure_view(client)
    if view is not None and hasattr(view, "heights"):
        view.heights[:] = view.heights_target


def _screen_gap(client):
    """Dragon nearest-point screen x minus the player's screen x, and the tile size."""
    monster = client.monsters[9]
    tx, ty = ev2._target_point(client, monster)
    feet_x = client.player["x"] + 0.5
    feet_y = client.player["y"] + 0.5
    hit = ev2._project(0, 0, 0, 0, 0, 0, tx, ty, None, 1, 1, MAP_W, MAP_H)
    feet = ev2._project(0, 0, 0, 0, 0, 0, feet_x, feet_y, None, 1, 1, MAP_W, MAP_H)
    if hit is None or feet is None:
        return None, None, None
    tile_px = max(24, int(feet[3]))
    return hit[1] - feet[1], tile_px, (tx, ty)


def _changed_ratio(with_player, without, rect):
    clip = rect.clip(with_player.get_rect())
    if clip.w < 1 or clip.h < 1:
        return 0.0, 0
    a = pygame.surfarray.array3d(with_player.subsurface(clip))
    b = pygame.surfarray.array3d(without.subsurface(clip))
    changed = (a != b).any(axis=2)
    return float(changed.mean()), int(changed.sum())


def _dragon_side_count(with_player, without, rect, cx, toward):
    clip = rect.clip(with_player.get_rect())
    if clip.w < 1 or clip.h < 1:
        return 0
    a = pygame.surfarray.array3d(with_player.subsurface(clip))
    b = pygame.surfarray.array3d(without.subsurface(clip))
    changed = (a != b).any(axis=2)
    # surfarray is indexed [x, y] inside the clip.
    local_cx = int(cx - clip.x)
    if toward > 0:
        side = changed[max(0, local_cx + 1):, :]
    else:
        side = changed[:max(0, local_cx), :]
    if side.size == 0:
        return 0
    return int(side.sum())


def _draw_pair(client, skip, calls):
    skip[0] = False
    calls.clear()
    ev2.draw_first_person(client)
    shown = client.screen.copy()
    skip[0] = True
    ev2.draw_first_person(client)
    hidden = client.screen.copy()
    skip[0] = False
    return shown, hidden, list(calls)


def _sheet(frames):
    thumb_w, thumb_h = 160, 114
    label_h = 18
    cols = len(YAWS)
    rows = len(PROGRESSES)
    sheet = pygame.Surface((cols * thumb_w, rows * (thumb_h + label_h)))
    sheet.fill((12, 10, 12))
    font = pygame.font.Font(None, 16)
    for (yaw, progress), surf in frames.items():
        col = YAWS.index(yaw)
        row = PROGRESSES.index(progress)
        thumb = pygame.transform.smoothscale(surf, (thumb_w, thumb_h))
        x = col * thumb_w
        y = row * (thumb_h + label_h)
        sheet.blit(thumb, (x, y + label_h))
        tag = font.render(f"{yaw}°  {progress:.2f}", True, (240, 220, 190))
        sheet.blit(tag, (x + 4, y + 2))
    pygame.image.save(sheet, "/tmp/ember_hit_sheet.png")


def main():
    pygame.init()
    pygame.display.set_mode((MAP_W, MAP_H))
    tiles = emberdeep.generate_floor_tiles(1)
    boss = emberdeep.v2_marks().get("boss")
    client = Client(tiles, boss)
    _snap_camera(client)

    calls = []
    skip = [False]
    real_draw = player_hd_client.draw_player

    def wrapped(*args, **kwargs):
        if skip[0]:
            return True
        calls.append((args, kwargs))
        return real_draw(*args, **kwargs)

    player_hd_client.draw_player = wrapped
    rows = []
    frames = {}
    failed = False
    try:
        cases = [(yaw, None) for yaw in YAWS]
        cases.append((0, (25, 5)))
        for yaw, corner in cases:
            if corner is not None:
                client.player["x"], client.player["y"] = corner
            else:
                client.player["x"], client.player["y"] = 22, 5
            frames_for_yaw = []
            for progress in PROGRESSES:
                client.progress = progress
                client._ember_yaw = math.radians(yaw)
                client._ember_yaw_draw = client._ember_yaw
                _snap_camera(client)
                shown, hidden, got = _draw_pair(client, skip, calls)
                name = f"{yaw}_{progress:.2f}"
                if corner is not None:
                    name = f"corner_{name}"
                path = f"/tmp/ember_hit_{name}.png"
                pygame.image.save(shown, path)
                if corner is None:
                    frames[(yaw, progress)] = shown

                problems = []
                if not got:
                    problems.append("draw_player was not called")
                    anim, facing, frame, cx, cy, tile = None, None, None, 0, 0, 32
                else:
                    args, kwargs = got[0]
                    anim = kwargs.get("anim")
                    facing = kwargs.get("facing")
                    cx, cy, tile = args[3], args[4], args[5]
                    frame = player_hd_client._frame_for_anim(
                        anim, args[6], kwargs.get("progress"),
                        kwargs.get("hit_t", -1.0), kwargs.get("death_t", -1.0),
                    )[1]
                    frames_for_yaw.append(frame)
                    if anim != "melee":
                        problems.append(f"anim {anim}")
                    if facing not in (1, -1):
                        problems.append(f"facing {facing}")

                gap, tile_px, target = _screen_gap(client)
                if gap is not None and tile_px and facing in (1, -1):
                    if abs(gap) > 0.12 * tile_px:
                        want = 1 if gap > 0 else -1
                        if facing != want:
                            problems.append(f"facing {facing} but screen gap {gap:.1f}")
                elif gap is None:
                    problems.append("target did not project")

                if corner is not None and target is not None:
                    if target != (24.5, 4.5):
                        problems.append(f"nearest point {target}")

                body_tile = max(1.0, float(tile) / 1.1)
                rect = pygame.Rect(
                    int(cx - body_tile * 0.6),
                    int(cy - body_tile * 2.2),
                    max(1, int(body_tile * 1.2)),
                    max(1, int(body_tile * 2.2)),
                )
                ratio, _count = _changed_ratio(shown, hidden, rect)
                if ratio < 0.25:
                    problems.append(f"visible {ratio:.0%}")
                side = None
                if progress == 0.48 and facing in (1, -1):
                    side = _dragon_side_count(shown, hidden, rect, cx, facing)
                    if side <= 0:
                        problems.append("no pixels on the dragon side")

                ok = not problems
                failed = failed or not ok
                where = "corner" if corner else f"{yaw:>3}"
                rows.append((
                    where, f"{progress:.2f}", str(anim), str(facing),
                    str(frame), f"{ratio:.0%}",
                    "" if side is None else str(side),
                    "PASS" if ok else "FAIL " + "; ".join(problems),
                ))
            if corner is None and len(set(frames_for_yaw)) != len(PROGRESSES):
                failed = True
                rows.append((
                    f"{yaw:>3}", "swing", "", "", str(frames_for_yaw),
                    "", "", "FAIL frame index did not change",
                ))
    finally:
        player_hd_client.draw_player = real_draw

    _sheet(frames)
    header = f"{'yaw':>6}  {'prog':>5}  {'anim':<6}  {'face':>4}  {'frame':>5}  {'body':>5}  {'blade':>5}  result"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row[0]:>6}  {row[1]:>5}  {row[2]:<6}  {row[3]:>4}  {row[4]:>5}  "
            f"{row[5]:>5}  {row[6]:>5}  {row[7]}"
        )
    print("sheet /tmp/ember_hit_sheet.png")
    if failed:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
