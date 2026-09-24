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


def _parse_facing(facing):
    """Return (view, side) with view in side|front|back and side ±1 for profile."""
    if isinstance(facing, str):
        key = facing.strip().lower()
        if key in ("front", "south", "s", "down"):
            return "front", 1
        if key in ("back", "north", "n", "up"):
            return "back", 1
        if key in ("west", "w", "left"):
            return "side", -1
        return "side", 1
    try:
        val = float(facing)
    except (TypeError, ValueError):
        return "side", 1
    if val <= -1.5:
        return "back", 1
    if val >= 1.5:
        return "front", 1
    return "side", (1 if val >= 0 else -1)


def _weapon_kind(weapon, weapon_id):
    # Prefer an explicit style string from the client (e.g. "battleaxe").
    # Booleans like True only mean "has a weapon" — resolve from item id.
    if isinstance(weapon, str) and weapon:
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
    if "rod" in weapon_id or "fish" in weapon_id:
        return "rod"
    return "sword"


def _draw_weapon(surf, hx, hy, s, kind, facing, item_id, swing, sheathed=False, back_view=False):
    """Equipped weapon with bevelled metal, fuller, wrapped grip, and pommel."""
    outline = rs.OUTLINE
    base, shadow, highlight, _ = rs.metal_palette(item_id)
    hi, face, sh, deep = highlight, base, shadow, rs.shade(shadow, -28)
    gold = (228, 196, 78)
    gold_d = (160, 120, 40)
    gold_l = (255, 230, 140)
    # Sheathed on the back — tip high over the far shoulder, grip by the near hip.
    # Otherwise idle tip-down / axe head-up, blending into the strike arc in combat.
    if sheathed:
        combat = 0.0
        # Near-vertical tip-up on the far/back side (local −Y upward)
        if kind in ("battleaxe", "axe", "pickaxe", "staff"):
            rest = -0.12
        elif kind == "bow":
            rest = -0.20
        else:
            rest = -0.08
        ang = rest * facing
        ws = s * 1.08
    else:
        combat = max(0.0, min(1.0, abs(float(swing or 0.0)) / 0.55))
        if kind == "bow":
            # Upright bow in front of the body; swing encodes draw amount
            combat = max(0.0, min(1.2, abs(float(swing or 0.0))))
            ang = -0.12 * facing
            ws = s * 1.05
            hx = hx + 0.6 * s * facing
            hy = hy - 0.4 * s
        else:
            if kind in ("battleaxe", "axe", "pickaxe"):
                rest = -0.18 + 0.06 * (1.0 - combat)  # head-up, tight to the hip
            else:
                rest = 2.05 * (1.0 - combat) + (-0.52) * combat
            # Positive swing = tip toward facing (the enemy)
            ang = (rest + float(swing or 0.0) * 1.05) * facing
            ws = s * 1.02
            # Rest: grip beside the hip (not across the chest). Strike: drive toward enemy.
            side = 0.45 * s if kind in ("battleaxe", "axe", "pickaxe") else 1.55 * s
            hx = hx + (side * facing) * (1.0 - combat) + (0.85 * s * facing) * combat * max(0.0, float(swing or 0.0))
            hy = hy + (0.35 * s) * (1.0 - combat) - (0.35 * s) * combat * max(0.0, float(swing or 0.0))
    c, sn = math.cos(ang), math.sin(ang)

    def R(px, py):
        x = px * ws
        y = py * ws
        # Sheathed: mirror local X so the bit sits on the FAR side, and shift so
        # the tip (local y ≈ -16) lands on (hx, hy) — only the head peeks past
        # the shoulder; the long shaft is not drawn through the torso.
        if sheathed:
            x = -x
            y = y + 16.5 * ws
        return hx + (x * c - y * sn) * facing, hy + (x * sn + y * c)

    if not kind:
        return
    wood = (118, 82, 48)
    wood_l = (148, 108, 68)
    wood_d = (78, 52, 28)

    # Walk-up back view: show tip + short shaft on the backplate (not chest-peek only).
    if sheathed and back_view:
        if kind in ("axe", "battleaxe"):
            rs.draw_poly(surf, wood_d, [
                R(-0.65, -6), R(0.65, -6), R(0.55, -14.8), R(-0.55, -14.8),
            ], outline, 1)
            rs.draw_volume(surf, face, [
                R(0.1, -11.5), R(5.5, -14.0), R(5.2, -9.0), R(0.6, -9.5),
            ], outline, 1)
            return
        if kind == "pickaxe":
            rs.draw_poly(surf, wood_d, [
                R(-0.65, -6), R(0.65, -6), R(0.55, -15.2), R(-0.55, -15.2),
            ], outline, 1)
            rs.draw_volume(surf, face, [
                R(-5.5, -14), R(5.5, -14), R(4.5, -11), R(-4.5, -11),
            ], outline, 1)
            return
        if kind == "bow":
            rs.draw_poly(surf, wood_d, [
                R(-0.95, -5), R(0.95, -5), R(1.15, -15.4), R(-1.15, -15.4),
            ], outline, 1)
            return
        # Sword / staff / dagger — tip + short scabbard on the upper back
        tip = [
            R(0, -16.8), R(1.6, -14.5), R(0.4, -12.5), R(-0.4, -12.5), R(-1.6, -14.5),
        ]
        rs.draw_poly(surf, deep, tip, outline, 1)
        rs.draw_poly(surf, face, [
            R(0, -16.2), R(1.0, -14.6), R(0.2, -13.0), R(-0.15, -13.0),
        ], None, 0)
        rs.draw_poly(surf, wood_d, [
            R(-0.7, -8.5), R(0.7, -8.5), R(0.55, -13.0), R(-0.55, -13.0),
        ], outline, 1)
        return

    # Sheathed: only a short tip / bit peeks over the far shoulder — never the
    # full shaft (that read as the weapon sitting across the front of the body).
    if sheathed and kind not in ("axe", "pickaxe", "bow", "battleaxe"):
        tip = [
            R(0, -16.8), R(1.6, -14.5), R(0.4, -12.5), R(-0.4, -12.5), R(-1.6, -14.5),
        ]
        rs.draw_poly(surf, deep, tip, outline, 1)
        rs.draw_poly(surf, face, [
            R(0, -16.2), R(1.0, -14.6), R(0.2, -13.0), R(-0.15, -13.0),
        ], None, 0)
        return
    if sheathed and kind in ("axe", "battleaxe"):
        rs.draw_poly(surf, wood_d, [R(-0.7, -10), R(0.7, -10), R(0.55, -14.5), R(-0.55, -14.5)], outline, 1)
        rs.draw_volume(surf, face, [
            R(0.1, -11.5), R(5.5, -14.0), R(5.2, -9.0), R(0.6, -9.5),
        ], outline, 1)
        return
    if sheathed and kind == "pickaxe":
        rs.draw_poly(surf, wood_d, [R(-0.7, -10), R(0.7, -10), R(0.55, -15), R(-0.55, -15)], outline, 1)
        rs.draw_volume(surf, face, [
            R(-5.5, -14), R(5.5, -14), R(4.5, -11), R(-4.5, -11),
        ], outline, 1)
        return
    if sheathed and kind == "bow":
        rs.draw_poly(surf, wood_d, [
            R(-0.9, -8), R(0.9, -8), R(1.1, -15.2), R(-1.1, -15.2),
        ], outline, 1)
        return

    def blade_layers(tip_y, half_w):
        """Shade / mid / lit blade stack + fuller groove."""
        rs.draw_poly(surf, deep, [
            R(0, 1.2), R(half_w + 0.35, 0.2), R(half_w * 0.55, tip_y + 2),
            R(0, tip_y), R(-half_w * 0.55, tip_y + 2), R(-(half_w + 0.35), 0.2),
        ], outline, 1)
        rs.draw_poly(surf, face, [
            R(0, 0.6), R(half_w, 0), R(half_w * 0.45, tip_y + 2.2),
            R(0, tip_y + 0.8), R(-0.35, tip_y + 2.2), R(-0.4, 0),
        ], None, 0)
        rs.draw_poly(surf, hi, [
            R(0.2, -0.5), R(half_w * 0.7, -0.8), R(half_w * 0.4, tip_y + 3),
            R(0.25, tip_y + 1.5),
        ], None, 0)
        pygame.draw.line(surf, sh, R(0.15, -1), R(0.1, tip_y + 3.5), max(1, int(ws * 0.35)))
        pygame.draw.line(surf, (245, 245, 250), R(0, tip_y + 1.5), R(0, tip_y - 0.2), max(1, int(ws * 0.25)))

    def crossguard(half=4.2):
        rs.draw_poly(surf, gold_d, [
            R(-half, 0.2), R(half, 0.2), R(half + 0.5, 1.6), R(half * 0.7, 2.4),
            R(-half * 0.7, 2.4), R(-(half + 0.5), 1.6),
        ], outline, 1)
        rs.draw_poly(surf, gold, [
            R(-half + 0.3, 0.4), R(half - 0.3, 0.4), R(half * 0.55, 1.5), R(-half * 0.55, 1.5),
        ], None, 0)
        for sx in (-half, half):
            pygame.draw.circle(surf, gold, (int(R(sx, 1.0)[0]), int(R(sx, 1.0)[1])), max(1, int(0.7 * ws)))

    def grip_and_pommel(grip_end=6.4):
        rs.draw_poly(surf, wood_d, [
            R(-1.35, 2.3), R(1.35, 2.3), R(1.15, grip_end), R(-1.15, grip_end),
        ], outline, 1)
        rs.draw_poly(surf, wood, [
            R(-1.0, 2.5), R(0.55, 2.5), R(0.45, grip_end - 0.2), R(-0.9, grip_end - 0.2),
        ], None, 0)
        for i in range(3):
            yy = 3.1 + i * 1.05
            pygame.draw.line(surf, wood_l, R(-1.05, yy), R(1.05, yy), 1)
        pygame.draw.circle(surf, gold_d, (int(R(0, grip_end + 0.55)[0]), int(R(0, grip_end + 0.55)[1])), max(2, int(1.55 * ws)))
        pygame.draw.circle(surf, gold, (int(R(-0.25, grip_end + 0.3)[0]), int(R(-0.25, grip_end + 0.3)[1])), max(1, int(0.85 * ws)))

    if kind == "dagger":
        blade_layers(-11.5, 1.55)
        crossguard(3.1)
        grip_and_pommel(5.4)
    elif kind == "battleaxe":
        # Classic battleaxe: slim haft, crescent bit + rear fluke.
        # Eclipse Cleaver: black steel + gold trim, dragon crest on the bit.
        eclipse = bool(item_id and "eclipse" in item_id)
        if eclipse:
            shaft_d, shaft_m, shaft_l = (12, 12, 16), (28, 28, 34), (70, 70, 78)
            bit_hi, bit_face = (95, 95, 105), (42, 42, 50)
            bit_sh, bit_deep = (22, 22, 28), (8, 8, 12)
            edge = gold_l
        else:
            shaft_d, shaft_m, shaft_l = wood_d, wood, wood_l
            bit_hi, bit_face, bit_sh, bit_deep = hi, face, sh, deep
            edge = (245, 245, 250)
        if sheathed:
            # Compact tip peek — stub + small bit only (no full crescent across the chest)
            rs.draw_poly(surf, shaft_d, [
                R(-0.55, -13.5), R(0.55, -13.5), R(0.4, -16.5), R(-0.4, -16.5),
            ], outline, 1)
            rs.draw_poly(surf, shaft_m, [
                R(-0.28, -13.7), R(0.28, -13.7), R(0.2, -16.2), R(-0.2, -16.2),
            ], None, 0)
            rs.draw_poly(surf, bit_deep, [
                R(0.2, -15.5), R(2.2, -16.6), R(3.2, -15.4), R(2.4, -14.0), R(0.3, -14.4),
            ], outline, 1)
            rs.draw_poly(surf, bit_face, [
                R(0.3, -15.4), R(2.0, -16.3), R(2.8, -15.3), R(2.1, -14.2), R(0.4, -14.5),
            ], None, 0)
            rs.draw_poly(surf, bit_sh, [
                R(-0.2, -15.3), R(-1.6, -15.8), R(-1.8, -15.0), R(-0.3, -14.5),
            ], outline, 1)
            if eclipse:
                pygame.draw.circle(surf, gold, (int(R(1.6, -15.2)[0]), int(R(1.6, -15.2)[1])), max(1, int(0.7 * ws)), 1)
            # skip full blade / grip
        else:
            rs.draw_poly(surf, shaft_d, [
                R(-0.85, 2.4), R(0.85, 2.4), R(0.75, -16.5), R(-0.75, -16.5),
            ], outline, 1)
            rs.draw_poly(surf, shaft_m, [
                R(-0.42, 2.0), R(0.38, 2.0), R(0.32, -16.1), R(-0.38, -16.1),
            ], None, 0)
            rs.draw_poly(surf, shaft_l, [
                R(-0.18, 1.6), R(0.12, 1.6), R(0.1, -15.8), R(-0.16, -15.8),
            ], None, 0)
            for band_y in (-13.8, -14.6):
                pygame.draw.line(surf, gold_d, R(-0.95, band_y), R(0.95, band_y), max(1, int(ws * 0.35)))
                pygame.draw.line(surf, gold, R(-0.8, band_y - 0.12), R(0.8, band_y - 0.12), 1)
            rs.draw_poly(surf, bit_sh, [
                R(-0.3, -16.2), R(0.3, -16.2), R(0.0, -18.0),
            ], outline, 1)
            if eclipse:
                rs.draw_poly(surf, gold, [R(-0.15, -16.3), R(0.15, -16.3), R(0.0, -17.5)], None, 0)
            outer = [
                R(0.5, -15.8), R(2.8, -17.0), R(5.0, -16.6), R(6.0, -15.2),
                R(5.5, -13.6), R(3.6, -12.6), R(1.4, -12.9), R(0.5, -14.0),
            ]
            inner = [
                R(1.1, -15.2), R(2.8, -15.9), R(4.4, -15.6), R(5.0, -14.8),
                R(4.6, -13.9), R(3.2, -13.4), R(1.6, -13.6), R(1.1, -14.4),
            ]
            rs.draw_poly(surf, bit_deep, outer, outline, 1)
            rs.draw_poly(surf, bit_face, outer[:], None, 0)
            rs.draw_poly(surf, bit_sh, inner, None, 0)
            rs.draw_poly(surf, bit_hi, [
                R(1.4, -15.6), R(3.2, -16.5), R(4.8, -16.2), R(4.2, -15.4), R(1.8, -14.8),
            ], None, 0)
            pygame.draw.lines(surf, edge, False, [
                R(2.6, -16.9), R(5.0, -16.5), R(5.9, -15.2), R(5.3, -13.7), R(3.8, -12.8),
            ], max(1, int(ws * 0.32)))
            if eclipse:
                pygame.draw.lines(surf, gold, False, [
                    R(0.55, -15.7), R(2.8, -16.9), R(5.0, -16.5), R(5.95, -15.2),
                    R(5.45, -13.65), R(3.6, -12.7), R(1.45, -13.0), R(0.55, -14.0),
                ], max(1, int(ws * 0.28)))
                dx, dy = R(2.7, -14.7)
                ds = ws * 0.55
                pygame.draw.circle(surf, gold_d, (int(dx), int(dy)), max(2, int(1.35 * ds)))
                pygame.draw.circle(surf, (20, 20, 24), (int(dx), int(dy)), max(2, int(1.05 * ds)))
                pygame.draw.circle(surf, gold, (int(dx), int(dy)), max(2, int(1.35 * ds)), max(1, int(ds * 0.35)))
                rs.draw_poly(surf, gold, [
                    (dx - 0.7 * ds, dy + 0.1 * ds),
                    (dx - 0.55 * ds, dy - 0.85 * ds),
                    (dx + 0.1 * ds, dy - 1.05 * ds),
                    (dx + 0.95 * ds, dy - 0.35 * ds),
                    (dx + 1.05 * ds, dy + 0.15 * ds),
                    (dx + 0.35 * ds, dy + 0.55 * ds),
                    (dx - 0.35 * ds, dy + 0.5 * ds),
                ], (10, 10, 12), 1)
                rs.draw_poly(surf, gold_l, [
                    (dx - 0.35 * ds, dy - 0.65 * ds), (dx + 0.05 * ds, dy - 0.9 * ds),
                    (dx + 0.45 * ds, dy - 0.4 * ds), (dx + 0.05 * ds, dy - 0.25 * ds),
                ], None, 0)
                rs.draw_poly(surf, gold_d, [
                    (dx - 0.2 * ds, dy - 0.9 * ds), (dx + 0.05 * ds, dy - 1.55 * ds),
                    (dx + 0.3 * ds, dy - 0.85 * ds),
                ], None, 0)
                pygame.draw.circle(surf, (255, 70, 45), (int(dx + 0.2 * ds), int(dy - 0.5 * ds)), max(1, int(0.22 * ds)))
                rs.draw_poly(surf, gold_d, [
                    (dx - 0.2 * ds, dy - 0.15 * ds), (dx - 1.5 * ds, dy - 0.85 * ds),
                    (dx - 0.9 * ds, dy + 0.15 * ds),
                ], None, 0)
                rs.draw_poly(surf, gold_d, [
                    (dx + 0.2 * ds, dy - 0.1 * ds), (dx + 1.55 * ds, dy - 0.75 * ds),
                    (dx + 0.95 * ds, dy + 0.2 * ds),
                ], None, 0)
            rs.draw_poly(surf, bit_sh, [
                R(-0.35, -15.4), R(-2.4, -16.0), R(-2.7, -15.1), R(-1.4, -14.3), R(-0.45, -14.3),
            ], outline, 1)
            if eclipse:
                pygame.draw.lines(surf, gold, False, [
                    R(-0.4, -15.35), R(-2.35, -15.95), R(-2.65, -15.1),
                ], 1)
            pygame.draw.circle(surf, gold_d, (int(R(0.05, -14.8)[0]), int(R(0.05, -14.8)[1])), max(2, int(0.8 * ws)))
            pygame.draw.circle(surf, gold, (int(R(-0.05, -14.95)[0]), int(R(-0.05, -14.95)[1])), max(1, int(0.4 * ws)))
            if eclipse:
                rs.draw_poly(surf, (18, 18, 22), [
                    R(-1.2, 2.4), R(1.2, 2.4), R(1.05, 5.5), R(-1.05, 5.5),
                ], outline, 1)
                for i in range(3):
                    yy = 2.9 + i * 0.85
                    pygame.draw.line(surf, gold_d, R(-1.05, yy), R(1.05, yy), 1)
                pygame.draw.circle(surf, gold_d, (int(R(0, 6.05)[0]), int(R(0, 6.05)[1])), max(2, int(1.45 * ws)))
                pygame.draw.circle(surf, gold, (int(R(-0.2, 5.8)[0]), int(R(-0.2, 5.8)[1])), max(1, int(0.8 * ws)))
            else:
                grip_and_pommel(5.6)
    elif kind == "axe":
        rs.draw_poly(surf, wood_d, [R(-1.35, 2), R(1.35, 2), R(1.45, -14.5), R(-1.45, -14.5)], outline, 1)
        rs.draw_poly(surf, wood, [R(-0.65, 1.2), R(0.55, 1.2), R(0.6, -14), R(-0.6, -14)], None, 0)
        rs.draw_volume(surf, face, [
            R(0.2, -8.5), R(9.2, -13), R(9.0, -4.2), R(1.0, -4.8),
        ], outline, 1)
        rs.draw_poly(surf, hi, [R(1.2, -10.5), R(6.8, -11.8), R(6.5, -6.2), R(1.5, -6.5)], None, 0)
        pygame.draw.line(surf, (240, 240, 245), R(8.5, -12.2), R(8.4, -5.2), max(1, int(ws * 0.4)))
        pygame.draw.circle(surf, gold_d, (int(R(0.3, -6)[0]), int(R(0.3, -6)[1])), max(2, int(1.2 * ws)))
    elif kind == "pickaxe":
        rs.draw_poly(surf, wood_d, [R(-1.35, 2), R(1.35, 2), R(1.45, -15), R(-1.45, -15)], outline, 1)
        rs.draw_poly(surf, wood, [R(-0.6, 1), R(0.55, 1), R(0.6, -14.5), R(-0.55, -14.5)], None, 0)
        rs.draw_volume(surf, face, [
            R(-9.2, -13.2), R(9.2, -13.2), R(8.0, -8.5), R(-8.0, -8.5),
        ], outline, 1)
        rs.draw_poly(surf, hi, [R(-5.5, -13), R(0, -14.8), R(5.5, -13), R(0, -11.2)], None, 0)
        rs.draw_poly(surf, deep, [R(-9.0, -13), R(-11.5, -11.5), R(-7.5, -9.5)], None, 0)
        rs.draw_poly(surf, deep, [R(9.0, -13), R(11.5, -11.5), R(7.5, -9.5)], None, 0)
    elif kind == "staff":
        rs.draw_poly(surf, wood_d, [R(-1.5, 3), R(1.5, 3), R(1.7, -18), R(-1.7, -18)], outline, 1)
        rs.draw_poly(surf, wood, [R(-0.7, 2.5), R(0.7, 2.5), R(0.85, -17.5), R(-0.85, -17.5)], None, 0)
        for band_y in (-4, -10, -15):
            pygame.draw.line(surf, gold, R(-1.6, band_y), R(1.6, band_y), max(1, int(ws * 0.45)))
        pygame.draw.circle(surf, (160, 100, 210), (int(R(0, -19)[0]), int(R(0, -19)[1])), max(3, int(3.2 * ws)))
        pygame.draw.circle(surf, (240, 200, 255), (int(R(-0.7, -19.7)[0]), int(R(-0.7, -19.7)[1])), max(1, int(1.4 * ws)))
    elif kind == "bow":
        # Stave + string; draw pulls the string back toward the grip hand
        draw = 0.0 if sheathed else max(0.0, min(1.2, abs(float(swing or 0.0))))
        rs.draw_poly(surf, wood_d, [
            R(-1.1, 5.2), R(1.1, 5.2), R(1.5, -15.2), R(-1.5, -15.2),
        ], outline, 1)
        rs.draw_poly(surf, wood, [
            R(-0.75, 4.6), R(0.75, 4.6), R(1.05, -14.6), R(-1.05, -14.6),
        ], None, 0)
        tip_top = R(0.2, -15.5)
        tip_bot = R(0.2, 5.5)
        pygame.draw.circle(surf, wood_l, (int(tip_top[0]), int(tip_top[1])), max(2, int(1.2 * ws)))
        pygame.draw.circle(surf, wood_l, (int(tip_bot[0]), int(tip_bot[1])), max(2, int(1.2 * ws)))
        mid = R(-2.2 - 3.5 * draw, -4.5)
        pygame.draw.lines(surf, (230, 220, 185), False, [
            tip_top, mid, tip_bot,
        ], max(1, int(ws * 0.45)))
        if draw > 0.25:
            arrow_tip = R(6.5 + 1.5 * (1.0 - min(1.0, draw)), -5.0)
            pygame.draw.line(surf, (150, 105, 55), mid, arrow_tip, max(2, int(ws * 0.5)))
            pygame.draw.polygon(surf, (180, 185, 195), [
                arrow_tip,
                (arrow_tip[0] - 2.2 * ws * facing, arrow_tip[1] - 1.4 * ws),
                (arrow_tip[0] - 2.2 * ws * facing, arrow_tip[1] + 1.4 * ws),
            ])
    elif kind == "rod":
        # Long fishing rod with line tip
        rs.draw_poly(surf, wood_d, [R(-1.1, 2.5), R(1.1, 2.5), R(1.0, -20), R(-1.0, -20)], outline, 1)
        rs.draw_poly(surf, wood_l, [R(-0.45, 2.0), R(0.45, 2.0), R(0.4, -19.5), R(-0.4, -19.5)], None, 0)
        for band_y in (1.0, -4, -10):
            pygame.draw.line(surf, gold, R(-1.2, band_y), R(1.2, band_y), max(1, int(ws * 0.35)))
        tip = R(0, -21)
        pygame.draw.circle(surf, (220, 210, 190), (int(tip[0]), int(tip[1])), max(1, int(0.7 * ws)))
        # Slack line toward the water (screen-down from tip)
        line_end = (tip[0] + 2.5 * ws * facing, tip[1] + 10 * ws + abs(swing) * 3 * ws)
        pygame.draw.lines(surf, (190, 200, 210), False, [
            tip,
            (tip[0] + 1.2 * ws * facing, tip[1] + 4 * ws),
            line_end,
        ], max(1, int(ws * 0.28)))
        pygame.draw.circle(surf, (90, 70, 40), (int(line_end[0]), int(line_end[1])), max(1, int(0.9 * ws)))
    else:
        blade_layers(-16.8, 2.05)
        rs.draw_poly(surf, sh, [R(-1.6, 0.2), R(1.6, 0.2), R(1.4, -2.2), R(-1.4, -2.2)], None, 0)
        crossguard(4.5)
        grip_and_pommel(6.6)


