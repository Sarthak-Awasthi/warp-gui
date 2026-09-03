#!/usr/bin/env bash
# Build .deb and .rpm packages from the project using fpm.
#
# The packages install the warp_gui sources into /usr/share/warp-gui and a small
# /usr/bin/warp-gui launcher that adds that directory to sys.path. This is
# deliberately version-independent: it works with whatever python3 minor version
# the target distro ships (unlike installing into a python3.X/site-packages that
# only matches one version). Python itself is NOT bundled; the packages depend on
# the distro's python3 + PyQt5.
#
# Requirements: python3, fpm (Ruby gem); the rpm target also needs `rpm`.
# Usage:  packaging/build-deb-rpm.sh [deb|rpm|all]   (default: all)
set -euo pipefail

TARGET="${1:-all}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

VERSION="$(python3 -c 'import warp_gui; print(warp_gui.__version__)')"
STAGE="$HERE/build/stage"
DIST="$HERE/dist"
MAINTAINER="Sarthak-Awasthi <bengdeeba@gmail.com>"
URL="https://github.com/Sarthak-Awasthi/warp-gui"
DESC="Unofficial Linux GUI (system tray + window) for the Cloudflare WARP client (warp-cli)."

echo ">> Staging files (version $VERSION)"
rm -rf "$STAGE"; mkdir -p "$DIST"
APPLIB="$STAGE/usr/share/warp-gui"

# App sources (source only, no bytecode).
for f in warp_gui/*.py; do
  install -Dm644 "$f" "$APPLIB/$f"
done

# Version-independent launcher.
install -d "$STAGE/usr/bin"
cat > "$STAGE/usr/bin/warp-gui" <<'EOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/share/warp-gui")
from warp_gui.app import main
sys.exit(main())
EOF
chmod 755 "$STAGE/usr/bin/warp-gui"

# Desktop entry, icons, metainfo, license.
install -Dm644 packaging/warp-gui.desktop \
  "$STAGE/usr/share/applications/warp-gui.desktop"
install -Dm644 assets/warp-gui.svg \
  "$STAGE/usr/share/icons/hicolor/scalable/apps/warp-gui.svg"
install -Dm644 assets/warp-gui.png \
  "$STAGE/usr/share/icons/hicolor/256x256/apps/warp-gui.png"
install -Dm644 packaging/io.github.sarthak_awasthi.warp_gui.metainfo.xml \
  "$STAGE/usr/share/metainfo/io.github.sarthak_awasthi.warp_gui.metainfo.xml"
install -Dm644 LICENSE "$STAGE/usr/share/doc/warp-gui/LICENSE"

fpm_common=(
  -s dir -n warp-gui -v "$VERSION" -C "$STAGE"
  --license MIT --maintainer "$MAINTAINER" --url "$URL" --description "$DESC"
  --category net --force
)

build_deb() {
  echo ">> Building .deb"
  fpm "${fpm_common[@]}" -t deb --architecture all \
    --depends python3 --depends python3-pyqt5 \
    --deb-suggests cloudflare-warp \
    -p "$DIST/warp-gui_${VERSION}_all.deb" usr
}

build_rpm() {
  echo ">> Building .rpm"
  fpm "${fpm_common[@]}" -t rpm --architecture noarch \
    --depends python3 --depends 'python3-qt5' \
    -p "$DIST/warp-gui-${VERSION}-1.noarch.rpm" usr
}

case "$TARGET" in
  deb) build_deb ;;
  rpm) build_rpm ;;
  all) build_deb; build_rpm ;;
  *) echo "Usage: $0 [deb|rpm|all]" >&2; exit 2 ;;
esac

echo ">> Done. Artifacts in $DIST:"
ls -1 "$DIST"/*.deb "$DIST"/*.rpm 2>/dev/null || true
