#!/usr/bin/env bash
# Build Crownfall.app for friends beta.
# Friends: unzip Crownfall-Mac.zip → right-click Crownfall → Open (first time).
#
#   CROWNFALL_PLAY_HOST=play.yourdomain.com ./game/assets/mmorpg/tools/pack_beta_macos.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
ASSETS="$ROOT/game/assets"
MMORPG="$ASSETS/mmorpg"
WEB_DL="$ROOT/website/downloads"
PLAY_HOST="${CROWNFALL_PLAY_HOST:-localhost}"
if [[ -n "${CROWNFALL_WS_URL:-}" ]]; then
  WS_URL="$CROWNFALL_WS_URL"
elif [[ "$PLAY_HOST" == "localhost" || "$PLAY_HOST" == "127.0.0.1" ]]; then
  WS_URL="ws://localhost:8765"
else
  WS_URL="wss://${PLAY_HOST}"
fi
STAGE="${TMPDIR:-/tmp}/crownfall-beta-pack-$$"
RES="$STAGE/Crownfall.app/Contents/Resources"
APP="$STAGE/Crownfall.app"
PY=python3
LAUNCHER_SRC="$MMORPG/tools/crownfall_macos_launcher.c"

# Sibling packs the client loads via ../../from mmorpg (see client/server paths).
SIBLINGS=(
  characters
  wolf_pass
  player_hd
  npc_hd
  knights_hd
  fairy_village
  emberdeep_v2_pack
  emberdeep_hd
  emberdeep_creatures_pack
  interior_props
  pets_hd
  pets_and_legacy_monsters_pack
  monsters_hd
  housing_pack_lite
  portal_pack
  opening_comic_pack
)

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This packer builds a macOS .app and must run on a Mac." >&2
  exit 1
fi

command -v "$PY" >/dev/null || { echo "python3 required" >&2; exit 1; }
command -v clang >/dev/null || { echo "clang required (Xcode CLT)" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync required" >&2; exit 1; }
command -v ditto >/dev/null || { echo "ditto required" >&2; exit 1; }

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "==> Play host: $WS_URL"
rm -rf "$STAGE"
mkdir -p "$APP/Contents/MacOS" "$RES"

echo "==> Staging mmorpg"
rsync -a \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude '*.db' \
  --exclude '*.db-*' \
  --exclude 'world_clock.json' \
  --exclude '.DS_Store' \
  --exclude 'panda_building_proto/' \
  --exclude 'tools/' \
  --exclude 'tests/' \
  --exclude 'deploy/' \
  "$MMORPG/" "$RES/mmorpg/"

echo "==> Staging sibling asset packs"
for name in "${SIBLINGS[@]}"; do
  src="$ASSETS/$name"
  if [[ -d "$src" ]]; then
    echo "    + $name"
    rsync -a \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude '.DS_Store' \
      --exclude '.git/' \
      "$src/" "$RES/$name/"
  else
    echo "    skip missing $name"
  fi
done

echo "==> Embedded venv"
"$PY" -m venv "$RES/mmorpg/.venv"
"$RES/mmorpg/.venv/bin/pip" install --upgrade pip
"$RES/mmorpg/.venv/bin/pip" install -r "$MMORPG/requirements-client.txt"
# Drop bytecode so Gatekeeper sealed-resources stay valid after first run.
find "$RES" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$RES" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

# Embed launcher that starts a local server when targeting localhost.
sed "s|@WS_URL@|${WS_URL}|g" "$MMORPG/tools/run_crownfall.sh.in" > "$RES/run_crownfall.sh"
chmod +x "$RES/run_crownfall.sh"

echo "==> Native launcher"
clang -Os -o "$APP/Contents/MacOS/Crownfall" "$LAUNCHER_SRC"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleExecutable</key><string>Crownfall</string>
  <key>CFBundleIdentifier</key><string>com.crownfall.friendsbeta</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>Crownfall</string>
  <key>CFBundleDisplayName</key><string>Crownfall</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.1</string>
  <key>CFBundleVersion</key><string>2</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Sign the Mach-O only, then the app. Avoid --deep on the huge Resources tree
# (venv + assets); sealing thousands of files breaks when anything changes.
codesign --force -s - "$APP/Contents/MacOS/Crownfall"
codesign --force -s - "$APP"
xattr -cr "$APP" 2>/dev/null || true

# Quick import smoke test before shipping
echo "==> Smoke-test imports"
(
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH="$RES/mmorpg/client:$RES/mmorpg/server:$RES/characters"
  cd "$RES/mmorpg/client"
  "$RES/mmorpg/.venv/bin/python" -B -c "import procedural_sprites_finished, content, world_map; print('imports ok')"
)

mkdir -p "$WEB_DL"
ZIP="$WEB_DL/Crownfall-Mac.zip"
rm -f "$ZIP" "$WEB_DL/Crownfall.dmg" "$WEB_DL/Crownfall-Friends-Beta-macOS.zip"

echo "==> Writing $ZIP"
ditto -c -k --keepParent --sequesterRsrc "$APP" "$ZIP"

# Local play helper (strips Gatekeeper quarantine — required on Sequoia for unsigned apps)
cat > "$WEB_DL/Play Crownfall.command" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
# Prefer an already-unzipped app next to this script; else unpack the zip once.
if [[ ! -d Crownfall.app ]]; then
  if [[ -f Crownfall-Mac.zip ]]; then
    echo "Unpacking Crownfall…"
    ditto -x -k Crownfall-Mac.zip .
  else
    echo "Put Crownfall-Mac.zip next to this script, or unzip it first."
    read -r -p "Press Return to close…"
    exit 1
  fi
fi
xattr -cr Crownfall.app 2>/dev/null || true
open Crownfall.app
EOF
chmod +x "$WEB_DL/Play Crownfall.command"

# Install a ready-to-run copy for this machine (skips download/Gatekeeper path)
LOCAL_APP="$HOME/Applications/Crownfall.app"
mkdir -p "$HOME/Applications"
rm -rf "$LOCAL_APP"
ditto "$APP" "$LOCAL_APP"
xattr -cr "$LOCAL_APP" 2>/dev/null || true

BYTES="$(wc -c < "$ZIP" | tr -d ' ')"
echo "==> Done (${BYTES} bytes)"
echo "    Zip: $ZIP"
echo "    Local install: $LOCAL_APP  (quarantine cleared — double-click to play)"
echo "    Or: open '$WEB_DL/Play Crownfall.command'"
