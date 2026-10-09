"""Zip knights_hd (arcname root knights_hd/), each part <= 15 MB: docs part, then per knight a/b parts."""
import zipfile
from pathlib import Path
ROOT = Path("/workspace/knights_hd"); OUT = Path("/workspace"); MAX = 15 * 1024 * 1024; PREFIX = "knights_hd"
KEYS = ["knight", "shadow_knight", "knight_captain_vorn", "barrow_knight", "sir_aldric", "magma_knight"]


def files(rel):
    p = ROOT / rel
    return [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file())


def write(name, paths):
    zp = OUT / f"{PREFIX}_{name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in paths:
            z.write(f, arcname=f"knights_hd/{f.relative_to(ROOT)}")
    sz = zp.stat().st_size; print("wrote", zp, sz)
    if sz > MAX:
        raise SystemExit(f"OVERSIZED {zp}")
    return zp


def main():
    for old in OUT.glob(f"{PREFIX}_*.zip"):
        old.unlink()
    docs = sum((files(r) for r in ("KNIGHTS_HD_CURSOR_PROMPT.md", "NOTES_KNIGHTS_HD.md", "manifest.json", "previews", "src")), [])
    write("part0_docs", [f for f in docs if "__pycache__" not in f.parts])
    n = 1
    lim = int(MAX * 0.93)
    for k in KEYS:
        fs = files(f"assets/{k}")
        fs.sort(key=lambda f: (0 if "sprite_4x" not in f.parts else 1, str(f)))
        parts, cur, tot = [], [], 0
        for f in fs:
            sz = f.stat().st_size
            if cur and tot + sz > lim:
                parts.append(cur); cur, tot = [], 0
            cur.append(f); tot += sz
        if cur:
            parts.append(cur)
        for j, ch in enumerate(parts):
            write(f"part{n}_{k}_{chr(97 + j)}", ch)
        n += 1

if __name__ == "__main__":
    main()
