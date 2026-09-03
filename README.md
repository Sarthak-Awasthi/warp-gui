# warp-gui — a Linux GUI for Cloudflare WARP

A lightweight **PyQt5** desktop front-end for `warp-cli` (the Cloudflare WARP
client for Linux). Register a device, pick your mode, and connect/disconnect —
all without touching a terminal. Lives in the system tray so it's one click away.

![states: connected / connecting / disconnected](assets/warp-gui.svg)

> **Unofficial project.** warp-gui is an independent, community-built GUI. It is
> **not** affiliated with or endorsed by Cloudflare, Inc., and bundles none of
> Cloudflare's software — it only controls the official `warp-cli` you install
> yourself. "Cloudflare" and "WARP" are trademarks of Cloudflare, Inc., used
> here nominatively. See [DISCLAIMER.md](DISCLAIMER.md).

## Features

- **One-click connect / disconnect** with a colour-coded status pill.
- **System-tray icon** that reflects the live connection state (orange =
  connected, amber = connecting, grey = disconnected, red = error). Left-click
  toggles the window; right-click gives a quick menu (connect/disconnect, mode
  submenu, quit).
- **Device registration** — register a new device (free personal account or a
  Zero Trust organization), or delete the current registration, from a dialog.
- **Mode selector** — all seven `warp-cli` modes: `warp`, `doh`, `warp+doh`,
  `dot`, `warp+dot`, `proxy`, `tunnel_only`.
- **Tunnel protocol** — switch between MASQUE (default) and WireGuard.
- **DNS family filter** (consumer) — Off / Malware / Malware+Adult. Defaults to
  **Off** and remembers the last value you applied (warp-cli has no read-back).
- **Profiles** — save the current Mode + Protocol + DNS-filter under a name and
  re-apply all three with one click. Stored in `~/.config/warp-gui/config.json`.
- **Verify** button — checks `https://www.cloudflare.com/cdn-cgi/trace` and
  reports whether traffic really goes through WARP (`warp=on`).
- **Non-blocking** — every `warp-cli` call runs on a background thread, so the
  UI never freezes. Status is polled every 3 seconds.
- Closing the window **hides to tray** instead of quitting; quit from the tray
  menu.

## Requirements

- The Cloudflare WARP client installed (`warp-cli` + the `warp-svc` daemon).
  Confirm the daemon is running:
  ```
  systemctl status warp-svc
  ```
- Python 3 and **PyQt5**:
  - Arch / CachyOS: `sudo pacman -S python-pyqt5`
  - Debian / Ubuntu: `sudo apt install python3-pyqt5`

  (PyQt5 is already present on this machine — no install needed.)

No `sudo` is needed to *run* the app: `warp-cli` talks to `warp-svc` over a
local socket as your user.

## Run it

From the project folder:

```
./warp-gui
# or
python3 main.py
```

## Install (menu entry + launcher)

```
./install.sh              # add to your app menu + a `warp-gui` launcher
./install.sh --autostart  # ...and start automatically on login
./install.sh --uninstall  # remove everything the installer added
```

This installs, for the current user only:

| What | Where |
|------|-------|
| Launcher symlink | `~/.local/bin/warp-gui` |
| App menu entry   | `~/.local/share/applications/warp-gui.desktop` |
| Icon             | `~/.local/share/icons/hicolor/scalable/apps/warp-gui.svg` |
| Autostart (opt.) | `~/.config/autostart/warp-gui.desktop` |

After installing, search for **“WARP”** in your application launcher. The
project files in `~/Projects/warp-gui` are never moved — the launcher points
back at them, so keep the folder in place (or re-run `install.sh` if you move it).

## Project layout

