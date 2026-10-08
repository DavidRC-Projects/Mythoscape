# Cursor prompt: Overworld HD NPCs Batch 3 (Forest / Mine / Fringe) for Mythoscape

Repo: `DavidRC-Projects/Mythoscape`. Game code is under `game/assets/mmorpg/`.
Asset pack: `npc_hd_overworld_batch3_part*.zip`. David copies the zip(s) onto the Mac; extract so the pack root is **`npc_hd/`** (same tree as King court / batch1 / batch2 — assets land beside them under `game/assets/npc_hd/assets/npcs/<id>/`).

These eight NPCs are a **permanent, always-on** part of the overworld (forest / lake / mine / dungeon fringe / mountain pass). Content ids stay the same — **swap art only** / HD blit path like Fairy Village. **Do not move tiles.**

**NO feature flags.** Do not add `USE_OVERWORLD_NPC_HD`, `USE_NPC_HD`, or any other switch. Do not gate these NPCs behind an existing flag. When you are done they are live by default — same permanence as Fairy Village / King court / batch1 / batch2.

**Remove old NPC data** for these eight ids. Delete / replace prior sprites, registrations, placeholders, and dual-path fallbacks so only the new HD pack remains. Do not keep old assets alongside the new ones.

**Do NOT redo** fairy NPCs (`elowen_moonwhisper`, `warden_thorne`, `tumbleroot`, `pip_dewdrop`), King court (`king`, `mythos_knight_*`), batch1 ids (`shopkeeper_joe`, `jeweler_lira`, `fletcher_elena`, `blacksmith_gareth`, `banker_iris`, `elder_miriam`, `farmer_tom`, `innkeeper_sarah`), or batch2 ids (`wizard_elowen`, `guard_marcus`, `guard_aldric`, `village_kid_timmy`, `village_idiot_bob`, `priest_cedric`, `monk_healer`, `pet_keeper_luna`).

**Note:** `mine_scout` (Scout Elena) must stay visually distinct from batch1 `fletcher_elena` (Fletcher Elena).

---

## Hard rules (read first, apply to every step)

1. **Step 1 is investigation only. Change no files, report back, then STOP and wait for my go-ahead.**
2. Use small hooks. Do not rewrite or reorganise existing systems, and do not reformat files you touch.
3. **Never edit** (word-for-word protection — sprite NPCs only, not skeletal walk edits):
   - `pose_walk` and any walk posing in `rs_style.py`;
   - `rs_humanoid.py` and `rs_humanoid_v2.py`;
   - `tools/walk_proof.py`;
   - `draw_humanoid` and `draw_humanoid_detailed`.

   The walk cycle must stay exactly as it is.
4. **No feature flags** — permanent always-on content only.
5. **Remove old NPC data** for these 8 ids (sprites, content registrations, placeholders, dual paths). Replace in place; do not leave stubs beside the new assets.
6. Copy the art into **`game/assets/npc_hd/`** (same pack root as King court / batch1 / batch2). Keep layout: `assets/npcs/<id>/`, `json/`, `previews/`.
7. Take before and after screenshots of forest/lake, mine fringe, dungeon hermit, mountain pass with these NPCs.
8. **Never merge, never push, never open a PR.** Work on a local branch and leave it for review.
9. If something in this prompt contradicts the code, trust the code. Report the conflict instead of guessing.
10. World **xy stay as in `content.py`** — do not move tiles. Ids stay exactly:
    `old_fisherman_pete`, `mia`, `mysterious_traveler`, `merchant_wanderer`, `mine_scout`, `dungeon_hermit`, `mad_scientist`, `pass_scout`.

---

## Step 1: Investigate, then STOP

Confirm each point against the current branch and report line numbers.

- **Existing NPC spawn system**
  - Where overworld NPCs are registered (`content.py` `NPCS` list or equivalent).
  - Confirm the eight ids above already exist with names/roles/shops/quests; line numbers for each.
  - Confirm **xy must not change** — report current x,y only; do not propose moves.
- **How sprite sheets for NPCs are loaded**
  - Directory layout, `meta.json`, facings `s/e/n/w`, feet anchor.
  - How Fairy Village HD NPCs / King court / batch1 / batch2 HD path blits (reuse that hook).
- **Existing HD hooks**
  - Any loader for `npc_hd/` that can be reused with a one-line path or registry append.
  - Plan **permanent always-on** registration (no flag).
- **Old data to remove for these 8 ids**
  - Find previous sprites / procedural stubs / dual-path fallbacks for exactly these ids.
  - List exact paths/ids that must be deleted or replaced in Step 3 so there is no dual path.
- **Protected walk files** listed above: confirm you will not open them for edit.
- Confirm `mine_scout` art is **Scout Elena (mine)** — ochre/lantern — not Fletcher Elena (forest green/bow).

Report findings, then **STOP**.

---

## Step 2: Install art (after go-ahead)

1. Copy pack `assets/npcs/*` into `game/assets/npc_hd/assets/npcs/` so paths sit beside King court / batch1 / batch2.
2. Copy `json/overworld_batch3_spawns.json` under `npc_hd/json/`.
3. Do not convert, recompress, or rename sprite frames.

Each NPC folder contains:
- `<id>_hero_2048.png` (+ optional `_bg.jpg`)
- `portrait_bust.png` / `_512.png` / `_bg.jpg`
- `sprite_{1x,2x,4x}/{s,e,n,w}/f00.png …`
- `meta.json` (canvas, feet_px, frames, role, sex)

---

## Step 3: Remove old sprites/regs for these 8 ids, then wire HD blit

**3a. Remove old data first**
- Delete previous sprites / placeholder art for these eight ids.
- Remove dual-path fallbacks that would draw old procedural art if HD is missing — single path only.
- Do **not** delete their `content.py` spawn entries or change x,y — keep ids and world positions; swap art only.

**3b. Register HD art**
- Wire into the existing NPC spawn / blit system the same way Fairy Village / King court / batch1 / batch2 HD does.
- No new feature flags. No spawn rewrites. No tile moves.

**3c. Dialogue / shop / quest**
- Leave talk lines, shops, quests as they are in `content.py`. Art-only change.

---

## Step 4: Screenshots + self-check

- Before/after screenshots near lake (Pete/Mia), forest traveler/merchant, mine (Scout Elena), dungeon hermit, potion lab (Mad Scientist), mountain pass (Scout Bren).
- Confirm idle sprites read at 1x (40 px/tile): hat/rod, child dress, hood, pack, lantern, rags, vials, fur collar.
- Confirm walk cycle files were never opened for edit.
- Confirm no feature flag was added.
- Confirm Scout Elena (`mine_scout`) is visually distinct from Fletcher Elena.

---

## Characters (ids exact)

| id | name | sex | role |
|----|------|-----|------|
| old_fisherman_pete | Old Fisherman Pete | M | weathered lake fisherman |
| mia | Mia | F | lost daughter (child scale) |
| mysterious_traveler | Mysterious Traveler | M | hooded cloaked traveler |
| merchant_wanderer | Wandering Merchant | M | traveling merchant |
| mine_scout | Scout Elena | F | mine/dungeon fringe scout |
| dungeon_hermit | Hermit Cole | M | dungeon fringe hermit |
| mad_scientist | Mad Scientist | M | potion lab scientist |
| pass_scout | Scout Bren | M | mountain-pass scout |

See `NOTES_OVERWORLD_BATCH3.md`, `json/overworld_batch3_spawns.json`, `previews/overworld_batch3_contact_sheet.png`, `manifest.json`.
