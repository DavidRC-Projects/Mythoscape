"""Jewellery overlays + Crown Jewels sparkle for HD whole-figure players (JEWELLERY_SPEC.md).

draw(dest, frame_surf, frame_rect, layer_dir, anim, facing, frame_idx, flip, look, ctx)
  frame_surf/frame_rect: the scaled figure frame exactly as blitted (rect on dest).
  layer_dir: the figure layer's asset dir at the scale tag in use (holds jw_anchors.json).
Pieces sit on per-frame anchors, are clipped to the face_box (never shifted) and to the figure silhouette,
get a 1 px contact shadow, are never tinted, and are drawn wrist -> hand -> neck -> chest -> ears -> head.
"""
import json, math, os, random
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "player_hd", "assets", "jewellery"))
ORDER = {"wrist": 0, "hand": 1, "neck": 2, "neck+ears": 2, "chest": 3, "ears": 4, "head_back": 5, "head_top": 6}
GEM = {"diamond": (232, 244, 255), "ruby": (255, 106, 122), "emerald": (106, 255, 176), "sapphire": (122, 168, 255), "lilac": (226, 200, 255)}
GLOW_TIERS = ("mithril", "adamant", "dragon", "eclipse")
_items = None; _img = {}; _anc = {}; _scaled = {}

def items():
    global _items
    if _items is None:
        try: _items = {e["id"]: e for e in json.load(open(os.path.join(ROOT, "jewellery.json")))["jewellery"]}
        except (OSError, ValueError): _items = {}
    return _items

def item(pid): return items().get(pid)

def card_path(pid): return os.path.join(ROOT, "cards", pid + ".png")

def _anchors(layer_dir):
    if layer_dir not in _anc:
        try: _anc[layer_dir] = json.load(open(os.path.join(layer_dir, "jw_anchors.json")))
        except (OSError, ValueError): _anc[layer_dir] = {}
    return _anc[layer_dir]

def anchor(layer_dir, anim, facing, frame_idx):
    a = _anchors(layer_dir)
    key = f"{anim}_{facing}"
    if key not in a: key = f"idle_{facing}"       # actions: fall back to the idle pose anchors (necklaces etc. barely move)
    fr = a.get(key) or []
    return fr[frame_idx % len(fr)] if fr else None

def _sprite(pid, part, view, u, w60, h60):
    k = 2 if u <= 2.5 else 4 if u <= 5 else 8
    key = (pid, part, view, k)
    if key not in _img:
        p = os.path.join(ROOT, f"{k}x", pid, f"{part + '_' if part else ''}{view}.png")
        _img[key] = pygame.image.load(p).convert_alpha() if os.path.exists(p) and pygame.display.get_init() and pygame.display.get_surface() else (pygame.image.load(p) if os.path.exists(p) else None)
    return _img[key], k

def _scaled_sprite(pid, part, view, u, w60, h60, sx=1.0, fit_w=None, bright=False):
    base, k = _sprite(pid, part, view, u, w60, h60)
    if base is None: return None
    r = u / k
    W, H = base.get_width() * r * sx, base.get_height() * r
    if fit_w: s = fit_w / max(1, base.get_width() * r); W, H = W * s, H * s
    key = (pid, part, view, round(W), round(H), bright)
    if key not in _scaled:
        s = pygame.transform.smoothscale(base, (max(1, round(W)), max(1, round(H))))
        if bright:
            s = s.copy(); s.fill((70, 60, 40, 0), special_flags=pygame.BLEND_RGBA_ADD)
        _scaled[key] = s
    return _scaled[key]

# --- clash rules -------------------------------------------------------------------------
def hidden_reason(pid, flags=None, equipment=None, facing="s", hood_up=False):
    """None when the piece shows; else a short UI reason. flags: painted.* flags of the worn set."""
    it = item(pid); flags = flags or {}; eq = equipment or {}
    if not it: return "Unknown"
    an = it["anchor"]
    helmet = bool(eq.get("head")); plate = bool(eq.get("body")); gloves = bool(eq.get("hands"))
    if an in ("neck", "neck+ears"):
        if flags.get("neck"): return "Your outfit has a painted necklace" + (" (try just the ring)" if an == "neck+ears" else "")
        if plate: return "Hidden by platebody"
        if flags.get("collar") and facing in ("e", "n"): return "Hidden by collar"
    if an in ("ears",) or (an == "neck+ears" and False):
        if helmet: return "Hidden by helmet"
        if hood_up: return "Hidden by hood"
        if flags.get("hair_covers_ears"): return "Hidden by hair"
    if an == "wrist":
        if plate or gloves: return "Hidden by armour"
        if flags.get("sleeves_long"): return "Hidden by long sleeves"
    if an == "hand" and gloves: return "Hidden by gloves"
    if an == "chest":
        if plate: return "Hidden by platebody"
        if flags.get("clasp"): return "Your cloak has a painted clasp"
    if an == "head_back":
        if flags.get("head"): return "Your outfit has a painted crown"
        if helmet or hood_up: return "Hidden by helmet"
    if an == "head_top":
        if flags.get("head"): return "Your outfit has a painted crown"
        if helmet: return "Hidden by helmet"
    return None

