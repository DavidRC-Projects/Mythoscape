# Emberdeep creatures — implementation prompt

Pack art, manifest, and this note live in `/workspace/emberdeep/creatures/`. Do not merge or push. Do not change the bank. Game strings use the ids and display names in `manifest.json` only. Do not put Dungeon Keeper or Raid proper names in game strings.

## Flag

Add `USE_EMBERDEEP_CREATURES` next to the other flags, default **off**:

```python
# Emberdeep set-piece creatures and props. Off by default.
# Set USE_EMBERDEEP_CREATURES=1 to spawn the manifest layout.
USE_EMBERDEEP_CREATURES = _on("USE_EMBERDEEP_CREATURES", "0")
```

Use the existing `feature_flags._on`. This flag does not read or change `USE_EMBERDEEP_FIRST_PERSON`. Either flag can be on without the other.

## Step 1 — investigate only, then STOP

Do not edit files in this step. Report what you found and wait until the user says continue.

1. How Emberdeep monsters are spawned. Start at `game/assets/mmorpg/server/emberdeep.py` (`generate_floor_tiles`, `pick_spawn_tiles`, `scaled_monster_stats`, `visual_type_for_floor`, `_FLOOR_VISUAL`) and the dungeon mod table used by `server.py` `_build_dungeon_floor` (it calls `mod.generate_floor_tiles`, `dungeon_props.install`, `mod.pick_spawn_tiles`, `mod.scaled_monster_stats`, `mod.visual_type_for_floor`, then builds `MonsterInstance`s). Note leash / home_room.
2. How the hand-authored grid is loaded, if it is loaded. The grid is `/workspace/emberdeep/v2/interior/emberdeep_v2_floor.txt` (48 by 36, north at the top). `K` is the boss threshold, center of the north doorway, file column 22, row 7. Find where `boss_door` is stored on the dungeon (the first-person client reads `client.dungeon.get("boss_door")`). If server `y` is flipped relative to the file, say so. Manifest coordinates are file columns and rows: `x` from the left, `y` from the top, `y` increases south. Convert only if the loader's origin differs. Do not invent a second map.
3. How monster art is chosen on the client. Check `legacy_creature_sprites.draw_monster` and `characters/procedural_sprites_finished.draw_monster`, and the first-person Emberdeep draw (projected sprites, not a new camera). Note the visual id string the server sends and how facing is picked. Normal dragon sheets stay on their own path.

Stop after the report.

## Step 2 — only after the user says continue

Small hooks. When `USE_EMBERDEEP_CREATURES` is off, behaviour stays as it is now.

When the flag is on:

- Spawn the ids in `manifest.json` on the listed tiles of the v2 floor. One actor per tile. Do not stack. Do not put toads or hounds on the bridge center (`B`, file x 21–23). Do not cover `S`, `E`, `K`, `H`, or `N`, and do not spawn on `#` or `L`.
- Reuse `scaled_monster_stats(level)` for combat numbers. Levels: ember_imp 20, bile_toad 35, cinder_bitch 50, ash_warlock 70, troll_cook 85, mistress_of_cinders 110, emberdeep_wyrm 250. Display names are in the manifest (Cinder Hound for `cinder_bitch`).
- Boss only in the north boss chamber. Anchor and footprint are in the manifest. It is static: speed 0, it does not pathfind, it does not walk. Override max HP to 2500 (the level formula alone is too low). Other stats can follow the level-250 formula.
- Boss attack: on a timer, a fire cone in front of it. Damage players who are standing on `boss.cone_tiles` (south of the mouth, toward `K`, not on `K` itself). Use `fx/fire_cone.png` for the combat FX. This is not a travelling projectile.
- Props: one scenery object per manifest tile (not monsters, not stacked). Two gallery props sit in different niches. Reuse `dungeon_props` if that already places static cells; otherwise a small static record is enough. Do not block the three-tile doors.
- Skip random Emberdeep picks on tiles this pack already occupies so a rolled monster does not stack on them. Do not change spawns in other dungeons.
- Normal dragons elsewhere are unchanged. Do not retune their stats, sheets, or AI.

Art root, copied from this pack (do not rename ids):

`game/assets/mmorpg/assets/emberdeep_creatures/`

Client: when the flag is on, these visuals use the same projected sprite path as other monsters. Do not add a camera. In first person, billboard the facing render that matches the existing facing enum (`front`, `back`, `side_east`, `side_west`). The wyrm is about 2.5 times a normal dragon. Its frames are 768×512; creature frames are 256×256. `idle_contact.png` is a reference strip, not an in-world animation. The wyrm does not use a walk cycle.

## Do not touch

Walk cycle files: `rs_style.py` `pose_walk`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`.

No merge, no push, no bank changes, no copyrighted Dungeon Keeper or Raid names in game strings.
