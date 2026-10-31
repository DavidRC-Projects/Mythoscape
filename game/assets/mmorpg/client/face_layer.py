"""Chosen face (David, 29 Oct 2026): the player's own painted head on every outfit and armour figure.

The head comes from player_hd/assets/faces (built by tools/build_faces.py from the faces already painted
in the game). Per frame: the figure's own head is erased above its neck line (its idle-frame silhouette,
moved with the frame's head anchor) and the chosen head is drawn in, joined at the neck. The head image is
always the same painted frame per facing, so it is identical on every outfit, tier and animation.

Hair colour tints only the chosen head's hair mask, which never reaches below the neck line, so clothes are
never recoloured (fixes the tint bleeding into brown / red / gold fabric).
"""
import json
import os

import pygame

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "player_hd", "assets")
_DIR = os.path.join(_BASE, "faces")
_META = None
_IMG = {}
_CACHE = {}
_CACHE_MAX = 1500
ACTION_ANIMS = ("melee", "melee_sword", "melee_axe", "chop", "mine", "fish", "ranged")


def meta():
    global _META
    if _META is None:
        try:
            with open(os.path.join(_DIR, "faces.json")) as f:
                _META = json.load(f)
        except (OSError, ValueError):
            _META = {}
    return _META


def faces(sex):
    sex = "female" if sex == "female" else "male"
    return list((meta().get("faces") or {}).get(sex) or [])


def face_ids(sex):
    return [f["id"] for f in faces(sex)]


def default_face(sex):
    ids = face_ids(sex)
    return ids[0] if ids else None


def face_for(appearance, sex, layer=None):
    """The look's chosen face; an old save without one keeps the face its outfit was painted with."""
    fid = (appearance or {}).get("face")
    if fid in face_ids(sex):
        return fid
    return (face_of_layer(sex, layer) if layer else None) or default_face(sex)


def face_of_layer(sex, layer):
    """The face id painted on an outfit layer (used to keep existing players' looks on migration)."""
    for f in faces(sex):
        if f.get("layer") == layer:
            return f["id"]
    return None


# ---- crowns (David, 29 Oct 2026): a crown is its own layer on top of whichever face is worn -------------
# player_hd/assets/crowns/<crown>/<tag>/crown_<facing>.png + crowns.json (tools/build_royal_faces.py).
# Each design is anchored to the top / centre / width of the head it was painted on, so it sits on any
# face's head top, follows the head through every animation frame and is hidden under a helmet.
_CROWN_DIR = os.path.join(_BASE, "crowns")
_CROWNS = None


def crowns():
    global _CROWNS
    if _CROWNS is None:
        try:
            with open(os.path.join(_CROWN_DIR, "crowns.json")) as f:
                _CROWNS = json.load(f).get("crowns") or {}
        except (OSError, ValueError):
            _CROWNS = {}
    return _CROWNS


def crown_for(appearance, items=None, helmet=False):
    """The crown design a look wears (its head piece's crown_art), None under a helmet or without one."""
    if helmet:
        return None
    pid = (appearance or {}).get("head")
    if not pid:
        return None
    cid = ((items or {}).get(pid) or {}).get("crown_art")
    return cid if cid in crowns() else None


def head_metrics(head, key):
    """(top, cx, width) of a head image's upper skull, in its own px."""
    k = ("hm", key)
    if k not in _CACHE:
        import numpy as np
        a = pygame.surfarray.array_alpha(head).T
        rows = np.where((a > 128).any(1))[0]
        if not len(rows):
            return _remember(k, None)
        top, bot = int(rows[0]), int(rows[-1])
        band = a[top:top + max(2, int((bot - top) * 0.25))] > 128
        xs = np.where(band.any(0))[0]
        _remember(k, (top, float(xs.mean()), float(xs[-1] - xs[0] + 1)))
    return _CACHE[k]


def crown_layer(crown_id, facing, tag, head, head_key):
    """(crown surface, (x, y)) in the head image's own px, or None."""
    info = crowns().get(crown_id or "")
    if not info:
        return None
    anc = ((info.get("anchor") or {}).get(facing) or {}).get(tag)
    surf = _img(os.path.join(_CROWN_DIR, crown_id, tag, f"crown_{facing}.png"))
    hm = head_metrics(head, head_key)
    if not anc or surf is None or not hm:
        return None
    top, cx, w = hm
    c = max(0.8, min(1.25, w / max(1.0, anc["w"])))
    return surf, c, (cx - anc["cx"] * c, top - anc["top"] * c)


def _face(sex, fid):
    for f in faces(sex):
        if f["id"] == fid:
            return f
    return None


def _img(path):
    if path not in _IMG:
        surf = None
        if os.path.isfile(path):
            try:
                surf = pygame.image.load(path)
                try:
                    surf = surf.convert_alpha()
                except pygame.error:
                    pass
            except pygame.error:
                surf = None
        _IMG[path] = surf
    return _IMG[path]


def _remember(key, val):
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = val
    return val


def head_surface(sex, fid, facing, tag, skin_rgb, hair_rgb, tint_fn):
    """The chosen head (one facing), skin toned and hair tinted. tag: 2x or 4x."""
    key = ("head", sex, fid, facing, tag, tuple(skin_rgb or ()), tuple(hair_rgb or ()))
    if key in _CACHE:
        return _CACHE[key]
    d = os.path.join(_DIR, sex, fid, tag)
    head = _img(os.path.join(d, f"head_{facing}.png"))
    if head is None:
        return None
    out = head
    skin = _img(os.path.join(d, f"skin_{facing}.png"))
    hair = _img(os.path.join(d, f"hair_{facing}.png"))
    if tint_fn is not None and skin is not None and skin_rgb:
        out = tint_fn(out, skin, tuple(skin_rgb))
    if tint_fn is not None and hair is not None and hair_rgb:
        out = tint_fn(out, hair, tuple(hair_rgb))
    return _remember(key, out)


def _scaled(surf, size, key):
    k = ("scaled", key, size)
    if k not in _CACHE:
        _remember(k, pygame.transform.smoothscale(surf, size))
    return _CACHE[k]


_MUL = {"1x": 0.5, "2x": 1.0, "4x": 2.0, "8x": 4.0}


