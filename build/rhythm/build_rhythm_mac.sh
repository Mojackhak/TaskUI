#!/usr/bin/env bash
set -euo pipefail

# Build a macOS .app bundle for the Rhythm task.
# Requires: python3 + PyInstaller installed in the current environment.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/rhythm"
APP_NAME="Rhythm"
ENTRYPOINT="$ROOT_DIR/rhythm/gui/gui.py"
PNG_ICON="$ROOT_DIR/rhythm/icon/icon.png"
ICNS_ICON="$BUILD_DIR/icon.icns"

DIST_DIR="$BUILD_DIR/dist"
WORK_DIR="$BUILD_DIR/pyi_build"
SPECPATH="$BUILD_DIR"

mkdir -p "$DIST_DIR" "$WORK_DIR" "$SPECPATH"

# Convert PNG to ICNS if possible for a proper macOS app icon.
if command -v iconutil >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
  ICONSET_DIR="$BUILD_DIR/icon.iconset"
  mkdir -p "$ICONSET_DIR"
  for size in 16 32 64 128 256 512; do
    sips -z "$size" "$size" "$PNG_ICON" --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
    sips -z $((size * 2)) $((size * 2)) "$PNG_ICON" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns -o "$ICNS_ICON" "$ICONSET_DIR"
else
  echo "Warning: iconutil/sips not available; app will use default icon."
fi

python3 -m PyInstaller --clean --noconfirm \
  --name "$APP_NAME" \
  --windowed \
  --onefile \
  --workpath "$WORK_DIR" \
  --distpath "$DIST_DIR" \
  --specpath "$SPECPATH" \
  ${ICNS_ICON:+--icon "$ICNS_ICON"} \
  "$ENTRYPOINT"

echo "Built app at: $DIST_DIR/${APP_NAME}.app"
echo "If you need logs, run: $DIST_DIR/${APP_NAME}.app/Contents/MacOS/${APP_NAME} from a terminal."
