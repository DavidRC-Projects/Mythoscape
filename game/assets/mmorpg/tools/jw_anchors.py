"""tools/jw_anchors.py - derive jewellery anchors for HD whole-figure layers (pygame only, no numpy/scipy).
Usage: python3 tools/jw_anchors.py [layer_dir ...]   (no args: every outfit_set_*/hd_set_*/armour HD layer at 1x/2x/4x)
Writes <layer_dir>/jw_anchors.json: {"_frame": px, "<anim>_<facing>": [anchors per frame]}.
Anchor keys: u, head_top, face_box, neck, ear_l, ear_r, head_back, chest, hand_l, hand_r."""
import glob, json, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ANIMS = ("idle", "walk", "sword", "axe", "chop", "mine", "fish")

def _bbox_rows(mask, w, h):
    top = bot = None
    for y in range(h):
        if any(mask.get_at((x, y)) for x in range(0, w, 2)):
            top = y; break
    for y in range(h - 1, -1, -1):
        if any(mask.get_at((x, y)) for x in range(0, w, 2)):
            bot = y; break
    return top, bot

def _ear_points(sm, m, w, h, x0, x1, ear_y, u, facing, cx, fw, body_h):
    """Earlobe anchors — inset from face center (old 98% of face_box sat on the hair edge)."""
    hw = max(fw, 0.09 * body_h) / 2
    # ~58% of face half-width lands on the lobe for these HD figures.
    safe_l, safe_r = cx - hw * 0.58, cx + hw * 0.58
    if facing == "e":
        return [[cx - 0.12 * max(fw, 1.0), ear_y], [cx - 0.12 * max(fw, 1.0), ear_y]]
    xs = []
    y0b, y1b = max(0, int(ear_y - u)), min(h, int(ear_y + 1.5 * u) + 1)
    x_lo, x_hi = max(0, int(x0 - u)), min(w, int(x1 + u) + 1)
    mask = sm if sm is not None else m
    for y in range(y0b, y1b):
        for x in range(x_lo, x_hi):
            if mask.get_at((x, y)):
                xs.append(x)
    if len(xs) >= 2:
        left, right = float(min(xs)), float(max(xs))
        # Trust skin only when it is tighter than the face box (avoids hair/jaw blobs).
        if (right - left) < fw * 0.85:
            left, right = left - 0.15 * u, right + 0.15 * u
            return [[max(left, safe_l), ear_y], [min(right, safe_r), ear_y]]
    return [[safe_l, ear_y], [safe_r, ear_y]]


def frame_anchors(fr, sk, facing):
    w, h = fr.get_size()
    m = pygame.mask.from_surface(fr, 40)
    r = m.get_bounding_rects()
    if not r: return None
    bb = r[0].unionall(r[1:]) if len(r) > 1 else r[0]
    top, bot = bb.top, bb.bottom - 1; H = bot - top + 1; u = H / 60.0
    band = [x for y in range(top, int(top + 0.2 * H)) for x in range(w) if m.get_at((x, y))]
    band.sort(); cx = band[len(band) // 2] if band else bb.centerx
    face = None; hands = []; sm = None
    if sk is not None:
        sm = pygame.mask.from_surface(sk, 40)
        for c in sm.connected_components(max(2, int(6 * u))):
            cr = c.get_bounding_rects(); cr = cr[0].unionall(cr[1:]) if len(cr) > 1 else cr[0]
            area = c.count()
            if cr.top < top + 0.30 * H and (face is None or area > face[4]): face = (cr.left, cr.top, cr.right, cr.bottom, area)
            elif cr.top > top + 0.35 * H and cr.bottom < top + 0.75 * H: hands.append((cr.centerx, cr.centery, area))
    if facing == "n" or face is None:
        ry = int(top + 0.11 * H); row = [x for x in range(w) if m.get_at((x, ry))]
        hw2 = min((max(row) - min(row)) / 2 * 0.85, 0.075 * H) if row else 0.06 * H
        face = (cx - hw2, top + 0.03 * H, cx + hw2, top + 0.175 * H, 0)
    x0, y0, x1, y1 = [float(v) for v in face[:4]]; fw = x1 - x0
    chin = min(y1, top + 0.175 * H); neck = [(x0 + x1) / 2, chin + 0.02 * H]; ear_y = top + 0.11 * H
    ear_l, ear_r = _ear_points(sm, m, w, h, x0, x1, ear_y, u, facing, (x0 + x1) / 2, fw, H)
    hands.sort()
    if facing == "e":
        hp = list(hands[-1][:2]) if hands else [cx + 0.02 * H, top + 0.5 * H]; hand_l = hand_r = hp
    else:
        hand_l = list(hands[0][:2]) if hands else [cx - 0.16 * H, top + 0.5 * H]
        hand_r = list(hands[-1][:2]) if len(hands) > 1 else [cx + 0.16 * H, top + 0.5 * H]
    R = lambda v: round(float(v), 1)
    return {"u": round(u, 3), "head_top": [cx, top], "face_box": [R(x0), R(y0), R(x1), R(chin)], "neck": [R(neck[0]), R(neck[1])],
            "ear_l": [R(ear_l[0]), R(ear_l[1])], "ear_r": [R(ear_r[0]), R(ear_r[1])], "head_back": [cx, R(top + 5 * u)],
            "chest": [R(neck[0] + (3 if facing != "e" else 1) * u), R(neck[1] + 7 * u)], "hand_l": [R(v) for v in hand_l], "hand_r": [R(v) for v in hand_r]}

def layer(d):
    out = {}
    for an in ANIMS:
        for f in "sen":
            p = f"{d}/{an}_{f}.png"
            if not os.path.exists(p): continue
            st = pygame.image.load(p); s = st.get_height(); out["_frame"] = s
            sp = f"{d}/{an}_{f}_skin.png"; sk = pygame.image.load(sp) if os.path.exists(sp) else None
            out[f"{an}_{f}"] = [frame_anchors(st.subsurface((i * s, 0, s, s)), sk.subsurface((i * s, 0, s, s)) if sk else None, f)
                                for i in range(st.get_width() // s)]
    json.dump(out, open(f"{d}/jw_anchors.json", "w"))
    return out

if __name__ == "__main__":
    pygame.init()
    dirs = sys.argv[1:]
    if not dirs:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")
        dirs = []
        for scale in ("1x", "2x", "4x"):
            for pat in ("outfit_*_hd", "armour_*_hd"):
                dirs.extend(glob.glob(f"{base}/*/{scale}/{pat}"))
    for d in dirs:
        if not os.path.isdir(d):
            continue
        layer(d)
        print("ok", d)
