# Realistic OSRS-style item icons

Replace inventory and ground-item drawing with the pre-rendered low-poly icon pack when a feature flag is on. Every Mythoscape item id has a 128×128 transparent PNG. The flag ships off. Ground drops use that same sprite, including coins, sit on the tile, and despawn 5 minutes after they are dropped. Do not rewrite the existing drawers and do not touch the walk cycle.

## Flag

Add `USE_REALISTIC_ITEM_ICONS` to `server/feature_flags.py`, default **OFF**, using the same `_on()` helper as `USE_NEW_VOID_DUNGEON`:

```python
USE_REALISTIC_ITEM_ICONS = _on("USE_REALISTIC_ITEM_ICONS", "0")
```

`_on(name, default)` reads the environment variable and treats `0`, `false`, `no`, and `off` as disabled. The client imports this module and reads the flag. Do **not** tie it to `USE_NEW_CHARACTERS` or any character-sprite flag.

## Step 1 — investigate only

Do not edit anything in this step. Find and read:

- `draw_item_icon` in `game/assets/characters/procedural_sprites_finished.py`
- `gear_v2.draw_icon`
- `draw_ground_item`
- `draw_ground_loot_pad`
- the ground-item blit in `client.py` (around line 5440)
- `World.drop_loot` and `handle_drop` in `server.py`

Report how inventory icons are drawn today, how ground loot is drawn (including coins and any loot pad), and how drops are created and removed. Then **stop** and wait. No edits in step 1.

## Step 2 — small hooks

Only after the user says continue. Hook the existing drawers; do not rewrite them.

- Copy this pack's `icons/` to `game/assets/mmorpg/assets/items/realistic/` (one `<id>.png` per item).
- When the flag is on, inventory icons load `icons/<id>.png` from that tree. If a file is missing, fall back to the old drawer.
- Ground drops use the **same** PNG as the inventory icon, including coins. Do not draw a generic coin stack. Do not draw a pad that covers the icon. A soft oval shadow under the sprite is fine. The feet/center of the sprite sits on the tile.
- Despawn: when a player or a monster drops an item, set `expires_at = now + 300` seconds. A server tick removes expired ground items before they can be picked up. 5 minutes exactly. Do not despawn items in the inventory or the bank. Campfire expiry is unrelated; do not change it.
- Do not touch the character walk cycle: `rs_style.py` `pose_walk`, `rs_humanoid.py`, `rs_humanoid_v2.py`, `tools/walk_proof.py`, `draw_humanoid`.
- Capture one before/after inventory screenshot and one before/after ground-drop screenshot.

## Non-goals

No combat changes. No new items. No bank cap change. No merge and no push.
