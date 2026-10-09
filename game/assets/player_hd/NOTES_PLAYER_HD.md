# Mythoscape – HD Player (paper-doll) set — NOTES

Destination on the Mac: `game/assets/player_hd/` (zip root `player_hd/`).
Integration steps: see `PLAYER_HD_CURSOR_PROMPT.md` (small steps, on main, no PR).

## 1. What is in the set
- `assets/meta.json`: canvas, feet anchor, anims, frame counts, sample points, combat sync, compose rules.
- `assets/catalogue.json`: items (id, slot, name, price, starter, tint, z per facing), defaults, hair palette, tier tints, override rules.
- `assets/anchors.json`: per sex/anim/facing/frame `head_top`, `chest`, `hand_R`, `hand_L`, and weapon `tip`, in 2x px.
- `assets/<sex>/<scale>/<layer>/<anim>_<facing>.png`: horizontal strips. Tinted layers also ship a `<anim>_<facing>_tint.png` part.
  - Scales: 2x (288×288, feet 144,248) and 1x (144×144, feet 72,124).
  - 4x (576×576) is idle frame 0 only, for creator/shop previews.
- `previews/`:
  - `creator_options_contact_sheet.png`: every skin/hair/colour/item option at 4x;
  - `outfits_male_4facings.png`, `outfits_female_4facings.png`: composed looks incl. bronze/steel/mithril/adamant armour, s/e/n/w;
  - `anim_frames_2x.png`: idle/walk/melee/ranged/skilling at game size;
  - `combat_states_2x.png` (2x in-game size): melee with contact frame + swing smear, hit and death in 4 facings, ranged with release frame and the arrow-origin anchor, plus a 1-tile footprint line;
  - `hero_lineup_grey.png` and `hero/*.jpg`: 8 high-sample hero renders (4 male, 4 female looks).
- `src/`: the full Blender pipeline (rebuildable). Blender 4.2, Cycles, AgX Medium High Contrast.

## 2. Scale / anchor / footprint (same as NPC + monster packs)
- Same 30° orthographic camera and the same 87.8 px/m at 2x as the batch NPC packs.
- Feet sit at the canvas bottom-centre anchor and are blitted like `npc_hd_client.draw_npc`: feet on the tile centre, one-tile footprint.
- The canvas is bigger than the NPC canvas (288 vs 192 wide) **only** for sword reach and the death fall. The body pixel size is identical.
- So the player never floats or overlaps a monster when the two stand side by side.

## 3. Paper-doll layers
- One rig per sex. Every layer is rendered with the body as a Cycles **holdout**, so the parts hidden by the body are already cut out.
- Compose by ascending `z[facing]`; west = east mirrored.

| layer | z (s / e,w / n) |
|---|---|
| shadow | 0 |
| cloak (back part) | 2 / 2 / 66 |
| body | 10 |
| brows | 12 |
| trousers | 20 |
| shoes | 24 |
| skirt | 28 |
| top | 40 |
| outfit | 45 |
| mid accessories | 50 |
| armour legs / feet / body / hands | 52 / 54 / 58 / 60 |
| front accessories | 62 |
| hair | 70 |
| helm | 80 |
| weapon | 90 / 90 / **8** (behind the body facing north) |
| shield | 92 / 3 / 92 |
| bow | 90 / 3 / 8 |

- **Tint:** the grey `_tint` part is multiplied by an sRGB colour (`hair_palette`, `tier_tints` × gain 1.25), then drawn over the fixed part.
  - Hair style and hair colour are independent.
  - Hair colour change costs 20 coins. At most 2 accessories.
- **Outfits** cover the top + bottom slots.
- **Armour** overrides the cosmetic slot it covers:
  - helm → hair;
  - platebody/chainbody → top + outfit;
  - platelegs → bottom + outfit;
  - gauntlets → gloves;
  - sabatons → shoes.
  - Taking the armour off restores the cosmetic. The cosmetic stays owned and saved.
- **Armour tier recolour:** one grey-steel render per piece. The tier colour comes from `tier_tints`:
  - bronze, iron, steel, mithril, adamant, mythos, eclipse; plus leather and wood for hilts/straps.
  - Leather straps and the wood grip are in the fixed (untinted) part, so only the metal changes colour.
- **Defaults for existing players** (no saved appearance):
  - male = side part / dark brown / linen shirt / work trousers / leather shoes;
  - female = ponytail / chestnut / linen shirt / long skirt / leather shoes;
  - light skin in both cases. The creator lets the player change all of this for free once.

## 4. Repo findings (read via GitHub, nothing edited)
- **Player draw:** `client.py` ~L5850 calls `sprites.draw_humanoid_detailed(...)` with `pose_walk`/`pose_attack`/skilling poses.
  - The HD hook wraps this call in `if hd_player and player_hd.ready: … else: <existing call unchanged>`.
- **Walk:** phase is `(t*1.15)%1`, 8 frames. HD walk frames are sampled at the same phase, so stride and foot plants line up.
  - `pose_walk`, `rs_style.py`, `rs_humanoid*.py`, `walk_proof.py` and `draw_humanoid*` are untouched.
  - Movement and tile interpolation are unchanged.
- **Options:** follow the `SET_OPTION` pattern of `auto_pickup_items` (client ~L1722, server ~L2681/~L5179, DB column).
  - The new `hd_player` option is a player setting, default on. 2D stays fully working.