```
warp-gui/
├── main.py                 # entry point (run from source)
├── warp-gui                # bash launcher (resolves symlinks)
├── install.sh              # per-user install / uninstall
├── warp-gui.desktop.in     # desktop-entry template (for install.sh)
├── pyproject.toml          # package metadata + entry point + data files
├── Makefile                # build/packaging shortcuts
├── requirements.txt
├── assets/                 # app icons (svg + png)
├── packaging/
│   ├── warp-gui.desktop    # desktop entry (installed by packages)
│   ├── *.metainfo.xml      # AppStream metadata
│   ├── aur/PKGBUILD        # Arch / AUR recipe
│   ├── build-deb-rpm.sh    # .deb / .rpm via fpm
│   └── build-appimage.sh   # self-contained AppImage
├── .github/workflows/      # ci.yml (tests) + release.yml (build packages)
└── warp_gui/
    ├── backend.py          # warp-cli wrapper (no Qt) — parses JSON output
    ├── worker.py           # runs warp-cli off the UI thread
    ├── icons.py            # state icons drawn at runtime
    ├── config.py           # persisted family value + saved profiles
    ├── __main__.py         # `python -m warp_gui`
    └── app.py              # main window + system tray
```

`backend.py` is Qt-free and can be imported and tested on its own.

## Installing a prebuilt package

Prebuilt packages are attached to each [GitHub Release](https://github.com/Sarthak-Awasthi/warp-gui/releases):

- **AppImage** (any distro): download `warp-gui-*.AppImage`, `chmod +x` it, and
  run it. It bundles Python + Qt, so it only needs the official `warp-cli`
  installed on your system.
- **Debian/Ubuntu:** `sudo apt install ./warp-gui_*_all.deb`
- **Fedora/openSUSE:** `sudo dnf install ./warp-gui-*.noarch.rpm`
- **Arch/CachyOS (AUR):** build from `packaging/aur/PKGBUILD` (`makepkg -si`), or
  once published, install `warp-gui` with your AUR helper.

The `.deb`/`.rpm`/AUR packages depend on your distro's system PyQt5; the AppImage
is fully self-contained. None of them bundle Cloudflare software — you still
install the official WARP client yourself.

## Building packages yourself

All packaging lives in `packaging/` and is driven by `pyproject.toml`. A
`Makefile` wraps the common targets:

```bash
make wheel      # Python wheel + sdist          -> dist/
make deb        # .deb via fpm                   -> dist/
make rpm        # .rpm via fpm                   -> dist/
make appimage   # self-contained .AppImage       -> dist/
make packages   # deb + rpm + appimage
```

- **wheel** needs `python3 -m build`.
- **deb/rpm** need [`fpm`](https://fpm.readthedocs.io/) (and `rpm` for the rpm
  target). They install the app to `/usr/share/warp-gui` with a
  version-independent `/usr/bin/warp-gui` launcher, so they work with any
  `python3` the distro ships.
- **appimage** needs `curl` + network access; it downloads a relocatable Python
  base and `appimagetool`, bundles the app and PyQt5, and repacks.

CI builds all of these automatically: pushing a `v*` tag runs
`.github/workflows/release.yml`, which attaches the `.deb`, `.rpm`, `.AppImage`,
and wheel to a GitHub Release. `.github/workflows/ci.yml` runs a compile + import
smoke test and a wheel build on every push and PR.

## Notes & troubleshooting

- **No tray icon?** Some minimal desktops lack a StatusNotifier host. The main
  window still works window-only; the app prints a warning in that case.
- **"warp-cli not found"** — install the `cloudflare-warp` package and make sure
  `warp-svc` is running.
- **Registration fails** — if a registration already exists, delete it first
  (Delete Registration), then register again. Joining a Zero Trust org requires
  your team name and may open a browser for login.
- The DNS family filter has no read-back command in `warp-cli`, so the dropdown
  shows the last value applied **through this app** (persisted in the config
  file, defaulting to Off). If you change it from the CLI, the app won't know.
- **Connectivity drops after changing mode / protocol / DNS family while
  connected.** Applying one of these on a *live* tunnel makes `warp-svc`
  reconfigure DNS/routing; WARP may keep reporting *Connected / healthy* while
  name resolution is briefly broken. This is a WARP-client behaviour (it happens
  from the CLI too), not specific to this GUI. The app logs a reminder, and the
  fix is a quick **Disconnect → Connect**. If you prefer, change these settings
  while disconnected.

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the [MIT License](LICENSE).

## Disclaimer

This is an unofficial project and is not affiliated with Cloudflare, Inc. Please
read [DISCLAIMER.md](DISCLAIMER.md) for the full trademark notice and warranty
disclaimer.
