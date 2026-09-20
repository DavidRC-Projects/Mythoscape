# Tiny MMORPG — v0.1

A minimal, server-authoritative, persistent-world MMORPG prototype in Python.
One village, one forest, one mine, one dungeon. Multiplayer, SQLite-backed,
RuneScape-2001-style combat math.

## What's in v0.1
- One persistent world (all players share the same map/server/database)
- Account creation + login/logout, characters persist between sessions
- Walking around a 40x36 tile map (village / forest / mine / dungeon)
- 15 NPCs (shopkeepers, quest givers, flavor characters)
- Public chat
- Inventory (24 slots), equipment (weapon/shield/body/legs)
- 27 items (weapons, armor, tools, food, resources, quest items)
- Gathering: Woodcutting, Mining, Fishing (3 skills, with XP + levels)
- Combat: Attack, Strength, Defence, Hitpoints — classic RS2001 hit-chance
  and max-hit formulas (see `server/combat.py`)
- 3 monsters (Giant Rat, Goblin, Skeleton) with respawns and loot tables
- 2 shops (buy + sell)
- Player-to-player trading (request → offer → confirm, server-validated)
- 5 quests (kill, collect, collect-multiple, find-NPC types)
- Server-authoritative game state: the server validates every move, attack,
  gather, trade and quest completion. The client only renders and sends intent.

## Requirements
```
pip install -r requirements.txt
```
(Needs Python 3.9+.)

## Running it
Start the server first (creates `server/world.db` on first run):
```
cd server
python server.py
```
Then start one or more clients (each is a separate player):
```
cd client
python client.py            # connects to localhost
python client.py 192.168.1.5  # connect to a server on your LAN
```
Anyone on the same network can point their client at your machine's IP to
play together, as long as port 8765 is reachable.

On the login screen, click **Hiscores** (or press **F3**) to open a modal of
the top players for each skill.

## Controls
- **Arrow keys** — walk (one tile per press, server validates)
- **Space** — attack the nearest adjacent monster
- **H** — controls help popup
- **E** — equipment & stats modal (click a slot to unequip)
- **F** — forge UI inside the smithy (furnace to smelt, anvil to smith)
- **Tab** — Skills modal (levels, XP, combat level, total level)
- **C** — cooking UI at a hearth or player campfire
- **Click** a monster / NPC / resource / shoreline / furnace / anvil / hearth / campfire / player as usual
- Click **logs** or a **tinderbox** in inventory to light a campfire (needs both; trains Firemaking)
- Higher **Cooking** level reduces the chance of burning fish
- Oak logs need **Firemaking 15**
- **G** — pick up an item on your tile
- **P** — toggle auto-pickup for non-coin items (or click the sidebar button)
- **B** — open the Village Bank (stand at the booth / talk to Banker Iris)
- **I** — toggle inventory panel; click a slot to equip/eat, right-click to drop
- **Q** — toggle quest log
- **Enter** — open/send chat
- In dialogue: **A** accept quest, **T** turn in quest, **B** browse shop / open bank, **S** open forge (Gareth), **Esc** close
- In trading: click inventory slots to add to your offer, **Enter** confirm, **Esc** cancel

Economy caps: purse holds at most **65,000** coins; bank vault holds **10,000,000** coins
plus 48 item slots; inventory may hold at most **100** ores (bank extras).

**Pet Emporium** (south of the smithy): talk to Pet Keeper Luna and press **B**.
Companions follow you and attack monsters that aggro you.
- Cat (Lv 1) — 10c
- White Husky (Lv 10) — 1,000c
- Skeleton (Lv 25) — 10,000c
- Dragon (Lv 50) — 65,000c

Buildings have solid walls and a single door — roofs hide interiors (and NPCs)
until you walk through the doorway.

## Architecture
```
server/
  server.py      websocket server, tick loop (0.6s, RS-style), all message handlers
  database.py    SQLite persistence (accounts, inventory, equipment, quests)
  content.py     all static data: items, monsters, NPCs, shops, quests
  combat.py      RS2001-style hit-chance / max-hit formulas + XP curve
  world_map.py   40x36 tile grid generation for the 4 zones
client/
  network.py     background-thread websocket bridge (queues in/out)
  client.py      pygame rendering + input + UI (login, map, inventory, shop, trade)
shared/
  protocol.py    documents every message type both sides send
```

The server is authoritative: it owns positions, HP, inventory, combat rolls,
gathering, shop transactions and trades. The client never decides outcomes —
it sends an intent (e.g. `ATTACK target_id`) and renders whatever the server
broadcasts back on the next tick.

## Known v0.1 simplifications (fair game for a v0.2!)
- Movement is per-tile keypress, not click-to-pathfind.
- Area-of-interest isn't implemented — all players see all state updates,
  which is fine for the 10-20 concurrent players targeted here but wouldn't
  scale much further.
- Resource-node depletion is tracked server-side, but the client's node
  markers don't visually grey out while depleted (gathering will just quietly
  pause and resume once the node respawns).
- No password reset / account recovery; sha256+salt hashing is enough to stop
  casual snooping in a hobby prototype, not production-grade security.
- Monster "AI" is a light random wander plus simple aggro-while-attacked;
  no pathfinding toward players.

## Extending it
- New item: add an entry to `ITEMS` in `content.py`.
- New monster: add to `MONSTERS` + a few `MONSTER_SPAWNS` entries.
- New quest: add to `QUESTS`; supports `kill`, `collect`, `collect_multi`,
  and `find_npc` types out of the box.
- New zone/map area: extend `world_map.py`'s `generate_world()`.
