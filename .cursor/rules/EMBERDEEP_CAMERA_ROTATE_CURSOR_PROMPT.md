# Emberdeep: free camera rotation and easy navigation

You work **directly on `main`** in `/Users/davidcarr/Mythoscape`. Code is in `game/assets/mmorpg/`. Take one small step at a time. After each step, run `python3 -m py_compile` on every file you touched, then commit and push to `main` with the message given. No branches or PRs.

## Run order
- `EMBERDEEP_UX_CURSOR_PROMPT.md` and `EMBERDEEP_DRAGON_HIT_FIX_CURSOR_PROMPT.md` are **already applied** (commits `3e7e4cb3`…`9fd76de5`, `65b7be1f`…`8d764056`). Do not re-run them.
- Many tracked files are modified but not committed, including `client/client.py`, `client/emberdeep_v2_client.py` and `server/*`. Before Step 1, ask David to commit or stash that work. Run this prompt only when `git status` shows no modified tracked files under `game/assets/mmorpg/client/`. Don't overwrite or revert those changes.
- This prompt does not depend on the other prompts in `.cursor/rules/`. If one of them touches `client.py` input handling and is still pending, run it after this one.

## Hard rules
- **Never touch the walk cycle**: `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
- **Keep the combat timing**: `TICK_SECONDS 0.6`, `ATTACK_ANIM_SECS 1.05`, `RANGED_ANIM_SECS 0.72`, contact at 0.48 (ranged 0.58), `STEP_SECONDS`, `_begin_key_step` and the server walk rate are all unchanged. This is client-side only. No server changes.
- **No feature flags.** The "Camera follows behind" item in the existing settings panel is a user setting, not a flag.
- Do not change the overworld camera or overworld input. Every change is gated by `emberdeep_v2_client.fp_active(self)`.

## Why navigation feels hard today (root causes, all in the current code)
1. **Tank controls with a 15° yaw.** In `client.py` `_poll_held_walk`, about line 2660, holding ←/→ calls `emberdeep_v2_client.turn` every 0.08 s, which spins about 190°/s in 15° steps (`_YAW_STEP = math.radians(15)`). The KEYDOWN branch (about line 1460) also turns on the same press, so one tap can turn twice. ↑/↓ and W/S walk "forward", so the view and the walk are the same control.
2. **Moves snap to the nearest axis, so diagonal yaws break.** `step_delta` / `strafe_delta` pick whichever of x or y is larger in the look vector. At 45°, 135° and so on (reachable in 15° steps), forward and strafe both resolve to the **same axis**, so W and D walk the same way. Near those angles the direction flips between axes as the yaw eases.
3. **Misclicks walk you somewhere random.** `pick_tile` returns `cam.pick(...)`, which is `None` for a click on a wall top, the void or the sky. `screen_to_tile` (client.py about line 3218) then **falls through to the top-down picker** (`camera_origin() + mx // TILE`), which returns an unrelated tile, and the player walks off in a strange direction.
4. **Click picking on monsters ignores what is drawn.** `pick_tile`'s monster loop uses `_sprite_world` (the server tile) and a square box. It ignores the wyrm's glide position and its 4.8-tile canvas, so clicking a gliding monster or the dragon's body often picks the floor behind it.
5. **The camera moves on its own in combat.** `_ease_follow` pulls the focus 35% toward the combat target and forces zoom ≥ 0.25 whenever a foe is within 3 tiles. The view lurches when fights start or end.
6. **There is no way to look around with the mouse.** Middle mouse is "unused (camera is fixed)" (client.py about line 1797), there are no rotate buttons and no compass, and the yaw resets to 0 whenever the client object is rebuilt.

Picking itself is correct at any yaw when it does hit. `EmberView3D.pick` ray-casts against the last render's depth buffer. The wall fade (`_cutaway`) already follows the camera position at any yaw. The camera never auto-snaps behind the player today; the follow-behind behaviour below is new and opt-in.

---

## Step 1: one yaw model with smooth easing
In `client/emberdeep_v2_client.py`:
1. Replace `_YAW_STEP` with `_ROT_STEP = math.radians(45)`.
2. `turn(client, direction)`:
   - Snap the **target** yaw to the next 45° multiple in that direction: `target = (round(yaw / step) + direction) * step`, where `yaw` is the current target.
   - Keep a 0.18 s repeat guard (`_ember_turn_at`) so a held key steps about 5 times a second, not 12.
   - Set `client._ember_user_rot_at = now`.