def _draw_eclipse_shield_face(surf, sx, sy, ss, outline):
    """Magnificent black/gold kite — ornate rim, eclipse disc, dragon crest."""
    black = (18, 18, 22)
    face = (38, 38, 46)
    face_l = (72, 72, 82)
    deep = (8, 8, 12)
    gold = (228, 196, 78)
    gold_d = (160, 120, 40)
    gold_l = (255, 230, 140)
    pts = [
        (sx - 6.4 * ss, sy - 8.0 * ss), (sx + 6.4 * ss, sy - 8.0 * ss),
        (sx + 8.0 * ss, sy - 0.2 * ss), (sx, sy + 11.8 * ss), (sx - 8.0 * ss, sy - 0.2 * ss),
    ]
    # Drop shadow
    sh = [(p[0] + 0.55 * ss, p[1] + 0.7 * ss) for p in pts]
    rs.draw_poly(surf, (10, 8, 12), sh, None, 0)
    # Face
    rs.draw_volume(surf, face, pts, outline, 1)
    rs.draw_poly(surf, face_l, [
        (sx - 4.4 * ss, sy - 6.6 * ss), (sx + 1.2 * ss, sy - 6.6 * ss),
        (sx + 2.2 * ss, sy - 0.4 * ss), (sx - 4.2 * ss, sy + 0.6 * ss),
    ], None, 0)
    # Outer gold rim
    pygame.draw.polygon(surf, gold_d, pts, max(2, int(ss * 0.85)))
    pygame.draw.polygon(surf, gold, pts, max(1, int(ss * 0.45)))
    # Inner filigree ring
    inner = [
        (sx - 5.0 * ss, sy - 6.4 * ss), (sx + 5.0 * ss, sy - 6.4 * ss),
        (sx + 6.2 * ss, sy - 0.2 * ss), (sx, sy + 9.0 * ss), (sx - 6.2 * ss, sy - 0.2 * ss),
    ]
    pygame.draw.polygon(surf, gold_d, inner, max(1, int(ss * 0.35)))
    # Edge studs / filigree ticks around the rim
    rim_anchors = [
        (-5.6, -7.4), (-2.0, -7.8), (2.0, -7.8), (5.6, -7.4),
        (7.2, -2.8), (6.6, 2.2), (3.2, 7.2), (0.0, 10.2),
        (-3.2, 7.2), (-6.6, 2.2), (-7.2, -2.8),
    ]
    for ox, oy in rim_anchors:
        px, py = sx + ox * ss, sy + oy * ss
        pygame.draw.circle(surf, gold_d, (int(px), int(py)), max(2, int(0.7 * ss)))
        pygame.draw.circle(surf, gold, (int(px - 0.15 * ss), int(py - 0.15 * ss)), max(1, int(0.35 * ss)))
    # Corner flourishes (top corners)
    for side in (-1, 1):
        rs.draw_poly(surf, gold_d, [
            (sx + side * 5.8 * ss, sy - 7.6 * ss),
            (sx + side * 4.2 * ss, sy - 6.2 * ss),
            (sx + side * 5.2 * ss, sy - 5.4 * ss),
            (sx + side * 6.6 * ss, sy - 6.6 * ss),
        ], None, 0)
        rs.draw_poly(surf, gold_l, [
            (sx + side * 5.5 * ss, sy - 7.2 * ss),
            (sx + side * 4.6 * ss, sy - 6.4 * ss),
            (sx + side * 5.1 * ss, sy - 5.9 * ss),
        ], None, 0)
    # Eclipse disc (void + gold ring)
    bx, by = sx, sy + 0.2 * ss
    br = 3.4 * ss
    pygame.draw.circle(surf, gold_d, (int(bx), int(by)), max(3, int(br + 0.55 * ss)))
    pygame.draw.circle(surf, gold, (int(bx), int(by)), max(3, int(br + 0.55 * ss)), max(1, int(ss * 0.4)))
    pygame.draw.circle(surf, deep, (int(bx), int(by)), max(3, int(br)))
    pygame.draw.circle(surf, black, (int(bx + 0.15 * ss), int(by + 0.1 * ss)), max(2, int(br * 0.72)))
    # Gold crescent (eclipse)
    pygame.draw.circle(surf, gold, (int(bx - 0.55 * ss), int(by - 0.2 * ss)), max(2, int(br * 0.55)), max(1, int(ss * 0.35)))
    # Mini dragon crest (same motif as Eclipse Cleaver)
    ds = ss * 0.95
    dx, dy = bx + 0.15 * ss, by - 0.15 * ss
    rs.draw_poly(surf, gold, [
        (dx - 0.85 * ds, dy + 0.15 * ds),
        (dx - 0.65 * ds, dy - 1.0 * ds),
        (dx + 0.15 * ds, dy - 1.25 * ds),
        (dx + 1.15 * ds, dy - 0.4 * ds),
        (dx + 1.25 * ds, dy + 0.2 * ds),
        (dx + 0.4 * ds, dy + 0.7 * ds),
        (dx - 0.4 * ds, dy + 0.65 * ds),
    ], (10, 10, 12), 1)
    rs.draw_poly(surf, gold_l, [
        (dx - 0.4 * ds, dy - 0.75 * ds), (dx + 0.1 * ds, dy - 1.05 * ds),
        (dx + 0.55 * ds, dy - 0.45 * ds), (dx + 0.1 * ds, dy - 0.3 * ds),
    ], None, 0)
    rs.draw_poly(surf, gold_d, [
        (dx - 0.25 * ds, dy - 1.05 * ds), (dx + 0.1 * ds, dy - 1.85 * ds),
        (dx + 0.4 * ds, dy - 1.0 * ds),
    ], None, 0)
    pygame.draw.circle(surf, (255, 70, 45), (int(dx + 0.25 * ds), int(dy - 0.55 * ds)), max(1, int(0.28 * ds)))
    rs.draw_poly(surf, gold_d, [
        (dx - 0.25 * ds, dy - 0.15 * ds), (dx - 1.7 * ds, dy - 1.0 * ds),
        (dx - 1.0 * ds, dy + 0.2 * ds),
    ], None, 0)
    rs.draw_poly(surf, gold_d, [
        (dx + 0.25 * ds, dy - 0.1 * ds), (dx + 1.8 * ds, dy - 0.9 * ds),
        (dx + 1.1 * ds, dy + 0.25 * ds),
    ], None, 0)
    # Tip jewel
    pygame.draw.circle(surf, gold_d, (int(sx), int(sy + 9.6 * ss)), max(2, int(1.1 * ss)))
    pygame.draw.circle(surf, gold_l, (int(sx - 0.25 * ss), int(sy + 9.35 * ss)), max(1, int(0.5 * ss)))


