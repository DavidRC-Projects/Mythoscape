# Emberdeep UX: HD follow camera, wall occlusion, combat spacing and animations, roaming wyrm, wall detail

You work **directly on `main`** in `/Users/davidcarr/Mythoscape`. Code is in `game/assets/mmorpg/`.
Make **one small step at a time**. After each step, run `python3 -m py_compile` on every file you touched, then commit and push to `main` with a short message. Do not open branches or PRs.

## Run order (read first)
`CUSTOMISATION_FIX_CURSOR_PROMPT.md` edits `client/client.py` and `client/cosmetics_ui.py`, and is in progress. **Finish and push it first.** Start this prompt only when `git status` shows no modified tracked files under `game/assets/mmorpg/`. This prompt touches `client.py` only in the few places listed in Steps 2, 4 and 5. Do not touch `cosmetics_ui.py`.

## Hard rules
- **Never touch the walk cycle.** Do not edit `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid` or `draw_humanoid_detailed`. You may *call* them.
- **Keep the combat timing.** Server tick `TICK_SECONDS = 0.6`. Client `ATTACK_ANIM_SECS = 1.05`, `RANGED_ANIM_SECS = 0.72`, melee contact at progress `0.48` (ranged 0.58). Emberdeep creature `attack_cooldown = 1.2`; wyrm breath cooldown 2.4 with the one-tick telegraph in `_ember_cones`. Every animation below is a pure client visual keyed to these numbers. No server damage or timing changes.
- **No feature flags.** Do not add any. Leave existing flags alone.
- Keep changes small. Keep the existing public function names in `emberdeep_v2_client.py` (`fp_active`, `draw_first_person`, `pick_tile`, `draw_magic`, `adjust_zoom`, `set_zoom`, `zoom_label`, `zoom_control_layout`, `draw_zoom_controls`, `turn`, `step_delta`, `strafe_delta`, `wyrm_swing_tiles`, `wyrm_approach_goals`), so the hooks in `client.py` keep working. Change their bodies, not their call sites, unless a step says otherwise.

## Assets (already in the repo, `game/assets/emberdeep_hd/`)
- `textures/`: `wall_stone.png`, `wall_stone_b.png`, `wall_stone_lava.png`, `floor_flagstone.png` (spans 2×2 tiles), `wall_top.png`, `wall_base_trim.png` (512×96), `wall_cap_trim.png` (512×64), `lava_flow.png`, `torch_sconce_strip.png` (4 frames of 96×160 RGBA) and `door_boss.png` (512×1024 carved gate pillar with ember runes, one tile wide × full wall height). All except the door tile seamlessly.
- `dragon/`: the wyrm as rendered Blender frames. `{anim}_{facing}.png` strips of 768×512 RGBA frames, left to right: `idle` 4, `walk` 8, `breath` 8, `hit` 3, `death` 8, for facings `s`, `e`, `n`, `w` (all four are real renders, **never mirror**). `dragon/meta.json` holds the frame size, `feet_px` [384, 330], fps per anim and the breath release frame (4). Every frame has the same scale and feet point, so frames swap with no jitter.
- `reference/emberdeep_view3d.py`: a working numpy renderer (class `EmberView3D`). Its docstring describes the API. It is tested: on a slow Linux box it renders 400×250 in about 60 ms and 320×200 in about 34 ms.
- `previews/cam_close.png`, `cam_mid.png`, `cam_far.png`, `cam_lair.png`, `cam_lair_breath.png`, `emberdeep_camera_zoom_sheet.png`: the target look (HD player in coloured clothes, rendered wyrm frames). `previews/dragon_frames_sheet.png` shows every dragon frame.
- `tools/`: the scripts that made the textures and previews. Do not run them in the game.

