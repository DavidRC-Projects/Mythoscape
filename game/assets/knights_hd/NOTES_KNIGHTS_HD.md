# Mythoscape HD attackable knights: notes

Built on the box only (Blender 4.2 Cycles, CC0 stylized Human Base Meshes, custom FK rig). Nothing was copied to David's Mac. `/workspace/player_hd/` was read for conventions only and was not modified.

## What the monster code shows (main @ d693040)
| id | name / lvl | content.py fields that matter | old look | old draw path |
|---|---|---|---|---|
| `knight` | Castle Knight 48 | aggro 0, patrol, reach 1 (default) | legacy `castle_knight.png` preview | `_draw_mon` → legacy_creature_sprites (flip + bob) → procedural `draw_knight` |
| `shadow_knight` | Shadow Knight 88 | aggro 8, wander 3, reach 1 | legacy `shadow_knight.png` | legacy preview / procedural `draw_shadow_knight` |
| `knight_captain_vorn` | boss 92 | `visual: shadow_knight`, `tint (255,80,60)`, **scale 1.2**, aggro 7, force_retaliate | recoloured shadow knight + tint halo | same as shadow_knight + `void_v2_client.tint_and_halo` |
| `barrow_knight` | 44 (Depths) | `visual: shadow_knight`, tint, **side_by_side, attack_range 2, side_gap 2, attack_cooldown 1.1**, aggro 6 | recoloured shadow knight | same |
| `sir_aldric` | boss 52 (Depths) | `visual: shadow_knight`, tint, **scale 1.3**, side_by_side, range 2, gap 2, cooldown 1.1, aggro 8 | recoloured shadow knight | same |
| `magma_knight` | 78 (Emberdeep) | aggro 8, wander 2, reach 1 | procedural only | `emberdeep_v2_client._draw_monster_sprite` → `sprites.draw_monster` (`_LEGS` biped stride) |

Combat timing (`server/server.py`, `server/combat.py`, `client/client.py`):
- `combat.py` holds only the formulas (hit chance, max hit, xp). Strikes resolve once per server tick (`TICK_SECONDS = 0.6`) in the combat loop: `can_strike` (alive, not frozen, cooldown `next_attack_at`, reach = chebyshev ≤ `attack_range`, or for `side_by_side`: same row and 1 ≤ |dx| ≤ range). The result is sent as a `COMBAT_EVENT` (`monster_hits_player` / `player_hits_monster`), then `mark_attacked()` starts `attack_cooldown`.
- The client starts the swing on that event (`attack_anims[id] = now + ATTACK_ANIM_SECS (1.05 s)`, ranged 0.72 s), and the hitsplat is queued and released at `strike_t = 0.48` (melee) / 0.58 (ranged). Arrows launch at 0.55 of the draw with a 0.32 s flight, and only dragons get a monster projectile. The knights use none.
- During swings, `face_toward_target` forces a side facing (±1). `"front"`/`"back"` only appear while walking.
- Hurt is a red tint while hp < max. On `DEATH` the server drops the monster from state, so today there is no death animation (it pops out). HP bar and nameplate use the generic `entity_anchor` lift.

## How the HD knights fit combat
- **Same tick and same timing:** nothing on the server changes. The attack's 6 frames use explicit `frame_starts [0, .14, .30, .42, .60, .80]` of the 1.05 s swing progress: wind-up f00–f01, strike f02, **impact f03 (0.42–0.60)**, follow-through f04, recovery f05. The hitsplat the client already releases at 0.48 lands on the impact frame. The swing includes a short lunge (about 0.085 m forward at impact).
- **Hit reaction:** 3 frames (0.36 s), started when this knight's hitsplat is released. The attack wins if it is mid-swing, and the red hurt tint stays on top.
- **Death:** 6 frames (0.9 s): stagger, knees buckle, fall, impact bounce, settle. Then hold and fade over 0.6 s from a client-side corpse snapshot taken on `DEATH`. Falls stay screen-horizontal so nothing clips: in `e`/`w` the knight falls backward, away from the target; in `s`/`n` it falls to the side.
- **Facing:** 4 separately rendered facings, `w` included (not mirrored), so the sword stays in the right hand. Swings use `e`/`w` as the client forces. The s/n swing frames are there for completeness.
- **Scale and anchor:** 175.6 px/m at 4x (43.9 at 1x), feet bottom-centre on the tile foot point. This is identical to npc_hd and the HD player pack (`player_hd/assets/meta.json`: 43.9 px/m, feet anchor), so player and knight share one ground line and scale. Bosses only get content `scale` (Vorn 1.2, Aldric 1.3).
- **Spacing:** the four reach-1 knights fight adjacent. Barrow and Aldric park 2 tiles away on the player's row (side_by_side, gap 2), and their impact frame reaches `impact_reach_tiles` (in meta.json) forward, so the blades meet in the gap. No overlap, no floating.
- **Anchors:** in meta.json, `anchors_4x["state/facing/NN"]` = `head_top` (health bar / hitsplat), `weapon_tip` (hit point), `weapon_hand`. Also `hit_point_4x[facing]` (tip on the impact frame) and `healthbar_y_offset_1x`.

## Scale check (important for side-by-side)
- The shared `fv_npc_helpers.sprite_camera` sets `ortho_scale` from the canvas width, but Blender's AUTO sensor fit applies it to the longer side. On portrait canvases this inflates the scale and pushes the feet down. I verified this by projecting the world origin:
  - npc_hd 384×512: real **234 px/m** with the feet at **y=544**. That is below the 512 canvas, so the NPC feet are cut off at the bottom edge (seen in batch2–4 frames, e.g. harbour_cook). Their meta says 175.6 px/m with feet at 472.
  - player_hd renders on square canvases, so it really is 87.8 px/m at 2x (43.9 at 1x) as its meta says.
