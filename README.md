# Crownfall

Crownfall is a RuneScape-classic-style multiplayer sandbox RPG: shared overworld, skills, quests, combat, crafting, dungeons, housing, and politics — all running locally on your machine over WebSockets.

This repository is the Crownfall game project (folder name may still say Mythoscape).

## Requirements

- **Python 3.10+** (3.11–3.13 recommended)
- macOS, Linux, or Windows
- A display for the Pygame client (server can be headless)

Optional:

- **Blender** — only if you rebuild building / prop art (`brew install --cask blender` on macOS)
- **Panda3D** extras — already listed in `requirements.txt` for the optional building prototype

## Install (local)

From the repo root:

```bash
cd game/assets/mmorpg
python3 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
# .venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

Dev / asset-pipeline tools (Blender export helpers, not needed to play):

```bash
pip install -r requirements-dev.txt
```

## Run

Open **two terminals**, both with the venv activated.

**1. Server** (binds `0.0.0.0:8765`):

```bash
cd game/assets/mmorpg/server
python server.py
```

**2. Client**:

```bash
cd game/assets/mmorpg/client
python client.py              # connect to localhost
python client.py 192.168.1.5  # connect to a LAN host
```

Create an account on the login screen, then enter the world. Player data is stored in a local SQLite database under `server/` (gitignored).

On the login screen you can open **Hiscores** (or press **F3**) for top players per skill.

### LAN / friends on the same network

1. Start the server on the host machine as above.
2. Allow inbound TCP **8765** on that machine’s firewall if needed.
3. On other PCs, run `python client.py <host-lan-ip>`.

## How to play

Crownfall plays like a classic point-and-click MMORPG: click to move and interact, train skills, complete quests, gear up, and push into harder areas (caves, Emberdeep, castles, politics).

### First session

1. Log in and press **H** for the full controls list.
2. Talk to **Elder Miriam** in the NW cottage — she gives the starter quest.
3. Click NPCs to talk, monsters to fight, trees/rocks/fish spots to gather.
4. Open your **quest log** with **Q**, **skills** with **Tab**, **equipment** with **E**, and the **world map / travel** with **M**.
5. When you die or run low, eat with **R** (best food / potions). Bring food before caves.

### What to do next

| Goal | Where / who |
|------|-------------|
| Starter quest | **Elder Miriam** (NW cottage) |
| Free bow kit + fletching shop | **Fletcher Elena** (east of the village) — talk once; **B** for her shop |
| Lost Locket quest | **Lira the Jeweler** — locket near the wishing well (south of the crossroads) |
| Smelt & smith | **Gareth** at the smithy — stand at furnace/anvil, press **F** |
| Food, potions, early steel | **Mira** in **Stonehaven** |
| Fishing / cooking gear | **Harbourreach** (tackle shop + Nell’s Catch) |
| First dungeon | **Tidehollow Cave** at Harbourreach — bring food; loot goes to your pack |

### Combat

- Click a monster (or press **Space** for the nearest in reach).
- Styles **1–5**: Attack / Strength / Defence / Hitpoints / Archery (bows lock you to Archery).
- While fighting, use the buttons above your head to eat or drink from inventory / bags.
- Wear better gear in **E** (weapon, shield, body, legs, helmet, amulet, ring, ammo).

### Gathering, crafting, inventory

- **Mine**, **chop**, **fish**, then process: **F** forge, **C** cook, **N** fletch (needs a knife).
- Inventory is **4 tabs × 24 slots**: Gen / Gather / Craft / **Bags**.
- Storage bags (Mining, Log, Gem, Food, Raw Food, Potion pouch, tip box, quiver): open the **Bags** tab, click a bag to **Pack** / **Unpack**. Crafting prefers bag contents.
- Shops: click to sell **1**, **Shift+click** to sell the whole stack. Purse max **65,000**; bank vault **10,000,000** + 96 slots.

### Dialogue & menus

| Key | Action |
|-----|--------|
| **A** | Accept quest |
| **T** | Turn in quest |
| **B** | Open shop or bank (when available) |
| **S** | Open forge from dialogue |
| **Esc** | Close panels / abandon a dungeon run when no modal is open |
| **Enter** | Chat |
| **G** / **P** | Pickup / toggle auto-pickup |

### Controls cheat sheet

| Action | Input |
|--------|--------|
| Walk / talk / attack / gather / use objects | Click the world |
| Step one tile | Arrow keys |
| Attack nearest | Space |
| Eat / drink | **R** |
| Help | **H** |
| Equipment / skills / map | **E** / **Tab** / **M** |
| Forge / cook / fletch | **F** / **C** / **N** |
| Bank or shop | **B** |
| Quest log / chat | **Q** / Enter |

More architecture and builder notes: [`game/assets/mmorpg/README.md`](game/assets/mmorpg/README.md).

## Project layout

```
game/assets/mmorpg/
  server/          Authoritative WebSocket server, world, content, SQLite
  client/          Pygame client (window title: Crownfall)
  shared/          Shared protocol notes
  assets/          Runtime art and audio used by client/server
  requirements.txt Python dependencies
  PATCH_NOTES.md   Changelog
