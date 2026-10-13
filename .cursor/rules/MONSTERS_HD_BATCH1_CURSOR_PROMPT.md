# Mythoscape: HD monsters batch 1 + Mae the Outfitter + full HD coverage pass

Work **directly on `main`**: no branches, no PRs. Make small steps and commit + push to `origin main` after each one.
**No feature flags.** Everything here is always on. Do not add a new `USE_*` toggle.
**Never touch the walk cycle:** `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
**Combat timing stays exactly as it is:** server ticks, `attack_range`, `side_by_side`, `side_gap`, `attack_cooldown`, `ATTACK_ANIM_SECS`, `strike_t`. Only the visuals change.

## Art (already in the repo)
- `game/assets/npc_hd/assets/npcs/outfitter_mae/`: Mae the Outfitter, in exactly the same format as every other `npc_hd` NPC (walk 8 frames × s/e/n/w, 1x/2x/4x, `meta.json` with feet_px, hero + portrait).
- `game/assets/monsters_hd/<id>/` for `giant_rat`, `big_skeleton`, `giant`, `wolf`, `guard`, `adamant_duelist`, `mythos_champion`. This is **the same format as `game/assets/knights_hd/assets/<id>/`**:
  - `sprite_{1x,2x,4x}/{idle,walk,attack,hit,death}/{s,e,n,w}/fNN.png` (idle 4, walk 8, attack 6, hit 3, death 6);
  - `meta.json` with `canvas`, `feet_px`, `states` (attack `frame_starts` [0, .14, .30, .42, .60, .80], impact frame 3 = the 0.48 hitsplat), `anchors_4x`, `healthbar_y_offset_1x`, `hit_point_4x`, `combat` (copied from content.py, unchanged), `complete: true`;
  - a hero and portrait.
- The fixed camera is 175.6 px/m at 4x (43.9 at 1x), the same scale as the HD NPCs, knights and HD player. Feet sit on the ground with a baked soft contact shadow.
- **The giant uses a bigger canvas** (4x 768×672, feet 384,624), so always read `canvas` and `feet_px` from its meta and never hard-code 512×576.
- Wolf and giant rat are beasts. Their `weapon_tip` / `hit_point` anchor is the mouth (bite point).
- Previews: `game/assets/monsters_hd/previews/monsters_hd_batch1_lineup.png` (HD player for scale).

## Step 1: Mae
Add `"outfitter_mae"` to `OVERWORLD_HD` in `client/npc_hd_client.py`. Check that she draws HD at (66, 41) inside Mythos Outfitters, with no 2D fallback. Commit.

## Step 2: HD monster loader
Generalise `client/knights_hd_client.py`. Do not write a second copy of the draw code.
- Add `MONSTERS_HD = {"giant_rat", "big_skeleton", "giant", "wolf", "guard", "adamant_duelist", "mythos_champion"}`.
- Add a per-id asset dir: knights resolve to `knights_hd/assets/<id>`, and the batch 1 ids resolve to `monsters_hd/<id>`.
- `handles()` returns True for both sets. `draw`, `head_top_dy`, `anchor`, `portrait`, the corpse list (`knight_corpses`) and the hit reaction (`knight_hit_at`) then work unchanged for the new ids.
- Keep the scaled-image cache limit, and load lazily.
- In `_draw_mon` the HD branch already runs first. `adamant_duelist` is `humanoid: True`, so make sure the HD branch wins before the `draw_humanoid_detailed` branch. Leave the `humanoid` flag itself alone: it still drives the PK tutorial, anchors and side-by-side logic.
- Click radius (`client.py` ~3311 / `_monster_click_radius`): keep it at least as generous as now. Use 2 tiles for `giant` and 1 for the others, unless the current value is bigger.
- Commit.

## Step 3: Remove the replaced 2D visuals (no fallback for these ids)
- In `legacy_creature_sprites.py`, remove `giant_rat`, `guard` and `mythos_champion` from `_MONSTER_PREVIEW` / `_HEIGHT`, plus their preview files if nothing else uses them.
- In `anim_strip_sprites.py`, remove the `giant` (giant_hill), `wolf` (wolf_grey) and `big_skeleton` (skeleton_mage) mappings, and their strips if unused.
  **Keep `skeleton`, `goblin`, `spider` and `ember_wolf` (wolf_dire)**: they are not replaced yet.
- Remove any procedural `sprites.draw_monster` cases that only served these 7 ids.
- Commit.

## Step 4: Combat check (visual only)
- Swings use the existing attack progress, so frame 3 lands on the 0.48 hitsplat.
- Hit reaction: 3 frames over 0.36 s from the released hitsplat.
- Death: 6 frames over 0.9 s, then a 0.6 s fade from the corpse snapshot.
- Side-by-side fighters keep their gap: giant gap 3, big_skeleton/wolf/duelist gap 2.
- Swings are e/w; walking uses all four facings.
- Draw at `TILE * content scale * 1.1` exactly like the knights. The HP bar uses `head_top_dy`.
- Smoke-test by fighting one of each: rats and giants at the dungeon entrance, wolves at the mountain pass, guards in Stonehaven, the champion in the keep, and the duelist with PK on. Commit.

## Step 5 (final): HD coverage audit + wiring of EVERYTHING
Write `tools/hd_coverage.py`. Make it read-only, with no game start, runnable with `python tools/hd_coverage.py`. It must:
1. Load every NPC id (`server/content.py` `NPCS`) and every monster type (`MONSTERS`).
2. For each id, find its HD art folder in: `game/assets/npc_hd/assets/npcs/<id>`, `game/assets/fairy_village/assets/npcs/<id>`, `game/assets/knights_hd/assets/<id>`, `game/assets/monsters_hd/<id>`, and `game/assets/emberdeep_hd/dragon` (the Emberdeep wyrm).
3. For each id, report whether the client actually draws it HD:
   - in `npc_hd_client.OVERWORLD_HD`, `fairy_village_client.FAIRY_NPCS`, or `knights_hd_client.handles()`;
   - for the wyrm, the Emberdeep loader from `EMBERDEEP_UX_CURSOR_PROMPT.md`.
4. Also check the non-character HD packs are referenced by client code:
   - `player_hd` (`player_hd_client` + the 3D/2D toggle);
   - `emberdeep_hd/textures` (`emberdeep_v2_client`);
   - `emberdeep_hd/dragon` frames;
   - `fairy_village` tiles/buildings/fountains;
   - every `meta.json` with `complete: true`.
5. Print a table (`id | kind | hd_folder | drawn_hd | old_2d_path_still_present`) and a final `MISSING: N`. Exit 1 if N > 0.
   - **Excluded on purpose** (list them as `excluded`, not missing): `goblin`, `skeleton`, `spider`, `dragon` (Adamant Dragon). These stay as they are.
   - Also exclude the Void / Depths / Emberdeep creatures that have no HD art yet: `shade`, `crypt_ghoul`, `void_imp`, `obsidian_colossus`, `void_horror`, `gallery_warden`, `void_crawler`, `rift_wraith`, `nyxarath`, `ossuary_keeper`, `drowned_dead`, `morvath`, `magma_slug`, `ash_imp`, `ember_wolf`, `crucible_beast`.
     Rule: an id with no HD folder is `excluded`; an id **with** an HD folder that isn't drawn HD is `MISSING`.

Then fix everything it reports:
- wire in any HD asset that exists but isn't drawn (including the Emberdeep wyrm frames and textures if `EMBERDEEP_UX_CURSOR_PROMPT.md` hasn't been run yet);
- remove the replaced 2D visuals wherever HD exists;
- re-run until it prints **`MISSING: 0`**.

Commit the script and the fixes, push to main, and paste the final table in the commit message.
