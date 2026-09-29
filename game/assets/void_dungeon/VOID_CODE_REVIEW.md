# Void Sanctum: code review (before the redesign)

Fresh clone of `main` @ ca336ee (27 Sep 2026, 11:58 BST). Paths are relative to `game/assets/mmorpg/` unless they start with `characters/`. Read-only review; nothing was changed.

## Summary
- **Private instance.** The Void Sanctum is an "explore" dungeon. On entry, the server copies a rectangle of the overworld into a **private, per-player map** (`session.dungeon`). Monsters, tiles and props live on that session, so **every player already has their own instance**. Door, key, chest and secret state can therefore be per-player just by storing it in `session.dungeon`, with no shared-world conflicts.
- **What David sees.** The "room" in his screenshot is the six Void Sanctum rooms from the overworld generator. `widen_single_file_passages` and the entrance lane then open them up so far that they read as one big rectangle. The "rows of spikes" are the wall stubs left between rooms, drawn as `draw_dungeon_cliff`.
- **Missing systems.** There are no doors, keys, chests, levers, triggers, secret walls, fog of war or boss mechanics in dungeon code. Overworld `door` and `chest` interactables are client-side walk targets and decoration only.
- **Three bugs worth knowing about:**
  - Explore-dungeon monsters never respawn during a visit.
  - Dropping an item inside a dungeon writes it into the **overworld** ground-item table at dungeon-local coordinates.
  - The dungeon AI ignores `aggro_range`, so everything in your room chases you (capped at 2).

## 1. How dungeons are defined and generated
| What | Where |
|---|---|
| Dungeon modules and meta (`tidehollow`, `emberdeep`, `depths`, `sanctum`) | `server/server.py:46` `DUNGEON_MODS`, `:52` `DUNGEON_META` (sanctum at `:74`) |
| Explore regions: world rect, pad and entrance for `depths` and `sanctum` | `server/explore_dungeons.py:14-29` (sanctum rect 154,98 → 190,140) |
| Capture at boot: copy the rect, open the entrance lane, widen passages, pick spawn/exit, then turn the overworld copy to grass | `server/explore_dungeons.py:47-86` (called from `server/server.py:1067`) |
| Instance build on enter: copy tiles, create monsters from `MONSTER_SPAWNS` inside the rect, set `home_room`, install props | `server/explore_dungeons.py:127-169` |
| Void Sanctum layout: 6 rooms + corridors + entrance building | `server/world_map.py:728-777`; rooms in `DUNGEON_ROOMS` `server/world_map.py:60-77` |
| Passage widening (why rooms merge) | `server/world_map.py:95` `widen_single_file_passages`, used at `explore_dungeons.py:66` |
| Floor dungeons (Tidehollow/Emberdeep): generated per floor, clear to advance | `server/dungeon.py:297-345`, `server/server.py:1742-1793`, `:2016` |
| Enter / leave | `server/server.py:1950` `handle_enter_dungeon`, `:1991` `handle_leave_dungeon`; walking onto the exit tile leaves (`:1700-1705`) |
| Payload sent to the client (tiles, monsters, exit, props) | `server/server.py:1796-1833`; per-tick `STATE_UPDATE` for dungeon players at `:4403-4420` |

**Takeaway:** a hand-authored layout slots in cleanly as a new explore region whose snapshot comes from data (for example `void_map.py`) instead of the overworld capture. `build()` would just take the tiles and spawns from the data file behind the flag.

## 2. Tile types, walls, spikes and decor
- **Tile ids:** `server/world_map.py:1-33`. The ones that matter here are WALL=4, FLOOR=6 and PATH=5. `WALKABLE_TILES` is at `:36`, and dungeon walkability is `explore_dungeons.dungeon_walkable` at `:119` (tile-grid only).
- **Client terrain:** `client/client.py:6047` `draw_terrain_tile`.
  - Inside any dungeon except Emberdeep, zone is forced to `"dungeon"` (`:6048-6050`), so the sanctum uses the generic purple dungeon floor and walls. The `shadow_crypt` palette in `characters/procedural_sprites_finished.py:180` and `draw_void_crypt_wall` at `:305` go unused inside.
  - Floor: `characters/procedural_sprites_finished.py:162`. Walls: `:285` → `draw_dungeon_wall` `:482`.
