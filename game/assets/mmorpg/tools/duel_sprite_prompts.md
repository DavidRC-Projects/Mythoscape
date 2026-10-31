# Duel sprite pose sheets (painted HD fighters for client/arena_duel_ui.draw_stage)

Pipeline (re-runnable):
1. `python tools/duel_hero_ref.py REFDIR` on the machine with the latest player_hd art -> hero_{sword,axe,bow}_ref.png.
2. Generate one 16:9 sheet per id with an image model, using the prompts below (refs: hero ref PNGs + hero_sword sheet;
   bosses: their cinematic standoff shot or boss ref). Save as SHEET_DIR/<id>_sheet.jpg.
3. `/path/to/rembg-venv/python tools/duel_sprites.py SHEET_DIR [ids]` -> client/assets/castle_realm/arena/duel_sprites/<id>/{idle,attack,block,dodge,hit}.png
4. Check tools output with a contact sheet; bad frames -> edit the sheet (keep other poses) and re-cut.

Tips: a front-facing reference locks all five poses to one stance; use a side-view ref. Ask for "WIDE EMPTY GAPS, nothing touches"
or the cutter has to split merged figures by column. If a ref carries a wrong detail (Brutus fish crest), fix it with an edit pass.

## Hero (ids hero_sword / hero_axe / hero_bow), FACING RIGHT
Fighting-game sprite sheet, painterly HD fantasy illustration, warm golden light with orange rim light. The same young
brown-haired knight as image 1 (steel plate armour, blue tassets, <longsword | two-handed double-bladed battle axe>)
[bow: as an archer in brown leather armour with a longbow and quiver] in five poses, strict side view FACING RIGHT, same scale,
feet on one baseline, separated by WIDE EMPTY GAPS; no figure, weapon or foot overlaps another. Holds the weapon in EVERY pose.
Poses: GUARD, ATTACK (lunging strike/full draw to the right), BLOCK (weapon raised to block, braced), DODGE (leaping back to the
left), HIT (staggering back to the left, head snapped back, arms flung out). Plain flat light grey background, no ground, no shadow, no text.

## Bosses (varro, brutus, crixus, sabina, ignatius, unbroken), FACING LEFT
Fighting-game sprite sheet, painterly HD fantasy illustration, warm golden light with orange rim light. The same gladiator boss
as in the reference image (same armour, weapons, colours) [unbroken: the RIGHT-hand figure: gilded plate, gold helmet with red
crest, purple tabard/cape, round gold sun shield, longsword]. Five poses in a row, strict side view FACING LEFT, same scale, feet
on one baseline: GUARD, ATTACK (big lunging strike to the left), BLOCK (crouched defending), DODGE (leaping back to the right),
HIT (staggering back to the right, head snapped back, arms flung wide, off balance). Plain flat light grey background, no ground,
no shadow, no text.

Brutus edit pass: "keep all five poses ... only change the helmet: remove the fish ornament and replace it with a tall bronze
Roman crested helmet crest (stylised curved fan-shaped metal crest ridge front to back)"; then "redo only pose 5 as a real HIT
STAGGER: reeling backward to the right, torso bent back, head snapped back, shield arm swung wide, one foot lifted".
