"""
Volumetric skeletal humanoid — stylized low-poly fantasy character.

Anatomical forms (not stick+circles): jaw/skull, neck, shouldered torso,
tapered limbs with mid-bulge, planted boots, garment-shaped clothing,
equipment seated on the body. Directional light from upper-left.
"""
from __future__ import annotations

import math
import pygame

import rs_style as rs


def _weapon_kind(weapon, weapon_id):
    if weapon:
        return weapon
    if not weapon_id:
        return None
    if "dagger" in weapon_id:
        return "dagger"
    if "pickaxe" in weapon_id:
        return "pickaxe"
    if "battleaxe" in weapon_id or "cleaver" in weapon_id:
        return "battleaxe"
    if "axe" in weapon_id:
        return "axe"
    if "staff" in weapon_id:
        return "staff"
    if "bow" in weapon_id:
        return "bow"
    return "sword"


def _draw_weapon(surf, hx, hy, s, kind, facing, item_id, swing):
    outline = rs.OUTLINE
    light, mid, dark, _ = rs.metal_palette(item_id)
    ang = -0.55 * facing + swing * 1.0 * facing
    c, sn = math.cos(ang), math.sin(ang)
    ws = s * 0.98

    def R(px, py):
        x = px * ws
        y = py * ws
        return hx + (x * c - y * sn) * facing, hy + (x * sn + y * c)

    if not kind:
        return
    wood = (118, 82, 48)
    wood_d = (78, 52, 28)
    if kind == "dagger":
        rs.draw_volume(surf, mid, [R(0, 1), R(1.9, 0), R(2.1, -10), R(0, -13), R(-2.1, -10), R(-1.9, 0)], outline, 1)
        rs.draw_poly(surf, dark, [R(-3.4, 1), R(3.4, 1), R(3.8, 3.2), R(-3.8, 3.2)], outline, 1)
        rs.draw_poly(surf, wood, [R(-1.4, 3.2), R(1.4, 3.2), R(1.15, 6.2), R(-1.15, 6.2)], outline, 1)
    elif kind == "battleaxe":
        rs.draw_poly(surf, wood_d, [R(-1.4, 2), R(1.4, 2), R(1.5, -13), R(-1.5, -13)], outline, 1)
        rs.draw_volume(surf, mid, [R(0, -8), R(8, -12), R(9, -5), R(6.5, -2), R(1, -4)], outline, 1)
        rs.draw_poly(surf, light, [R(1.5, -9.5), R(6.2, -10.5), R(6.2, -6)], None, 0)
    elif kind == "axe":
        rs.draw_poly(surf, wood_d, [R(-1.35, 2), R(1.35, 2), R(1.45, -14), R(-1.45, -14)], outline, 1)
        rs.draw_volume(surf, mid, [R(0, -9), R(8.5, -12.5), R(8.2, -4), R(0.8, -5)], outline, 1)
        rs.draw_poly(surf, light, [R(1, -10.5), R(6.2, -11.5), R(6.2, -6)], None, 0)
    elif kind == "pickaxe":
        rs.draw_poly(surf, wood_d, [R(-1.35, 2), R(1.35, 2), R(1.45, -15), R(-1.45, -15)], outline, 1)
        rs.draw_volume(surf, mid, [R(-8.5, -12.5), R(8.5, -12.5), R(7.2, -8.2), R(-7.2, -8.2)], outline, 1)
        rs.draw_poly(surf, light, [R(-5.5, -12.5), R(0, -14.2), R(5.5, -12.5)], None, 0)
    elif kind == "staff":
        rs.draw_poly(surf, wood, [R(-1.5, 3), R(1.5, 3), R(1.7, -18), R(-1.7, -18)], outline, 1)
        pygame.draw.circle(surf, (180, 120, 220), (int(R(0, -19)[0]), int(R(0, -19)[1])), max(3, int(3.1 * ws)))
        pygame.draw.circle(surf, (240, 200, 255), (int(R(-0.6, -19.6)[0]), int(R(-0.6, -19.6)[1])), max(1, int(1.3 * ws)))
    elif kind == "bow":
        rs.draw_poly(surf, wood, [R(-0.8, 4), R(0.8, 4), R(1.2, -14), R(-1.2, -14)], outline, 1)
        rs.draw_poly(surf, wood_d, [
            R(-4, -2), R(-1, -14), R(1, -14), R(0.5, -1),
        ], outline, 1)
        pygame.draw.line(surf, (200, 190, 160), R(-3.5, -3), R(-0.5, 3), max(1, int(ws * 0.4)))
    else:
        # Bevelled sword: shade edge, mid face, lit edge, guard, grip, pommel
        rs.draw_poly(surf, dark, [R(0, 1), R(2.0, 0), R(2.1, -13), R(0, -16.5), R(-2.1, -13), R(-2.0, 0)], outline, 1)
        rs.draw_poly(surf, mid, [R(0, 0.5), R(1.55, 0), R(1.65, -12.5), R(0, -15.5), R(-0.4, -12.5), R(-0.3, 0)], None, 0)
        rs.draw_poly(surf, light, [R(0.15, -1), R(1.2, -1), R(1.25, -12), R(0.2, -14)], None, 0)
        rs.draw_poly(surf, dark, [R(-4.0, 0), R(4.0, 0), R(4.4, 2.1), R(-4.4, 2.1)], outline, 1)
        rs.draw_poly(surf, wood, [R(-1.25, 2.1), R(1.25, 2.1), R(1.05, 5.8), R(-1.05, 5.8)], outline, 1)
        pygame.draw.circle(surf, (220, 190, 80), (int(R(0, 6.2)[0]), int(R(0, 6.2)[1])), max(2, int(1.35 * ws)))