- **"Spikes":** every WALL tile with open floor to camera-south is queued as a tall cliff sprite: `client/client.py:5940-5983` → `sprites.draw_dungeon_cliff` (`characters/procedural_sprites_finished.py:518`). Leftover room-divider walls therefore show as rows of dark spikes.
- **Wall AO:** `client/client.py:6089-6093`, `characters/procedural_sprites_finished.py:213`.
- **Decor props:**
  - two 2×2 pads near the spawn from `server/dungeon_props.py:45-100`; sanctum uses `void_altar` and `void_crystals` (`:27`);
  - drawn with `prop_sprites.draw_prop` at `client/client.py:4973-4986`;
  - an unused overworld-only 3D prop pass for `shadow_crypt` at `client/client.py:5527-5546`.

## 3. Monsters: spawn, roam, respawn, levels
- **Definitions** (`server/content.py`):

  | Monster | Level | Line |
  |---|---|---|
  | shade | 55 | `:864` |
  | crypt_ghoul | 62 | `:885` |
  | void_imp | 70 | `:906` |
  | obsidian_colossus | 78 | `:927` |
  | shadow_knight | 88 | `:949` |
  | void_horror | 95 | `:967` |

- **Levels are fixed per type**; there is no scaling for explore dungeons. Tidehollow scales stats per floor instead (`server/dungeon.py:279`).
- **Spawns:** `MONSTER_SPAWNS` Void block at `server/content.py:1101-1107`, 18 monsters, 3 per room. The overworld copies are skipped via `contains_region` (`server/server.py:1070-1072`).
- **Instance:** `MonsterInstance` `server/server.py:989-1060`. `home_room` comes from `room_containing` mapped to local coordinates (`explore_dungeons.py:136-141`).
- **Roaming and chasing inside dungeons:** `process_dungeon_ai` `server/server.py:4926-5001`.
  - At most 2 pursuers.
  - A monster chases whenever the player is inside its `home_room`.
  - It walks back to spawn once the player leaves.
  - No `aggro_range`, no wander.
- **Respawn:** a kill sets `respawn_at_tick` (`:2538`, `:4618`, `:4682`), but `process_monster_respawns` (`:4912`) only iterates `WORLD.monsters`. Explore-dungeon monsters therefore **stay dead until you leave and re-enter** (a new instance). Mini-bosses get this behaviour for free; normal mobs would need an in-instance respawn.

## 4. Aggro and leash
- **Overworld:** `process_monster_ai` `server/server.py:5004+`.
  - `aggro_range` acquisition happens at `:5021-5050`, skipping players in dungeons (`:5034-5035`).
  - A 2-attacker cap applies, with a boss exception at `:5031`.
  - Leash is `max(aggro*2, 10)` or leaving `home_room` (`:5057-5060`), and the monster walks home.
- **Dungeon:** leash is `home_room` only (`:4960-4968`). `aggro_range` is ignored, so the Sanctum feels like "everything wakes up at once".

## 5. Entry and exit portals
- **Overworld objects:** `void_sanctum_door` (kind `door`) and `void_sanctum_portal` (kind `dungeon_entrance`, `pack: "void_rift"`, `warning: True`) at `server/content.py:2384-2396`.
  - Warning signs are at `:2397-2400`; mouth tiles come from `entrance_mouth_tiles` `server/content.py:2189`.
  - Walking into the mouth enters (`server/server.py:1717-1721`); the lookup is `_find_dungeon_entrance` `:1925`.
- **Exit:** the tile south of the captured entrance (`explore_dungeons.py:67-70`). It is drawn as a cave entrance with "EXIT / Walk here to leave" plates at `client/client.py:4960-4971`, and the HUD is at `:9256`.

## 6. Item drops and ground items
- **Overworld kills:** `WORLD.drop_loot` → `WORLD.ground_items[(x, y)]` (`server/server.py:1284-1301`), then vacuum and auto-pickup (`:2123`) and manual pickup (`:3975`).
- **Explore-dungeon kills:** the drop table is rolled **straight into the inventory** by `_grant_monster_table` (`:1883-1906`), called from `_finish_dungeon_kill` (`:1909`). The dungeon `STATE_UPDATE` always sends `ground_items: {}` (`:4412`).
- **Bug:** `handle_drop` (`:3915-3936`) has no dungeon branch. Inside a dungeon, the item lands in `WORLD.ground_items` at dungeon-local (x, y), which is an overworld tile. Phase E must add per-instance ground items (`session.dungeon["ground"]`) and route drops and pickups there.

