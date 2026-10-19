"""Pure UI logic: control linkage and label text, with no Qt imports.

Every rule about "which control is enabled when" lives here so it can be tested
without constructing a window — the widget layer only reads these decisions.
"""
from __future__ import annotations

from ..core import formats
from ..core.formats import FormatSpec
from ..core.planner import (
    DEFAULT_QUALITY,
    QUALITY_PRESETS,
    CompressionPlan,
    MetadataPolicy,
    Mode,
    NamingPolicy,
    png_colors_for_quality,
    quality_label,
)
from ..core.unit_report import dimensions, human_size, saved_percent, scale_target

KEEP_FORMAT_VALUE = "keep"

MODE_LOSSLESS = Mode.LOSSLESS.value
MODE_LOSSY = Mode.LOSSY.value

SCALE_PRESETS: tuple[tuple[str, int], ...] = (
    ("100%", 100),
    ("75%", 75),
    ("50%", 50),
    ("25%", 25),
)

QUALITY_PRESET_OPTIONS: tuple[tuple[str, str], ...] = tuple(
    (str(value), label) for label, value in QUALITY_PRESETS
)


def format_options() -> list[tuple[str, str]]:
    """Target-format combo entries; the first is "keep the original"."""
    options = [(KEEP_FORMAT_VALUE, "保持原格式")]
    options.extend((spec.key, spec.label) for spec in formats.writable_specs())
    return options


def metadata_options() -> list[tuple[str, str]]:
    return [(policy.value, policy.label) for policy in MetadataPolicy]


def naming_options() -> list[tuple[str, str]]:
    return [(policy.value, policy.label) for policy in NamingPolicy]


def collision_options() -> list[tuple[str, str]]:
    from ..core.planner import CollisionPolicy

    return [(policy.value, policy.label) for policy in CollisionPolicy]


def effort_options() -> list[tuple[str, str]]:
    from ..core.planner import Effort

    return [(effort.value, effort.label) for effort in Effort]


def effective_target(source_key: str | None, target_key: str | None) -> FormatSpec | None:
    """The container a plan will actually write for a given source.

    Mirrors ``CompressionPlan.resolved_format`` so the panel can show the truth
    before anything runs.
    """
    if target_key and target_key != KEEP_FORMAT_VALUE:
        return formats.BY_KEY.get(target_key)
    if source_key:
        spec = formats.BY_KEY.get(source_key)
        if spec is None:
            return None
        if spec.can_write:
            return spec
        if spec.key == "heic":
            return formats.JPEG
    return None


def mode_availability(target: FormatSpec | None) -> dict[str, tuple[bool, str]]:
    """Whether each mode can run for ``target``, with the reason when it cannot."""
    if target is None:
        return {MODE_LOSSLESS: (True, ""), MODE_LOSSY: (True, "")}
    return {
        MODE_LOSSLESS: (
            target.can_lossless,
            "" if target.can_lossless else (target.lossless_note or f"{target.label} 不支持无损压缩"),
        ),
        MODE_LOSSY: (
            target.can_lossy,
            "" if target.can_lossy else (target.lossy_note or f"{target.label} 不支持有损压缩"),
        ),
    }


def quality_applies(mode: str, target: FormatSpec | None) -> bool:
    """Quality only means something in a lossy mode with a knob to turn."""
    if mode != MODE_LOSSY or target is None:
        return False
    return target.can_lossy


def quality_hint(target: FormatSpec | None, mode: str, quality: int) -> str:
    """One line describing what the current quality value will do."""
    if target is None:
        return ""
    if mode == MODE_LOSSLESS:
        return target.lossless_note or "无损重压缩：像素与压缩前完全一致"
    if not target.can_lossy:
        return target.lossy_note or f"{target.label} 没有质量参数"
    if target.key == "png":
        return (
            f"调色板量化至 {png_colors_for_quality(quality)} 色 · 画质 {quality_label(quality)}"
            " · 照片建议改用 WebP"
        )
    if target.key == "tiff":
        return "TIFF 使用 deflate 无损压缩"
    return f"质量 {quality}（{quality_label(quality)}）"


def lossless_or_note(target: FormatSpec | None, mode: str) -> str:
    if target is None:
        return ""
    return target.lossless_note if mode == MODE_LOSSLESS else ""


def scale_readout(percent: float, source_size: tuple[int, int] | None) -> str:
    """``(50, (6000, 4000))`` -> ``"→ 3,000 × 2,000"``."""
    if not source_size or source_size[0] == 0:
        return "→ 尺寸未知"
    if percent >= 100:
        return f"→ 保持 {dimensions(*source_size)}"
    return f"→ {dimensions(*scale_target(source_size, percent))}"