def _draw_shield(surf, sx, sy, s, item_id, on_back=False, facing=1, face_on=False):
    """Hand-held shield, or flattened back-mounted kite when on_back."""
    base, shadow, highlight, outline = rs.metal_palette(item_id)
    if item_id and "wood" in item_id:
        base, shadow, highlight = (140, 95, 55), (90, 60, 35), (180, 130, 80)
    eclipse = bool(item_id and "eclipse" in item_id)
    if eclipse and (face_on or not on_back):
        # Full face for held + walk-up back; skip generic metal kite.
        _draw_eclipse_shield_face(surf, sx, sy, s * (0.78 if face_on else 0.95), outline)
        return
    if on_back and face_on:
        # Walk-up: shield face on the backplate. Darken + hard rim so it doesn't
        # melt into matching plate metal (mythos-on-mythos / steel-on-steel).
        ss = s * 0.78
        mythos = bool(item_id and "mythos" in item_id)
        face = rs.shade(base, -22)
        rim = rs.shade(shadow, -24)
        boss = (228, 196, 78) if mythos else highlight
        boss_d = (160, 120, 40) if mythos else shadow
        if item_id and "sq" in item_id:
            sh_pts = [
                (sx - 5.0 * ss + 0.55 * ss, sy - 4.4 * ss + 0.65 * ss),
                (sx + 5.4 * ss + 0.55 * ss, sy - 4.4 * ss + 0.65 * ss),
                (sx + 5.4 * ss + 0.55 * ss, sy + 5.8 * ss + 0.65 * ss),
                (sx - 5.0 * ss + 0.55 * ss, sy + 5.8 * ss + 0.65 * ss),
            ]
            pts = [
                (sx - 5.0 * ss, sy - 4.4 * ss), (sx + 5.4 * ss, sy - 4.4 * ss),
                (sx + 5.4 * ss, sy + 5.8 * ss), (sx - 5.0 * ss, sy + 5.8 * ss),
            ]
        else:
            sh_pts = [
                (sx - 4.4 * ss + 0.5 * ss, sy - 5.6 * ss + 0.65 * ss),
                (sx + 4.4 * ss + 0.5 * ss, sy - 5.6 * ss + 0.65 * ss),
                (sx + 5.4 * ss + 0.5 * ss, sy - 0.1 * ss + 0.65 * ss),
                (sx + 0.5 * ss, sy + 7.6 * ss + 0.65 * ss),
                (sx - 5.4 * ss + 0.5 * ss, sy - 0.1 * ss + 0.65 * ss),
            ]
            pts = [
                (sx - 4.4 * ss, sy - 5.6 * ss), (sx + 4.4 * ss, sy - 5.6 * ss),
                (sx + 5.4 * ss, sy - 0.1 * ss), (sx, sy + 7.6 * ss),
                (sx - 5.4 * ss, sy - 0.1 * ss),
            ]
        rs.draw_poly(surf, (18, 16, 20), sh_pts, None, 0)
        rs.draw_volume(surf, rim, pts, outline, 1)
        rs.draw_poly(surf, face, pts[:], None, 0)
        rs.draw_poly(surf, rs.shade(face, 24), [
            (sx - 2.8 * ss, sy - 4.0 * ss), (sx + 0.5 * ss, sy - 4.0 * ss),
            (sx + 1.1 * ss, sy - 0.2 * ss), (sx - 2.8 * ss, sy + 0.35 * ss),
        ], None, 0)
        if item_id and "wood" not in (item_id or ""):
            if mythos:
                pygame.draw.circle(surf, boss_d, (int(sx), int(sy + 0.1 * ss)), max(2, int(1.9 * ss)))
                pygame.draw.circle(surf, boss, (int(sx), int(sy + 0.1 * ss)), max(2, int(1.35 * ss)))
                pygame.draw.circle(surf, (255, 230, 140), (int(sx - 0.3 * ss), int(sy - 0.15 * ss)), max(1, int(0.5 * ss)))
            elif "sq" in (item_id or ""):
                for ox, oy in ((-3.0, -2.4), (3.0, -2.4), (-3.0, 2.8), (3.0, 2.8)):
                    pygame.draw.circle(surf, rim, (int(sx + ox * ss), int(sy + oy * ss)), max(1, int(0.65 * ss)))
                pygame.draw.circle(surf, rim, (int(sx), int(sy + 0.2 * ss)), max(2, int(1.15 * ss)))
                pygame.draw.circle(surf, highlight, (int(sx - 0.25 * ss), int(sy - 0.05 * ss)), max(1, int(0.45 * ss)))
            else:
                red = (180, 45, 45)
                pygame.draw.line(surf, red, (sx, sy - 3.8 * ss), (sx, sy + 5.0 * ss), max(2, int(ss * 0.7)))
                pygame.draw.line(surf, red, (sx - 3.2 * ss, sy - 0.45 * ss), (sx + 3.2 * ss, sy - 0.45 * ss), max(2, int(ss * 0.7)))
                pygame.draw.circle(surf, rim, (int(sx), int(sy + 0.15 * ss)), max(2, int(1.1 * ss)))
                pygame.draw.circle(surf, highlight, (int(sx - 0.25 * ss), int(sy - 0.1 * ss)), max(1, int(0.45 * ss)))
        pygame.draw.lines(surf, outline, True, pts, max(1, int(ss * 0.55)))
        return
    if on_back:
        # Flattened kite — bulk sits under the torso; outer rim peeks past the shoulder.
        ss = s * 0.88
        far = -4.4 * ss * facing
        near = 2.6 * ss * facing
        top, bot = -4.6 * ss, 6.2 * ss
        pts = [
            (sx + far * 0.9, sy + top),
            (sx + near * 0.55, sy + top + 0.6 * ss),
            (sx + near * 0.7, sy + 0.8 * ss),
            (sx + near * 0.2, sy + bot),
            (sx + far * 0.45, sy + bot - 0.8 * ss),
            (sx + far, sy + 0.4 * ss),
        ]
        rs.draw_volume(surf, shadow, pts, outline, 1)
        rs.draw_poly(surf, base, pts[:], None, 0)
        rs.draw_poly(surf, highlight, [
            (sx + far * 0.35, sy + top + 0.9 * ss),
            (sx + near * 0.1, sy + top + 1.2 * ss),
            (sx + near * 0.15, sy + 0.3 * ss),
            (sx + far * 0.2, sy + 0.05 * ss),
        ], None, 0)
        pygame.draw.lines(surf, shadow, True, pts, max(1, int(ss * 0.4)))
        if eclipse:
            gold = (228, 196, 78)
            pygame.draw.lines(surf, gold, True, pts, max(1, int(ss * 0.35)))
            pygame.draw.circle(surf, gold, (int(sx + far * 0.35), int(sy + 0.2 * ss)), max(1, int(0.7 * ss)), 1)
        return
    ss = s * 0.95
    if item_id and "sq" in item_id:
        rs.draw_volume(surf, base, [
            (sx - 7.2 * ss, sy - 6.8 * ss), (sx + 7.2 * ss, sy - 6.8 * ss),
            (sx + 7.2 * ss, sy + 8.2 * ss), (sx - 7.2 * ss, sy + 8.2 * ss),
        ], outline, 1)
        rs.draw_poly(surf, highlight, [
            (sx - 5.8 * ss, sy - 5.4 * ss), (sx + 0.8 * ss, sy - 5.4 * ss),
            (sx + 0.8 * ss, sy + 0.8 * ss), (sx - 5.8 * ss, sy + 0.8 * ss),
        ], None, 0)
        # Rivets
        for ox, oy in ((-4.2, -3.5), (4.2, -3.5), (-4.2, 4), (4.2, 4)):
            pygame.draw.circle(surf, shadow, (int(sx + ox * ss), int(sy + oy * ss)), max(1, int(0.85 * ss)))
            pygame.draw.circle(surf, highlight, (int(sx + ox * ss - 0.3 * ss), int(sy + oy * ss - 0.3 * ss)), max(1, int(0.35 * ss)))
        pygame.draw.circle(surf, shadow, (int(sx), int(sy + 0.6 * ss)), max(2, int(1.6 * ss)))
        pygame.draw.circle(surf, highlight, (int(sx - 0.4 * ss), int(sy + 0.2 * ss)), max(1, int(0.7 * ss)))
    else:
        rs.draw_volume(surf, base, [
            (sx - 6.2 * ss, sy - 8.2 * ss), (sx + 6.2 * ss, sy - 8.2 * ss),
            (sx + 7.8 * ss, sy), (sx, sy + 11.5 * ss), (sx - 7.8 * ss, sy),
        ], outline, 1)
        rs.draw_poly(surf, highlight, [
            (sx - 4.2 * ss, sy - 6.8 * ss), (sx + 1.4 * ss, sy - 6.8 * ss),
            (sx + 2.4 * ss, sy - 0.6 * ss), (sx - 4.2 * ss, sy + 0.4 * ss),
        ], None, 0)
        # Rim
        pygame.draw.polygon(surf, shadow, [
            (sx - 6.2 * ss, sy - 8.2 * ss), (sx + 6.2 * ss, sy - 8.2 * ss),
            (sx + 7.8 * ss, sy), (sx, sy + 11.5 * ss), (sx - 7.8 * ss, sy),
        ], max(1, int(ss * 0.55)))
        if item_id and "wood" not in (item_id or ""):
            red = (180, 45, 45)
            pygame.draw.line(surf, red, (sx, sy - 5.8 * ss), (sx, sy + 7.5 * ss), max(2, int(ss * 0.75)))
            pygame.draw.line(surf, red, (sx - 4.8 * ss, sy - 0.8 * ss), (sx + 4.8 * ss, sy - 0.8 * ss), max(2, int(ss * 0.75)))
        pygame.draw.circle(surf, shadow, (int(sx), int(sy + 0.4 * ss)), max(2, int(1.5 * ss)))
        pygame.draw.circle(surf, highlight, (int(sx - 0.35 * ss), int(sy)), max(1, int(0.65 * ss)))


def _draw_helmet(surf, hx, hy, s, item_id):
    """Compact helm seated on the skull — medium / full / dragon variants."""
    base, shadow, highlight, outline = rs.metal_palette(item_id)
    mythos = bool(item_id and "mythos" in item_id)
    eclipse = bool(item_id and "eclipse" in item_id)
    leather = bool(item_id and ("leather" in item_id or "cowl" in item_id))

    if leather:
        # Soft cowl — snug hood, open face
        rs.draw_volume(surf, base, [
            (hx - 4.4 * s, hy + 0.6 * s),
            (hx - 3.6 * s, hy - 3.4 * s),
            (hx, hy - 4.8 * s),
            (hx + 3.6 * s, hy - 3.4 * s),
            (hx + 4.4 * s, hy + 0.6 * s),
            (hx + 3.2 * s, hy + 2.2 * s),
            (hx - 3.2 * s, hy + 2.2 * s),
        ], outline, 1, detail="leather")
        rs.draw_poly(surf, highlight, [
            (hx - 2.0 * s, hy - 2.8 * s), (hx, hy - 4.4 * s), (hx + 1.2 * s, hy - 2.4 * s),
        ], None, 0)
        return

    if eclipse:
        # Full black grillhelm — closed face cage, gold bars, crest crescent
        gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
        deep = (8, 8, 12)
        # Tall closed dome
        rs.draw_volume(surf, base, [
            (hx - 4.8 * s, hy + 1.0 * s),
            (hx - 4.0 * s, hy - 3.8 * s),
            (hx - 1.4 * s, hy - 5.4 * s),
            (hx + 1.4 * s, hy - 5.4 * s),
            (hx + 4.0 * s, hy - 3.8 * s),
            (hx + 4.8 * s, hy + 1.0 * s),
            (hx + 3.6 * s, hy + 3.0 * s),
            (hx - 3.6 * s, hy + 3.0 * s),
        ], outline, 1, detail="metal_armor")
        rs.draw_poly(surf, highlight, [
            (hx - 2.6 * s, hy - 3.0 * s), (hx - 0.4 * s, hy - 4.9 * s),
            (hx + 1.0 * s, hy - 2.8 * s), (hx - 0.8 * s, hy - 1.8 * s),
        ], None, 0)
        # Gold crown band
        rs.draw_poly(surf, gold_d, [
            (hx - 4.6 * s, hy - 1.4 * s), (hx + 4.6 * s, hy - 1.4 * s),
            (hx + 4.4 * s, hy - 0.35 * s), (hx - 4.4 * s, hy - 0.35 * s),
        ], outline, 1)
        rs.draw_poly(surf, gold, [
            (hx - 4.2 * s, hy - 1.2 * s), (hx + 4.2 * s, hy - 1.2 * s),
            (hx + 4.0 * s, hy - 0.55 * s), (hx - 4.0 * s, hy - 0.55 * s),
        ], None, 0)
        for ox in (-3.2, -1.6, 0, 1.6, 3.2):
            pygame.draw.circle(surf, gold_l, (int(hx + ox * s), int(hy - 0.85 * s)), max(1, int(0.35 * s)))
        # Face grill cage
        rs.draw_poly(surf, deep, [
            (hx - 3.4 * s, hy - 0.2 * s), (hx + 3.4 * s, hy - 0.2 * s),
            (hx + 3.2 * s, hy + 2.8 * s), (hx - 3.2 * s, hy + 2.8 * s),
        ], outline, 1)
        # Horizontal grill rails
        for i, yy in enumerate((-0.05, 0.7, 1.45, 2.2)):
            pygame.draw.line(
                surf, gold_d if i % 2 else gold,
                (hx - 3.1 * s, hy + yy * s), (hx + 3.1 * s, hy + yy * s),
                max(1, int(s * (0.45 if i % 2 == 0 else 0.32))),
            )
        # Vertical bars
        for ox in (-2.2, -1.1, 0.0, 1.1, 2.2):
            pygame.draw.line(
                surf, gold,
                (hx + ox * s, hy - 0.15 * s), (hx + ox * s, hy + 2.7 * s),
                max(1, int(s * 0.38)),
            )
        # Eye slits behind grill (glow)
        for ox in (-1.55, 1.55):
            pygame.draw.ellipse(
                surf, (255, 160, 40),
                (hx + ox * s - 0.7 * s, hy + 0.35 * s, 1.4 * s, 0.55 * s),
            )
        # Cheek / bevor plates with gold trim
        for side in (-1, 1):
            rs.draw_poly(surf, shadow, [
                (hx + side * 3.0 * s, hy + 0.4 * s),
                (hx + side * 4.4 * s, hy + 0.6 * s),
                (hx + side * 4.0 * s, hy + 2.8 * s),
                (hx + side * 2.8 * s, hy + 2.6 * s),
            ], outline, 1)
            pygame.draw.line(
                surf, gold,
                (hx + side * 3.2 * s, hy + 0.7 * s), (hx + side * 3.8 * s, hy + 2.5 * s),
                max(1, int(s * 0.3)),
            )
        # Crescent crest (eclipse motif)
        rs.draw_poly(surf, gold_d, [
            (hx - 0.9 * s, hy - 4.8 * s), (hx + 0.9 * s, hy - 4.8 * s),
            (hx + 1.4 * s, hy - 6.6 * s), (hx, hy - 7.4 * s), (hx - 1.4 * s, hy - 6.6 * s),
        ], outline, 1)
        rs.draw_poly(surf, gold, [
            (hx - 0.55 * s, hy - 5.0 * s), (hx + 0.55 * s, hy - 5.0 * s),
            (hx + 0.85 * s, hy - 6.3 * s), (hx, hy - 6.9 * s), (hx - 0.85 * s, hy - 6.3 * s),
        ], None, 0)
        pygame.draw.circle(surf, deep, (int(hx + 0.35 * s), int(hy - 6.2 * s)), max(2, int(0.85 * s)))
        pygame.draw.circle(surf, gold_l, (int(hx - 0.15 * s), int(hy - 6.55 * s)), max(1, int(0.4 * s)))
        return

    if mythos:
        # Crimson dragon helm — compact skull-cap, horns, snout guard
        gold = (232, 188, 72)
        gold_d = (150, 100, 32)
        # Dome
        rs.draw_volume(surf, base, [
            (hx - 4.6 * s, hy + 0.8 * s),
            (hx - 3.8 * s, hy - 3.6 * s),
            (hx - 1.2 * s, hy - 5.0 * s),
            (hx + 1.4 * s, hy - 5.0 * s),
            (hx + 3.8 * s, hy - 3.6 * s),
            (hx + 4.6 * s, hy + 0.8 * s),
            (hx + 3.4 * s, hy + 2.4 * s),
            (hx - 3.4 * s, hy + 2.4 * s),
        ], outline, 1, detail="metal_armor")
        rs.draw_poly(surf, highlight, [
            (hx - 2.4 * s, hy - 2.8 * s), (hx - 0.2 * s, hy - 4.5 * s),
            (hx + 1.0 * s, hy - 2.6 * s), (hx - 0.6 * s, hy - 1.6 * s),
        ], None, 0)
        # Twin horns (back-swept)
        for side in (-1, 1):
            rs.draw_poly(surf, base, [
                (hx + side * 2.4 * s, hy - 3.8 * s),
                (hx + side * 3.6 * s, hy - 5.8 * s),
                (hx + side * 5.2 * s, hy - 6.6 * s),
                (hx + side * 4.4 * s, hy - 4.8 * s),
                (hx + side * 3.2 * s, hy - 3.2 * s),
            ], outline, 1)
            rs.draw_poly(surf, highlight if side < 0 else shadow, [
                (hx + side * 2.8 * s, hy - 4.0 * s),
                (hx + side * 3.8 * s, hy - 5.6 * s),
                (hx + side * 4.2 * s, hy - 5.0 * s),
            ], None, 0)
            pygame.draw.circle(
                surf, gold,
                (int(hx + side * 5.0 * s), int(hy - 6.4 * s)),
                max(1, int(0.55 * s)),
            )
        # Brow ridge + eye slots
        rs.draw_poly(surf, shadow, [
            (hx - 3.6 * s, hy - 0.6 * s), (hx + 3.6 * s, hy - 0.6 * s),
            (hx + 3.2 * s, hy + 0.9 * s), (hx - 3.2 * s, hy + 0.9 * s),
        ], outline, 1)
        for ox in (-1.5, 1.5):
            pygame.draw.ellipse(
                surf, (12, 8, 8),
                (hx + ox * s - 0.85 * s, hy - 0.15 * s, 1.7 * s, 0.75 * s),
            )
            pygame.draw.ellipse(
                surf, (255, 170, 60),
                (hx + ox * s - 0.45 * s, hy, 0.9 * s, 0.4 * s),
            )
        # Snout / muzzle plate
        rs.draw_poly(surf, base, [
            (hx - 1.6 * s, hy + 0.7 * s), (hx + 1.6 * s, hy + 0.7 * s),
            (hx + 1.1 * s, hy + 3.4 * s), (hx, hy + 4.0 * s), (hx - 1.1 * s, hy + 3.4 * s),
        ], outline, 1)
        rs.draw_poly(surf, highlight, [
            (hx - 0.9 * s, hy + 0.9 * s), (hx + 0.4 * s, hy + 0.9 * s),
            (hx + 0.3 * s, hy + 2.6 * s), (hx - 0.7 * s, hy + 2.6 * s),
        ], None, 0)
        for ox in (-0.55, 0.55):
            pygame.draw.line(
                surf, shadow,
                (hx + ox * s, hy + 2.8 * s), (hx + ox * s, hy + 3.5 * s),
                max(1, int(s * 0.4)),
            )
        pygame.draw.circle(surf, gold_d, (int(hx), int(hy - 1.8 * s)), max(2, int(0.7 * s)))
        pygame.draw.circle(surf, gold, (int(hx - 0.15 * s), int(hy - 1.95 * s)), max(1, int(0.4 * s)))
        for side in (-1, 1):
            rs.draw_poly(surf, gold_d, [
                (hx + side * 3.0 * s, hy + 1.2 * s),
                (hx + side * 3.6 * s, hy + 1.0 * s),
                (hx + side * 3.2 * s, hy + 2.8 * s),
            ], outline, 1)
        return

    # Compact metal medium-helm — sits on the skull, not a bucket
    rs.draw_volume(surf, base, [
        (hx - 4.5 * s, hy + 0.7 * s),
        (hx - 3.7 * s, hy - 3.5 * s),
        (hx - 1.0 * s, hy - 4.9 * s),
        (hx + 1.2 * s, hy - 4.9 * s),
        (hx + 3.7 * s, hy - 3.5 * s),
        (hx + 4.5 * s, hy + 0.7 * s),
        (hx + 3.3 * s, hy + 2.3 * s),
        (hx - 3.3 * s, hy + 2.3 * s),
    ], outline, 1, detail="metal_armor")
    rs.draw_poly(surf, highlight, [
        (hx - 2.2 * s, hy - 2.6 * s), (hx, hy - 4.4 * s),
        (hx + 1.1 * s, hy - 2.4 * s), (hx - 0.4 * s, hy - 1.5 * s),
    ], None, 0)
    pygame.draw.rect(surf, shadow, (hx - 3.4 * s, hy - 0.35 * s, 6.8 * s, 1.05 * s))
    pygame.draw.rect(surf, (14, 12, 12), (hx - 2.6 * s, hy - 0.15 * s, 5.2 * s, 0.65 * s))
    pygame.draw.line(
        surf, (70, 160, 210),
        (hx - 2.2 * s, hy + 0.15 * s), (hx + 2.2 * s, hy + 0.15 * s),
        max(1, int(s * 0.28)),
    )
    rs.draw_poly(surf, shadow, [
        (hx - 0.5 * s, hy + 0.5 * s), (hx + 0.5 * s, hy + 0.5 * s),
        (hx + 0.4 * s, hy + 2.5 * s), (hx - 0.4 * s, hy + 2.5 * s),
    ], outline, 1)
    rs.draw_poly(surf, shadow, [
        (hx - 4.0 * s, hy + 0.5 * s), (hx - 2.6 * s, hy + 0.5 * s),
        (hx - 2.5 * s, hy + 2.4 * s), (hx - 3.7 * s, hy + 2.0 * s),
    ], None, 0)
    rs.draw_poly(surf, shadow, [
        (hx + 2.6 * s, hy + 0.5 * s), (hx + 4.0 * s, hy + 0.5 * s),
        (hx + 3.7 * s, hy + 2.0 * s), (hx + 2.5 * s, hy + 2.4 * s),
    ], None, 0)
    for ox in (-2.0, 0, 2.0):
        pygame.draw.circle(surf, shadow, (int(hx + ox * s), int(hy - 2.8 * s)), max(1, int(0.32 * s)))
    if item_id and "steel" in item_id:
        plume, plume_d = (190, 40, 45), (120, 20, 25)
        rs.draw_poly(surf, plume, [
            (hx - 0.35 * s, hy - 4.4 * s),
            (hx + 0.15 * s, hy - 6.6 * s),
            (hx + 1.1 * s, hy - 5.8 * s),
            (hx + 0.55 * s, hy - 4.2 * s),
        ], plume_d, 1)



