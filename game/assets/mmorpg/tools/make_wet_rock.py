"""Build assets/village_ground/wet_rock_world.jpg: a tileable dark wet-rock texture
for water that meets a cliff or wall (castle moat against the mountain)."""
import os
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "..", "assets", "village_ground")


def tile_noise(n, radius, seed):
    """Tileable smooth noise in 0..1 (blur a 3x3 wrapped copy, keep the centre)."""
    rng = np.random.default_rng(seed)
    a = Image.fromarray((rng.random((n, n)) * 255).astype(np.uint8))
    big = Image.new("L", (n * 3, n * 3))
    for i in range(3):
        for j in range(3):
            big.paste(a, (i * n, j * n))
    big = big.filter(ImageFilter.GaussianBlur(radius)).crop((n, n, 2 * n, 2 * n))
    v = np.asarray(big, np.float32).ravel() + rng.random(n * n) * 0.999
    r = np.empty_like(v)
    r[np.argsort(v, kind="stable")] = np.linspace(0, 1, v.size)
    return r.reshape(n, n)


def main():
    base = Image.open(os.path.join(DIR, "dirt_world.jpg")).convert("RGB")
    n = base.size[0]
    d = np.asarray(base, np.float32) / 255.0
    lum = d.mean(axis=2)
    nz = sum(tile_noise(n, r, s) * w for r, s, w in ((90, 1, .5), (30, 2, .3), (8, 3, .2)))
    ridge = 1 - np.abs(tile_noise(n, 22, 5) - .5) * 2
    v = 0.10 + 0.22 * nz + 0.10 * ridge ** 4
    rgb = np.stack([v * 1.0, v * 0.98, v * 0.95], axis=2)
    spec = np.clip((tile_noise(n, 6, 11) - .62) * 3.0, 0, 1) * np.clip(nz - .45, 0, 1) * .5
    rgb = np.clip(rgb + spec[..., None] * np.array([.75, .85, .95]), 0, 1)
    im = Image.fromarray((rgb * 255).astype(np.uint8)).filter(ImageFilter.SMOOTH)
    im.save(os.path.join(DIR, "wet_rock_world.jpg"), quality=90)
    print("wrote", n, "px")


if __name__ == "__main__":
    main()