def ears_hidden(flags, equipment, hood_up=False):
    return bool((equipment or {}).get("head")) or hood_up or bool((flags or {}).get("hair_covers_ears"))

# --- placement --------------------------------------------------------------------------------
def _placements(it, A, facing):
    an = it["anchor"]; u = A["u"]
    if an in ("neck", "neck+ears") and facing != "n":
        p = A["neck"] if facing == "s" else [A["neck"][0] + 2.6 * u, A["neck"][1] - 0.5 * u]
        yield ("neck" if an == "neck+ears" else None, p, "top", it["size60"], "neck")
    if an in ("ears", "neck+ears"):
        sz = [1, 3] if an == "neck+ears" else it["size60"]
        for p in ([A["ear_r"]] if facing == "e" else [A["ear_l"], A["ear_r"]]):
            # Hook at the lobe point (no +u — that dropped earrings beside/below the head).
            yield ("ear" if an == "neck+ears" else None, [p[0], p[1]], "top", sz, "ears")
    if an == "wrist" and facing != "n":
        yield (None, [A["hand_l"][0], A["hand_l"][1] - 2 * u], "center", it["size60"], "wrist")
    if an == "hand" and facing != "n":
        yield (None, [A["hand_r"][0] + u, A["hand_r"][1] + 0.6 * u], "center", it["size60"], "hand")
    if an == "head_back" and facing != "s":
        hb = A["head_back"]; yield (None, hb if facing == "n" else [hb[0] - 3 * u, hb[1] + 2 * u], "center", it["size60"], "head_back")
    if an == "chest" and facing != "n":
        yield (None, A["chest"], "center", it["size60"], "chest")
    if an == "head_top":
        yield (None, [A["head_top"][0] + (u if facing == "e" else 0), A["head_top"][1] + 4.5 * u], "bottom", it["size60"], "head_top")

def _sparkle_mode(ctx):
    ctx = ctx or {}
    if ctx.get("preview"): return "full"
    if ctx.get("armour_glow"): return "off"
    try:
        import outfit_fx
        m = outfit_fx.state.get("mode", "full")
        if m == "off": return "off"
        if m == "reduced" or outfit_fx.state.get("crowd", 0) > 8 or outfit_fx.state.get("in_combat"): m = "reduced"
    except Exception:
        m = "full"
    if ctx.get("elemental_full") and m == "full": m = "reduced"   # don't fight elemental fx
    return m

def pieces_for(look, which="jewellery"):
    ids = list(look.get("jewellery") or [])
    if look.get("head") and item(look.get("head")): ids.append(look["head"])  # tiara in Headwear slot
    return [i for i in ids if item(i)]