def _draw_dragon_emblem(surf, cx, cy, s):
    """Stylized gold dragon crest for Mythos plate — head + wings on chest."""
    gold = (232, 188, 72)
    gold_l = (255, 230, 140)
    gold_d = (150, 100, 32)
    ink = (35, 12, 10)
    crimson = (160, 22, 30)
    # Medallion disc (dark crimson face, gold rim)
    pygame.draw.circle(surf, gold_d, (int(cx), int(cy)), max(3, int(3.1 * s)))
    pygame.draw.circle(surf, crimson, (int(cx), int(cy)), max(2, int(2.55 * s)))
    pygame.draw.circle(surf, gold, (int(cx), int(cy)), max(3, int(3.1 * s)), max(1, int(s * 0.45)))
    pygame.draw.circle(surf, ink, (int(cx), int(cy)), max(3, int(3.1 * s)), 1)
    # Wings (spread behind head)
    left_wing = [
        (cx - 0.5 * s, cy - 0.15 * s),
        (cx - 3.4 * s, cy - 1.9 * s),
        (cx - 2.6 * s, cy - 0.15 * s),
        (cx - 3.1 * s, cy + 1.35 * s),
        (cx - 0.7 * s, cy + 0.55 * s),
    ]
    right_wing = [
        (cx + 0.5 * s, cy - 0.15 * s),
        (cx + 3.4 * s, cy - 1.9 * s),
        (cx + 2.6 * s, cy - 0.15 * s),
        (cx + 3.1 * s, cy + 1.35 * s),
        (cx + 0.7 * s, cy + 0.55 * s),
    ]
    rs.draw_poly(surf, gold_d, left_wing, ink, 1)
    rs.draw_poly(surf, gold_d, right_wing, ink, 1)
    rs.draw_poly(surf, gold, [
        (cx - 0.55 * s, cy - 0.1 * s), (cx - 2.6 * s, cy - 1.35 * s),
        (cx - 2.0 * s, cy), (cx - 0.75 * s, cy + 0.35 * s),
    ], None, 0)
    rs.draw_poly(surf, gold, [
        (cx + 0.55 * s, cy - 0.1 * s), (cx + 2.6 * s, cy - 1.35 * s),
        (cx + 2.0 * s, cy), (cx + 0.75 * s, cy + 0.35 * s),
    ], None, 0)
    # Dragon head (profile, facing right) — gold on crimson for contrast
    head = [
        (cx - 1.25 * s, cy + 0.2 * s),
        (cx - 1.0 * s, cy - 1.55 * s),
        (cx - 0.1 * s, cy - 1.95 * s),
        (cx + 0.65 * s, cy - 1.3 * s),
        (cx + 1.85 * s, cy - 0.6 * s),  # snout
        (cx + 2.05 * s, cy - 0.05 * s),
        (cx + 1.35 * s, cy + 0.4 * s),
        (cx + 0.4 * s, cy + 1.0 * s),
        (cx - 0.65 * s, cy + 0.9 * s),
    ]
    rs.draw_poly(surf, gold, head, ink, 1)
    rs.draw_poly(surf, gold_l, [
        (cx - 0.6 * s, cy - 1.15 * s), (cx, cy - 1.65 * s),
        (cx + 0.55 * s, cy - 1.05 * s), (cx + 0.2 * s, cy - 0.55 * s),
    ], None, 0)
    # Horn
    rs.draw_poly(surf, gold_d, [
        (cx - 0.4 * s, cy - 1.6 * s), (cx - 0.05 * s, cy - 2.7 * s),
        (cx + 0.4 * s, cy - 1.5 * s),
    ], ink, 1)
    # Jaw fang
    rs.draw_poly(surf, gold_l, [
        (cx + 0.9 * s, cy + 0.35 * s), (cx + 1.15 * s, cy + 1.15 * s),
        (cx + 1.35 * s, cy + 0.25 * s),
    ], None, 0)
    # Eye + nostril
    pygame.draw.circle(surf, (255, 70, 45), (int(cx + 0.3 * s), int(cy - 0.95 * s)), max(1, int(0.4 * s)))
    pygame.draw.circle(surf, (255, 230, 90), (int(cx + 0.18 * s), int(cy - 1.05 * s)), max(1, int(0.16 * s)))
    pygame.draw.circle(surf, ink, (int(cx + 1.6 * s), int(cy - 0.28 * s)), max(1, int(0.25 * s)))


def _draw_mythos_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, facing=1):
    """Extra ridges, gold trim, winged pauldrons, and dragon chest emblem."""
    gold = (232, 188, 72)
    gold_l = (255, 228, 130)
    gold_d = (150, 100, 32)
    # Gold collar torc
    rs.draw_poly(surf, gold_d, [
        (neck[0] - 2.6 * s, neck[1] + 1.7 * s),
        (neck[0] + 2.4 * s, neck[1] + 1.7 * s),
        (neck[0] + 1.6 * s, neck[1] + 4.9 * s),
        (neck[0] - 1.8 * s, neck[1] + 4.9 * s),
    ], None, 0)
    rs.draw_poly(surf, gold, [
        (neck[0] - 2.2 * s, neck[1] + 2.0 * s),
        (neck[0] + 2.0 * s, neck[1] + 2.0 * s),
        (neck[0] + 1.3 * s, neck[1] + 4.4 * s),
        (neck[0] - 1.5 * s, neck[1] + 4.4 * s),
    ], None, 0)
    # Scale rows between plate ridges
    for i in range(5):
        yy = neck[1] + (5.0 + i * 2.0) * s
        for j in range(-3, 4):
            xx = pelvis[0] + j * 1.15 * s + (0.35 * s if i % 2 else 0)
            if abs(j) > 2 and i > 3:
                continue
            pygame.draw.ellipse(
                surf, shirt_d,
                (xx - 0.55 * s, yy - 0.35 * s, 1.1 * s, 0.85 * s),
            )
            pygame.draw.ellipse(
                surf, shirt_l if j <= 0 else shirt_m,
                (xx - 0.35 * s, yy - 0.4 * s, 0.55 * s, 0.4 * s),
            )
    # Winged / horned pauldrons
    for side in (-1, 1):
        px = neck[0] + side * 5.6 * s
        py = neck[1] + 2.4 * s
        pygame.draw.circle(surf, shirt_m, (int(px), int(py)), max(3, int(3.0 * s)))
        pygame.draw.circle(surf, gold_d, (int(px), int(py)), max(3, int(3.0 * s)), max(1, int(s * 0.55)))
        pygame.draw.circle(surf, gold_l if side < 0 else gold, (int(px - 0.6 * s), int(py - 0.6 * s)), max(1, int(1.1 * s)))
        # Wing flare off shoulder
        wing = [
            (px, py - 0.8 * s),
            (px + side * 3.8 * s, py - 2.8 * s),
            (px + side * 3.2 * s, py - 0.4 * s),
            (px + side * 2.6 * s, py + 1.6 * s),
            (px + side * 0.4 * s, py + 1.2 * s),
        ]
        rs.draw_poly(surf, gold_d, wing, (42, 6, 10), 1)
        rs.draw_poly(surf, gold, [
            (px, py - 0.5 * s),
            (px + side * 2.8 * s, py - 2.1 * s),
            (px + side * 2.2 * s, py - 0.2 * s),
            (px + side * 0.5 * s, py + 0.6 * s),
        ], None, 0)
        # Horn tip
        tip = (px + side * 0.2 * s, py - 3.2 * s)
        rs.draw_poly(surf, gold, [
            (px - 0.5 * s, py - 1.2 * s), tip, (px + 0.5 * s, py - 1.2 * s),
        ], (42, 6, 10), 1)
    # Belt with gold buckle
    by = pelvis[1] - 1.1 * s
    pygame.draw.rect(surf, gold_d, (pelvis[0] - 3.6 * s, by, 7.2 * s, 1.35 * s))
    pygame.draw.rect(surf, gold, (pelvis[0] - 3.4 * s, by + 0.2 * s, 6.8 * s, 0.85 * s))
    pygame.draw.rect(surf, gold_l, (pelvis[0] - 0.9 * s, by - 0.15 * s, 1.8 * s, 1.6 * s))
    # Chest dragon emblem
    emblem_y = neck[1] + (pelvis[1] - neck[1]) * 0.40
    _draw_dragon_emblem(surf, pelvis[0], emblem_y, s * 1.05)


def _draw_eclipse_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, facing=1):
    """Black plate extras — gold filigree ridges, angular pauldrons, eclipse seal."""
    gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
    deep = (10, 10, 14)
    # Layered gold collar with void inset
    rs.draw_poly(surf, gold_d, [
        (neck[0] - 2.8 * s, neck[1] + 1.5 * s),
        (neck[0] + 2.6 * s, neck[1] + 1.5 * s),
        (neck[0] + 1.7 * s, neck[1] + 5.1 * s),
        (neck[0] - 1.9 * s, neck[1] + 5.1 * s),
    ], None, 0)
    rs.draw_poly(surf, gold, [
        (neck[0] - 2.3 * s, neck[1] + 1.9 * s),
        (neck[0] + 2.1 * s, neck[1] + 1.9 * s),
        (neck[0] + 1.35 * s, neck[1] + 4.5 * s),
        (neck[0] - 1.55 * s, neck[1] + 4.5 * s),
    ], None, 0)
    rs.draw_poly(surf, deep, [
        (neck[0] - 1.4 * s, neck[1] + 2.6 * s),
        (neck[0] + 1.2 * s, neck[1] + 2.6 * s),
        (neck[0] + 0.85 * s, neck[1] + 4.0 * s),
        (neck[0] - 1.0 * s, neck[1] + 4.0 * s),
    ], None, 0)
    # Gold-trimmed plate ridges + rivet row between each
    for i in range(5):
        yy = neck[1] + (5.2 + i * 2.05) * s
        pygame.draw.line(surf, gold_d, (pelvis[0] - 3.4 * s, yy), (pelvis[0] + 3.4 * s, yy), max(1, int(s * 0.4)))
        pygame.draw.line(surf, gold, (pelvis[0] - 3.1 * s, yy - 0.55 * s), (pelvis[0] + 1.8 * s, yy - 0.55 * s), 1)
        for j in range(-3, 4):
            xx = pelvis[0] + j * 1.1 * s
            pygame.draw.circle(surf, gold_d, (int(xx), int(yy + 0.55 * s)), max(1, int(0.32 * s)))
            if j % 2 == 0:
                pygame.draw.circle(surf, gold_l, (int(xx - 0.1 * s), int(yy + 0.4 * s)), max(1, int(0.18 * s)))
    # Central void seam with gold twin lines
    pygame.draw.line(surf, deep, (pelvis[0], neck[1] + 4.4 * s), (pelvis[0], pelvis[1] - 0.6 * s), max(2, int(s * 0.55)))
    pygame.draw.line(surf, gold_d, (pelvis[0] - 0.55 * s, neck[1] + 4.6 * s), (pelvis[0] - 0.55 * s, pelvis[1] - 0.8 * s), 1)
    pygame.draw.line(surf, gold_d, (pelvis[0] + 0.55 * s, neck[1] + 4.6 * s), (pelvis[0] + 0.55 * s, pelvis[1] - 0.8 * s), 1)
    # Angular spiked pauldrons
    for side in (-1, 1):
        px = neck[0] + side * 5.7 * s
        py = neck[1] + 2.5 * s
        pygame.draw.circle(surf, shirt_m, (int(px), int(py)), max(3, int(2.9 * s)))
        pygame.draw.circle(surf, gold_d, (int(px), int(py)), max(3, int(2.9 * s)), max(1, int(s * 0.6)))
        pygame.draw.circle(surf, gold_l if side < 0 else gold, (int(px - 0.55 * s), int(py - 0.55 * s)), max(1, int(1.05 * s)))
        spike = [
            (px - side * 0.3 * s, py - 1.0 * s),
            (px + side * 1.2 * s, py - 3.6 * s),
            (px + side * 2.8 * s, py - 2.4 * s),
            (px + side * 2.2 * s, py - 0.2 * s),
            (px + side * 0.8 * s, py + 0.8 * s),
        ]
        rs.draw_poly(surf, gold_d, spike, (8, 8, 12), 1)
        rs.draw_poly(surf, gold, [
            (px, py - 0.8 * s),
            (px + side * 1.0 * s, py - 2.8 * s),
            (px + side * 2.0 * s, py - 1.8 * s),
            (px + side * 0.6 * s, py + 0.2 * s),
        ], None, 0)
        # Gold studs on pauldron face
        for ox, oy in ((-0.6, -0.3), (0.5, 0.4), (-0.2, 0.9)):
            pygame.draw.circle(surf, gold, (int(px + ox * s), int(py + oy * s)), max(1, int(0.35 * s)))
    # Fauld / belt with eclipse buckle
    by = pelvis[1] - 1.15 * s
    pygame.draw.rect(surf, gold_d, (pelvis[0] - 3.8 * s, by, 7.6 * s, 1.5 * s))
    pygame.draw.rect(surf, gold, (pelvis[0] - 3.5 * s, by + 0.25 * s, 7.0 * s, 0.9 * s))
    for ox in (-2.8, -1.4, 1.4, 2.8):
        pygame.draw.circle(surf, gold_l, (int(pelvis[0] + ox * s), int(by + 0.7 * s)), max(1, int(0.3 * s)))
    bx, byy = pelvis[0], by + 0.55 * s
    pygame.draw.circle(surf, gold_d, (int(bx), int(byy)), max(3, int(1.55 * s)))
    pygame.draw.circle(surf, deep, (int(bx), int(byy)), max(2, int(1.15 * s)))
    pygame.draw.circle(surf, gold, (int(bx - 0.25 * s), int(byy - 0.15 * s)), max(2, int(0.7 * s)), max(1, int(s * 0.28)))
    # Chest eclipse seal
    ex = pelvis[0]
    ey = neck[1] + (pelvis[1] - neck[1]) * 0.38
    pygame.draw.circle(surf, gold_d, (int(ex), int(ey)), max(3, int(2.4 * s)))
    pygame.draw.circle(surf, gold, (int(ex), int(ey)), max(3, int(2.4 * s)), max(1, int(s * 0.4)))
    pygame.draw.circle(surf, deep, (int(ex), int(ey)), max(2, int(1.85 * s)))
    pygame.draw.circle(surf, (18, 18, 22), (int(ex + 0.25 * s), int(ey + 0.1 * s)), max(2, int(1.25 * s)))
    pygame.draw.circle(surf, gold, (int(ex - 0.45 * s), int(ey - 0.15 * s)), max(2, int(0.95 * s)), max(1, int(s * 0.3)))
    # Tiny dragon crest inside seal
    ds = s * 0.7
    rs.draw_poly(surf, gold, [
        (ex - 0.55 * ds, ey + 0.1 * ds), (ex - 0.35 * ds, ey - 0.75 * ds),
        (ex + 0.55 * ds, ey - 0.2 * ds), (ex + 0.2 * ds, ey + 0.45 * ds),
    ], (8, 8, 10), 1)
    pygame.draw.circle(surf, (255, 70, 45), (int(ex + 0.1 * ds), int(ey - 0.25 * ds)), max(1, int(0.2 * ds)))


