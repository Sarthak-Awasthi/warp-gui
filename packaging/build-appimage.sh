#!/usr/bin/env bash
# Build a self-contained warp-gui AppImage.
#
# Strategy: start from a relocatable Python base AppImage (niess/python-appimage),
# pip-install our wheel into it (this pulls the PyQt5 wheel, which bundles Qt),
# swap in our AppRun/desktop/icon, then repack with appimagetool. The result
# carries its own Python + Qt and only needs a normal desktop's system libs.
#
# Requirements: bash, curl, python3 (+ build), and network access. FUSE is not
# required (we use --appimage-extract / APPIMAGE_EXTRACT_AND_RUN).
#
# Env overrides: PYVER (default 3.12), ARCH (default x86_64).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PYVER="${PYVER:-3.12}"
ARCH="${ARCH:-x86_64}"
VERSION="$(python3 -c 'import warp_gui; print(warp_gui.__version__)')"

WORK="$HERE/build/appimage"
DIST="$HERE/dist"
rm -rf "$WORK"; mkdir -p "$WORK" "$DIST"

echo ">> Building wheel (version $VERSION)"
python3 -m build --wheel

echo ">> Resolving a Python $PYVER base AppImage for $ARCH"
CP="cp${PYVER//./}"
API="https://api.github.com/repos/niess/python-appimage/releases/tags/python${PYVER}"
# Prefer the most compatible manylinux2014 (glibc 2.17) build.
BASE_URL="$(curl -fsSL "$API" \
  | grep -o "https://[^\"]*${CP}-${CP}-manylinux2014_${ARCH}\.AppImage" | head -1 || true)"
if [ -z "$BASE_URL" ]; then
  BASE_URL="$(curl -fsSL "$API" \
    | grep -o "https://[^\"]*${CP}-${CP}-manylinux[^\"]*_${ARCH}\.AppImage" | head -1)"
fi
[ -n "$BASE_URL" ] || { echo "Could not find a base Python AppImage" >&2; exit 1; }
echo "   $BASE_URL"

BASE="$WORK/python-base.AppImage"
curl -fsSL "$BASE_URL" -o "$BASE"
chmod +x "$BASE"

echo ">> Extracting base into AppDir"
( cd "$WORK" && "$BASE" --appimage-extract >/dev/null )
APPDIR="$WORK/squashfs-root"

echo ">> Installing warp-gui (+ PyQt5) into the AppDir's Python"
"$APPDIR/AppRun" -m pip install --no-warn-script-location \
  "$DIST"/warp_gui-"$VERSION"-*.whl

echo ">> Installing AppRun / desktop / icon"
# Remove the base image's Python launcher metadata.
rm -f "$APPDIR"/*.desktop "$APPDIR"/*.png "$APPDIR"/.DirIcon 2>/dev/null || true

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export APPDIR="$HERE"
PY="$(ls "$HERE"/opt/python*/bin/python[0-9]*.[0-9]* 2>/dev/null | head -1)"
[ -z "$PY" ] && PY="$HERE/usr/bin/python3"
exec "$PY" -m warp_gui "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

cp "$HERE/packaging/warp-gui.desktop" "$APPDIR/warp-gui.desktop"
cp "$HERE/assets/warp-gui.png" "$APPDIR/warp-gui.png"
cp "$HERE/assets/warp-gui.png" "$APPDIR/.DirIcon"
install -Dm644 "$HERE/assets/warp-gui.png" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps/warp-gui.png"
install -Dm644 "$HERE/packaging/warp-gui.desktop" \
  "$APPDIR/usr/share/applications/warp-gui.desktop"

echo ">> Fetching appimagetool"
TOOL="$WORK/appimagetool-${ARCH}.AppImage"
curl -fsSL \
  "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage" \
  -o "$TOOL"
chmod +x "$TOOL"

echo ">> Packing AppImage"
OUT="$DIST/warp-gui-${VERSION}-${ARCH}.AppImage"
export APPIMAGE_EXTRACT_AND_RUN=1
ARCH="$ARCH" "$TOOL" "$APPDIR" "$OUT"

echo ">> Done: $OUT"
ls -l "$OUT"