## Why it feels bad now (root causes)
1. `emberdeep_v2_client.draw_first_person` (about lines 1437–1554) is a Wolfenstein-style raycaster that runs **per pixel in Python** (`for col…: for y…: pix[col, y] = …`). That is about 144k Python iterations per frame, so the frame rate is low. A raycaster can only see the first wall in each column, so it **can never show neighbouring rooms**. The "zoom" (`_ZOOMS`, lines 27–31) only raises a fake eye and widens the FOV to 120–145°, which gives fisheye distortion. `_eye()` (471–481) pulls the camera in to the nearest wall, and `_advance_camera` (455–468) snaps per tile.
2. Combat: `_draw_billboards` (1086–1091) pulls every adjacent monster out of the world. `_draw_opponents` (1179–1216) then redraws them at 2.4× player size, stacked just above the player's feet on screen, so they overlap the player and hide the room. `pick_tile` (1601–1604) shoves sprites sideways to match.
3. In Emberdeep the player is drawn with the old 2D `draw_humanoid_detailed` (`_draw_local_player`, 1039–1049) and is always forced to face `"back"` (`_local_draw_args`, 431–440). The HD player is never used and the swing is hidden behind the body. Dead monsters vanish instantly, because only HD knights have corpses (`client.py` DEATH handler, about 687–705).
4. The wyrm is static by design. `emberdeep_creatures.build` sets `static=True, speed=0, wander_radius=0`. `_ember_cones` (`server.py` about 5305) uses the **manifest's fixed cone tiles**. The client always draws `idle_front` (`emberdeep_creatures_client._frame`, 69–74) and adds raycaster workarounds (`_sprite_world` +1.55 y, `_ember_nest_drop`).
5. Walls use 256 px placeholder textures (`emberdeep_v2_pack/fp/*.png`, flat squares), with no trim, contact shadow or real lighting.

---

## Step 1: add the renderer module (no wiring yet)
1. Add `numpy>=1.26` to `game/assets/mmorpg/requirements.txt`. pygame's surfarray needs it, and it is already installed on David's Mac (2.1.3).
2. Copy `game/assets/emberdeep_hd/reference/emberdeep_view3d.py` to `game/assets/mmorpg/client/emberdeep_view3d.py`. Change only the texture loader so it uses `pygame.image.load` + `pygame.surfarray.array3d(...).swapaxes(0, 1)` (PIL is optional). Keep the class and API as they are.
3. Boss door: the renderer already loads `door_boss.png` from the texture folder and puts it on the wall blocks around the door cell. Construct it with `boss_door=client.dungeon.get("boss_door")` (K is (22, 7) on floor 1). Do not use the old `emberdeep_v2_pack/fp/door_boss.png`.
4. Texture folder: `game/assets/emberdeep_hd/textures/` (resolve it relative to the mmorpg folder the same way the other packs are resolved).
5. py_compile, commit "emberdeep: add numpy view3d renderer".

## Step 2: camera rig and smooth zoom
In `client/emberdeep_v2_client.py`:
1. Module state: `_VIEW = None` (an `EmberView3D` per `id(client.tiles)`; rebuild when the tiles object changes) and `_FRAME = {}` (the cached scaled frame plus the camera state it was rendered with).
2. Zoom becomes continuous:
   - `client.ember_zoom` is a float target from 0.0 to 1.0, defaulting to 0.35.
   - `client._ember_zoom_cur` eases toward it at `1 - exp(-dt*10)`.
   - `adjust_zoom(client, delta)`: `target = clamp(target - delta * 0.10)`. Negative delta zooms out, as now.
   - `set_zoom(client, level)` maps the three buttons 0/1/2 to 0.0/0.5/1.0.
   - `zoom_label` shows "Near", "Mid" or "Far" for the nearest preset.
   - Delete `_ZOOMS`, `apply_zoom`, `_EYE_BACK`, `_HORIZON`, `_CAM_Z`, and the module globals they write. `pick_tile` and `draw_first_person` must stop calling `apply_zoom`.
