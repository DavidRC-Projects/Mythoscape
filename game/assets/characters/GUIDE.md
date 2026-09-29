# Characters, gear looks and Equipment screen: guide

Prototype on a fresh clone of main @ ca336ee. Nothing was pushed and no PR was opened. Everything sits behind flags; the old code is untouched apart from 4 small hooks.

## Flags (`game/assets/mmorpg/server/feature_flags.py`)
| Flag | Default | Effect |
|---|---|---|
| `USE_NEW_CHARACTERS=1` | off | Uses the new body, face, hair and palette for players and NPCs (`characters/rs_humanoid_v2.py`), plus per-item armour and weapon looks and new inventory/slot icons (`characters/gear_v2.py`) |
| `USE_NEW_EQUIPMENT_UI=1` | off | Uses the new Equipment & Stats screen (`mmorpg/client/equipment_ui_v2.py`) |

## Hooks (the only edits to existing files; `reference_code/hooks_only.patch`, 92 lines)
1. `rs_humanoid.py`: module flag `USE_NEW_CHARACTERS=False`. At the top of `draw_skeletal_humanoid`, `if USE_NEW_CHARACTERS: rs_humanoid_v2.draw(...same args...); return`.
2. `procedural_sprites_finished.py`: `USE_NEW_ITEM_ICONS=False`. `draw_item_icon` tries `gear_v2.draw_icon` first and falls back to the old icon.
3. `client.py`: import both flags and set `rs_humanoid.USE_NEW_CHARACTERS` and `sprites.USE_NEW_ITEM_ICONS`. At the top of `draw_equipment_modal`, `if USE_NEW_EQUIPMENT_UI: equipment_ui_v2.draw(self, ...); return`.
4. `feature_flags.py`: the two new flags (default "0").

## What changed
### Bodies and faces (OSRS direction: realistic proportions, flat-shaded, muted)
- **Same skeleton, new flesh.** `rig_side()` and `rig_ortho()` are verbatim copies of the old joint maths. The new drawer only hangs new shapes on those joints.
- **Head:** 0.86 of the old size, centred 1.8 s above the neck joint, so it sits slightly lower than before and helmets clear the HP bar better (see the anchor check below). The figure is about 6.8 heads tall (was about 4.3).
- **Torso:** tapers from the shoulders to a real waist, with a female bust line. The belt sits at pelvis−2 s, so the legs read longer (belt to sole ≈ 47 % of height) without moving any joint.
- **Limbs and shoulders:**
  - Limb half-widths: upper arm 1.2 (was 1.75), forearm 0.9 (was 1.45), thigh 1.75, calf 1.28 tapering to a 0.92 ankle.
  - No shoulder pads on cloth. Armour gets layered pauldrons; see the bulk pass below.
- **Face:** 2-tone eyes (sclera plus pupil), brows, nose underside, mouth line, jaw shading, ears. Side view is a 3/4 profile.
- **Hair:** male short crop with a side part; female long hair behind the shoulders plus a fringe. Both work in all 4 views.
- **Palette:** muted cloth (body colour about 35 % desaturated), muted skin, and no photo-texture dither. Flat 2-tone facets are lit from the upper left, with a soft dark outline.
- **Female cloth colour:** unarmoured females now keep their `body_color`, so NPCs like Lira show their real shirt colour. The old code forced pink. The default player green still maps to pink on female.

### Armour bulk pass (feedback round 2, `characters/armour_v2.py`)
- **Bulk by material** (`armour_v2.bulk`): plate 1.0 (1.15 for Mythos/Eclipse), chain 0.7, goblin mail 0.6, leather 0.4, cloth and bare bodies 0 (still slim). The chest widens by bulk×0.95 s and the waist by bulk×0.6 s.
- **Plate:**
  - body: a broad breastplate with a keel ridge, abdomen lames, edge trim and rivet rows;
  - shoulders: 3-lame layered pauldrons that get bigger each tier;
  - arms: rerebrace, couter, vambrace cuff and gauntlet;
  - legs: a two-row faulds skirt, tassets that follow the thighs, cuisses, fan-winged knee cops, greaves and segmented sabatons.
- **Chain and leather:**
  - chain: widened limbs, a mail mantle over the shoulders, a trim hem band, bracers and mail knee cops;
  - leather: moderate caps and bracers, studs and chap knee pads.
