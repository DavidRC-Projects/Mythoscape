# Mythoscape HUD — ChatGPT Mockup Plates

Cropped from `mockup_01_fantasy_rpg_village_sidebar_chat.png` into blit plates + overlays + hitboxes for **pygame** (no pygame_gui).

## Score: **8.7/10** vs ChatGPT mockup

**Hits:** Literal crops of the target mockup (sidebar, chat, left-nav, action bar, minimap frame, zone chip); `*_full.png` for pixel parity; hole-punched plates for live text/icons; hover/selected overlays; `meta/hitboxes.json` (71 regions); before/after + reference comparison on live 2406×1596 layout; 1x halves.

**Weaknesses:** Hole/hitbox geometry is estimated (not pixel-perfect per control); scaled mockup→live may leave thin gaps where old flat HUD peeks; inventory grid hole grid is approximate; some overlays are synthetic neon (nav hover) vs extracted; baked mockup icons/text remain until live content fills holes.

## Flag
`USE_HUD_MOCKUP_PLATES`

## Draw order
world → zone → minimap → left_nav → sidebar → chat → action_bar → state overlays → live content in holes

## Files
- `sidebar/sidebar_inventory[_full][_1x].png` + `.json`
- `chat/chat_plate[_full][_1x].png` + `.json`
- `action_bar/`, `left_nav/`, `minimap/`, `zone/`
- `overlays/` — tab/nav/slot/btn states + zone_safe/danger
- `meta/hitboxes.json`
- `mockups/before_after.png`, `after_plates_on_live.png`, `plates_overview.png`, `reference_vs_plates.png`
- Prefer `*_full.png` for visual QA blit; hole-punched for engine.

## Hitboxes
Plate-local `[x0,y0,x1,y1]`. Screen = `anchor_live` + box (live artboard) or half for 1x.
