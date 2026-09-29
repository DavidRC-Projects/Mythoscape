# The Depths: code review (before the redesign)

Fresh clone of `main` at `ca336ee` (27 Sep 2026, 11:58 BST). Paths are relative to `game/assets/mmorpg/`. The clone was deleted afterwards.

**Shared systems:** the Depths uses exactly the same explore-dungeon machinery as the Void Sanctum. Everything in `/workspace/void_dungeon/VOID_CODE_REVIEW.md` §1–§12 applies unchanged, and this review doesn't repeat it:
- per-player private instance (`session.dungeon`);
- no server-side doors, keys, chests, levers, secrets or interact message;
- the in-instance monster respawn bug and the ignored `aggro_range`;
- `handle_drop` writing to the overworld `ground_items`;
- the minimap leak (the whole map is visible, with no fog);
- `widen_single_file_passages`.

This file only covers what's specific to the Depths.

## 1. Which dungeon is "the Depths"
- **Picked: the `depths` explore dungeon.** It's the only thing literally named "The Depths".
  - Region: `server/explore_dungeons.py:15-21`. Rect (44,54)→(90,143), pad (43,69,50,76), entrance (46,71).
  - Meta: `server/server.py:49` (`DUNGEON_MODS`) and `server/server.py:67-72` (`DUNGEON_META`: chat_from "Dungeon", entrance kind `dungeon_entrance`).
  - Entrance: `server/content.py:2219-2221`. `dungeon_entrance` at (46,71), enter (48,71), exit (38,71), art `pack: "skeleton_crypt"`.
  - Nearby: the `dungeon_gate` place (`content.py:2133`) and a dungeon bank chest at (44,68) (`content.py:2217`).
- **Other candidates, noted and not used:**
  - `skeleton_crypt` isn't a dungeon. It's only the *entrance art pack* for the Depths (`server/dungeon_pack/json/skeleton_crypt.json`, `images/skeleton_crypt_concept.png`).
  - The Void Sanctum is `kind: "crypt"` in BUILDINGS (`content.py:2488`) and sits in the `shadow_crypt` zone. It's covered by the void pack.
  - Tidehollow floors 3–4 use crypt props (`server/dungeon_props.py:15-16`).
  - The Depths already references the `crypt_sarcophagus` and `crypt_candelabra` props (`dungeon_props.py:26`), which the v2 design reuses.

## 2. Current layout
It comes from the overworld generator, not from dedicated map data: `server/world_map.py:476-553`, with zone `"dungeon"` = (44,54,90,143) at `:50` and `DUNGEON_ROOMS` at `:60-68`.
- 4 upper rooms joined by 3-wide corridors. The mine↔dungeon mouth at 36-48 × 66-76 sits **partly outside** the explore region.
- Iron/coal room (50,82,64,92), giant hall (66,84,78,98), mithril cavern (48,102,62,118), spider nest (66,99,78,103) and adamantite lair (64,104,78,128).
- Ore tiles are scattered at random. It reads as a **mine/cave**, with no crypt theme at all.
- The spawn is at the pad and the exit is back to (38,71). Walls draw as dungeon cliffs ("spikes"), the same way as the Void.

## 3. Monsters and levels
Spawns are at `content.py:1064-1090`; stats are at `content.py:595-743`.

| Monster | Count | Level | Notes |
|---|---|---|---|
| giant_rat | 6 | 3 | in the mine mouth, **outside** the region |
| goblin | 14 | 8 | |
| skeleton | 12 | 15 | anim strip `skeleton_warrior` |
| giant | 5 | 28 | `aggro_range` 0 |
| big_skeleton | 5 | 30 | anim strip `skeleton_mage` |
| spider | 7 | 48 | |
| dragon (Adamant Dragon) | 1 | 78 | `confine_room`, drops Mythos |

Undead types available to reuse:
- skeleton (15)
- big_skeleton (30)
- shade (55, `barrow_wraith` strip)
- crypt_ghoul (62, `rot_ghoul`)
- shadow_knight (88)

## 4. Depths-specific problems
1. **The level curve jumps from 48 to 78.** Nothing sits between the spiders and the dragon, so there's no build-up or boss mechanics.
2. **Ore tiles are dead obstacles inside the instance.** `handle_gather` refuses inside dungeons (`server.py:2620-2623`, "nothing to gather in the cave"). The resource nodes are built after `capture_and_hide` blanks the interior, so the ore art blocks movement but gives nothing.
3. **The layout is generated from world zones.** Any change to `world_map.py` moves the dungeon too. v2 should use its own map data, like the void pack.
4. **The mine mouth crosses the region edge.** Rats spawn outside the instance, and the entry feels like a mine, not a crypt.
5. The dragon is the only "boss", with no telegraphs or phases. v2 keeps it as an optional side lair so no content is lost.

## 5. How it differs from the Void
- **Tier:** low–mid (8→62, boss 70) against the Void's high tier. The new mobs sit between the existing skeleton, spider, shade and ghoul stats.
- **Theme:** a mine/cave today; v2 turns it into a crypt descent.
- **Entry:** the entry is an overworld pad beside the mine, not a building.
- **Content that must survive:** the Adamant Dragon (Mythos drop).
- **Same hooks:** `explore_dungeons.build`, `handle_enter_dungeon` (`server.py:1950`), `handle_leave_dungeon` (`:1991`), `handle_drop` (`:3915`), `game_loop` (`:4349`), `process_dungeon_ai` (`:4926`). The flag goes in `server/feature_flags.py`, like `USE_NEW_VOID_DUNGEON`.

## 6. Risks
- If both v2 dungeons are built separately, the door, key, secret, chest, fog and boss-bar systems get duplicated. Build them once, generically, keyed by map data (see `CURSOR_PROMPT.md`).
- The Mythos drop must stay on the dragon.
- The explore region pad (43,69,50,76) and the bank chest must be left as they are.
- Removing ore from the dungeon zone must not change overworld mining. Only the v2 instance ignores `world_map` tiles.
