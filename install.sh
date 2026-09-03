#!/usr/bin/env bash
# Install (or remove) the Cloudflare WARP GUI for the current user.
#   ./install.sh              install launcher + menu entry + icon
#   ./install.sh --autostart  also start automatically on login
#   ./install.sh --uninstall  remove everything this script installed
set -euo pipefail

PROJECT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART_DIR="$HOME/.config/autostart"

LAUNCHER="$BIN_DIR/warp-gui"
DESKTOP="$APP_DIR/warp-gui.desktop"
AUTOSTART="$AUTOSTART_DIR/warp-gui.desktop"
ICON="$ICON_DIR/warp-gui.svg"

uninstall() {
  echo "Removing Cloudflare WARP GUI..."
  rm -f "$LAUNCHER" "$DESKTOP" "$AUTOSTART" "$ICON"
  command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
  echo "Done. (Project files in $PROJECT_DIR were left untouched.)"
}

install_files() {
  local autostart="$1"

  # Dependency check.
  if ! command -v warp-cli >/dev/null 2>&1; then
    echo "WARNING: warp-cli not found on PATH. Install the cloudflare-warp client." >&2
  fi
  if ! python3 -c "import PyQt5" >/dev/null 2>&1; then
    echo "ERROR: PyQt5 is not installed for python3." >&2
    echo "  Arch/CachyOS: sudo pacman -S python-pyqt5" >&2
    echo "  Debian/Ubuntu: sudo apt install python3-pyqt5" >&2
    exit 1
  fi

  mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

  chmod +x "$PROJECT_DIR/warp-gui" "$PROJECT_DIR/main.py"
  ln -sf "$PROJECT_DIR/warp-gui" "$LAUNCHER"
  echo "Launcher: $LAUNCHER -> $PROJECT_DIR/warp-gui"

  install -m 644 "$PROJECT_DIR/assets/warp-gui.svg" "$ICON"
  echo "Icon:     $ICON"

  sed -e "s|@EXEC@|$LAUNCHER|g" -e "s|@ICON@|warp-gui|g" \
    "$PROJECT_DIR/warp-gui.desktop.in" > "$DESKTOP"
  chmod 644 "$DESKTOP"
  echo "Menu:     $DESKTOP"

  if [ "$autostart" = "yes" ]; then
    mkdir -p "$AUTOSTART_DIR"
    cp "$DESKTOP" "$AUTOSTART"
    echo "Autostart enabled: $AUTOSTART"
  fi

  command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "NOTE: $BIN_DIR is not on your PATH; add it to run 'warp-gui' from a shell." ;;
  esac

  echo
  echo "Installed. Launch from your app menu (search \"WARP\") or run: warp-gui"
}

case "${1:-}" in
  --uninstall) uninstall ;;
  --autostart) install_files yes ;;
  "")          install_files no ;;
  *) echo "Usage: $0 [--autostart | --uninstall]" >&2; exit 2 ;;
esac
