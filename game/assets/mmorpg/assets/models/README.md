# Models (Blender → BAM)

Offline asset pipeline for Panda3D `.bam` models. Not used by the live pygame client.

## Layout

| Path | Purpose |
|------|---------|
| `src/*.blend` | Authoring sources (Blender) |
| `*.bam` | Converted runtime models (output of `tools/convert_models.py`) |

## Workflow

1. Install Blender and put `blender` on your PATH.
2. From `game/assets/mmorpg` with the project venv active:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Save Blender files into `assets/models/src/`.
4. Convert:
   ```bash
   python tools/convert_models.py
   ```

`blend2bam` shells out to Blender; conversion will fail if Blender is missing.

## Blender version notes

`panda3d-blend2bam==0.26.0` is tested with **Blender 4.2**. On **Blender 5.x**, stock
blend2bam hits `TypeError: bpy_struct: this type doesn't support IDProperties` in
`exportgltf.py` when checking `allow_embedded_format`.

`tools/convert_models.py` auto-runs `tools/patch_blend2bam_blender5.py` before
converting (safe to re-run after `pip install`). Prefer Blender 4.2 LTS until
upstream ships a fix.

`convert_models.py` passes `-m legacy` so materials stay flat/non-PBR.
