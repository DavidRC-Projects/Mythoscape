"""Mock of the client-side Eclipse worn effect (aura + twinkling gold sparkles). Mirrors what the pygame client
will do per frame: aura = blurred dilated sprite alpha, gold, low alpha, drawn BEHIND the sprite; sparkles = few tiny
4-point stars on a drifting orbit around the body, twinkle by sin(phase), drawn in front but never over the face/grille box."""
import math, random
from PIL import Image, ImageFilter, ImageDraw
GOLD = (255, 190, 70)

def aura(sprite, px):   # sprite at device px; px = device pixels per logical tile/40
    a = sprite.getchannel("A").point(lambda v: 255 if v > 170 else 0)
    a = a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(max(2.5, 4 * px)))
    a = a.point(lambda v: int(v * 0.62))
    g = Image.new("RGBA", sprite.size, GOLD + (0,)); g.putalpha(a)
    return g

def sparkles(size, bbox, t, px, n=10, seed=11, face=None):
    lay = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = bbox; cx, w, h = (x0 + x1) / 2, (x1 - x0), (y1 - y0)
    rnd = random.Random(seed)
    for i in range(n):
        ph = rnd.random() * 6.283; sp = 0.6 + rnd.random() * 0.6
        life = (t * 0.25 * sp + rnd.random()) % 1.0              # drift upward over its life, then respawn
        ang = ph + t * 0.9 * sp
        x = cx + math.cos(ang) * w * (0.45 + 0.15 * rnd.random())
        y = y1 - h * (0.15 + 0.8 * ((rnd.random() + life * 0.35) % 1.0))
        if face and face[0] < x < face[2] and face[1] < y < face[3]:
            continue                                              # never over the grille
        tw = max(0.0, math.sin(math.pi * life)) * (0.6 + 0.4 * math.sin(t * 7 + ph))
        if tw < 0.15: continue
        r = max(2.5, 3.6 * px) * (0.6 + 0.6 * tw); al = int(235 * tw)
        d.line((x - r, y, x + r, y), fill=GOLD + (al,), width=2 if px > 1.2 else 1); d.line((x, y - r, x, y + r), fill=GOLD + (al,), width=2 if px > 1.2 else 1)
        d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 245, 210, al))
    return lay

def apply(dev, t, px):
    """dev: RGBA sprite in device px. Returns sprite with aura behind + sparkles."""
    bb = dev.getchannel("A").point(lambda v: 255 if v > 170 else 0).getbbox()
    out = Image.new("RGBA", dev.size, (0, 0, 0, 0))
    if not bb: return dev
    out.alpha_composite(aura(dev, px)); out.alpha_composite(dev)
    hh = bb[3] - bb[1]; ww = bb[2] - bb[0]
    face = (bb[0] + ww * 0.25, bb[1] + hh * 0.04, bb[2] - ww * 0.25, bb[1] + hh * 0.20)
    out.alpha_composite(sparkles(dev.size, bb, t, px, face=face))
    return out
