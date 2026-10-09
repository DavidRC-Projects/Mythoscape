# Cursor prompt: HD player character, cosmetics, armour layers + 3D/2D setting (Mythoscape)

Repo: `DavidRC-Projects/Mythoscape`. Game code lives in `game/assets/mmorpg/`.
Asset pack: `player_hd_part*.zip`. David unzips every part onto the Mac so the pack root is **`game/assets/player_hd/`**:

```
game/assets/player_hd/
  assets/meta.json            canvas / feet anchor / px-per-metre / anim -> frame mapping / compose rules
  assets/catalogue.json       every cosmetic (id, slot, name, price, starter flag, tintable, z per facing, files),
                              defaults for male/female, hair palette, armour + weapon layers, tier tints, override rules
  assets/<male|female>/<1x|2x>/<layer>/<anim>_<facing>.png        sprite strips (frames left->right)
  assets/<male|female>/<1x|2x>/<layer>/<anim>_<facing>_tint.png   neutral-grey part to colour (hair / metal)
  assets/<male|female>/4x/<layer>/idle_<facing>.png (+_tint)      single big frame for creator / shop / wardrobe preview
  assets/anchors.json         per sex/anim/facing/frame: head_top, chest, hand_R, hand_L, weapon tip (for HP bar, hitsplats, projectiles)
  previews/ ...  NOTES_PLAYER_HD.md  src/ (Blender sources, not needed at runtime)
```

This adds an **HD paper-doll player** on top of the existing game. Unlike the NPC packs, the **old 2D procedural player stays**. A **player setting** chooses "HD (3D-rendered)" or "Classic 2D". This is a normal in-game option the player can flip, **not a developer feature flag**, and the 2D path must keep working exactly as today.

---

## Hard rules (read first, apply to every step)

1. **Step 1 is investigation only. Change no files, report back, then STOP and wait for my go-ahead.** After that, do **one step at a time** and stop after each step with a short report and screenshots.
2. **Never edit**, not even whitespace:
   - `pose_walk` and any walk posing in `rs_style.py` (`rs_style.py` is read-only for this whole job);
   - `rs_humanoid.py` and `rs_humanoid_v2.py`;
   - `tools/walk_proof.py`;
   - `draw_humanoid` and `draw_humanoid_detailed`.
