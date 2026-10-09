# Cursor prompt: wire the HD attackable knights (Mythoscape, directly on `main`)

Read this file first, then `NOTES_KNIGHTS_HD.md` and `manifest.json`. Work **directly on `main`** with small, incremental commits (one per step below). No rewrites.

## Hard rules
- **No feature flags.** The HD knights are permanent and always on. Do not add a toggle, env var or `USE_*` constant.
- **Remove the old look for these six ids** (tint/visual sharing, legacy preview entries, procedural drawers) once the new path is in. Keep anything that other monsters still use.
- **Do not change stats, drops, spawns, aggro, patrol, combat timing or server behaviour.** Only the client drawing and the `visual`/`tint` keys listed below change.
- **Never edit the walk cycle:** `pose_walk`, the walk posing in `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`.
- Paths below are relative to `game/assets/mmorpg/` unless they start with `game/`.

## The art (already in the repo at `game/assets/knights_hd/`)
```
game/assets/knights_hd/assets/<id>/
  meta.json
  sprite_1x/<state>/<facing>/fNN.png   128x144, feet at (64,132)   (40 px tile)
  sprite_2x/<state>/<facing>/fNN.png   256x288, feet at (128,264)  (80 px tile)
  sprite_4x/<state>/<facing>/fNN.png   512x576, feet at (256,528)
  <id>_hero_2048.png (+ _bg.jpg), portrait_bust.png (1024) + portrait_bust_512.png + portrait_bust_bg.jpg
```
- ids: `knight`, `shadow_knight`, `knight_captain_vorn`, `barrow_knight`, `sir_aldric`, `magma_knight`
- states (exact runtime formulas are in each `meta.json` → `states.<state>.runtime`):
  - `idle` 4 frames, loop: `int(((t * 1.5) % 1) * 4)`
  - `walk` 8 frames, loop: `int(((t * 1.15) % 1) * 8)` (same cadence as the HD player walk)
  - `attack` 6 frames from swing progress 0..1 (`_attack_progress`, 1.05 s): wind-up f00–f01, strike f02, **impact f03**, follow-through f04, recovery f05. Use `meta["states"]["attack"]["frame_starts"] = [0, .14, .30, .42, .60, .80]`, so f03 covers 0.42–0.60 and the hitsplat the client already releases at `strike_t = 0.48` lands on the impact frame. **Do not change `ATTACK_ANIM_SECS`, `strike_t` or any server timing.**
  - `hit` 3 frames, 0.36 s (recoil, then settle)
  - `death` 6 frames, 0.9 s (stagger, buckle, fall, impact, settle). After that, hold f05 and fade out over 0.6 s.
- facings: `s` (game `"front"`), `n` (`"back"`), `e` (numeric facing > 0), `w` (numeric facing < 0)
- Scale: a true 175.6 px per metre at 4x (43.9 at 1x), feet bottom-centre at `feet_px`, drawn at `tile/40`. That is the same as the HD player pack. Bosses keep content.py `scale` (Vorn 1.2, Aldric 1.3), and the caller already passes `_ts = TILE * scale`. Always blit using this pack's own `feet_px` and don't reuse npc_hd offsets. (The npc_hd sprite sets were re-rendered with the same camera fix, so NPCs now match too. See NOTES "Scale check".)
- Matches the HD player pack (`player_hd` meta: 43.9 px/m at 1x, feet bottom-centre on the tile foot point). The player and the knights share one scale and one ground line, so they stand side by side without overlapping or floating. Only the boss `scale` makes Vorn and Aldric bigger.
- Every frame has a soft, semi-transparent contact shadow baked in. Do not draw an extra blob shadow under these ids.
- Per-frame anchors in `meta.json → anchors_4x["<state>/<facing>/<NN>"]`: `head_top` (health bar and hitsplat), `weapon_tip` (hit point), `weapon_hand`. Coordinates are 4x canvas px, so divide by 2 for 2x and by 4 for 1x, then scale by `k` like the sprite. `hit_point_4x[facing]` is the blade tip on the impact frame. `healthbar_y_offset_1x` is the idle head-top minus 4 px, relative to the feet.
- Facing in fights: `face_toward_target` already forces ±1 while swinging, so swings use the `e`/`w` frames. `w` is its own render (not a flip), so the sword stays in the right hand and the shield on the left.

## Step 1: check the art is present
`ls game/assets/knights_hd/assets/*/meta.json` must list 6 files, and each `meta.json` must say `"complete": true`. If anything is missing, stop and report back. Don't fall back to old art.

