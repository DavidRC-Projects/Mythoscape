"""Emberdeep HD follow camera: a small numpy software renderer for pygame.

Reference implementation for Cursor to port into game/assets/mmorpg/client/emberdeep_view3d.py.
The dungeon is a grid of wall blocks (height WALL_H tiles), floor and lava. The camera orbits
behind and above the player: zoom 0 = close third person, zoom 1 = high, near top-down.

World axes: x east, y south (map rows), z up. One tile = 1.0. Yaw matches the client:
look = (sin(yaw), -cos(yaw)), so yaw 0 looks north.

API
    view = EmberView3D(tiles, tex_dir, is_wall, is_lava)   # tiles: list[list[int]]
    view.set_camera(focus_x, focus_y, yaw, zoom)           # zoom float 0..1
    rgb, depth = view.render(rw, rh, now)                  # numpy (rh, rw, 3) uint8, (rh, rw) float32
    view.project(wx, wy, wz)  -> (depth, sx, sy, px_per_tile) in render pixels, or None
    view.pick(sx, sy)         -> (tile_x, tile_y) or None  (sx, sy in render pixels)
Only numpy + PIL/pygame. No feature flags.
"""
from __future__ import annotations

import math
import os

import numpy as np

WALL_H = 2.2       # wall height in tiles (HD bodies are ~2 tiles tall)
CUT_H = 0.30       # height of a wall that is cut away between camera and player
MAX_STEPS = 72


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _load_rgb(path):
    """RGB float image. pygame is always present in the game; surfarray needs numpy."""
    import pygame
    surf = pygame.image.load(path)
    if pygame.display.get_surface() is not None:
        surf = surf.convert()
    return pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(np.float32) / 255.0


def _sample(tex, u, v):
    h, w = tex.shape[:2]
    x = (np.floor(u * w).astype(np.int32)) % w
    y = (np.floor(v * h).astype(np.int32)) % h
    return tex[y, x]