- **Same joints only:** every extra shape hangs off the existing joints, and the rig maths is untouched (walk and attack proof below: 0.0).
- **Per-tier identity** (trim colour, rivet count, helm shape):
  - bronze: open cap, nasal and mail aventail;
  - iron: kettle brim and aventail;
  - steel: snouted bascinet with a visor slit and breath holes;
  - mithril: sallet with a tail and ridge crest, silver trim;
  - adamant: flat-top great helm with a cross visor, comb and red plume, brass trim.

### Magnificent sets: Eclipse and "dragon" (= Mythos)
- **Which set is "dragon":** `content.py` has no dragon armour set; the only dragon item is `dragon_bones`. I treated the crimson, horned **Mythos set** ("Crimson dragon-plate") as the dragon set.
- **Both sets:**
  - double gold filigree with scroll curls on every plate edge;
  - runes on the pauldrons, tassets, greaves and tabard;
  - gem inlays and additive glow accents with a subtle pulse (driven by the anim time `t`, cosmetic only; static in the equipment preview);
  - a cape with a gold border, showing the emblem and hem runes in back view;
  - weapons with gold blade runes and glowing pommel gems;
  - shields with a large emblem, double filigree and gems.
- **Eclipse:**
  - chest: a large gold sun with 12 rays, bitten by a dark crescent, with an amber gem;
  - shoulders: sun-spiked pauldrons;
  - helm: gold wings, a 7-ray sun crown, a gold grill and a glowing brow gem.
- **Mythos:**
  - chest: a gold dragon head with spread wings and glowing ruby eyes;
  - shoulders: gold-horned pauldrons;
  - helm: big gold horns, red fin spines, a gold chevron visor, cheek wings and glowing eyes.
- **Scale check:** `eclipse_dragon_closeup.png` shows old vs new in 4 directions plus attack at 1× (game scale, about 48 px), a 3× zoom, and equipment-preview scale at 1×. Chosen shapes are at least 1–2 px so they survive 1×.

### Unique armour and weapon looks: 74 items, table in `ITEM_LOOKS.md`
- **Weapons:** the silhouette comes from type (sword, longsword, dagger, battleaxe, axe, pickaxe, cleaver, bow). Tier detail changes the crossguard shape per metal (plain → square ends → angled → upswept → winged → dragon-wing plus ruby), adds a fuller from steel up, widens axe bits, and adds a top spike from mithril up. The six bows are coloured by wood species; the magic bow has a glowing string.
- **Body:** plate (keel ridge, pec line, pauldrons, plated forearms), chain (staggered rings, mail sleeves), leather (stitched seams), goblin mail (rust patches). Mythos and eclipse get the royal ornament described above.
- **Legs, helmets, shields:**
  - legs: plate tassets and knee cops, chain rows, leather chaps;
  - helmets: tier-specific shapes (above), cowl, ornate dragon helm and eclipse helm;
  - shields: wooden round, square with rivets, kite with a tier stripe, mythos kite and eclipse aegis with large emblems.
- **Icons:** built from the same look data for every armour, weapon, ammo and jewellery item (jewellery uses `gem_color`). Other items keep the old icons.

### Equipment & Stats screen
- **Panel:** stone-and-gold framed panel, inset title bar, OSRS orange headings.
- **Paper doll:** the helmet sits above the doll, amulet/ammo, weapon/shield and body/legs are on either side, and the ring is below. Guide lines run to the body. Empty slots show silhouette glyphs; filled slots show item icons (the quiver shows its count).
- **Bonuses:** cards with a glyph, value, karma part and a 10-segment bar; a ranged row; combat levels as a card grid.
- **Unchanged:** the modal rect, the `equip_slot_rects` keys (click to unequip), the data, the hover detail text, the footer, and Esc/E.

## Walk proof: PASS (`walk_proof.json`, `walk_compare_sheet.png`, `walk_compare.gif`)
- **Method:** `tools/walk_proof.py` spies on `rs.draw_volume_limb` while the old drawer runs and records every limb segment it draws (hip→knee→foot, shoulder→elbow→hand per frame). It then computes the new rig for the same inputs and requires bit-identical floats.
- **Walk coverage:** 3,200 frames (100 `t` samples × 4 directions × M/F × unarmed/steel/eclipse/mythos) and 25,600 segments. Max diff **0.0**, 0 mismatches. `resolve_pose` output is identical.
- **Attack coverage:** 1,176 frames (sword, cleaver, dagger, bow, battleaxe, plus the Eclipse and Mythos loadouts; both facings; both genders), 0 mismatches.
- **Timing and selection:** `t` source, cadence (TAU·1.15, 0.8696 s cycle), `moving_for` (0.55 s hold), `facing_for` and view selection are untouched; no client animation code was edited.
- **Sensitivity check:** a 0.01 % change to `t` in the new rig makes the check fail.