3. In `client.py`, inside the MOUSEWHEEL branch "Wheel over the world map" (about lines 1674–1679), do this only when `emberdeep_v2_client.fp_active(self)`: call `self.adjust_zoom(float(getattr(event, "precise_y", event.y)))` so trackpads zoom smoothly. Leave the other branches as they are.
4. Follow camera:
   - Focus eases toward the player's tile centre with a time constant of 0.12 s, which removes the per-tile snap.
   - The drawn yaw eases toward `client._ember_yaw` the same way. `turn()` keeps its 15° steps.
   - Call `view.set_camera(fx, fy, yaw, zoom_cur)`, then `view.ease(dt)`.
   - Zoom 0 is just behind the shoulder at a 30° pitch, 3 tiles back. Zoom 1 is 78° pitch, 15.5 tiles back. Both are already built into `EmberView3D.PITCH`/`DIST`/`VFOV`.
5. `draw_first_person`: replace the whole pixel loop with:
   - `rgb, depth = view.render(rw, rh, now)`, at an internal size of `rw, rh = MAP_W*0.42, MAP_H*0.42` (rounded to ints).
   - `pygame.surfarray.make_surface(rgb.swapaxes(0, 1))`, then `smoothscale` it to the map size and blit.
   - **Re-render only when** the focus has moved more than 0.005, the yaw more than 0.002 or the zoom more than 0.002, when heights are still easing, or when 1/15 s has passed (for lava and flicker). Otherwise blit the cached frame.
   - Perf guard, which is not a flag: if the average render time over 30 renders goes above 45 ms, lower the internal scale by 0.04, down to a minimum of 0.30.
   - Keep `_draw_corner_map` and `draw_zoom_controls`.
6. Re-implement `_project(...)` as a thin wrapper around `view.project(wx, wy, 0)`. Convert render pixels to map pixels by multiplying by `MAP_W / rw`, and return `(depth, sx, sy, px_per_tile * scale)`. `_draw_hitsplats`, `_draw_projectiles` and `draw_magic` then keep working unchanged.
   - `_draw_tile_highlight`: project the 4 floor corners with `view.project`.
   - Delete `_eye`, `_advance_camera`, `_feet_y`, `_tile_px` and `_cast` only once nothing references them.
7. `pick_tile`:
   - First test the sprite hit rects recorded during the last draw.
   - Then call `view.pick(mx / scale, my / scale)`.
   - The corner-map click stays as it is.
8. py_compile, commit "emberdeep: behind-and-above camera with smooth zoom". At this point the room renders and sprites may still use the old sizes.

## Step 3: walls never block the view
1. The cutaway is built into the renderer (`_cutaway` and `ease`). Walls within 1.6 tiles of the camera→player line, and walls within 2.2 tiles of the player on the camera side, sink to a 0.30-tile stub over about 0.2 s. Their tops still show, so the room shape stays readable. Call `view.ease(dt)` every frame.
2. Per-pixel sprite occlusion: after drawing each monster or prop, get `mask, (ox, oy) = view.occluders(x0, y0, x1, y1, depth)` for its render-space rect. Re-blit the cached background through the mask: build a small RGBA surface from the background subsurface and set its alpha to `mask*255` with `pygame.surfarray.pixels_alpha`. Walls in front then cover monsters correctly, as the wyrm behind the lair wall shows in `cam_lair.png`.
3. Draw the local player last and never occlude them, because the cutaway guarantees they are visible.
4. py_compile, commit "emberdeep: wall cutaway and sprite occlusion".

## Step 4: combat spacing and visibility
1. Delete the adjacent-monster lineup:
   - the `beside … fighting.append … continue` block in `_draw_billboards`;
   - `_draw_opponents`;
   - the sideways shove in `pick_tile`.
   Every monster draws at its projected world tile. The server already keeps melee foes one tile away: `process_dungeon_ai` → `step_toward` only while `dist > 1`, and `can_stand` excludes the player's tile.
2. Sizes:
   - Use `px_per_tile` from the projection everywhere.
   - Body heights come from `emberdeep_creatures_client.creature_height(type, px_per_tile)`.
   - Remove the old `max(tile_px, 72)`, `max(tile_px, 78)` and `min(max(tile_px, 64), 72)` floors and caps.
