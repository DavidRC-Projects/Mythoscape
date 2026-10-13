# Mythoscape: HD monsters batch 3 (Emberdeep)

Work **directly on `main`**: no branches, no PRs. Make small steps and commit + push to `origin main` after each one.
**No feature flags.** Everything here is always on. Do not add a new `USE_*` toggle, and do not keep a fallback for these ids.
**Never touch the walk cycle:** `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
**Combat timing stays exactly as it is:** server ticks, `attack_range`, `side_by_side`, `side_gap`, `attack_cooldown`, `confine_room`, boss phases, `ATTACK_ANIM_SECS`, `strike_t`. Only the visuals change.
Batches 1 and 2 (`MONSTERS_HD_BATCH1_CURSOR_PROMPT.md`, `MONSTERS_HD_BATCH2_CURSOR_PROMPT.md`) must already be done: `knights_hd_client` resolves `monsters_hd/<id>` and `tools/hd_coverage.py` exists.

## Art (already in the repo)
`game/assets/monsters_hd/<id>/` for 4 Emberdeep ids, in **exactly the batch 1 / knights_hd format** (`sprite_{1x,2x,4x}/{idle,walk,attack,hit,death}/{s,e,n,w}/fNN.png`, idle 4, walk 8, attack 6, hit 3, death 6; `meta.json` with `canvas`, `feet_px`, `states`, `anchors_4x`, `healthbar_y_offset_1x`, `hit_point_4x`, `combat`, `complete: true`; hero + portrait):

| id | region | canvas 4x (feet) | note |
|---|---|---|---|
| `magma_slug` | Emberdeep floors 1–3 | 512×576 (256,528) | **knee height ~0.45 m** — small on purpose |
| `ash_imp` | Emberdeep floors 2–5 | 512×576 | ash-grey imp, ember eyes |
| `ember_wolf` | Emberdeep floors 4–7 | 512×576 | charred wolf, ember glow |
| `crucible_beast` | Emberdeep floors 6–8 | **768×672 (384,624)** | lava golem |

- Same fixed camera: 175.6 px/m at 4x (43.9 at 1x). **Always read `canvas`/`feet_px` from meta.**
- **Size is baked in** (`meta.scale_baked: true`). Do **not** multiply by content `scale` for these ids. Do **not** enlarge the slug.
- Preview: `game/assets/monsters_hd/previews/monsters_hd_batch3_lineup.png`. Notes: `NOTES_BATCH3.md`. Manifest: `manifest_batch3.json`.

## Step 1: Magma Slug + Ash Imp
- Add `magma_slug` and `ash_imp` to `MONSTERS_HD` in `knights_hd_client.py` (asset dir `monsters_hd/<id>`).
- In `server/content.py`, delete any `visual`, `tint` and `scale` from both entries. Leave every stat and drop exactly as it is.
- Remove any `emberdeep_creatures_client` / `legacy_creature_sprites` / `sprites.draw_monster` / `anim_strip_sprites` cases that only served these two. Grep for `magma_slug` and `ash_imp`. Commit.

## Step 2: Ember Wolf
- Add `ember_wolf` to `MONSTERS_HD`.
- It currently uses an anim strip (`wolf_dire` or similar). Remove that mapping and any tinted wolf reuse. Keep combat keys (`attack_range` 2, `side_by_side`, `side_gap` 2, `attack_cooldown` 1.0, `force_retaliate`). Commit.

## Step 3: Crucible Beast
- Add `crucible_beast` to `MONSTERS_HD`.
- Delete legacy / procedural drawing for it. Click radius 2 tiles (like colossus/horror) unless the current value is bigger. `side_gap` 3. Commit.

## Step 4: Combat check (visual only)
- Frame 3 of the attack lands on the 0.48 hitsplat. Hit: 3 frames over 0.36 s. Death: 6 frames over 0.9 s, then a 0.6 s fade.
- Draw at `TILE * 1.1` (scale baked). The HP bar and nameplate use `head_top_dy`.
- Confirm the slug reads **small** next to the HD player (about knee height). Do not add a scale-up. Commit.

## Step 5 (final): run the HD coverage check
- In `tools/hd_coverage.py`, remove these 4 ids from the "no HD art yet" exclusion list. The excluded list is now only `goblin`, `skeleton`, `spider`, `dragon` (Adamant Dragon, stays as is) — Emberdeep creatures are done.
- Add/keep a check: for every id drawn HD, `old_2d_path_still_present` must be False (no `visual` key pointing at a 2D drawer, no anim-strip/legacy mapping, no custom emberdeep creature drawing for these ids).
- Run `python tools/hd_coverage.py`. Fix anything it reports (wire in, remove leftovers) and re-run until it prints **`MISSING: 0`**.
- Commit the script and the fixes, push to main, and paste the final table in the commit message.
