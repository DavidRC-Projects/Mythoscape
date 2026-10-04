# Pets and legacy monsters — low-poly OSRS pass

Concept pack only. Nothing here is merged. David asked for pets and the old 2D monsters to match the low-poly monsters already made ("I like the look of the monsters you made before.").

Style bar: realistic-enough proportions, low-poly, flat-shaded, muted OSRS palette. Same Panda3D pipeline as `/workspace/monsters` (`mesh_builder.py`, `lighting.py`). Dragons and the husky are built with the existing `_dragon` / `_wolf` rigs. No textures, no smooth shading.

## What is in this folder

| Path | What |
|---|---|
| `MANIFEST.md` / `manifest.json` | Every pet (8) and every `content.py` monster id (32 unique). Current art, proposed sprite name, reuse vs new. |
| `previews/` | **12 new** concept PNGs (768 px) plus `contact_sheet.png`. Only creatures that do not already have a pack render. |
| `reused/` | Copies of the existing pack concepts that should be **referenced, not redrawn**. |
| `code/render_previews.py` | Headless renderer. Re-run with `/workspace/monsters_venv/bin/python code/render_previews.py`. |
| `PETS_AND_LEGACY_MONSTERS_CURSOR_PROMPT.md` | Incremental Cursor prompt. Step 1 is investigate-only, then STOP. |

## Counts

- Pets: 8. New previews: cat, white husky, frost dragon, mythic dragon. Reuse (do not redraw): skeleton → `skeleton_warrior`, green → `dragon_green`, crimson → `dragon_red`, shadow → `dragon_black`.
- Content monsters: 32 unique ids (`wolf` is defined twice in `content.py`; the later entry wins).
- Already on the new art at runtime (strips or dragon sheets): 20 ids, including visual aliases (`gallery_warden`, `nyxarath`, `morvath`, …).
- New monster previews: giant rat, city guard, castle knight, mythos champion, shadow knight, magma slug, ash imp, crucible beast.
- Three more ids share the new shadow knight sheet: `barrow_knight`, `sir_aldric`, `knight_captain_vorn`.
- Deferred (no preview): **Magma Knight** only.
- Pack models with no content id (do not spawn): goblin shaman, spider broodmother, ice giant, bog lurker, cave gnasher.

## Flag

`USE_NEW_PETS_AND_MONSTERS` in `server/feature_flags.py`, default **off** (`"0"`).

When off, pets and any monster not already on a strip/dragon sheet stay on today's procedural drawers.

When on, **swap sprites only**. Do not rewrite combat AI, drops, spawns, or the character walk cycle. Guards, knights and the champion currently call `draw_humanoid_detailed` (the player body). They must get their own sheets. Do not edit `rs_humanoid` or the player walk.

The existing hardcoded `USE_LOWPOLY_DRAGONS` and `USE_ANIM_STRIP_MONSTERS` (both `True` in `client.py`) already cover dragons and the mapped monsters. This flag must not turn those off.

## Score

**8/10** against `/workspace/monsters/images/contact_sheet.png`.

- Frost dragon, mythic dragon, husky: same rigs and lighting as the pack (about 9/10).
- Cat, giant rat, ash imp, magma slug: readable silhouettes in the same facet language (about 8/10).
- Armoured humanoids and the crucible beast are blockier than the hill giant / rot ghoul. Fine as OSRS concepts, not as sculpted.

## Do not

- Do not reuse HUD icon names or the `ui_hud` folders.
- Do not redraw a dragon, goblin, skeleton, spider, giant, wolf, wraith, ghoul, void, or golem that already has a render.
- Do not change the player walk cycle.
- Do not merge, push, or open a PR from this pack.