3. Gap guarantee: if a monster's screen rect overlaps the player's by more than 35% horizontally and their depths differ by less than 0.6, offset its *drawn* position 0.35 tile further from the player along the player→monster vector. If they are on the same tile, offset sideways relative to the camera. Draw only; do not move it on the server.
4. Combat framing: while `client.combat_target_id` is alive and within 3 tiles, ease the camera focus 35% of the way toward the target and keep the zoom at 0.25 or more, so both bodies and the gap between them are in frame. Ease back when combat ends.
5. HP bar, nameplate and level go above the projected head (`creature_height`), and `_ember_screen_anchor` is updated as now, so hitsplats follow.
6. py_compile, commit "emberdeep: monsters stand a tile apart and stay visible".

## Step 5: visible attack, hit and death animations (client only)
Add a small helper module, `client/ember_combat_fx.py`, and call it from `emberdeep_v2_client`.
1. **Monster attack** (progress `p = client._attack_progress(mid)`, duration `ATTACK_ANIM_SECS`). Offsets are in world tiles along the monster→player vector and are applied *before* projection:
   - wind-up `p < 0.30`: lean back 0.08 and squash 0.94;
   - lunge `0.30–0.48`: forward 0.28 and stretch 1.06;
   - contact at **0.48**: a spark burst at the midpoint, plus a 2 px screen shake for 0.08 s if the local player was hit;
   - recover `0.48–1.0`: ease back to 0.
   This works for every draw path, because only the feet point changes.
2. **Hit reaction**: in `client.handle_combat_event` (client.py about line 990), set `self.monster_hit_at[def_id] = now + strike_t * anim_secs` for `player_hits_monster` / `pet_hits_monster` with damage > 0. This mirrors `knight_hit_at`; initialise the dict in `__init__`. For 0.25 s after that time:
   - knock back 0.12 tile away from the attacker;
   - flash: draw the creature into a temp SRCALPHA surface, then `fill((110, 40, 30), special_flags=BLEND_RGB_ADD)` at 60%→0 strength.
3. **Death**: in the DEATH handler (client.py about lines 687–705), when `self.dungeon` is Emberdeep and the type is **not** handled by `knights_hd_client`, append to `self.ember_corpses` `{type, x, y, face, t0}`. Draw it for 1.0 s:
   - topple, by rotating the temp surface 0→80° away from the player;
   - sink 0.2 tile;
   - alpha 255→0 from 0.5 to 1.0 s;
   - 6 ember particles.
   HD knights keep their own corpse path.
4. **HD player in Emberdeep**: replace the body of `_draw_local_player` with the same call `client.py` uses for the local player in the world (about lines 5955–5985): `player_hd_client.draw_player(screen, gender, appearance, sx, sy_feet, tile, t, anim=…, progress=…, facing=…, hit_t=…, death_t=…, equipment=eq)`. Respect `hd_player`. Fall back to `draw_humanoid_detailed` (called, not edited) when it returns False. Factor the shared bit into a small helper if both sites need it; do not change the world call's behaviour.
5. **Player facing in combat** (in `_local_draw_args`): while attacking or with a live target, face the target *as seen on screen*:
   - `|dx_screen| > 0.35 × body width` → `1` / `-1`;
   - otherwise `"back"` if the target is deeper than the player, else `"front"`.
   Walking keeps the current back, strafe and reverse rules. The HD `melee`/`ranged` anims and swing FX then show the player's attack.
6. Wyrm breath FX: the dragon frames carry the mouth flame; the long cone stays an in-world FX. Draw `emberdeep_creatures_pack/fx/fire_cone.png` projected over the current cone tiles **only from breath frame 4 to frame 7** (the 0.6 s tick when damage lands, see Step 6), rotated to the wyrm's facing, with a light flicker on the floor tiles. During frames 0–3 (the telegraph) draw only a faint red floor glow on the cone tiles so players can step out.
7. The monster attack lunge (5.1) and the hit knock-back (5.2) are **not** applied to the wyrm; its frames carry that motion. The hit flash (5.2) still applies over its frame.
8. py_compile, commit "emberdeep: attack, hit and death animations".

