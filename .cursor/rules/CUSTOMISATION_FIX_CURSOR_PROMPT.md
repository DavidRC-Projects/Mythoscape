# Mythoscape: fix the HD player and build Mythos Outfitters (one customisation shop)

Work directly on **main**. Make small steps. After each step, run the compile check, commit with a short message and push to origin main:

```
cd game/assets/mmorpg && python3 -m py_compile client/*.py server/*.py shared/*.py
```

## Hard rules
- **Never touch the walk cycle**: `pose_walk`, `rs_style.py`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`, `draw_humanoid_detailed`. You may still *call* `draw_humanoid_detailed` as the 2D fallback.
- Keep combat timing exactly as it is (`ATTACK_ANIM_SECS`, `RANGED_ANIM_SECS`, `_attack_progress`, strike_t and arrow timing). The HD layer only changes what is drawn.
- Keep the `hd_player` 3D/2D toggle and the old 2D characters.
- **No feature flags.** Remove old data outright when it is replaced.
- Don't rewrite large existing code. Make focused edits.
- Art lives in `game/assets/player_hd/assets/` (`meta.json`, `catalogue.json`, `anchors.json`, `{sex}/{1x|2x|4x}/{layer}/{anim}_{facing}.png` plus `_tint.png`). Read `catalogue.json` → `armour_layers`, `weapon_layers`, `tier_tints`, `tier_tint_gain`, `hair_palette`, `override_rules` before Step A.
- UI mockups:
  - `game/assets/player_hd/previews/customisation_screen_mockup.png` (new-player creator mode)
  - `game/assets/player_hd/previews/customisation_shop_mockup.png` (shop mode)

---

## Step A: fix the blank HD player (`client/player_hd_client.py`, plus one call site in `client/client.py`)

The player looks bare and untextured because of these bugs. Fix every one of them.

1. **Tint-only layers never load.** `_load_layer_frame()` (around lines 162–189) returns `(None, None)` when `{anim}_{facing}.png` is missing. Hair and brows ship **only** `_tint.png` (catalogue `files.<sex>.fixed == false`), so the player is always bald with no brows.
   - Load the base and tint parts independently.
   - In `draw_player()`, skip a layer only when **both** parts are missing.
2. **Hair colour is always black.** `_parse_hair_colour()` reads `cat["hair_colours"][...]["rgb"]`, but the catalogue key is `hair_palette` with `mul`. Brows use the same hair colour.
3. **Outfits draw nothing.** In `_visible_layers()`, outfits read `outfit_item.get("layers", [])`, but catalogue outfits have a single `"layer"`. The result is a bare body whenever an outfit is worn. That is exactly David's saved look: `outfit_hunter` with top, bottom and shoes all null.
   - Use `item["layer"]`.
   - Per `override_rules`, an outfit hides **top and bottom only**. Shoes still draw.
   - When a slot is empty, fall back to the starter item from `catalogue.defaults[sex]`.
4. **Wrong surfaces from the scale cache.** `_scaled()` (lines 79–88) caches by `id(surf)`. Every frame is a fresh `.copy()`, so ids get reused, and the cache returns the wrong layer's surface at any tile size other than 40. The default zoom is TILE 32 → 35 px, so this happens all the time. The cache also grows forever.
   - Cache by `(path, frame_idx, w, h)`, or scale the whole strip once per `(path, w, h)` and then subsurface it.
   - Pick the source scale **at or above** the target (use 2x for any tile from 41 to 80, and 1x only when tile ≤ 40) and smoothscale **down**. This keeps the sprite crisp.
5. **West facing is misaligned.** In the flip branch (around line 354), `feet_x = main_surf.get_width() - feet_x` runs inside the layer loop, so the anchor flips back and forth on every layer.
   - Compute the mirrored anchor once, before the loop.
6. **The shadow is never drawn.** `meta.always = ["shadow", "body_<skin>", "brows"]`. Draw `shadow` first, using the same frame index.
7. **Equipment is never drawn. This is why there is no armour, weapon or shield.**
   - Add an `equipment=None` argument to `draw_player()`.
   - In `client.py` (around line 6031), pass `equipment=eq`. `eq` is already built at lines 5966/5971.
   - Map gear to layers using `catalogue.json` and the table below.
   - Tint each layer with `tier_tints[prefix] × tier_tint_gain`, clamped to 255. The prefix is the part of the item id before the first `_`.
   - Multiply the `_tint.png` part by that colour, then blit it over the fixed part, exactly as is done for hair.

   | Equipped slot / item id | HD layer(s) | Hides | Tint |
   |---|---|---|---|
   | helmet `*_helmet` | `arm_helm` | hair (brows stay) | tier |
   | helmet `leather_cowl` | `arm_helm` | hair | `leather` |
   | helmet `bone_crown` | `arm_helm` | hair | `(225, 215, 185)` |
   | body `*_body` (plate) | `arm_platebody` + `arm_gauntlets` | top, outfit, `acc_leather_gloves` | tier |
   | body `*_chainbody`, `goblin_mail` | `arm_chainbody` | top, outfit | tier (`goblin_mail` → `leather`) |
   | body `leather_body` | `arm_chainbody` | top, outfit | `leather` |
   | legs `*_legs` (plate) | `arm_platelegs` + `arm_sabatons` | bottom, outfit, shoes | tier |
   | legs `*_chainlegs`, `leather_chaps` | `arm_platelegs` | bottom, outfit | tier / `leather` |
   | shield any `*_shield`, `*_sq_shield` | `arm_kiteshield` | – | tier (`wooden_shield` → `wood`) |
   | weapon `*_sword`, `*_longsword`, `*_dagger` | `wpn_sword` | – | tier |
   | weapon `*_axe`, `*_battleaxe`, `eclipse_cleaver` | `wpn_axe` | – | tier |
   | weapon `*_pickaxe` | `wpn_pickaxe` | – | tier |
   | weapon `*bow*` (`shortbow`, `oak_`, `willow_`, `maple_`, `yew_`, `magic_`) | `wpn_bow` | – | `wood` |
   | weapon `*staff*`, `*wand*` | `wpn_staff` | – | tier |

   More gear rules:
   - Unknown prefixes such as `void` fall back to `steel`.
   - If an outfit is hidden on one half only, draw the saved top or bottom (or the starter one) on the uncovered half.
   - **Skilling:** `chop` shows `wpn_axe`, `mine` shows `wpn_pickaxe`, and `fish` shows `wpn_rod`, in place of the wielded weapon for that animation only.
   - Use `z[facing]` from the catalogue entries for sorting. The shield and bow have different `e`/`n` values on purpose.
   - Draw `fx_swing_<weapon_layer>/melee_e.png` (z 91) during melee frames 4–5 if the file exists.
   - Amulets, rings and ammo have no HD layer, so ignore them.
8. **Ranged uses the wrong animation.** At `client.py` (around line 6030), `anim` is always `"melee"` while attacking.
   - Use `"ranged"` when `self.attack_anim_kind.get(p["id"]) == "ranged"`, or when the weapon is a bow.
   - Pass the same `atk` progress as now.
9. **2D fallback per layer.** If a required layer file is missing for the current anim and facing, try the `e` strip mirrored (as now). If the **body** layer itself can't be found, return `False` so the existing `draw_humanoid_detailed` path draws the 2D character with gear. Never draw a half-empty HD figure.
10. **Existing players need a default look.** `server.py` `appearance_state()` returns `None` when nothing is saved, and the DB backfill in `database.py` `_backfill_existing_looks()` only ran on the migration that *added* the column.
    - Keep `None` for brand-new accounts (`stats_allocated == 0`). That is what triggers the creator.
    - For any character with `stats_allocated == 1` and no saved look, return `player_hd_client`-equivalent defaults for their gender (male: `hair_side_part`/`dark_brown`/`top_linen_shirt`/`bottom_work_trousers`/`shoes_leather`; female: `hair_ponytail`/`chestnut`/`top_linen_shirt`/`bottom_long_skirt`/`shoes_leather`). Return them in the state only, without writing to the DB.

**Check:** log in as "The Creator" (eclipse helmet, body, legs, shield and cleaver; look = `outfit_hunter`). You should see a dark eclipse helm, platebody and gauntlets, platelegs and sabatons, the red kite shield, and the axe-type weapon. Hair is hidden under the helm. The shading and textures look the same at all zoom levels, and west matches east mirrored.
- Also check a player with no gear: textured shirt, trousers and shoes, with brown hair and brows.

Commit as `fix(hd-player): tint-only hair/brows, outfit layer, armour/weapon/shield layers, scale cache, west anchor`.

## Step B: one building, Mythos Outfitters (remove the salon and the tailor completely)

Delete all of the following. There are no flags, and no data from them should be left behind:
- `server/content.py`:
  - NPCs `hair_stylist_wren` and `tailor_bram` (around lines 1465–1473)
  - INTERACTABLES `hair_salon_door` and `clothing_shop_door` (around lines 2639–2642)
  - BUILDINGS `hair_salon` and `clothing_shop` (around lines 2938–2949)
- `server/world_map.py`:
  - `_building(54, 6, 64, 16, …)` and `_building(66, 6, 75, 16, …)` (lines 241–242)
  - aprons `(59, 17), (70, 17)` (line 255)
  - the lane loops `for x in range(58, 77)` and `grid[y][76]` (lines 262–268)
  - footprints `(54, 6, 64, 16), (66, 6, 75, 16)` (line 810)
- `client/client.py`:
  - the `DIALOGUE` intercepts for `hair_stylist_wren` and `tailor_bram` (around lines 803–811)

Then add **one** building in Step C, with one NPC, `outfitter_mae` ("Mae the Outfitter"), whose `cosmetic` field is `"outfitters"`. Talking to her opens the unified UI in shop mode (Step F).

Commit as `feat(world): single Mythos Outfitters building; remove salon + tailor`.

## Step C: put it somewhere open and visible

There is a clear grass field south-east of the bank, between the SE cottage (wall x 41–53) and the Pet Emporium (x 80–93), above the main east road (path rows y 49–51). Rows y 34–48 across x 56–78 are plain grass, with no NPCs, interactables or props. The only thing nearby is `sign_bank` at (64, 33), north of the field.

- **Building shell:** `x0=60, y0=37, x1=72, y1=47`, `door_x=66` (13×11, the same size as the bank). That leaves 6+ tiles to the cottage, 7 to the Pet Emporium, 3 tiles of grass plus the path band to the north, and the door opening straight onto the road.
- **`world_map.generate_world()`:**
  - `_building(60, 37, 72, 47, door_x=66)` next to the other village shells
  - add apron `(66, 48)` to `door_aprons`
  - add `(60, 37, 72, 47)` to `_BUILDING_FOOTPRINTS` (keeps trees out of the margin)
  - the apron already touches road row 49, so no lane is needed
- **`content.py` BUILDINGS:**
  - `{"id": "mythos_outfitters", "name": "Mythos Outfitters", "kind": "house", "style": 1, "material": "red_brick", "x0": 60, "y0": 37, "x1": 72, "y1": 47, "floor_x0": 61, "floor_y0": 38, "floor_x1": 71, "floor_y1": 46}`
- **INTERACTABLES:**
  - door `{"id": "outfitters_door", "kind": "door", "name": "Mythos Outfitters Door", "x": 66, "y": 47, "enter_x": 66, "enter_y": 45, "exit_x": 66, "exit_y": 48, "building": "mythos_outfitters"}`
  - a sign at (63, 48) reading "Mythos Outfitters: hair, clothes, outfits"
- **NPC:** `outfitter_mae` inside at (66, 41). She has no HD NPC art yet, so the 2D fallback is fine.
- Also add `{"id": "outfitters", "kind": "place", "label": "Mythos Outfitters", "x": 66, "y": 49, "blurb": "Hair, clothes & outfits"}` to `TRAVEL_DESTINATIONS`, so it appears in the M travel list.

**Check:** generate the world and print an ASCII crop of x 50–95, y 30–52. The shell must be closed apart from a 3-wide door, the door must reach the road, and the cottage, bank and Pet Emporium must be unchanged.

Commit as `feat(world): place Mythos Outfitters in the open SE field`.

## Step D: add it to the teleport menu

- `server/content.py` `TELEPORT_DESTINATIONS`: add `{"id": "outfitters", "label": "Mythos Outfitters", "blurb": "Hair, clothes & outfits", "where": "overworld", "x": 66, "y": 49}` right after `bank`.
- `client/client.py` `draw_teleport_modal()` (around line 7858): the box is `Rect(250, 70, 420, 620)`, and with 7 overworld and 5 castle rows the last row would overlap the Close button.
  - Make the box 660 tall (`Rect(250, 50, 420, 660)`), or reduce the row step from 40 to 36. Keep the clicks working.
- The server's `handle_teleport` needs no change, because it reads the list. It still requires `knows_teleport`.

Commit as `feat(teleport): Mythos Outfitters destination`.

## Step E: customisation screen for new players

The hook already exists:
1. `client.py` line 493 sets `needs_appearance` when the login payload has no appearance.
2. `_offer_appearance()` runs after `STAT_ALLOC` and the opening comic (`client.py` around line 526, and `opening_comic.py` line 66).

Make it reliable:
- Open the unified UI (Step F) in **creator mode** (`mode="creator"`). Nothing costs coins; only starter items are selectable, and the paid items show "In shop".
- Block game input while it is open. Esc does nothing in creator mode.
- **Skip** sends the basic look for their body type (the defaults above) through `UPDATE_APPEARANCE`. **Confirm look** sends the chosen look. Both clear `needs_appearance`.
- If the client reconnects before saving, the creator shows again (the server state is still `None`).
- The Male/Female toggle in creator mode may change `gender`. If it does, add a small `SET_GENDER` server message that is only accepted while appearance is still `None`. If that is too invasive, keep the gender from registration and hide the toggle in creator mode. Pick one and note which in the commit.

Commit as `feat(creator): first-start customisation screen with skip`.

## Step F: the unified clean customisation UI (`client/cosmetics_ui.py`)

Replace `CharacterCreator`, `HairSalon` and `ClothingShop` with **one** class, `Outfitters(client)`, with `open(mode)` where mode is `"creator"` or `"shop"`. Match the mockups pixel for pixel where you can, on the 1200×800 window, using the `hud_v2.py` palette: `NAVY (12,18,34)`, `NAVY_CARD (20,28,48)`, `NAVY_HI (32,42,68)`, `GOLD (212,175,90)`, `GOLD_DIM (120,96,52)`, `INK (232,226,210)`, `MUTED (150,160,180)`, `SAFE_GREEN (72,180,110)`.

**Layout:**
- **Overlay and panel.** A dim overlay over the world: `(4,6,14,190)`. The panel is at `Rect(40,30,1120,740)`, radius 14, with a 2 px GOLD border and an inner 1 px GOLD_DIM line.
- **Header.** A serif title in GOLD at (72,50): "Create your adventurer" (creator) or "Mythos Outfitters" (shop). A MUTED subtitle goes under it. There is an X close button at the top right (shop mode only), and a divider at y = 120.
- **Preview stage** at `Rect(60,136,400,554)`. It is NAVY_CARD with a soft radial glow behind the figure and an oval plinth.
  - Draw the figure with `player_hd_client.draw_player(..., anim="idle", facing=f, equipment=None)` using the **4x** idle frames: tile 160, scaled about ×1.35, feet on the plinth.
  - The `<` and `>` buttons and click-drag rotate it through front (s), side (e), back (n) and side (w, mirrored). Labels underneath read "Front / Side / Back".
  - A Male | Female pill toggle sits at the top of the stage (see Step E).
- **Category rail** at x 480, 150 wide, with 44 px tabs: **Body, Face, Hair, Hair colour, Tops, Bottoms, Shoes, Outfits, Accessories**, plus **Wardrobe** in shop mode.
  - The active tab gets NAVY_HI, a GOLD border and a 4 px gold bar on the left.
  - Body = body type plus skin tone. Face = skin tone and brows preview. There are no separate face meshes; brows follow the hair colour.
- **Item grid** at `Rect(650,136,490,484)`, with a 4-column grid of 108×132 cards and a 12 px gap. It scrolls with the mouse wheel.
  - Each card shows a thumbnail of the item worn on the current look (render 2x, crop to the slot region), the name, and a price line:
    - "Free" (green) for starter items, or "In shop" (muted) in creator mode
    - "Owned" (green) or "N coins" (gold) in shop mode
  - The selected card gets a 3 px GOLD border and a gold tick.
  - **Hair colour** shows round swatches from `hair_palette`. There is also a quick swatch row under the grid at y ≈ 632.
  - **Accessories** allow up to `accessory_max` (2).
- **Footer** below a divider at y = 702.
  - Shop mode:
    - a coin icon and "13,213 coins" (the real `player.coins`)
    - a "Trying on: …" line with the total cost of the unowned items being tried on
    - buttons **Randomise**, **Reset**, **Save outfit**, **Buy & wear N**. The last one is the gold primary button; if nothing needs buying it reads "Wear".
  - Creator mode: **Randomise** (starter items only), **Reset**, **Skip**, **Confirm look**.
- **Wardrobe tab.** It shows owned items grouped by slot, plus 3 saved outfit slots ("Outfit 1–3": Save / Wear). Store them in a new `saved_outfits` TEXT column (JSON, default `'[]'`), added in `database.py` the same way as `owned_cosmetics`.

**Server (`server/server.py`), so purchases are real:**
- Add `owned_cosmetics` (parsed list) and `saved_outfits` to `full_state()`.
- New `BUY_COSMETICS {items:[ids], appearance:{…}}`:
  1. Validate every id against `catalogue.json`.
  2. Sum the prices of the unowned, non-starter items, check `coins`, and deduct.
  3. Add the items to `owned_cosmetics`, save the appearance, then send `PLAYER_UPDATE` and broadcast.
  4. Reply with a short chat line.
- `UPDATE_APPEARANCE` must reject any non-starter item the player doesn't own, and any id that isn't in the catalogue. Remove the chat line "Press J for the hair salon, K for the clothing shop".
- New `SAVE_OUTFIT {slot:0..2, appearance}`.

**Client wiring:**
- Replace the three objects in `client.py` (around lines 423–426) with `self.outfitters = Outfitters(self)`.
- Update the scroll handling (around lines 1612–1630), the click handling (around lines 3397–3406) and the render calls (around lines 4929–4938) to use the one object.
- **Remove the J and K key binds** (lines 1321–1332). The shop is reached by talking to Mae or teleporting to Mythos Outfitters.
- The `DIALOGUE` for `outfitter_mae` opens `self.outfitters.open("shop")`.
- Esc closes shop mode.

Commit as `feat(ui): unified Mythos Outfitters customisation screen`.

## Step G: a visible 3D/2D toggle

There is a server handler `TOGGLE_HD_PLAYER` (server.py around line 3939) but nothing in the client sends it. The sidebar "Settings" button (`hud_v2.py` around line 398, click at `client.py` around line 3914) only opens Help.
- Add a pill button at the top of the Help/Settings panel reading "Player look: 3D | 2D". It sends `TOGGLE_HD_PLAYER {enabled}` and reflects `player.hd_player`.
- The draw code already reads `self.player["hd_player"]` (`client.py` line 6018).

Commit as `feat(settings): 3D/2D player toggle button`.

## Final check
- `py_compile` passes.
- A new account goes through stats, comic and then the creator. Skip gives the default look, and Confirm saves it.
- An existing character shows textured clothes with armour, weapon and shield.
- Only one shop building exists, and it is reachable by walking, by teleport (T) and from the travel list (M).
- Neither J nor K opens anything.
- No walk-cycle file changed (check with `git diff --stat origin/main~N -- …`).
