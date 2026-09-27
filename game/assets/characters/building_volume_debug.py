"""
TEMPORARY world-space building geometry test (NO textures, NO farmhouse art).

One fixed volume in WORLD space with five unmistakable faces:

  FRONT (south) = RED    + label "FRONT"
  RIGHT (east)  = BLUE   + label "RIGHT"
  BACK  (north) = GREEN  + label "BACK"
  LEFT  (west)  = YELLOW + label "LEFT"
  TOP           = PURPLE

Camera yaw only selects which world faces project to the screen.
The volume never rotates / flips / mirrors to face the camera.
"""
from __future__ import annotations

import pygame

# World-space face ids (match camera_yaw convention: 0=S, 1=W, 2=N, 3=E)
FACE_S, FACE_W, FACE_N, FACE_E = 0, 1, 2, 3

# Debug colors (RGB)
COLOR_FRONT = (220, 40, 40)      # RED   — south
COLOR_RIGHT = (40, 90, 230)      # BLUE  — east
COLOR_BACK = (40, 180, 70)       # GREEN — north
COLOR_LEFT = (230, 210, 40)      # YELLOW — west
COLOR_TOP = (150, 60, 200)       # PURPLE

FACE_COLOR = {
    FACE_S: COLOR_FRONT,
    FACE_E: COLOR_RIGHT,
    FACE_N: COLOR_BACK,
    FACE_W: COLOR_LEFT,
}

FACE_LABEL = {
    FACE_S: "FRONT",
    FACE_E: "RIGHT",
    FACE_N: "BACK",
    FACE_W: "LEFT",
}


def visible_roles(yaw: int):
    """
    Map camera yaw → which WORLD faces fill screen roles.

    yaw 0: looking from south → screen-front = SOUTH (FRONT/red)
    yaw 1: looking from west  → screen-front = WEST  (LEFT/yellow)
    yaw 2: looking from north → screen-front = NORTH (BACK/green)
    yaw 3: looking from east  → screen-front = EAST  (RIGHT/blue)

    Screen-right side is the world face clockwise from front when viewed
    from outside (toward the building).
    """
    yaw = int(yaw) % 4
    front = yaw                          # world face facing camera
    side_right = (yaw - 1) % 4           # world face on screen-right
    side_left = (yaw + 1) % 4            # world face on screen-left (thin)
    back = (yaw + 2) % 4                 # culled
    return front, side_right, side_left, back


def _fill(dest, pts, rgb, shade=0):
    if len(pts) < 3:
        return
    c = tuple(max(0, min(255, v + shade)) for v in rgb)
    pygame.draw.polygon(dest, c, pts)
    pygame.draw.polygon(dest, (20, 16, 18), pts, 2)


def _label(dest, text, cx, cy, *, color=(255, 255, 255)):
    font = pygame.font.SysFont(None, 22, bold=True)
    img = font.render(text, True, color)
    # Dark plate behind text so label stays readable on any face color
    pad = 3
    plate = pygame.Surface((img.get_width() + pad * 2, img.get_height() + pad * 2), pygame.SRCALPHA)
    plate.fill((0, 0, 0, 180))
    dest.blit(plate, (cx - plate.get_width() // 2, cy - plate.get_height() // 2))
    dest.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))


