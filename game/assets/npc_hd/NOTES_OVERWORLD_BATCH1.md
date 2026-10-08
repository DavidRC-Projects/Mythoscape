# Overworld HD NPC pack Batch 1 (Village Core) — NOTES

Built on the box under `/workspace/npc_hd_overworld/batch1/` (2026-10-06 BST). Fairy Village quality bar: CC0 Blender Human Base Meshes + same Cycles / sprite pipeline patterns as `/workspace/fairy_village/src/npc/fv_npc.py` and `/workspace/npc_hd/src/kc_npc.py`.

## Characters

| id | sex | read | notes |
|----|-----|------|-------|
| shopkeeper_joe | M | Warm middle-age merchant: lavender vest, cream sleeves, tan apron, gold buckle, mustache, ledger | Distinct male merchant silhouette |
| jeweler_lira | F | Elegant burgundy gown, gold belt + ruby, gem necklace, loupe + gem tray | Fine dress / jeweler tools |
| fletcher_elena | F | Forest-green tunic, leather vest + bracers, quiver + bow, braid | Archer/fletcher gear |
| blacksmith_gareth | M | Burly soot-tinged smith, leather apron, bare strong arms, hammer, short hair + stubble | Smith silhouette at 40px |
| banker_iris | F | Formal navy dress, gold collar/cuffs, tidy bun, spectacles, ledger + keys | Professional bank attire |
| elder_miriam | F | Lavender robes, tan shawl, white hair bun, staff with moon gem | Wise elder |
| farmer_tom | M | Straw hat, rustic shirt, suspenders, weathered trousers, rake | Farmer silhouette |
| innkeeper_sarah | F | Rose dress, cream tavern apron, auburn hair, tankard | Friendly host |

**Not in this pack:** fairy NPCs (`elowen_moonwhisper`, `warden_thorne`, `tumbleroot`, `pip_dewdrop`) and King court (`king`, `mythos_knight_*`).

## Spawns

`json/overworld_batch1_spawns.json` lists id, name, sex, role. **World xy stay as in `content.py` — do not move tiles.** Swap art only / HD blit path.

## Honest quality scores (vs commercial fantasy NPCs)

Target ≥ 8/10. Reviewed on hero + portrait + 1x/4x south idle after assemble.

| character | hero score | 40px sprite readability | notes |
|-----------|------------|-------------------------|-------|
| shopkeeper_joe | 8/10 | 8/10 | Lavender vest + tan apron + mustache + ledger; one fix pass (continuous shirt, thinner apron). Collar/sleeve seam slightly busy in hero |
| jeweler_lira | 8.5/10 | 8/10 | Burgundy gown + gems clear; loupe small at 1x but dress reads elegant |
| fletcher_elena | 8.5/10 | 8.5/10 | Quiver + bow silhouette strong at 1x |
| blacksmith_gareth | 8.5/10 | 8.5/10 | Hammer + apron + burly arms read immediately; forge rim-light |
| banker_iris | 8/10 | 8/10 | Formal navy + bun + specs; professional |
| elder_miriam | 8.5/10 | 8/10 | Shawl + staff + white hair; elder read clear |
| farmer_tom | 8/10 | 8.5/10 | Straw hat + pitchfork read at 40px; one fix pass (continuous shirt, single thigh fill). Breeches silhouette slightly stylized |
| innkeeper_sarah | 8.5/10 | 8/10 | Cream apron + mug; friendly host |

**Pass vs bar:** all eight ≥ 8/10 after targeted fix re-renders for shopkeeper_joe + farmer_tom. Minor caveats only (prop scale at 1x for loupe/keys; idle breath not walk; Joe collar seam / Tom breeches silhouette).

## Deliverables

- `assets/npcs/<id>/` — hero, portrait, sprites 1x/2x/4x, meta.json
- `json/overworld_batch1_spawns.json`, `manifest.json` (`feature_flag: null`)
- `previews/overworld_batch1_contact_sheet.png`
- `OVERWORLD_NPCS_BATCH1_CURSOR_PROMPT.md` (Step 1 investigate-only then STOP; permanent; protected walk files)
- Zip via Python zipfile: `npc_overworld_batch1_pack*.zip`, arcname root **`npc_hd/`** (merge-friendly with King court)

## Caveats

- Sprite NPCs only — do not touch walk-cycle code.
- Idle animation is breath + prop sway (8 frames), not a skeletal walk.
- Parent agent delivers to David's Mac; this box never CopyFromBox'd the pack.

## Integration rules (David)

1. **NO feature flags.** Always-on permanent village content.
2. **REMOVE old NPC data** for these 8 ids (sprites, registrations, dual paths). Replace in place.
3. Content.py ids stay the same — swap art only / HD blit path like fairy. **Do not move tiles.**
4. Cursor prompt Step 1 must list the old assets/ids to delete; Step 3 removes them before wiring HD.