## Step 6: the wyrm roams its lair
The server is the source of truth. The client can import `emberdeep_creatures`, because `client.py` puts `../server` on `sys.path`. Use it for the swing and cone rules, so client and server match.
1. In `emberdeep_creatures_pack/manifest.json` → `boss`, add `"lair": {"x0": 18, "y0": 1, "x1": 26, "y1": 6}` and `"posts": [[21,2],[22,2],[23,2],[21,3],[22,3],[23,3],[21,4],[22,4],[23,4]]`. Keep `anchor` (22, 3) as the spawn. The footprint is anchor ±2 in x and ±1 in y, so the wyrm never covers row 6 or the door K (22, 7).
2. In `server/emberdeep_creatures.py` add:
   - `footprint(ax, ay)`;
   - `cone_tiles_for(ax, ay, facing)`, where south is rows `ay+2, ay+3` and cols `ax-2..ax+2`, and east/west is cols `ax±3, ax±4` and rows `ay-2..ay+2`. Clip to lair floor tiles.
   - Generalise `swing_tiles` to `swing_tiles(cone_tiles, footprint=None)`: the cone plus every floor tile 8-adjacent to the footprint. With no footprint it keeps the old rule.
   - `wyrm_tick(monster, tiles, players_xy, tick)`:
     - Do nothing while `monster._cone_pending` is set (the breath telegraph).
     - **No player in the lair** (lair box plus row 7): every 3 ticks, step to a random neighbouring post (±1 in x or y). Face east/west for x moves; keep the facing for y moves.
     - **Player in the lair**: every 2 ticks, step one post toward the post that puts the player in a cone. Facing is south if `py > ay + 1`, else east if `px > ax`, else west. Turning uses a tick without moving, and set `monster._turned_tick = tick`.
     - Never move onto a post whose footprint covers a player's tile.
     - After a move or turn, set `monster.stats["cone_tiles"] = cone_tiles_for(...)` and `monster.stats["facing"] = facing`, then update `monster.x, monster.y`.
     - The wyrm cannot leave the lair or get stuck, because the posts are prevalidated and it stays put when no move is valid.
3. In `server.py`:
   - In `_ember_cones`, call `wyrm_tick` before the breath logic.
   - Replace the manifest `cones` set with `{tuple(p) for p in monster.stats["cone_tiles"]}`.
   - Do not breathe on the tick right after a turn (`tick - monster._turned_tick < 1`), so players see it turn.
   - In `_ember_wyrm_can_hit`, pass the footprint.
   - In `MonsterInstance.public_state`, also send `facing` when stats has it.
   - Leave `static=True`, so the generic AI never moves the wyrm.
4. Client:
   - `wyrm_swing_tiles` / `wyrm_approach_goals` call the server helpers.
   - Remove `_sprite_world`'s `+1.55` and all `_ember_nest_drop` code.
   - Interpolate the wyrm's drawn position over 0.6 s between updates.
5. py_compile, commit "emberdeep: wyrm roams its lair and turns to breathe".