def _offset(sex, layer, anim, facing, frame_idx, frame, tpts, kt):
    """Head movement of this frame relative to the layer's idle frame 0, in native px of its scale."""
    import helmet_overlay as _helm
    w, h = frame.get_size()
    anc = None
    if anim in ACTION_ANIMS:
        anc = _helm.action_anchor(sex, layer, anim, facing, frame_idx, w, h)
    if anc is None:
        anc = _helm.head_anchor(frame)
    if anc is None:
        return None
    top, cx, _fh = anc
    return cx / kt - tpts["cx"], top / kt - tpts["top"]


def _bottom(head, key):
    """Lowest mostly-opaque row of a donor head (its own px)."""
    k = ("bottom", key)
    if k not in _CACHE:
        import numpy as np
        a = pygame.surfarray.array_alpha(head)
        rows = np.where((a > 128).any(0))[0]
        _remember(k, int(rows[-1]) if len(rows) else head.get_height())
    return _CACHE[k]


def _top(head, key):
    """Highest mostly-opaque row of a donor head (its own px)."""
    k = ("top", key)
    if k not in _CACHE:
        import numpy as np
        a = pygame.surfarray.array_alpha(head)
        rows = np.where((a > 128).any(0))[0]
        _remember(k, int(rows[0]) if len(rows) else 0)
    return _CACHE[k]


def _pick(points, tag):
    if tag in points:
        return tag
    return "2x" if "2x" in points else (next(iter(points)) if points else None)


LAST = {}   # placement of the most recent apply() (tools/test_head_alignment.py)


