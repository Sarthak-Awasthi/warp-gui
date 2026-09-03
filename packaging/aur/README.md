# Publishing warp-gui to the AUR

This directory holds an Arch `PKGBUILD` (and a generated `.SRCINFO`) for
**warp-gui**. The project maintainer has **not** published it to the AUR yet — so
if you'd like to maintain an AUR package, you're very welcome to. This note has
everything you need.

> Please coordinate first by opening an issue on
> <https://github.com/Sarthak-Awasthi/warp-gui/issues> so we don't end up with
> duplicate packages, and so the README can link to yours.

## What the package does

- Installs the `warp_gui` module and a `/usr/bin/warp-gui` launcher, plus the
  desktop entry, icons and AppStream metadata.
- `depends`: `python`, `python-pyqt5`.
- `optdepends`: `cloudflare-warp-bin` — the official Cloudflare WARP client,
  which provides the `warp-cli` this GUI drives. It's an optdepend rather than a
  hard depend so users who install the WARP client another way aren't forced to
  pull it; the app warns at startup if `warp-cli` is missing.

Two obvious package names are possible:

- **`warp-gui`** — a versioned package built from the release tarball (this
  `PKGBUILD`). Bump `pkgver` and `sha256sums` on each release.
- **`warp-gui-git`** — a `-git` variant that builds from the latest `main`. If
  you publish this, rename `pkgname` to `warp-gui-git`, add a `pkgver()` function
  and use the git source (`source=("git+https://github.com/Sarthak-Awasthi/warp-gui.git")`,
  `sha256sums=('SKIP')`).

## Build & test it locally

```bash
cd packaging/aur
makepkg -si          # build and install (pulls makedepends + deps)
# or just build without installing:
makepkg -f
namcap warp-gui-*.pkg.tar.zst   # optional lint (pacman -S namcap)
```

`makepkg` verifies the source `sha256sums` automatically. If you change the
tarball or version, refresh the checksum with `updpkgsums` (from
`pacman-contrib`) and regenerate the srcinfo:

```bash
updpkgsums
makepkg --printsrcinfo > .SRCINFO
```

## Submit / update on the AUR

You need an [AUR account](https://aur.archlinux.org/) with an SSH key added to
your profile.

```bash
# First time: clone the (empty) AUR repo for the name you're claiming
git clone ssh://aur@aur.archlinux.org/warp-gui.git aur-warp-gui
cd aur-warp-gui

# Copy in the packaging files (PKGBUILD + .SRCINFO are the only required ones)
cp /path/to/warp-gui/packaging/aur/PKGBUILD .
makepkg --printsrcinfo > .SRCINFO      # always regenerate before committing

git add PKGBUILD .SRCINFO
git commit -m "Initial import: warp-gui 1.0.0"
git push
```

To push a new version later: bump `pkgver`, run `updpkgsums`, regenerate
`.SRCINFO`, commit and push.

## Checklist before submitting

- [ ] `pkgver` matches the release tag and `sha256sums` matches the tarball
- [ ] `.SRCINFO` regenerated from the final `PKGBUILD`
- [ ] `namcap` shows no serious warnings
- [ ] `makepkg -si` builds and the installed `warp-gui` launches
- [ ] `Maintainer:` line updated to your name/email