## Combat interaction
- **Weapon placement:** `gear_v2.weapon_transform` is an exact copy of `_draw_weapon`'s placement and angle maths. Swings, sheathe position, bow draw and the grip push follow the same arc; only the shape differs. The bow shows a nocked arrow while drawing. See `combat_attacks_before_after.png`.
- **Transform keying:** the transform uses the old `weapon_style()` families (cleaver = battleaxe, longsword = sword).
- **Hit, target and click areas:** click and target areas are tile-based (`screen_to_tile`) and the anchor (`cx,cy`, feet) is unchanged, so hitboxes, targeting and click areas do not change. Projectiles still use tile centres.
- **HP bar and name label:** `entity_anchor` / `label_lift` (18 s) are unchanged. `tools/anchor_check.py` (results in `anchor_check.json`) renders every helm, set and direction at tiles 40/32/24/16/12. It measures the gap from the highest opaque pixel to the bottom of the 4 px HP bar.
  - **Correction:** round 1 said the head stayed under the bar. That was wrong. At every zoom, today's game already touches or overlaps the bar: old bare head −1 to −4 px, old helms −4 to −6 px.
  - **New worst case per zoom** (T40 / 32 / 24 / 16 / 12): 0 / 0 / −2 / −3 / −4 px. So every new helm, including the horns, crests and sun crown, sits at or below today's bare head and 2–4 px lower than the old helms.
  - Helm tops are squashed and clamped at 4.25 head units, and the head is 0.86 scale, set lower on the neck.
  - Fully clearing the bar at small zooms would mean moving the bar (`label_lift`), which is outside this task.
- **Hit feedback:** hitsplats, level-up glow and monster `hurt` flashes are unchanged.
- **Gathering:** poses keep the same tool angles; the tools get the new look.

## Scores against OSRS (honest)
| Area | Score | Notes |
|---|---|---|
| Body proportions and faces | **8.0** | 6.8-head figure, readable face at game size, muted flat shading. Held back by the fixed rig: the side view keeps frontal shoulder width (3/4 read), and legs stay a little apart in front view |
| Armour bulk and detail (vs OSRS high-tier) | **8.0** | Plate now has the chunky presence of the old art with far more structure (layered pauldrons, gauntlets, faulds, knee cops, tier helms). Chain is intentionally lighter, and chain texture is subtle at 1× |
| Eclipse / dragon (Mythos) magnificence | **8.5** | Gold filigree, big readable emblems, runes, gems, glow, ornate helms, capes, matching weapons and shields. Richer than the old Eclipse. Short of 9: helms are squat because of the HP-bar clamp, and runes blur to dots below tile 32 |
| Equipment & Stats screen | **8.5** | Paper doll, slot glyphs, icons, bonus cards, OSRS stone/orange styling |
| Walk and combat preservation | **10** | Proven identical |

## Files
- `characters_4dir_before_after.png` (2×) and `_gamescale.png` (1×): player M/F, esteph, Lira, Eclipse set, robed NPC, 4 directions.
- `gear_sets_before_after.png` (11 loadouts), `weapons_sheet.png` (26 weapons as icon plus held at impact), `armour_jewellery_icons.png`, `combat_attacks_before_after.png`.
- `equipment_screen/equip_{empty,steel,mythos,eclipse,archer_f}_{before,after}.png`.
- `eclipse_dragon_closeup.png`: 4 directions plus attack at 1×, 3× zoom, and equipment preview at 1×.
- `anchor_check.json`: HP-bar clearance by zoom.
- `walk_compare_sheet.png`, `walk_compare.gif`, `walk_proof.json`.
- `CODE_REVIEW.md`, `ITEM_LOOKS.md`, `CURSOR_PROMPT.md`.
- `reference_code/`: `characters_all.patch` (applies cleanly to main @ ca336ee; adds `characters/armour_v2.py`), `hooks_only.patch`, and `files/`.
- `tools/`: headless renderers. Run them with the pygame venv, `SDL_VIDEODRIVER=dummy`, and `MYTHO_REPO=<patched clone>`.

## Try it
```
git apply characters_all.patch
USE_NEW_CHARACTERS=1 USE_NEW_EQUIPMENT_UI=1 python game/assets/mmorpg/client/client.py
```