def _draw_eclipse_leg_ornament(surf, hip, knee, foot, s, pants_m, pants_d, pants_l):
    """Gold-trimmed greaves, ornate knee-cop, thigh ridge for eclipse platelegs."""
    gold, gold_d, gold_l = (228, 196, 78), (160, 120, 40), (255, 230, 140)
    # Outer thigh ridge (along the bone)
    pygame.draw.line(surf, gold_d, (hip[0], hip[1] + 0.8 * s), (knee[0], knee[1] - 0.6 * s), max(2, int(s * 0.55)))
    pygame.draw.line(surf, gold, (hip[0] + 0.15 * s, hip[1] + 1.0 * s), (knee[0] + 0.1 * s, knee[1] - 0.4 * s), 1)
    for t in (0.25, 0.5, 0.75):
        xx = hip[0] + (knee[0] - hip[0]) * t
        yy = hip[1] + (knee[1] - hip[1]) * t
        pygame.draw.circle(surf, gold_d, (int(xx), int(yy)), max(1, int(0.4 * s)))
        pygame.draw.circle(surf, gold_l, (int(xx - 0.1 * s), int(yy - 0.1 * s)), max(1, int(0.2 * s)))
    # Ornate knee cop
    pygame.draw.circle(surf, pants_m, (int(knee[0]), int(knee[1])), max(3, int(1.85 * s)))
    pygame.draw.circle(surf, gold_d, (int(knee[0]), int(knee[1])), max(3, int(1.85 * s)), max(1, int(s * 0.5)))
    pygame.draw.circle(surf, gold, (int(knee[0]), int(knee[1])), max(3, int(1.85 * s)), max(1, int(s * 0.28)))
    pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.4 * s), int(knee[1] - 0.4 * s)), max(1, int(0.75 * s)))
    pygame.draw.circle(surf, gold_l, (int(knee[0] - 0.15 * s), int(knee[1] - 0.2 * s)), max(1, int(0.35 * s)))
    # Thin gold shin trim only (no floating greave plate — that read as a detached boot)
    dx, dy = foot[0] - knee[0], foot[1] - knee[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    g0 = (knee[0] + ux * 1.4 * s, knee[1] + uy * 1.4 * s)
    g1 = (foot[0] - ux * 0.35 * s, foot[1] - uy * 0.35 * s)
    pygame.draw.line(surf, gold_d, g0, g1, max(2, int(s * 0.4)))
    pygame.draw.line(surf, gold, g0, g1, max(1, int(s * 0.22)))
    # Ankle cuff seated on the foot joint (drawn under the boot upper)
    ax, ay = foot[0], foot[1] - 0.15 * s
    cuff_w = 1.35 * s
    pygame.draw.line(
        surf, gold_d,
        (ax - px * cuff_w, ay - py * cuff_w),
        (ax + px * cuff_w, ay + py * cuff_w),
        max(2, int(s * 0.45)),
    )
    pygame.draw.line(
        surf, gold,
        (ax - px * cuff_w * 0.85, ay - py * cuff_w * 0.85),
        (ax + px * cuff_w * 0.85, ay + py * cuff_w * 0.85),
        1,
    )


def _draw_boot(surf, fx, fy, s, facing, boots_base, outline):
    """Planted boot: sole contact + upper with lit toe, slight asymmetry.

    facing ±1 = side profile (toe along facing). facing 0 = front/back plant
    (centered under the ankle so boots don't slide off the shin).
    """
    # Ankle seal — fills the taper gap where the calf meets the boot
    pygame.draw.circle(surf, boots_base, (int(fx), int(fy - 0.6 * s)), max(2, int(1.9 * s)))
    pygame.draw.circle(surf, rs.shade(boots_base, 18), (int(fx - 0.35 * s), int(fy - 0.9 * s)), max(1, int(0.85 * s)))
    if not facing:
        # Ortho plant — round sole under the ankle, tall upper overlaps the shin
        sole = [
            (fx - 2.6 * s, fy + 0.35 * s),
            (fx + 2.6 * s, fy + 0.35 * s),
            (fx + 2.4 * s, fy + 2.4 * s),
            (fx - 2.4 * s, fy + 2.4 * s),
        ]
        rs.draw_volume(surf, rs.shade(boots_base, -18), sole, outline, 1)
        upper = [
            (fx - 2.05 * s, fy - 3.1 * s),
            (fx + 2.05 * s, fy - 3.1 * s),
            (fx + 2.25 * s, fy + 0.55 * s),
            (fx - 2.25 * s, fy + 0.55 * s),
        ]
        rs.draw_volume(surf, boots_base, upper, outline, 1)
        rs.draw_poly(surf, rs.shade(boots_base, 28), [
            (fx - 1.2 * s, fy - 2.2 * s),
            (fx + 0.45 * s, fy - 2.3 * s),
            (fx + 0.55 * s, fy + 0.1 * s),
            (fx - 1.1 * s, fy + 0.15 * s),
        ], None, 0)
        return
    # Side profile — ankle seated on the foot joint; tall upper covers the shin join
    ax = fx - 0.25 * s * facing
    sole = [
        (ax - 2.2 * s * facing, fy + 0.3 * s),
        (ax + 3.8 * s * facing, fy + 0.1 * s),
        (ax + 4.0 * s * facing, fy + 2.5 * s),
        (ax - 1.8 * s * facing, fy + 2.65 * s),
    ]
    rs.draw_volume(surf, rs.shade(boots_base, -18), sole, outline, 1)
    upper = [
        (ax - 1.55 * s * facing, fy - 3.15 * s),
        (ax + 1.65 * s * facing, fy - 3.3 * s),
        (ax + 2.75 * s * facing, fy + 0.35 * s),
        (ax + 0.25 * s * facing, fy + 0.85 * s),
        (ax - 1.75 * s * facing, fy + 0.5 * s),
    ]
    rs.draw_volume(surf, boots_base, upper, outline, 1)
    # Toe highlight
    rs.draw_poly(surf, rs.shade(boots_base, 28), [
        (ax + 0.85 * s * facing, fy - 1.5 * s),
        (ax + 2.35 * s * facing, fy - 1.7 * s),
        (ax + 2.65 * s * facing, fy + 0.05 * s),
        (ax + 1.05 * s * facing, fy + 0.25 * s),
    ], None, 0)


def _draw_hand(surf, hx, hy, s, skin_m, skin_l, outline):
    """Palm + slight finger mass (readable at gameplay scale)."""
    rs.draw_volume(surf, skin_m, [
        (hx - 1.5 * s, hy - 1.1 * s), (hx + 1.6 * s, hy - 1.0 * s),
        (hx + 1.8 * s, hy + 1.3 * s), (hx + 0.3 * s, hy + 2.0 * s),
        (hx - 1.4 * s, hy + 1.2 * s),
    ], outline, 1, detail="skin")
    pygame.draw.circle(surf, skin_l, (int(hx - 0.35 * s), int(hy - 0.35 * s)), max(1, int(0.65 * s)))


def _draw_ortho_humanoid(
    surf, cx, cy, s, view, moving, t, pose,
    shirt_base, shirt_l, shirt_m, shirt_d,
    pants_base, pants_l, pants_m, pants_d,
    skin_l, skin_m, skin_d, hair_m, hair_d, boots_base, outline,
    body_id, legs_id, helmet_id, shield_id, weapon_id, wkind,
    shield, robe, body_color, feminine, attacking, action, equipment,
):
    """
    Front (walk down) / back (walk up) views.
    Keeps the same armour materials as the side view — plate ridges, pauldrons, helmet.
    Contralateral gait: opposite arm/leg depth offsets (see gait-cycle reference).
    """
    bob = pose.get("root_bob", 0.0) * s * 0.55
    # Match walk cadence used by pose_walk
    ph = t * rs.TAU * 1.15 if moving else 0.0
    depth = 1.0 if view == "front" else -1.0

    # Modest stride — feet stay near the ground (depth = small Y bias)
    stride = 0.75 * s
    arm_swing = 2.4 * s
    # Contralateral: left leg fwd ⇒ right arm fwd (same sign on sin for arm_r vs leg_l)
    leg_l = math.sin(ph) * stride * depth
    leg_r = math.sin(ph + math.pi) * stride * depth
    arm_l = math.sin(ph + math.pi) * arm_swing * depth  # opposite to left leg
    arm_r = math.sin(ph) * arm_swing * depth
    lift_l = max(0.0, math.cos(ph)) ** 1.2 * 0.45 * s if moving else 0.0
    lift_r = max(0.0, math.cos(ph + math.pi)) ** 1.2 * 0.45 * s if moving else 0.0

    hip_w = 3.3 if feminine else 2.85
    sh_w = 5.1 if feminine else 5.5
    pelvis = (cx, cy + 3.2 * s + bob)
    neck = (cx, pelvis[1] - (12.4 if feminine else 13.0) * s)
    hip_l = (pelvis[0] - hip_w * s, pelvis[1])
    hip_r = (pelvis[0] + hip_w * s, pelvis[1])
    sh_l = (neck[0] - sh_w * s, neck[1] + 2.6 * s)
    sh_r = (neck[0] + sh_w * s, neck[1] + 2.6 * s)

    knee_l = (hip_l[0], hip_l[1] + 6.3 * s - lift_l * 0.4 + leg_l * 0.35)
    knee_r = (hip_r[0], hip_r[1] + 6.3 * s - lift_r * 0.4 + leg_r * 0.35)
    foot_l = (hip_l[0], hip_l[1] + 12.7 * s - lift_l + leg_l)
    foot_r = (hip_r[0], hip_r[1] + 12.7 * s - lift_r + leg_r)
    el_l = (sh_l[0] - 0.5 * s, sh_l[1] + 4.8 * s + arm_l * 0.5)
    el_r = (sh_r[0] + 0.5 * s, sh_r[1] + 4.8 * s + arm_r * 0.5)
    hand_l = (sh_l[0] - 0.65 * s, sh_l[1] + 9.3 * s + arm_l)
    hand_r = (sh_r[0] + 0.65 * s, sh_r[1] + 9.3 * s + arm_r)

    foot_y = max(foot_l[1], foot_r[1]) + 2.2 * s
    rs.draw_contact_shadow(surf, cx, foot_y, 8.5 * s, 3.2 * s, 150)
    rs.draw_cast_shadow(surf, cx + 1.2 * s, foot_y + 0.4 * s, 11.0 * s, 3.4 * s, 90)

    is_plate = bool(body_id and ("plate" in body_id or (body_id.endswith("_body") and "chain" not in body_id and "leather" not in body_id)))
    is_chain = bool(body_id and "chain" in body_id)
    is_leather = bool(body_id and "leather" in body_id)
    if is_plate or is_chain:
        shirt_detail = "metal_armor"
    elif is_leather:
        shirt_detail = "leather"
    elif robe:
        shirt_detail = "fabric"
    else:
        shirt_detail = "cloth"

    on_back = (
        float(attacking or 0) <= 0.01
        and action in (None, "stand")
        and ((bool(wkind) and wkind != "rod") or bool(shield))
    )

    # --- Back layer: cape + sheathed gear for FRONT view (drawn first; torso covers) ---
    # Walk-up (back view): gear is drawn later ON the backplate so it faces the camera.
    if view == "back" or on_back:
        if robe or (body_id and "cape" in (body_id or "")):
            cape_col = rs.shade(body_color, -22)
            rs.draw_volume(surf, cape_col, [
                (neck[0] - 4.6 * s, neck[1] + 2.0 * s),
                (neck[0] + 4.6 * s, neck[1] + 2.0 * s),
                (pelvis[0] + 6.2 * s, pelvis[1] + 9 * s),
                (pelvis[0] - 6.2 * s, pelvis[1] + 9 * s),
            ], outline, 1)
        if view == "front" and on_back:
            if shield:
                _draw_shield(
                    surf, neck[0] - 3.0 * s, neck[1] + 4.6 * s, s * 1.0,
                    shield_id or "wooden_shield", on_back=True, facing=1,
                )
            if wkind and wkind != "rod":
                _draw_weapon(
                    surf, neck[0] + 4.6 * s, neck[1] - 3.2 * s, s * 0.78, wkind,
                    1, weapon_id, 0.0, sheathed=True,
                )

    def _depth_y(pt):
        return pt[1] if view == "front" else -pt[1]

    # Legs
    thigh_w = 2.35 * s if feminine else 2.15 * s
    calf_w = 1.55 * s if feminine else 1.75 * s
    pant_detail = "metal_armor" if legs_id and ("plate" in legs_id or "chain" in legs_id or "eclipse" in legs_id) else "cloth"
    for foot, knee, hip in sorted(
        ((foot_l, knee_l, hip_l), (foot_r, knee_r, hip_r)),
        key=lambda tr: _depth_y(tr[0]),
    ):
        rs.draw_volume_limb(surf, *hip, *knee, thigh_w, pants_base, outline, taper=0.82, bulge=0.14, detail=pant_detail)
        rs.draw_volume_limb(surf, *knee, *foot, calf_w, pants_base, outline, taper=0.72, bulge=0.08, detail=pant_detail)
        if legs_id and "eclipse" in legs_id:
            _draw_eclipse_leg_ornament(surf, hip, knee, foot, s, pants_m, pants_d, pants_l)
        elif legs_id and ("plate" in legs_id or "chain" in legs_id):
            pygame.draw.circle(surf, pants_m, (int(knee[0]), int(knee[1])), max(2, int(1.55 * s)))
            pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.35 * s), int(knee[1] - 0.35 * s)), max(1, int(0.8 * s)))
            pygame.draw.circle(surf, pants_d, (int(knee[0]), int(knee[1])), max(2, int(1.55 * s)), 1)
        else:
            pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.2 * s), int(knee[1] - 0.2 * s)), max(1, int(1.0 * s)))
        _draw_boot(surf, *foot, s * 0.92, 0, boots_base, outline)

    # Back-view arms behind torso so they peek at the sides
    def _draw_arms():
        for hand, el, sh in sorted(
            ((hand_l, el_l, sh_l), (hand_r, el_r, sh_r)),
            key=lambda tr: _depth_y(tr[0]),
        ):
            rs.draw_volume_limb(surf, *sh, *el, 1.7 * s, shirt_base, outline, taper=0.8, bulge=0.1, detail=shirt_detail)
            rs.draw_volume_limb(surf, *el, *hand, 1.4 * s, skin_m, outline, taper=0.75, bulge=0.06, detail="skin")
            _draw_hand(surf, *hand, s * 0.95, skin_m, skin_l, outline)

    if view == "back":
        _draw_arms()

    # Torso — same materials as side view
    chest = [
        (pelvis[0] - 4.0 * s, pelvis[1] - 0.2 * s),
        (pelvis[0] + 4.0 * s, pelvis[1] - 0.2 * s),
        (neck[0] + 4.4 * s, neck[1] + 1.6 * s),
        (neck[0] - 4.4 * s, neck[1] + 1.6 * s),
    ]
    if feminine:
        chest = [
            (pelvis[0] - 4.4 * s, pelvis[1] - 0.2 * s),
            (pelvis[0] + 4.4 * s, pelvis[1] - 0.2 * s),
            (neck[0] + 3.6 * s, neck[1] + 1.6 * s),
            (neck[0] - 3.6 * s, neck[1] + 1.6 * s),
        ]
    rs.draw_volume(surf, shirt_base, chest, outline, max(1, int(s * 0.35)), detail=shirt_detail)

    # Chest highlight (front only)
    if view == "front":
        rs.draw_poly(surf, shirt_l, [
            (pelvis[0] - 2.4 * s, pelvis[1] - 0.6 * s),
            (pelvis[0] + 0.4 * s, pelvis[1] - 0.6 * s),
            (neck[0] + 0.2 * s, neck[1] + 3.8 * s),
            (neck[0] - 3.6 * s, neck[1] + 3.5 * s),
        ], None, 0)

    # Pauldrons
    for side, lit in ((-1, shirt_l), (1, shirt_d)):
        px = neck[0] + side * sh_w * s
        py = neck[1] + 2.8 * s
        pygame.draw.circle(surf, shirt_m, (int(px), int(py)), max(2, int(2.5 * s)))
        pygame.draw.circle(surf, lit, (int(px - 0.4 * s), int(py - 0.4 * s)), max(1, int(1.15 * s)))
        pygame.draw.circle(surf, shirt_d, (int(px), int(py)), max(2, int(2.5 * s)), 1)

    # Collar
    rs.draw_poly(surf, shirt_l if view == "front" else shirt_d, [
        (neck[0] - 2.2 * s, neck[1] + 1.8 * s),
        (neck[0] + 2.2 * s, neck[1] + 1.8 * s),
        (neck[0] + 1.4 * s, neck[1] + 4.4 * s),
        (neck[0] - 1.4 * s, neck[1] + 4.4 * s),
    ], None, 0)

    if is_plate:
        for i in range(4):
            yy = neck[1] + (4.6 + i * 2.4) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3.2 * s, yy), (pelvis[0] + 3.2 * s, yy), max(1, int(s * 0.45)))
            if view == "front":
                pygame.draw.line(surf, shirt_l, (pelvis[0] - 3.0 * s, yy - 0.7 * s), (pelvis[0] + 1.4 * s, yy - 0.7 * s), 1)
        pygame.draw.line(surf, shirt_d, (pelvis[0], neck[1] + 4.2 * s), (pelvis[0], pelvis[1] - 0.5 * s), max(1, int(s * 0.4)))
        if body_id and "mythos" in body_id and view == "front":
            _draw_mythos_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, 1)
        elif body_id and "eclipse" in body_id and view == "front":
            _draw_eclipse_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, 1)
    elif is_chain:
        for i in range(5):
            yy = neck[1] + (4.0 + i * 2.0) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3.0 * s, yy), (pelvis[0] + 3.0 * s, yy), 1)
            for j in range(5):
                xx = pelvis[0] + (j - 2) * 1.4 * s
                pygame.draw.circle(surf, shirt_d, (int(xx), int(yy + 0.55 * s)), max(1, int(0.35 * s)), 1)
    elif is_leather and view == "front":
        for i in range(3):
            yy = neck[1] + (5.0 + i * 2.8) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 2.8 * s, yy), (pelvis[0] + 2.8 * s, yy), 1)

    # Belt
    bw = 5.0 if feminine else 4.5
    rs.draw_volume(surf, rs.shade(pants_base, -28), [
        (pelvis[0] - bw * s, pelvis[1] - 0.7 * s),
        (pelvis[0] + bw * s, pelvis[1] - 0.7 * s),
        (pelvis[0] + bw * s, pelvis[1] + 0.9 * s),
        (pelvis[0] - bw * s, pelvis[1] + 0.9 * s),
    ], outline, 1)
    pygame.draw.rect(surf, (200, 170, 70), (pelvis[0] - 1.1 * s, pelvis[1] - 0.15 * s, 2.2 * s, 1.5 * s))

    # Walk-up: sheathed gear on the backplate (before head so helm stays on top).
    if view == "back" and on_back:
        if shield:
            # Offset left so it reads as strapped gear, not a chest emblem.
            _draw_shield(
                surf, neck[0] - 1.6 * s, neck[1] + 5.6 * s, s * 0.95,
                shield_id or "wooden_shield", on_back=True, facing=1, face_on=True,
            )
        if wkind and wkind != "rod":
            _draw_weapon(
                surf, neck[0] + 3.6 * s, neck[1] - 2.8 * s, s * 0.82, wkind,
                1, weapon_id, 0.0, sheathed=True, back_view=True,
            )

    # Head
    hx, hy = neck[0], neck[1] - 0.35 * s
    if helmet_id:
        _draw_helmet(surf, hx, hy, s * 0.72, helmet_id)
        if view == "back":
            # Cover the faceplate with a solid back-of-helm disc
            pygame.draw.ellipse(
                surf, shirt_d if is_plate else rs.shade(hair_m, -10),
                (int(hx - 2.6 * s), int(hy - 2.8 * s), int(5.2 * s), int(5.6 * s)),
            )
            pygame.draw.ellipse(
                surf, outline,
                (int(hx - 2.6 * s), int(hy - 2.8 * s), int(5.2 * s), int(5.6 * s)), 1,
            )
    elif view == "back":
        if feminine:
            # Full cape of hair behind the skull — walk-up must not read as male bowl-cut
            soft_hair = rs.shade(hair_m, -18)
            rs.draw_volume(surf, hair_m, [
                (hx - 4.0 * s, hy - 0.4 * s), (hx - 3.2 * s, hy - 3.6 * s),
                (hx, hy - 5.0 * s), (hx + 3.2 * s, hy - 3.6 * s),
                (hx + 4.0 * s, hy - 0.4 * s),
                (hx + 4.4 * s, hy + 5.0 * s), (hx + 3.2 * s, hy + 10.0 * s),
                (hx + 1.4 * s, hy + 9.4 * s), (hx, hy + 4.2 * s),
                (hx - 1.4 * s, hy + 9.4 * s), (hx - 3.2 * s, hy + 10.0 * s),
                (hx - 4.4 * s, hy + 5.0 * s),
            ], soft_hair, 1)
            # Narrower skull / neck — no heavy male jaw mass
            ip = [
                (hx - 2.35 * s, hy + 0.15 * s), (hx - 2.15 * s, hy - 2.5 * s),
                (hx - 0.65 * s, hy - 3.75 * s), (hx + 0.65 * s, hy - 3.75 * s),
                (hx + 2.15 * s, hy - 2.5 * s), (hx + 2.35 * s, hy + 0.15 * s),
                (hx + 1.05 * s, hy + 1.55 * s), (hx - 1.05 * s, hy + 1.55 * s),
            ]
            pygame.draw.polygon(surf, skin_m, [(int(p[0]), int(p[1])) for p in ip])
            rs.draw_poly(surf, skin_l, [
                (hx - 1.3 * s, hy - 2.3 * s), (hx + 1.3 * s, hy - 2.3 * s),
                (hx + 1.1 * s, hy - 0.15 * s), (hx - 1.1 * s, hy - 0.15 * s),
            ], None, 0)
            # Soft crown rim only
            pygame.draw.lines(surf, rs.shade(skin_m, -20), False, [
                (int(hx - 2.0 * s), int(hy - 1.9 * s)),
                (int(hx - 0.65 * s), int(hy - 3.55 * s)),
                (int(hx + 0.65 * s), int(hy - 3.55 * s)),
                (int(hx + 2.0 * s), int(hy - 1.9 * s)),
            ], 1)
            # Rounded feminine crown (not a flat male bowl rim)
            rs.draw_volume(surf, hair_m, [
                (hx - 3.4 * s, hy - 0.2 * s), (hx - 2.6 * s, hy - 3.6 * s),
                (hx, hy - 4.8 * s), (hx + 2.6 * s, hy - 3.6 * s),
                (hx + 3.4 * s, hy - 0.2 * s),
                (hx + 2.6 * s, hy + 1.6 * s), (hx + 1.2 * s, hy + 2.8 * s),
                (hx - 1.2 * s, hy + 2.8 * s), (hx - 2.6 * s, hy + 1.6 * s),
            ], soft_hair, 1)
            # Centre part highlight so it doesn't read as a solid male cap
            rs.draw_poly(surf, hair_d, [
                (hx - 0.35 * s, hy - 4.2 * s), (hx + 0.35 * s, hy - 4.2 * s),
                (hx + 0.25 * s, hy + 1.8 * s), (hx - 0.25 * s, hy + 1.8 * s),
            ], None, 0)
        else:
            # Male back — soft brown hair cap (no black outline blob at TILE≈40)
            soft_hair = rs.shade(hair_m, -16)
            pygame.draw.polygon(surf, skin_m, [(int(p[0]), int(p[1])) for p in [
                (hx - 2.6 * s, hy + 0.2 * s), (hx - 2.4 * s, hy - 2.6 * s),
                (hx - 0.6 * s, hy - 3.9 * s), (hx + 0.6 * s, hy - 3.9 * s),
                (hx + 2.4 * s, hy - 2.6 * s), (hx + 2.6 * s, hy + 0.2 * s),
                (hx + 1.4 * s, hy + 2.0 * s), (hx - 1.4 * s, hy + 2.0 * s),
            ]])
            rs.draw_poly(surf, skin_l, [
                (hx - 1.3 * s, hy - 2.2 * s), (hx + 1.3 * s, hy - 2.2 * s),
                (hx + 1.1 * s, hy - 0.1 * s), (hx - 1.1 * s, hy - 0.1 * s),
            ], None, 0)
            rs.draw_volume(surf, hair_m, [
                (hx - 3.0 * s, hy - 0.1 * s), (hx - 2.5 * s, hy - 3.4 * s),
                (hx, hy - 4.5 * s), (hx + 2.5 * s, hy - 3.4 * s),
                (hx + 3.0 * s, hy - 0.1 * s), (hx + 2.2 * s, hy + 1.15 * s),
                (hx - 2.2 * s, hy + 1.15 * s),
            ], soft_hair, 1)
    else:
        # Front face
        if feminine:
            soft_hair = rs.shade(hair_m, -18)
            # Wide side cascades first (behind cheeks) — match side-view female volume
            rs.draw_volume(surf, hair_m, [
                (hx - 2.8 * s, hy - 2.4 * s), (hx - 4.2 * s, hy - 1.4 * s),
                (hx - 4.6 * s, hy + 4.2 * s), (hx - 3.8 * s, hy + 9.6 * s),
                (hx - 2.9 * s, hy + 9.2 * s), (hx - 2.7 * s, hy + 1.2 * s),
            ], soft_hair, 1)
            rs.draw_volume(surf, hair_m, [
                (hx + 2.8 * s, hy - 2.4 * s), (hx + 4.2 * s, hy - 1.4 * s),
                (hx + 4.6 * s, hy + 4.2 * s), (hx + 3.8 * s, hy + 9.6 * s),
                (hx + 2.9 * s, hy + 9.2 * s), (hx + 2.7 * s, hy + 1.2 * s),
            ], soft_hair, 1)
            # Softer, narrower skull — no heavy chin (outline reads as beard at this scale)
            skull = [
                (hx - 2.45 * s, hy + 0.1 * s), (hx - 2.25 * s, hy - 2.55 * s),
                (hx - 0.7 * s, hy - 4.0 * s), (hx + 0.7 * s, hy - 4.0 * s),
                (hx + 2.25 * s, hy - 2.55 * s), (hx + 2.45 * s, hy + 0.1 * s),
                (hx + 1.05 * s, hy + 2.0 * s), (hx - 1.05 * s, hy + 2.0 * s),
            ]
            pygame.draw.polygon(surf, skin_m, [(int(p[0]), int(p[1])) for p in skull])
            rs.draw_poly(surf, skin_l, [
                (hx - 1.4 * s, hy - 2.5 * s), (hx + 1.4 * s, hy - 2.5 * s),
                (hx + 1.2 * s, hy + 0.35 * s), (hx - 1.2 * s, hy + 0.35 * s),
            ], None, 0)
            pygame.draw.lines(surf, rs.shade(skin_m, -20), False, [
                (int(hx - 2.1 * s), int(hy - 2.0 * s)),
                (int(hx - 0.65 * s), int(hy - 3.8 * s)),
                (int(hx + 0.65 * s), int(hy - 3.8 * s)),
                (int(hx + 2.1 * s), int(hy - 2.0 * s)),
            ], 1)
            # Soft fringe crown — scalloped bangs, not a male bowl rim
            rs.draw_volume(surf, hair_m, [
                (hx - 3.1 * s, hy - 0.7 * s), (hx - 2.4 * s, hy - 3.7 * s),
                (hx, hy - 4.7 * s), (hx + 2.4 * s, hy - 3.7 * s),
                (hx + 3.1 * s, hy - 0.7 * s),
                (hx + 2.0 * s, hy - 0.15 * s), (hx + 1.0 * s, hy - 1.15 * s),
                (hx, hy - 0.35 * s), (hx - 1.0 * s, hy - 1.15 * s),
                (hx - 2.0 * s, hy - 0.15 * s),
            ], soft_hair, 1)
            rs.draw_poly(surf, hair_d, [
                (hx - 1.5 * s, hy - 1.4 * s), (hx, hy - 4.0 * s),
                (hx + 1.5 * s, hy - 1.4 * s), (hx, hy - 1.7 * s),
            ], None, 0)
            eye_y = hy - 0.15 * s
            for ex in (-1.05, 1.05):
                exx = hx + ex * s
                pygame.draw.ellipse(surf, (250, 248, 240), (exx - 0.48 * s, eye_y - 0.38 * s, 0.96 * s, 0.76 * s))
                pygame.draw.circle(surf, (55, 90, 130), (int(exx), int(eye_y)), max(1, int(0.30 * s)))
                pygame.draw.circle(surf, (20, 22, 28), (int(exx + 0.04 * s), int(eye_y)), max(1, int(0.14 * s)))
            # Thin soft brows (thick dark brows read as stubble)
            brow = rs.shade(hair_m, -10)
            pygame.draw.line(surf, brow, (hx - 1.45 * s, hy - 1.0 * s), (hx - 0.35 * s, hy - 1.12 * s), max(1, int(s * 0.22)))
            pygame.draw.line(surf, brow, (hx + 0.35 * s, hy - 1.12 * s), (hx + 1.45 * s, hy - 1.0 * s), max(1, int(s * 0.22)))
            pygame.draw.line(surf, (160, 100, 105), (hx - 0.55 * s, hy + 1.25 * s), (hx + 0.55 * s, hy + 1.3 * s), max(1, int(s * 0.26)))
        else:
            # Male front — clean face (no skin texture dither / heavy outline)
            soft_hair = rs.shade(hair_m, -16)
            pygame.draw.polygon(surf, skin_m, [(int(p[0]), int(p[1])) for p in [
                (hx - 2.7 * s, hy + 0.15 * s), (hx - 2.5 * s, hy - 2.6 * s),
                (hx - 0.75 * s, hy - 3.9 * s), (hx + 0.75 * s, hy - 3.9 * s),
                (hx + 2.5 * s, hy - 2.6 * s), (hx + 2.7 * s, hy + 0.15 * s),
                (hx + 1.4 * s, hy + 2.4 * s), (hx - 1.4 * s, hy + 2.4 * s),
            ]])
            rs.draw_poly(surf, skin_l, [
                (hx - 1.4 * s, hy - 2.4 * s), (hx + 1.4 * s, hy - 2.4 * s),
                (hx + 1.2 * s, hy + 0.35 * s), (hx - 1.2 * s, hy + 0.35 * s),
            ], None, 0)
            rs.draw_volume(surf, hair_m, [
                (hx - 2.9 * s, hy - 1.0 * s), (hx - 2.2 * s, hy - 3.6 * s),
                (hx, hy - 4.45 * s), (hx + 2.2 * s, hy - 3.6 * s),
                (hx + 2.9 * s, hy - 1.0 * s), (hx + 1.55 * s, hy - 1.45 * s),
                (hx - 1.55 * s, hy - 1.45 * s),
            ], soft_hair, 1)
            eye_y = hy - 0.1 * s
            for ex in (-1.15, 1.15):
                exx = hx + ex * s
                pygame.draw.ellipse(surf, (250, 248, 240), (exx - 0.5 * s, eye_y - 0.4 * s, 1.0 * s, 0.8 * s))
                pygame.draw.circle(surf, (55, 90, 130), (int(exx), int(eye_y)), max(1, int(0.32 * s)))
                pygame.draw.circle(surf, (20, 22, 28), (int(exx + 0.05 * s), int(eye_y)), max(1, int(0.16 * s)))
            pygame.draw.line(surf, hair_d, (hx - 1.6 * s, hy - 1.05 * s), (hx - 0.35 * s, hy - 1.15 * s), max(1, int(s * 0.28)))
            pygame.draw.line(surf, hair_d, (hx + 0.35 * s, hy - 1.15 * s), (hx + 1.6 * s, hy - 1.05 * s), max(1, int(s * 0.28)))
            # Soft nose bridge
            pygame.draw.line(surf, rs.shade(skin_m, -16), (hx, hy + 0.15 * s), (hx, hy + 0.85 * s), max(1, int(s * 0.28)))
            pygame.draw.line(surf, (140, 80, 75), (hx - 0.65 * s, hy + 1.55 * s), (hx + 0.65 * s, hy + 1.55 * s), max(1, int(s * 0.3)))

    # Front-view arms last (in front of armour)
    if view == "front":
        _draw_arms()
        if shield and not on_back:
            _draw_shield(surf, hand_l[0] - 1.1 * s, hand_l[1], s * 0.88, shield_id or "wooden_shield")
        if wkind and not on_back and wkind != "rod":
            _draw_weapon(surf, hand_r[0], hand_r[1], s, wkind, 1, weapon_id, pose.get("weapon", 0.0))


