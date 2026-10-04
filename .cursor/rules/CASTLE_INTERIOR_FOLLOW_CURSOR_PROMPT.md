# Castle interior follow camera

When the player walks through a castle door and the interior map starts, switch to the same behind-and-above view used in Emberdeep. Furniture and decor stay as they are. Interior walls become stone block walls. The castle grounds and the overworld stay top-down.

## Flag

Add `USE_CASTLE_INTERIOR_FOLLOW` to `server/feature_flags.py`, default OFF:

```python
USE_CASTLE_INTERIOR_FOLLOW = _on("USE_CASTLE_INTERIOR_FOLLOW", "0")
```

Do not tie it to `USE_EMBERDEEP_FIRST_PERSON` or `USE_CASTLE_INTERIORS_V2`.

## Step 1 — investigate only

Do not edit anything. Read:

- `castle_realm.enter`, `transition_at`, and `move_to_plane` (a door starts a new plane inside the same castle realm instance)
- `client.py` `draw_map` and the Emberdeep early return
- `castle_realm_renderer.draw_floor_plane` and `castle_interiors_v2.draw` / `queue_walls` / `queue_props`
- `emberdeep_v2_client._draw_local_player` (reuse the idea, not the Emberdeep textures)

Report how a door changes the plane, how `#` walls are drawn today (flat colour rectangles), and where props are queued. Then stop.

## Step 2 — small hooks

Only after the user says continue.

- New module, do not bend `emberdeep_v2_client.draw_first_person` to castles. Turn the view on only when the flag is on, `dungeon.id == "castle_realm"`, and the plane is not `"realm"`.
- Hook it at the start of `draw_map`, same pattern as Emberdeep, and return early only for that case.
- Camera sits just behind and above the player and looks along the way they are walking. Draw the player with the existing `draw_humanoid_detailed` call (same facing, moving, and attacking). Do not edit `rs_style.py` `pose_walk`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, or `draw_humanoid` / `draw_humanoid_detailed`.
- Keep `queue_props`, rugs, stairs, and `castle_room_layouts` as they are. Project those sprites into the follow view. Do not move or redesign the furniture.
- Replace the flat `#` wall faces with the stone texture `castle_stone_wall.png` from this pack (copy it to `game/assets/mmorpg/assets/castle_interior/`). Sample it on the wall faces. Do not use the Emberdeep lava rock texture.
- Clicks still walk and use doors and stairs. Leaving back to the castle grounds returns to the top-down view.

## Check

One shot in a castle room with the player in front of the camera, stone walls, and the existing furniture still in the room. One shot back on the castle grounds, which must still be top-down.

## Non-goals

No walk-cycle edits. No decor changes. No Emberdeep changes. No merge and no push.
