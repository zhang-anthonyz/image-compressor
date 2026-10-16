"""Human-readable formatting for sizes, ratios and dimensions.

Kept separate from the UI so both the status bar and the ``--headless``
self-check report the same numbers the same way.
"""
from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_size(num_bytes: int | float | None) -> str:
    """``1_048_576`` -> ``"1.0 MB"``.

    Binary units, one decimal below 100 and none above it — the convention every
    file manager uses, and the one that keeps a column of sizes scannable.
    """
    if num_bytes is None:
        return "—"
    value = float(num_bytes)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value < 1024:
        return f"{sign}{int(value)} B"
    for unit in _UNITS[1:]:
        value /= 1024.0
        if value < 1024.0 or unit == _UNITS[-1]:
            decimals = 0 if value >= 100 else 1
            return f"{sign}{value:.{decimals}f} {unit}"
    return f"{sign}{value:.1f} TB"


def size_delta(original: int | None, compressed: int | None) -> str:
    """``(4_400_000, 1_100_000)`` -> ``"−3.15 MB"`` (a real minus sign)."""
    if not original or compressed is None:
        return "—"
    saved = original - compressed
    return f"{'−' if saved >= 0 else '+'}{human_size(abs(saved))}"


def saved_percent(original: int | None, compressed: int | None) -> str:
    """``(4_400_000, 1_100_000)`` -> ``"−75.0%"``."""
    if not original or compressed is None or original <= 0:
        return "—"
    return f"{'−' if compressed <= original else '+'}{abs(1 - compressed / original) * 100:.1f}%"


def saved_ratio(original: int | None, compressed: int | None) -> float:
    """Fraction saved in ``[0, 1]``; 0 when there is nothing to compare."""
    if not original or compressed is None or original <= 0:
        return 0.0
    return max(0.0, min(1.0, 1 - compressed / original))


def dimensions(width: int | None, height: int | None) -> str:
    """``(6000, 4000)`` -> ``"6000 × 4000"``."""
    if not width or not height:
        return "—"
    return f"{width:,} × {height:,}"


def scale_target(size: tuple[int, int], percent: float) -> tuple[int, int]:
    """Target pixel size for a percentage scale, aspect ratio preserved.

    Both axes are rounded but never below 1 px, and never above the source
    (upscaling is not what a compressor is for).
    """
    width, height = size
    factor = max(0.0, percent) / 100.0
    if factor >= 1.0:
        return width, height
    return max(1, round(width * factor)), max(1, round(height * factor))


def duration(seconds: float | None) -> str:
    """``12.44`` -> ``"12.4 s"``; ``95`` -> ``"1 分 35 秒"``."""
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes} 分 {rest} 秒"
