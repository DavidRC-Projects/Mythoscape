# Mythoscape MMORPG

A RuneScape-classic-style multiplayer sandbox: skills, quests, combat, crafting, and a shared overworld.

## Building art (3D→2D shells)

Village buildings can use **pre-rendered PNG shells** instead of procedural roofs.

```
cd tools
./render_buildings.sh cottage_nw     # Blender if installed, else pygame bake
./render_buildings.sh --all
```

Sprites land in `client/assets/buildings/{id}.png`. Drop a Blender ortho render on
the same filename to upgrade quality — no client code change needed.

Install Blender (optional): `brew install --cask blender`

```
cd server
python server.py
```
```
cd client
python client.py            # localhost
python client.py 192.168.1.5  # LAN server
```
Port **8765** must be reachable for LAN play.

On the login screen, click **Hiscores** (or press **F3**) for top players per skill.

## New player tips
1. Press **H** for the full controls list.
2. **Elder Miriam** (NW cottage) — starter quest.
3. **Fletcher Elena** (east of the village) — free bow kit (includes an **Arrow Quiver** and **Arrowtip Box**) on first talk; **B** opens her shop (scroll buy/sell lists). Click arrows to load the quiver or drop; click tips to pack the tip box. Fletching draws tips from the box automatically. Quiver holds **1000** of each arrow type.
4. **Lira the Jeweler** (east of Joe) — common jewelry shop; buys all gems/jewelry; sells a **Gem Bag**; quest **Lira's Lost Locket** (near the wishing well).
5. **Gareth** (smithy) — furnace **F** to smelt, anvil to smith weapons, armour, and jewelry.
6. **Mira** in Stonehaven — food, potions, steel scraps; sells a **Food Bag** and **Potion Pouch**.
7. **Harbourreach** — tackle shop sells a **Raw Food Bag**; Nell's Catch sells cooked fish and food bags. Cooking draws raw fish from the bag; food bag eats highest-heal first.
8. **Storage bags** (Bags tab): Mining / Log / Gem bags, Fletching & Potion pouches, tip box, quiver. Click a bag to **Pack** or **Unpack**. Crafting draws from bags first.
9. Inventory has **4 tabs × 24 slots** (Gen / Gather / Craft / **Bags**). Shops: click to sell 1, **Shift+click** to sell the whole stack.
10. **Tidehollow Cave** at Harbourreach — bring food; loot drops into your pack each kill.

## Controls
- **Click** the map to walk / attack / talk / gather / use interactables
- **Arrow keys** — walk one tile
- **Space** — attack nearest monster in reach
- **R** — eat best food (or health potion); while under attack, click the buttons above your head to eat / drink potions from inventory or bags
- **1–5** — combat styles (Att/Str/Def/HP/Arch); with a bow only Archery is available
- **H** — help · **E** — equipment · **Tab** — skills · **M** — travel / world map
- **F** — forge (furnace/anvil) · **C** — cook · **N** — fletch (needs a knife)
- **B** — bank or shop (when beside booth / in dialogue)
- **G** — pickup · **P** — toggle auto-pickup · **Q** — quest log · **Enter** — chat
- Dialogue: **A** accept quest · **T** turn in · **B** shop/bank · **S** forge · **Esc** close
- Tidehollow: confirm at the cave mouth; **Esc** abandons the run when no modal is open
- Equipment slots: weapon / shield / body / legs / helmet / amulet / ring / ammo

Economy: purse max **65,000** coins; bank vault **10,000,000** + 96 slots; inventory **96** slots (4×24 tabs).

## Architecture
```
server/
  server.py      websocket server, 0.6s tick, handlers
  database.py    SQLite persistence
  content.py     items, monsters, NPCs, shops, quests, recipes
  combat.py      RS2001 hit / max-hit + XP curve
  world_map.py   procedural overworld
  dungeon.py     Tidehollow floors + kill loot
client/
  network.py     websocket bridge
  client.py      pygame UI + rendering
shared/
  protocol.py    message type reference
```

## Extending it
- New item → `ITEMS` in `content.py`
- New monster → `MONSTERS` + `MONSTER_SPAWNS`
- New quest → `QUESTS` (`kill`, `collect`, `collect_multi`, `find_npc`, `gift`)
- New shop → `SHOPS` + NPC `shop_id`
- New map area → `world_map.py` `generate_world()`
