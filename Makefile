# Convenience targets for building and packaging warp-gui.
.PHONY: help run wheel deb rpm appimage packages clean

help:
	@echo "warp-gui make targets:"
	@echo "  run       - run the app from source (python3 main.py)"
	@echo "  wheel     - build the Python wheel + sdist into dist/"
	@echo "  deb       - build a .deb package (needs fpm)"
	@echo "  rpm       - build a .rpm package (needs fpm + rpm)"
	@echo "  appimage  - build a self-contained .AppImage (needs curl + network)"
	@echo "  packages  - build deb + rpm + appimage"
	@echo "  clean     - remove build/ and dist/"

run:
	python3 main.py

wheel:
	python3 -m build

deb:
	packaging/build-deb-rpm.sh deb

rpm:
	packaging/build-deb-rpm.sh rpm

appimage:
	packaging/build-appimage.sh

packages: deb rpm appimage

clean:
	rm -rf build/ dist/ *.egg-info warp_gui.egg-info
