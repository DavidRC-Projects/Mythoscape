# Cursor prompt: King's Court HD NPCs (King + 4 Mythos Knights) for Mythoscape

Repo: `DavidRC-Projects/Mythoscape`, branch **`castle-interiors-v2`** (or the interiors branch you are on). Game code is under `game/assets/mmorpg/`.
Asset pack: `npc_king_court_pack.zip` (or `npc_king_court_pack_part1.zip` + `part2…`). David copies the zip(s) onto the Mac; extract so the pack root is `npc_hd/` (assets, json, previews, this prompt, NOTES.md, manifest.json).

These five NPCs are a **permanent, always-on** part of the King's Castle Great Hall (`plane = king_f1`).

**NO feature flags.** Do not add `USE_KING_COURT`, `USE_NPC_HD`, or any other switch. Do not gate these NPCs behind an existing flag either. When you are done they are live by default in the Great Hall — same permanence as Fairy Village.

**Remove old NPC data** for this court. Delete / replace prior king and Mythos-knight sprites, registrations, placeholders, and dual-path fallbacks so only the new HD pack remains. Do not keep the old assets alongside the new ones.

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
5. **Remove old king / Mythos-knight NPC data** (sprites, content registrations, placeholders, dual paths). Replace with this pack; do not leave stubs beside the new assets.
6. Copy the art into **`game/assets/mmorpg/assets/npc_hd/`** (or `game/assets/npc_hd/` as pack root if that is where other HD NPC packs land — confirm in Step 1). Keep the pack layout: `assets/npcs/<id>/`, `json/`, `previews/`.
7. Take before and after screenshots of the Great Hall with and without the court.
8. **Never merge, never push, never open a PR.** Work on a local branch cut from the current interiors branch and leave it for review.
9. If something in this prompt contradicts the code, trust the code. Report the conflict instead of guessing.

---

## Step 1: Investigate, then STOP

Confirm each point against the current branch and report line numbers.

- **Interior plane `king_f1`**
  - `game/assets/interiors_v2/json/kings_interiors_v2.json` (or the live path the server loads): Great Hall room rect `(16,12)-(36,22)`, vestibule arrival tiles `(25,30)` and `(26,30)`.
  - Walkable chars include `.`. Verify proposed spawn tiles are `.`:
    - King `(26, 13)` facing south
    - Knights `(22,14)`, `(24,14)`, `(28,14)`, `(30,14)` facing south
  - If a tile is blocked, note it; the pack's `NOTES.md` / `json/king_court_spawns.json` already verified these on the interiors_v2 JSON copy.
- **How interiors spawn NPCs / talk**
  - Where castle / interior NPCs are registered (content, interiors loader, or plane-specific JSON).
  - How talk lines / dialogue packs are wired for interior NPCs (Fairy Village pattern if present).
  - How sprite sheets for NPCs are loaded (directory layout, `meta.json`, facings `s/e/n/w`, feet anchor).
- **Existing HD / Fairy Village NPC hooks**
  - Any loader for `game/assets/mmorpg/assets/fairy_village/…/npcs/` that can be reused with a one-line path or registry append for `npc_hd`.
  - Plan **permanent always-on** registration (no flag).
- **Old king / Mythos knight data to remove**
  - Find existing king NPC and any Mythos-knight / royal-guard placeholders on `king_f1` or in content tables (sprites, spawn entries, dialogue stubs, plane JSON).
  - List exact paths/ids that must be deleted or replaced in Step 3 so there is no dual path.
- **Protected walk files** listed above: confirm you will not open them for edit.

Report findings, then **STOP**.

---

## Step 2: Install art (after go-ahead)

1. Copy pack `assets/npcs/*` into `game/assets/mmorpg/assets/npc_hd/assets/npcs/` (or the confirmed pack root so paths match `manifest.json`).
2. Copy `json/king_court_spawns.json` beside other interior NPC data (or under `npc_hd/json/` as the pack specifies).
3. Do not convert, recompress, or rename sprite frames.

Each NPC folder contains:
- `<id>_hero_2048.png` (+ optional `_bg.jpg`)
- `portrait_bust.png` / `_512.png` / `_bg.jpg`
- `sprite_{1x,2x,4x}/{s,e,n,w}/f00.png …`
- `meta.json` (canvas, feet_px, frames, role, tile)

---

## Step 3: Remove old court NPCs, then register the five HD ones on `king_f1`

**3a. Remove old data first**
- Delete previous king / knight sprite assets and any placeholder art for these roles.
- Remove their spawn/registration/dialogue entries (content tables, interior JSON, client sprite maps).
- Do not leave a fallback that draws the old sprites if the new pack is missing — single path only.

**3b. Register the new pack**

Use `json/king_court_spawns.json` as the source of truth:

| id | name | tile | facing | role |
|----|------|------|--------|------|
| king | The King of Mythoscape | (26, 13) | s | ruler |
| mythos_knight_1 | Mythos Knight Valerius | (22, 14) | s | royal guard |
| mythos_knight_2 | Mythos Knight Cedric | (24, 14) | s | royal guard |
| mythos_knight_3 | Mythos Knight Roland | (28, 14) | s | royal guard |
| mythos_knight_4 | Mythos Knight Garrick | (30, 14) | s | royal guard |

Wire talk lines from the JSON (`talk` arrays). Keep them short. Prefer the smallest existing NPC spawn / dialogue hook (append entries; do not rewrite content tables wholesale).

Sprite draw: reuse Fairy Village / HD NPC blit path if it already respects `meta.json` feet anchors and 1x/2x/4x. Anchor feet on the tile; facing south toward the vestibule entrance.

---

## Step 4: Screenshots

1. **Before:** Great Hall empty (or prior state) from vestibule looking north.
2. **After:** King on the dais line with four Mythos knights flanking; player at (25,30)/(26,30).
3. Optional: talk UI with the King and one knight.

---

## Step 5: Done checklist

- [ ] Five NPCs visible on `king_f1` at the spawn tiles
- [ ] Facings correct (all south)
- [ ] Talk lines fire
- [ ] **No feature flag** — always-on permanent
- [ ] **Old king/knight NPC data removed** (no dual path / stubs left)
- [ ] No edits to walk-cycle protected files
- [ ] No merge / push / PR
- [ ] Before/after screenshots saved for review
