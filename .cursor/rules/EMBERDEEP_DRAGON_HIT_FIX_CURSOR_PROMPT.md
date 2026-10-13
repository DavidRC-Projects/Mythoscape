# HD player: true 4-facing attacks (Emberdeep dragon first, then everywhere)

Work **directly on `main`** in `/Users/davidcarr/Mythoscape`. The code lives in `game/assets/mmorpg/`.
- Make small steps.
- After each step, run `python3 -m py_compile` on every file you touched. Then commit and push to `main` with the message given.
- No branches or PRs.

## Hard rules
- **Never touch the walk cycle**: `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`. Calling them is fine.
- **Keep the combat timing**: `TICK_SECONDS 0.6`, `ATTACK_ANIM_SECS 1.05`, `RANGED_ANIM_SECS 0.72`, contact at progress 0.48 (ranged release frame 5 at 0.55, strike 0.58), `player_hd_client.MELEE_PROGRESS` unchanged. This is client drawing only. No server changes.
- **No feature flags.** The player's own 3D/2D setting stays as it is. The **2D player path and 2D combat are unchanged**; only the HD (3D) player gets the new facings.
- Do not change the HD art. Only change which facing and strip `player_hd_client.draw_player` picks while attacking.

## New assets (already copied, uncommitted)
`game/assets/player_hd/` now also holds these files. They came from the `player_hd_attack4_*.zip` files and have been unpacked over the existing tree.
- `assets/<sex>/<1x|2x|4x>/<layer>/melee_s.png`, `melee_n.png`, `ranged_s.png` and `ranged_n.png` for every body, clothing, armour, hair and weapon layer, plus the `_tint.png` masks where a layer is tintable.
  - Same frame counts and sample points as `melee_e` and `ranged_e`: melee has 10 frames with contact on f4 at 0.48; ranged has 8 frames with release on f5 at 0.55.
  - `w` is still the horizontal flip of `e`.
  - **Front (`s`)**: a diagonal slash. The blade is raised high on the player's right, then arcs across the body toward the camera, reaching the target in front at contact.
  - **Back (`n`)**: the blade is visible over the right shoulder in the windup, then swings out past the right flank on contact.
  - **Ranged `s`/`n`**: the archer stands side-on in a 3/4 view, so the bow and the draw both show.
- `assets/<sex>/<1x|2x>/fx_swing_<weapon>/melee_s.png` and `melee_n.png` (frames 4–5 only, z 91).
- `assets/anchors.json`: `melee` and `ranged` now have `s`, `e` and `n` entries (`hand_R`, `hand_L`, weapon `tip`, `head_top`, `chest`).
- `assets/meta.json`:
  - `anims.melee` / `anims.ranged` facings are `s`, `e`, `n`.
  - **New `weapon_layers[].z_anim`**: in `melee_n` and `ranged_n`, draw the weapon/bow at z 90 (on top) instead of its `n` z of 8. Honour this when sorting layers.

## Root cause (read this first)
1. Until now the HD player had attack frames for the side view only.
2. `_combat_facing` (`client/emberdeep_v2_client.py`, around line 747) returns `"back"` or `"front"` whenever the target is more ahead of or behind the player than to the side, relative to the camera. Walking up to the dragon with the camera looking at it gives `"back"`.
3. `_draw_local_player` (around lines 890–939) then **switches the body to `idle`** for `back`/`front` attacks. It also pastes a stretched, rotated east blade through `_swing_toward_head` / `_dragon_aim_point`, so from the front the player just stands there. The blade:
   - aims at the dragon's **anchor centre** plus 1.8 tiles;
   - starts at a hidden hand;
   - floats loose of the hand.
4. Facing is measured to the wyrm **anchor**, not to the nearest of its 15 footprint tiles or its glided draw position.
5. When the dragon hits you mid-swing, `_frame_for_anim` swaps to `hit` frames and the swing disappears.

Occlusion and depth sorting are **not** the cause. `_draw_billboards` always draws the local player last. Keep it that way.

