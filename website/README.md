# Crownfall friends-beta site

Static landing page for a closed friends beta: invite code → download Mac client → open and play.

The Mac app starts a **local game server** when opened (localhost) and stops it on quit. For a shared online world, pack with `CROWNFALL_PLAY_HOST=play.yourdomain.com` instead.

## Local preview

```bash
cd website
python3 -m http.server 8080
# open http://localhost:8080
```

Default invite code: `CROWNFALL-FRIENDS` (change in `js/site.js`).

## Build the Mac download

On a Mac, from the repo root:

```bash
chmod +x game/assets/mmorpg/tools/pack_beta_macos.sh
./game/assets/mmorpg/tools/pack_beta_macos.sh
# or online friends server:
# CROWNFALL_PLAY_HOST=play.yourdomain.com ./game/assets/mmorpg/tools/pack_beta_macos.sh
```

Slim (default download):

```bash
./game/assets/mmorpg/tools/pack_beta_macos_slim.sh
# → website/downloads/Crownfall-Mac-Slim.zip
```

Full HD (multi‑GB, optional):

```bash
./game/assets/mmorpg/tools/pack_beta_macos.sh
# → website/downloads/Crownfall-Mac.zip
```

A “compiled binary” (PyInstaller/Nuitka) only shrinks the Python runtime a little; almost all size is art. The slim pack drops HD packs and uses procedural art instead.

## Deploy

Point Caddy (or any static host) at this folder. See `game/assets/mmorpg/deploy/Caddyfile.example` for site + `play.` WebSocket hosts.

Art: AI-painted hero and wax seal under `assets/`; brand wordmark from the in-game login title.