def _draw_shield(surf, sx, sy, s, item_id):
    light, mid, dark, outline = rs.metal_palette(item_id)
    ss = s * 0.92
    if item_id and "wood" in item_id:
        mid, dark, light = (140, 95, 55), (90, 60, 35), (180, 130, 80)
    if item_id and "sq" in item_id:
        rs.draw_volume(surf, mid, [
            (sx - 7 * ss, sy - 6.5 * ss), (sx + 7 * ss, sy - 6.5 * ss),
            (sx + 7 * ss, sy + 8 * ss), (sx - 7 * ss, sy + 8 * ss),
        ], outline, 1)
        rs.draw_poly(surf, light, [
            (sx - 5.5 * ss, sy - 5 * ss), (sx + 0.5 * ss, sy - 5 * ss),
            (sx + 0.5 * ss, sy + 0.5 * ss), (sx - 5.5 * ss, sy + 0.5 * ss),
        ], None, 0)
        pygame.draw.circle(surf, dark, (int(sx), int(sy + 0.5 * ss)), max(2, int(1.4 * ss)))
    else:
        rs.draw_volume(surf, mid, [
            (sx - 6 * ss, sy - 8 * ss), (sx + 6 * ss, sy - 8 * ss),
            (sx + 7.5 * ss, sy), (sx, sy + 11 * ss), (sx - 7.5 * ss, sy),
        ], outline, 1)
        rs.draw_poly(surf, light, [
            (sx - 4 * ss, sy - 6.5 * ss), (sx + 1.2 * ss, sy - 6.5 * ss),
            (sx + 2.2 * ss, sy - 0.8 * ss), (sx - 4 * ss, sy + 0.2 * ss),
        ], None, 0)
        if item_id and "wood" not in (item_id or ""):
            red = (180, 45, 45)
            pygame.draw.line(surf, red, (sx, sy - 5.5 * ss), (sx, sy + 7 * ss), max(2, int(ss * 0.7)))
            pygame.draw.line(surf, red, (sx - 4.5 * ss, sy - 1 * ss), (sx + 4.5 * ss, sy - 1 * ss), max(2, int(ss * 0.7)))