```

Source art packs and HD pipelines live under `game/assets/` (buildings, monsters, player skins, etc.). Runtime code loads from `game/assets/mmorpg/`.

## Extending the game

| Add… | Edit… |
|------|--------|
| Item | `server/content.py` → `ITEMS` |
| Monster | `MONSTERS` + `MONSTER_SPAWNS` |
| Quest | `QUESTS` |
| Shop | `SHOPS` + NPC `shop_id` |
| Map area | `server/world_map.py` |

## Security / deploy (go-live checklist)

Crownfall is designed to sit **behind a TLS reverse proxy**. Never expose port `8765` to the public internet.

### Recommended layout

```
Internet → (optional Cloudflare) → Caddy :443 (wss) → 127.0.0.1:8765 (Python)
```

Example configs: [`game/assets/mmorpg/deploy/Caddyfile.example`](game/assets/mmorpg/deploy/Caddyfile.example) and [`game/assets/mmorpg/deploy/crownfall.service.example`](game/assets/mmorpg/deploy/crownfall.service.example).

### Production environment

```bash
export CROWNFALL_ENV=production          # binds 127.0.0.1 by default
export CROWNFALL_HOST=127.0.0.1
export CROWNFALL_PORT=8765
export CROWNFALL_ALLOW_REGISTER=1        # set 0 for closed beta
export CROWNFALL_DEV=0                   # never 1 on a public box unless needed
# Only if you truly need :: commands on that host:
# export CROWNFALL_DEV=1
# export CROWNFALL_DEV_USERS=your_gm_name
# Optional DB path outside the web tree:
# export CROWNFALL_DB_PATH=/var/lib/crownfall/world.db
```

Players connect with TLS:

```bash
python client.py play.example.com
# or
export CROWNFALL_WS_URL=wss://play.example.com
python client.py
```

Local / LAN without TLS still works: `python client.py` or `python client.py 192.168.1.5:8765`.

### Before you go live

- [ ] App binds `127.0.0.1` only (`CROWNFALL_ENV=production`)
- [ ] Caddy/nginx terminates TLS; firewall allows **22 / 80 / 443** only — **not** 8765
- [ ] Optional Cloudflare proxy for volumetric DDoS
- [ ] `CROWNFALL_DEV=0` (no `::` god commands for normal players)
- [ ] Passwords are argon2id; registration rate-limited; login lockout after failed attempts
- [ ] `world.db` is mode `600`, not under any static HTTP root; WAL enabled
- [ ] Encrypted off-box backups of the DB (restic/borg/S3) — never leave `*.bak` on a public path
- [ ] Dedicated OS user + systemd unit with restart limits
- [ ] Smoke-test: bad login lockout, MOVE flood does not speed-hack, `::give` fails for normals, `wss://` client connects
- [ ] Run economy integrity suite: `cd game/assets/mmorpg && python3 tools/test_economy_integrity.py`

### What the server already enforces

| Control | Behaviour |
|---------|-----------|
| Auth | argon2id hashes; legacy SHA-256 upgraded on login; username `[A-Za-z0-9_]{3,20}`; password 8–128 on register |
| Abuse | Per-IP connection caps, login/register cooldowns, messages/sec limit, 64 KiB WS frame max |
| Cheats | One MOVE per world tick; inventory/economy server-authoritative; trade checks free space before swap |
| Admin | `::` commands only when `CROWNFALL_DEV=1` **and** username is in `CROWNFALL_DEV_USERS` |

## Credits & license notes

Third-party art attributions: [`CREDITS.md`](CREDITS.md) and `game/assets/mmorpg/client/textures/ATTRIBUTION.txt`.

## More detail

- Building art pipeline & architecture: [`game/assets/mmorpg/README.md`](game/assets/mmorpg/README.md)
- Patch history: [`game/assets/mmorpg/PATCH_NOTES.md`](game/assets/mmorpg/PATCH_NOTES.md)
