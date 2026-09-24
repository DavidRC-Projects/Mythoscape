#!/usr/bin/env bash
# Prefer Blender ortho render; fall back to pygame bake.
# Usage: ./render_buildings.sh [building_id|--all]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ID="${1:-cottage_nw}"

find_blender() {
  if command -v blender >/dev/null 2>&1; then command -v blender; return; fi
  for c in \
    "/Applications/Blender.app/Contents/MacOS/Blender" \
    "/opt/homebrew/bin/blender" \
    "/usr/local/bin/blender"
  do
    [[ -x "$c" ]] && { echo "$c"; return; }
  done
  return 1
}

if BLENDER="$(find_blender)"; then
  echo "Using Blender: $BLENDER"
  if [[ "$ID" == "--all" ]]; then
    for bid in cottage_nw cottage_ne cottage_sw cottage_se bank; do
      "$BLENDER" --background --python "$ROOT/blender_render_building.py" -- "$bid"
    done
  else
    "$BLENDER" --background --python "$ROOT/blender_render_building.py" -- "$ID"
  fi
else
  echo "Blender not found — baking pygame ortho shells (install Blender to upgrade)."
  echo "  brew install --cask blender"
  PY="${PYTHON:-python3}"
  if [[ "$ID" == "--all" ]]; then
    "$PY" "$ROOT/bake_building_sprite.py" --all
  else
    "$PY" "$ROOT/bake_building_sprite.py" "$ID"
  fi
fi
