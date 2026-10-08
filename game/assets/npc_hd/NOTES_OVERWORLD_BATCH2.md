# Overworld HD NPC pack Batch 2 (Village Life) — NOTES

Built on the box under `/workspace/npc_hd_overworld/batch2/` (2026-10-06 BST). Reuses batch1 pipeline patterns (`ow_npc.py`, assemble, package, run_parallel) and Fairy Village quality bar: CC0 Blender Human Base Meshes + Cycles / sprite pipeline.

## Characters

| id | sex | read | notes |
|----|-----|------|-------|
| wizard_elowen | F | Indigo/violet mage robes, pointed hat, auburn hair, violet teleport staff | **Not** fairy Lady Elowen Moonwhisper (no wings, no silver hair, no moon tiara) |
| guard_marcus | M | Dark leather/mail, nasal helm, spear, dark hair + stubble | Village north guard |
| guard_aldric | M | Lighter leather + mail shoulders, open face, sandy beard, sword | Village south guard — distinct face/kit from Marcus |
| village_kid_timmy | M | Child scale (~0.58), blue tunic, shorts, toy ball | Smaller than adults at constant 175.6 px/m |
| village_idiot_bob | M | Mustard tunic, blue sleeve, green patch, purple-grey pants, stick | Loud mismatched oddball silhouette |
| priest_cedric | M | Cream robes, burgundy stole, gold cross, white hair/beard, prayer book | Gentle older priest |
| monk_healer | M | Brown habit, hood capelet, rope cintura, tonsure ring, herb pouch | Monk Alaric healer look |
| pet_keeper_luna | F | Teal dress, leather apron, paw-print badge, treat pouches, ponytail | **Replaces missing `packer_nell`** (absent from content.py) |

**Not in this pack:** fairies, King court, batch1 village-core ids.

## Spawns

`json/overworld_batch2_spawns.json` lists id, name, sex, role. **World xy stay as in `content.py` — do not move tiles.** Swap art only / HD blit path.

## Honest quality scores (vs commercial fantasy NPCs)

Target ≥ 8/10. Reviewed on hero + portrait + 1x/4x south idle after assemble.

| character | hero score | 40px sprite readability | notes |
|-----------|------------|-------------------------|-------|
| wizard_elowen | 8.5/10 | 8.5/10 | Pointed hat + violet staff read immediately; clearly not fairy Elowen |
| guard_marcus | 8.5/10 | 8.5/10 | Helm + spear + mail silhouette strong |
| guard_aldric | 8/10 | 8/10 | Sword + open face + sandy beard distinct from Marcus |
| village_kid_timmy | 8/10 | 8/10 | Scale + ball + blue tunic; child read clear |
| village_idiot_bob | 8/10 | 8/10 | Color mismatch + patch + stick read oddball |
| priest_cedric | 8.5/10 | 8/10 | Cream + red stole + book; gentle elder priest |
| monk_healer | 8/10 | 8/10 | Brown habit + herb pouch + tonsure ring; one fix pass (tonsure Y-radius bug → visible horseshoe) |
| pet_keeper_luna | 8.5/10 | 8/10 | Teal + apron + paw badge; pet-shop clear |

**Pass vs bar:** all eight ≥ 8/10 after targeted fix re-render for monk_healer tonsure. Minor caveats only (prop scale at 1x for cross/whistle; idle breath not walk).

## Deliverables

- `assets/npcs/<id>/` — hero, portrait, sprites 1x/2x/4x, meta.json
- `json/overworld_batch2_spawns.json`, `manifest.json` (`feature_flag: null`)
- `previews/overworld_batch2_contact_sheet.png`
- `OVERWORLD_NPCS_BATCH2_CURSOR_PROMPT.md` (Step 1 investigate-only then STOP; permanent; protected walk files)
- `NOTES_OVERWORLD_BATCH2.md` (this file — do not overwrite King NOTES.md)
- Zip via Python zipfile: `npc_hd_overworld_batch2_part*.zip`, arcname root **`npc_hd/`**

## Caveats

- Sprite NPCs only — do not touch walk-cycle code.
- Idle animation is breath + prop sway (8 frames), not a skeletal walk.
- Parent agent delivers to David's Mac; this box never CopyFromBox'd the pack.
- `packer_nell` not in content.py → `pet_keeper_luna` used.

## Integration rules (David)

1. **NO feature flags.** Always-on permanent village content.
2. **REMOVE old NPC data** for these 8 ids (sprites, registrations, dual paths). Replace in place.
3. Content.py ids stay the same — swap art only / HD blit path like fairy. **Do not move tiles.**
4. Cursor prompt Step 1 must list the old assets/ids to delete; Step 3 removes them before wiring HD.
5. Do not redo fairies, King court, or batch1 ids.
