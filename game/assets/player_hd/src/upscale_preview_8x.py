#!/usr/bin/env python3
"""AI-upscale whole-figure idle portraits (s/e/n) from 4x → 8x for Outfitters / creator.

Uses Real-ESRGAN-ncnn-vulkan (x4plus @ scale 2) with gray composite + uncomposite so
transparency survives. Skin masks are nearest-neighbour ×2 so tint ratios stay aligned.

Requires: REALESRGAN_BIN env or /tmp/realesrgan-full/realesrgan-ncnn-vulkan
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "assets"
BIN = os.environ.get(
    "REALESRGAN_BIN",
    "/tmp/realesrgan-full/realesrgan-ncnn-vulkan",
)
MODELS = os.environ.get(
    "REALESRGAN_MODELS",
    str(Path(BIN).resolve().parent / "models"),
)
MODEL = os.environ.get("REALESRGAN_MODEL", "realesrgan-x4plus")
SCALE = 2
BG = np.array([120.0, 110.0, 100.0], dtype=np.float32)


def _hd_layers() -> list[tuple[str, str]]:
    cat = json.loads((ROOT / "catalogue.json").read_text())
    out: list[tuple[str, str]] = []
    seen = set()
    for it in cat.get("items") or []:
        hd = it.get("hd_art")
        sex = it.get("sex")
        if not hd or sex not in ("male", "female"):
            continue
        key = (sex, hd)
        if key not in seen:
            seen.add(key)
            out.append(key)
    for e in cat.get("collection") or []:
        hd = e.get("hd_art")
        sex = e.get("sex")
        if not hd or sex not in ("male", "female"):
            continue
        key = (sex, hd)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return sorted(out)


def _esrgan(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [BIN, "-i", str(src), "-o", str(dst), "-n", MODEL, "-s", str(SCALE), "-m", MODELS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def upscale_rgba(src: Path, dst: Path, work: Path) -> None:
    im = Image.open(src).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3:4] / 255.0
    comp = (rgb * a + BG * (1.0 - a)).clip(0, 255).astype(np.uint8)
    alpha_u8 = arr[:, :, 3].astype(np.uint8)
    work.mkdir(parents=True, exist_ok=True)
    cpath, apath = work / "comp.png", work / "alpha.png"
    cup, aup = work / "comp_up.png", work / "alpha_up.png"
    Image.fromarray(comp).save(cpath)
    Image.fromarray(alpha_u8, "L").save(apath)
    _esrgan(cpath, cup)
    _esrgan(apath, aup)
    c_up = np.array(Image.open(cup).convert("RGB")).astype(np.float32)
    a_im = Image.open(aup).convert("L")
    if a_im.size != (c_up.shape[1], c_up.shape[0]):
        a_im = a_im.resize((c_up.shape[1], c_up.shape[0]), Image.LANCZOS)
    au = np.array(a_im).astype(np.float32) / 255.0
    au = np.where(au < 0.04, 0.0, au)
    au = np.where(au > 0.96, 1.0, au)
    au3 = np.maximum(au[..., None], 1e-4)
    rgb_out = np.clip((c_up - BG * (1.0 - au3)) / au3, 0, 255)
    rgb_out = rgb_out * (au3 > 0.04)
    out = np.dstack([rgb_out, au * 255]).astype(np.uint8)
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(dst)


def upscale_skin_nearest(src: Path, dst: Path) -> None:
    """Placeholder: skins are rebuilt after AI art so the mask matches the new silhouette."""
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    out = im.resize((w * SCALE, h * SCALE), Image.NEAREST)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)


def upscale_soft(src: Path, dst: Path) -> None:
    """Lanczos ×2 for soft layers (shadow) — no ESRGAN needed."""
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    out = im.resize((w * SCALE, h * SCALE), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)


def process_layer(sex: str, layer: str, work_root: Path, force: bool = False) -> tuple[int, int]:
    src_dir = ROOT / sex / "4x" / layer
    dst_dir = ROOT / sex / "8x" / layer
    if not src_dir.is_dir():
        print(f"  skip missing {sex}/4x/{layer}")
        return 0, 0
    done = skipped = 0
    for name in sorted(src_dir.iterdir()):
        if not name.name.startswith("idle_") or name.suffix.lower() != ".png":
            continue
        if "_tint" in name.name or "_skin" in name.name:
            # skins rebuilt after AI art (nearest prior ≠ AI silhouette)
            continue
        dst = dst_dir / name.name
        if dst.exists() and not force and dst.stat().st_size > 1000:
            skipped += 1
            continue
        work = work_root / f"{sex}_{layer}_{name.stem}"
        print(f"  {sex}/8x/{layer}/{name.name} ...", flush=True)
        upscale_rgba(name, dst, work)
        done += 1
    return done, skipped


def ensure_shadow(sex: str) -> None:
    src_dir = ROOT / sex / "4x" / "shadow"
    dst_dir = ROOT / sex / "8x" / "shadow"
    if not src_dir.is_dir():
        return
    for name in src_dir.iterdir():
        if not name.name.startswith("idle_") or name.suffix.lower() != ".png":
            continue
        dst = dst_dir / name.name
        if dst.exists():
            continue
        print(f"  {sex}/8x/shadow/{name.name} (lanczos)", flush=True)
        upscale_soft(name, dst)


def main() -> int:
    if not Path(BIN).is_file():
        print(f"Real-ESRGAN binary not found: {BIN}", file=sys.stderr)
        return 1
    force = "--force" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    layers = _hd_layers()
    if only:
        layers = [(s, l) for s, l in layers if l in only or f"{s}/{l}" in only]
    work_root = Path("/tmp/preview_8x_work")
    work_root.mkdir(parents=True, exist_ok=True)
    total_d = total_s = 0
    print(f"Upscaling {len(layers)} HD outfit layers → 8x (model={MODEL})")
    for sex, layer in layers:
        d, s = process_layer(sex, layer, work_root, force=force)
        total_d += d
        total_s += s
    for sex in ("male", "female"):
        ensure_shadow(sex)
    print(f"Done. wrote={total_d} skipped={total_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
