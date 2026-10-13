# Mythoscape: HD pets (Cat + White Husky)

Work **directly on `main`**: no branches, no PRs. Small steps; commit + push to `origin main` after each one.
**No feature flags.** Always on. Do not add a new `USE_*` toggle, and do not keep a 2D fallback for these two pets once HD is wired.
**Never touch the walk cycle:** `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
**Combat timing stays exactly as it is:** server ticks, pet damage formula, `pet_target_id` rules, `ATTACK_ANIM_SECS`, hitsplat timing. Only visuals and **follow placement** change as specified below.

## Art (already in the repo)
`game/assets/pets_hd/<id>/` for:

| id (sprite) | PETS key | canvas 4x | note |
|---|---|---|---|
| `pet_cat` | `cat` | 512×576 | tabby house cat, ~0.28 m shoulder, red collar |
| `pet_husky` | `husky` | 512×576 | white husky, grey saddle/ears, blue eyes, curled tail; smaller than mountain wolf |

Same knights_hd / monsters_hd format: `sprite_{1x,2x,4x}/{idle,walk,attack,hit,death}/{s,e,n,w}/`, meta with `scale_baked: true`, anchors, combat. Preview: `game/assets/pets_hd/previews/pets_hd_lineup.png`. Notes: `NOTES.md`.

Server already: pets follow the owner and **attack monsters the player has engaged** (`process_pets`, `pet_hits_monster`, `attack_anims["pet:"+owner_id]`). Do not invent new combat rules.

## Step 1: HD draw path for pets
- Add a thin loader (new `pets_hd_client.py`, or extend `knights_hd_client.py`) that loads `game/assets/pets_hd/<sprite>/` the same way monsters_hd is loaded (meta, sprite sheets, facings, states).
- In `client.py` pet draw loop, if the sprite is `pet_cat` / `pet_husky` (or `cat` / `husky`), draw HD instead of `legacy_creature_sprites.draw_pet` / `sprites.draw_pet`.
- Map facing from the existing `facing_for` / `facing_for_view` into `s/e/n/w`.
- **Walk anim while moving:** when `mov` is true and not swinging, play `walk` (8 frames, same cadence style as HD monsters).
- **Attack anim when attacking:** when `pet:{owner_id}` is in `attack_anims` (already set from `pet_hits_monster`), play `attack` with `_attack_progress`; impact frame 3 at progress 0.48. Do not change damage or when pets choose targets.
- **Hit anim if cheap:** if the pet takes damage and you already have a hit flash path, play `hit` (3 frames / 0.36 s); otherwise skip.
- Nameplate / HP bar: use `head_top` from meta anchors (like monsters_hd). Draw at `TILE * 1.1` (scale baked).
- Remove the old 2D path for these two sprites only: drop `pet_cat` from `legacy_creature_sprites._PET_PREVIEW`, and stop calling procedural `draw_pet_cat` / `draw_pet_husky` when HD is present. Leave other pets (skeleton, dragons) on their current drawers.
- Pets modal icon: prefer HD idle frame (or existing `blit_pet_icon` fed from HD) so the menu matches in-world. Commit.

## Step 2: Follow distance — exactly 1 tile, never on the player
Edit **server** `process_pets` / `_pet_step_toward` (and any activate/teleport that sets pet position):

1. **Never share the player's tile.** After every pet move (and on activate / dungeon enter / teleport), if `(pet_x, pet_y) == (player_x, player_y)`, immediately place the pet on a free adjacent tile.
2. **Follow at exactly 1 tile (Chebyshev).** While the player is moving and the pet is not chasing a `pet_target_id`, keep the pet on a walkable tile with `chebyshev(pet, player) == 1`. If farther than 1, step toward an adjacent ring tile (not onto the player). If somehow on the player tile, step off first.
3. **When the player stops:** settle the pet on a free adjacent tile, **prefer behind the player, then beside** (use the player's facing if available; otherwise south, then west/east, then north). Face the pet toward the player (client already derives facing from movement; if you expose pet facing from the server, set it to look at the player when idle).
4. Soft leash (`> 10` snap) may remain, but the snap target must be an adjacent free tile, **not** the player's cell.
5. Do not change attack engagement rules. Commit + smoke-test: walk, stop, enter door, call pet — pet never overlaps the player sprite tile.

## Step 3: Coverage / cleanup
- Grep for `pet_cat`, `pet_husky`, `draw_pet_cat`, `draw_pet_husky` and ensure no leftover 2D-only path runs for the active HD pets.
- If `tools/hd_coverage.py` (or a pets checklist) exists, add these two sprite ids and require HD present + old path absent. Run until clean.
- Commit, push to main, paste a short before/after note in the commit message.