- The knights set `sensor_fit = HORIZONTAL`, which gives a **true 175.6 px/m with the feet exactly at (256,528)**. They therefore match the HD player 1:1, so the two stand side by side without overlap or float. Next to the current npc_hd sprites they will read about 25% smaller, because those NPCs are drawn too big and have clipped feet. That NPC-pack bug is now fixed: all HD NPC sprite sets were re-rendered with `sensor_fit HORIZONTAL` (see /workspace/npc_hd_spritefix_PROGRESS.md), so NPCs, knights and the player are 1:1.
- The first knight sprite pass used the uncorrected helper (197.5 px/m, toes clipped). Those frames are kept, untouched, in `renders/<id>/sprite_4x/`, and the shipped assets come only from the corrected `sprite_4x_fix/` pass.

## Designs (each id = one fixed design)
| id | sex | design |
|---|---|---|
| `knight` | M | Polished Stonehaven steel with brass rivets and rolled edges, blue split tabard with silver hem, blue cape, plumed great helm (eye slits + breaths), longsword with fuller, blue heater shield with silver tower |
| `shadow_knight` | F | Void-black lacquered plate, violet glow rivets and sigil, jagged spined pauldrons, horned sallet with glowing slit, silver braid, tattered cape and skirt, serrated rune blade, void flame in the off hand |
| `knight_captain_vorn` | M | Crimson-black captain's plate with blackened-gold trim, spiked pauldrons + neck guards, hounskull helm with red eyes, crown spikes and red transverse crest, falchion, void-sigil tower shield |
| `barrow_knight` | M (undead) | Rusted grave iron with moss and verdigris bronze, open bascinet + mail aventail, gaunt face with green eyes, lank hair, shroud cape and skirt, notched sword, broken round shield |
| `sir_aldric` | M (undead lord) | Tarnished silver-gilt plate with sun emblem, winged open helm with broken crown, white beard, ember eyes, faded teal surcoat and cape, spectral ember longsword, battered teal heater with sun |
| `magma_knight` | F | Obsidian plate with glowing lava seams and shards, ram-horned helm with molten T-visor, fiery braid, charred skirt with ember hem, lava-core greatblade, molten drips from the off hand |

All six have articulated sabatons (lames + sole, no toe shapes), rolled plate edges, rivets, leather straps with buckles, belt and pouch, and edge wear, scratches and sheen in the materials.

## Frames
- 4 facings (s, e, n, w; w is rendered, not mirrored) × idle 4, walk 8, attack 6, hit 3, death 6 = 108 frames per knight. 4x 512×576 (feet 256,528), 2x 256×288 (128,264), 1x 128×144 (64,132), so the 40 px tile is at 1x.
- Hero 2048 (transparent + `_bg.jpg`) and portrait bust 1024/512 (+ bg).
- Contact shadow from a Cycles shadow catcher, baked soft and semi-transparent. It is feathered at the canvas edges so it is never cut hard (no dark blocks).

## Honest scores (vs commercial stylized fantasy assets, 10 = top AAA)
| id | hero / portrait | in-game sprite (1x/2x) | main limits |
|---|---|---|---|
| knight | 7.5 | 8 | sword reads a bit flat/beige in the hero; tabard is good; head slightly large (stylized base body) |
| shadow_knight | 7.5 | 8 | strong silhouette and glow; black-on-black loses some plate detail in shadow |
| knight_captain_vorn | 7.5 | 8 | best boss read (crest, spikes, tower shield); the crest is a flat fan |
| barrow_knight | 8 | 8 | rust, moss and verdigris sell it; the broken shield reads well |
| sir_aldric | 7.5 | 8 | sun shield and crown good; the beard is a simple shape |
| magma_knight | 7.5 | 8 | v2: lighter obsidian, hot-bronze trim, fewer and larger lava seams, red-brown skirt, so it now separates at 1x; still the darkest of the six |
Overall: about 7.5 on the hero renders and 8 on sprites at game size. These are good indie/commercial-stylized quality, but not AAA. Lifting the heroes to 8.5+ would take sculpted (not procedural) helm and plate detail plus hand-tuned materials.

## Known limits
- The s-facing attack impact and follow-through (f03/f04) and some s-facing death frames put the blade tip a few px past the bottom edge. The client never shows s-facing swings (it forces ±1). The death cases lose only the tip, at most 1–4 px at 1x.
- Vorn's crest touches the side edge in death e/w f05 (a few px).
- The game had no death or hit visuals before. These frames need the small client additions in the Cursor prompt (corpse snapshot on `DEATH`, hit timer on the hitsplat release). There are no server changes.

## Measured combat anchors (from meta.json)
| id | health bar y offset @1x (from feet, before boss scale) | impact reach, tiles (incl. boss scale) | fights |
|---|---|---|---|
| knight | -82.8 | 1.25 | adjacent (reach 1) |
| shadow_knight | -79.2 | 1.28 | adjacent |
| knight_captain_vorn | -82.8 (×1.2) | 1.61 | adjacent |
| barrow_knight | -77.0 | 1.20 | side-by-side, gap 2 → blade passes the midpoint (1.0) |
| sir_aldric | -75.0 (×1.3) | 1.69 | side-by-side, gap 2 → crosses the midpoint |
| magma_knight | -73.8 | 1.33 | adjacent |

Previews: `previews/knights_hd_lineup_grey.png` (feet on one baseline over a tile grid, 2x and 1x) and `previews/knights_hd_contact_sheet.png` (heroes, 4 facings, walk/attack/hit/death strips).