def apply(frame, sex, layer, anim, facing, frame_idx, face_id, skin_rgb, hair_rgb, tint_fn, tag="2x",
          with_erase=False, crown=None):
    """New frame surface with the chosen head, or None (no data for this layer: caller keeps its own).
    tag: the scale folder the frame came from (1x / 2x / 4x).
    with_erase=True returns (frame, erase): erase is the frame-sized multiply mask that took the old head
    off, for the caller to apply to anything already drawn underneath (base body layers)."""
    if frame is None or not face_id or anim in ("death",):
        return None
    sex = "female" if sex == "female" else "male"
    tgt_all = (meta().get("targets") or {}).get(f"{sex}/{layer}")
    face = _face(sex, face_id)
    if not tgt_all or not face:
        return None
    tt = _pick(tgt_all, tag)
    ft = _pick(face.get("points") or {}, tag)
    if tt != tag and tag in _MUL and tt is not None:
        return None                      # this scale has no measured head for the figure
    if not tt or not ft or facing not in tgt_all[tt] or facing not in face["points"][ft]:
        return None
    tp, fp = tgt_all[tt][facing], face["points"][ft][facing]
    mt, md = _MUL[tt], _MUL[ft]
    w, h = frame.get_size()
    kt = w / (288.0 * mt)                # native px of the target scale -> this frame's px
    trk = track(sex, layer, anim, facing, frame_idx)
    loose = False
    if trk is not None and len(trk) > 4 and not trk[4]:
        if anim.startswith(("idle", "walk")):
            trk = None                   # idle/walk: the anchor-measured offset (no face flicker mid-stride)
        else:
            loose = True                 # action frame between matched ones: their line, a wider erase
    if trk is not None:
        # measured: the figure's own head this frame (moved + tilted about its neck), tools/build_head_track.py
        dx, dy, ang = trk[0] * mt, trk[1] * mt, float(trk[2])
        k = float(trk[3]) if len(trk) > 3 else 1.0
        if abs(ang) < 6:
            ang = 0.0                    # interpolated small tilts: keep the head crisp
    else:
        off = _offset(sex, layer, anim, facing, frame_idx, frame, tp, kt)
        if off is None:
            return None
        (dx, dy), ang = off, 0.0
        k = 1.0
        if abs(dx) > 40 * mt or abs(dy) > 40 * mt:   # anchor lost: keep the figure's own head
            return None
    erase = _img(os.path.join(_DIR, "targets", sex, layer, tt, f"erase_{facing}.png"))
    head = head_surface(sex, face_id, facing, ft, skin_rgb, hair_rgb, tint_fn)
    if erase is None or head is None:
        return None
    import numpy as np
    out = frame.copy()
    tx = (tp["neck"][0] + dx) * kt
    ty = (tp["neck"][1] + dy) * kt
    # 1) take the figure's own head off: its erase mask, moved and tilted with it, multiplied out
    ke = kt * k * (1.0 if not loose else 1.0)                          # the head drawn bigger/smaller this frame (leaning to or from us)
    esz = (max(1, int(round(erase.get_width() * ke))), max(1, int(round(erase.get_height() * ke))))
    e = _scaled(erase, esz, (sex, layer, tt, facing, "erase"))
    er, (epx, epy) = _rot(e, ang, (tp["neck"][0] * ke, tp["neck"][1] * ke), ("erase", sex, layer, tt, facing, esz))
    full = pygame.Surface((w, h), pygame.SRCALPHA)
    full.fill((0, 0, 0, 0))
    full.blit(er, (int(round(tx - epx)), int(round(ty - epy))))
    own_top = None
    prot = None
    if not anim.startswith(("idle", "walk")):
        # action frames: also take off the figure's whole own head blob (its hair + skin masks touching
        # the erase), so a head drawn bigger than the template leaves no old hair or face behind
        blob = _own_head(sex, layer, tt, anim, facing, frame_idx, (w, h), full, frame)
        if blob is not None:
            full.blit(blob[0], (0, 0))
            own_top = blob[1]
        if frame.get_size() == (w, h):
            prot = _protect_limbs(full, frame, blob[0] if blob is not None else None, h,
                                      skin_src=(sex, layer, tt, anim, facing, frame_idx),
                                      top_lim=None if own_top is None else int(own_top - max(2, 2 * kt)))
    canvas = pygame.Surface((w, h), pygame.SRCALPHA)
    canvas.fill((255, 255, 255, 255))
    ca_ = pygame.surfarray.pixels_alpha(canvas)
    ca_[...] = 255 - np.asarray(pygame.surfarray.pixels_alpha(full))
    # soft lower edge: what is left of a collar / hood under the erase fades in over a few px
    # instead of a hard straight cut (male fire outfit side view)
    nf = max(2, int(round(4 * kt * mt)))
    cf = ca_.astype(np.int32)
    soft = cf.copy()
    for k_ in range(1, nf + 1):
        sh_ = np.full_like(cf, 255)
        sh_[:, k_:] = cf[:, :-k_]
        soft = np.minimum(soft, sh_ + (k_ * 255) // (nf + 1))
    ca_[...] = np.clip(soft, 0, 255).astype(np.uint8)
    del ca_
    # 2) the chosen head, its neck on the figure's neck, scaled by neck-to-feet height
    s = max(0.85, min(1.15, (248.0 * mt - tp["neck"][1]) / mt / max(1.0, (248.0 * md - fp["neck"][1]) / md)))
    sc = kt * mt / md * s * k
    base = kt * mt / md * s          # the head's own size on this figure (before lunge growth / 4x art)
    if own_top is not None:
        # the chosen head reaches the top of the figure's own head (no see-through gap where it was)
        hb = _top(head, (sex, face_id, facing, ft))
        reach = (fp["neck"][1] - hb) * sc
        need = ty - own_top
        if need > reach + 2 * kt:
            sc *= min(1.35, need / max(1.0, reach))
    if sc > 1.15 and ft != "4x" and facing in ((face.get("points") or {}).get("4x") or {}):
        # drawn well over its own size (a lunge at the camera): use the sharper 4x art of the same head
        h4 = head_surface(sex, face_id, facing, "4x", skin_rgb, hair_rgb, tint_fn)
        if h4 is not None:
            sc *= md / float(_MUL["4x"])
            ft, md, head, fp = "4x", _MUL["4x"], h4, face["points"]["4x"][facing]
    # never erase below where the chosen head reaches (a short back-view head must not leave a gap)
    bot = _bottom(head, (sex, face_id, facing, ft))
    cut_y = int(round(ty + (bot - fp["neck"][1]) * sc)) - 1
    if 0 <= cut_y < h:
        canvas.fill((255, 255, 255, 255), pygame.Rect(0, cut_y, w, h - cut_y))
    clean = _clean_frame(sex, layer, tag, anim, facing, frame_idx, (w, h))
    if clean is not None:
        # hand-painted frame (tools/handpaint_heads.py): the old head is already painted out of the art,
        # arms / weapon / collar repainted whole, so nothing is erased here
        out = clean.copy()
        ca_ = pygame.surfarray.pixels_alpha(canvas)
        ca_[...] = 255 - np.clip(pygame.surfarray.array_alpha(frame).astype(np.int16)
                                 - pygame.surfarray.array_alpha(clean), 0, 255).astype(np.uint8)
        del ca_
    else:
        out.blit(canvas, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        # the figure's own long hair below where the chosen head ends: painted over from the cloth around it
        _clear_old_hair(out, sex, layer, tt, anim, facing, frame_idx, cut_y, tx, ty,
                        head.get_width() * sc, head.get_height() * sc, protect=prot,
                        orig_alpha=pygame.surfarray.array_alpha(frame) if frame.get_size() == out.get_size() else None)
    hs = (max(1, int(round(head.get_width() * sc))), max(1, int(round(head.get_height() * sc))))
    hkey = ("head", sex, face_id, facing, ft, tuple(skin_rgb or ()), tuple(hair_rgb or ()))
    hsurf = _scaled(head, hs, hkey)
    if crown:
        # the crown is its own layer on the head: drawn onto it so it tilts with it
        cl = crown_layer(crown, facing, ft, head, (sex, face_id, facing, ft))
        if cl:
            csurf, c, (cx0, cy0) = cl
            cs = (max(1, int(round(csurf.get_width() * c * sc))), max(1, int(round(csurf.get_height() * c * sc))))
            hsurf = hsurf.copy()
            hsurf.blit(_scaled(csurf, cs, ("crown", crown, facing, ft)), (int(round(cx0 * sc)), int(round(cy0 * sc))))
            hkey = hkey + (crown,)
    hr, (hpx, hpy) = _rot(hsurf, ang, (fp["neck"][0] * sc, fp["neck"][1] * sc), hkey + (hs,))
    hx, hy = tx - fp["neck"][0] * sc, ty - fp["neck"][1] * sc
    pos = (int(round(tx - hpx)), int(round(ty - hpy)))
    out.blit(hr, pos)
    if clean is not None and facing != "n" and not anim.startswith(("idle", "walk")):
        # hand-painted plate: what is left of it above the neck is arm / sleeve / weapon (the old head is
        # painted out), which the figure holds in front of its face, so it goes back over the new head
        # only the upper part of the head (shoulders stay behind the new hair) and never over its face
        cov = pygame.Surface((w, h), pygame.SRCALPHA)
        cov.fill((0, 0, 0, 0))
        cov.blit(hr, pos)
        ca = pygame.surfarray.pixels_alpha(cov)
        crgb = pygame.surfarray.pixels3d(cov).astype(np.int16)
        hy_ = int(pos[1])
        ny = max(0, min(h, int(hy_ + 0.55 * (ty - hy_))))
        if ny > 0:
            top = clean.copy()
            ta = pygame.surfarray.pixels_alpha(top)
            r_, g_, b_ = crgb[..., 0], crgb[..., 1], crgb[..., 2]
            facepx = (ca > 60) & (r_ > g_) & (g_ > b_) & (r_ - b_ > 25) & (r_ > 150)
            for _ in range(max(1, int(2 * kt))):
                f2 = facepx.copy()
                f2[1:] |= facepx[:-1]; f2[:-1] |= facepx[1:]; f2[:, 1:] |= facepx[:, :-1]; f2[:, :-1] |= facepx[:, 1:]
                facepx = f2
            # arms (light sleeve / skin) stay behind the new face; a dark haft held across it stays in front
            prgb = pygame.surfarray.array3d(clean).astype(np.int16)
            light = prgb.max(axis=2) > 105
            ta[facepx & light] = 0
            ta[:, ny:] = 0
            del ta
            out.blit(top, (0, 0))
        del ca, crgb
    LAST.update(tx=tx, ty=ty, sc=sc, hx=hx, hy=hy, bot=bot, neck=tuple(fp["neck"]), ang=ang, k=k, loose=loose, base=base)
    if with_erase:
        # the new head stays drawn: only the uncovered part of the old head is cleared underneath
        hole = canvas.copy()
        cover = pygame.Surface((w, h), pygame.SRCALPHA)
        cover.fill((0, 0, 0, 0))
        cover.blit(hr, pos)
        ha = pygame.surfarray.pixels_alpha(hole)
        ca = pygame.surfarray.pixels_alpha(cover)
        ha[...] = np.maximum(ha, ca)
        del ha, ca
        return out, hole
    return out


def _clean_frame(sex, layer, tag, anim, facing, frame_idx, size):
    """The hand-painted copy of this frame with the old head already painted out
    ({anim}_{facing}_clean.png beside the art, same strip layout), or None."""
    q = os.path.join(_BASE, sex, tag, layer, f"{anim}_{facing}_clean.png")
    if not os.path.exists(q):
        return None
    st = _img(q)
    if st is None:
        return None
    sh = st.get_height()
    i = int(frame_idx)
    if i < 0 or i >= st.get_width() // sh:
        return None
    fr = st.subsurface((i * sh, 0, sh, sh))
    if (sh, sh) != tuple(size):
        key = (q, i, tuple(size))
        hit = _CLEAN_SC.get(key)
        if hit is None:
            hit = pygame.transform.smoothscale(fr, tuple(size))
            if len(_CLEAN_SC) > 64:
                _CLEAN_SC.clear()
            _CLEAN_SC[key] = hit
        return hit
    return fr


_CLEAN_SC = {}


def _hair_mask(sex, layer, tt, anim, facing, frame_idx, size):
    """The figure's own hair mask for this frame (bool, surfarray x/y order), or None."""
    q = os.path.join(_BASE, sex, tt, layer, f"{anim}_{facing}_hair.png")
    st = _img(q) if os.path.exists(q) else None
    if st is None:
        return None
    sh = st.get_height()
    i = max(0, min(int(frame_idx), st.get_width() // sh - 1))
    fr = st.subsurface((i * sh, 0, sh, sh))
    if (sh, sh) != tuple(size):
        fr = pygame.transform.smoothscale(fr, size)
    import numpy as np
    return pygame.surfarray.array_alpha(fr) > 90


def _clear_old_hair(out, sex, layer, tt, anim, facing, frame_idx, cut_y, tx, ty, hw, hh, orig_alpha=None, protect=None):
    """Old hair hanging below the new head (long hair on the shoulders / back, Tide gown, back-view
    armour): grown over from the figure pixels around it (cloth), or cleared where it stood out past
    the figure's outline. Only a band under the new head is touched. In place on out."""
    import numpy as np
    w, h = out.get_size()
    m = _hair_mask(sex, layer, tt, anim, facing, frame_idx, (w, h))
    if m is None:
        return
    x0, x1 = max(0, int(tx - hw * 0.95)), min(w, int(tx + hw * 0.95) + 1)
    y0, y1 = max(0, int(cut_y) - 1), min(h, int(ty + hh * 1.3))
    if x1 <= x0 or y1 <= y0:
        return
    band = np.zeros_like(m)
    band[x0:x1, y0:y1] = True
    al_all = pygame.surfarray.array_alpha(out)
    if orig_alpha is not None:
        # near-black backdrop baked into some action art behind the old head (a black panel between
        # raised arms): the erase takes most of it, the slivers it leaves against the arms are taken too.
        # Grown only through near-black pixels, from holes the erase made, above the chin.
        rgb0 = pygame.surfarray.array3d(out).astype(np.int16)
        blk = (rgb0.max(axis=2) < 30) & (al_all > 0)
        zone = np.zeros_like(blk)
        zy0 = max(0, int(ty - hh * 0.7))
        zone[max(0, int(tx - hw * 0.8)):min(w, int(tx + hw * 0.8) + 1), zy0:max(zy0, int(cut_y) + 1)] = True
        blk &= zone
        if protect is not None:
            blk &= ~protect             # a dark haft / limb kept across the erase is not a backdrop sliver
        if blk.any():
            seed = (al_all == 0) & (orig_alpha > 100) & zone
            reach_ = seed.copy()
            got = np.zeros_like(blk)
            for _ in range(max(6, int(h * 0.05))):
                g2 = reach_.copy()
                g2[1:] |= reach_[:-1]; g2[:-1] |= reach_[1:]; g2[:, 1:] |= reach_[:, :-1]; g2[:, :-1] |= reach_[:, 1:]
                new_ = g2 & blk & ~got
                if not new_.any():
                    break
                got |= new_
                reach_ = new_
            if got.sum() >= 3:
                pa_ = pygame.surfarray.pixels_alpha(out)
                pa_[got] = 0
                del pa_
                al_all = pygame.surfarray.array_alpha(out)
    tgt = m & band & (al_all > 0)
    if protect is not None:
        tgt &= ~protect
    if facing in ("e", "w") and orig_alpha is not None and anim in ("idle", "walk"):
        # side view: where the erase cut straight across the figure behind the neck (long hair down the
        # back, a high collar), what is left has a flat, hard top. Round it off into a shoulder: cut deeper
        # the further back from the neck, only in columns whose top edge the erase made.
        D = max(3, int(h * 0.028))
        side = -1 if facing == "e" else 1
        opq_ = al_all > 100
        rgbv = pygame.surfarray.array3d(out).astype(np.int16)
        dark = rgbv.max(axis=2) < 75
        depth = np.zeros(w, np.float32)
        tops = np.full(w, -1)
        for x in range(x0, x1):
            back = (x - tx) * side
            if back < h * 0.005:
                continue
            col = opq_[x, y0:y1]
            if not col.any():
                continue
            yt = y0 + int(np.argmax(col))
            if yt < 2 or orig_alpha[x, yt - 2] <= 100:   # a real outline, not an erase cut
                continue
            tops[x] = yt
            t_ = min(1.0, back / (h * 0.07))
            depth[x] = D * t_ * t_ * (3 - 2 * t_)      # smoothstep: a sloping shoulder, not a scoop
            # follow the figure's own contour: a dark fur / hood band left on top goes down to where
            # the lighter shoulder plate under it starts (within reach), so the new top edge is the
            # plate's own outline, not a ruler line
            reach_ = int(2.2 * D * t_)
            if reach_ >= 2:
                cc = dark[x, yt:min(h, yt + reach_ + 1)] & opq_[x, yt:min(h, yt + reach_ + 1)]
                nd = int(np.argmin(cc)) if not cc.all() else 0
                if nd > depth[x]:
                    depth[x] = float(nd)
        if depth.any():
            k_ = max(5, int(h * 0.02)) | 1
            pad_ = np.pad(depth, k_ // 2, mode="edge")
            med = np.array([np.median(pad_[i:i + k_]) for i in range(w)], np.float32)
            sm = np.convolve(med, np.ones(k_) / k_, mode="same")
            pa_ = pygame.surfarray.pixels_alpha(out)
            for x in np.where(tops >= 0)[0]:
                d = sm[x]
                if d < 0.5:
                    continue
                yt = tops[x]
                di = int(d)
                pa_[x, yt:yt + di] = 0
                # feathered rim: fades in over a few px instead of a hard step
                nfe = max(2, int(h * 0.01))
                fr_ = d - di
                for j in range(nfe):
                    yy = yt + di + j
                    if yy >= h:
                        break
                    f_ = min(1.0, (j + 1 - fr_) / (nfe + 1))
                    pa_[x, yy] = int(pa_[x, yy] * max(0.0, f_))
            del pa_
            al_all = pygame.surfarray.array_alpha(out)
            tgt &= al_all > 0
    if tgt.sum() < 3:
        return
    # grow the mask 1px so the strands' soft edges go too
    g = tgt.copy()
    g[1:] |= tgt[:-1]; g[:-1] |= tgt[1:]; g[:, 1:] |= tgt[:, :-1]; g[:, :-1] |= tgt[:, 1:]
    tgt = g & band
    xs, ys = np.where(tgt)
    pad = 6
    X0, X1 = max(0, xs.min() - pad), min(w, xs.max() + pad + 1)
    Y0, Y1 = max(0, ys.min() - pad), min(h, ys.max() + pad + 1)
    px = pygame.surfarray.pixels3d(out)
    pa = pygame.surfarray.pixels_alpha(out)
    rgb = px[X0:X1, Y0:Y1].astype(np.float32)
    al = pa[X0:X1, Y0:Y1].astype(np.float32)
    unk = tgt[X0:X1, Y0:Y1].copy()
    opq = (~unk) & (al > 100)
    clear = (~unk) & (al <= 100)
    # right under the new head's chin the strands stand for the neck: always grow cloth/skin there,
    # never see-through, so no gap opens between head and body
    neckz = np.zeros(unk.shape, bool)
    nz0, nz1 = max(0, int(cut_y) - 5 - Y0), max(0, int(cut_y + max(10, hh * 0.3)) - Y0)
    neckz[:, nz0:nz1] = True
    for _ in range(int(max(X1 - X0, Y1 - Y0))):
        if not unk.any():
            break
        so = np.zeros(unk.shape, np.float32); sc_ = np.zeros(unk.shape, np.float32)
        sr = np.zeros(rgb.shape, np.float32)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            o = np.roll(np.roll(opq, dx, 0), dy, 1)
            c = np.roll(np.roll(clear, dx, 0), dy, 1)
            so += o; sc_ += c
            sr += np.roll(np.roll(rgb * opq[..., None], dx, 0), dy, 1)
        front = unk & ((so + sc_) > 0)
        if not front.any():
            break
        fo = front & ((so >= sc_) | (neckz & (so > 0)))
        front &= ~(neckz & (so == 0))
        rgb[fo] = sr[fo] / np.maximum(so[fo], 1)[:, None]
        al[fo] = 255
        al[front & ~fo] = 0
        opq |= fo
        clear |= front & ~fo
        unk &= ~front
    # the grown cloth carries rows of smeared colour (streaks): diffuse it inside what was grown
    grown = tgt[X0:X1, Y0:Y1] & ~unk & (al > 100)
    if grown.sum() >= 6:
        wgt = (al > 100).astype(np.float32)
        for _ in range(max(6, int(h * 0.03))):
            acc = rgb * wgt[..., None]; ws = wgt.copy()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 2), (0, -2), (0, 3), (0, -3)):
                acc += np.roll(np.roll(rgb * wgt[..., None], dx, 0), dy, 1)
                ws += np.roll(np.roll(wgt, dx, 0), dy, 1)
            av = acc / np.maximum(ws, 1e-3)[..., None]
            rgb[grown] = av[grown]
    keep = unk & neckz          # nothing to grow from under the chin: keep the old strands, no hole
    al[unk & ~keep] = 0
    al[keep] = pa[X0:X1, Y0:Y1][keep]
    px[X0:X1, Y0:Y1] = np.clip(rgb, 0, 255).astype(np.uint8)
    pa[X0:X1, Y0:Y1] = np.clip(al, 0, 255).astype(np.uint8)
    del px, pa


def _rot(surf, ang, pivot, key):
    """surf tilted counter-clockwise by ang degrees, and where its pivot point lands in the result."""
    if not ang:
        return surf, pivot
    k = ("rot", key, round(ang, 1))
    hit = _CACHE.get(k)
    if hit is None:
        rs = pygame.transform.rotozoom(surf, ang, 1.0)
        v = pygame.math.Vector2(pivot[0] - surf.get_width() / 2.0, pivot[1] - surf.get_height() / 2.0).rotate(-ang)
        hit = _remember(k, (rs, (rs.get_width() / 2.0 + v.x, rs.get_height() / 2.0 + v.y)))
    return hit


_TRACK = None


_BLOB = {}


def _protect_limbs(full, frame, blob, h, skin_src=None, top_lim=None):
    """Action frames: the erase template sits where the idle head was, so a raised arm, a sleeve or a
    weapon held over the head can fall inside it. Whatever of the figure reaches into the erase from
    outside it, through pixels that are not the old head (not in its hair/skin blob, not hair-coloured,
    not a near-black backdrop), is kept. In place on full (the erase alpha)."""
    import numpy as np
    fa = pygame.surfarray.pixels_alpha(full)
    er_ = fa > 60
    if not er_.any():
        del fa
        return None
    rgbf = pygame.surfarray.array3d(frame).astype(np.int32)
    alf = pygame.surfarray.array_alpha(frame) > 100
    headm = (pygame.surfarray.array_alpha(blob) > 0) if blob is not None else np.zeros_like(er_)
    hk = headm & alf & (rgbf.max(2) > 30)
    ref = np.zeros(3)
    far = np.ones(er_.shape, bool)
    if hk.sum() > 20:
        ref = np.median(rgbf[hk], axis=0)
        far = np.abs(rgbf - ref).sum(2) >= 110
    r_, g_, b_ = rgbf[..., 0], rgbf[..., 1], rgbf[..., 2]
    skinish = (r_ > g_) & (g_ >= b_ - 5) & (r_ - b_ > 30) & (r_ > 90)
    # inside the head blob too: a blade over the hair (back view) is neither hair- nor skin-coloured
    # skin inside the blob is the old face only where the skin mask says so (a fist gripping a haft
    # in front of the hair is skin-coloured too, but in the hair mask, not the skin mask)
    facem = headm & skinish
    if skin_src is not None:
        sx_, ly_, tt_, an_, fc_, fi_ = skin_src
        q = os.path.join(_BASE, sx_, tt_, ly_, f"{an_}_{fc_}_skin.png")
        st = _img(q) if os.path.exists(q) else None
        if st is not None:
            sh_ = st.get_height()
            i_ = max(0, min(int(fi_), st.get_width() // sh_ - 1))
            fr_ = st.subsurface((i_ * sh_, 0, sh_, sh_))
            if (sh_, sh_) != er_.shape:
                fr_ = pygame.transform.smoothscale(fr_, er_.shape)
            sm_ = pygame.surfarray.array_alpha(fr_) > 60
            g_ = sm_.copy()
            for _ in range(3):
                g2 = g_.copy(); g2[1:] |= g_[:-1]; g2[:-1] |= g_[1:]; g2[:, 1:] |= g_[:, :-1]; g2[:, :-1] |= g_[:, 1:]; g_ = g2
            facem = headm & skinish & g_
    # a dark pixel is kept only when neutral (a black blade / haft); a dark warm one is the shadowed
    # rim of the old hair
    # outside the head blob a dark pixel is the black backdrop baked in between raised arms (its
    # slivers along the arms): only figure colours flood; a dark haft there is kept by the line /
    # rod tests below. Over the hair (back view) a black blade can only be told by not being hair.
    lum_ = rgbf.max(2)
    eo = er_ & alf
    backdrop = eo.any() and (eo & (lum_ < 12)).sum() > 0.12 * eo.sum()
    dk = (lum_ > 45) | (headm & (lum_ > 14)) if backdrop else (lum_ > 14)
    cand = er_ & alf & dk & far & ~facem
    reach = alf & ~er_
    got = np.zeros_like(cand)
    for _ in range(max(8, int(h * 0.2))):
        g = reach.copy()
        g[1:] |= reach[:-1]; g[:-1] |= reach[1:]; g[:, 1:] |= reach[:, :-1]; g[:, :-1] |= reach[:, 1:]
        new = g & cand & ~got
        if not new.any():
            break
        got |= new
        reach = new
    # a weapon haft passing straight across the erase (dark, so the flood above can't tell it from a
    # black backdrop, and often inside the blocky hair mask): a straight line that runs on through the
    # figure for a good length on both sides of the erase, in the same colour inside as outside, is kept
    w = er_.shape[0]
    xs_, ys_ = np.where(er_ & alf)
    if len(xs_):
        ex0, ex1, ey0, ey1 = xs_.min(), xs_.max(), ys_.min(), ys_.max()
        ext = max(5, int(h * 0.03))
        cx, cy = (ex0 + ex1) / 2.0, (ey0 + ey1) / 2.0
        half = (ex1 - ex0) / 2.0 + ext
        tt = np.linspace(-half, half, int(2 * half) + 1)
        lum = rgbf.max(2)
        acc = []
        for deg in range(-40, 41, 2):
            dx_, dy_ = np.cos(np.radians(deg)), np.sin(np.radians(deg))
            for off in np.arange(ey0 - cy - 2, ey1 - cy + 3, 1.0):
                px_ = np.round(cx + tt * dx_ - off * dy_ * 0).astype(int)
                py_ = np.round(cy + off + tt * dy_).astype(int)
                ok = (px_ >= 0) & (px_ < w) & (py_ >= 0) & (py_ < h)
                if not ok.all():
                    continue
                ins = er_[px_, py_]
                if ins.sum() < 6:
                    continue
                ii = np.where(ins)[0]
                left, right = np.arange(0, ii.min()), np.arange(ii.max() + 1, len(tt))
                if len(left) < ext * 0.8 or len(right) < ext * 0.8:
                    continue
                lo, ro = left[-ext:], right[:ext]
                if alf[px_[lo], py_[lo]].mean() < 0.95 or alf[px_[ro], py_[ro]].mean() < 0.95:
                    continue
                seg = np.arange(ii.min(), ii.max() + 1)
                if alf[px_[seg], py_[seg]].mean() < 0.95:
                    continue
                cl = np.median(rgbf[px_[lo], py_[lo]], 0); cr = np.median(rgbf[px_[ro], py_[ro]], 0)
                ci = np.median(rgbf[px_[seg], py_[seg]], 0)
                # the inside matches at least one side (the other may be the hand gripping it)
                if min(np.abs(ci - cl).sum(), np.abs(ci - cr).sum()) > 60:
                    continue
                # a black backdrop row between two dark strips is not a haft: the line must be the
                # figure's colour along its whole length, with no long run of pure black
                if (lum[px_[seg], py_[seg]] < 8).mean() > 0.3:
                    continue
                if hk.sum() > 20 and np.abs(ci - ref).sum() < 60 and ref.max() >= 60:
                    continue
                acc.append((deg, off, len(seg)))
        # lines found close together are one haft: its centre line, as thick as the haft is just
        # outside the erase on both sides (perpendicular opaque run, the thinner side, capped)
        acc.sort(key=lambda a: -a[2])
        used = []
        for deg, off, _n in acc:
            if any(abs(deg - d2) <= 6 and abs(off - o2) <= 5 for d2, o2 in used):
                continue
            grp = [(d2, o2) for d2, o2, _ in acc if abs(deg - d2) <= 6 and abs(off - o2) <= 5]
            dg = float(np.median([g[0] for g in grp])); of = float(np.median([g[1] for g in grp]))
            used.append((deg, off))
            dx_, dy_ = np.cos(np.radians(dg)), np.sin(np.radians(dg))
            nx_, ny_ = -dy_, dx_
            px_ = cx + tt * dx_; py_ = cy + of + tt * dy_
            ins = er_[np.clip(np.round(px_).astype(int), 0, w - 1), np.clip(np.round(py_).astype(int), 0, h - 1)]
            if not ins.any():
                continue
            ii = np.where(ins)[0]
            cxs = np.clip(np.round(px_).astype(int), 0, w - 1); cys = np.clip(np.round(py_).astype(int), 0, h - 1)
            cmed = np.median(rgbf[cxs[ii], cys[ii]], 0)
            th = []
            for idx in (max(0, ii.min() - 3), min(len(tt) - 1, ii.max() + 3)):
                run = []
                for sgn in (-1, 1):
                    k = 0
                    while k < int(h * 0.03):
                        qx = int(round(px_[idx] + sgn * (k + 1) * nx_)); qy = int(round(py_[idx] + sgn * (k + 1) * ny_))
                        if not (0 <= qx < w and 0 <= qy < h) or not alf[qx, qy]:
                            break
                        # the haft itself, not the black backdrop panel lying against it
                        if k >= max(1, int(h * 0.005)) and (np.abs(rgbf[qx, qy] - cmed).sum() > 75 or rgbf[qx, qy].max() < 10):
                            break
                        k += 1
                    run.append(k)
                th.append(run)
            up_ = min(th[0][0], th[1][0]); dn_ = min(th[0][1], th[1][1])
            up_ = min(up_, max(2, int(h * 0.012))); dn_ = min(dn_, max(2, int(h * 0.012)))
            X0, X1 = int(max(0, ex0 - 2)), int(min(w, ex1 + 3))
            Y0, Y1 = int(max(0, ey0 - 2)), int(min(h, ey1 + 3))
            gx, gy = np.mgrid[X0:X1, Y0:Y1]
            dd = (gx - cx) * nx_ + (gy - (cy + of)) * ny_
            band = (dd >= -up_ - 0.5) & (dd <= dn_ + 0.5) & alf[X0:X1, Y0:Y1] & er_[X0:X1, Y0:Y1]
            got[X0:X1, Y0:Y1] |= band
    # a thin straight rod in open air (a wooden haft the hair's colour, held up past the head): opaque
    # along a straight run of good length with clear background on both sides of it, kept whole
    if len(xs_):
        X0, X1 = int(max(0, ex0 - 2)), int(min(w, ex1 + 3))
        Y0, Y1 = int(max(0, ey0 - 2)), int(min(h, ey1 + 3))
        pad = int(h * 0.03) + 8
        A = np.zeros((X1 - X0 + 2 * pad, Y1 - Y0 + 2 * pad), bool)
        qx0, qy0 = max(0, X0 - pad), max(0, Y0 - pad)
        sub = alf[qx0:min(w, X1 + pad), qy0:min(h, Y1 + pad)]
        A[qx0 - (X0 - pad):qx0 - (X0 - pad) + sub.shape[0], qy0 - (Y0 - pad):qy0 - (Y0 - pad) + sub.shape[1]] = sub

        def sh_(M, ox, oy):
            return np.roll(np.roll(M, ox, 0), oy, 1)
        L = max(8, int(h * 0.05))
        rod = np.zeros_like(A)
        for deg in range(0, 180, 6):
            dx_, dy_ = np.cos(np.radians(deg)), np.sin(np.radians(deg))
            nx_, ny_ = -dy_, dx_
            for tw in (2, 3, 4):
                if tw > max(2, int(h * 0.012)):
                    break
                o1, o2 = int(round(nx_ * (tw + 2))), int(round(ny_ * (tw + 2)))
                thin = A & ~sh_(A, o1, o2) & ~sh_(A, -o1, -o2)
                run = thin.copy()
                for k in range(1, L):
                    run &= sh_(thin, int(round(-dx_ * k)), int(round(-dy_ * k)))
                if not run.any():
                    continue
                full_ = run.copy()
                for k in range(1, L):
                    full_ |= sh_(run, int(round(dx_ * k)), int(round(dy_ * k)))
                # carry the rod on a little past where it stops being thin (where it crosses the hair
                # or the hand), as long as the figure is opaque there
                E = max(4, int(h * 0.025))
                for k in range(1, E + 1):
                    full_ |= sh_(run, int(round(dx_ * (L - 1 + k))), int(round(dy_ * (L - 1 + k)))) & A
                    full_ |= sh_(run, int(round(-dx_ * k)), int(round(-dy_ * k))) & A
                for k in range(-tw, tw + 1):
                    rod |= sh_(full_, int(round(nx_ * k)), int(round(ny_ * k))) & A
        rod = rod[pad:pad + X1 - X0, pad:pad + Y1 - Y0]
        r2 = rod & er_[X0:X1, Y0:Y1] & ~skinish[X0:X1, Y0:Y1]
        if r2.sum() >= L:
            got[X0:X1, Y0:Y1] |= r2
    # above the figure's own crown the erase only meets what is held up there (a blade, a haft, a
    # raised sleeve): kept unless it is the hair's colour (the crown's shadowed rim)
    if top_lim is not None and top_lim > 0:
        up = np.zeros_like(got)
        up[:, :top_lim] = True
        got |= up & er_ & alf & (rgbf.max(2) > 40) & (np.abs(rgbf - ref).sum(2) >= 140 if hk.sum() > 20 else True) & ~facem
    if got.sum() >= 4:
        fa[got] = 0
    del fa
    return got


def _own_head(sex, layer, tt, anim, facing, frame_idx, size, erase_full, frame=None):
    """The figure's own head pixels (hair/skin mask blobs overlapping the placed erase), as a white
    alpha surface of the frame's size, dilated 1px; cached per frame. None without masks."""
    key = (sex, layer, tt, anim, facing, int(frame_idx), size)
    if key in _BLOB:
        return _BLOB[key]
    w, h = size
    pm = None
    for suf in ("_hair", "_skin"):
        q = os.path.join(_BASE, sex, tt, layer, f"{anim}_{facing}{suf}.png")
        if not os.path.exists(q):
            continue
        st = _img(q)
        if st is None:
            continue
        sh = st.get_height()
        i = max(0, min(int(frame_idx), st.get_width() // sh - 1))
        fr = st.subsurface((i * sh, 0, sh, sh))
        if (sh, sh) != (w, h):
            fr = pygame.transform.smoothscale(fr, (w, h))
        m = pygame.mask.from_surface(fr, 127)
        if pm is None:
            pm = m
        else:
            pm.draw(m, (0, 0))
    import numpy as np
    out = None
    if pm is not None:
        em = pygame.mask.from_surface(erase_full, 60)
        keep = pygame.mask.Mask((w, h))
        for c in pm.connected_components(12):
            if c.overlap_area(em, (0, 0)) >= max(4, c.count() // 5):
                keep.draw(c, (0, 0))
        if keep.count():
            out = keep.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
            ks = keep.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
            sc_ = w / 288.0
            # masks stop short of the hair's outer strands: grow 2px sideways and up to 7px upward
            for dx, dy in [(x, 0) for x in (-2, -1, 1, 2)] + [(x, -y) for y in range(1, 8) for x in (-1, 0, 1)]:
                out.blit(ks, (int(round(dx * sc_ * 1.5)), int(round(dy * sc_ * 1.5))))
            if frame is not None:
                # stray strands outside the masks: hair-coloured pixels around the blob go too
                rgb = pygame.surfarray.array3d(frame).astype(np.int32)
                al = pygame.surfarray.array_alpha(frame)
                hm = pygame.surfarray.array_alpha(ks) > 0
                hairish = hm & (al > 128) & (rgb.max(2) > 30)   # the hair itself, not a black backdrop in the mask
                if hairish.sum() > 20:
                    xs, ys = np.where(hm)
                    top = hairish & (np.arange(h)[None, :] < ys.min() + (ys.max() - ys.min()) // 4)
                    ref = np.median(rgb[top if top.sum() > 8 else hairish], axis=0)   # the hair, at the crown
                    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
                    pw, ph = int((x1 - x0) * 0.3) + 2, int((y1 - y0) * 0.6) + 3
                    X0, X1, Y0 = max(0, x0 - pw), min(w, x1 + pw + 1), max(0, y0 - ph)
                    Y1 = min(h, y0 + (y1 - y0) // 2)          # only the upper half: never the shoulders
                    sub = rgb[X0:X1, Y0:Y1]
                    near = (np.abs(sub - ref).sum(2) < 110) & (al[X0:X1, Y0:Y1] > 20)
                    if ref.max() >= 60:
                        # light hair: a near-black backdrop / weapon haft beside it is not a stray strand
                        near &= sub.max(2) > 45
                    oa = pygame.surfarray.pixels_alpha(out)
                    oa[X0:X1, Y0:Y1] = np.maximum(oa[X0:X1, Y0:Y1], near.astype(np.uint8) * 255)
                    del oa
    res = None
    if out is not None:
        ka = pygame.surfarray.array_alpha(keep.to_surface(setcolor=(255, 255, 255, 255),
                                                          unsetcolor=(0, 0, 0, 0))) > 0
        top = int(np.where(ka.any(0))[0].min())
        if frame is not None:
            # the masks often stop well short of the hair's crown: per column, whatever of the figure
            # runs on unbroken above the blob (up to 22px at 2x) is the rest of the head
            al = pygame.surfarray.array_alpha(frame) > 100
            # only hair-like pixels continue the run: a black backdrop between raised arms or an axe haft
            # held over the head is not the crown and must not be cut out with it
            rgbf = pygame.surfarray.array3d(frame).astype(np.int32)
            hk = ka & al
            if hk.sum() > 20:
                ref2 = np.median(rgbf[hk], axis=0)
                al &= (np.abs(rgbf - ref2).sum(2) < 150) & (rgbf.max(2) > 40)
            oa = pygame.surfarray.pixels_alpha(out)
            lim = int(round(22 * w / 288.0))
            tops = []
            for x in np.where(ka.any(1))[0]:
                y = int(np.where(ka[x])[0].min()) - 1
                n = 0
                while y >= 0 and n < lim and al[x, y]:
                    y -= 1
                    n += 1
                if n < lim:                      # a run that never ends is a weapon or arm: leave it
                    oa[x, y + 1:y + 1 + n + 1] = 255
                    tops.append(y + 1)
            del oa
            if tops:
                top = min(top, int(np.percentile(tops, 10)))
        res = (out, top)
    _BLOB[key] = res
    return res


def track(sex, layer, anim, facing, frame_idx):
    """[dx, dy, deg] of the figure's own head in this frame (2x px from idle frame 0), or None."""
    global _TRACK
    if _TRACK is None:
        try:
            with open(os.path.join(_DIR, "targets", "track.json")) as f:
                _TRACK = json.load(f)
        except (OSError, ValueError):
            _TRACK = {}
    lst = _TRACK.get(f"{'female' if sex == 'female' else 'male'}/{layer}/{anim}_{facing}")
    if not lst:
        return None
    i = max(0, min(int(frame_idx), len(lst) - 1))
    v = lst[i]
    if v and len(v) > 3:
        # a lone frame measured far bigger / smaller than the rest of its strip is a tracker miss
        # (a raised arm read as head): take the size from its neighbours instead
        ks = sorted(float(e[3]) for e in lst if e and len(e) > 3)
        med = ks[len(ks) // 2]
        if med > 0 and abs(float(v[3]) / med - 1.0) > 0.3:
            near = [lst[j] for j in (i - 1, i + 1)
                    if 0 <= j < len(lst) and lst[j] and len(lst[j]) > 3 and abs(float(lst[j][3]) / med - 1.0) <= 0.3]
            v = list(v)
            if near:  # the whole reading is suspect: place, tilt and size all from the neighbours
                for c in range(4):
                    v[c] = sum(float(e[c]) for e in near) / len(near)
            else:
                v[3] = med
    return v


def neck_line(sex, layer, facing, frame, anim, frame_idx, tag="2x"):
    """Neck y in this frame's pixels (for confining a figure's own hair mask), or None."""
    tgt_all = (meta().get("targets") or {}).get(f"{'female' if sex == 'female' else 'male'}/{layer}")
    tt = _pick(tgt_all or {}, tag)
    if not tt or facing not in tgt_all[tt]:
        return None
    kt = frame.get_width() / (288.0 * _MUL[tt])
    trk = track(sex, layer, anim, facing, frame_idx)
    if trk is not None:
        dy = trk[1] * _MUL[tt]
    else:
        off = _offset(sex, layer, anim, facing, frame_idx, frame, tgt_all[tt][facing], kt)
        dy = off[1] if off else 0.0
    return (tgt_all[tt][facing]["neck"][1] + dy) * kt


def confine_hair(hair_surf, neck_y, feather=3):
    """Zero a hair mask below the neck line: hair colour never reaches clothes."""
    if hair_surf is None or neck_y is None:
        return hair_surf
    import numpy as np
    out = hair_surf.copy()
    a = pygame.surfarray.pixels_alpha(out)
    h = a.shape[1]
    ys = np.arange(h, dtype=np.float32)
    ramp = np.clip((neck_y - ys) / float(max(1, feather)), 0.0, 1.0)
    a[...] = (a.astype(np.float32) * ramp[None, :]).astype(np.uint8)
    del a
    return out
