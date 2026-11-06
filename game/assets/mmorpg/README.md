# Crownfall

A RuneScape-classic-style multiplayer sandbox: skills, quests, combat, crafting, and a shared overworld.

For install and first-run steps from the repo root, see the top-level [`README.md`](../../../README.md).

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

### Panda3D building prototype (optional)

A **standalone test scene** (does not replace the live Pygame renderer): Panda3D
owns its own window and shows one original low-poly medieval cottage under a
fixed isometric-style camera. Geometry is original; open-source samples were
used only as technique references (Panda procedural-cube / Modified BSD;
Epihaius primitives maker-pattern idea / BSD-3; RTS_pygame data-vs-footprint
pattern only — no assets copied).

```
cd game/assets/mmorpg
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt    # pygame, websockets, panda3d
cd client
python client.py --panda-building-proto
```

Controls: fixed iso by default · `0` reset iso · `[` `]` / `A` `D` optional yaw · `F` debug faces · `Esc` quit.

See `client/panda_building_proto/` (`coords.py`, `cottage.py`, `geom_util.py`). Do not run the proto and the pygame client as two competing windows for the same session.

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
11. **War for the Crown** — contest the King's Castle with your guild (see the full guide below). Talk to the **Royal Herald** in the castle, open the **War Council** on the world map (**M**), or use `/siege status`.

## War for the Crown

The throne is no longer taken by a solo Crown Challenge. Guilds fight a monthly **War for the Crown**: register, supply a shared storehouse, breach the castle with siege engines, capture stages, and hold the Throne Room. Combat is not the only path — gatherers, smiths, and woodcutters earn contribution by depositing supplies all month.

Core code: `server/crown_siege.py`. Headless suite: `tools/test_crown_siege.py`.

### Where to start

1. **In-game guide (recommended):** after Seraphine’s first village tour, she offers a **War for the Crown** walk. She leads you from the village to the **Royal Herald**, who stands **outside the King’s Castle approach** (beside the gold King’s Realm portal, west of the wishing well). Choose **How the War for the Crown works** and read every page. Replay anytime under **Settings → Help → War for the Crown tour**.
2. **Join or create a guild** (you need a guild Leader to register a war side).
3. Talk to the **Royal Herald** again for live war actions, or type `/siege status` in chat.
4. Check the **monthly calendar** on the board / War Council — Day 30 is The Siege of Crownfall. Contribute materials throughout the month; registration peaks on days 28–29.
5. **World map (M)** → **War Council** card shows open wars, countdown to the next war, and the last Crownfall report.
6. Top-centre **war chip** in the castle realm opens the live war board (click again or Esc to close).

### How a war works (lifecycle)

```
Registration → Confirm (48h) → Scheduled (assault window) → Active assault (3h)
        → Crownfall resolve → 30-day cooldown → next registration
```

| Phase | What happens |
| --- | --- |
| **Registration** | Guild Leaders `/siege register attack` or `defend`. Alliances via `/siege ally`. Deposit supplies, craft engines, scout. |
| **Confirm** | Each lead has **48 hours** to `/siege confirm` with enough humans (default **20+**). Fail → next guild in queue may take the slot. |
| **Scheduled** | Both sides confirmed. Attack Leader sets when the fight starts (`/siege when <1–72>h`) or `/siege begin` early. Start time is published in **UTC**. |
| **Active assault** | **3-hour** clock. Breach walls, capture stages, hold the throne. Defenders win if time expires without a successful hold. Roster / merc contracts lock. |
| **Crownfall** | Attackers who hold the Throne Room long enough crown their lead; defenders who outlast keep the crown. Heraldry / regal robes for the victor. Full `/siege report` afterwards. |
| **Cooldown** | About **30 days** before the next war opens. |

**Roster rules (assault):** **20–100** fighters per side · mercenaries ≤ **40%** of a side · under-strength wars can postpone or run at a smaller human minimum after a postpone.

### Player roles — who should do what

| Role | What to do |
| --- | --- |
| **Guild Leader** | Register attack or defend, invite allies, set storehouse allocation (`/siege alloc`), set assault window (attack), organise fighters. |
| **King (Monarch)** | Defend Crownfall; organise defending guilds; appoint up to **4** Royal Guard players (`/siege royalguard <name>`). The King's death does **not** end the siege — attackers must still take the throne. King's guild cannot register to *attack*. |
| **Marshal** | May also appoint / dismiss Royal Guard. |
| **Warriors / archers** | Fight on capture points; clear barricades and posted Guards; protect or assault the Throne Room. |
| **Miners / woodcutters / smiths** | Gather ore, stone, timber, bars → `/siege deposit` into the war storehouse (contribution without kills). |
| **Scouts** | `/siege scout` soft spots on gates, walls, keep. |
| **Everyone eliminated** | Death in the siege removes you from *this* war only — respawn outside, watch/cheer, read `/siege report` after Crownfall. |