def quality_value_from_preset(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def preset_for_quality(quality: int) -> str:
    """Nearest preset value for a quality, or "" when it fits none exactly."""
    for _label, value in QUALITY_PRESETS:
        if value == quality:
            return str(value)
    return ""


def naming_preview(plan: CompressionPlan, source_name: str = "photo.jpg", target: FormatSpec | None = None) -> str:
    """Show the resulting file name so naming rules are never a guess."""
    from pathlib import Path

    from ..core.naming import _apply_naming

    stem = _apply_naming(plan, Path(source_name), 0, 0)
    extension = ".jpg"
    if target is not None:
        for candidate in target.extensions:
            if Path(source_name).suffix.lower() == candidate:
                extension = candidate
                break
        else:
            extension = ".jpg" if target.key == "jpeg" else f".{target.key}"
    return f"{stem}{extension}"


def plan_from_widget_values(values: dict) -> CompressionPlan:
    """Build a plan from a dict of raw control values (also used by tests)."""
    plan = CompressionPlan()
    plan.mode = Mode(values.get("mode", MODE_LOSSY))
    plan.quality = int(values.get("quality", DEFAULT_QUALITY))
    plan.scale_percent = float(values.get("scale_percent", 100))
    target = values.get("target_format", KEEP_FORMAT_VALUE)
    plan.target_format = None if target in ("", None, KEEP_FORMAT_VALUE) else str(target)
    plan.metadata = MetadataPolicy(values.get("metadata", MetadataPolicy.SLIM.value))
    plan.naming = NamingPolicy(values.get("naming", NamingPolicy.SUFFIX.value))
    plan.suffix = str(values.get("suffix", plan.suffix))
    plan.prefix = str(values.get("prefix", plan.prefix))
    plan.template = str(values.get("template", plan.template))
    from ..core.planner import CollisionPolicy, Effort

    plan.collision = CollisionPolicy(values.get("collision", CollisionPolicy.RENAME.value))
    plan.effort = Effort(values.get("effort", Effort.BALANCED.value))
    plan.keep_smaller = bool(values.get("keep_smaller", True))
    plan.inplace = bool(values.get("inplace", False))
    plan.workers = int(values.get("workers", 0) or 0)
    return plan


def summary_line(stats: dict, *, running: bool = False, cancelling: bool = False) -> str:
    """Status-bar sentence for the current queue stats."""
    count = int(stats.get("count", 0))
    if count == 0:
        return "队列为空 · 拖入图片或点击「添加文件」开始"
    parts = [f"{count} 个文件"]
    enabled = int(stats.get("enabled", 0))
    if enabled != count:
        parts.append(f"已选 {enabled}")
    saved = int(stats.get("saved", 0))
    if saved:
        parts.append(
            f"总节省 {human_size(saved)} ({saved_percent(int(stats.get('original', 0)), int(stats.get('new', 0))).lstrip('−')})"
        )
    failures = int(stats.get("failed", 0))
    if failures:
        parts.append(f"{failures} 个失败")
    skipped = int(stats.get("skipped", 0))
    if skipped:
        parts.append(f"{skipped} 个跳过")
    if cancelling:
        parts.append("正在取消")
    elif running:
        parts.append("正在压缩")
    return " · ".join(parts)


# ------------------------------------------------------------------ layout ---
#: Minimum name-column width before the queue table starts scrolling instead of
#: squeezing file names into unreadable slivers.
QUEUE_NAME_MIN_WIDTH = 180

#: The settings rail scales with the window but stays within a readable band.
#: 336 is the measured minimum: the settings card itself needs 318 px, plus the
#: scrollbar gutter, before its right edge would be clipped (see ui_preview).
RAIL_MIN_WIDTH = 336
RAIL_MAX_WIDTH = 456


def rail_width(window_width: int) -> int:
    """Sidebar width for a given window width (proportional, clamped)."""
    return max(RAIL_MIN_WIDTH, min(RAIL_MAX_WIDTH, round(window_width * 0.28)))


def queue_name_width(viewport_width: int, fixed_widths: int) -> int:
    """Width for the stretch column; overflowing the viewport is intentional.

    When the result exceeds the viewport the table must show a horizontal
    scrollbar rather than clipping information, which is why the minimum width
    is a hard floor instead of shrinking to zero.
    """
    return max(QUEUE_NAME_MIN_WIDTH, int(viewport_width) - int(fixed_widths) - 2)
