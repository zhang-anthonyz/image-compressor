"""Bundled font registration and family resolution.

The app ships Archivo (variable, nine named instances) and IBM Plex Mono, both
OFL-1.1. Chinese text is left to the system's Microsoft YaHei UI — bundling a CJK
font would add 10+ MB for glyphs Windows already has.

Every resolution goes through this module so a missing font degrades to a
working fallback chain instead of silently rendering something unintended.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from ..core.paths import fonts_dir

DISPLAY_FAMILY = "Archivo"
MONO_FAMILY = "IBM Plex Mono"

#: Appended to every family string so Qt resolves CJK glyphs by itself.
CJK_STACK = ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "SimSun")
UI_FALLBACKS = ("Segoe UI Variable Text", "Segoe UI", "Tahoma")
MONO_FALLBACKS = ("Cascadia Mono", "Consolas", "Courier New")

#: Weights used across the UI, as QFont.Weight numeric values.
WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500
WEIGHT_SEMIBOLD = 600
WEIGHT_BOLD = 700

_registered: dict[str, tuple[str, ...]] = {}
_resolved: dict[str, str] = {}


def load_bundled_fonts() -> dict[str, tuple[str, ...]]:
    """Register every bundled TTF. Idempotent; returns family -> styles."""
    if _registered:
        return _registered
    directory = fonts_dir()
    if directory.is_dir():
        for path in sorted(directory.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id == -1:
                continue
            for family in QFontDatabase.applicationFontFamilies(font_id):
                styles = tuple(QFontDatabase.styles(family))
                existing = _registered.get(family, ())
                _registered[family] = tuple(sorted(set(existing) | set(styles)))
    return _registered


def _installed() -> set[str]:
    return set(QFontDatabase.families())


def _pick(preferred: str, fallbacks: tuple[str, ...]) -> str:
    """First family that actually exists on this machine."""
    installed = _installed()
    for candidate in (preferred, *fallbacks):
        if candidate in installed:
            return candidate
    return preferred


def display_family() -> str:
    """Resolved Latin UI family (bundled Archivo, else a system grotesque)."""
    if "display" not in _resolved:
        load_bundled_fonts()
        _resolved["display"] = _pick(DISPLAY_FAMILY, UI_FALLBACKS)
    return _resolved["display"]


def mono_family() -> str:
    """Resolved monospace family for every numeric readout."""
    if "mono" not in _resolved:
        load_bundled_fonts()
        _resolved["mono"] = _pick(MONO_FAMILY, MONO_FALLBACKS)
    return _resolved["mono"]


def display_families() -> list[str]:
    """Explicit fallback chain: Latin display font, then CJK faces."""
    return _dedupe([display_family(), *CJK_STACK, *UI_FALLBACKS])


def mono_families() -> list[str]:
    """Mono for digits, with the same CJK tail (some readouts contain 汉字)."""
    return _dedupe([mono_family(), *CJK_STACK, *MONO_FALLBACKS])


def _dedupe(names: list[str]) -> list[str]:
    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return seen


def display_stack() -> str:
    """QSS ``font-family`` value: display font, then CJK fallbacks."""
    return ", ".join(f'"{name}"' for name in display_families())


def mono_stack() -> str:
    """QSS ``font-family`` value: mono font, then CJK fallbacks."""
    return ", ".join(f'"{name}"' for name in mono_families())


def make_font(
    family: str | None = None,
    size: int = 10,
    weight: int = WEIGHT_REGULAR,
    *,
    mono: bool = False,
    tracking: float | None = None,
) -> QFont:
    """Build a QFont, optionally with real letter-spacing.

    The family list is set with ``setFamilies`` rather than ``setFamily``: Qt then
    does per-character fallback through the list, which is what makes Archivo
    (Latin only) sit next to Microsoft YaHei UI for Chinese text. Setting a single
    family instead renders every Chinese character as a tofu box, because nothing
    tells Qt where to look for the missing glyphs.

    QSS cannot express ``letter-spacing`` (Qt ignores it), so tracking is applied
    to the QFont object here — which is why the micro-caps labels in this app look
    tracked instead of merely uppercase.
    """
    font = QFont()
    font.setFamilies(mono_families() if mono else ([family] if family else []) + display_families())
    font.setPointSize(size)
    font.setWeight(QFont.Weight(weight))
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def apply_tracking(font: QFont, spacing: float) -> QFont:
    """Set absolute letter-spacing on an existing QFont."""
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def font_report() -> dict[str, object]:
    """Diagnostics for the settings page and ``--headless``."""
    return {
        "bundled": {family: list(styles) for family, styles in load_bundled_fonts().items()},
        "display": display_family(),
        "mono": mono_family(),
        "display_is_bundled": display_family() == DISPLAY_FAMILY,
        "mono_is_bundled": mono_family() == MONO_FAMILY,
    }
