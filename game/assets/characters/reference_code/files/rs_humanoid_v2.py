"""
rs_humanoid_v2.py — USE_NEW_CHARACTERS drawer (OSRS-leaning proportions/faces).

RULE: animation is NOT re-authored here. rig_side()/rig_ortho() are verbatim
copies of the joint maths in rs_humanoid.draw_skeletal_humanoid /
_draw_ortho_humanoid (same rs.resolve_pose, same bob, same phase, same
lift/stride/hand_shift). tools/walk_proof.py asserts the joints are identical
to what the old drawer feeds rs.draw_volume_limb, frame by frame.
Only the SHAPES drawn on those joints, the face, hair and colours change.
"""
import math
import pygame
import rs_style as rs
import rs_humanoid as old
import gear_v2 as gear
import armour_v2 as armour

OUT = (30, 24, 22)


def _mute(c, k=0.30, dark=0.92):
    g = (c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11)
    return tuple(int(max(0, min(255, (v + (g - v) * k) * dark))) for v in c)


def _sh(c, d):
    return rs.shade(c, d)


def _fp(surf, col, pts, outline=OUT, w=1):
    gear.fpoly(surf, col, pts, outline, w)


def _limb(surf, a, b, wa, wb, col, outline=OUT, lit=True):
    """Tapered flat-shaded limb: base fill + darker half on the shadow side."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    pts = [(a[0] + nx * wa, a[1] + ny * wa), (b[0] + nx * wb, b[1] + ny * wb),
           (b[0] - nx * wb, b[1] - ny * wb), (a[0] - nx * wa, a[1] - ny * wa)]
    _fp(surf, col, pts, None)
    # shadow side = the side facing away from the upper-left light
    side = 1 if (nx * rs.LIGHT_DIR[0] + ny * rs.LIGHT_DIR[1]) < 0 else -1
    half = [(a[0], a[1]), (b[0], b[1]), (b[0] + side * nx * wb, b[1] + side * ny * wb), (a[0] + side * nx * wa, a[1] + side * ny * wa)]
    _fp(surf, _sh(col, -26), half, None)
    if outline:
        pygame.draw.polygon(surf, outline, [(int(round(x)), int(round(y))) for x, y in pts], 1)
    return pts


def _circ(surf, col, c, r, outline=OUT):
    pygame.draw.circle(surf, col, (int(round(c[0])), int(round(c[1]))), max(1, int(round(r))))
    if outline:
        pygame.draw.circle(surf, outline, (int(round(c[0])), int(round(c[1]))), max(1, int(round(r))), 1)


# ---------------------------------------------------------------------------
# RIGS — verbatim joint maths (do not edit without re-running walk_proof)
def resolve(moving, t, attacking, facing, action, weapon, equipment):
    """Pose + weapon kind resolution exactly as draw_skeletal_humanoid."""
    pose = rs.resolve_pose(moving, t, attacking, facing, action=action, weapon_kind=None)
    weapon_id = equipment.get("weapon")
    wkind = old._weapon_kind(weapon, weapon_id)
    if float(attacking or 0.0) > 0.02 and wkind == "bow":
        pose = rs.resolve_pose(moving, t, attacking, facing, action=action, weapon_kind="bow")
    return pose, wkind


def rig_side(cx, cy, s, pose, feminine, facing, moving, attacking):
    bob = pose["root_bob"] * s
    sway = pose.get("hip_sway", 0.0) * s * facing
    hip_w = 3.15 if feminine else 2.5
    sh_w = 4.6 if feminine else 5.2
    pelvis = (cx + sway, cy + 3.2 * s + bob)
    torso_len = (12.8 if feminine else 13.5) * s
    arm_len, leg_len = 11.2 * s, (13.2 if feminine else 13.6) * s
    neck = rs.joint(pelvis[0], pelvis[1] - 1.5 * s, -math.pi / 2 + (pose["torso"] - rs.DOWN) * 0.28, torso_len)
    hip_l = (pelvis[0] - hip_w * s, pelvis[1] + 0.2 * s)
    hip_r = (pelvis[0] + hip_w * s, pelvis[1] + 0.2 * s)
    if facing < 0:
        hip_l, hip_r = hip_r, hip_l
    knee_bend_l = pose.get("knee_l", 0.08)
    knee_bend_r = pose.get("knee_r", 0.08)
    lift_l = pose.get("foot_lift_l", 0.0) * s
    lift_r = pose.get("foot_lift_r", 0.0) * s
    knee_l = rs.joint(*hip_l, pose["leg_l"], leg_len * 0.48)
    knee_r = rs.joint(*hip_r, pose["leg_r"], leg_len * 0.48)
    foot_l = rs.joint(*knee_l, pose["leg_l"] + knee_bend_l * facing, leg_len * 0.52)
    foot_r = rs.joint(*knee_r, pose["leg_r"] + knee_bend_r * facing, leg_len * 0.52)
    foot_l = (foot_l[0], foot_l[1] - lift_l)
    foot_r = (foot_r[0], foot_r[1] - lift_r)
    foot_y = max(foot_l[1], foot_r[1]) + 2.4 * s
    sh_far = (neck[0] - sh_w * s, neck[1] + 3.0 * s)
    sh_near = (neck[0] + sh_w * s, neck[1] + 3.0 * s)
    pa_far, pa_near = pose["arm_l"], pose["arm_r"]
    el_far = rs.joint(*sh_far, pa_far, arm_len * 0.5)
    elbow_out = 0.22 if float(attacking or 0) > 0.02 else 0.0
    hand_far = rs.joint(*el_far, pa_far + elbow_out * facing, arm_len * 0.5)
    el_near = rs.joint(*sh_near, pa_near, arm_len * 0.5)
    hand_near = rs.joint(*el_near, pa_near - (elbow_out * 0.75) * facing + pose["weapon"] * 0.15, arm_len * 0.55)
    hs = float(pose.get("hand_shift") or 0.0)
    if moving and abs(hs) > 0.001 and float(attacking or 0) <= 0.02:
        slide = 0.9 * s * hs
        hand_far = (hand_far[0] - slide, hand_far[1])
        hand_near = (hand_near[0] + slide, hand_near[1])
        el_far = (el_far[0] - slide * 0.45, el_far[1])
        el_near = (el_near[0] + slide * 0.45, el_near[1])
    far_leg = (foot_l, knee_l, hip_l) if facing > 0 else (foot_r, knee_r, hip_r)
    near_leg = (foot_r, knee_r, hip_r) if facing > 0 else (foot_l, knee_l, hip_l)
    return dict(view="side", pelvis=pelvis, neck=neck, far_leg=far_leg, near_leg=near_leg, foot_y=foot_y,
                sh_far=sh_far, sh_near=sh_near, el_far=el_far, el_near=el_near,
                hand_far=hand_far, hand_near=hand_near, hip_w=hip_w, sh_w=sh_w, bob=bob)


def rig_ortho(cx, cy, s, view, moving, t, pose, feminine):
    bob = pose.get("root_bob", 0.0) * s * 0.55
    ph = t * rs.TAU * 1.15 if moving else 0.0
    depth = 1.0 if view == "front" else -1.0
    stride = 0.75 * s
    arm_swing = 2.4 * s
    leg_l = math.sin(ph) * stride * depth
    leg_r = math.sin(ph + math.pi) * stride * depth
    arm_l = math.sin(ph + math.pi) * arm_swing * depth
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
    dy = (lambda p: p[1]) if view == "front" else (lambda p: -p[1])
    legs = sorted(((foot_l, knee_l, hip_l), (foot_r, knee_r, hip_r)), key=lambda tr: dy(tr[0]))
    arms = sorted(((hand_l, el_l, sh_l), (hand_r, el_r, sh_r)), key=lambda tr: dy(tr[0]))
    return dict(view=view, pelvis=pelvis, neck=neck, legs=legs, arms=arms, foot_y=foot_y,
                sh_l=sh_l, sh_r=sh_r, hand_l=hand_l, hand_r=hand_r, hip_w=hip_w, sh_w=sh_w, bob=bob)


# ---------------------------------------------------------------------------
# Colours
def palette(body_color, skin_color, hair_color, feminine, equipment, robe):
    body_id = equipment.get("body")
    legs_id = equipment.get("legs")
    shirt = _mute(body_color, 0.35, 0.86)
    if feminine and not body_id and not robe and tuple(body_color) == (70, 210, 90):
        shirt = (150, 92, 112)
    pants = (78, 74, 70) if not feminine else (96, 70, 84)
    skin = _mute(skin_color, 0.12, 0.93)
    hair = _mute(hair_color, 0.15, 1.0)
    if feminine and tuple(hair_color) == (70, 45, 30):
        hair = (96, 56, 38)
    boots = (78, 56, 38) if not feminine else (92, 58, 50)
    bl = gear.look_for(body_id)
    ll = gear.look_for(legs_id)
    return dict(shirt=shirt, pants=pants, skin=skin, hair=hair, boots=boots, body=bl, legs=ll,
                helm=gear.look_for(equipment.get("helmet")), amulet=equipment.get("amulet"))


# ---------------------------------------------------------------------------
# Body parts
def _leg(surf, s, hip, knee, foot, P, feminine, view, facing=1):
    ll = P["legs"]
    col = ll["pal"][0] if ll else P["pants"]
    tw = 1.8 if feminine else 1.75
    bk = armour.bulk(ll)
    if ll and ll["kind"] == "platelegs":
        armour.leg_plate(surf, s, hip, knee, foot, ll, view, facing, P.get("t", 0.0))
        return
    kb = 1.0 + 0.16 * bk
    _limb(surf, hip, knee, tw * s * kb, 1.28 * s * kb, col)
    _limb(surf, knee, foot, 1.28 * s * kb, 0.92 * s * kb, col)
    if ll:
        k, (b, d, l) = ll["kind"], ll["pal"]
        g = ll["gold"]
        if k == "platelegs":
            # tasset on thigh + knee cop, shin plate highlight
            mid = ((hip[0] + knee[0]) / 2, (hip[1] + knee[1]) / 2)
            fl = gear.fline
            fl(surf, l, (mid[0] - 0.5 * s, mid[1] - 2.2 * s), (knee[0] - 0.5 * s, knee[1] - 0.8 * s), 1)
            _circ(surf, gear.GOLD[0] if g else l, knee, 1.05 * s, OUT)
            fl(surf, l, (knee[0] - 0.3 * s, knee[1] + 1.2 * s), (foot[0] - 0.3 * s, foot[1] - 1.0 * s), max(1, int(s * 0.4)))
            if ll["mat"] == "mythos":
                _fp(surf, gear.GOLD[0], [(knee[0] - 0.6 * s, knee[1] - 1.0 * s), (knee[0] + 0.6 * s, knee[1] - 1.0 * s), (knee[0], knee[1] + 1.2 * s)], gear.GOLD[1])
        elif k == "chainlegs":
            for i in range(1, 6):
                u = i / 6.0
                p = (hip[0] + (foot[0] - hip[0]) * u, hip[1] + (foot[1] - hip[1]) * u)
                w = (1.3 - 0.5 * u) * s
                gear.fline(surf, l, (p[0] - w * 0.8, p[1]), (p[0] + w * 0.8, p[1]), 1)
        elif k == "chaps":
            gear.fline(surf, l, (hip[0] - 0.8 * s, hip[1] + 0.5 * s), (knee[0] - 0.6 * s, knee[1]), 1)
            gear.fline(surf, d, (knee[0], knee[1]), (foot[0], foot[1] - 1.0 * s), 1)
            _circ(surf, d, knee, 0.95 * s)          # hardened knee pad
            gear.fline(surf, armour.STYLE["leather"]["rivet"], (knee[0] - 0.3 * s, knee[1]), (knee[0] + 0.3 * s, knee[1]), 1)
        if k == "chainlegs":
            _circ(surf, _sh(b, -8), knee, 1.1 * s)   # mail knee cop
            _circ(surf, armour.st(ll)["trim"], knee, 0.4 * s, None)
    # boot
    bc = (ll["pal"][1] if ll and ll["kind"] == "platelegs" else P["boots"])
    fx, fy = foot
    if view == "side":
        f = facing
        _fp(surf, bc, [(fx - 0.9 * s * f, fy - 1.0 * s), (fx + 0.8 * s * f, fy - 1.0 * s), (fx + 1.0 * s * f, fy + 0.5 * s),
                       (fx + 2.3 * s * f, fy + 1.1 * s), (fx + 2.3 * s * f, fy + 2.0 * s), (fx - 1.1 * s * f, fy + 2.0 * s)])
        gear.fline(surf, _sh(bc, -30), (fx - 1.1 * s * f, fy + 1.8 * s), (fx + 2.3 * s * f, fy + 1.8 * s), 1)
    else:
        _fp(surf, bc, [(fx - 1.0 * s, fy - 1.0 * s), (fx + 1.0 * s, fy - 1.0 * s), (fx + 1.25 * s, fy + 1.9 * s), (fx - 1.25 * s, fy + 1.9 * s)])
        gear.fline(surf, _sh(bc, 25), (fx - 0.6 * s, fy - 0.6 * s), (fx - 0.6 * s, fy + 1.2 * s), 1)


def _arm(surf, s, sh, el, hand, P, feminine):
    bl = P["body"]
    if bl and bl["kind"] == "platebody":
        armour.arm_plate(surf, s, sh, el, hand, bl, P.get("t", 0.0))
        return
    sleeve = bl["pal"][0] if bl else P["shirt"]
    ua = (1.2 if not feminine else 1.05) * (1.0 + 0.2 * armour.bulk(bl))
    _limb(surf, sh, el, ua * s, 0.92 * s, sleeve)
    armoured_fore = bl and bl["kind"] == "platebody"
    fore = bl["pal"][0] if armoured_fore else P["skin"]
    if bl and bl["kind"] in ("chainbody", "leather_body"):
        # sleeve to mid-forearm, then skin
        mid = (el[0] + (hand[0] - el[0]) * 0.45, el[1] + (hand[1] - el[1]) * 0.45)
        _limb(surf, el, mid, 0.92 * s, 0.84 * s, sleeve)
        _limb(surf, mid, hand, 0.8 * s, 0.66 * s, P["skin"])
        # bracer
        st_ = armour.st(bl)
        w0 = (mid[0] + (hand[0] - mid[0]) * 0.2, mid[1] + (hand[1] - mid[1]) * 0.2)
        _limb(surf, w0, (hand[0] + (w0[0] - hand[0]) * 0.25, hand[1] + (w0[1] - hand[1]) * 0.25), 1.0 * s, 0.9 * s,
              armour.MATSH(bl) if hasattr(armour, "MATSH") else _sh(bl["pal"][1], 0))
        gear.fline(surf, st_["rivet"], (w0[0] - 0.4 * s, w0[1] + 0.6 * s), (w0[0] + 0.4 * s, w0[1] + 0.6 * s), 1)
    else:
        _limb(surf, el, hand, 0.9 * s if not feminine else 0.8 * s, 0.66 * s, fore)
        if armoured_fore:  # vambrace cuff
            gear.fline(surf, bl["pal"][2] if not bl["gold"] else gear.GOLD[0],
                       (hand[0] - 0.8 * s, hand[1] - 1.4 * s), (hand[0] + 0.8 * s, hand[1] - 1.4 * s), max(1, int(s * 0.4)))
    hc = P["skin"] if not armoured_fore else _sh(bl["pal"][0], -10)
    _circ(surf, hc, hand, 0.82 * s)


def _deltoid(surf, s, sh, P, sign):
    bl = P["body"]
    if bl and bl["kind"] in ("platebody", "chainbody", "leather_body", "goblin_mail"):
        armour.pauldron(surf, s, sh, bl, sign, P.get("view", "front"), P.get("t", 0.0))
        return
    if bl and bl["kind"] == "platebody":
        b, d, l = bl["pal"]
        g = bl["gold"]
        r = 1.55 * s + (0.25 * s if bl["tier"] >= 5 else 0)
        pts = [(sh[0] - r * 1.05, sh[1] + 0.6 * s), (sh[0] - r * 0.7, sh[1] - r * 0.75), (sh[0] + r * 0.7, sh[1] - r * 0.8),
               (sh[0] + r * 1.05, sh[1] + 0.6 * s), (sh[0] + r * 0.6, sh[1] + r * 0.95), (sh[0] - r * 0.6, sh[1] + r * 0.95)]
        _fp(surf, b, pts)
        gear.fline(surf, gear.GOLD[0] if g else l, (sh[0] - r * 0.8, sh[1] + 0.3 * s), (sh[0] + r * 0.8, sh[1] + 0.3 * s), max(1, int(s * 0.35)))
        if bl["mat"] == "mythos":
            _fp(surf, gear.GOLD[0], [(sh[0] + sign * r * 0.3, sh[1] - r * 0.7), (sh[0] + sign * r * 1.3, sh[1] - r * 1.6), (sh[0] + sign * r * 0.9, sh[1] - r * 0.4)], gear.GOLD[1])
    else:
        col = bl["pal"][0] if bl else P["shirt"]
        _circ(surf, col, (sh[0], sh[1] + 0.3 * s), 1.2 * s, None)


def _torso(surf, s, neck, pelvis, sh_a, sh_b, P, feminine, view, facing=1):
    """Chest from shoulders to the waist; hips/belt block sits over the pelvis joint."""
    bl = P["body"]
    col = bl["pal"][0] if bl else P["shirt"]
    xa, xb = min(sh_a[0], sh_b[0]), max(sh_a[0], sh_b[0])
    shy = (sh_a[1] + sh_b[1]) / 2
    cxn = neck[0]
    waist_y = pelvis[1] - 1.9 * s
    ww = (2.55 if feminine else 3.05) * s
    chest_w = (xb - xa) / 2 - 0.9 * s
    bk = armour.bulk(bl)
    chest_w += bk * 0.95 * s
    ww += bk * 0.6 * s
    bust = 0.4 * s if (feminine and not bk) else 0.0
    pts = [(cxn - chest_w * 0.72, neck[1] + 0.9 * s), (cxn + chest_w * 0.72, neck[1] + 0.9 * s),
           (xb - 0.4 * s, shy - 0.5 * s), (xb - 0.7 * s, shy + 1.8 * s),
           (cxn + chest_w * 0.82 + bust, shy + 4.2 * s), (pelvis[0] + ww, waist_y),
           (pelvis[0] - ww, waist_y), (cxn - chest_w * 0.82 - bust, shy + 4.2 * s),
           (xa + 0.7 * s, shy + 1.8 * s), (xa + 0.4 * s, shy - 0.5 * s)]
    _fp(surf, col, pts, None)
    # shadow half (right side for front/side; flat shading)
    half = [(cxn + chest_w * 0.1, neck[1] + 0.9 * s), (cxn + chest_w * 0.72, neck[1] + 0.9 * s), (xb - 0.4 * s, shy - 0.5 * s),
            (xb - 0.7 * s, shy + 1.8 * s), (cxn + chest_w * 0.82 + bust, shy + 4.2 * s), (pelvis[0] + ww, waist_y),
            (pelvis[0] + ww * 0.25, waist_y)]
    _fp(surf, _sh(col, -22), half, None)
    pygame.draw.polygon(surf, OUT, [(int(round(x)), int(round(y))) for x, y in pts], 1)
    # --- clothing / armour detail
    if bl is None:
        if view != "back":
            # collar V + hem
            gear.fline(surf, _sh(col, -40), (cxn - 0.9 * s, neck[1] + 1.0 * s), (cxn, neck[1] + 2.6 * s), 1)
            gear.fline(surf, _sh(col, -40), (cxn + 0.9 * s, neck[1] + 1.0 * s), (cxn, neck[1] + 2.6 * s), 1)
            if feminine:
                gear.fline(surf, _sh(col, -34), (cxn - chest_w * 0.6, shy + 3.2 * s), (cxn + chest_w * 0.6, shy + 3.2 * s), 1)
        else:
            gear.fline(surf, _sh(col, -30), (cxn, neck[1] + 2.0 * s), (cxn, waist_y - 1.0 * s), 1)
        return
    k, (b, d, l) = bl["kind"], bl["pal"]
    g = bl["gold"]
    if k == "platebody":
        armour.chest_plate(surf, s, neck, pelvis, chest_w, ww, shy, waist_y, bl, view, P.get("t", 0.0))
        return
    if k == "platebody_OLD":
        if view != "back":
            gear.fline(surf, l, (cxn, neck[1] + 1.4 * s), (cxn, waist_y - 0.4 * s), max(1, int(s * 0.4)))   # keel ridge
            gear.fline(surf, d, (cxn - chest_w * 0.7, shy + 3.4 * s), (cxn + chest_w * 0.7, shy + 3.4 * s), 1)  # pec line
            if bl["tier"] >= 4:
                gear.fline(surf, l, (cxn - ww * 0.8, waist_y - 1.4 * s), (cxn + ww * 0.8, waist_y - 1.4 * s), 1)
            if bl["tier"] == 2:
                for xx in (-1.5, 1.5):
                    _circ(surf, l, (cxn + xx * s, shy + 1.2 * s), 0.3 * s, None)
            if g:
                gear.fline(surf, gear.GOLD[0], pts[0], pts[1], max(1, int(s * 0.45)))
                c = (cxn, shy + 1.8 * s)
                _circ(surf, gear.GOLD[0], c, 1.35 * s, gear.GOLD[1])
                if bl["mat"] == "eclipse":
                    _circ(surf, b, (c[0] + 0.45 * s, c[1] - 0.1 * s), 1.05 * s, None)
                    for sg in (-1, 1):
                        gear.fline(surf, gear.GOLD[0], (c[0] + sg * 1.6 * s, c[1] + 1.2 * s), (c[0] + sg * 2.4 * s, waist_y - 0.6 * s), 1)
                else:
                    _fp(surf, (150, 30, 32), [(c[0] - 0.7 * s, c[1] - 0.5 * s), (c[0] + 0.7 * s, c[1] - 0.5 * s), (c[0], c[1] + 0.9 * s)], None)
        else:
            gear.fline(surf, l, (cxn, neck[1] + 1.4 * s), (cxn, waist_y - 0.4 * s), 1)
            if g:
                gear.fline(surf, gear.GOLD[0], (cxn - chest_w * 0.6, shy + 1.0 * s), (cxn + chest_w * 0.6, shy + 1.0 * s), 1)
    elif k == "chainbody":
        yy = neck[1] + 1.8 * s
        row = 0
        while yy < waist_y - 0.3 * s:
            u = (yy - neck[1]) / max(1.0, waist_y - neck[1])
            half_w = chest_w * (0.8 - 0.1 * u) if u < 0.6 else ww * 0.95
            x = cxn - half_w + (row % 2) * 0.6 * s
            while x < cxn + half_w - 0.3 * s:
                surf.set_at((int(x), int(yy)), l)
                x += 1.2 * s
            yy += 1.0 * s
            row += 1
        gear.fline(surf, d, (cxn - chest_w * 0.72, neck[1] + 1.0 * s), (cxn + chest_w * 0.72, neck[1] + 1.0 * s), max(1, int(s * 0.5)))
        # mail hem + tier trim band
        gear.fline(surf, armour.st(bl)["trim"], (pelvis[0] - ww, waist_y - 0.2 * s), (pelvis[0] + ww, waist_y - 0.2 * s), max(1, int(s * 0.4)))
    elif k == "leather_body":
        for xx in (-1.6, 1.6):
            gear.fline(surf, l, (cxn + xx * s, neck[1] + 1.6 * s), (pelvis[0] + xx * 0.9 * s, waist_y - 0.2 * s), 1)
        gear.fline(surf, d, (cxn - chest_w * 0.8, shy + 3.0 * s), (cxn + chest_w * 0.8, shy + 3.0 * s), 1)
        for xx in (-2.2, -0.8, 0.8, 2.2):          # studs
            _circ(surf, armour.STYLE["leather"]["rivet"], (cxn + xx * s, shy + 1.4 * s), 0.25 * s, None)
    elif k == "goblin_mail":
        _fp(surf, (112, 80, 48), [(cxn - 2.2 * s, shy + 0.2 * s), (cxn + 0.4 * s, shy - 0.2 * s), (cxn + 0.6 * s, shy + 2.8 * s), (cxn - 2.0 * s, shy + 3.2 * s)], None)
        _fp(surf, d, [(cxn + 0.8 * s, shy + 2.4 * s), (cxn + 2.6 * s, shy + 2.2 * s), (cxn + 2.2 * s, shy + 4.8 * s), (cxn + 0.6 * s, shy + 4.6 * s)], None)
        for xx, yv in ((-1.6, 0.8), (1.8, 2.8), (-0.8, 4.4)):
            _circ(surf, l, (cxn + xx * s, shy + yv * s), 0.3 * s, None)


def _hips(surf, s, pelvis, hip_w, P, feminine, view, robe):
    ll = P["legs"]
    col = ll["pal"][0] if ll else P["pants"]
    hw = (hip_w + 1.35) * s
    top = pelvis[1] - 2.0 * s
    _fp(surf, col, [(pelvis[0] - hw * 0.86, top), (pelvis[0] + hw * 0.86, top), (pelvis[0] + hw, pelvis[1] + 1.2 * s),
                    (pelvis[0] + 0.4 * s, pelvis[1] + 2.2 * s), (pelvis[0] - 0.4 * s, pelvis[1] + 2.2 * s), (pelvis[0] - hw, pelvis[1] + 1.2 * s)])
    bl = P["body"]
    skirt = (feminine and not ll and not bl) or robe
    if skirt:
        sc = P["shirt"] if robe else _sh(P["pants"], 14)
        L = 5.6 * s if robe else 4.4 * s
        _fp(surf, sc, [(pelvis[0] - hw * 0.9, top), (pelvis[0] + hw * 0.9, top), (pelvis[0] + hw * 1.25, pelvis[1] + L - 1.0 * s),
                       (pelvis[0] - hw * 1.25, pelvis[1] + L - 1.0 * s)])
        gear.fline(surf, _sh(sc, -30), (pelvis[0] + 0.6 * s, top + 1.0 * s), (pelvis[0] + 1.0 * s, pelvis[1] + L - 1.2 * s), 1)
    if ll and ll["kind"] == "platelegs":
        armour.faulds(surf, s, pelvis, hw * 1.08, top + 0.4 * s, ll, view, P.get("t", 0.0))
    # belt
    belt = (58, 42, 30) if not (bl and bl["gold"]) else (30, 26, 28)
    _fp(surf, belt, [(pelvis[0] - hw * 0.88, top - 0.3 * s), (pelvis[0] + hw * 0.88, top - 0.3 * s),
                     (pelvis[0] + hw * 0.9, top + 0.6 * s), (pelvis[0] - hw * 0.9, top + 0.6 * s)], None)
    if view != "back":
        buck = gear.GOLD[0] if (bl and bl["gold"]) else (170, 150, 96)
        pygame.draw.rect(surf, buck, pygame.Rect(int(pelvis[0] - 0.5 * s), int(top - 0.3 * s), max(2, int(1.0 * s)), max(2, int(0.9 * s))))


HEAD_SCALE = 0.86  # head drawn at 0.86 of the old size -> ~6.5 heads tall figure


def _head(surf, s, H, P, feminine, view, facing=1, helmet_id=None):
    s = s * HEAD_SCALE
    skin, hair = P["skin"], P["hair"]
    hd = _sh(hair, -28)
    f = facing
    Q = lambda x, y: (H[0] + x * s * f, H[1] + y * s)
    hl = P["helm"]
    full_helm = hl and hl["kind"] in ("dragon_helm", "grill_helm")
    # long hair behind (female)
    if feminine and not full_helm:
        if view == "side":
            _fp(surf, hair, [Q(-1.0, -2.6), Q(-2.5, -1.2), Q(-2.9, 2.0), Q(-2.6, 4.6), Q(-0.6, 4.2), Q(0.0, 1.0)], _sh(hair, -45))
        elif view == "front":
            _fp(surf, hair, [Q(-2.5, -1.8), Q(2.5, -1.8), Q(2.9, 2.2), Q(2.7, 4.6), Q(-2.7, 4.6), Q(-2.9, 2.2)], _sh(hair, -45))
    if view == "side":
        head = [Q(-2.1, -1.2), Q(-1.5, -2.6), Q(0.1, -3.1), Q(1.6, -2.6), Q(2.2, -1.2), Q(2.25, 0.1), Q(2.75, 0.75), Q(2.25, 1.05),
                Q(2.15, 1.7), Q(1.45, 2.55), Q(0.2, 2.75), Q(-0.9, 1.7), Q(-1.9, 0.5)]
        _fp(surf, skin, head)
        _fp(surf, _sh(skin, -22), [Q(-0.9, 1.7), Q(0.2, 2.75), Q(1.45, 2.55), Q(0.9, 1.9), Q(-0.3, 1.2)], None)  # jaw shade
        # ear
        _fp(surf, _sh(skin, -14), [Q(-0.9, -0.4), Q(-0.3, -0.5), Q(-0.3, 0.7), Q(-0.9, 0.8)], _sh(skin, -50))
        if not full_helm:
            ex, ey = Q(1.25, -0.25)
            pygame.draw.rect(surf, (238, 232, 222), pygame.Rect(int(ex - 0.2 * s), int(ey - 0.3 * s), max(1, int(0.75 * s)), max(1, int(0.6 * s))))
            pygame.draw.rect(surf, (36, 28, 26), pygame.Rect(int(ex + 0.1 * s * f), int(ey - 0.3 * s), max(1, int(0.4 * s)), max(1, int(0.65 * s))))
            gear.fline(surf, hd, Q(0.7, -0.95), Q(2.0, -0.9), max(1, int(s * 0.32)))   # brow
            gear.fline(surf, _sh(skin, -45), Q(1.55, 1.55), Q(2.1, 1.5), 1)            # mouth
            gear.fline(surf, _sh(skin, -30), Q(2.2, 1.05), Q(2.7, 0.8), 1)             # nose underside
            if feminine:
                gear.fline(surf, _sh(skin, -8), Q(1.6, 1.7), Q(2.05, 1.65), 1)
        if not hl:
            if feminine:
                cap = [Q(-2.3, 0.6), Q(-2.4, -1.6), Q(-1.4, -3.1), Q(0.4, -3.45), Q(2.0, -2.8), Q(2.55, -1.3), Q(1.9, -1.1), Q(1.0, -2.0), Q(-0.2, -1.6), Q(-0.9, -0.5)]
            else:
                cap = [Q(-2.3, 0.4), Q(-2.35, -1.6), Q(-1.4, -3.05), Q(0.4, -3.4), Q(1.9, -2.85), Q(2.4, -1.5), Q(1.8, -1.55), Q(0.9, -2.05),
                       Q(-0.2, -1.5), Q(-0.6, 0.3), Q(-1.1, 0.9)]
            _fp(surf, hair, cap, _sh(hair, -45))
            gear.fline(surf, _sh(hair, 22), Q(-1.2, -2.6), Q(0.6, -3.0), 1)
    else:
        head = [Q(-2.2, -1.0), Q(-1.8, -2.6), Q(0, -3.1), Q(1.8, -2.6), Q(2.2, -1.0), Q(2.1, 0.8), Q(1.4, 2.2), Q(0, 2.8), Q(-1.4, 2.2), Q(-2.1, 0.8)]
        # ears
        for sg in (-1, 1):
            _fp(surf, _sh(skin, -12), [Q(2.05 * sg, -0.5), Q(2.6 * sg, -0.3), Q(2.5 * sg, 0.8), Q(2.05 * sg, 0.9)], _sh(skin, -50))
        _fp(surf, skin, head)
        if view == "front":
            _fp(surf, _sh(skin, -20), [Q(0.2, -3.0), Q(1.8, -2.6), Q(2.2, -1.0), Q(2.1, 0.8), Q(1.4, 2.2), Q(0.2, 2.8)], None)
            pygame.draw.polygon(surf, OUT, [(int(round(x)), int(round(y))) for x, y in head], 1)
            if not full_helm:
                for sg in (-1, 1):
                    ex, ey = Q(0.95 * sg, -0.2)
                    pygame.draw.rect(surf, (238, 232, 222), pygame.Rect(int(ex - 0.45 * s), int(ey - 0.3 * s), max(2, int(0.9 * s)), max(1, int(0.6 * s))))
                    pygame.draw.rect(surf, (36, 28, 26), pygame.Rect(int(ex - 0.2 * s), int(ey - 0.3 * s), max(1, int(0.45 * s)), max(1, int(0.65 * s))))
                    gear.fline(surf, _sh(hair, -28), Q(0.45 * sg, -0.95), Q(1.55 * sg, -0.85), max(1, int(s * 0.3)))
                gear.fline(surf, _sh(skin, -32), Q(0.1, 0.1), Q(0.35, 0.9), 1)
                gear.fline(surf, _sh(skin, -32), Q(-0.3, 1.0), Q(0.35, 1.0), 1)
                gear.fline(surf, _sh(skin, -48), Q(-0.6, 1.65), Q(0.6, 1.65), 1)
            if not hl:
                if feminine:
                    cap = [Q(-2.45, 0.4), Q(-2.4, -1.8), Q(-1.5, -3.1), Q(0, -3.45), Q(1.5, -3.1), Q(2.4, -1.8), Q(2.45, 0.4), Q(1.9, -1.4), Q(0.3, -1.9), Q(-1.2, -1.2), Q(-1.95, -0.2)]
                else:
                    cap = [Q(-2.4, 0.1), Q(-2.4, -1.7), Q(-1.6, -3.0), Q(0, -3.45), Q(1.6, -3.0), Q(2.4, -1.7), Q(2.4, 0.1), Q(1.95, -1.35), Q(0.7, -1.7), Q(-0.3, -1.45), Q(-1.95, -1.3)]
                _fp(surf, hair, cap, _sh(hair, -45))
                gear.fline(surf, _sh(hair, 22), Q(-1.3, -2.6), Q(0.2, -3.1), 1)
        else:  # back
            pygame.draw.polygon(surf, OUT, [(int(round(x)), int(round(y))) for x, y in head], 1)
            if not hl:
                if feminine:
                    cap = [Q(-2.45, -1.6), Q(-1.6, -3.1), Q(0, -3.45), Q(1.6, -3.1), Q(2.45, -1.6), Q(2.8, 2.2), Q(2.5, 4.8), Q(-2.5, 4.8), Q(-2.8, 2.2)]
                else:
                    cap = [Q(-2.4, 1.2), Q(-2.4, -1.7), Q(-1.6, -3.0), Q(0, -3.45), Q(1.6, -3.0), Q(2.4, -1.7), Q(2.4, 1.2), Q(1.4, 2.0), Q(-1.4, 2.0)]
                _fp(surf, hair, cap, _sh(hair, -45))
                _fp(surf, hd, [Q(0.2, -3.3), Q(1.6, -3.0), Q(2.4, -1.7), Q(2.4 if not feminine else 2.8, 1.2 if not feminine else 2.2), Q(0.4, 1.0)], None)
    if hl:
        gear.draw_helmet_front(surf, H[0], H[1], s * 0.95, helmet_id, view=view, facing=f, t=P.get("t", 0.0))


def _amulet(surf, s, neck, amulet_id, view):
    if not amulet_id or view == "back":
        return
    try:
        import content_items_cache as _c  # optional; falls back to gold
        gem = _c.gem(amulet_id)
    except Exception:
        gem = (200, 60, 60) if "ruby" in amulet_id else (60, 170, 90) if ("emerald" in amulet_id or "jade" in amulet_id) else \
            (60, 90, 210) if "sapphire" in amulet_id else (230, 230, 240) if ("diamond" in amulet_id or "opal" in amulet_id) else \
            (100, 50, 160) if "void" in amulet_id else (40, 36, 48) if "onyx" in amulet_id else (220, 150, 50)
    gear.fline(surf, gear.GOLD[0], (neck[0] - 1.0 * s, neck[1] + 1.0 * s), (neck[0], neck[1] + 2.6 * s), 1)
    gear.fline(surf, gear.GOLD[0], (neck[0] + 1.0 * s, neck[1] + 1.0 * s), (neck[0], neck[1] + 2.6 * s), 1)
    _circ(surf, gem, (neck[0], neck[1] + 2.9 * s), 0.55 * s, gear.GOLD[1])


# ---------------------------------------------------------------------------
def draw(surf, cx, cy, tile, body_color=(70, 120, 210), skin_color=(235, 195, 150), hair_color=(70, 45, 30),
         weapon=None, shield=False, moving=False, t=0.0, robe=False, facing=1, equipment=None,
         attacking=0.0, action=None, gender="male"):
    """Drop-in replacement for rs_humanoid.draw_skeletal_humanoid (same args)."""
    equipment = equipment or {}
    view, facing = old._parse_facing(facing)
    feminine = str(gender).lower() == "female"
    if view == "side" and facing < 0:
        pad = max(72, int(tile * 2.7))
        tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        draw(tmp, pad, pad, tile, body_color, skin_color, hair_color, weapon, shield, moving, t, robe, 1,
             equipment, attacking, action, gender)
        surf.blit(pygame.transform.flip(tmp, True, False), (int(cx - pad), int(cy - pad)))
        return
    s = rs.unit(tile, "character")
    if feminine:
        s *= 0.96
    pose, wkind = resolve(moving, t, attacking, facing, action, weapon, equipment)
    weapon_id = equipment.get("weapon")
    shield_id = equipment.get("shield")
    helmet_id = equipment.get("helmet")
    gather_tool = None
    if action == "fishing":
        wkind, gather_tool = "rod", "fishing_rod"
    elif action == "woodcutting" and wkind not in ("axe", "battleaxe"):
        wkind, gather_tool = "axe", "bronze_axe"
    elif action == "mining" and wkind != "pickaxe":
        wkind, gather_tool = "pickaxe", "bronze_pickaxe"
    if shield_id and action not in ("fishing", "woodcutting", "mining"):
        shield = True
    elif action in ("fishing", "woodcutting", "mining"):
        shield = False
    draw_id = gather_tool or weapon_id
    P = palette(body_color, skin_color, hair_color, feminine, equipment, robe)
    P["t"] = float(t or 0.0)
    if view in ("front", "back") and (float(attacking or 0) > 0.02 or action in ("fishing", "woodcutting", "mining", "stand")):
        view = "side"
    on_back = (float(attacking or 0) <= 0.01 and action in (None, "stand")
               and ((bool(wkind) and wkind != "rod") or bool(shield)))

    def _weapon(hx, hy, sc, fac, swing, sheathed=False):
        if not wkind:
            return
        if draw_id and gear.draw_weapon(surf, hx, hy, sc, draw_id, fac, swing, sheathed, fallback_kind=wkind):
            return
        old._draw_weapon(surf, hx, hy, sc, wkind, fac, draw_id, swing, sheathed=sheathed)

    if view in ("front", "back"):
        R = rig_ortho(cx, cy, s, view, moving, t, pose, feminine)
        neck, pelvis = R["neck"], R["pelvis"]
        rs.draw_contact_shadow(surf, cx, R["foot_y"], 8.5 * s, 3.2 * s, 150)
        rs.draw_cast_shadow(surf, cx + 1.2 * s, R["foot_y"] + 0.4 * s, 11.0 * s, 3.4 * s, 90)
        if robe:
            _fp(surf, _sh(P["shirt"], -22), [(neck[0] - 4.2 * s, neck[1] + 2.0 * s), (neck[0] + 4.2 * s, neck[1] + 2.0 * s),
                                              (pelvis[0] + 5.6 * s, pelvis[1] + 9 * s), (pelvis[0] - 5.6 * s, pelvis[1] + 9 * s)])
        if view == "front":
            armour.back_cape(surf, s, neck, pelvis, P["body"], "front", 0.0, P["t"])
        if view == "front" and on_back:
            if shield:
                gear.draw_shield(surf, neck[0] - 3.0 * s, neck[1] + 4.6 * s, s * 0.95, shield_id or "wooden_shield")
            if wkind and wkind != "rod":
                _weapon(neck[0] + 4.6 * s, neck[1] - 3.2 * s, s * 0.78, 1, 0.0, sheathed=True)
        for foot, knee, hip in R["legs"]:
            _leg(surf, s, hip, knee, foot, P, feminine, view)
        _hips(surf, s, pelvis, R["hip_w"], P, feminine, view, robe)
        if view == "back":
            for hand, el, sh in R["arms"]:
                _arm(surf, s, sh, el, hand, P, feminine)
        _torso(surf, s, neck, pelvis, R["sh_l"], R["sh_r"], P, feminine, view)
        for sh, sg in ((R["sh_l"], -1), (R["sh_r"], 1)):
            _deltoid(surf, s, sh, P, sg)
        if view == "back":
            armour.back_cape(surf, s, neck, pelvis, P["body"], "back", math.sin(t * rs.TAU * 1.15) * 0.4 * s if moving else 0.0, P["t"])
        if view == "back" and on_back:
            if shield:
                gear.draw_shield(surf, neck[0], neck[1] + 6.0 * s, s * 1.0, shield_id or "wooden_shield", on_back=True)
            if wkind and wkind != "rod":
                _weapon(neck[0] - 3.0 * s, neck[1] - 1.8 * s, s * 0.78, -1, 0.0, sheathed=True)
        # neck + head
        _limb(surf, (neck[0], neck[1] + 1.0 * s), (neck[0], neck[1] - 1.2 * s), 0.95 * s, 0.9 * s, _sh(P["skin"], -12))
        _amulet(surf, s, neck, P["amulet"], view)
        _head(surf, s, (neck[0], neck[1] - 1.8 * s), P, feminine, view, 1, helmet_id)
        if view == "front":
            for hand, el, sh in R["arms"]:
                _arm(surf, s, sh, el, hand, P, feminine)
        return R

    R = rig_side(cx, cy, s, pose, feminine, facing, moving, attacking)
    neck, pelvis = R["neck"], R["pelvis"]
    rs.draw_contact_shadow(surf, cx, R["foot_y"], 8.5 * s, 3.2 * s, 150)
    rs.draw_cast_shadow(surf, cx + 1.5 * s, R["foot_y"] + 0.5 * s, 11.5 * s, 3.6 * s, 95)
    if robe:
        sway = pose.get("cape", 0.0) * 4 * s * facing
        _fp(surf, _sh(P["shirt"], -22), [(neck[0] - 4.2 * s, neck[1] + 2.5 * s), (neck[0] + 3.8 * s, neck[1] + 2.5 * s),
                                          (pelvis[0] + 6.8 * s + sway, pelvis[1] + 10 * s), (pelvis[0] + 1 * s + sway * 0.5, pelvis[1] + 11.5 * s),
                                          (pelvis[0] - 6.0 * s + sway * 0.3, pelvis[1] + 10 * s)])
    armour.back_cape(surf, s, neck, pelvis, P["body"], "side", pose.get("cape", 0.0) * 3 * s * facing, P["t"])
    weapon_on_back = on_back and bool(wkind) and wkind != "rod"
    shield_on_back = on_back and bool(shield)
    if shield_on_back:
        gear.draw_shield(surf, neck[0] - 2.2 * s * facing, neck[1] + 5.5 * s, s * 1.0, shield_id or "wooden_shield", on_back=True)
    if weapon_on_back:
        _weapon(neck[0] - 5.8 * s * facing, neck[1] - 2.4 * s, s * 0.78, facing, 0.0, sheathed=True)
    for foot, knee, hip in (R["far_leg"], R["near_leg"]):
        _leg(surf, s, hip, knee, foot, P, feminine, "side", facing)
    _hips(surf, s, pelvis, R["hip_w"], P, feminine, "side", robe)
    _arm(surf, s, R["sh_far"], R["el_far"], R["hand_far"], P, feminine)
    _torso(surf, s, neck, pelvis, R["sh_far"], R["sh_near"], P, feminine, "side", facing)
    _deltoid(surf, s, R["sh_far"], P, -1)
    if shield and not shield_on_back:
        gear.draw_shield(surf, R["hand_far"][0] - 1.6 * s * facing, R["hand_far"][1] + 0.8 * s, s * 0.85, shield_id or "wooden_shield")
    _limb(surf, (neck[0] + 0.1 * s, neck[1] + 1.0 * s), (neck[0] + 0.3 * s, neck[1] - 1.2 * s), 0.95 * s, 0.85 * s, _sh(P["skin"], -12))
    _amulet(surf, s, neck, P["amulet"], "side")
    _head(surf, s, (neck[0] + 0.35 * s * facing, neck[1] - 1.8 * s), P, feminine, "side", facing, helmet_id)
    _deltoid(surf, s, R["sh_near"], P, 1)
    _arm(surf, s, R["sh_near"], R["el_near"], R["hand_near"], P, feminine)
    if wkind and not weapon_on_back:
        _weapon(R["hand_near"][0], R["hand_near"][1], s, facing, pose["weapon"])
    return R
