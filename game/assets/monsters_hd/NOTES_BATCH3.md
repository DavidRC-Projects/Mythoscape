# HD monsters batch 3: Emberdeep

Pipeline: Blender 4.2 Cycles, LIGHT settings (2x canvas / 16 spp + adaptive OIDN → Lanczos+unsharp to 4x via `src/upscale_mon4x.py`).
- `ash_imp`, `crucible_beast`: `src/mon_hd.py` + `src/ember_designs.py` (ash_imp from `_imp`, crucible_beast colossus-style lava golem).
- `ember_wolf`: `src/qd_hd.py` wolf rig clone (charred fur + ember glow).
- `magma_slug`: `src/magma_slug_hd.py` legless metaball body, **≤ 0.45 m (knee height)** — deliberately small.

Fixed sprite camera: 175.6 px/m at 4x. Drivers: `src/lane4.sh` / `src/finish4.sh` → `V4 PACKAGED`.
Honest score bar: 8/10 (same as batch 2 light keys). Re-render anything that reads below 8.