def draw(dest, frame_surf, frame_rect, layer_dir, anim, facing, frame_idx, flip, look, ctx=None, which="all"):
    """which: 'jewellery' (under cloak_front/fx_front), 'head' (tiara + its sparkle, above headwear) or 'all'."""
    ctx = ctx or {}
    A = anchor(layer_dir, anim, facing, frame_idx)
    if not A: return 0
    ids = pieces_for(look)
    if not ids: return 0
    fw = frame_surf.get_width(); src = _anchors(layer_dir).get("_frame", fw)
    S = fw / float(src) if src else 1.0   # anchors are in source-frame px; frame_surf may be scaled
    def X(x): return frame_rect.x + ((src - x) if flip else x) * S
    def Y(y): return frame_rect.y + y * S
    u = A["u"] * S
    fb = A["face_box"]; pad = 2 * A["u"]
    body = pygame.mask.from_surface(frame_surf, 60)
    drawn = 0; sparks = []
    for pid in sorted(ids, key=lambda i: ORDER.get(item(i)["anchor"], 9)):
        it = item(pid)
        if hidden_reason(pid, ctx.get("flags"), ctx.get("equipment"), facing, ctx.get("hood_up")): continue
        is_head = it["anchor"] == "head_top"
        if which == "jewellery" and is_head: continue
        if which == "head" and not is_head: continue
        for part, p, align, sz, kind in _placements(it, A, facing):
            if kind == "ears" and ears_hidden(ctx.get("flags"), ctx.get("equipment"), ctx.get("hood_up")): continue
            view = facing
            if kind == "neck" and facing == "e":
                sp = _scaled_sprite(pid, part, "s", u, *sz, sx=0.42); view = "s"
            elif kind == "head_top":
                hw = (fb[2] - fb[0]) * S * (1.05 * 0.75 if facing == "e" else 1.05)
                sp = _scaled_sprite(pid, part, "s" if facing == "e" else facing, u, *sz, fit_w=hw, bright=True)
                view = "s" if facing == "e" else facing
            else:
                sp = _scaled_sprite(pid, part, view, u, *sz)
            if sp is None: continue
            if flip: sp = pygame.transform.flip(sp, True, False)
            w, h = sp.get_size()
            x = round(X(p[0]) - w / 2); y = round(Y(p[1]) - (0 if align == "top" else h if align == "bottom" else h / 2))
            piece = sp.copy()
            # face rule: clip (never shift). Earrings sit on the lobe point outside the box; N has no face.
            if kind not in ("ears",) and facing != "n":
                fx0 = (min(X(fb[0] - pad), X(fb[2] + pad))) - x; fx1 = (max(X(fb[0] - pad), X(fb[2] + pad))) - x
                fy0 = (Y(fb[1] + A["u"]) if kind == "head_top" else Y(fb[1] - pad)) - y; fy1 = Y(fb[3]) - y
                r = pygame.Rect(round(fx0), round(fy0), round(fx1 - fx0), round(fy1 - fy0)).clip(piece.get_rect())
                if r.w > 0 and r.h > 0: piece.fill((0, 0, 0, 0), r)
            if kind in ("neck", "chest", "wrist", "hand"):  # stay on the body silhouette
                m = body.overlap_mask(pygame.mask.Mask((w, h), fill=True), (x - frame_rect.x, y - frame_rect.y))
                cut = pygame.mask.Mask((w, h)); cut.draw(m, (frame_rect.x - x, frame_rect.y - y))
                keep = cut.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
                piece.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            shadow = piece.copy(); shadow.fill((20, 12, 6, 115), special_flags=pygame.BLEND_RGBA_MULT)
            dest.blit(shadow, (x, y + max(1, round(S)))); dest.blit(piece, (x, y)); drawn += 1
            if it.get("fx"):
                pts = (it.get("sparkle_points_ear") if part == "ear" else it.get("sparkle_points")) or {}
                for q in pts.get(view, []):
                    qx = (1 - q[0]) if flip else q[0]
                    sparks.append((x + qx * w, y + q[1] * h, it["fx"].get("gem", "diamond")))
    if sparks:
        _draw_sparkle(dest, sparks, ctx, u, (X(fb[0] - pad), Y(fb[1] - pad), X(fb[2] + pad), Y(fb[3])) if facing != "n" else None)
    return drawn

def _draw_sparkle(dest, sparks, ctx, u, face):
    mode = _sparkle_mode(ctx)
    if mode == "off": return
    sparks = sparks[:10]
    if mode == "reduced": sparks = sparks[:2]
    t = ctx.get("t", pygame.time.get_ticks() / 1000.0)
    fr = int(t / 1.8 * 12) % 12
    if mode == "reduced": fr -= fr % 2
    rng = random.Random(ctx.get("player_id", 1)); n = len(sparks); lit = []
    for i, (sx, sy, gem) in enumerate(sparks):
        ph = (fr - int(i * 12 / n) - rng.randint(-2, 2)) % 12
        if ph < 4: lit.append((abs(ph - 1.5), sx, sy, gem, ph))
    lit.sort()
    for _, sx, sy, gem, ph in lit[:2]:   # never more than 2 lit
        if face:
            fx0, fy0, fx1, fy1 = min(face[0], face[2]), face[1], max(face[0], face[2]), face[3]
            if fx0 - 2 < sx < fx1 + 2 and fy0 - 2 < sy < fy1 + 2: continue   # dropped, never moved
        s = (0.35, 1.0, 1.0, 0.35)[ph]; L = max(1.5, 1.4 * u * s); al = int(255 * 0.85 * (0.4 if mode == "reduced" else 1))
        c = tuple(int(255 * 0.7 + v * 0.3) for v in GEM.get(gem, GEM["diamond"]))
        size = int(L * 2 + 5); g = pygame.Surface((size, size), pygame.SRCALPHA); o = size / 2
        rot = math.radians(15 * (ph - 1.5) / 1.5)
        for ang, ln, a in ((0, L, al), (math.pi / 2, L, al), (math.pi / 4, L * 0.45, al // 2), (-math.pi / 4, L * 0.45, al // 2)):
            dx, dy = math.cos(ang + rot) * ln, math.sin(ang + rot) * ln
            pygame.draw.line(g, (*c, a), (o - dx, o - dy), (o + dx, o + dy), 1)
        pygame.draw.circle(g, (255, 255, 255, al), (o, o), max(1, round(L * 0.3)))
        dest.blit(g, (round(sx - o), round(sy - o)), special_flags=pygame.BLEND_RGBA_ADD)