### Combat (server/combat.py + client)
- **Server:**
  - tick 0.6 s; the player swings every 1.2 s (`next_swing_at = now + 1.2`).
  - Reach: `side_by_side` = same row, gap 1..reach (melee 1, ranged/magic longer).
  - Monsters use `can_strike` + `attack_cooldown`.
  - RS-style accuracy/max-hit formulas. **No attack styles** ("no prayers/styles in v0.1"), so there is no stab/slash/crush split. **One melee anim** matches the single `pose_attack`.
- **Client `handle_combat_event`:**
  - `ATTACK_ANIM_SECS 1.05`, `RANGED_ANIM_SECS 0.72`.
  - The hitsplat is queued for `now + anim_secs*strike_t`, with strike_t 0.48 melee / 0.58 ranged.
  - The arrow spawns at `anim_secs*0.55` and flies 0.32 s.
  - `attack_face` is always ±1 (east/west, "never front/back during a swing"). Humanoid foes swing back on the same beat.
- **Magic:** `MAGIC_CAST` only spawns `magic_fx` at the target. There is no player cast pose in 2D, so HD keeps the current anim (idle/melee frame) and adds no new timing.
- **Death:** the client shows a banner only. There is no hurt/death anim in 2D.

### How HD matches it (no timing changes at all)
- The HD frame is picked from the **existing** `_attack_progress` value (0..1): the last frame `i` with `sample_progress[i] ≤ progress`.
  - **Melee:** 10 frames sampled at `[0,.10,.22,.34,.48,.55,.62,.71,.80,.91]`. Frame 4 is the blade-contact pose exactly at 0.48 = `strike_t`, so the hitsplat appears on the contact frame, on the same tick as today.
  - **Ranged:** 8 frames at `[0,.12,.24,.36,.48,.55,.72,.86]`. Frame 5 = string release at 0.55 = the arrow-spawn time.
  - Ranged hitsplat at 0.58 (arrow arrival) is unchanged.
- **Projectile origin:** `anchors.json` `ranged/e/frame5/hand_L` (the bow hand). Mirror x for west.
- **Hitsplat and HP bar:** `head_top` per frame (stable during melee). Use the idle `head_top` for the HP bar so it does not bob.
- **Facing:** combat and skilling frames exist for east only (west mirrored), exactly like the 2D rule.
  - Hit and death exist in s/e/n (+w mirror). They play in whatever facing the player has.
- **New visual-only states (optional):**
  - `hit`: 4 frames over 0.36 s, played on a received hitsplat;
  - `death`: 8 frames over 1.2 s, held until respawn.
  - Neither changes server logic or timing.
- 2D combat is untouched. If HD is off or assets are missing, everything goes through the old path.

## 5. Honest scores (v2 polish pass; bar = commercial HD sprite sets, judged at in-game 2x)

| area | v1 | v2 | what changed / what limits it |
|---|---|---|---|
| Scale/anchor/footprint match with NPC + monster packs | 9 | 9 | unchanged |
| Combat timing sync | 9 | 9 | unchanged (contact f4 @0.48, release f5 @0.55) |
| Combat swing | 6.5 | **8** | 10 real phases (guard, lift, windup, accelerate, contact, follow-through x2, recover). Contact blade is level at an adjacent monster's chest (~1.0 m). Optional smear strip on f4/f5. Staff has its own layer |
| Armour | 7.5 | **8** | edge highlights + local AO on plate, articulated gauntlet lames, rivets, hems; tier tint unchanged |
| Layering / occlusion | 7.5 | **8** | garments are pushed out of the skin (no more hip/buttock holes through robes/skirts), shrunk holdout, staff flip handled per layer. Cross-layer overlaps are still z-order approximations |
| Cloth (folds, seams, materials) | 7 | **7.5–8** | local AO + edge wear make seams/folds/hems read; 16 samples + OIDN remove the dark-cloth noise. Folds are still procedural, not simulated |
| Hair | 7 | **7.5–8** | combed crop; stronger clumps with staggered tips; flyaways; feathered hairline; root-to-tip value; baked sway (walk/melee/hit). Long styles no longer cover the face in profile. Braid/ponytail still read as a cap from the front |
| Faces / skin | 7 | **7.5** | per-pixel liner, lid crease, socket/nose/lip/cheek shading, male stubble, no-glow darker irises, bolder brows, tuned SSS. Big step at 4x and in heroes; at 2x the head is ~20 px, so the face is eyes + brows + mouth spots. Male and female now read apart, but this is a pixel-budget limit, not a modelling one |
| Hands | 7 | **7.5** | fingers curl round grips; gauntlets have wrist/back/finger plates. At 2x a hand is 4–5 px |
| **Overall** | ~7–7.5 | **~8** | combat, armour and layering reach 8. Faces and hands stop at 7.5 at 2x because of pixel size; they read at 8+ at 4x / hero size |

## 6. Known gaps
- Goblin/leather items reuse the steel pieces with a leather tint.
- Amulet, ring and ammo are not drawn.
- No magic cast pose (none exists in 2D).
- Hit and death are new visual-only states.
- Hair sway is baked (no simulation). Some cross-layer occlusions are approximated by z-order.
- Leather jerkin + plate legs only: a sliver of lower back skin shows between them in the n facing (short jerkin hem).
- The hero renders were made before the push-out fix. They are front views, so nothing visible changes.
- Combat and skilling are side-only, matching the client rule.
- Render settings were trimmed to fit a shared, overloaded 8-core box: 12 samples at 2x and 64 at 4x, plus denoised heroes. v2 uses 16 samples + OIDN at 2x, so dark cloth is clean.