3. Add `orbit(client, d_yaw_rad)` for mouse drags. It adds to the target **and** to the drawn yaw (`_ember_yaw_draw`), so dragging feels 1:1 with no easing lag, and sets `_ember_user_rot_at`.
4. Add `reset_north(client)`, which sets the target to 0. The draw yaw eases there.
5. `_ease_follow` keeps the shortest-arc easing it already has, but give the yaw its own constant (`1 - exp(-dt / 0.10)`), so a 45° step settles in about 0.3 s.
6. Optional pitch: add `client._ember_pitch_bias` in −8°…+8°, passed through to `view.set_camera` as an extra argument. In `EmberView3D.set_camera(..., pitch_bias=0.0)`, add it to `pitch` and clamp to 25–80°. Keep the default 0 so nothing else changes.
7. py_compile, commit "emberdeep: 45° eased rotation, orbit and reset-north helpers".

## Step 2: keys
In `client/client.py`, only when `emberdeep_v2_client.fp_active(self)`:
1. **Rotate**:
   - **Q / E** and **← / →** call `turn(self, -1)` / `turn(self, +1)` on KEYDOWN only. Remove the ←/→ turning from `_poll_held_walk`; holding is handled by the KEYDOWN repeat guard plus `pygame.key.set_repeat`, which is already in use.
   - Q (quests tab) and E (equipment) keep their current meaning **outside** Emberdeep. Inside Emberdeep, rotation takes priority. Put the Emberdeep check first in those `elif` chains, and show the panels' shortcut hint as unavailable there.
2. **Move, camera-relative**:
   - W/↑ is forward, S/↓ is back, A is left and D is right, all relative to the **drawn** camera yaw.
   - Replace `step_delta`/`strafe_delta` with one `camera_step(client, fwd, right)`. It turns `(fwd, right)` into a world vector with `lx, ly = sin(yaw), -cos(yaw)` and `rx, ry = cos(yaw), sin(yaw)`, then rounds it to the nearest of the **8** grid directions, so 45° gives a true diagonal and W and D never collapse onto one axis.
   - If the diagonal is blocked (`try_move` refuses it, or either orthogonal neighbour is a wall), try the closer orthogonal component, then the other one.
   - Keep the existing `_begin_key_step` / `STEP_SECONDS` pacing unchanged.
   - Set `_ember_strafe` / `_ember_reverse` from the camera-relative intent, as now, so the player sprite faces the same way.
3. Delete the old `dy == 0 → turn` branch in the arrow KEYDOWN handler.
4. py_compile, commit "emberdeep: Q/E and arrows rotate 45°; WASD moves relative to the camera".

## Step 3: mouse orbit
In `client.py`:
1. Right mouse button or middle mouse button **drag** inside the map, in Emberdeep:
   - On MOUSEBUTTONDOWN (button 2 or 3) set `self._ember_orbit = {"x": mx, "y": my, "moved": False, "button": b}`.
   - On MOUSEMOTION while it is set, call `orbit(self, -dx * 0.0085)`, about 0.5° per pixel. If the pitch option is on, `_ember_pitch_bias += -dy * 0.15°`, clamped. Once the total movement passes 6 px, set `moved = True`.
   - On MOUSEBUTTONUP, if it never `moved` and it was button 3, run the **existing** right-click behaviour (the context menu). This way a right-click still opens menus and a right-drag rotates. Then clear `_ember_orbit`.
   - Replace the "middle mouse unused (camera is fixed)" `pass` with this.
2. Releasing the drag does **not** snap to 45°. The yaw stays where the user left it, and Q/E then step from that angle to the next 45° multiple.
3. Don't start an orbit when the press lands on UI: the sidebar, the corner map, the zoom, rotate or compass buttons, open panels, or chat. Use the same checks that already guard left clicks on the map.
4. py_compile, commit "emberdeep: right/middle drag orbits the camera".

## Step 4: on-screen rotate buttons and a compass
In `emberdeep_v2_client.py`, next to `zoom_control_layout` / `draw_zoom_controls`:
1. Add `rotate_control_layout()`:
   - two 26×26 buttons, "⟲" (left) and "⟳" (right), placed beside the existing zoom buttons;
   - a 40 px round compass just above them, with an "N" needle drawn at `-yaw_draw`, so it points to world north.
   Use the same palette and fonts as the zoom buttons.
2. Clicking:
   - the left or right button calls `turn(-1 / +1)`;
   - the compass calls `reset_north`.
   Hook these into the same place in `client.py` that handles `zoom_control_layout()` clicks (about line 3522), before the map click.
3. Tooltips (if the HUD has a tooltip helper): "Rotate left (Q)", "Rotate right (E)", "Reset to north".
4. py_compile, commit "emberdeep: rotate buttons and click-to-north compass".

