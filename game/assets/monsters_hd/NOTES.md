# Mythoscape HD monsters batch 1: notes
Built in Blender 4.2 with Cycles, using the fixed sprite camera (175.6 px/m at 4x, sensor_fit HORIZONTAL, 30° ortho). Feet are anchored at meta feet_px and the soft contact shadow is baked in.
States follow the knights_hd format: idle 4, walk 8, attack 6 (impact f03 = 0.48 hitsplat), hit 3, death 6, each in s/e/n/w.

| id | build | honest score |
|---|---|---|
| guard | knights rig + steel half-plate, red tabard, bascinet | 8 |
| adamant_duelist | knights rig + adamant plate, great helm, cape | 8 |
| mythos_champion | knights rig + white/gold plate, winged pauldrons, crest helm | 8 |
| big_skeleton (key-dropper) | knights rig driving modelled bones (skull, ribs, spine, limbs), rusted horned helm, rune greatsword | 7.5 |
| giant | knights rig, base ×1.55 (2.7 m), hide/fur, spiked club; canvas 768×672 | 7.5 |
| giant_rat | metaball body, particle fur, quadruped FK rig, bare tail, whiskers | 8 |
| wolf | metaball body, particle fur (dark saddle), quadruped FK rig | 7.5 |
| outfitter_mae (npc_hd) | CC0 base, plum bodice, teal skirt, tape measure, pincushion, shears | 8 |

Combat values come from server/content.py @ 9fd76de5 and are unchanged.
Beasts' weapon_tip anchor = mouth.
Sources: /workspace/hd_monsters/src (mon_hd.py, qd_hd.py, mae_npc.py).