## Step 6b: the wyrm uses its rendered frames (no code-driven moves)
In `client/emberdeep_creatures_client.py` (wyrm only; other creatures are unchanged):
1. Loader: read `game/assets/emberdeep_hd/dragon/meta.json`. Load each `{anim}_{facing}.png` strip **lazily** on first use with `pygame.image.load(...).convert_alpha()`. Cut it into `meta["anims"][anim]["frames"]` frames of 768×512. Scale each frame once to the current draw size with `smoothscale`, bucketing the height to multiples of 16 px. Cache by `(anim, facing, i, bucket)`, keep at most 3 buckets and drop the unscaled source strip after cutting. All 124 full-size frames would be about 190 MB, so never keep them all unscaled.
2. Size and anchor: `WYRM_TILES_H = 4.8` (one constant, not a flag): the full 512 px canvas is `4.8 × px_per_tile` tall. Blit so canvas pixel `feet_px` (384, 330) lands on the projected ground point of the wyrm's anchor tile centre. Do not use `creature_height` or the 280 px cap for the wyrm. Put its HP bar and name `3.0 × px_per_tile` above the feet point.
3. Facing: `public_state["facing"]` (`s`, `e`, `w`, or `n`), default `s`. `w` is its own file; delete the mirroring.
4. Which animation, checked in this order each frame:
   - **death**: when the wyrm dies, play `death` once at 8 fps and hold the last frame for 2.5 s, then fade out over 0.5 s. This replaces the Step 5.3 topple for the wyrm.
   - **breath**: when the `EMBER_CONE` telegraph arrives (the tick before the hit), set `breath_t0 = now`. Frame = `int((now - breath_t0) / 0.15)` for 0–7. Frame 4 starts at 0.6 s, which is the next server tick, when the cone damage lands. Then return to idle.
   - **hit**: for 0.3 s after `monster_hit_at[wyrm_id]`, play `hit` at 10 fps, unless breathing.
   - **walk**: while the interpolated draw position is moving (Step 6.4), loop `walk` at 10 fps. Keep the frame phase continuous between moves so the legs do not restart every tile.
   - **idle**: otherwise, loop `idle` at 6 fps.
   - A melee swing (`wyrm_swing_tiles`) plays breath frames 1→3→7 over the attack's `ATTACK_ANIM_SECS` (rear back, then snap) with no fire, since only the cone breath shows the flame.
5. Delete the old wyrm drawing: `idle_front`, `idle_side`, `fire_breath_*` from `emberdeep_creatures_pack/emberdeep_wyrm`, the mirroring, and any code bob, sway, squash or rotation of the wyrm sprite. The occlusion mask from Step 3 still applies.
6. py_compile, commit "emberdeep: wyrm uses rendered frame animations".

## Step 7: wall detail polish
Most of this comes with Steps 1–2, because the renderer already does:
- stone ashlar with mortar, two stone variants and lava-veined stone next to lava;
- a 0.22-tile base plinth and a 0.14 cap trim;
- floor contact AO, wall-base darkening, deep-rock darkening;
- baked torch and lava light, a player lantern, and distance fog.
Add only:
1. **Torches**: billboard `torch_sconce_strip.png` at every `view.torches` entry, with the face point at z = 1.25. Cycle the 4 frames at 8 fps, offset each torch's phase by its position, and apply the occlusion mask. They must line up with the baked warm light.
2. Pack props (`emberdeep_creatures_client.draw_prop`) are drawn at the projected size with occlusion. Remove the old `max(tile_px, 78)`.
3. Remove the now-unused raycaster texture code (`_wall_name`, `_sample_floor`, `_paint_theme`, `_theme_tex`, `_theme_at`, `_sconces`, `_candle`, `_warm`), but only once nothing references it.
4. py_compile, commit "emberdeep: torches and prop occlusion; remove raycaster".

## Step 8: smoke test
Add `game/assets/mmorpg/tools/ember_view_smoke.py`. With `SDL_VIDEODRIVER=dummy`, it should:
- load the v2 floor through `server/emberdeep.generate_floor_tiles(1)`;
- build `EmberView3D`;
- render zoom 0, 0.5 and 1 at spawn and next to the lair;
- save the PNGs under `/tmp`;
- print the ms per render.
Run it and report the timings in your final message. Then list what David should check in game:
- the wheel zooms smoothly from near to far;
- walls sink between the camera and the player;
- foes stand a tile away and lunge at the contact beat;
- corpses fall;
- the wyrm walks with its walk frames, turns (all 4 facings, real back view), rears back for 0.6 s and releases fire exactly on the damage tick, flinches when hit and plays its death;
- the boss door pillars show the carved rune texture;
- torches flicker.