## Step 5: click-to-move picks the right tile at any yaw
In `emberdeep_v2_client.pick_tile` and `client.screen_to_tile`:
1. Never fall through to the top-down picker in Emberdeep. When `fp_active` is true and `pick_tile` returns `None`, `screen_to_tile` returns `None` (no walk). Do this with a sentinel: `pick_tile` returns `False` for "in Emberdeep, nothing under the cursor", and `screen_to_tile` returns `None` on `False`.
2. Make sure `view.pick` uses the camera that produced the cached depth buffer. In `_render_cached`, store a copy of `(cam, f, r, u)` with the frame. In `pick_tile`, temporarily restore those vectors on the view, or add `EmberView3D.pick(sx, sy, basis=None)`, before picking. This way a click during a yaw ease or an orbit drag maps to the pixel the user actually sees.
3. Monster picking:
   - Use the rects recorded during the last draw (`_ember_sprite_hits`), which already include the wyrm's real frame rect, first.
   - In the fallback loop, use `_wyrm_glide` for the wyrm and the HD body rect for other creatures.
   - Drop `_sprite_world`-only squares.
4. A wall face resolves to the floor tile in front of it. This is already done in `pick`; keep it. If the resolved tile is unreachable, the existing pathing handles it as now.
5. py_compile, commit "emberdeep: click picking matches the drawn view at every yaw".

## Step 6: the camera stays where the user put it
1. In `_ease_follow`:
   - Remove the forced `zoom = max(zoom, 0.25)` in combat.
   - Reduce the focus pull toward the foe from 0.35 to 0.15, and skip it entirely for 1.5 s after `_ember_user_rot_at` (and while `_ember_orbit` is active), so the view never lurches while the user is looking around.
2. Add a "Camera follows behind" on/off item to the existing settings panel (the `sidebar_settings_rect` panel), default **off**. Store it as `client.ember_follow_behind`. When it is on, and the player has walked at least 2 steps in the same direction, and the user has not rotated in the last 3 s, ease the target yaw toward the walk direction (snapped to 45°) at time constant 0.6 s. When it is off (the default), the yaw never changes on its own.
3. Per session: keep `client._ember_yaw` (and the pitch bias) on the client object, and don't reset them when entering or leaving Emberdeep, changing floors or respawning. Initialise them once in `Client.__init__` (`self._ember_yaw = 0.0`, `self._ember_yaw_draw = 0.0`) instead of relying on `getattr` defaults, so they live for the whole run.
4. Wall fade: `set_camera` → `_cutaway` already uses the camera position, so it works at any yaw. Check that the cutaway runs every frame during an orbit drag. `_render_cached` re-renders when the yaw changes by more than 0.002, so it should.
5. py_compile, commit "emberdeep: camera never moves on its own; optional follow-behind setting; yaw kept for the session".

## Step 7: test
Add `game/assets/mmorpg/tools/ember_camera_rotate_test.py` (`SDL_VIDEODRIVER=dummy`, no server). Reuse the fake-client setup from `tools/ember_dragon_hit_test.py`.
1. **Picking**: for yaws 0° to 315° in 45° steps, and yaw 20°, at zoom 0.0, 0.5 and 1.0:
   - render via `draw_first_person`;
   - for 20 random floor tiles within the view, project the tile centre with `view.project` and convert to map pixels;
   - assert that `pick_tile` returns that tile at least 95% of the time (100% for the tile under the screen centre);
   - assert that a click on a pixel with no floor returns `False`, and that `screen_to_tile` returns `None`.
2. **Movement**: for every yaw above, assert that `camera_step(1, 0)` is a unit grid vector within 22.5° of the camera forward on the floor plane, that `camera_step(0, 1)` is within 22.5° of camera right, and that the two are never equal.
3. **Rotation**: simulate a Q press. The target yaw changes by exactly −45° (mod 360), and the drawn yaw reaches within 1° within 0.5 s of simulated `dt`. A held key gives at most 6 steps per second. A simulated right-drag of 100 px changes the drawn yaw by about 0.85 rad immediately. A right press without motion still calls the right-click menu handler (wrap it). A compass click sets the target to 0.
4. **No auto-snap**: with `ember_follow_behind` off, walking 6 steps in one direction and fighting a foe leaves the target yaw unchanged.
5. **Wall fade**: at each yaw, with the player in a corridor, the wall heights between the camera and the player are below `CUT_H + 0.05` after easing.
6. Print a PASS/FAIL table, exit non-zero on failure, and save `/tmp/ember_rotate_<yaw>.png` plus a contact sheet. Run it, along with `tools/ember_view_smoke.py` and `tools/ember_dragon_hit_test.py` to confirm no regressions.
7. py_compile, commit "emberdeep: camera rotation, movement and picking test".

## Report
Give the test table and the timings. Then list what David should check in game:
- Right-drag or middle-drag spins the view smoothly.
- Q/E, ←/→ and the on-screen buttons turn the view 45° with easing.
- The compass resets the view to north.
- W/A/S/D move the way the screen faces at every angle, including diagonals.
- Clicking any floor tile walks there; clicking a wall top or the void does nothing.
- The view no longer lurches when a fight starts.
- The wheel zoom works as before.
- The angle is remembered for the whole session.
- "Camera follows behind" in Settings turns on the old-style behind-the-player view.
