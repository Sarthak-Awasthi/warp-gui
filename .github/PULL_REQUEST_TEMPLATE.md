<!-- Thanks for contributing to warp-gui! -->

## What does this change?

<!-- A short description of the change and why. Link any related issue: Fixes #123 -->

## How did you test it?

<!-- e.g. ran `python3 main.py`, exercised connect/disconnect + profiles, built a package -->

- [ ] `python3 -m py_compile main.py warp_gui/*.py` passes
- [ ] Ran the app and checked the affected screens
- [ ] Screenshots attached (for UI changes)

## Checklist

- [ ] warp-cli calls run off the UI thread (via `Worker`)
- [ ] No new runtime dependencies beyond PyQt5 (or explained why)
- [ ] Stays within scope — controls the official client, bundles no Cloudflare software
