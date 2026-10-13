# Mythoscape: HD monsters batch 2 (Void Sanctum + Depths)

Work **directly on `main`**: no branches, no PRs. Make small steps and commit + push to `origin main` after each one.
**No feature flags.** Everything here is always on. Do not add a new `USE_*` toggle, and do not keep a fallback for these ids.
**Never touch the walk cycle:** `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
**Combat timing stays exactly as it is:** server ticks, `attack_range`, `side_by_side`, `side_gap`, `attack_cooldown`, `confine_room`, boss phases, `ATTACK_ANIM_SECS`, `strike_t`. Only the visuals change.
Batch 1 (`MONSTERS_HD_BATCH1_CURSOR_PROMPT.md`) must already be done: `knights_hd_client` resolves `monsters_hd/<id>` and `tools/hd_coverage.py` exists. If not, do batch 1 first.

## Art (already in the repo)
`game/assets/monsters_hd/<id>/` for 12 ids, in **exactly the batch 1 / knights_hd format** (`sprite_{1x,2x,4x}/{idle,walk,attack,hit,death}/{s,e,n,w}/fNN.png`, idle 4, walk 8, attack 6, hit 3, death 6; `meta.json` with `canvas`, `feet_px`, `states`, `anchors_4x`, `healthbar_y_offset_1x`, `hit_point_4x`, `combat`, `complete: true`; hero + portrait):

| id | region | canvas 4x (feet) |
|---|---|---|
| `ossuary_keeper` | Depths, Ossuary Halls (Bone Key) | 640×672 (320,624) |
| `morvath` | Depths boss, Throne of Bones | **1152×1024 (576,968)** |
| `drowned_dead` | Depths, Flooded Catacombs | 512×576 (256,528) |
| `shade`, `crypt_ghoul` | Void Entry Hall / Galleries (+ Depths Mausoleum) | 512×576 |
| `gallery_warden` | Void Galleries mini-boss (Amethyst Key) | 512×576 |
| `void_imp`, `void_crawler` | Void Barracks / Crystal Depths (+ Nyxarath adds) | 512×576 |
| `obsidian_colossus`, `void_horror` | Void Barracks / Rift Edge | 768×672 (384,624) |
| `rift_wraith` | Void Rift Edge | 512×576 |
| `nyxarath` | Void boss, Eclipse Throne | **1152×1024 (576,968)** |

- Same fixed camera as everything else: 175.6 px/m at 4x (43.9 at 1x). **Always read `canvas`/`feet_px` from meta.**
- **Size is baked in** (`meta.scale_baked: true`). Gallery Warden is already 1.2×, Ossuary Keeper 1.15× a big skeleton, Nyxarath and Morvath are modelled at full boss size. Do **not** multiply by content `scale` for these ids.
- Each id has its own look. The tint, the eclipse halo and the bone crown are now part of the art.
- Creatures with no weapon (shade, rift_wraith, crypt_ghoul, imps, colossus, horrors) use the claw/fist tip as `weapon_tip` / `hit_point`.
- Preview: `game/assets/monsters_hd/previews/monsters_hd_batch2_lineup.png`. Notes: `NOTES_BATCH2.md`. Manifest: `manifest_batch2.json`.

## Step 1: Ossuary Keeper + Morvath first (remove the shared skeleton path)
These two currently borrow the shared `big_skeleton` drawing (`"visual": "big_skeleton"` + tint + scale).
- Add `ossuary_keeper` and `morvath` to `MONSTERS_HD` in `knights_hd_client.py` (asset dir `monsters_hd/<id>`).
- In `server/content.py`, delete `visual`, `tint` and `scale` from both entries. Leave every stat, drop, `confine_room` and combat key exactly as it is (`visual`, `tint` and `scale` are only read by the client).
- Delete `depths_v2_client.draw_bone_crown()` and its call in `client.py` (`if m.get("type") == "morvath": ... draw_bone_crown`). The crown is now in the art.
- Make sure **no code path** draws these two ids through `big_skeleton`: not `anim_strip_sprites`, not `legacy_creature_sprites`, not `sprites.draw_monster`, not a tinted re-use. Grep for `ossuary_keeper`, `morvath` and `"big_skeleton"` and remove anything left that only served these two. The boss health bar, boss label and phase logic stay.
- Smoke-test the Ossuary Halls key fight and the Morvath arena (including the phase 2 adds). Commit.

## Step 2: The other Depths creature
- Add `drowned_dead` to `MONSTERS_HD`. Delete its `visual: "skeleton"` + `tint` from content.py.
- **`skeleton` itself stays 2D**: keep its strip/legacy drawing for the plain `skeleton` id only. Commit.

## Step 3: Void Sanctum regulars (replace the old strips)
- Add `shade`, `crypt_ghoul`, `void_imp`, `obsidian_colossus` and `void_horror` to `MONSTERS_HD`.
- In `anim_strip_sprites.py`, remove the mappings `shade→barrow_wraith`, `crypt_ghoul→rot_ghoul`, `void_imp→void_spawn`, `void_horror→void_brute` and `obsidian_colossus→stone_golem`, plus their height entries. Delete the strip PNGs if nothing else uses them (grep first).
- Remove any `sprites.draw_monster` / `legacy_creature_sprites` cases that only served these ids. Commit.

## Step 4: Void creatures that had no sprite of their own
`gallery_warden`, `void_crawler` and `rift_wraith` were tinted re-uses (crypt_ghoul / void_imp / shade + tint).
- Add them to `MONSTERS_HD`, and delete their `visual`, `tint` and `scale` keys in content.py. Commit.

## Step 5: Nyxarath (replace the custom boss drawing)
- Add `nyxarath` to `MONSTERS_HD`. Delete `visual: "void_horror"` and `scale: 1.9` from content.py.
- In `void_v2_client.py`, delete the Nyxarath branch of `tint_and_halo` (the gold `pygame.draw.circle` halo). Once no batch-2 id has a `tint` any more, delete `tint_and_halo` itself and its call in `client.py` (`if _mdef.get("visual"): ... tint_and_halo`), unless the coverage script shows another id still uses `visual`/`tint`. If one does, keep only that.
- Keep the boss arena, phases, pylons, rift pools, orbs, the boss HP bar and the `boss_label`/`boss_type` panel. Those are not character drawing.
- Smoke-test all three phases (the Void Crawler adds are now HD too). Commit.

## Step 6: Combat check (visual only)
- Frame 3 of the attack lands on the 0.48 hitsplat. Hit: 3 frames over 0.36 s. Death: 6 frames over 0.9 s, then a 0.6 s fade from the corpse snapshot.
- Side-by-side gaps are unchanged: colossus/horror/nyxarath 3, the rest 2. `void_crawler` and `drowned_dead` stay melee-adjacent (range 1).
- Draw at `TILE * 1.1` (scale baked). The HP bar and nameplate use `head_top_dy`.
- Click radius: 2 tiles for `obsidian_colossus`, `void_horror`, `nyxarath` and `morvath`, 1 for the rest, unless the current value is bigger.
- Bosses: check that Nyxarath and Morvath fit their arenas visually (the big canvas has headroom for the overhead swing and the death fall). Commit.

## Step 7 (final): run the HD coverage check
- In `tools/hd_coverage.py`, remove these 12 ids from the "no HD art yet" exclusion list. The excluded list is now only `goblin`, `skeleton`, `spider`, `dragon` (Adamant Dragon, stays as is) and the Emberdeep creatures still waiting for batch 3 (`magma_slug`, `ash_imp`, `crucible_beast`, `ember_wolf`).
- Add a check: for every id drawn HD, `old_2d_path_still_present` must be False. That means no `visual` key in content.py pointing at a 2D drawer, no anim-strip/legacy mapping, and no custom boss drawing.
- Run `python tools/hd_coverage.py`. Fix anything it reports (wire in, remove leftovers) and re-run until it prints **`MISSING: 0`**.
- Commit the script and the fixes, push to main, and paste the final table in the commit message.