def _draw_helmet(surf, hx, hy, s, item_id):
    light, mid, dark, outline = rs.metal_palette(item_id)
    rs.draw_volume(surf, mid, [
        (hx - 6.2 * s, hy + 1.2 * s), (hx - 5 * s, hy - 5 * s),
        (hx, hy - 7.2 * s), (hx + 5 * s, hy - 5 * s), (hx + 6.2 * s, hy + 1.2 * s),
        (hx + 4 * s, hy + 3.2 * s), (hx - 4 * s, hy + 3.2 * s),
    ], outline, 1)
    rs.draw_poly(surf, light, [
        (hx - 3.2 * s, hy - 4.2 * s), (hx, hy - 6.4 * s), (hx + 1.8 * s, hy - 3.2 * s),
    ], None, 0)
    pygame.draw.line(surf, dark, (hx - 3.6 * s, hy + 0.2 * s), (hx + 3.6 * s, hy + 0.2 * s), max(2, int(s)))
    rs.draw_poly(surf, dark, [
        (hx - 5.5 * s, hy + 0.5 * s), (hx - 3.5 * s, hy + 0.5 * s),
        (hx - 3.2 * s, hy + 3.5 * s), (hx - 5.2 * s, hy + 2.8 * s),
    ], None, 0)


def _draw_boot(surf, fx, fy, s, facing, boots_base, outline):
    """Planted boot: sole contact + upper with lit toe, slight asymmetry."""
    sole = [
        (fx - 2.4 * s * facing, fy + 0.35 * s),
        (fx + 3.6 * s * facing, fy + 0.15 * s),
        (fx + 3.8 * s * facing, fy + 2.55 * s),
        (fx - 2.0 * s * facing, fy + 2.7 * s),
    ]
    rs.draw_volume(surf, rs.shade(boots_base, -18), sole, outline, 1)
    upper = [
        (fx - 1.7 * s * facing, fy - 2.1 * s),
        (fx + 1.5 * s * facing, fy - 2.4 * s),
        (fx + 2.6 * s * facing, fy + 0.4 * s),
        (fx + 0.2 * s * facing, fy + 0.9 * s),
        (fx - 1.9 * s * facing, fy + 0.55 * s),
    ]
    rs.draw_volume(surf, boots_base, upper, outline, 1)
    # Toe highlight
    rs.draw_poly(surf, rs.shade(boots_base, 28), [
        (fx + 0.8 * s * facing, fy - 1.2 * s),
        (fx + 2.2 * s * facing, fy - 1.5 * s),
        (fx + 2.5 * s * facing, fy + 0.1 * s),
        (fx + 1.0 * s * facing, fy + 0.3 * s),
    ], None, 0)


def _draw_hand(surf, hx, hy, s, skin_m, skin_l, outline):
    """Palm + slight finger mass (readable at gameplay scale)."""
    rs.draw_volume(surf, skin_m, [
        (hx - 1.5 * s, hy - 1.1 * s), (hx + 1.6 * s, hy - 1.0 * s),
        (hx + 1.8 * s, hy + 1.3 * s), (hx + 0.3 * s, hy + 2.0 * s),
        (hx - 1.4 * s, hy + 1.2 * s),
    ], outline, 1)
    pygame.draw.circle(surf, skin_l, (int(hx - 0.35 * s), int(hy - 0.35 * s)), max(1, int(0.65 * s)))


