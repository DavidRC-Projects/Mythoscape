# Emberdeep follow camera

The first-person Emberdeep view only draws the corridor. Monsters show as brown boxes or not at all, the player is never drawn, and hitsplats, arrows, and spells stay on the old top-down screen positions. Change the camera so it sits just behind and above the player, blit the existing walk and attack sprites in front of it, and draw real monsters and combat in that same view. Do not redesign the walk cycle.

## Flag

Keep `USE_EMBERDEEP_FIRST_PERSON` as it is. Do not add another flag and do not change its default.

## Step 1 — investigate only

Do not edit anything. Read:

- `game/assets/mmorpg/client/emberdeep_v2_client.py` `draw_first_person` and `pick_tile`
- `client.py` `draw_map` early return when first person draws
- the top-down monster block and the player `draw_humanoid_detailed` call
- hitsplats, `_draw_projectiles`, and `draw_magic_fx`

Report what the first-person pass draws, why monsters and the player are missing, and where combat FX are skipped. Then stop.

## Step 2 — small hooks

Only after the user says continue. Edit `emberdeep_v2_client.py` and the smallest possible hooks in `client.py`. Do not rewrite `draw_map`.

- Move the camera eye back about two thirds of a tile behind the player and raise the view so the player stands in the lower middle of the screen. Look along the way the player is walking, not locked north, so walking south looks south.
- After the walls, draw the local player with the same `sprites.draw_humanoid_detailed` call the top-down view already uses: same `facing`, `moving`, `attacking`, equipment, and gender. Forward, sideways, and backward must be the poses that already exist (`"back"`, `1` / `-1`, `"front"`). Do not edit `rs_style.py` `pose_walk`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, or `draw_humanoid` / `draw_humanoid_detailed`.
- Replace the brown monster rectangles with the same monster draw chain the top-down view uses (humanoid, low-poly dragon, anim strip, legacy sheet, then `draw_monster`). Project each live monster by distance, scale it by depth, hide it when a wall is closer, and sort far to near. Draw name and health when the player is fighting that monster or standing near it.
- Draw hitsplats, arrows, and spell effects at those same projected positions, including on the player. Clicking a monster in this view must still send `ATTACK` the way the top-down click does. Melee range, bows, and the Leave button stay as they are.
- This view stays inside an Emberdeep instance only. The overworld and other dungeons stay top-down.

## Check

One screenshot walking away from the camera, one walking sideways, one facing the camera, and one of a monster in the corridor with a hitsplat. The walk cycle frames must match the overworld.

## Non-goals

No walk-cycle edits. No new combat rules. No Dungeon Keeper digging. No merge and no push.