### Step-by-step: attacking alliance

1. Leader: `/siege register attack` (or Herald → *Register to attack*).
2. Ally smaller guilds: `/siege ally <guild name>` → they `/siege accept`.
3. Pad to **20+ humans**, then `/siege confirm` before the 48h deadline.
4. Members deposit: `/siege deposit logs 40`, `/siege deposit iron_ore 10`, etc.
5. Leader sets budgets: `/siege alloc rams=40 ladders=25 barricades=20 reserve=15` (must sum to 100%). Crafting spends against those % budgets.
6. Craft engines: `/siege craft ram`, `ladder`, `tower`, `catapult` (and qty).
7. Set the fight time: `/siege when 24h` (or `2d`) — board shows countdown **and UTC** — or `/siege begin` when ready.
8. During assault: `/siege fire <weapon> <structure>` (e.g. `fire ram outer_gate`, `fire tower west_wall`, `fire catapult royal_keep`).
9. Push capture order: **Outer Yard → Gatehouse → Courtyard → Throne Room**. Gatehouse needs a wall/gate breach; throne needs the **royal keep** destroyed.
10. Hold the Throne Room (~**120s**) for Crownfall. Break system Royal Guard fortification and drive out appointed player Royal Guards first.

### Step-by-step: defending alliance

1. Leader: `/siege register defend` → confirm with 20+ humans.
2. Deposit and craft **barricades**; `/siege barricade <point>` onto capture points.
3. Post Guard recruits: `/siege guard <point>`.
4. Repair damaged structures: `/siege repair <structure>`.
5. King/Marshal: `/siege royalguard <name>` (cap **4**) — standing in the Throne Room they **protect the King** (chamber cannot fall while they are present).
6. Hold until the **3h** assault clock runs out, or retake the throne during Last Stand.

### Structures, weapons, and breaches

Castle structures (shared HP; states: intact → damaged → heavily damaged → destroyed):

`outer_gate` · `west_wall` · `east_wall` · `watchtower` · `armoury` · `supply_depot` · `royal_keep`

| Weapon | Cost (store resources) | Typical targets |
| --- | --- | --- |
| Battering Ram | 40 timber + 5 bars | Outer Gate |
| Siege Ladder | 25 timber | West / East Wall |
| Siege Tower | 50 timber + 4 bars | Walls, Watchtower |
| Catapult | 30 timber + 10 ore + 3 bars | Gates, walls, tower, armoury, depot, keep |
| Barricade | 20 timber + 10 stone | Deployed on capture points (defend) |

Destroyed **outer gate / west wall / east wall** open **breach tiles** you can walk through. Watchtower down widens combat interest; supply depot down hurts defender repairs; armoury / keep have their own board effects.

### Capture stages (assault)

1. **Outer Yard** — clear barricades/guards; press the supply area.
2. **Gatehouse** — needs a breach; engines vs gates/walls; repairs slow the push.
3. **Courtyard** — fight inside; defenders may regroup with fallback fortification.
4. **Throne Room (Last Stand)** — keep must be down; system Royal Guard fortifies the chamber; appointed player guards protect the King; attackers must hold to claim.
5. **Crownfall** — coronation / realm announce; heraldry on the King's Castle; battle report.

### War storehouse

- Deposit inventory items with `/siege deposit <item> <qty>` — they convert to **timber / ore / bars / stone**.
- Deposits **cannot be withdrawn** for personal use. The lead Leader only **allocates** % to rams / ladders / barricades / reserve.
- Allocations **lock** when the assault begins.
- Contribution board: `/siege contrib` (deposits, engine work, captures, kills).

Common deposit items: logs (all wood tiers) → timber; ores / coal → ore or stone; bars → bars. See `/siege costs` for engine recipes.

### Useful commands