## Step 2: add `client/knights_hd_client.py` (new file, about 90 lines)
- `_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "knights_hd", "assets"))`
- `KNIGHTS_HD = {"knight", "shadow_knight", "knight_captain_vorn", "barrow_knight", "sir_aldric", "magma_knight"}`
- `handles(mtype) -> bool`
- Lazy `meta.json` and image cache: `pygame.image.load(...).convert_alpha()`, then cached `smoothscale` per `(path, size)`. Clear it when it passes 512 entries.
- `draw(screen, mtype, cx, foot_y, size, t, facing=1, moving=False, attacking=-1.0, hurt=False, hit_t=-1.0, death_t=-1.0, alpha=255) -> bool`
  - `size` is the scaled tile (`TILE * scale`, the existing `_ts`). Pick `tag, base = ("2x", 80) if size >= 80 else ("1x", 40)`, with `k = size / base`.
  - Facing: `"back"` → `n`, `"front"` → `s`, numeric < 0 → `w`, numeric > 0 → `e`, anything else → `s`.
  - State priority: `death_t >= 0` → `death` frame `min(5, int(death_t / 0.15))`. Else `attacking >= 0` → `attack`, frame = last index whose `frame_starts` ≤ `attacking`. Else `0 <= hit_t < 0.36` → `hit` frame `min(2, int(hit_t / 0.12))`. Else `moving` → `walk`. Else `idle`. Use the formulas above.
  - `alpha < 255` → `set_alpha` on a copy (used by the death fade).
- `anchor(mtype, size, facing, state, frame, name) -> (dx, dy)`: offset from the feet point in screen px, read from `anchors_4x`. Add `head_top_dy(mtype, size)` = `healthbar_y_offset_1x * size / 40`.
  - Blit so the feet pixel (`meta["feet_px"][tag]` × `k`) lands on `(cx, foot_y)`.
  - If `hurt` is set, blit a copy filled `(255, 80, 80, 80)` with `BLEND_RGBA_MULT` (same as `legacy_creature_sprites._blit_preview`).
  - Return `False` only if the id isn't handled or the file is missing.
- `portrait(mtype, height)` → scaled `portrait_bust_512.png` (same shape as `npc_hd_client.portrait`) for any UI that wants it later.

## Step 3: overworld / dungeon draw chain (`client/client.py`, inside `_draw_mon`)
- Put the HD knight branch **first** in the chain, before `emberdeep_creatures_client.draw_creature`:
  `if knights_hd_client.draw(self.screen, m["type"], cx, cy + TILE // 2, _ts, t, facing=face, moving=draw_moving, attacking=atk_arg, hurt=hurt): pass`
  (`cy` here is after the `castle_sprites.lift_px` adjustment, and `foot_y = cy + TILE // 2` matches `npc_hd_client`.) Turn the current `if emberdeep...` into `elif`.
- Add `knights_hd_client.handles(m["type"])` to the conditions that **skip the red target ellipse**, like the `legacy_sheet` case.
- Import it next to the other sprite modules at the top (`import knights_hd_client  # noqa: E402`).
- In `_draw_mon`, pass `hit_t=now - self.knight_hit_at.get(mid, -9)` (if that is less than 0.36, else -1). For HD knight ids, put the HP bar and nameplate at `foot_y + knights_hd_client.head_top_dy(type, _ts)` instead of the generic `entity_anchor` lift, so tall or boss knights don't have the bar inside the helm. Don't change it for other monsters.

## Step 4: Emberdeep chain (`client/emberdeep_v2_client.py`, `_draw_monster_sprite`)
- Right after `ts` is computed and the `_LEGS` stride offset is applied, add:
  `if knights_hd_client.draw(client.screen, m["type"], cx, cy, ts, t, facing=face, moving=moving, attacking=(atk if (m["id"] in client.attack_anims or str(m["id"]) in client.attack_anims) else -1.0), hurt=hurt): return`
  (`cy` is already the projected foot point in this renderer.)
- Remove `"magma_knight"` from `_LEGS` because the walk frames now carry the step. Leave `_ROOM_THEME` alone, since it's room dressing, not the sprite.