class EmberView3D:
    # zoom 0 -> close behind the shoulder, zoom 1 -> high above
    PITCH = (30.0, 78.0)   # degrees below horizontal
    DIST = (3.0, 15.5)     # tiles from the focus point
    VFOV = (52.0, 44.0)    # vertical field of view

    def __init__(self, tiles, tex_dir, is_wall, is_lava, boss_door=None):
        self.tiles = tiles
        self.h = len(tiles)
        self.w = len(tiles[0]) if self.h else 0
        grid = np.array(tiles)
        self.wall = np.vectorize(is_wall)(grid).astype(bool)
        self.lava = np.vectorize(is_lava)(grid).astype(bool)
        t = lambda n: _load_rgb(os.path.join(tex_dir, n))
        self.tex_wall = [t("wall_stone.png"), t("wall_stone_b.png")]
        self.tex_lava_wall = t("wall_stone_lava.png")
        self.tex_floor = t("floor_flagstone.png")
        self.tex_top = t("wall_top.png")
        self.tex_base = t("wall_base_trim.png")
        self.tex_cap = t("wall_cap_trim.png")
        self.tex_lava = t("lava_flow.png")
        door = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "emberdeep_v2_pack", "fp", "door_boss.png",
        ))
        self.tex_door = _load_rgb(door) if os.path.isfile(door) else None
        self.boss_door = boss_door
        # per-cell wall material: 0/1 stone variants, 2 lava-veined, 3 boss door
        mat = ((np.arange(self.w)[None, :] * 7 + np.arange(self.h)[:, None] * 13) % 5 < 2).astype(np.int8)
        near_lava = np.zeros_like(self.lava)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            near_lava |= np.roll(np.roll(self.lava, dy, 0), dx, 1)
        mat[self.wall & near_lava] = 2
        if boss_door and self.tex_door is not None:
            bx, by = boss_door
            for dx in (-1, 0, 1):
                for yy in (by - 1, by, by + 1):
                    if 0 <= yy < self.h and 0 <= bx + dx < self.w and self.wall[yy, bx + dx]:
                        mat[yy, bx + dx] = 3
        self.mat = mat
        self.heights = np.where(self.wall, WALL_H, 0.0).astype(np.float32)
        # rim = wall cells that touch floor or lava (8-neighbour); deeper rock reads as dark mass
        open_ = ~self.wall
        rim = np.zeros_like(self.wall)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                rim |= np.roll(np.roll(open_, dy, 0), dx, 1)
        self.rim = rim & self.wall
        self.torches = self._place_torches()
        self._bake_light()
        self.set_camera(self.w / 2, self.h / 2, 0.0, 0.0)

    # ---------- static bakes (once per floor) ----------
    def _place_torches(self):
        """Wall faces that look onto floor, spaced out. Returns [(x, y, nx, ny)] at the face."""
        out = []
        taken = set()
        for y in range(1, self.h - 1):
            for x in range(1, self.w - 1):
                if not self.wall[y, x] or (x * 7 + y * 13) % 5:
                    continue
                for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                    fx, fy = x + dx, y + dy
                    if self.wall[fy, fx] or self.lava[fy, fx]:
                        continue
                    if any(abs(fx - a) + abs(fy - b) < 4 for a, b in taken):
                        break
                    taken.add((fx, fy))
                    out.append((x + 0.5 + dx * 0.5, y + 0.5 + dy * 0.5, dx, dy))
                    break
        return out

    def _bake_light(self, res=8):
        """Torch + lava light and floor contact AO on a res-per-tile grid."""
        H, W = self.h * res, self.w * res
        ys, xs = (np.mgrid[0:H, 0:W] + 0.5) / res
        light = np.zeros((H, W, 3), np.float32)
        warm = np.array([1.0, 0.58, 0.26], np.float32)
        for (tx, ty, nx, ny) in self.torches:
            lx, ly = tx + nx * 0.25, ty + ny * 0.25
            d = np.hypot(xs - lx, ys - ly)
            # light only spills on the floor side of the wall
            facing = np.clip(((xs - tx) * nx + (ys - ty) * ny) * 4 + 0.6, 0, 1)
            light += (np.clip(1 - d / 4.6, 0, 1) ** 2 * 1.25 * facing)[..., None] * warm
        lava_px = np.kron(self.lava.astype(np.float32), np.ones((res, res), np.float32))
        glow = lava_px
        for _ in range(4):  # cheap blur
            glow = (glow + np.roll(glow, res, 0) + np.roll(glow, -res, 0) + np.roll(glow, res, 1) + np.roll(glow, -res, 1)) / 5
        light += (glow * 1.4)[..., None] * np.array([1.0, 0.38, 0.08], np.float32)
        self.light = light
        self.light_res = res
        # contact AO: distance from each floor sample to the nearest wall cell
        wall_px = np.kron(self.wall.astype(np.float32), np.ones((res, res), np.float32))
        dist = np.where(wall_px > 0, 0.0, 99.0).astype(np.float32)
        for step in range(1, int(res * 0.8) + 1):
            for ax in (0, 1):
                for sh in (step, -step):
                    dist = np.minimum(dist, np.where(np.roll(wall_px, sh, ax) > 0, step / res, 99.0))
        self.floor_ao = (1 - 0.55 * np.exp(-dist / 0.22)).astype(np.float32)

    # ---------- camera ----------
    def set_camera(self, fx, fy, yaw, zoom):
        z = float(np.clip(zoom, 0.0, 1.0))
        pitch = math.radians(self.PITCH[0] + (self.PITCH[1] - self.PITCH[0]) * z ** 0.85)
        dist = self.DIST[0] + (self.DIST[1] - self.DIST[0]) * z ** 1.25
        self.vfov = math.radians(self.VFOV[0] + (self.VFOV[1] - self.VFOV[0]) * z)
        lx, ly = math.sin(yaw), -math.cos(yaw)
        focus = np.array([fx, fy, 1.0], np.float32)
        cam = focus + np.array([-lx * math.cos(pitch) * dist, -ly * math.cos(pitch) * dist, math.sin(pitch) * dist], np.float32)
        f = focus - cam
        f /= np.linalg.norm(f)
        up = np.array([0, 0, 1], np.float32)
        r = np.cross(up, f); r /= np.linalg.norm(r)
        u = np.cross(f, r)
        self.cam, self.f, self.r, self.u = cam, f, r, u
        self.focus = focus
        self.zoom = z
        self._cutaway(fx, fy)

    def _cutaway(self, fx, fy):
        """Walls standing between the camera and the player drop to a stub, so the player
        and their room stay visible. Heights ease toward the target over a few frames."""
        target = np.where(self.wall, WALL_H, 0.0).astype(np.float32)
        cx, cy = self.cam[0], self.cam[1]
        ys, xs = np.mgrid[0:self.h, 0:self.w] + 0.5
        sx, sy = cx - fx, cy - fy
        seg2 = sx * sx + sy * sy + 1e-6
        tpar = np.clip(((xs - fx) * sx + (ys - fy) * sy) / seg2, 0, 1)
        px, py = fx + tpar * sx, fy + tpar * sy
        near = np.hypot(xs - px, ys - py) < 1.6
        # also anything within 1.5 tiles of the player on the camera's side
        side = ((xs - fx) * sx + (ys - fy) * sy) > 0
        ring = (np.hypot(xs - fx, ys - fy) < 2.2) & side
        cut = self.wall & ((near & (tpar > 0.04)) | ring)
        target[cut] = CUT_H
        self.heights_target = target

    def ease(self, dt):
        k = 1 - math.exp(-dt * 10.0)
        self.heights += (self.heights_target - self.heights) * k

    # ---------- rendering ----------
    def render(self, rw, rh, now=0.0, player_light=True):
        tan_v = math.tan(self.vfov / 2)
        tan_h = tan_v * rw / rh
        xs = ((np.arange(rw, dtype=np.float32) + 0.5) / rw * 2 - 1) * tan_h
        ys = (1 - (np.arange(rh, dtype=np.float32) + 0.5) / rh * 2) * tan_v
        D = (self.f[None, None, :] + xs[None, :, None] * self.r[None, None, :] + ys[:, None, None] * self.u[None, None, :])
        D = D.reshape(-1, 3)
        n = D.shape[0]
        C = self.cam
        Dx, Dy, Dz = D[:, 0], D[:, 1], D[:, 2]
        out = np.zeros((n, 3), np.float32)
        depth = np.full(n, 1e4, np.float32)
        hmax = WALL_H
        down = Dz < -1e-4
        idx = np.nonzero(down)[0]
        dz = -Dz[idx]
        t0 = np.maximum(0.0, (C[2] - hmax) / dz)
        tf = C[2] / dz
        px = C[0] + Dx[idx] * t0
        py = C[1] + Dy[idx] * t0
        cx = np.floor(px).astype(np.int32)
        cy = np.floor(py).astype(np.int32)
        dxr, dyr = Dx[idx], Dy[idx]
        step_x = np.where(dxr > 0, 1, -1).astype(np.int32)
        step_y = np.where(dyr > 0, 1, -1).astype(np.int32)
        inv_x = np.where(np.abs(dxr) > 1e-6, 1.0 / np.abs(dxr), 1e9).astype(np.float32)
        inv_y = np.where(np.abs(dyr) > 1e-6, 1.0 / np.abs(dyr), 1e9).astype(np.float32)
        tmx = t0 + np.where(dxr > 0, (cx + 1 - px), (px - cx)) * inv_x
        tmy = t0 + np.where(dyr > 0, (cy + 1 - py), (py - cy)) * inv_y
        t_in = t0.copy()
        side = np.zeros(len(idx), np.int8)   # 0 entered through an x face, 1 through a y face
        first = np.ones(len(idx), bool)
        kind = np.zeros(len(idx), np.int8)   # 1 side, 2 top, 3 floor
        t_hit = np.zeros(len(idx), np.float32)
        hit_cx = np.zeros(len(idx), np.int32)
        hit_cy = np.zeros(len(idx), np.int32)
        hit_h = np.zeros(len(idx), np.float32)
        act = np.arange(len(idx))
        H = self.heights
        for _ in range(MAX_STEPS):
            if act.size == 0:
                break
            ax, ay = cx[act], cy[act]
            inb = (ax >= 0) & (ay >= 0) & (ax < self.w) & (ay < self.h)
            h = np.where(inb, H[np.clip(ay, 0, self.h - 1), np.clip(ax, 0, self.w - 1)], hmax)
            ti = t_in[act]
            to = np.minimum(tmx[act], tmy[act])
            zi = C[2] - dz[act] * ti
            th = (C[2] - h) / dz[act]
            solid = h > 0
            s_hit = solid & (zi <= h + 1e-4) & ~first[act]
            top = solid & ~s_hit & (th <= to + 1e-5)
            fl = ~solid & (tf[act] <= to + 1e-5)
            done = s_hit | top | fl
            sel = act[done]
            kind[sel] = np.where(s_hit[done], 1, np.where(top[done], 2, 3))
            t_hit[sel] = np.where(s_hit[done], ti[done], np.where(top[done], th[done], tf[act][done]))
            hit_cx[sel] = ax[done]
            hit_cy[sel] = ay[done]
            hit_h[sel] = h[done]
            act = act[~done]
            if act.size == 0:
                break
            first[act] = False
            gox = tmx[act] < tmy[act]
            a_x = act[gox]
            a_y = act[~gox]
            t_in[a_x] = tmx[a_x]; cx[a_x] += step_x[a_x]; tmx[a_x] += inv_x[a_x]; side[a_x] = 0
            t_in[a_y] = tmy[a_y]; cy[a_y] += step_y[a_y]; tmy[a_y] += inv_y[a_y]; side[a_y] = 1
        # leftovers: floor at tf
        if act.size:
            kind[act] = 3; t_hit[act] = tf[act]
        P = C[None, :] + D[idx] * t_hit[:, None]
        col = np.zeros((len(idx), 3), np.float32)
        lightv = np.zeros((len(idx), 3), np.float32)
        ao = np.ones(len(idx), np.float32)
        # --- wall sides ---
        m = kind == 1
        if m.any():
            sx_ = side[m]
            u = np.where(sx_ == 0, P[m, 1], P[m, 0])
            u = u - np.floor(u)
            z = P[m, 2]
            hh = hit_h[m]
            v = (WALL_H - z)  # texture v from the top of a full wall
            mats = self.mat[hit_cy[m], hit_cx[m]]
            c = np.where((mats == 1)[:, None], _sample(self.tex_wall[1], u, v), _sample(self.tex_wall[0], u, v))
            c = np.where((mats == 2)[:, None], _sample(self.tex_lava_wall, u, v), c)
            if self.tex_door is not None:
                c = np.where((mats == 3)[:, None], _sample(self.tex_door, u, np.clip(z / WALL_H, 0, 0.999) * -1 + 1), c)
            # base plinth (bottom 0.16) and cap trim on full-height walls
            base = z < 0.22
            if base.any():
                c[base] = _sample(self.tex_base, u[base], 1 - z[base] / 0.22)
            capm = (hh > WALL_H - 0.01) & (z > WALL_H - 0.14)
            if capm.any():
                c[capm] = _sample(self.tex_cap, u[capm], (WALL_H - z[capm]) / 0.14)
            # cut face shows a rough break line
            cutm = (hh < WALL_H - 0.01) & (z > hh - 0.03)
            c[cutm] *= 0.55
            # face orientation vs. a fixed key light from the north-west
            face = np.where(sx_ == 0, np.where(Dx[idx][m] > 0, 0.70, 1.0), np.where(Dy[idx][m] > 0, 0.82, 0.92))
            # floor contact shadow and soot toward the top
            occl = (0.50 + 0.50 * _smooth(0.0, 0.55, z)) * (1 - 0.25 * _smooth(0.8, WALL_H, z))
            col[m] = c
            ao[m] = face * occl
            # sample light just in front of the face
            nx = np.where(sx_ == 0, -np.sign(Dx[idx][m]), 0)
            ny = np.where(sx_ == 1, -np.sign(Dy[idx][m]), 0)
            lightv[m] = self._light_at(P[m, 0] + nx * 0.2, P[m, 1] + ny * 0.2) * (0.6 + 0.4 * _smooth(0, 1.0, z))[:, None]
        # --- wall tops ---
        m = kind == 2
        if m.any():
            col[m] = _sample(self.tex_top, P[m, 0] * 0.6, P[m, 1] * 0.6)
            cut = hit_h[m] < WALL_H - 0.01
            col[m] = np.where(cut[:, None], col[m] * 0.8 + np.array([0.03, 0.02, 0.015]), col[m])
            rim = self.rim[hit_cy[m], hit_cx[m]]
            # deep rock fades to a dark mass so the open rooms read first
            ao[m] = np.where(rim | cut, 0.85, 0.38)
            lightv[m] = self._light_at(P[m, 0], P[m, 1]) * 0.45
        # --- floor / lava ---
        m = kind == 3
        if m.any():
            fx, fy = P[m, 0], P[m, 1]
            ix = np.clip(np.floor(fx).astype(np.int32), 0, self.w - 1)
            iy = np.clip(np.floor(fy).astype(np.int32), 0, self.h - 1)
            lv = self.lava[iy, ix]
            c = _sample(self.tex_floor, fx * 0.5, fy * 0.5)
            flow = _sample(self.tex_lava, fx * 0.35 + now * 0.03, fy * 0.35 + now * 0.012)
            c = np.where(lv[:, None], flow, c)
            col[m] = c
            res = self.light_res
            ax_ = np.clip((fx * res).astype(np.int32), 0, self.w * res - 1)
            ay_ = np.clip((fy * res).astype(np.int32), 0, self.h * res - 1)
            ao[m] = np.where(lv, 1.0, self.floor_ao[ay_, ax_])
            lightv[m] = self._light_at(fx, fy)
            lightv[m] = np.where(lv[:, None], 1.6, lightv[m])  # lava is self-lit
        # player lantern: keeps the area around you readable
        if player_light:
            d = np.hypot(P[:, 0] - self.focus[0], P[:, 1] - self.focus[1])
            lightv += (np.clip(1 - d / 5.5, 0, 1) ** 1.6 * 0.55)[:, None] * np.array([1.0, 0.86, 0.68], np.float32)
        flick = 0.92 + 0.08 * math.sin(now * 11.0) * math.sin(now * 7.3 + 1.0)
        amb = np.array([0.30, 0.28, 0.31], np.float32)
        shade = amb + lightv * flick
        rgb = col * shade * ao[:, None]
        # distance fog
        fog = 1 - np.exp(-np.maximum(t_hit - 6.0, 0) / 22.0)
        rgb = rgb * (1 - fog[:, None]) + np.array([0.05, 0.035, 0.03], np.float32) * fog[:, None]
        out[idx] = rgb
        depth[idx] = t_hit  # D has unit forward component, so t is view depth
        out[~down] = np.array([0.04, 0.03, 0.03], np.float32)
        rgb8 = (np.clip(out, 0, 1) ** (1 / 1.08) * 255).astype(np.uint8).reshape(rh, rw, 3)
        self._last = (rw, rh, tan_h, tan_v, depth.reshape(rh, rw))
        return rgb8, depth.reshape(rh, rw)

    def _light_at(self, x, y):
        res = self.light_res
        ax = np.clip((x * res).astype(np.int32), 0, self.w * res - 1)
        ay = np.clip((y * res).astype(np.int32), 0, self.h * res - 1)
        return self.light[ay, ax]

    # ---------- sprites and picking ----------
    def project(self, wx, wy, wz=0.0):
        """World point -> (depth, sx, sy, px_per_tile) in the last render's pixels."""
        if not hasattr(self, "_last"):
            return None
        rw, rh, tan_h, tan_v, _depth = self._last
        q = np.array([wx, wy, wz], np.float32) - self.cam
        z = float(q @ self.f)
        if z < 0.2:
            return None
        x = float(q @ self.r) / (z * tan_h)
        y = float(q @ self.u) / (z * tan_v)
        sx = (x + 1) / 2 * rw
        sy = (1 - y) / 2 * rh
        return z, sx, sy, rh / (2 * z * tan_v)

    def visible(self, wx, wy, height=1.0):
        """True when the feet or the head of a body at (wx, wy) is not behind a wall."""
        rw, rh, _th, _tv, depth = self._last
        for wz in (0.1, height * 0.6, height):
            p = self.project(wx, wy, wz)
            if p is None:
                continue
            z, sx, sy, _ = p
            ix, iy = int(sx), int(sy)
            if 0 <= ix < rw and 0 <= iy < rh and depth[iy, ix] >= z - 0.45:
                return True
        return False

    def occluders(self, x0, y0, x1, y1, z):
        """Boolean mask (rows, cols) of render pixels inside the rect that are nearer than z.
        Draw a sprite, then re-blit the cached background through this mask so walls in front
        of it cover it (per-pixel occlusion)."""
        _rw, _rh, _th, _tv, depth = self._last
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(depth.shape[1], int(x1)), min(depth.shape[0], int(y1))
        if x1 <= x0 or y1 <= y0:
            return None, (x0, y0)
        return depth[y0:y1, x0:x1] < (z - 0.35), (x0, y0)

    def pick(self, sx, sy):
        """Render-pixel -> floor tile under it (walls resolve to the floor tile in front)."""
        rw, rh, tan_h, tan_v, depth = self._last
        x = (sx + 0.5) / rw * 2 - 1
        y = 1 - (sy + 0.5) / rh * 2
        D = self.f + x * tan_h * self.r + y * tan_v * self.u
        if D[2] >= -1e-4:
            return None
        t = float(depth[int(np.clip(sy, 0, rh - 1)), int(np.clip(sx, 0, rw - 1))])
        P = self.cam + D * min(t, self.cam[2] / -D[2])
        P = P - D / np.linalg.norm(D) * 0.05
        tx, ty = int(math.floor(P[0])), int(math.floor(P[1]))
        if 0 <= tx < self.w and 0 <= ty < self.h and not self.wall[ty, tx]:
            return tx, ty
        # clicked a wall face: step back toward the camera onto floor
        for k in range(1, 12):
            Q = P - D / np.linalg.norm(D) * (0.25 * k)
            tx, ty = int(math.floor(Q[0])), int(math.floor(Q[1]))
            if 0 <= tx < self.w and 0 <= ty < self.h and not self.wall[ty, tx]:
                return tx, ty
        return None
