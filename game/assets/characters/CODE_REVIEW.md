# Mythoscape character rendering: code review (main @ ca336ee, 27 Sep 2026 11:58 BST)

Line numbers refer to **unmodified main**. Paths are relative to `game/assets/`.

## 1. Pipeline at a glance
| Step | Where |
|---|---|
| Players are drawn in `_draw_pl` (a closure inside the world draw). It calls `sprites.draw_humanoid_detailed(...)` with `weapon=weapon_style(eq["weapon"])`, `shield=bool(eq["shield"])`, `moving`, `t`, `facing`, `equipment=eq`, `attacking`, `action`, `gender` | `mmorpg/client/client.py:5493` |
| Player inputs: `mov = moving_for(key, x, y)`, `atk = _attack_progress(id, t)`, `face = facing_for_view(facing_for(...))`. Gathering sets `mov=False`; `atk>0` also sets `mov=False` ("freeze gait during the swing") | `client.py:5452-5487` |
| NPCs: `palette_for(nid)` (`characters/procedural_sprites_finished.py:771`), special colours for mad_scientist, herald_rowan and city_vendor_mira, `ROBED_NPC_IDS` (`client.py:118`), then `draw_humanoid_detailed` | `client.py:~5280-5300` |
| Wrapper that forwards to the skeletal drawer | `characters/procedural_sprites_finished.py:3775` to `characters/rs_humanoid.py:1619 draw_skeletal_humanoid` |
| Global scale: `s = rs.unit(tile,"character") = tile/32*2.5` (3.125 px per unit at TILE=40), ×0.96 for female | `characters/rs_style.py:53`, `rs_humanoid.py:1664-1667` |
| Name and HP bar anchor: `entity_anchor(cx,cy)` gives `hp_y = cy - label_lift` (18 s), `name_y = hp_y-16` | `client.py:6479`, `rs_style.py:67` |

## 2. Body parts and proportions (units of s)
**Side view** (`rs_humanoid.py:1738-2209`). Left facing is drawn as right facing on a temp surface and then flipped (`:1632-1660`).
- Joints: `pelvis=(cx+sway, cy+3.2+bob)`. `torso_len` 13.5 (12.8 F). `arm_len` 11.2. `leg_len` 13.6 (13.2 F). Hip half-width 2.5 (3.15 F), shoulder half-width **5.2** (4.6 F): the shoulders are frontal width even in profile.
- `neck = joint(pelvis-1.5, -π/2 + (torso-DOWN)*0.28, torso_len)` (`:1745`).
- Knee = hip + 0.48·leg along `leg_*`. Foot = knee + 0.52·leg along `leg_*+knee_*`, minus `foot_lift`. Ground `foot_y = max(feet)+2.4` (`:1753-1776`).
- Limbs are `rs.draw_volume_limb` (`rs_style.py:291`), with photo-texture detail (`draw_volume` at `:196` plus `building_textures`). That texture is the checker/dither noise visible in the screenshots.
  - Thigh 2.15 half-width (2.35 F), calf 1.75 (`:1819-1826`).
  - Sleeve **1.75**, forearm **1.45** (`:2019-2020`, `:2205-2206`). These are the "forearm blocks": about 9 px wide at TILE 40.
- Chest polygon from the pelvis to the neck (`:1889-1905`). Deltoid circles, then plate pauldron discs of radius **2.6** (the huge shoulder pads).
- Belt/hip block `:1856-1870`. Female skirt/flare `:1838-1855`.
- **Proportion problem:** the head is about 7.2 s tall on a figure about 31 s tall (4.3 heads). Shoulders are 10.4 s wide in every view, and the limbs are thick. The result is boxy and chibi.

**Front/back view** (`_draw_ortho_humanoid`, `rs_humanoid.py:1228-1616`)
- `pelvis=(cx, cy+3.2+bob)`, `bob=root_bob*s*0.55`. `neck=pelvis-13.0` (12.4 F). Hip half-width 2.85 (3.3 F), shoulders 5.5 (5.1 F) at neck+2.6.
- Knees at hip+6.3. Feet at hip+12.7. Elbows at sh±0.5, +4.8. Hands at sh±0.65, +9.3.
- Chest trapezoid is 4.0 s wide at the pelvis and 4.4 s at the neck (`:1356-1375`). Pauldron circles 2.5 s. Belt `:1420`.

