# Manifest — pets and legacy 2D monsters

Source of truth for ids: `game/assets/mmorpg/server/content.py` (`PETS`, `MONSTERS`) on Mythoscape `main`, read 2026-10-03.
Old pixels are procedural (no PNG): `game/assets/characters/procedural_sprites_finished.py`.
New low-poly pack already in repo: `game/assets/mmorpg/server/monsters/` and on this box `/workspace/monsters/`.

Runtime today (`client/client.py`, hardcoded, not `feature_flags.py`):
- `USE_LOWPOLY_DRAGONS = True` blits `client/assets/sprites/dragons/dragon_{green,red,black}_{idle,walk,attack,death}.png` for content type `dragon` only.
- `USE_ANIM_STRIP_MONSTERS = True` blits `server/monsters/anim_strips/<key>_anim.png` for the `TYPE_MAP` in `client/anim_strip_sprites.py`.
- Everything else, including every pet, still calls `sprites.draw_monster` / `sprites.draw_pet`.

| kind | content id | name | lv | action | proposed sprite | existing match | art now | preview in this pack |
|---|---|---|---:|---|---|---|---|---|
| pet | `cat` | Cat | 1 | new_preview | `pet_cat` | none | procedural draw_pet_cat — game/assets/characters/procedural_sprites_finished.py (no PNG; PETS['cat'].sprite='pet_cat') | previews/pet_cat.png |
| pet | `husky` | White Husky | 10 | new_preview | `pet_husky` | wolf rig, not the grey/dire renders | procedural draw_pet_husky — procedural_sprites_finished.py (sprite pet_husky) | previews/pet_husky.png |
| pet | `skeleton_pet` | Skeleton | 25 | reuse_existing | `skeleton_warrior` | skeleton_warrior | procedural draw_pet_skeleton — procedural_sprites_finished.py (sprite pet_skeleton) | reused/skeleton_warrior.png |
| pet | `dragon_pet` | Green Dragon | 50 | reuse_existing | `dragon_green` | dragon_green | procedural draw_pet_dragon — procedural_sprites_finished.py (sprite pet_dragon) | reused/dragon_green.png |
| pet | `dragon_crimson` | Crimson Dragon | 65 | reuse_existing | `dragon_red` | dragon_red | procedural draw_pet_dragon_crimson (sprite pet_dragon_crimson) | reused/dragon_red.png |
| pet | `dragon_frost` | Frost Dragon | 75 | new_preview | `pet_dragon_frost` | none (ice giant is not a dragon) | procedural draw_pet_dragon_frost (sprite pet_dragon_frost) | previews/pet_dragon_frost.png |
| pet | `dragon_shadow` | Shadow Dragon | 85 | reuse_existing | `dragon_black` | dragon_black | procedural draw_pet_dragon_shadow (sprite pet_dragon_shadow) | reused/dragon_black.png |
| pet | `dragon_mythic` | Mythic Dragon | 99 | new_preview | `pet_dragon_mythic` | none | procedural draw_pet_dragon_mythic (sprite pet_dragon_mythic) | previews/pet_dragon_mythic.png |
| monster | `goblin` | Goblin | 8 | reuse_existing | `goblin_grunt` | goblin_grunt | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/goblin_grunt.png |
| monster | `skeleton` | Skeleton | 15 | reuse_existing | `skeleton_warrior` | skeleton_warrior | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/skeleton_warrior.png |
| monster | `big_skeleton` | Big Skeleton | 30 | reuse_existing | `skeleton_mage` | skeleton_mage | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/skeleton_mage.png |
| monster | `spider` | Giant Spider | 48 | reuse_existing | `spider_giant` | spider_giant | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/spider_giant.png |
| monster | `giant` | Giant | 28 | reuse_existing | `giant_hill` | giant_hill | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/giant_hill.png |
| monster | `wolf` | Wolf | 40 | reuse_existing | `wolf_grey` | wolf_grey | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/wolf_grey.png |
| monster | `ember_wolf` | Ember Wolf | 58 | reuse_existing | `wolf_dire` | wolf_dire | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/wolf_dire.png |
| monster | `shade` | Shade | 55 | reuse_existing | `barrow_wraith` | barrow_wraith | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/barrow_wraith.png |
| monster | `crypt_ghoul` | Crypt Ghoul | 62 | reuse_existing | `rot_ghoul` | rot_ghoul | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/rot_ghoul.png |
| monster | `void_imp` | Void Imp | 70 | reuse_existing | `void_spawn` | void_spawn | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/void_spawn.png |
| monster | `obsidian_colossus` | Obsidian Colossus | 78 | reuse_existing | `stone_golem` | stone_golem | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/stone_golem.png |
| monster | `void_horror` | Void Horror | 95 | reuse_existing | `void_brute` | void_brute | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/void_brute.png |
| monster | `dragon` | Adamant Dragon | 78 | reuse_existing | `dragon_green` | dragon_green | legacy procedural drawer, but runtime already swaps to new art when USE_ANIM_STRIP_MONSTERS / USE_LOWPOLY_DRAGONS (both hardcoded True in client.py) | reused/dragon_green.png |
| monster | `gallery_warden` | Gallery Warden | 68 | reuse_existing | `rot_ghoul` | rot_ghoul | content visual='crypt_ghoul' → existing strip rot_ghoul (client passes visual into anim_strip_sprites) | reused/rot_ghoul.png |
| monster | `void_crawler` | Void Crawler | 82 | reuse_existing | `void_spawn` | void_spawn | content visual='void_imp' → existing strip void_spawn (client passes visual into anim_strip_sprites) | reused/void_spawn.png |
| monster | `rift_wraith` | Rift Wraith | 91 | reuse_existing | `barrow_wraith` | barrow_wraith | content visual='shade' → existing strip barrow_wraith (client passes visual into anim_strip_sprites) | reused/barrow_wraith.png |
| monster | `nyxarath` | Nyxarath, the Hollow Eclipse | 110 | reuse_existing | `void_brute` | void_brute | content visual='void_horror' → existing strip void_brute (client passes visual into anim_strip_sprites) | reused/void_brute.png |
| monster | `ossuary_keeper` | Ossuary Keeper | 34 | reuse_existing | `skeleton_mage` | skeleton_mage | content visual='big_skeleton' → existing strip skeleton_mage (client passes visual into anim_strip_sprites) | reused/skeleton_mage.png |
| monster | `drowned_dead` | Drowned Dead | 36 | reuse_existing | `skeleton_warrior` | skeleton_warrior | content visual='skeleton' → existing strip skeleton_warrior (client passes visual into anim_strip_sprites) | reused/skeleton_warrior.png |
| monster | `morvath` | Morvath, the Bone King | 70 | reuse_existing | `skeleton_mage` | skeleton_mage | content visual='big_skeleton' → existing strip skeleton_mage (client passes visual into anim_strip_sprites) | reused/skeleton_mage.png |
| monster | `giant_rat` | Giant Rat | 3 | new_preview | `giant_rat` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: overworld starter field (spawns ~10–24, 60–72) | previews/giant_rat.png |
| monster | `guard` | City Guard | 28 | new_preview | `guard` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Stonehaven streets, many spawns | previews/guard.png |
| monster | `knight` | Castle Knight | 48 | new_preview | `castle_knight` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Castle yard | previews/castle_knight.png |
| monster | `mythos_champion` | Mythos Champion | 90 | new_preview | `mythos_champion` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Castle elite, one spawn | previews/mythos_champion.png |
| monster | `shadow_knight` | Shadow Knight | 88 | new_preview | `shadow_knight` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Void Sanctum | previews/shadow_knight.png |
| monster | `barrow_knight` | Barrow Knight | 44 | shares_new_preview | `shadow_knight` | shadow_knight (new preview, not an old pack render) | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Depths | previews/shadow_knight.png |
| monster | `sir_aldric` | Sir Aldric the Unquiet | 52 | shares_new_preview | `shadow_knight` | shadow_knight (new preview, not an old pack render) | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Depths | previews/shadow_knight.png |
| monster | `knight_captain_vorn` | Knight-Captain Vorn | 92 | shares_new_preview | `shadow_knight` | shadow_knight (new preview, not an old pack render) | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Void Sanctum | previews/shadow_knight.png |
| monster | `magma_slug` | Magma Slug | 22 | new_preview | `magma_slug` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Emberdeep | previews/magma_slug.png |
| monster | `ash_imp` | Ash Imp | 38 | new_preview | `ash_imp` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Emberdeep | previews/ash_imp.png |
| monster | `crucible_beast` | Crucible Beast | 88 | new_preview | `crucible_beast` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Emberdeep | previews/crucible_beast.png |
| monster | `magma_knight` | Magma Knight | 78 | deferred | `magma_knight` | none | procedural drawer in procedural_sprites_finished.py; not in anim_strip TYPE_MAP. Where: Emberdeep | — |
| pack_only | `None` | Goblin Shaman | — | available_unused | `goblin_shaman` | goblin_shaman | /workspace/monsters/images/goblin_shaman.png (also game/assets/mmorpg/server/monsters/images/goblin_shaman.png) | (not copied) /workspace/monsters/images/goblin_shaman.png |
| pack_only | `None` | Spider Broodmother | — | available_unused | `spider_broodmother` | spider_broodmother | /workspace/monsters/images/spider_broodmother.png (also game/assets/mmorpg/server/monsters/images/spider_broodmother.png) | (not copied) /workspace/monsters/images/spider_broodmother.png |
| pack_only | `None` | Ice Giant | — | available_unused | `giant_ice` | giant_ice | /workspace/monsters/images/giant_ice.png (also game/assets/mmorpg/server/monsters/images/giant_ice.png) | (not copied) /workspace/monsters/images/giant_ice.png |
| pack_only | `None` | Bog Lurker | — | available_unused | `bog_lurker` | bog_lurker | /workspace/monsters/images/bog_lurker.png (also game/assets/mmorpg/server/monsters/images/bog_lurker.png) | (not copied) /workspace/monsters/images/bog_lurker.png |
| pack_only | `None` | Cave Gnasher | — | available_unused | `cave_gnasher` | cave_gnasher | /workspace/monsters/images/cave_gnasher.png (also game/assets/mmorpg/server/monsters/images/cave_gnasher.png) | (not copied) /workspace/monsters/images/cave_gnasher.png |

