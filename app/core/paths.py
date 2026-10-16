"""Application root resolution for source and PyInstaller frozen builds.

Getting this wrong is the classic frozen-app failure: resources exist in the
bundle but the code looks for them somewhere else. PyInstaller 6 collects
everything into ``_internal/`` and exposes it as ``sys._MEIPASS``, so that is the
authoritative location — with the executable's own directory checked as well, so
a user can swap in a newer ``vendor/oxipng.exe`` next to the exe without a
rebuild.
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    """Directory containing the exe (frozen) or the project root (source)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def app_root() -> Path:
    """Directory holding bundled resources (fonts, vendor binaries).

    Frozen: PyInstaller's ``_MEIPASS`` (the ``_internal`` folder in a one-dir
    build). Source: the repository root, i.e. two parents up from this file.
    Never use ``__file__`` without the frozen check — in a bundle it points into
    the extraction directory, and in a one-file build that directory is deleted
    on exit.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return executable_dir()


def search_roots() -> tuple[Path, ...]:
    """Where to look for optional resources, most specific first.

    The executable's own folder wins so a user-provided binary can override the
    packaged one.
    """
    roots = [executable_dir()]
    bundled = app_root()
    if bundled not in roots:
        roots.append(bundled)
    return tuple(roots)


def vendor_binary(name: str) -> Path:
    """Path to an external tool, preferring ``<exe dir>/vendor/<name>``.

    Returns the first existing candidate, or the packaged path when none exists
    so error messages point somewhere meaningful.
    """
    candidates = [root / "vendor" / name for root in search_roots()]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def fonts_dir() -> Path:
    """Directory holding the bundled OFL fonts.

    Source: ``app/assets/fonts`` next to the package. Frozen: the spec copies
    them to ``assets/fonts`` beside the bundle, and the executable's own folder
    is checked first so they can also be dropped in by hand.
    """
    if not is_frozen():
        return Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for root in search_roots():
        candidate = root / "assets" / "fonts"
        if candidate.is_dir():
            return candidate
    return search_roots()[-1] / "assets" / "fonts"