## 3. Face (`rs_humanoid.py`)
- The head centre is `neck-(0,0.35)` front/back (`:1445`) and `neck+(0.2f,-0.5)` side (`:2034`).
- Front faces (`:1523-1608`): white eye ellipses 1.0×0.8 s with blue iris and pupil, thick brows, nose line, and a big jaw.
- Side faces (`:2034-2202`): a large skull plus a protruding nose and chin.
- At about 3 px per unit the eyes become 3 px white blobs. That is the "crude face".

## 4. Hair
- Back view: a full hair cape for female (`:1460-1497`) and a hair cap for male (`:1504-1521`).
- Front: fringe/cap polygons (`:1525-1597`).
- Side: inside the side-face block.
- Colours: `hair_m=hair_color`, `hair_d=shade(-36)`. The female default is swapped to (92,48,36) when the default brown is passed (`:1719`).

## 5. Skin and clothing colours (`rs_humanoid.py:1690-1725`)
- Shirt: `body_color` with light/dark from `rs.shade`.
- Armour ids (leather, chain, plate, `*_body`, goblin_mail) use `rs.metal_palette(id)` (`rs_style.py:857`). These are saturated (e.g. adamant (70,180,110), mithril (100,160,200)).
- Pants default to (72,74,82), or `metal_palette(legs)`.
- Female overrides, used whenever no armour is worn (`body_color` is ignored):
  - pants (118,72,98)
  - shirt (168,92,118)
- Boots: (92,62,38) male, (110,58,72) female, or the legs material.
- The local player is always drawn with body (70,210,90) (bright green), skin (235,195,150) and hair (70,45,30) (`client.py:5443`).

## 6. Equipped items on the body, slot by slot
| Slot | How it is drawn |
|---|---|
| weapon | `_weapon_kind` (`:38`) maps to dagger, pickaxe, battleaxe (includes cleaver), axe, staff, bow, rod, or sword. `_draw_weapon` (`:62`) has one geometry per *kind*, coloured by `metal_palette(id)`. So bronze/iron/steel/mithril/adamant swords differ only in colour. Held weapon: `hand_near` + `pose["weapon"]` swing (`:2209`). Sheathed on the back when not attacking and action ∈ {None, "stand"} (`:1795-1814`, ortho `:1296-1320`, back view `:1441`) |
| shield | `_draw_shield` (`:527`): wooden, square, kite, mythos, eclipse (`:430`). Held off the far hand (`:2024-2031`) or on the back |
| helmet | `_draw_helmet` (`:661`) replaces the face/hair: med/full helm, mythos dragon helm, eclipse grill (`:714`) |
| body | Palette plus plate ridges, chain rings or leather lines on the chest. Pauldrons. Mythos and eclipse ornaments (`:959`, `:1029`) |
| legs | Palette on the leg limbs, knee plates (`:1827-1836`), eclipse leg ornament (`:1117`), boots coloured with the legs material |
| amulet | Only `tidehollow_medal`/amulet is drawn on the chest. Other amulets and rings are not visible |
| ammo | Not drawn on the body. Arrows exist only as projectiles |

## 7. Walk animation
- **Frames:** there are no frame indices. Animation is continuous-time: `t = time.time()` (`client.py:4924`) is passed through. `rs.resolve_pose(moving,t,attacking,facing,action,weapon_kind)` (`rs_style.py:687`) selects in this order: attack (melee `pose_attack:613`, bow `pose_ranged:554`), woodcutting, mining, fishing, stand, walk, idle.
- **Walk timing:** `pose_walk` (`rs_style.py:499`), cadence `TAU*1.15`, so one gait cycle takes 0.8696 s. It sets:
  - `root_bob = 0.22+0.40*(1-|cos ph|)`
  - `hip ±0.20*sin`
  - knee bend and `foot_lift = swing^1.15*0.55`
  - `hand_shift = sin(ph)` (0.9 s hand slide)
  - lean and cape sway.
- **Front/back:** `_draw_ortho_humanoid` recomputes its own phase `ph=t*TAU*1.15` with stride 0.75 s, arm swing 2.4 s (contralateral), `lift=max(0,cos)^1.2*0.45 s` and `bob=root_bob*0.55`.
- **Directions:** `facing_for` (`client.py:4989`) takes the travel delta and returns ±1 (side) or "front"/"back". `facing_for_view` maps it for the camera, and `_parse_facing` (`rs_humanoid.py:16`) parses it. Attacks and gathering force side view (`:1727`).
- **Moving flag:** `moving_for` (`client.py:5052`) holds the gait for 0.55 s after each tile step. Positions are tile-snapped (`cx,cy` = tile centre); there is no sub-tile interpolation.

