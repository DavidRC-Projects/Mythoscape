# Mythoscape Player Housing — King's Row Estate

10 player-owned homes (2–3 floors) in the SW bottom corner of the map,
sold by the Estate Agent for 1M–50M gold with weekly 50k lease to the king.

## Estate
- Plot world tiles: (4,96)–(51,141) = 48×46
- Gate: (27,141)
- Flag: `USE_PLAYER_HOUSING`

## Price tiers
- **Willow Cottage** (`willow_cottage`): 1,000,000 gold · 6×5 · 2 floors · door (9,132)
- **Reed Cottage** (`reed_cottage`): 2,000,000 gold · 7×5 · 2 floors · door (17,132)
- **Meadow House** (`meadow_house`): 3,500,000 gold · 8×6 · 2 floors · door (27,132)
- **Oak Villa** (`oak_villa`): 5,000,000 gold · 9×6 · 2 floors · door (37,132)
- **Ash Manor** (`ash_manor`): 7,500,000 gold · 10×7 · 2 floors · door (11,122)
- **Cedar Townhouse** (`cedar_townhouse`): 10,000,000 gold · 8×8 · 3 floors · door (22,122)
- **Stonehaven Row** (`stonehaven_row`): 15,000,000 gold · 10×8 · 3 floors · door (33,122)
- **Riverview Estate** (`riverview_estate`): 25,000,000 gold · 12×9 · 3 floors · door (12,110)
- **Crown Villa** (`crown_villa`): 35,000,000 gold · 14×10 · 3 floors · door (27,110)
- **King's Folly** (`kings_folly`): 50,000,000 gold · 14×11 · 3 floors · door (43,110)

## Lease flow
1. Buy from Estate Agent Mira → pay `price_gold` from `bank_coins` → receive `deed_<key>`.
2. House name plaque shows the owner's display name (vacant = "For Sale").
3. Every 7 days: auto-debit **50,000** from `bank_coins` to the king; chat reminder.
4. If bank cannot pay: **1 week grace**; still unpaid → lose property, deed void.

## Bank note
- Current `MAX_BANK_COINS` = 10,000,000.
- Top tier is 50,000,000 → Step 1 must raise bank cap (recommend 100,000,000).

## Checker
```
python3 work/tools/housing_data.py
```

## Pack contents
- `json/` estate + per-house footprints/doors/floors/walkability
- `sprites/{1x,2x}/` ground/body/cutaway layers
- `floors/` interior previews per level
- `concepts/hero/` 3/4 renders
- `HOUSING_CURSOR_PROMPT.md` — Step 1 investigation only

## Score vs OSRS / RuneScape housing: **8/10**

**Hits:** Distinct 1M–50M tiers with scaling footprints and 2–3 floors; estate agent + deed + name plaque; weekly bank lease with grace/repossess; OSRS low-poly layered sprites (same camera/kit as the buildings pack); walkable/door/floor JSON + checker PASS; SW estate placement clear of dungeon/mine/city.

**Weaknesses:** Not a POH construction/editor (no room hotspots / flatpack furniture skill); interiors are preview scenes, not interactable prop sets; houses share one parametric builder (size/palette/roof vary more than unique floor plans); `MAX_BANK_COINS` is still 10M in main (top tiers need a later raise); estate grounds sprite is lanes/fence, not a single baked street with all ten bodies; fast software-GL samples soften some sprites.
