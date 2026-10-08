# Overworld HD NPC pack Batch 3 (Forest / Mine / Fringe) — NOTES

Built on the box under `/workspace/npc_hd_overworld/batch3/` (2026-10-06 BST). Reuses batch1/batch2 pipeline patterns (`ow_npc.py`, assemble, package, run_parallel) and Fairy Village quality bar: CC0 Blender Human Base Meshes + Cycles / sprite pipeline.

## Characters

| id | sex | read | notes |
|----|-----|------|-------|
| old_fisherman_pete | M | Slate oilskin coat, floppy hat, grey beard, fishing rod + net bag | Weathered lake fisherman |
| mia | F | Child scale (~0.55), rose dress, white pinafore, pink ribbon, wildflower | Lost daughter — distinct from Timmy (boy / ball / blue tunic) |
| mysterious_traveler | M | Charcoal hooded cloak, crystal staff, satchel | Enigmatic hooded silhouette |
| merchant_wanderer | M | Burgundy trader coat, gold vest, backpack + wares, coin pouches | Traveling merchant pack |
| mine_scout | F | Ochre leather, scout cap, lantern + pickaxe | **Scout Elena** — distinct from Fletcher Elena (no forest green, no braid/bow/quiver) |
| dungeon_hermit | M | Ragged grey-brown robes, wild grey hair/beard, gnarled staff | Hermit Cole near dungeon |
| mad_scientist | M | Stained lab coat, wild hair spikes, goggles, glowing vials | Potion lab vibe |
| pass_scout | M | Slate travel tunic, fur collar, trail spear, satchel | **Scout Bren** mountain-pass scout |

**Not in this pack:** fairies, King court, batch1 village-core ids, batch2 village-life ids.

## Spawns

`json/overworld_batch3_spawns.json` lists id, name, sex, role. **World xy stay as in `content.py` — do not move tiles.** Swap art only / HD blit path.

## Honest quality scores (vs commercial fantasy NPCs)

Target ≥ 8/10. Reviewed on hero + portrait + 1x/4x south idle after assemble.

| character | hero score | 40px sprite readability | notes |
|-----------|------------|-------------------------|-------|
| old_fisherman_pete | 8.5/10 | 8.5/10 | Floppy hat + rod + net bag; slate oilskin reads |
| mia | 8/10 | 8/10 | Child scale (~0.55) + rose dress + white pinafore; distinct from Timmy |
| mysterious_traveler | 8.5/10 | 8.5/10 | Charcoal hood silhouette + crystal staff glow |
| merchant_wanderer | 8/10 | 8/10 | Burgundy coat + gold vest + coin pouches; pack stronger on north |
| mine_scout | 8.5/10 | 8.5/10 | Ochre leather + lantern — clearly not Fletcher Elena (no forest green/bow) |
| dungeon_hermit | 8/10 | 8/10 | Ragged grey-brown robes + wild grey hair/beard + gnarled staff |
| mad_scientist | 8.5/10 | 8.5/10 | Cream lab coat + hair spikes + goggles + glowing vials + stain patches |
| pass_scout | 8/10 | 8/10 | Fur collar + trail spear + slate tunic; Scout Bren mountain read |

**Pass vs bar:** all eight ≥ 8/10 after assemble QA. No targeted re-render required. Minor caveats only (shoulder extract gaps inherited from Human Base Mesh clothing shells; flower/ribbon thin at 1x; backpack strongest on north facing; idle breath not walk).

## Deliverables

- `assets/npcs/<id>/` — hero, portrait, sprites 1x/2x/4x, meta.json
- `json/overworld_batch3_spawns.json`, `manifest.json` (`feature_flag: null`)
- `previews/overworld_batch3_contact_sheet.png`
- `OVERWORLD_NPCS_BATCH3_CURSOR_PROMPT.md` (Step 1 investigate-only then STOP; permanent; protected walk files)
- `NOTES_OVERWORLD_BATCH3.md` (this file — do not overwrite King NOTES.md)
- Zip via Python zipfile: `npc_hd_overworld_batch3_part*.zip`, arcname root **`npc_hd/`**

## Caveats

- Sprite NPCs only — do not touch walk-cycle code.
- Idle animation is breath + prop sway (8 frames), not a skeletal walk.
- Parent agent delivers to David's Mac; this box never CopyFromBox'd the pack.
- Scout Elena (`mine_scout`) must stay visually distinct from Fletcher Elena (`fletcher_elena`).

## Integration rules (David)

1. **NO feature flags.** Always-on permanent overworld content.
2. **REMOVE old NPC data** for these 8 ids (sprites, registrations, dual paths). Replace in place.
3. Content.py ids stay the same — swap art only / HD blit path like fairy. **Do not move tiles.**
4. Cursor prompt Step 1 must list the old assets/ids to delete; Step 3 removes them before wiring HD.
5. Do not redo fairies, King court, batch1, or batch2 ids.