## 7. Inventory and item definitions
- **Items:** `ITEMS` `server/content.py:15+`. Relevant flags:
  - `type`, `stackable`, `equip_slot`, `value`;
  - `tradeable` (`server/server.py:1640`) and `sellable` (`:1616`);
  - `bound_username` / `bound_to_inventory` (owner-bound uniques, `enforce_bound_items` `:1651`).
- **Inventory:** `add_item_to_inventory` `:1111`, `remove_item_qty` `:1195`.
- **Dungeon keys:** there's no dungeon-bound flag yet. Keys can follow the same pattern: `tradeable: False`, a new `dungeon_bound: "sanctum"`, stripped in `handle_leave_dungeon` and on login.

## 8. Doors, keys, chests, levers, triggers
Checked again, as asked.
- **Doors:** `kind: "door"` entries (`server/content.py:2202-2337`, `:2385`) are **client-side walk targets only**. `client/client.py:6015-6045` `click_door` walks to the far side. Walls are just tiles, so there is **no server door state and no locking**.
- **Chests:** `kind: "chest"` entries (`server/content.py:2237`, `:2274`, `:2349`, …) are decoration only; the server has no chest handler. `dungeon_bank` is a bank.
- **Keys, levers, triggers, pressure plates:** none. `rg` finds no key items, and no lever or trigger kinds.
- **Message types:** the WebSocket dispatch (`server/server.py:4270-4335`) has no `INTERACT` / `SEARCH` / `UNLOCK` message. A new `DUNGEON_INTERACT {x, y}` message is needed, validated server-side (adjacent, walkable, per-player state).

## 9. Instancing and multiplayer
- **Doors are per-player already.** Each player entering the Sanctum gets their own `session.dungeon`, with its own tile copy and monster dict (`explore_dungeons.py:128-163`). Other players never see it, since the dungeon `STATE_UPDATE` lists only the session's own player (`server/server.py:4405-4409`). A door opened by one player therefore stays closed for everyone else automatically. Keep door, secret, chest and lever state in `session.dungeon[...]`, and keep only the shortcut in the DB.
- **Consequence:** no co-op inside explore dungeons today; two friends entering see separate copies. That's fine for this redesign. If parties are ever added, the per-player state would move to a party-instance object; the design keeps state keyed on the instance so that change stays small.
- **Persistence:** the only per-player persistence that doesn't need a schema change is the `quest_progress` table (`server/database.py:81`, `get/set_quest_progress` `:310/:314`). The permanent shortcut can be stored as `quest_id="void_shortcut"`, `status="complete"`.
- **Disconnects:** `session.dungeon` is dropped on disconnect (`server/server.py:4338-4339`), so keys must also be stripped on login in case the player was in the dungeon when they disconnected.

## 10. Minimap and fog of war
- **Minimap:** `client/client.py:6672-6860`, rebuilt from `self.tiles` whenever the dungeon view changes (`:2699`). The world-map modal is at `:6869`.
- **Fog of war:** none; the full dungeon is sent and shown. Secret rooms would leak through the minimap, so the server must send hidden-room tiles as WALL until they're revealed.

## 11. Boss-like monsters today
- **Adamant Dragon** (`server/content.py:743`): `confine_room`, `force_retaliate`, `side_by_side`, 4-tile dragonfire. There's special attacker-cap handling for dragons (`server/server.py:4506`) and a "boss always acquires" rule (`:5031`).
- **Mythos Champion** (`:840`), Tidehollow floor 10 and the Emberdeep final floor.
- **Void Horror** is labelled "Sanctum boss" in the travel list (`server/content.py:2184`), but it's a normal mob with no mechanics.
- **No boss framework:** no phases, telegraphs, adds, boss HP bar or arena lock. Monster HP bars are the small per-entity ones (`client/client.py:5398`, `:7951`).

## 12. Risks for the redesign
- **`widen_single_file_passages`** would widen the 1-tile bridge and doors. The v2 build must **not** call it on the hand-authored map.
- **Client assumptions:** the client decides walkability from tiles, so doors, secrets and the shortcut gate must stay WALL in the tiles the client gets until opened. Send small `DUNGEON_TILES` patches when they change.
- **Loot routing:** explore kills grant loot straight into the inventory, so key drops must also go straight to the inventory (never the ground).
- **Scope:** the flag must leave `explore_dungeons.REGIONS["sanctum"]`, the overworld generator and the other dungeons untouched.
