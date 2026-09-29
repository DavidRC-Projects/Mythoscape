# Unzip characters_pack.zip to /Users/davidcarr/Downloads/characters/ first, then paste everything below into Cursor.

# Cursor prompt: characters, gear looks, Equipment screen (Mythoscape)

You are working in the Mythoscape repo. The 2D pygame client is under `game/assets/mmorpg/` and the characters are in `game/assets/characters/`.
Reference material is in the `characters/` pack: CODE_REVIEW.md, GUIDE.md, ITEM_LOOKS.md, `reference_code/files/*.py`, `reference_code/*.patch`, and before/after PNGs.
Use the reference code as a guide. **Do not paste-replace existing files.**

## Ground rules (every step)
- Put everything behind flags in `game/assets/mmorpg/server/feature_flags.py`: `USE_NEW_CHARACTERS` (default "0"), and later `USE_NEW_EQUIPMENT_UI` (default "0"). The old code path stays intact and is the default.
- Make **small incremental changes**: new files plus tiny hooks. **Never rewrite, restructure or reformat existing functions** (`rs_humanoid.py`, `rs_style.py` and `client.py` are big).
- **Walk animation is frozen. Do NOT touch any of these:**
  - `rs_style.pose_walk`, `pose_idle`, `pose_stand`, `pose_attack`, `pose_ranged`, `resolve_pose`, `unit`, `label_lift`;
  - `client.py` `moving_for`, `facing_for`, `facing_for_view`, `_attack_progress`, `ATTACK_ANIM_SECS`, `RANGED_ANIM_SECS`, the `t = time.time()` source, `entity_anchor`;
  - the joint maths in `draw_skeletal_humanoid` / `_draw_ortho_humanoid` (pelvis, neck, hips, knees, feet, shoulders, elbows, hands, bob, `hand_shift`, lift, stride, phase).
- The new drawer must read the **same** pose and joint values. Copy the joint maths verbatim into `rig_side()` / `rig_ortho()` and change only the shapes drawn on top. Frame count, timing, directions, frame selection, per-frame limb positions and bobbing must be identical.
- Keep the sprite anchor (`cx,cy` = feet) and overall height compatible, so HP bars and name labels stay correct. Hitboxes, targeting and clicks are tile-based and must not change.
- After each step, render before/after screenshots headless (`SDL_VIDEODRIVER=dummy`) using the game's own drawing code, then **STOP and wait for approval**.
- **Never commit to main, never merge, never push, never open a PR.** Work on a local branch only.

## Step 1: investigate only, then STOP
Read and summarise, with file:line references:
- `procedural_sprites_finished.draw_humanoid_detailed`
- `rs_humanoid.draw_skeletal_humanoid` and `_draw_ortho_humanoid` (which lines compute joints and which lines draw)
- `rs_style.resolve_pose` and `pose_walk`
- `client.py` `_draw_pl` and the NPC draw, `entity_anchor`, `draw_equipment_modal`, `handle_equipment_click`
- `procedural_sprites_finished.draw_item_icon`
- `feature_flags.py`

Confirm the walk is continuous-time (no frame indices). **Make no code changes. STOP and report.**

## Step 2: ONE thing, the base body and face on the PLAYER only
1. Add `USE_NEW_CHARACTERS` to `feature_flags.py` (default "0").
2. Create `game/assets/characters/rs_humanoid_v2.py`, based on `reference_code/files/rs_humanoid_v2.py`, with **only**:
   - `resolve()`, `rig_side()`, `rig_ortho()` (verbatim joint maths);
   - the body parts (legs, hips/belt, torso, deltoids, arms, neck, head/face/hair) and the muted palette.
   For gear in this step, keep calling the OLD helpers (`rs_humanoid._draw_weapon`, `_draw_shield`, `_draw_helmet`) with the same positions and arguments as the old code.
3. Hook: in `client.py` `_draw_pl` only (players, not NPCs), when the flag is on, call `rs_humanoid_v2.draw(...)` with the same args. The old call stays in the `else`.
4. Add `tools/walk_proof.py` from the pack. It spies on `rs.draw_volume_limb` during the old draw and compares the new rig joints bit for bit (4 directions, M/F, walk + attack), then writes a sheet and GIF. **It must print PASS with max diff 0.0.**
5. Screenshots: player M/F in 4 directions before/after, plus the walk GIF. **STOP for approval.**

## Step 3 (after approval): NPCs on the new base
Route the NPC path through the flag. The module flag at the top of `draw_skeletal_humanoid` does this; see `hooks_only.patch`. Check robed NPCs, Lira and the herald. Screenshots, then **STOP**.

## Step 4 (after approval): unique armour and weapon looks
1. Add `game/assets/characters/gear_v2.py`, the look table keyed by item id (see ITEM_LOOKS.md). Weapons must use `weapon_transform()`, an exact copy of `_draw_weapon`'s placement and angle maths, so attack swings are unchanged.
2. Switch the v2 drawer from the old gear helpers to `gear_v2` **one slot at a time**, with screenshots after each: weapon, shield, helmet, body, legs.
3. Icons: add `USE_NEW_ITEM_ICONS` in `procedural_sprites_finished.draw_item_icon`. It tries `gear_v2.draw_icon` and falls back to the old icon. The client sets it from `USE_NEW_CHARACTERS`.
4. Add `game/assets/characters/armour_v2.py` (bulk per material; layered pauldrons, gauntlets, faulds, knee cops; royal ornament with filigree, emblems, runes, gems and glow for Mythos/Eclipse). Call it from the v2 limb, torso and hip drawers only, as extra shapes on the same joints.
5. Re-run walk_proof (must PASS at 0.0) and `anchor_check.py` (no helm higher than today's bare head at any zoom). Render gear sets, the weapons sheet, combat attack frames and the eclipse/dragon closeup, before/after. **STOP.**

## Step 5 (after approval): Equipment & Stats screen
1. Add `USE_NEW_EQUIPMENT_UI` (default "0") and a new file `mmorpg/client/equipment_ui_v2.py`.
2. At the top of `draw_equipment_modal`, add `if USE_NEW_EQUIPMENT_UI: equipment_ui_v2.draw(self, ITEMS, karma_slot_bonus, sprites, weapon_style); return`. Leave the old body untouched.
3. Keep:
   - the modal rect (90,36,760,560), because `handle_equipment_click` closes the panel on an outside click;
   - `self.equip_slot_rects` with all 8 slots (click = UNEQUIP);
   - the same data fields, the hover detail text and the footer "Hover a slot for details · Esc / E to close";
   - Esc/E handling as is.
4. Screenshots of empty, steel and mythos loadouts, before/after. **STOP.**

## Definition of done per step
- The flag is off by default, and with it off the game is pixel-identical.
- With the flag on, walk_proof prints PASS.
- Before/after screenshots are shown and approval received.
- Nothing is merged or pushed.