def draw_debug_volume(dest, footprint: pygame.Rect, *, yaw: int = 0):
    """
    Draw the world-fixed debug volume into a screen rect for the footprint.

    footprint is already the building's view-space AABB on screen (pixels).
    yaw selects visibility — it does NOT rotate the building.
    """
    if footprint.w < 16 or footprint.h < 16:
        return

    front, side_r, side_l, _back = visible_roles(yaw)

    fx, fy, fw, fh = footprint.x, footprint.y, footprint.w, footprint.h

    # Oblique metrics — depth expressed in SCREEN space from the projector,
    # but WHICH face fills each slot comes from world face ids above.
    left_lip = max(10, int(fw * 0.10))
    side_w = max(22, int(fw * 0.28))
    front_w = max(20, fw - left_lip - side_w)
    dy = max(16, int(fh * 0.26))
    wall_top = fy + int(fh * 0.18)
    ground = fy + fh
    ox = fx + left_lip

    # Screen quads for the three visible vertical roles + top
    # LEFT lip (screen-left)
    sl_top = (fx, wall_top - int(dy * 0.55))
    sl_bot = (fx, ground)
    fl = (ox, wall_top)
    bl = (ox, ground)
    left_pts = [fl, sl_top, sl_bot, bl]

    # FRONT (screen-bottom facade)
    fr = (ox + front_w, wall_top)
    br = (ox + front_w, ground)
    front_pts = [fl, fr, br, bl]

    # RIGHT side (screen-right depth)
    sr_top = (ox + front_w + side_w, wall_top - dy)
    sr_bot = (ox + front_w + side_w, ground)
    right_pts = [fr, sr_top, sr_bot, br]

    # TOP (covers the extruded volume)
    peak_h = max(18, int(fh * 0.32))
    pf = (ox + front_w // 2, wall_top - peak_h)
    # Back ridge toward the far depth edge
    pb = (ox + front_w + side_w // 2, wall_top - peak_h - int(dy * 0.45))
    left_eave = (ox - 4, wall_top)
    right_eave = (ox + front_w + 4, wall_top)
    right_back = (ox + front_w + side_w, wall_top - dy)
    left_back = (fx + 4, wall_top - int(dy * 0.55))
    # Flat-ish top deck (purple) proving TOP is its own surface
    top_pts = [left_eave, right_eave, right_back, left_back]

    # Draw order: far → near for occlusion (left lip, right side, front, then top)
    # LEFT world face → screen-left lip
    _fill(dest, left_pts, FACE_COLOR[side_l], shade=-35)
    # RIGHT world face → screen-right side
    _fill(dest, right_pts, FACE_COLOR[side_r], shade=-25)
    # FRONT world face → screen-front
    _fill(dest, front_pts, FACE_COLOR[front], shade=0)
    # TOP always purple (world-fixed top surface)
    _fill(dest, top_pts, COLOR_TOP, shade=0)
    # Simple roof ridges for readability
    pygame.draw.line(dest, (90, 30, 120), left_eave, right_eave, 2)
    pygame.draw.line(dest, (90, 30, 120), right_eave, right_back, 2)

    # Labels on the three visible vertical faces (prove they're different surfaces)
    # Front label center
    _label(
        dest, FACE_LABEL[front],
        ox + front_w // 2,
        wall_top + (ground - wall_top) // 2,
    )
    # Right-side label (along parallelogram)
    _label(
        dest, FACE_LABEL[side_r],
        fr[0] + side_w // 2,
        wall_top + (ground - wall_top) // 2 - dy // 3,
    )
    # Left-side label
    _label(
        dest, FACE_LABEL[side_l],
        fx + left_lip // 2,
        wall_top + (ground - wall_top) // 2 - dy // 5,
    )
    # Top marker
    _label(dest, "TOP", (left_eave[0] + right_back[0]) // 2, (wall_top + right_back[1]) // 2 - 4)

    # Yaw readout — camera changes; building rotation stays 0
    yaw_deg = (int(yaw) % 4) * 90
    expect = {
        0: "expect FRONT (RED) near — door face",
        1: "expect LEFT (YELLOW) near",
        2: "expect BACK (GREEN) near — NO door",
        3: "expect RIGHT (BLUE) near",
    }[int(yaw) % 4]
    font = pygame.font.SysFont(None, 18, bold=True)
    lines = [
        f"CAMERA YAW: {yaw_deg}°  (step {int(yaw) % 4})",
        "BUILDING ROTATION: 0°  (MUST stay 0)",
        expect,
    ]
    y = fy + 4
    for line in lines:
        img = font.render(line, True, (255, 255, 255))
        plate = pygame.Surface((img.get_width() + 6, img.get_height() + 2), pygame.SRCALPHA)
        plate.fill((0, 0, 0, 170))
        dest.blit(plate, (fx, y))
        dest.blit(img, (fx + 3, y + 1))
        y += img.get_height() + 4
