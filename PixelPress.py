"""PixelPress launcher — the entry point PyInstaller freezes.

This file exists outside the ``app`` package on purpose. PyInstaller executes the
entry script as a top-level module with no parent package, so anything inside
``app/`` that uses relative imports (``from .cli import …``) fails with
"attempted relative import with no known parent package" once frozen. Importing
the package absolutely from here works both frozen and from source:

    python PixelPress.py            # GUI
    python PixelPress.py --headless # packaging self-check
"""
from __future__ import annotations

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
