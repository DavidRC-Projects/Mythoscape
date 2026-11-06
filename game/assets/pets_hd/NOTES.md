# HD pets: Cat + White Husky

Pipeline: Blender 4.2 Cycles, LIGHT settings (2x / 16 spp + OIDN → Lanczos 4x).
- `pet_husky`: `src/qd_pet.py` (wolf rig clone, sc=0.78, white/grey markings, blue eyes, curled sickle tail, collar).
- `pet_cat`: `src/cat_hd.py` (new small feline metaball + FK rig, tabby, amber eyes, red collar + bell). Shoulder ~0.28 m.
Animations: idle 4, walk 8, attack 6 (pounce/bite, impact f03 @ 0.48), hit 3, death 6 × s/e/n/w.
`pet_husky` in-game uses painted stills for idle/attack; walk plays `painted/walk/{n,e,s,w}/f00..f07.png`
(baked from the painted bases — see `mmorpg/tools/bake_husky_walk.py`) so the dog trots in all four directions.
Honest score bar: 9/10 (walk).
Server: PETS keys `cat` / `husky`, sprites `pet_cat` / `pet_husky`. Pets already attack monsters the player has engaged (`process_pets` + `pet_hits_monster`).