def draw_skeletal_humanoid(
    surf, cx, cy, tile,
    body_color=(70, 120, 210),
    skin_color=(235, 195, 150),
    hair_color=(70, 45, 30),
    weapon=None, shield=False, moving=False, t=0.0,
    robe=False, facing=1, equipment=None, attacking=0.0,
):
    """Anatomical adventurer with volumetric limbs and directional lighting."""
    equipment = equipment or {}
    facing = 1 if facing >= 0 else -1
    s = rs.unit(tile, "character")
    pose = rs.resolve_pose(moving, t, attacking, facing)
    cape_sway = pose.get("cape", 0.0)

    body_id = equipment.get("body")
    legs_id = equipment.get("legs")
    shield_id = equipment.get("shield")
    weapon_id = equipment.get("weapon")
    helmet_id = equipment.get("helmet")
    wkind = _weapon_kind(weapon, weapon_id)
    if shield_id:
        shield = True

    shirt_base = body_color
    if body_id and (
        "leather" in body_id or "chain" in body_id or "plate" in body_id
        or body_id.endswith("_body") or body_id == "goblin_mail"
    ):
        _, shirt_base, _, _ = rs.metal_palette(body_id)
        shirt_l, shirt_m, shirt_d, _ = rs.metal_palette(body_id)
    else:
        shirt_l, shirt_m, shirt_d = rs.shade(body_color, 32), body_color, rs.shade(body_color, -48)

    pants_base = (72, 74, 82)
    if legs_id:
        _, pants_base, _, _ = rs.metal_palette(legs_id)
        pants_l, pants_m, pants_d, _ = rs.metal_palette(legs_id)
    else:
        pants_l, pants_m, pants_d = (96, 98, 106), pants_base, (48, 50, 56)

    skin_l, skin_m, skin_d = rs.shade(skin_color, 26), skin_color, rs.shade(skin_color, -40)
    hair_m, hair_d = hair_color, rs.shade(hair_color, -36)
    boots_base = (92, 62, 38)
    outline = rs.OUTLINE

    bob = pose["root_bob"] * s
    pelvis = (cx, cy + 3.2 * s + bob)
    torso_len = 13.5 * s
    arm_len, leg_len = 11.6 * s, 13.6 * s
    neck = rs.joint(
        pelvis[0], pelvis[1] - 1.5 * s,
        -math.pi / 2 + (pose["torso"] - rs.DOWN) * 0.28,
        torso_len,
    )

    hip_l = (pelvis[0] - 2.5 * s, pelvis[1] + 0.2 * s)
    hip_r = (pelvis[0] + 2.5 * s, pelvis[1] + 0.2 * s)
    if facing < 0:
        hip_l, hip_r = hip_r, hip_l

    # Slight knee bend on down phase for weight
    knee_bend_l = 0.12 if pose["root_bob"] > 0.9 else 0.04
    knee_bend_r = 0.12 if pose["root_bob"] > 0.9 else 0.04
    knee_l = rs.joint(*hip_l, pose["leg_l"] + knee_bend_l, leg_len * 0.5)
    knee_r = rs.joint(*hip_r, pose["leg_r"] + knee_bend_r, leg_len * 0.5)
    foot_l = rs.joint(*knee_l, pose["leg_l"] + 0.06, leg_len * 0.5)
    foot_r = rs.joint(*knee_r, pose["leg_r"] - 0.02, leg_len * 0.5)
    foot_y = max(foot_l[1], foot_r[1]) + 2.4 * s

    # Ground plant: tight contact + soft cast
    rs.draw_contact_shadow(surf, cx, foot_y, 8.5 * s, 3.2 * s, 150)
    rs.draw_cast_shadow(surf, cx + 1.5 * s, foot_y + 0.5 * s, 11.5 * s, 3.6 * s, 95)

    # --- Cape (behind body, secondary motion) ---
    if robe or (body_id and "cape" in (body_id or "")):
        cape_col = rs.shade(body_color, -22)
        sway = cape_sway * 4 * s * facing
        cape = [
            (neck[0] - 4.5 * s, neck[1] + 2.5 * s),
            (neck[0] + 4.2 * s, neck[1] + 2.5 * s),
            (pelvis[0] + 7.5 * s + sway, pelvis[1] + 10 * s),
            (pelvis[0] + 1 * s + sway * 0.5, pelvis[1] + 12 * s),
            (pelvis[0] - 6.5 * s + sway * 0.3, pelvis[1] + 10 * s),
        ]
        rs.draw_volume(surf, cape_col, cape, outline, 1)

    # --- Legs (far then near) ---
    far_leg = (foot_l, knee_l, hip_l) if facing > 0 else (foot_r, knee_r, hip_r)
    near_leg = (foot_r, knee_r, hip_r) if facing > 0 else (foot_l, knee_l, hip_l)
    for foot, knee, hip in (far_leg, near_leg):
        # Thigh (wider) + calf (narrower) — separate garment legs
        rs.draw_volume_limb(surf, *hip, *knee, 2.15 * s, pants_base, outline, taper=0.82, bulge=0.14)
        rs.draw_volume_limb(surf, *knee, *foot, 1.75 * s, pants_base, outline, taper=0.72, bulge=0.08)
        # Knee joint read
        pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.3 * s), int(knee[1] - 0.3 * s)), max(1, int(1.0 * s)))
        _draw_boot(surf, *foot, s, facing, boots_base, outline)

    # Hip / belt
    belt = [
        (pelvis[0] - 4.4 * s, pelvis[1] - 0.8 * s),
        (pelvis[0] + 4.4 * s, pelvis[1] - 0.8 * s),
        (pelvis[0] + 3.6 * s, pelvis[1] + 2.8 * s),
        (pelvis[0] - 3.6 * s, pelvis[1] + 2.8 * s),
    ]
    rs.draw_volume(surf, pants_base if not robe else rs.shade(body_color, -10), belt, outline, 1)
    # Belt buckle
    pygame.draw.rect(surf, (200, 170, 70), (pelvis[0] - 1.1 * s, pelvis[1] - 0.2 * s, 2.2 * s, 1.6 * s))

    # Robe hem (widens toward ground)
    if robe:
        hem = [
            (pelvis[0] - 4.2 * s, pelvis[1] + 0.5 * s),
            (pelvis[0] + 4.2 * s, pelvis[1] + 0.5 * s),
            (pelvis[0] + 7.2 * s + cape_sway * s, pelvis[1] + 9.5 * s),
            (pelvis[0] - 7.2 * s + cape_sway * 0.5 * s, pelvis[1] + 9.5 * s),
        ]
        rs.draw_volume(surf, rs.shade(body_color, -8), hem, outline, 1)

    # Side plane (¾ body read — darker away from light)
    side = [
        (neck[0] + 4.8 * s * facing, neck[1] + 1.8 * s),
        (neck[0] + 6.0 * s * facing, neck[1] + 2.8 * s),
        (pelvis[0] + 5.0 * s * facing, pelvis[1]),
        (pelvis[0] + 3.7 * s * facing, pelvis[1]),
    ]
    rs.draw_poly(surf, shirt_d, side, outline, 1)

    # Chest — shoulders wide, waist narrow (garment, not rectangle)
    chest = [
        (pelvis[0] - 3.6 * s, pelvis[1] - 0.2 * s),
        (pelvis[0] + 3.4 * s, pelvis[1] - 0.2 * s),
        (neck[0] + 5.6 * s, neck[1] + 2.2 * s),
        (neck[0] + 2.0 * s, neck[1] + 1.0 * s),
        (neck[0] - 2.0 * s, neck[1] + 1.0 * s),
        (neck[0] - 5.6 * s, neck[1] + 2.2 * s),
    ]
    rs.draw_volume(surf, shirt_base, chest, outline, max(1, int(s * 0.35)))
    # Upper-left chest highlight plane
    rs.draw_poly(surf, shirt_l, [
        (pelvis[0] - 2.6 * s, pelvis[1] - 0.8 * s),
        (pelvis[0] - 0.1 * s, pelvis[1] - 0.8 * s),
        (neck[0] - 0.4 * s, neck[1] + 3.8 * s),
        (neck[0] - 4.0 * s, neck[1] + 3.5 * s),
    ], None, 0)
    # Deltoids
    pygame.draw.circle(surf, shirt_m, (int(neck[0] - 4.8 * s), int(neck[1] + 3.2 * s)), max(2, int(2.4 * s)))
    pygame.draw.circle(surf, shirt_l, (int(neck[0] - 5.3 * s), int(neck[1] + 2.5 * s)), max(1, int(1.3 * s)))
    pygame.draw.circle(surf, shirt_d, (int(neck[0] + 4.8 * s), int(neck[1] + 3.2 * s)), max(2, int(2.4 * s)))
    # Collar
    rs.draw_poly(surf, shirt_l, [
        (neck[0] - 2.3 * s, neck[1] + 2.0 * s),
        (neck[0] + 2.1 * s, neck[1] + 2.0 * s),
        (neck[0] + 1.3 * s, neck[1] + 4.6 * s),
        (neck[0] - 1.5 * s, neck[1] + 4.6 * s),
    ], None, 0)
    if body_id and "plate" in body_id:
        # Layered plate ridges
        for i in range(3):
            yy = neck[1] + (5.0 + i * 2.6) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3.2 * s, yy), (pelvis[0] + 3.2 * s, yy), max(1, int(s * 0.45)))
            pygame.draw.line(surf, shirt_l, (pelvis[0] - 3.0 * s, yy - 0.6 * s), (pelvis[0] + 1.5 * s, yy - 0.6 * s), 1)
    elif body_id and "chain" in body_id:
        for i in range(4):
            yy = neck[1] + (4.2 + i * 2.2) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3 * s, yy), (pelvis[0] + 3 * s, yy), 1)

    # Arms
    sh_l = (neck[0] - 5.2 * s, neck[1] + 3.0 * s)
    sh_r = (neck[0] + 5.2 * s, neck[1] + 3.0 * s)
    if facing < 0:
        sh_l, sh_r = sh_r, sh_l
        pose_arm_far, pose_arm_near = pose["arm_r"], pose["arm_l"]
    else:
        pose_arm_far, pose_arm_near = pose["arm_l"], pose["arm_r"]

    el_far = rs.joint(*sh_l, pose_arm_far, arm_len * 0.5)
    hand_far = rs.joint(*el_far, pose_arm_far + 0.1, arm_len * 0.5)
    el_near = rs.joint(*sh_r, pose_arm_near, arm_len * 0.5)
    hand_near = rs.joint(*el_near, pose_arm_near - 0.06 + pose["weapon"] * 0.15, arm_len * 0.55)

    # Far arm (sleeve → forearm skin)
    rs.draw_volume_limb(surf, *sh_l, *el_far, 1.75 * s, shirt_base, outline, taper=0.8, bulge=0.1)
    rs.draw_volume_limb(surf, *el_far, *hand_far, 1.45 * s, skin_m, outline, taper=0.75, bulge=0.06)
    _draw_hand(surf, *hand_far, s * 0.95, skin_m, skin_l, outline)

    if shield:
        _draw_shield(
            surf,
            hand_far[0] + 0.5 * s * facing,
            hand_far[1] - 0.2 * s,
            s * 0.9,
            shield_id or "wooden_shield",
        )

    # Neck
    hx, hy = neck[0] + 0.2 * s * facing, neck[1] - 0.5 * s
    rs.draw_volume(surf, skin_m, [
        (hx - 1.4 * s, hy + 0.5 * s), (hx + 1.4 * s, hy + 0.5 * s),
        (hx + 1.2 * s, hy + 3.6 * s), (hx - 1.2 * s, hy + 3.6 * s),
    ], outline, 1)

    if helmet_id:
        _draw_helmet(surf, hx, hy, s * 0.84, helmet_id)
    else:
        # Skull + jaw (irregular, not a circle)
        skull = [
            (hx - 2.9 * s, hy + 0.3 * s),
            (hx - 2.7 * s, hy - 2.6 * s),
            (hx - 1.0 * s, hy - 4.0 * s),
            (hx + 1.0 * s, hy - 4.1 * s),
            (hx + 2.5 * s, hy - 3.2 * s),
            (hx + 3.2 * s, hy - 1.0 * s),
            (hx + 2.9 * s, hy + 1.8 * s),
            (hx + 1.4 * s, hy + 3.0 * s),
            (hx - 0.8 * s, hy + 3.1 * s),
            (hx - 2.6 * s, hy + 1.7 * s),
        ]
        rs.draw_volume(surf, skin_m, skull, outline, 1)
        # Face plane (lit) — keep clear of hair so eyes read
        rs.draw_poly(surf, skin_l, [
            (hx - 1.2 * s * facing, hy - 1.8 * s),
            (hx + 2.1 * s * facing, hy - 1.6 * s),
            (hx + 2.3 * s * facing, hy + 1.6 * s),
            (hx - 0.3 * s * facing, hy + 2.0 * s),
        ], None, 0)
        # Nose bridge
        pygame.draw.line(
            surf, skin_d,
            (hx + 0.7 * s * facing, hy - 0.9 * s),
            (hx + 1.5 * s * facing, hy + 0.7 * s),
            max(1, int(s * 0.5)),
        )
        # Hair — crown + bangs that don't cover the eye band
        rs.draw_volume(surf, hair_m, [
            (hx - 3.2 * s, hy - 0.8 * s),
            (hx - 2.6 * s, hy - 3.8 * s),
            (hx + 0.2 * s, hy - 4.6 * s),
            (hx + 2.6 * s, hy - 3.8 * s),
            (hx + 3.2 * s, hy - 0.6 * s),
            (hx + 2.0 * s, hy - 1.4 * s),
            (hx - 2.2 * s, hy - 1.4 * s),
        ], hair_d, 1)
        # Side lock asymmetry
        rs.draw_poly(surf, hair_d, [
            (hx + 2.4 * s * facing, hy - 0.8 * s),
            (hx + 3.5 * s * facing, hy + 0.6 * s),
            (hx + 2.0 * s * facing, hy + 0.9 * s),
        ], None, 0)
        # Ear
        rs.draw_poly(surf, skin_d, [
            (hx - 2.7 * s * facing, hy - 0.5 * s),
            (hx - 3.7 * s * facing, hy - 1.0 * s),
            (hx - 3.5 * s * facing, hy + 0.6 * s),
            (hx - 2.7 * s * facing, hy + 1.1 * s),
        ], outline, 1)
        # Eyes — bright sclera so they don't collapse to a dark bar
        eye_y = hy - 0.05 * s
        for ex in (-1.15, 1.25):
            exx = hx + ex * s * facing
            pygame.draw.ellipse(surf, (250, 248, 240), (exx - 0.55 * s, eye_y - 0.42 * s, 1.1 * s, 0.85 * s))
            pygame.draw.ellipse(surf, outline, (exx - 0.55 * s, eye_y - 0.42 * s, 1.1 * s, 0.85 * s), max(1, int(s * 0.25)))
            pygame.draw.circle(surf, (55, 90, 130), (int(exx + 0.12 * s * facing), int(eye_y)), max(1, int(0.35 * s)))
            pygame.draw.circle(surf, (20, 22, 28), (int(exx + 0.15 * s * facing), int(eye_y)), max(1, int(0.18 * s)))
            pygame.draw.circle(surf, (255, 255, 255), (int(exx - 0.15 * s), int(eye_y - 0.2 * s)), max(1, int(0.12 * s)))
        # Brow
        pygame.draw.line(surf, hair_d, (hx - 1.5 * s, hy - 1.05 * s), (hx - 0.3 * s, hy - 1.15 * s), max(1, int(s * 0.35)))
        pygame.draw.line(surf, hair_d, (hx + 0.4 * s, hy - 1.15 * s), (hx + 1.6 * s, hy - 1.0 * s), max(1, int(s * 0.35)))
        # Mouth
        pygame.draw.line(surf, (140, 80, 75), (hx - 0.7 * s, hy + 1.7 * s), (hx + 0.9 * s, hy + 1.75 * s), max(1, int(s * 0.35)))

    # Near arm + weapon (drawn last so it overlays torso)
    rs.draw_volume_limb(surf, *sh_r, *el_near, 1.75 * s, shirt_base, outline, taper=0.8, bulge=0.1)
    rs.draw_volume_limb(surf, *el_near, *hand_near, 1.45 * s, skin_m, outline, taper=0.75, bulge=0.06)
    _draw_hand(surf, *hand_near, s, skin_m, skin_l, outline)
    if wkind:
        _draw_weapon(surf, hand_near[0], hand_near[1], s, wkind, facing, weapon_id, pose["weapon"])