def draw_skeletal_humanoid(
    surf, cx, cy, tile,
    body_color=(70, 120, 210),
    skin_color=(235, 195, 150),
    hair_color=(70, 45, 30),
    weapon=None, shield=False, moving=False, t=0.0,
    robe=False, facing=1, equipment=None, attacking=0.0, action=None,
    gender="male",
):
    """Anatomical adventurer with volumetric limbs and directional lighting."""
    equipment = equipment or {}
    view, facing = _parse_facing(facing)
    feminine = str(gender).lower() == "female"

    # Side-view left: draw the canonical right-facing figure, then flip.
    # Keeps weapon on the character's right hand and shield on the left for
    # both directions — no arm/gear swap when turning to face left.
    if view == "side" and facing < 0:
        pad = max(72, int(tile * 2.7))
        tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        draw_skeletal_humanoid(
            tmp, pad, pad, tile,
            body_color=body_color,
            skin_color=skin_color,
            hair_color=hair_color,
            weapon=weapon,
            shield=shield,
            moving=moving,
            t=t,
            robe=robe,
            facing=1,
            equipment=equipment,
            attacking=attacking,
            action=action,
            gender=gender,
        )
        surf.blit(
            pygame.transform.flip(tmp, True, False),
            (int(cx - pad), int(cy - pad)),
        )
        return

    s = rs.unit(tile, "character")
    # Slightly more compact frame for feminine silhouettes
    if feminine:
        s *= 0.96
    pose = rs.resolve_pose(moving, t, attacking, facing, action=action, weapon_kind=None)
    cape_sway = pose.get("cape", 0.0)

    body_id = equipment.get("body")
    legs_id = equipment.get("legs")
    shield_id = equipment.get("shield")
    weapon_id = equipment.get("weapon")
    helmet_id = equipment.get("helmet")
    wkind = _weapon_kind(weapon, weapon_id)
    # Re-resolve with weapon kind so bows use the archery draw pose
    if float(attacking or 0.0) > 0.02 and wkind == "bow":
        pose = rs.resolve_pose(moving, t, attacking, facing, action=action, weapon_kind="bow")
        cape_sway = pose.get("cape", 0.0)
    # Gathering props when the skill tool isn't the equipped weapon
    if action == "fishing":
        wkind = "rod"
        weapon_id = weapon_id or "fishing_rod"
    elif action == "woodcutting" and wkind not in ("axe", "battleaxe"):
        wkind = "axe"
        weapon_id = weapon_id or "bronze_axe"
    elif action == "mining" and wkind != "pickaxe":
        wkind = "pickaxe"
        weapon_id = weapon_id or "bronze_pickaxe"
    if shield_id and action not in ("fishing", "woodcutting", "mining"):
        shield = True
    elif action in ("fishing", "woodcutting", "mining"):
        shield = False

    shirt_base = body_color
    if body_id and (
        "leather" in body_id or "chain" in body_id or "plate" in body_id
        or body_id.endswith("_body") or body_id == "goblin_mail"
    ):
        shirt_m, shirt_d, shirt_l, _ = rs.metal_palette(body_id)
        shirt_base = shirt_m
    else:
        shirt_l, shirt_m, shirt_d = rs.shade(body_color, 32), body_color, rs.shade(body_color, -48)

    pants_base = (72, 74, 82)
    if legs_id:
        pants_m, pants_d, pants_l, _ = rs.metal_palette(legs_id)
        pants_base = pants_m
    else:
        pants_l, pants_m, pants_d = (96, 98, 106), pants_base, (48, 50, 56)
    # Feminine cloth/leather defaults — warmer soft tones when unarmoured
    if feminine and not legs_id:
        pants_base = (118, 72, 98) if not body_id else (96, 70, 88)
        pants_l, pants_m, pants_d = rs.shade(pants_base, 28), pants_base, rs.shade(pants_base, -40)
    if feminine and not body_id and not robe:
        shirt_base = (168, 92, 118)
        shirt_l, shirt_m, shirt_d = rs.shade(shirt_base, 30), shirt_base, rs.shade(shirt_base, -42)

    skin_l, skin_m, skin_d = rs.shade(skin_color, 26), skin_color, rs.shade(skin_color, -40)
    hair_m, hair_d = hair_color, rs.shade(hair_color, -36)
    if feminine and hair_color == (70, 45, 30):
        hair_m, hair_d = (92, 48, 36), (58, 28, 22)
    boots_base = (92, 62, 38) if not feminine else (110, 58, 72)
    if legs_id:
        boots_base = pants_m
    outline = rs.OUTLINE

    # Front / back walk — attacks & gather stay in side profile
    if view in ("front", "back"):
        if float(attacking or 0) > 0.02 or action in ("fishing", "woodcutting", "mining", "stand"):
            view = "side"
        else:
            _draw_ortho_humanoid(
                surf, cx, cy, s, view, moving, t, pose,
                shirt_base, shirt_l, shirt_m, shirt_d,
                pants_base, pants_l, pants_m, pants_d,
                skin_l, skin_m, skin_d, hair_m, hair_d, boots_base, outline,
                body_id, legs_id, helmet_id, shield_id, weapon_id, wkind,
                shield, robe, body_color, feminine, attacking, action, equipment,
            )
            return

    bob = pose["root_bob"] * s
    sway = pose.get("hip_sway", 0.0) * s * facing
    # Wider hips / narrower shoulders for feminine silhouette
    hip_w = 3.15 if feminine else 2.5
    sh_w = 4.6 if feminine else 5.2
    waist = 3.0 if feminine else 3.6
    pelvis = (cx + sway, cy + 3.2 * s + bob)
    torso_len = (12.8 if feminine else 13.5) * s
    arm_len, leg_len = 11.2 * s, (13.2 if feminine else 13.6) * s
    neck = rs.joint(
        pelvis[0], pelvis[1] - 1.5 * s,
        -math.pi / 2 + (pose["torso"] - rs.DOWN) * 0.28,
        torso_len,
    )

    hip_l = (pelvis[0] - hip_w * s, pelvis[1] + 0.2 * s)
    hip_r = (pelvis[0] + hip_w * s, pelvis[1] + 0.2 * s)
    if facing < 0:
        hip_l, hip_r = hip_r, hip_l

    knee_bend_l = pose.get("knee_l", 0.08)
    knee_bend_r = pose.get("knee_r", 0.08)
    lift_l = pose.get("foot_lift_l", 0.0) * s
    lift_r = pose.get("foot_lift_r", 0.0) * s
    # Thigh aims with hip angle; shin adds knee flexion toward the rear of facing
    knee_l = rs.joint(*hip_l, pose["leg_l"], leg_len * 0.48)
    knee_r = rs.joint(*hip_r, pose["leg_r"], leg_len * 0.48)
    foot_l = rs.joint(*knee_l, pose["leg_l"] + knee_bend_l * facing, leg_len * 0.52)
    foot_r = rs.joint(*knee_r, pose["leg_r"] + knee_bend_r * facing, leg_len * 0.52)
    foot_l = (foot_l[0], foot_l[1] - lift_l)
    foot_r = (foot_r[0], foot_r[1] - lift_r)
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

    # Sheathe gear behind the body when not in combat (idle + walk). Tip peeks
    # past the far shoulder; torso covers the rest so it never sits across the chest.
    on_back = (
        float(attacking or 0) <= 0.01
        and action in (None, "stand")
        and (bool(wkind) and wkind != "rod" or bool(shield))
    )
    weapon_on_back = on_back and bool(wkind) and wkind != "rod"
    shield_on_back = on_back and bool(shield)
    if shield_on_back:
        _draw_shield(
            surf,
            neck[0] - 2.2 * s * facing,
            neck[1] + 5.5 * s,
            s * 1.08,
            shield_id or "wooden_shield",
            on_back=True,
            facing=facing,
        )
    # Sheathed tip behind the body (torso/pauldrons drawn later occlude overlap)
    if weapon_on_back:
        bx = neck[0] - 5.8 * s * facing
        by = neck[1] - 2.4 * s
        _draw_weapon(surf, bx, by, s * 0.78, wkind, facing, weapon_id, 0.0, sheathed=True)

    # --- Legs (far then near) ---
    far_leg = (foot_l, knee_l, hip_l) if facing > 0 else (foot_r, knee_r, hip_r)
    near_leg = (foot_r, knee_r, hip_r) if facing > 0 else (foot_l, knee_l, hip_l)
    thigh_w = 2.35 * s if feminine else 2.15 * s
    calf_w = 1.55 * s if feminine else 1.75 * s
    for foot, knee, hip in (far_leg, near_leg):
        # Thigh (wider) + calf (narrower) — separate garment legs
        leg_metal = bool(legs_id and ("plate" in legs_id or "chain" in legs_id or "eclipse" in legs_id))
        leg_detail = "metal_armor" if leg_metal else "cloth"
        rs.draw_volume_limb(surf, *hip, *knee, thigh_w, pants_base, outline, taper=0.82, bulge=0.18 if feminine else 0.14, detail=leg_detail)
        rs.draw_volume_limb(surf, *knee, *foot, calf_w, pants_base, outline, taper=0.72, bulge=0.08, detail=leg_detail)
        # Knee joint / armour plate
        if legs_id and "eclipse" in legs_id:
            _draw_eclipse_leg_ornament(surf, hip, knee, foot, s, pants_m, pants_d, pants_l)
        elif legs_id and ("plate" in legs_id or "chain" in legs_id):
            pygame.draw.circle(surf, pants_m, (int(knee[0]), int(knee[1])), max(2, int(1.6 * s)))
            pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.4 * s), int(knee[1] - 0.4 * s)), max(1, int(0.85 * s)))
            pygame.draw.circle(surf, pants_d, (int(knee[0]), int(knee[1])), max(2, int(1.6 * s)), 1)
        else:
            pygame.draw.circle(surf, pants_l, (int(knee[0] - 0.3 * s), int(knee[1] - 0.3 * s)), max(1, int(1.0 * s)))
        _draw_boot(surf, *foot, s, facing, boots_base, outline)

    # Feminine skirt / plate flared cuisse over legs
    if feminine and (not legs_id or "chaps" in (legs_id or "") or "leather" in (legs_id or "")):
        skirt = [
            (pelvis[0] - 4.8 * s, pelvis[1] + 0.4 * s),
            (pelvis[0] + 4.8 * s, pelvis[1] + 0.4 * s),
            (pelvis[0] + 6.4 * s, pelvis[1] + 7.2 * s),
            (pelvis[0] - 6.4 * s, pelvis[1] + 7.2 * s),
        ]
        rs.draw_volume(surf, pants_base, skirt, outline, 1, detail="cloth")
    elif feminine and legs_id and ("plate" in legs_id or "chain" in legs_id):
        flare = [
            (pelvis[0] - 4.6 * s, pelvis[1] + 0.2 * s),
            (pelvis[0] + 4.6 * s, pelvis[1] + 0.2 * s),
            (pelvis[0] + 5.8 * s, pelvis[1] + 5.5 * s),
            (pelvis[0] - 5.8 * s, pelvis[1] + 5.5 * s),
        ]
        rs.draw_volume(surf, pants_base, flare, outline, 1, detail="metal_armor")

    # Hip / belt
    bw = 5.0 if feminine else 4.4
    belt = [
        (pelvis[0] - bw * s, pelvis[1] - 0.8 * s),
        (pelvis[0] + bw * s, pelvis[1] - 0.8 * s),
        (pelvis[0] + (bw - 0.6) * s, pelvis[1] + 2.8 * s),
        (pelvis[0] - (bw - 0.6) * s, pelvis[1] + 2.8 * s),
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

    # Chest — feminine: narrower shoulders, cinched waist, soft chest curve
    if feminine:
        chest = [
            (pelvis[0] - waist * s, pelvis[1] - 0.2 * s),
            (pelvis[0] + waist * s, pelvis[1] - 0.2 * s),
            (neck[0] + sh_w * s, neck[1] + 2.4 * s),
            (neck[0] + 1.6 * s, neck[1] + 1.0 * s),
            (neck[0] - 1.6 * s, neck[1] + 1.0 * s),
            (neck[0] - sh_w * s, neck[1] + 2.4 * s),
        ]
    else:
        chest = [
            (pelvis[0] - 3.6 * s, pelvis[1] - 0.2 * s),
            (pelvis[0] + 3.4 * s, pelvis[1] - 0.2 * s),
            (neck[0] + 5.6 * s, neck[1] + 2.2 * s),
            (neck[0] + 2.0 * s, neck[1] + 1.0 * s),
            (neck[0] - 2.0 * s, neck[1] + 1.0 * s),
            (neck[0] - 5.6 * s, neck[1] + 2.2 * s),
        ]
    is_plate = bool(body_id and ("plate" in body_id or (body_id.endswith("_body") and "chain" not in body_id and "leather" not in body_id)))
    is_chain = bool(body_id and "chain" in body_id)
    is_leather = bool(body_id and "leather" in body_id)
    if is_plate or is_chain:
        shirt_detail = "metal_armor"
    elif is_leather:
        shirt_detail = "leather"
    elif robe:
        shirt_detail = "fabric"
    else:
        shirt_detail = "cloth"
    rs.draw_volume(surf, shirt_base, chest, outline, max(1, int(s * 0.35)), detail=shirt_detail)
    # Tidehollow medal — worn at the sternum when equipped as amulet
    amulet_id = equipment.get("amulet")
    if amulet_id == "tidehollow_medal":
        mx = neck[0] + 0.4 * s * facing
        my = neck[1] + 5.2 * s
        pygame.draw.circle(surf, (210, 170, 55), (int(mx), int(my)), max(2, int(1.7 * s)))
        pygame.draw.circle(surf, (255, 220, 110), (int(mx), int(my)), max(1, int(1.15 * s)))
        pygame.draw.circle(surf, (40, 90, 120), (int(mx), int(my + 0.15 * s)), max(1, int(0.7 * s)))
        pygame.draw.line(surf, (180, 150, 60), (neck[0], neck[1] + 2.2 * s), (mx, my - 1.2 * s), max(1, int(0.7 * s)))
        pygame.draw.circle(surf, outline, (int(mx), int(my)), max(2, int(1.7 * s)), 1)
    # Upper-left chest highlight plane
    rs.draw_poly(surf, shirt_l, [
        (pelvis[0] - 2.6 * s, pelvis[1] - 0.8 * s),
        (pelvis[0] - 0.1 * s, pelvis[1] - 0.8 * s),
        (neck[0] - 0.4 * s, neck[1] + 3.8 * s),
        (neck[0] - 4.0 * s, neck[1] + 3.5 * s),
    ], None, 0)
    # Deltoids
    pygame.draw.circle(surf, shirt_m, (int(neck[0] - sh_w * s), int(neck[1] + 3.2 * s)), max(2, int(2.2 * s if feminine else 2.4 * s)))
    pygame.draw.circle(surf, shirt_l, (int(neck[0] - (sh_w + 0.5) * s), int(neck[1] + 2.5 * s)), max(1, int(1.3 * s)))
    pygame.draw.circle(surf, shirt_d, (int(neck[0] + sh_w * s), int(neck[1] + 3.2 * s)), max(2, int(2.2 * s if feminine else 2.4 * s)))
    # Collar
    rs.draw_poly(surf, shirt_l, [
        (neck[0] - 2.3 * s, neck[1] + 2.0 * s),
        (neck[0] + 2.1 * s, neck[1] + 2.0 * s),
        (neck[0] + 1.3 * s, neck[1] + 4.6 * s),
        (neck[0] - 1.5 * s, neck[1] + 4.6 * s),
    ], None, 0)
    if is_plate:
        # Layered plate ridges + central ridge
        for i in range(4):
            yy = neck[1] + (4.6 + i * 2.4) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3.3 * s, yy), (pelvis[0] + 3.3 * s, yy), max(1, int(s * 0.45)))
            pygame.draw.line(surf, shirt_l, (pelvis[0] - 3.1 * s, yy - 0.7 * s), (pelvis[0] + 1.6 * s, yy - 0.7 * s), 1)
        pygame.draw.line(surf, shirt_d, (pelvis[0], neck[1] + 4.2 * s), (pelvis[0], pelvis[1] - 0.5 * s), max(1, int(s * 0.4)))
        # Pauldron discs
        for side in (-1, 1):
            px = neck[0] + side * 5.4 * s
            py = neck[1] + 2.6 * s
            pygame.draw.circle(surf, shirt_m, (int(px), int(py)), max(2, int(2.6 * s)))
            pygame.draw.circle(surf, shirt_l if side < 0 else shirt_d, (int(px - 0.5 * s), int(py - 0.5 * s)), max(1, int(1.2 * s)))
            pygame.draw.circle(surf, shirt_d, (int(px), int(py)), max(2, int(2.6 * s)), 1)
        if body_id and "mythos" in body_id:
            _draw_mythos_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, facing)
        elif body_id and "eclipse" in body_id:
            _draw_eclipse_plate_ornament(surf, neck, pelvis, s, shirt_l, shirt_d, shirt_m, facing)
    elif is_chain:
        for i in range(5):
            yy = neck[1] + (4.0 + i * 2.0) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 3.1 * s, yy), (pelvis[0] + 3.1 * s, yy), 1)
            for j in range(5):
                xx = pelvis[0] + (j - 2) * 1.4 * s
                pygame.draw.circle(surf, shirt_d, (int(xx), int(yy + 0.6 * s)), max(1, int(0.35 * s)), 1)
    elif is_leather:
        for i in range(3):
            yy = neck[1] + (5.0 + i * 2.8) * s
            pygame.draw.line(surf, shirt_d, (pelvis[0] - 2.8 * s, yy), (pelvis[0] + 2.8 * s, yy), 1)
        # Strap
        pygame.draw.line(surf, shirt_d, (neck[0] - 2 * s, neck[1] + 3 * s), (pelvis[0] + 2.5 * s, pelvis[1]), max(2, int(s * 0.5)))

    # Small shoulder-pad strap only (never a diagonal across the breastplate —
    # that read as the axe handle sitting on the front of the body).
    if shield_on_back or weapon_on_back:
        strap = (92, 68, 42)
        strap_d = (60, 42, 26)
        # Short clip at the far shoulder only
        sx0 = neck[0] - 4.2 * s * facing
        sy0 = neck[1] + 2.2 * s
        sx1 = neck[0] - 1.0 * s * facing
        sy1 = neck[1] + 4.5 * s
        pygame.draw.line(surf, strap_d, (sx0, sy0), (sx1, sy1), max(2, int(s * 0.75)))
        pygame.draw.line(surf, strap, (sx0, sy0 - 0.3 * s), (sx1, sy1 - 0.3 * s), max(1, int(s * 0.45)))

    # Arms — always drawn facing right; left facing is a full-sprite flip above.
    # far = character's left (shield), near = character's right (weapon)
    sh_far = (neck[0] - sh_w * s, neck[1] + 3.0 * s)
    sh_near = (neck[0] + sh_w * s, neck[1] + 3.0 * s)
    pose_arm_far, pose_arm_near = pose["arm_l"], pose["arm_r"]

    el_far = rs.joint(*sh_far, pose_arm_far, arm_len * 0.5)
    # Elbow flare only in combat — idle/walk hang straight by the body
    elbow_out = 0.22 if float(attacking or 0) > 0.02 else 0.0
    hand_far = rs.joint(*el_far, pose_arm_far + elbow_out * facing, arm_len * 0.5)
    el_near = rs.joint(*sh_near, pose_arm_near, arm_len * 0.5)
    hand_near = rs.joint(
        *el_near,
        pose_arm_near - (elbow_out * 0.75) * facing + pose["weapon"] * 0.15,
        arm_len * 0.55,
    )
    # Small opposite front/back hand slide (does not open/close the arms from the torso)
    hs = float(pose.get("hand_shift") or 0.0)
    if moving and abs(hs) > 0.001 and float(attacking or 0) <= 0.02:
        # ~0.9s pixels along facing — one hand slightly forward, the other slightly back
        slide = 0.9 * s * hs
        # far=left, near=right; hs>0 ⇒ left back (−x), right forward (+x)
        hand_far = (hand_far[0] - slide, hand_far[1])
        hand_near = (hand_near[0] + slide, hand_near[1])
        el_far = (el_far[0] - slide * 0.45, el_far[1])
        el_near = (el_near[0] + slide * 0.45, el_near[1])

    # Far arm (sleeve → forearm skin)
    rs.draw_volume_limb(surf, *sh_far, *el_far, 1.75 * s, shirt_base, outline, taper=0.8, bulge=0.1, detail=shirt_detail)
    rs.draw_volume_limb(surf, *el_far, *hand_far, 1.45 * s, skin_m, outline, taper=0.75, bulge=0.06, detail="skin")
    _draw_hand(surf, *hand_far, s * 0.95, skin_m, skin_l, outline)

    if shield and not shield_on_back:
        # Hold shield off to the side (not covering the breastplate)
        _draw_shield(
            surf,
            hand_far[0] - 1.6 * s * facing,
            hand_far[1] + 0.8 * s,
            s * 0.9,
            shield_id or "wooden_shield",
        )

    # Neck
    hx, hy = neck[0] + 0.2 * s * facing, neck[1] - 0.5 * s
    if feminine:
        # Narrower short neck — wide tall neck + face reads as one masculine slab
        rs.draw_poly(surf, skin_m, [
            (hx - 1.05 * s, hy + 0.7 * s), (hx + 1.05 * s, hy + 0.7 * s),
            (hx + 0.95 * s, hy + 3.2 * s), (hx - 0.95 * s, hy + 3.2 * s),
        ], None, 0)
    else:
        rs.draw_volume(surf, skin_m, [
            (hx - 1.4 * s, hy + 0.5 * s), (hx + 1.4 * s, hy + 0.5 * s),
            (hx + 1.2 * s, hy + 3.6 * s), (hx - 1.2 * s, hy + 3.6 * s),
        ], outline, 1, detail="skin")

    if helmet_id:
        _draw_helmet(surf, hx, hy, s * 0.72, helmet_id)
    elif feminine:
        # 3/4-leaning side face matching front proportions.
        # Critical: bangs must be drawn AFTER the face so they aren't wiped.
        soft_hair = rs.shade(hair_m, -18)
        rs.draw_volume(surf, hair_m, [
            (hx - 1.2 * s, hy - 2.8 * s),
            (hx - 3.1 * s, hy - 1.2 * s),
            (hx - 3.7 * s, hy + 3.4 * s),
            (hx - 3.3 * s, hy + 9.2 * s),
            (hx - 2.3 * s, hy + 9.4 * s),
            (hx - 1.8 * s, hy + 3.0 * s),
            (hx - 0.6 * s, hy + 0.0 * s),
        ], soft_hair, 1)
        rs.draw_volume(surf, hair_m, [
            (hx + 0.5 * s, hy - 1.8 * s),
            (hx + 1.45 * s, hy - 0.2 * s),
            (hx + 1.5 * s, hy + 6.4 * s),
            (hx + 0.9 * s, hy + 6.2 * s),
            (hx + 0.65 * s, hy + 0.3 * s),
        ], soft_hair, 1)
        # Compact face first (low hairline — bangs will cover the top)
        face = [
            (hx - 1.3 * s, hy + 0.1 * s),
            (hx - 1.45 * s, hy - 1.2 * s),
            (hx - 0.5 * s, hy - 1.85 * s),
            (hx + 0.8 * s, hy - 1.9 * s),
            (hx + 1.6 * s, hy - 1.15 * s),
            (hx + 1.85 * s, hy + 0.05 * s),
            (hx + 1.75 * s, hy + 0.9 * s),
            (hx + 1.35 * s, hy + 1.5 * s),
            (hx + 0.2 * s, hy + 1.55 * s),
            (hx - 0.7 * s, hy + 1.1 * s),
            (hx - 1.2 * s, hy + 0.45 * s),
        ]
        pygame.draw.polygon(surf, skin_m, [(int(p[0]), int(p[1])) for p in face])
        rs.draw_poly(surf, skin_l, [
            (hx - 0.3 * s, hy - 1.3 * s),
            (hx + 1.05 * s, hy - 1.35 * s),
            (hx + 1.35 * s, hy + 0.5 * s),
            (hx + 0.1 * s, hy + 1.0 * s),
            (hx - 0.5 * s, hy + 0.25 * s),
        ], None, 0)
        pygame.draw.circle(surf, rs.shade(skin_m, -8), (int(hx + 1.7 * s), int(hy + 0.12 * s)), max(1, int(0.24 * s)))
        pygame.draw.ellipse(
            surf, rs.shade(skin_m, -12),
            (int(hx - 1.7 * s), int(hy - 0.3 * s), max(2, int(0.7 * s)), max(2, int(0.95 * s))),
        )
        # Bangs / crown ON TOP of face (must come after face fill)
        rs.draw_volume(surf, hair_m, [
            (hx - 2.3 * s, hy - 0.2 * s),
            (hx - 1.9 * s, hy - 3.1 * s),
            (hx - 0.4 * s, hy - 4.2 * s),
            (hx + 0.9 * s, hy - 4.1 * s),
            (hx + 1.65 * s, hy - 2.4 * s),
            (hx + 1.45 * s, hy - 0.45 * s),
            (hx + 0.4 * s, hy - 0.85 * s),
            (hx - 0.8 * s, hy - 0.75 * s),
        ], soft_hair, 1)
        # Far-eye hint + near eye (near eye sits forward toward the nose)
        pygame.draw.circle(surf, (240, 235, 225), (int(hx - 0.15 * s), int(hy + 0.05 * s)), max(1, int(0.24 * s)))
        pygame.draw.circle(surf, (45, 70, 100), (int(hx - 0.08 * s), int(hy + 0.05 * s)), max(1, int(0.12 * s)))
        eye_x = hx + 1.05 * s
        eye_y = hy + 0.05 * s
        pygame.draw.ellipse(surf, (250, 248, 240), (eye_x - 0.48 * s, eye_y - 0.38 * s, 1.0 * s, 0.8 * s))
        pygame.draw.circle(surf, (55, 90, 130), (int(eye_x + 0.1 * s), int(eye_y)), max(1, int(0.30 * s)))
        pygame.draw.circle(surf, (20, 22, 28), (int(eye_x + 0.14 * s), int(eye_y)), max(1, int(0.14 * s)))
        pygame.draw.circle(surf, (255, 255, 255), (int(eye_x - 0.1 * s), int(eye_y - 0.16 * s)), max(1, int(0.11 * s)))
        pygame.draw.line(
            surf, rs.shade(hair_m, -6),
            (hx + 0.55 * s, hy - 0.55 * s),
            (hx + 1.45 * s, hy - 0.65 * s),
            max(1, int(s * 0.2)),
        )
        pygame.draw.line(
            surf, (168, 105, 112),
            (hx + 1.05 * s, hy + 1.0 * s),
            (hx + 1.55 * s, hy + 1.08 * s),
            max(1, int(s * 0.26)),
        )
    else:
        # Male side head
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
        if facing < 0:
            skull = [(hx - (px - hx), py) for px, py in skull]
        rs.draw_volume(surf, skin_m, skull, outline, 1, detail="skin")
        rs.draw_poly(surf, skin_l, [
            (hx - 1.2 * s * facing, hy - 1.8 * s),
            (hx + 2.1 * s * facing, hy - 1.6 * s),
            (hx + 2.3 * s * facing, hy + 1.6 * s),
            (hx - 0.3 * s * facing, hy + 2.0 * s),
        ], None, 0)
        pygame.draw.line(
            surf, skin_d,
            (hx + 0.7 * s * facing, hy - 0.9 * s),
            (hx + 1.5 * s * facing, hy + 0.7 * s),
            max(1, int(s * 0.5)),
        )
        rs.draw_volume(surf, hair_m, [
            (hx - 3.2 * s, hy - 0.8 * s),
            (hx - 2.6 * s, hy - 3.8 * s),
            (hx + 0.2 * s, hy - 4.6 * s),
            (hx + 2.6 * s, hy - 3.8 * s),
            (hx + 3.2 * s, hy - 0.6 * s),
            (hx + 2.0 * s, hy - 1.4 * s),
            (hx - 2.2 * s, hy - 1.4 * s),
        ], hair_d, 1)
        rs.draw_poly(surf, hair_d, [
            (hx + 2.4 * s * facing, hy - 0.8 * s),
            (hx + 3.5 * s * facing, hy + 0.6 * s),
            (hx + 2.0 * s * facing, hy + 0.9 * s),
        ], None, 0)
        rs.draw_poly(surf, skin_d, [
            (hx - 2.7 * s * facing, hy - 0.5 * s),
            (hx - 3.7 * s * facing, hy - 1.0 * s),
            (hx - 3.5 * s * facing, hy + 0.6 * s),
            (hx - 2.7 * s * facing, hy + 1.1 * s),
        ], outline, 1)
        eye_y = hy - 0.05 * s
        for ex in (-1.15, 1.25):
            exx = hx + ex * s * facing
            pygame.draw.ellipse(surf, (250, 248, 240), (exx - 0.55 * s, eye_y - 0.42 * s, 1.1 * s, 0.85 * s))
            pygame.draw.ellipse(surf, outline, (exx - 0.55 * s, eye_y - 0.42 * s, 1.1 * s, 0.85 * s), max(1, int(s * 0.25)))
            pygame.draw.circle(surf, (55, 90, 130), (int(exx + 0.12 * s * facing), int(eye_y)), max(1, int(0.35 * s)))
            pygame.draw.circle(surf, (20, 22, 28), (int(exx + 0.15 * s * facing), int(eye_y)), max(1, int(0.18 * s)))
            pygame.draw.circle(surf, (255, 255, 255), (int(exx - 0.15 * s), int(eye_y - 0.2 * s)), max(1, int(0.12 * s)))
        pygame.draw.line(
            surf, hair_d,
            (hx - 1.5 * s * facing, hy - 1.05 * s),
            (hx - 0.3 * s * facing, hy - 1.15 * s),
            max(1, int(s * 0.35)),
        )
        pygame.draw.line(
            surf, hair_d,
            (hx + 0.4 * s * facing, hy - 1.15 * s),
            (hx + 1.6 * s * facing, hy - 1.0 * s),
            max(1, int(s * 0.35)),
        )
        pygame.draw.line(
            surf, (140, 80, 75),
            (hx - 0.7 * s * facing, hy + 1.7 * s),
            (hx + 0.9 * s * facing, hy + 1.75 * s),
            max(1, int(s * 0.35)),
        )

    # Near arm + weapon (drawn last so it overlays torso) — skip if sheathed on back
    rs.draw_volume_limb(surf, *sh_near, *el_near, 1.75 * s, shirt_base, outline, taper=0.8, bulge=0.1, detail=shirt_detail)
    rs.draw_volume_limb(surf, *el_near, *hand_near, 1.45 * s, skin_m, outline, taper=0.75, bulge=0.06, detail="skin")
    _draw_hand(surf, *hand_near, s, skin_m, skin_l, outline)
    if wkind and not weapon_on_back:
        _draw_weapon(surf, hand_near[0], hand_near[1], s, wkind, facing, weapon_id, pose["weapon"])