## Step 1: true 4-facing attack toward the nearest target body tile
In `client/emberdeep_v2_client.py`:
1. Add `_target_point(client, target)`:
   - For `emberdeep_wyrm`, use the glided position from `_wyrm_glide(client, target, now)` (ax, ay = that minus 0.5). Over `emberdeep_creatures.footprint(round(ax), round(ay))`, return the tile centre `(x+0.5, y+0.5)` nearest the player.
   - Otherwise return `(target["x"]+0.5, target["y"]+0.5)`.
2. Rewrite `_combat_facing(client, pose, sx, tile_px, player_depth)`:
   - With no live target, return `pose["face"]` (unchanged).
   - Otherwise project the target point and the player's feet with `_project(...)`, the same call `_dragon_aim_point` uses now. Take `dxs = target_sx - player_sx` and `dys = target_sy - player_sy` in screen pixels.
   - Pick the dominant screen axis:
     - `abs(dxs) > abs(dys)` gives `1` if `dxs > 0`, else `-1`;
     - otherwise `"front"` if `dys > 0` (target lower on screen, toward the camera), else `"back"`.
   - **Hysteresis**: keep the last facing (`client._ember_fight_face`) unless the new axis wins by more than 25% (`abs(a) > 1.25 * abs(b)`) or the target point changed. Ignore gaps under 0.12 tile. That way the player does not flip every frame on the diagonals.
   - Store the result in `client._ember_fight_face` and return it. `1`/`-1` map to HD facing `e`/`w`; `"front"`/`"back"` map to `s`/`n`.
3. py_compile, commit "emberdeep: face the nearest dragon body tile in 4 directions while fighting".

## Step 2: always play the real attack frames, in all 4 facings
1. In `_draw_local_player`:
   - Delete the `if face in ("back", "front") and not ranged: anim = "idle"` branch. When `pose["atk"] > 0` and there is no gather action, set `anim = "ranged" if ranged else "melee"`, whatever the facing.
   - Delete the `_swing_toward_head(...)` call.
2. Delete `_swing_toward_head`, `_dragon_aim_point`, `_melee_hand_tip`, `_rotate_about` and `_MELEE_ANCHORS`, after a grep shows nothing else uses them.
3. In `player_hd_client`:
   - Make the strip lookup for `melee`/`ranged` use the requested facing (`s`, `n`, `e`, or `w` = flipped `e`). Fall back to `e` only if a file is missing, and log that once.
   - Apply `meta["weapon_layers"][i]["z_anim"]` when sorting layers.
   - Load `fx_swing_<weapon>/melee_<facing>.png` for `s`/`n`/`e` and mirror `e` for `w`.
   - Read projectile origins and hitsplat points from `anchors.json` for the actual facing.
4. While attacking, pass `hit_t=-1.0` to `draw_player`. The hit flash still shows through the existing tint. When not attacking, keep the current `hit_t` behaviour.
5. py_compile, commit "hd player: real melee/ranged frames in s/e/n/w".

## Step 3: use the new frames everywhere, not just Emberdeep
1. Find every place the HD player is drawn attacking:
   - the overworld and the other dungeons in `client/client.py` and the shared combat draw;
   - `grep -n "_combat_facing\|pose_attack\|\"melee\"\|ranged" client/*.py`.
2. In each HD path, where the facing is now forced to the side (`±1`), use the same rule as Step 1: the dominant screen axis toward the target's nearest body tile, with hysteresis.
   - Move `_target_point` and the facing rule into one shared helper, e.g. `client/hd_combat_facing.py`, and call it from both.
   - A multi-tile monster uses its footprint; a single-tile monster uses its own tile.
3. The 2D player keeps its current side-only logic. Branch on the existing player 3D/2D setting only, and do not add a flag.
4. py_compile, commit "hd player: 4-facing attacks toward the nearest target tile everywhere".