## 8. Combat animations and effects
- Swing timing:
  - `attack_anims[id] = now + ATTACK_ANIM_SECS (0.62)` or `RANGED_ANIM_SECS (0.72)` (`client.py:343, 782`)
  - `_attack_progress` gives 0 to 1 (`client.py:6320`)
  - facing is locked with `face_toward_target` (`client.py:2255`) and `attack_face`.
- Melee: `pose_attack` goes brace → wind-up → commit → impact hold → follow-through → recover. `pose["weapon"]` (blade) drives the weapon angle in `_draw_weapon` (`rest=2.05·(1-combat) - 0.52·combat + swing·1.05`). The grip is pushed toward the enemy. Elbow flare is 0.22 in combat.
- Archery:
  - the bow is re-resolved with `weapon_kind="bow"` (`rs_humanoid.py:1676`) and uses `pose_ranged`;
  - the bow is drawn upright with a pulled string;
  - the arrow projectile starts at 55 % of the anim with a 0.32 s flight (`client.py:832-841`) and is drawn by `_draw_projectiles` (`client.py:6242`);
  - dragonfire uses the same system (`:843`).
- Hit feedback:
  - hitsplats are queued until the strike frame (`client.py:6359`) and drawn as RS-style splats (`client.py:6427`);
  - monsters get `hurt=` flashes (`client.py:5340-5391`). Players have no body flash.
  - a level-up glow is drawn under the player (`client.py:9170`).
- Click and target areas are tile-based (`screen_to_tile`, `client.py:3004`). They do not depend on the sprite shape.

## 9. Equipment panel UI (`client.py:9841-10085`)
- Modal rect (90,36,760,560), yellow border, title "Equipment & Stats".
- Left stage 340×460:
  - a column of 40 px slot boxes with 3-letter tags (HEL/AMU/…) and a name/item label;
  - item icons come from `sprites.draw_item_icon` (`procedural_sprites_finished.py:1692`) and are tiny;
  - the quiver count is shown;
  - a large `draw_humanoid_detailed(tile=118, action="stand")` preview and an HP bar;
  - a hover/first-worn detail box with Att/Str/Def and karma, and "Click slot to unequip".
- Right panel:
  - "Worn bonuses" with plain bars scaled to 200;
  - combat levels (potion boosts, gear), archery ranged bonuses, HP;
  - Karma line, Combat/Total;
  - footer "Hover a slot for details · Esc / E to close".
- Clicks: `handle_equipment_click` (`:10087`) uses `self.equip_slot_rects` (UNEQUIP), and a click outside the box closes the panel. `show_equipment` is toggled by E (`:1484`, `:1566`) and closed by Esc (`:1396`).

## 10. Item definitions (`mmorpg/server/content.py:15` ITEMS)
There are 102 equippable items (`equip_slot`): weapon 26, body 14, legs 13, shield 13, amulet 12, ring 10, helmet 8, ammo 6.

| Family | Items (tier = bronze<iron<steel<mithril<adamant<mythos/eclipse) |
|---|---|
| Swords | bronze_sword, iron_sword, steel_longsword, mithril_sword, adamant_sword, mythos_longsword |
| Daggers | bronze, iron, steel, mithril, adamant, mythos |
| Battleaxes | bronze, iron, steel, mithril, adamant; eclipse_cleaver (unique, bound to david) |
| Tools | bronze_axe (woodcutting), bronze_pickaxe (mining) |
| Bows (`weapon_type:"bow"`) | shortbow, oak, willow, maple, yew, magic shortbow |
| Body | leather_body, goblin_mail; bronze/iron/steel/mithril/adamant chainbody and platebody (`*_body`); mythos_body, eclipse_body |
| Legs | leather_chaps; bronze…adamant chainlegs and platelegs; mythos_legs, eclipse_legs |
| Helmets | leather_cowl; bronze…adamant helmet; mythos_helmet (dragon), eclipse_helmet (grill) |
| Shields | wooden_shield; bronze…adamant sq_shield and kiteshield; mythos_shield (kite), eclipse_shield (aegis) |
| Ammo | bronze…adamant arrow, arrow_quiver |
| Jewellery | 10 rings and 12 amulets with `gem_color` (gold, opal, jade, topaz, sapphire, emerald, ruby, diamond, onyx, void; bronze amulet; tidehollow and emberdeep medals) |

The game has no scimitar, mace, spear or staff items. `_weapon_kind` has a "staff" branch, but no item uses it.
The full per-item table with the new designs is in `ITEM_LOOKS.md`.
