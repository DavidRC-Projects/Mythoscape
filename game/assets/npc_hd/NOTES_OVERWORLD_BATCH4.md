# Overworld HD NPC pack Batch 4 (Harbourreach + Stonehaven) — NOTES

Built on the box under `/workspace/npc_hd_overworld/batch4/` (2026-10-06 BST). Reuses batch1–3 pipeline patterns (`ow_npc.py`, assemble, package, run_parallel) and Fairy Village quality bar: CC0 Blender Human Base Meshes + Cycles / sprite pipeline.

**Final overworld batch** — covers remaining Harbourreach + Stonehaven content.py NPCs plus Packer Nell.

## Characters

| id | sex | read | notes |
|----|-----|------|-------|
| tackle_merchant | F | Sea-green oilskin, straw angler hat, fishing rod, tackle pouch | **Marina the Angler** — Harbourreach Tackle |
| fishmonger_kai | M | Slate-blue shirt, brown trousers, stained off-white bib apron, tall boots, trimmed beard, cleaver, fish tray | **Fishmonger Kai** — Kai's Catch |
| harbour_cook | F | Terracotta cook dress, white kitchen apron, kerchief, ladle | **Cook Nell** — distinct from Marina (no oilskin/rod) |
| herald_rowan | M | Crimson/gold formal tabard, banner staff, scroll case | **Herald Rowan** — Stonehaven Keep |
| city_vendor_mira | F | Amber market dress, green stall apron, red neckerchief, bread basket + travel kit | **Mira the Vendor** — Stonehaven market |
| packer_nell | F | Indigo laced kirtle, oatmeal shirt, tan leather half-apron, cross-body satchel, twine coil, sack bundle on back, carried sack, copper braid | **Packer Nell** — bag/packing shop beside Shopkeeper Joe; distinct from Cook Nell + Mira |

**Not in this pack:** fairies, King court, batch1–3 ids.

## Spawns

`json/overworld_batch4_spawns.json` lists id, name, sex, role for all 6. **World xy stay as in `content.py` — do not move tiles** (Packer Nell keeps her existing spot near `shopkeeper_joe`). Swap art only / HD blit path.

## Fix pass (2026-10-08)

- **Kai** rebuilt: shirt + trousers + real bib apron (chest bib panel + hanging skirt panel that no longer shrink-wraps the legs; trouser legs visible below the hem), stains painted into the apron material (floating stain/pocket squares removed), proper boots (toe-box/heel/shaft — no bare toes), clean trimmed beard + moustache, fish tray carried forward on the raised left forearm and tilted toward camera, larger readable cleaver.
- **Marina**: white mask over mouth/chin removed (knit collar band was wrapping the chin; now sits on the neck base).
- **Mira**: red bar across the mouth removed (scarf torus sat at mouth height; replaced by a neckerchief + knot at the throat).
- **Cook Nell**: apron rebuilt as a bib + skirt panel that follows the dress folds on top — no white jagged tears through the skirt.
- **Herald Rowan**: shirt no longer catches the chin; shoulder seam gaps closed.
- All faces checked on 1536 portraits: no stray geometry. Shoulder seam gaps (torso/sleeve split) closed on all six.
- **Packer Nell** added (new).

## Honest quality scores (vs commercial fantasy NPCs)

Target ≥ 8/10. Reviewed on hero + 1536 portrait + 1x/2x idle facings after assemble.

| character | hero score | 40px sprite readability | notes |
|-----------|------------|-------------------------|-------|
| tackle_merchant | 8.0 | 8.5 | Mouth artifact gone; hat + rod + teal oilskin read instantly. Thin dark seam at the collar edge on close-up. |
| fishmonger_kai | 8.0 | 8.5 | Now a proper fishmonger: bib apron over shirt/trousers, tray of fish forward, cleaver. Beard is clean but a little patchy close-up; boots slightly chunky. |
| harbour_cook | 8.0 | 8.0 | Apron sits cleanly on the skirt; kerchief + ladle + whites read as cook. Simple face; strap ends a touch stiff. |
| herald_rowan | 8.0 | 8.5 | Clean neck/shoulders; crimson tabard + gold stripe + banner pennant read strongly. Tabard is plain (no heraldic charge). |
| city_vendor_mira | 8.0 | 8.0 | Mouth bar gone; green apron + basket + neckerchief distinct from Cook Nell. Pigtail strands slightly stringy. |
| packer_nell | 8.5 | 8.5 | Strongest silhouette in the batch: satchel, sack, back bundle, twine, laced indigo kirtle. Clearly distinct from Cook Nell and Mira. |

## Deliverables

- `assets/npcs/<id>/` — hero, portrait, sprites 1x/2x/4x, meta.json
- `json/overworld_batch4_spawns.json`, `manifest.json` (`feature_flag: null`)
- `previews/overworld_batch4_contact_sheet.png`, `previews/overworld_batch4_heroes_grey.png`
- `OVERWORLD_NPCS_BATCH4_CURSOR_PROMPT.md` (Step 1 investigate-only then STOP; permanent; protected walk files; work directly on `main`)
- `NOTES_OVERWORLD_BATCH4.md` (this file — do not overwrite King NOTES.md)
- Zip via Python zipfile: `npc_hd_overworld_batch4_part*.zip`, arcname root **`npc_hd/`**

## Caveats

- Sprite NPCs only — do not touch walk-cycle code.
- Idle animation is breath + prop sway (8 frames), not a skeletal walk.
- Parent agent delivers to David's Mac; this box never CopyFromBox'd the pack.
- Cook Nell (`harbour_cook`) must stay visually distinct from Marina (`tackle_merchant`) and Packer Nell (`packer_nell`).
- Mira (`city_vendor_mira`) green stall apron ≠ Cook Nell white kitchen apron.

## Integration rules (David)

1. **NO feature flags.** Always-on permanent overworld content.
2. **REMOVE old NPC data** for these 6 ids (sprites, registrations, dual paths). Replace in place.
3. Content.py ids stay the same — swap art only / HD blit path like fairy. **Do not move tiles.**
4. Cursor prompt Step 1 must list the old assets/ids to delete; Step 3 removes them before wiring HD.
5. Do not redo fairies, King court, or batch1–3 ids.