## Notes per row

- `cat` — House cat, ~0.43 m. Not a wolf.
- `husky` — Same _wolf builder as Grey Wolf, cream coat, blue eyes, collar. Do not swap in wolf_grey.png.
- `skeleton_pet` — Same creature as Skeleton Warrior. Scale the sheet to ~0.65. Do not redraw.
- `dragon_pet` — Same green dragon. Pet scale ~0.55 of the combat model. Sheets already at client/assets/sprites/dragons/dragon_green_*.png.
- `dragon_crimson` — OPEN: content name is Crimson; pack model is Red Dragon. Treated as the same red-dragon family. Confirm before a separate crimson palette.
- `dragon_frost` — Shared dragon rig, ice palette, ~1.47 m. No frost dragon in the existing pack.
- `dragon_shadow` — OPEN: Shadow pet vs Black Dragon. Treated as the same charcoal dragon. Confirm before a separate shadow palette.
- `dragon_mythic` — Gold body, violet wings, elder horns, chest gem. ~1.92 m hatchling, not a recolor of black/red/green.
- `goblin` — Upper dungeon. Already in anim_strip_sprites.TYPE_MAP.
- `skeleton` — Upper dungeon. TYPE_MAP.
- `big_skeleton` — Mithril cavern. TYPE_MAP uses skeleton_mage (robed), not a bigger warrior.
- `spider` — Spider nest. TYPE_MAP. Broodmother exists but is unused.
- `giant` — Deep dungeon. TYPE_MAP. Ice giant exists but is unused.
- `wolf` — Mountain pass (overworld). TYPE_MAP. content.py defines key 'wolf' twice; the later entry wins.
- `ember_wolf` — Emberdeep. TYPE_MAP to dire wolf. Charred look is only approximate.
- `shade` — Void Sanctum. TYPE_MAP.
- `crypt_ghoul` — Void Sanctum. TYPE_MAP.
- `void_imp` — Void Sanctum. TYPE_MAP.
- `obsidian_colossus` — Void Sanctum. TYPE_MAP. rune_golem is a drawer alias, not a content id.
- `void_horror` — Void Sanctum. TYPE_MAP.
- `dragon` — Adamantite lair. USE_LOWPOLY_DRAGONS blits client/assets/sprites/dragons/dragon_green_*.png. Not an anim strip.
- `gallery_warden` — visual=crypt_ghoul. Already strips when flag path uses visual.
- `void_crawler` — visual=void_imp.
- `rift_wraith` — visual=shade.
- `nyxarath` — visual=void_horror. Boss. Reuse brute; unique boss art not in this pass.
- `ossuary_keeper` — Depths. visual=big_skeleton.
- `drowned_dead` — Depths. visual=skeleton. Tint is separate; sprite swap only.
- `morvath` — Depths boss. visual=big_skeleton, scale 2. OPEN: keep mage sheet at 2x, or a later unique Bone King.
- `giant_rat` — No pack equivalent. Still drawn by draw_giant_rat.
- `guard` — Uses draw_humanoid_detailed today. Sprite sheet only. Do not edit the player walk cycle.
- `knight` — Proposed file name castle_knight so it does not collide with the content id.
- `mythos_champion` — Gold plate, violet cape. Still the humanoid drawer today.
- `shadow_knight` — Also the visual for barrow_knight, sir_aldric, knight_captain_vorn.
- `barrow_knight` — visual=shadow_knight. Shares the new shadow_knight sheet.
- `sir_aldric` — visual=shadow_knight, scale 1.3, orange tint. Sheet shared; tint stays a client overlay.
- `knight_captain_vorn` — visual=shadow_knight. Shares the new sheet.
- `magma_slug` — No pack equivalent.
- `ash_imp` — Not void_spawn. Winged ash imp.
- `crucible_beast` — Not void_brute. Lava brute.
- `magma_knight` — DEFERRED. No preview this pass. Nearest later: castle_knight or shadow_knight with a magma palette. Do not invent stats.
- `goblin_shaman` — Low-poly art exists. No content.py monster id uses it. Do not spawn a new monster in this pass.
- `spider_broodmother` — Low-poly art exists. No content.py monster id uses it. Do not spawn a new monster in this pass.
- `giant_ice` — Low-poly art exists. No content.py monster id uses it. Do not spawn a new monster in this pass.
- `bog_lurker` — Low-poly art exists. No content.py monster id uses it. Do not spawn a new monster in this pass.
- `cave_gnasher` — Low-poly art exists. No content.py monster id uses it. Do not spawn a new monster in this pass.