## Step 4b: hit reaction and death (client only; server events are unchanged)
- Hit: in `handle_combat_event`, when `kind in ("player_hits_monster", "pet_hits_monster")` and it hit with `damage > 0` on an HD-knight defender, record `self.knight_hit_at[def_id] = now + strike_t * anim_secs`. That is the same moment its hitsplat is released, so the recoil plays on the splat. `draw` ignores it while the knight is mid-swing (attack wins). Keep the red `hurt` tint.
- Death: on the `DEATH` message with `entity_kind == "monster"`, if that monster's type is an HD knight, snapshot `{type, x, y, facing, t0: time.time()}` into `self.knight_corpses` before the next state update removes it. Draw the corpses in the same pass and depth order as monsters, with `death_t = now - t0` and alpha fading from 255 to 0 between 0.9 s and 1.5 s, then drop them. Don't draw HP bars, nameplates or target rings for corpses. Loot drops are unchanged and still drawn by the existing code.
- Emberdeep (`emberdeep_v2_client._draw_monster_sprite`): pass the same `hit_t`. Draw `client.knight_corpses` whose position is inside the instance at the projected foot point, using the same helper.
- Dungeon instances use the same `DEATH` event (carrying `_dungeon_player`), so the same path covers barrow knights and Sir Aldric.

## Step 5: content (`server/content.py`, client visuals only)
- `knight_captain_vorn`: delete `"visual": "shadow_knight", "tint": (255, 80, 60)` and **keep** `"scale": 1.2`.
- `barrow_knight`: delete `"visual": "shadow_knight", "tint": (160, 200, 170)`.
- `sir_aldric`: delete `"visual": "shadow_knight", "tint": (255, 110, 70)` and **keep** `"scale": 1.3`.
- Touch nothing else in these dicts. `void_v2_client.tint_and_halo` stays, because other monsters still use `visual` and `tint`.

## Step 6: remove the old knight art paths (only for these ids)
- `client/legacy_creature_sprites.py`: drop `"knight"` and `"shadow_knight"` from `_MONSTER_PREVIEW` and `castle_knight`/`shadow_knight` from `_HEIGHT`. Delete `client/assets/sprites/legacy/castle_knight.png` and `shadow_knight.png` only if `grep -rn` shows no other users. Update the module docstring line about Magma Knight.
- `game/assets/characters/procedural_sprites_finished.py`: remove the `"knight"`, `"shadow_knight"` and `"magma_knight"` entries from `MONSTER_DRAWERS` (all `update` blocks plus `MONSTER_DRAWERS["knight"] = draw_knight`). Then delete the final `draw_shadow_knight` and `draw_magma_knight` bodies **only if nothing else calls them**. **Keep `draw_knight`** if any other drawer still calls it (the city guard / elite drawers do; check with grep). Don't touch `draw_humanoid*`.
- Check for leftovers with `grep -rn "shadow_knight\|magma_knight\|castle_knight" game/assets/mmorpg/client game/assets/characters`. Only `knights_hd_client.py`, the room-theme dict and unrelated text should remain.

## Step 6b: side-by-side spacing and projectiles (verify only, no logic changes)
- `barrow_knight` and `sir_aldric` are `side_by_side` with `attack_range 2` and `side_gap 2`. The server parks them 2 tiles from the player on the same row. Their impact frame reaches about `meta["impact_reach_tiles"]` tiles forward, so the knight's blade and the player's weapon meet in the gap (as the existing `humanoid` comment in `handle_combat_event` intends). Don't move them closer.
- The other four fight adjacent (`attack_range 1`, chebyshev). The feet anchor is the tile foot point, so the player and knight never overlap or float.
- The knights fire no projectiles. Player arrows already land with the splat. Optionally aim them at `foot_y + 0.55 * head_top_dy` for HD knights. Don't touch the arrow timing.

## Step 7: verify
- `python -m py_compile` every file you touched.
- Headless smoke test (`SDL_VIDEODRIVER=dummy`): init pygame with a small display, call `knights_hd_client.draw` for every id × state × facing at size 40, 80 and 104 (Aldric 80 × 1.3), and assert it returns True.
- If you can run the game: the Stonehaven keep knights at (128,66), the Void Sanctum shadow knights and Vorn, the Depths barrow knights and Sir Aldric, and the Emberdeep magma knights should all show the HD sprite. Each should walk on patrol, swing on attack with the splat on the impact frame, recoil when hit, collapse and fade on death, and turn left/right/front/back. Bosses should be bigger, feet should sit on the tile, and no red ellipse or tint halo should appear under them.
- Commit each step to `main` with a clear message, e.g. `feat(knights): HD knight sprites always on`. Push `main` and **do not open a PR**.
