# Mythoscape HUD redesign pack

Navy / gold fantasy HUD mockups matching David’s brief and the reference screenshot. **World stays top-down pixel; HUD only.**

## Score: **8.5/10** vs polished fantasy MMOs (OSRS clarity + modern MMO polish)

### Hits
- Full hierarchy: left nav, right sidebar, chat+quick chat, action bar, zone chip, minimap framing  
- Four primary systems with distinct Inventory / Crafting / Gathering / **Bags**  
- Inventory filters + Equip/Use/Split/Drop; bags called out as bulk storage  
- World event banner; PvP **Safe vs Danger** chrome  
- Before/after vs current Inv·Combat·Magic·Quests sidebar  
- `UI_CURSOR_PROMPT.md` — `USE_NEW_HUD`, Step 1 investigate-only, stop for approval, never merge/push  

### Weaknesses
- Mockup artboard 1326×892 vs live client 1200×800 (needs scale plan in Step 1)  
- Crafting/Gathering bodies are UX targets; not yet wired to forge/cook/`gathering` state  
- Quick-chat / channel filters need protocol + UI hooks (not in main today)  
- Title/lore/achievements are chrome placeholders until content APIs exist  
- Some panel crops use simplified icon glyphs vs final illustrated icons  

## Layout (target)
- Left nav · world viewport · right sidebar (~brief)  
- Chat bottom-left with channels + quick chat  
- Action bar bottom-center  
- Zone chip top-left; minimap top-right of world  

## Current game (code review)
See `work/CODE_REVIEW.md`. Today: 1200×800, sidebar tabs Inv/Combat/Magic/Quests, single chat log, bags as inventory filter + prompts, no left nav / world-event banner / PvP danger chrome as designed.

## Files
- `hud_overview.png` — overview collage  
- `mockups/` — full HUD states  
- `panels/` — close-ups  
- `reference/david_brief_hud.png` — canonical reference  
- `UI_CURSOR_PROMPT.md` — Cursor integration prompt  
