# Contributing to warp-gui

Thanks for your interest in improving warp-gui! This is a small, focused project
— a friendly PyQt5 front-end for the official Cloudflare `warp-cli`. Contributions
of all kinds are welcome: bug reports, fixes, features, docs, and packaging.

Please also read the [DISCLAIMER](DISCLAIMER.md) — this is an unofficial project
and contributions must respect Cloudflare's trademarks (see below).

## Getting set up

**Requirements**

- The official Cloudflare WARP client installed (`warp-cli` + the `warp-svc`
  daemon running). See the project [README](README.md).
- Python 3 and PyQt5:
  - Arch / CachyOS: `sudo pacman -S python-pyqt5`
  - Debian / Ubuntu: `sudo apt install python3-pyqt5`

**Run from source**

```bash
git clone <your-fork-url> warp-gui
cd warp-gui
python3 main.py
```

## Project layout

| Path | Responsibility |
|------|----------------|
| `warp_gui/backend.py` | Wraps `warp-cli` (no Qt). Parses JSON output, returns plain data. |
| `warp_gui/worker.py`  | Runs `warp-cli` calls off the UI thread via `QThreadPool`. |
| `warp_gui/icons.py`   | Draws the state icons at runtime. |
| `warp_gui/config.py`  | Persists the DNS-family value and saved profiles. |
| `warp_gui/app.py`     | The main window and system-tray UI. |
| `install.sh`          | Per-user install / uninstall of launcher + menu entry. |

`backend.py` is intentionally Qt-free so it can be imported and tested on its own.

## Guidelines

- **Keep the UI non-blocking.** Every `warp-cli` invocation must run through a
  `Worker` (never call `subprocess` directly on the GUI thread).
- **Combo boxes:** never mutate a `QComboBox` synchronously inside its own
  `activated` handler — defer with `QTimer.singleShot(0, ...)`. (See the note in
  `app.py`; doing otherwise can crash Qt during popup teardown.)
- **Handle `warp-cli` output defensively.** Field shapes vary between states
  (e.g. `status.reason` is a string when settled but an object while connecting).
- **Match the existing style** — standard library formatting, clear names, and
  comments only where the *why* isn't obvious.
- **No new runtime dependencies** beyond PyQt5 unless there's a strong reason.
- **Scope:** warp-gui only *controls* the official client. It must never bundle,
  download, or modify Cloudflare software.

## Submitting changes

1. Fork the repository and create a branch: `git checkout -b my-change`.
2. Make your change and test it:
   - `python3 -m py_compile warp_gui/*.py main.py`
   - Run the app and exercise the affected paths (connect/disconnect, mode,
     profiles, registration).
3. Commit with a clear message describing the *what* and *why*.
4. Open a pull request describing the change and how you tested it. Screenshots
   are appreciated for UI changes.

## Reporting bugs

Open an issue including:

- Your distro and desktop environment (e.g. "CachyOS, KDE Plasma Wayland").
- `warp-cli --version` and the PyQt5 version.
- What you did, what you expected, and what happened. If the app crashed, run it
  from a terminal (`python3 main.py`) and paste any output.

## Trademarks

"Cloudflare" and "WARP" are trademarks of Cloudflare, Inc. Use them only
*nominatively* — to describe interoperability — and never in a way that implies
this project is official or endorsed. Do not add Cloudflare logos or brand
assets to the project. See [DISCLAIMER.md](DISCLAIMER.md).

## License

By contributing, you agree that your contributions will be licensed under the
project's [MIT License](LICENSE).