```
/siege status          War board (also Herald / war chip)
/siege register attack|defend
/siege confirm | forfeit
/siege ally <guild> | accept | decline
/siege store | costs | deposit <item> <qty>
/siege alloc                     show budgets
/siege alloc rams=40 ladders=25 barricades=20 reserve=15
/siege craft <weapon> [qty]
/siege fire <weapon> <structure>
/siege repair <structure> [batches]
/siege barricade <outer_yard|gatehouse|courtyard|throne>
/siege guard <point>             post a Guard recruit
/siege royalguard <name>         appoint (Monarch/Marshal)
/siege royalguard dismiss <name>
/siege scout | weapons | roster | captures
/siege when <1-72>h | when 2d    attack Leader assault window
/siege begin                     open assault early (attack Leader)
/siege report                    battle report
/siege council | heraldry
```

Herald dialogue mirrors many of these (status, register, confirm, store, costs, scout, Royal Guard, battle report).

### UI surfaces

- **Royal Herald** (King's Castle) — dialogue options for war actions.
- **War chip** (top centre in castle realm) — status, assault countdown / UTC, Last Stand, Royal Guard markers; click for the board.
- **World map War Council** — peacetime countdown, calendar phase, last Crownfall + report teaser.
- **Great Hall** — chronicle of reigns, Royal Crown / King's Outfit notes while the throne is held.

### Monthly calendar (anticipation)

| Days | Focus |
| --- | --- |
| 1–7 | Royal announcements, guild recruitment, diplomacy |
| 8–14 | Gather wood, stone, ore, supplies |
| 15–21 | Craft weapons, engines, fortifications |
| 22–27 | Final alliances, scouting, military prep |
| 28–29 | War registration and battle assignments |
| 30 | **The Siege of Crownfall** |

### Rules of thumb

- The old **Crown Challenge** is retired — use War for the Crown.
- The King / treasury paths must **not** mint coins or items for siege rewards.
- Interest during assault fans out nearby fighters (radius grows after the watchtower falls; cap matches the 100-a-side profile).
- After Crownfall, check `/siege report` and the War Council for the full tally.

### Dev / test

```
cd game/assets/mmorpg
.venv/bin/python tools/test_crown_siege.py
```

Server: `server/server.py` on **127.0.0.1:8765** (use the project venv).

## Controls
- **Click** the map to walk / attack / talk / gather / use interactables
- **Arrow keys** — walk one tile
- **Space** — attack nearest monster in reach
- **R** — eat best food (or health potion); while under attack, click the buttons above your head to eat / drink potions from inventory or bags
- **1–5** — combat styles (Att/Str/Def/HP/Arch); with a bow only Archery is available
- **H** — help · **E** — equipment · **Tab** — skills · **M** — travel / world map
- **F** — forge (furnace/anvil) · **C** — cook · **N** — fletch (needs a knife)
- **B** — bank or shop (when beside booth / in dialogue)
- **G** — pickup · **P** — toggle Coins+bones auto-pickup (off by default) · **Q** — quest log · **Enter** — chat
- Dialogue: **A** accept quest · **T** turn in · **B** shop/bank · **S** forge · **Esc** close
- Tidehollow: confirm at the cave mouth; **Esc** abandons the run when no modal is open
- Equipment slots: weapon / shield / body / legs / helmet / amulet / ring / ammo

Economy: purse max **65,000** coins; bank vault **10,000,000** + 96 slots; inventory **96** slots (4×24 tabs).

## Architecture
```
server/
  server.py         websocket server, 0.6s tick, handlers
  database.py       SQLite persistence
  content.py        items, monsters, NPCs, shops, quests, recipes
  combat.py         RS2001 hit / max-hit + XP curve
  world_map.py      procedural overworld
  dungeon.py        Tidehollow floors + kill loot
  crown_siege.py    War for the Crown (structures, registration, storehouse, assaults)
  throne.py         throne / crowning; Crown Challenge retired in favour of war
  castle_realm.py   King's Castle planes + siege breach walkability
client/
  network.py        websocket bridge
  client.py         pygame UI + rendering (+ crown siege HUD merge)
  castle_realm_renderer.py   castle overlays, war chip / board
shared/
  protocol.py       message type reference
tools/
  test_crown_siege.py   headless War for the Crown suite
```

## Extending it
- New item → `ITEMS` in `content.py`
- New monster → `MONSTERS` + `MONSTER_SPAWNS`
- New quest → `QUESTS` (`kill`, `collect`, `collect_multi`, `find_npc`, `gift`)
- New shop → `SHOPS` + NPC `shop_id`
- New map area → `world_map.py` `generate_world()`
- War for the Crown tuning / weapons / stages → `server/crown_siege.py` (keep design-backed; see guide above)