## Step 4: keep the swing on screen
1. Keep `_separate_feet` as it is for normal monsters. For the wyrm, make sure the dragon's HP bar or nameplate never covers the player's sprite rect. If the bar's rect overlaps the player's head rect, move the bar up by the overlap.
2. Do **not** add any occlusion to the local player or the swing.
3. py_compile, commit "emberdeep: wyrm labels never cover the attacking player".

## Step 5: test from every camera yaw (keep the 8-angle test)
Add `game/assets/mmorpg/tools/ember_dragon_hit_test.py`. Run it with `SDL_VIDEODRIVER=dummy`. It needs no network and no server.

1. Build a minimal fake client:
   - `pygame.display.set_mode((MAP_W, MAP_H))`;
   - `dungeon = {"id": "emberdeep", "boss_door": ...}`;
   - `tiles = emberdeep.generate_floor_tiles(1)`;
   - `player = {"id": 1, "x": 22, "y": 5, "gender": "male", "equipment": {"weapon": "bronze_sword"}, "hd_player": True}`;
   - `monsters = {9: {"id": 9, "type": "emberdeep_wyrm", "x": 22, "y": 3, "hp": 100, "max_hp": 100, "alive": True, "facing": "s", "name": "Emberdeep Wyrm"}}`;
   - `combat_target_id = 9`;
   - `_attack_progress` returns the progress under test.
   - Reuse the attribute list the smoke test needs. Stub `draw_hp_bar`, `blit_nameplate`, `blit_combat_level`, `monster_threat_color` and `facing_for_view`.
2. Run every combination of:
   - yaws `0, 45, 90, 135, 180, 225, 270, 315` degrees (set `_ember_yaw` and `_ember_yaw_draw`);
   - zoom 0.35;
   - attack progress `0.0`, `0.34`, `0.48` and `0.62`.
3. For each combination, draw one frame through `draw_first_person`. Wrap `player_hd_client.draw_player` to capture the anim, facing and strip file it used, then call the real one.
4. **Assert** for each frame:
   - The anim is `"melee"`.
   - The facing matches the dominant screen axis toward the dragon's nearest body point:
     - `1`/`-1` with the sign of `dxs` when `abs(dxs) > abs(dys)`;
     - otherwise `"front"` when `dys > 0`, else `"back"`.
     - Allow the hysteresis margin.
   - The strip file used is `melee_<s|n|e>.png` for that facing, never an `idle` strip and never `e` standing in for `s`/`n`.
   - The frame index changes across the four progresses, so the body really swings. The 0.48 frame is index 4.
   - Across the 8 yaws, at least one case each hits `front`, `back` and a side facing. If the geometry cannot produce one, add a case that places the dragon so it does.
5. **Visibility**: render the same frame twice, once normally and once with the player draw skipped. Measure the changed pixels inside the player's rect (feet ± 0.6 tile wide, 2.2 tiles tall).
   - They must cover at least 25% of the rect at every yaw, so the body is visible.
   - At progress 0.48:
     - **side facings**: changed pixels must appear on the dragon's side of the player's centre line;
     - **front/back**: changed pixels must appear outside the player's idle silhouette, meaning the arm and blade are visible over the shoulder or across the body.
6. Add one extra case with the player on the footprint corner at (25, 5), to check the nearest-body-point rule.
7. Add one **overworld** case with a single-tile goblin straight south, north, east and west of the HD player. Assert facing `s`/`n`/`e`/`w` and anim `melee`. Repeat it with the 2D player setting and assert the 2D path is unchanged (side facing).
8. Save each frame to `/tmp/ember_hit_<yaw>_<progress>.png`, plus a contact sheet at `/tmp/ember_hit_sheet.png`.
9. Print a PASS/FAIL table and exit non-zero on any failure. Run it and fix until everything passes.
10. py_compile, commit "hd player: 4-facing attack test across 8 camera yaws".

## Report
Give:
- the test table;
- the contact sheet path;
- what David should check in game.

In game: attack the dragon from the front, then rotate the camera all the way round. The player should face the dragon's nearest body tile, whether front, back or side, and play the full swing. The blade should reach toward the dragon on the contact beat. Then attack a goblin from each of the four sides in the overworld.