3. **Walking stays identical**: movement, speed, tile stepping, step intervals (`try_move` 0.16 s, `update_walk` 0.2 s), `moving_for` (0.55 s hold), `facing_for`, attack timing (`ATTACK_ANIM_SECS`, `RANGED_ANIM_SECS`). The HD code only **draws**. It reads the same `t`, `mov`, `face`, `atk`, `action` values the 2D call gets and picks a frame from them. It never changes them.
4. **Keep the 2D path intact.** The existing `sprites.draw_humanoid_detailed(...)` call stays, with the same arguments. HD is an `if hd_enabled and player_hd_client.draw_player(...): ... else: <existing 2D call>` wrapper. If HD assets fail to load, fall back to 2D silently and log it once.
5. Small hooks only. Put new code in new modules (`client/player_hd_client.py`, `client/cosmetics_ui.py`, `server/cosmetics.py`). Do not reorganise or reformat existing files.
6. **The server is authoritative** for coins, ownership and the equipped look. The client never decides prices. Load prices from `game/assets/player_hd/assets/catalogue.json` on the server.
7. **Work directly on `main`** (David's instruction): no new branch, no PR, no force-push. Commit after each step with a clear message.
8. If something here contradicts the code, trust the code. Report the conflict instead of guessing.
9. Do not move NPCs or tiles. Do not add new NPC spawns without asking.

---

## Step 1: Investigate, then STOP

Report file paths and line numbers for each of these:

- **Player drawing.** All `sprites.draw_humanoid_detailed(` call sites for players in `client/client.py`: self and other players (around `_draw_pl`, ~L5850), plus any login, character-select or stat-alloc preview. Report how `body, skin, hair`, `eq`, `mov`, `face`, `atk`, `action`, `gather` and `gender` are computed (~L5795–5845).
- **NPC HD hook to mirror.** `client/npc_hd_client.py` `draw_npc(...)`: how it loads `meta.json`, picks 1x/2x from `TILE`, anchors the feet, mirrors west and caches surfaces. The player module should copy that pattern.
- **Animation inputs.** `rs_style.resolve_pose(...)` signature, `_attack_progress` (~L6762), `attack_anim_kind` (melee/ranged/magic?), gather `action` names (woodcutting/mining/fishing/...). Read only; no edits.
- **Equipment.** Equip slots on the server and client (weapon, shield, body, legs, helmet, amulet, ring, ammo). Item ids per tier (`bronze/iron/steel/mithril/adamant/mythos/eclipse_*`, `_sq_shield`, `_chainbody`, `_chainlegs`, `leather_*`, `goblin_mail`, `wooden_shield`). `rs_style.metal_palette()` and `_weapon_kind()`.
- **Persistence.**
  - `server/database.py` `players` table: `coins`, `gender`, `equip_*`, `owned_pets`, the `ALTER TABLE` migration pattern and `save_player_stats`.
  - `full_state()` / PLAYER_UPDATE.
  - The per-player data other clients receive (where `p["gender"]` comes from).
- **Options.** The `SET_OPTION` flow (`toggle_auto_pickup` client ~L1722, server ~L2681 / L5179, `auto_pickup_items` column). The HD/2D setting will use the same flow.
- **Shops.**
  - `content.SHOPS`, `send_shop_state`, `handle_shop_buy` and `handle_shop_sell` (~L3876–3970), and which coin source they use (inventory coins vs `coins` column).
  - The pet "owned collection" purchase pattern (re-buying an owned pet is a free switch).
- **Character creation.** Where `gender` is chosen (`create_account`, stat allocation ~L1730) and what screens exist (`client_screens.py`).
- **Settings UI.** Where a player-facing option toggle could live (sidebar settings/help panel `sidebar_settings_rect`, `show_help`). Propose the spot.
- **Shop NPCs.** Propose which existing NPC(s) could host the **Hair Salon** and the **Clothing / Costume shop**. Use existing ids and tiles, and ask me before adding anything new.
- Confirm you will not open the protected walk files for editing.

Then STOP.

---

## Step 2: Asset loader + offline check (no gameplay hook yet)

1. Add `client/player_hd_client.py`:
   - `load()` reads `meta.json`, `catalogue.json` and `anchors.json`, and lazily loads strips with `pygame.image.load(...).convert_alpha()`. It slices each strip into frames of the canvas width (1x 144×144 feet 72,124 · 2x 288×288 feet 144,248 · 4x 576×576 feet 288,496).
     - The scale and feet convention are the same as `npc_hd` (43.9 px/m at 1x, 30° camera).
     - The canvas is only bigger so that sword reach, bow, rod and the death fall are not clipped.
     - Always blit with `meta.feet_px`.
   - `layers_for(look, equipment, gender)` returns the ordered layer list. Apply `catalogue.override_rules`:
     - an outfit hides the top and bottom;
     - a helmet hides the hair, but the brows stay;
     - body armour hides the top and outfit, and plate body adds `arm_gauntlets`;
     - leg armour hides the bottom and outfit, and plate legs add `arm_sabatons`, which replace the shoes;
     - if an outfit is hidden on one half only, show the saved or starter top/bottom on the uncovered half;
     - the shield maps to `arm_kiteshield` and the weapon kind maps to `wpn_*`;
     - skilling swaps in axe/pickaxe/rod for that anim only.
   - `frame_index(anim, t, progress)` must use exactly the mapping in `meta.anims[...].runtime`:
     - idle: `int(((t/π)%1)*8)`;
     - walk: `int(((t*1.15)%1)*8)`;
     - chop: `(t*1.1)%1`;
     - mine: `(t*1.05)%1`;
     - fish: `(t*0.55)%1`.
     - **melee / ranged:** frame = the last `i` with `meta.sample_progress[anim][i] <= progress`.
       - Melee frame 4 is the contact pose at progress 0.48, which is exactly the client's `strike_t` when the hitsplat is released.
       - Ranged frame 5 is the release at 0.55, exactly when the arrow projectile spawns.
     - hit and death are new: see Step 9b.
   - `anim_for(mov, atk, attack_kind, action, weapon_kind, hit_u, death_u)` is the same decision order as `resolve_pose`, with death and hit added around it:
     0. death (if dead);
     1. attack (`atk > 0.02`): `ranged` if `weapon_kind == "bow"` or `action == "archery"` or `attack_anim_kind == "ranged"`, else `melee`. The game has **no stab/slash/crush styles**: `pose_attack` is one swing for every melee weapon, and `combat.py` says "no prayers/styles in v0.1". So there is one melee anim.
     2. then the skilling action: woodcutting → chop, mining → mine, fishing → fish; any other action → idle;
     2b. then `hit` while `hit_u < 1` (only when not attacking or moving);
     3. then walk if `mov`;
     4. else idle.
   - Facing:
     - game `1` → `e`, `-1` → `w` (horizontal flip of `e`), `"front"` → `s`, `"back"` → `n`.
     - melee, ranged, chop, mine and fish only exist for `e`/`w`. The client forces side-on facing for swings (`handle_combat_event`: "Face the defender sideways (±1) — never front/back during a swing"; `attack_face`), and gathering also forces ±1. If the game ever asks for them with front/back, use `e`.
     - hit and death exist for `s`, `e` and `n`, with `w` as the flip of `e`.
   - `compose(...)` sorts layers by `z[facing]` and blits each layer.
     - A tintable layer blits `<layer>` then a copy of `<layer>_tint` multiplied with `BLEND_RGBA_MULT`. The colour is the hair palette `mul`, or the tier colour × `tier_tint_gain`, clamped to 255.
     - Cache composed frames in an LRU keyed by (look hash, gender, scale, anim, facing, frame). Keep about 512 entries.
   - `draw_player(game, p, cx, cy, tile, t, face, mov, atk, action, eq, gender, look)` blits so the canvas `feet_px` lands on the same ground point the 2D figure uses. Copy the `npc_hd_client` anchor maths and keep `entity_anchor` / nameplate / HP bar positions unchanged. It returns `True` when drawn.
   - Scale: 1x at the normal 40 px tile, 2x when the tile is 80 px or larger (same rule as npc_hd). 4x is only for UI previews.
2. Add `tools/player_hd_check.py`: compose the male and female defaults plus one steel and one bronze armour look, in all 4 facings and several frames, and save PNGs to a temp folder. Run it and show the images.
3. Commit: `player_hd: asset loader + offline compose check`.

STOP and report.

---

## Step 3: In-game draw + the HD/2D player setting

1. Server:
   - Add `hd_player INTEGER NOT NULL DEFAULT 1` to `players`, using the existing `ALTER TABLE` migration pattern.
   - Add it to `full_state()`.
   - Handle `SET_OPTION hd_player=<bool>` exactly like `auto_pickup_items`.
2. Client:
   - Add the toggle in the settings spot from Step 1: **"Character graphics: HD / Classic 2D"**.
   - The setting controls how this client draws all players (self and others).
   - Default HD for everyone, existing players included.
3. Wrap each player draw site: `if hd_on and player_hd_client.draw_player(...): pass` `else:` the **unchanged** `sprites.draw_humanoid_detailed(...)` call. Do the same for the other-player branch.
4. Looks until Step 4 lands: use the catalogue `defaults[gender]` (basic male or basic female).
5. Verify, with screenshots in both modes:
   - walking (keyboard and click-path), idle, melee, ranged, chop, mine and fish;
   - walk speed and tile stepping unchanged; time 10 tiles in each mode and they must match;
   - nameplate and HP bar positions unchanged;
   - level-up glow, PK mark and gather FX still drawn.
6. Commit: `player_hd: HD player drawing + HD/2D setting (2D path intact)`.

STOP.

---

## Step 4: Saved look + defaults for existing players

1. Add `server/cosmetics.py`:
   - Load `catalogue.json` once.
   - `default_look(gender)`; `is_owned(player, item)`, which is true when the item is a starter item or in `owned_cosmetics`; `validate_look(look, owned)`.
2. In `players`, add `appearance TEXT NOT NULL DEFAULT ''` (JSON: skin, hair, hair_colour, top, bottom, shoes, outfit, accessories[≤2]) and `owned_cosmetics TEXT NOT NULL DEFAULT '[]'`.
3. **Existing players:** an empty `appearance` means `default_look(gender)` (basic male or basic female). Write it back on first login so it sticks. They can change it later in the shop and wardrobe.
4. Send `appearance` in `full_state()` and in the public per-player data, so other clients draw your outfit.
5. Client: pass `look` into `draw_player`.
6. Commit: `cosmetics: saved appearance + defaults for existing players`.

STOP.

---

## Step 5: Character creator (new characters)

1. Hook into the point where a new character picks gender (stat allocation / create flow from Step 1). Add an **Appearance** panel:
   - male/female body;
   - skin (light, tan, deep);
   - hair style (starter styles only);
   - hair colour (whole palette, free here);
   - starter top, bottom and shoes (items with `starter: true`).
2. Preview with the **4x** layers (`idle_s/e/n`, w = flip e) and rotate buttons.
3. Add a `CREATOR_SAVE {look}` message.
   - The server accepts it only during creation, or while `appearance == ''`.
   - It accepts only starter items, sets `gender` from the chosen body and saves.
4. Commit: `cosmetics: character creator`.

STOP.

---

## Step 6: Wardrobe (re-equip owned items, saved between sessions)

1. Add a Wardrobe modal (button beside Equipment/Pets).
   - Tabs: Hair, Tops, Bottoms, Shoes, Outfits, Accessories.
   - Show only owned and starter items. Use a 4x preview with rotation.
2. Add a `COSMETIC_EQUIP {slot, item_id}` message.
   - The server validates ownership, updates and saves `appearance`, and broadcasts it.
   - Equipping an outfit clears nothing: it hides the top and bottom while worn.
   - Unequipping the outfit shows the saved top and bottom again.
3. Show armour on the preview with a toggle ("show armour"), so players can see what will actually be visible.
4. Commit: `cosmetics: wardrobe`.

STOP.

---

## Step 7: Clothing shop with try-on + coin purchases

1. Add `content.SHOPS["costume_shop"]` (`type: "cosmetic"`) on the NPC agreed in Step 1. Stock: tops, bottoms, shoes, outfits and accessories from the catalogue.
2. UI (`cosmetics_ui.py`):
   - Grid of items with price.
   - Clicking an item tries it on the 4x preview (client-only) and shows "Buy (N coins)" plus Revert.
   - Owned items show "Owned: Wear".
3. Add a `COSMETIC_BUY {item_id, equip: bool}` message. The server:
   - checks the item exists and is not already owned;
   - checks the price from the catalogue and the coin balance, using the same coin source as `handle_shop_buy`;
   - deducts the coins, appends to `owned_cosmetics`, optionally equips, saves, and sends the updated state.
   - Buying an already-owned item never charges again (same as the pet pattern).
4. Commit: `cosmetics: clothing shop with try-on`.

STOP.

---

## Step 8: Hair salon (style and colour chosen independently)

1. Add `content.SHOPS["hair_salon"]` (`type: "salon"`) on the agreed NPC.
2. Style and colour are separate pickers, both previewed on the 4x model before paying.
   - **Style:** priced styles are bought once (`COSMETIC_BUY`) and owned forever. Starter styles are free.
   - **Colour:** `HAIR_COLOUR {colour_id}` costs `catalogue.hair_colour_change_price` coins. The colour must be in `hair_palette`, and the brows follow the hair colour.
3. Commit: `cosmetics: hair salon`.

STOP.

---

## Step 9: Armour + weapons on the HD player (male and female fitted)

1. Map equipped items to layers with `catalogue.armour_layers` / `weapon_layers`:
   - `*_helmet` → `arm_helm`;
   - `*_body` → `arm_platebody` + `arm_gauntlets`;
   - `*_chainbody` → `arm_chainbody`;
   - `*_legs` and `*_chainlegs` → `arm_platelegs`, with `*_legs` also drawing `arm_sabatons`;
   - `*_shield`, `*_sq_shield` and `wooden_shield` → `arm_kiteshield`;
   - sword, dagger and longsword → `wpn_sword`;
   - axe and battleaxe → `wpn_axe`;
   - pickaxe → `wpn_pickaxe`;
   - bow → `wpn_bow`;
   - staff and wand → `wpn_staff` (its own layer: carried head-up, swung head-first in melee);
   - fishing → `wpn_rod` (only while fishing).
2. **Tier colour**: the item-id prefix (`bronze`, `iron`, `steel`, `mithril`, `adamant`, `mythos`, `eclipse`) picks the colour from `tier_tints` (the same RGB as `rs_style.metal_palette`). Use `leather` for leather items and `wood` for the wooden shield.
3. Override rules: cosmetics show wherever no armour is worn, and armour wins on the slot it covers (see `override_rules`).
4. Known gaps, which must not crash:
   - `leather_*` and `goblin_mail` use the steel layers tinted `leather`;
   - `amulet`, `ring` and `ammo` are not drawn.
5. Verify combat: melee frames follow `atk` progress and the ranged frames use `RANGED_ANIM_SECS`. Hit and hurt flashes, damage splats and target rings stay where they were. Attacks still freeze the gait (`mov=False`) exactly as before.
6. Commit: `player_hd: armour + weapon layers with tier tint`.

STOP.

---

## Step 9b: Combat fit (melee, ranged, hit reaction, death, anchors)

Read first (no edits):
- `server/combat.py` (formulas only, no styles);
- the server player swing loop (`next_swing_at = now + 1.2`, `TICK_SECONDS = 0.6`, reach / `side_by_side` / `attack_range` checks);
- client `handle_combat_event` (`attack_anims`, `ATTACK_ANIM_SECS = 1.05`, `RANGED_ANIM_SECS = 0.72`, `strike_t` 0.48 melee / 0.58 ranged, arrow `start = now + anim_secs * 0.55`, flight 0.32 s), `_flush_pending_floaters`, `_draw_projectiles`, `face_toward_target`, `_maybe_flank_combat_target`, `DEATH`, `handle_magic_cast`.

**Nothing in this list changes.** Server ticks, cooldowns, reach, facing logic and the hitsplat or projectile times stay as they are. HD only picks frames.

1. **Melee:** while `atk > 0.02` and the kind is melee, use `melee` frames via `sample_progress`. The 10 frames are guard, lift, full windup, accelerating overhead, **contact (frame 4)**, follow-through, low follow-through, then recovery. Frame 4 is on screen at progress 0.48, when the client releases the hitsplat, so the blow lands on the same tick as today. At contact the blade is level at the chest height of a monster on the adjacent tile.
   - Optional swing smear: draw `{sex}/{scale}/fx_swing_{weapon_layer}/melee_e.png` (same frame index, z 91, mirrored for w) right after the weapon layer. Only frames 4 and 5 have pixels. It is visual only and skipped in 2D. Humanoid foes that "swing back on the same beat" keep their 2D/HD art; only the player changes.
2. **Ranged:** use the `ranged` frames. Frame 5 (release) shows at 0.55, when the arrow projectile starts. **Projectile origin:** if HD is on, start the arrow at `anchors[...]["ranged"]["e"][5]["hand_L"]` (mirror x for w) converted to world offset from the player's feet. This is a draw-position change only; keep `start` and `dur` untouched. Keep the old origin in 2D mode.
3. **Magic:** the game has no player cast pose (MAGIC_CAST only spawns `magic_fx` at the target). HD does the same: keep the current anim. If you want the bolt to start at the hand, use `hand_R` from anchors (optional).
4. **Hit reaction (new, visual only):** when a `monster_hits_player` event's hitsplat is released (`show_at`) for a player who is not attacking or moving, play `hit` for 0.36 s: `u = (now - show_at) / 0.36`, frame `min(3, int(u*4))`, in the facing the client already set. It is not used in 2D mode and changes no timing.
5. **Death (new, visual only):** on `DEATH` for a player entity, play `death` over 1.2 s (`frame = min(7, int(u*8))`) in the current facing, then hold frame 7 until the respawn position update arrives. The death banner flow is unchanged. In 2D mode keep today's behaviour.
6. **Layers and order:** weapon and shield are separate layers (`wpn_*`, `arm_kiteshield`). Sort by `z[facing]` from the catalogue:
   - the weapon is in front facing s/e and **behind the body facing n** (z 8 < body 10);
   - the shield (left arm) is in front facing s/n and behind everything facing e (z 3), because the left arm is the far side when facing east;
   - the bow is behind facing e and n.
7. **Footprint:** blit with `feet_px` at the same ground point as monsters/NPCs (tile centre, `entity_anchor` convention). Do not add any per-anim offset; the frames already contain the lunge. In `side_by_side` fights the sword tip reaches about 0.9–1.3 tiles forward at contact, the same as the 2D swing. Check with a screenshot that the player neither overlaps nor floats away from the monster.
8. **HP bar, nameplate, hitsplat:** keep `entity_anchor` positions. Use `anchors.head_top` only to check that the HD head never covers the HP bar (if it does, raise the bar by the difference in HD mode only). Optionally centre the player's hitsplats on `anchors.chest`.
9. **2D mode:** combat drawing stays exactly as today. The same events, the same `draw_humanoid_detailed` call.
10. Screenshots:
    - melee vs a `side_by_side` monster (frames 3/4/5);
    - bow shot with the arrow leaving the bow hand;
    - a hit reaction;
    - death and respawn;
    - each in HD and 2D.
11. Commit: `player_hd: combat frames synced to strike/release + hit/death`.

STOP.

---

## Step 10: Polish + final check

- Performance:
  - precompose on look or equipment change;
  - keep the LRU in place;
  - make sure there are no per-frame `pygame.transform` calls except the cached west flip.
- Flip the setting back and forth in-game. 2D must look and behave exactly as before.
- Final screenshots:
  - creator, salon, shop try-on and wardrobe;
  - starter male and female;
  - steel and bronze armour;
  - other players seeing your outfit;
  - the 2D mode.
- Commit `player_hd: polish` on `main` and report.
