# HD monsters batch 2: Void Sanctum + Depths

Pipeline: Blender 4.2 Cycles, the same CC0 base body + FK rig as knights_hd / batch 1 (`src/mon_hd.py`). Designs are in `src/void_designs.py`.
Fixed sprite camera: 175.6 px/m at 4x, `sensor_fit HORIZONTAL`, feet on the ground, baked soft contact shadow, idle/walk/attack/hit/death × s/e/n/w.
Shared rigs: one humanoid FK rig for all 12. Shared builders: `_wraith` (shade, rift_wraith), `_ghoul` (crypt_ghoul, gallery_warden), `_imp` (void_imp, void_crawler), `_horror` (void_horror, nyxarath) and `_skel` (ossuary_keeper, drowned_dead, morvath).
Per-creature poses are additive offsets on the shared poses (ghoul/imp/horror hunch, crawler crouch). The game walk-cycle code is untouched.
Size is baked in (`meta.scale_baked`). Boss canvas: 1152×1024 (feet 576,968). Large canvas: 768×672 (colossus, horror). Ossuary keeper: 640×672.

Scores (honest, /10): see the final report. The table is filled in when the renders finish.
