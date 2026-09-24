"""
RuneScape-style discrete camera yaw for the Mythoscape client.

yaw 0 = world north up (default)
yaw 1 = world east up  (90° CW view)
yaw 2 = world south up
yaw 3 = world west up

Server stays in world coords; only presentation + local input remap.
"""
from __future__ import annotations


class CameraYaw:
    """Mixin / helper — Client holds camera_yaw and world size."""

    camera_yaw = 0  # 0..3

    def view_size(self):
        """Width/height of the map in *view* tile space."""
        w = int(getattr(self, "world_w", 0) or 0)
        h = int(getattr(self, "world_h", 0) or len(getattr(self, "tiles", []) or []))
        if self.camera_yaw % 2 == 0:
            return w, h
        return h, w

    def world_to_view(self, wx, wy):
        """Map a world tile to view-space tile under current yaw."""
        W = int(getattr(self, "world_w", 0) or 0)
        H = int(getattr(self, "world_h", 0) or len(getattr(self, "tiles", []) or []))
        yaw = int(self.camera_yaw) % 4
        wx, wy = int(wx), int(wy)
        if yaw == 0:
            return wx, wy
        if yaw == 1:
            return wy, W - 1 - wx
        if yaw == 2:
            return W - 1 - wx, H - 1 - wy
        return H - 1 - wy, wx

    def view_to_world(self, vx, vy):
        """Inverse of world_to_view."""
        W = int(getattr(self, "world_w", 0) or 0)
        H = int(getattr(self, "world_h", 0) or len(getattr(self, "tiles", []) or []))
        yaw = int(self.camera_yaw) % 4
        vx, vy = int(vx), int(vy)
        if yaw == 0:
            return vx, vy
        if yaw == 1:
            return W - 1 - vy, vx
        if yaw == 2:
            return W - 1 - vx, H - 1 - vy
        return vy, H - 1 - vx

    def rotate_move_delta(self, dx, dy):
        """
        Remap a screen-relative move (dx,dy) into world delta.
        Screen up (0,-1) should always move 'away from camera'.
        """
        yaw = int(self.camera_yaw) % 4
        if yaw == 0:
            return dx, dy
        if yaw == 1:
            # screen up = east → world (+1, 0); screen right = south → (0, +1)
            return -dy, dx
        if yaw == 2:
            return -dx, -dy
        # yaw 3: screen up = west → (-1,0); screen right = north → (0,-1)
        return dy, -dx

    def facing_for_view(self, world_facing):
        """
        Convert world-space facing into screen-relative facing for sprites.
        world_facing: 1 (east), -1 (west), 'front' (south), 'back' (north)
        """
        # Encode as 0=S, 1=W, 2=N, 3=E then subtract yaw
        order = ("front", -1, "back", 1)  # S W N E — indices 0..3
        # Map facing → index
        if world_facing == "front":
            idx = 0
        elif world_facing == -1 or world_facing == "-1":
            idx = 1
        elif world_facing == "back":
            idx = 2
        elif world_facing == 1 or world_facing == "1":
            idx = 3
        else:
            return world_facing
        view_idx = (idx - (int(self.camera_yaw) % 4)) % 4
        return order[view_idx]

    def rotate_camera(self, steps=1):
        """Rotate yaw by ±1 (or more). Returns new yaw."""
        self.camera_yaw = (int(self.camera_yaw) + int(steps)) % 4
        return self.camera_yaw

    def building_view_bounds(self, b):
        """AABB of a building footprint in view tile space."""
        corners = [
            (b["x0"], b["y0"]),
            (b["x1"], b["y0"]),
            (b["x0"], b["y1"]),
            (b["x1"], b["y1"]),
        ]
        vs = [self.world_to_view(x, y) for x, y in corners]
        xs = [p[0] for p in vs]
        ys = [p[1] for p in vs]
        return min(xs), min(ys), max(xs), max(ys)

    def yaw_label(self):
        return ("N", "E", "S", "W")[int(self.camera_yaw) % 4]
