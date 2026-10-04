# Castle Realm — Phase C: Seller NPCs + Ownership Deeds / Plaques

**Status:** Design + data + concept art pack. Ready for Cursor (Step 1 investigate-only).  
**Flag:** `USE_CASTLE_OWNERS` (requires `USE_CASTLE_REALM`). Default **off**.  
**Not in this pack:** interior rebuild (A/B), knight AI (D), robbery (E).

## Contents

| Path | What |
|------|------|
| `CASTLE_OWNERS_CURSOR_PROMPT.md` | Full Cursor prompt (David’s rules, bank cap, steps, acceptance) |
| `json/sellers.json` | 4 sellers, dialogue trees, prices, spawn hints |
| `json/ownership_schema.json` | Deed ids, plaque text, weekly tax, persistence, buy/tax flows |
| `json/owners_registry.json` | Compact index |
| `sprites/standees/` | Concept 1x/2x standees + sheet (PIL; refine if &lt;8/10) |
| `sprites/plaques/` | For Sale / owned example signs |
| `previews/sellers_collage.png` | Preview collage |
| `previews/sellers_lineup_*.png` | Lineup reference |
| `castle_owners_pack.zip` | Zipped deliverable |

## Sellers (locked)

| Castle | NPC | Deed | Weekly tax | Seller (realm) | Plaque (realm) |
|--------|-----|------|------------|----------------|----------------|
| Duskspire (`gothic`) | Marcelline the Shade Broker | 25,000,000 | 100,000 | (52, 77) | (47, 76) |
| White Rose | Seraphine, Rose Seneschal | 40,000,000 | 150,000 | (257, 85) | (252, 84) |
| Sky-Anchor | Dockmaster Veyra Skychain | 55,000,000 | 200,000 | (52, 167) | (47, 166) |
| King’s | Herald Aldric Crownvale | 80,000,000 | 300,000 | (152, 77) | (147, 76) |

Spawns derived from `phase4/work/json/castle_realm_map.json` `gate_apron` entries: seller on grass east of apron; plaque on existing `l` signpost tile west of apron.

## Dialogue (plan-matched)

1. Buy castle (bank) → deed → plaque owner name  
2. Hire/fire knights — **placeholder** → Phase D / `USE_CASTLE_GUARDS`  
3. Place knight outside/inside — **placeholder** → Phase D  
4. View vault status — **placeholder** (locked / empty) → Phase E / `USE_CASTLE_VAULTS`  
5. Upkeep info (+ bank-cap reminder)  
6. Goodbye  

## Bank note (mandatory in Cursor prompt)

`MAX_BANK_COINS` on main is **10,000,000**. Recommend raise to **200,000,000** or 25M–80M purchases cannot succeed. Do not assume it is already raised.

## Art note

Standees are **fast PIL concept art** (OSRS-ish pixel standees), not final Blender meshes. Quality self-score ~**7/10** as concepts; Cursor/art pass should push to **≥8/10** vs OSRS shop NPCs before ship. Blender skipped for turnaround speed (available on box if a later pass needs 3D).

## How to use

1. Unzip `castle_owners_pack.zip` into the Mythoscape castle_realm assets tree.  
2. Paste `CASTLE_OWNERS_CURSOR_PROMPT.md` into Cursor.  
3. Enforce Step 1 investigation → STOP before any edits.

## Related

- Plans: `../CASTLE_INTERIOR_REDESIGN_PLANS.md`, `../APPROVAL_SUMMARY.md`  
- Realm map / gates: `../phase4/work/json/castle_realm_map.json`  
- Per-castle JSON: `../work/json/gothic_castle.json`, `../phase2/.../white_rose_castle.json`, `../phase3/.../king_castle.json`, `../phase4/.../sky_anchor_castle.json`
