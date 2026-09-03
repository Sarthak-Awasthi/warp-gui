#!/usr/bin/env python3
"""Entry point for the Cloudflare WARP GUI."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from warp_gui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
