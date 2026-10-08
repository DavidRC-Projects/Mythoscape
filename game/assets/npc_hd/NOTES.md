# King's Court HD NPC pack — NOTES

Built on the box under `/workspace/npc_hd/` (2026-10-06 BST). Fairy Village quality bar: CC0 Blender Human Base Meshes + same Cycles / sprite pipeline patterns as `/workspace/fairy_village/src/npc/fv_npc.py`.

Pass1 completed for all 5 keys; Pass2 (`src/run_pass2.sh`) finished `PASS2_ALL_DONE` at 18:44 BST — all heroes, portraits, and sprites are pass2.

## Characters

| id | read | notes |
|----|------|-------|
| king | The King at a glance: gold crown on open great-helm, older white beard, royal crimson+gold plate, ermine collar, velvet cape, sceptre + sheathed sword | Unique royal armour (not player Mythos plate clone) |
| mythos_knight_1..4 | Matching crimson dragon-plate unit: gold horns, ruby eyes, dragon chest emblem, kite + sword/polearm, crimson cape | Small face/helm/cape/pose/weapon differences (Valerius / Cedric / Roland spear / Garrick sword) |

## Placement (`king_f1` Great Hall)

Verified walkable `.` in `/workspace/castle_realm/interiors_v2/json/kings_interiors_v2.json` (same schema as game `kings_interiors_v2.json`):

- King `(26, 13)` facing **s** (toward vestibule / entrance)
- Knights `(22,14)`, `(24,14)`, `(28,14)`, `(30,14)` facing **s**
- Player arrival `(25,30)` / `(26,30)` facing **n** into hall rect `(16,12)-(36,22)`

No shifts required — all proposed tiles were walkable.

See `json/king_court_spawns.json` for ids, names, roles, talk lines.

## Honest quality scores (vs commercial fantasy NPCs)

Reviewed after pass2 final hero + portrait + 4x/1x south idle (target ≥ 8/10). No third re-render pass needed.

| character | hero score | 40px sprite readability | notes |
|-----------|------------|-------------------------|-------|
| king | 8.5/10 | 8.5/10 | Crown spikes + white beard + sceptre read clearly; gold chest emblem + crimson cape solid; cape slightly stiff/rectangular |
| mythos_knight_1 (Valerius) | 8/10 | 8/10 | Closed dragon helm + horn silhouette; kite shield emblem readable at 1x; matching unit look |
| mythos_knight_2 (Cedric) | 8/10 | 8/10 | Same unit read; sword + kite; slight pose/cape variance |
| mythos_knight_3 (Roland) | 8.5/10 | 8/10 | Spear/polearm differentiates him in hero + hall mock; silhouette still Mythos crimson |
| mythos_knight_4 (Garrick) | 8/10 | 8/10 | Sword out; four-horn helm variation; cape + emblem clear |

**Pass vs bar:** all five ≥ 8/10 on silhouette / emblem / cape. Minor caveats only (stiff cape panels; inner-thigh mesh gaps typical of plate idle).

## Deliverables

- `assets/npcs/<id>/` — hero, portrait, sprites 1x/2x/4x, meta.json
- `json/king_court_spawns.json`, `manifest.json` (`feature_flag: null`)
- `previews/king_court_contact_sheet.png`, `previews/great_hall_mock.png`
- `KING_COURT_CURSOR_PROMPT.md` (Step 1 investigate-only then STOP; permanent; protected walk files)
- Zip via Python zipfile: `npc_king_court_pack.zip` or part1/part2 ≤15 MB, extracting into `npc_hd/`

## Caveats

- Sprite NPCs only — do not touch walk-cycle code.
- Closed-helm knights hide faces (Mythos dragon helm by design); King is open-faced with beard.
- Idle animation is breath + cape sway (8 frames), not a skeletal walk.
- Parent agent delivers to David's Mac; this box never CopyFromBox'd the pack.


## Integration rules (David)

1. **NO feature flags.** Always-on permanent Great Hall content. Do not add or reuse a flag to gate these NPCs.
2. **REMOVE old NPC data** for the king and Mythos knights (sprites, registrations, placeholders). Do not keep dual paths or leave previous stubs alongside the new HD pack — replace in place.
3. Cursor prompt Step 1 must list the old assets/ids to delete; Step 3 removes them before registering the new five.
