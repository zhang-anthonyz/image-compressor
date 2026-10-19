"""Compression planning: turns UI intent into concrete encoder parameters.

This module owns every "what does this setting actually mean" decision, so the
UI never encodes policy and the pipeline never reads widgets.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from . import formats
from .formats import FormatSpec


class Mode(str, Enum):
    LOSSLESS = "lossless"
    LOSSY = "lossy"


class Effort(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    MAX = "max"

    @property
    def label(self) -> str:
        return {"fast": "快速", "balanced": "均衡", "max": "极致"}[self.value]


class MetadataPolicy(str, Enum):
    FULL = "full"
    SLIM = "slim"
    STRIP = "strip"

    @property
    def label(self) -> str:
        return {"full": "全部保留", "slim": "精简（保留色彩配置）", "strip": "全部剥离"}[self.value]


class NamingPolicy(str, Enum):
    SUFFIX = "suffix"
    PREFIX = "prefix"
    TEMPLATE = "template"

    @property
    def label(self) -> str:
        return {"suffix": "文件名 + 后缀", "prefix": "前缀 + 文件名", "template": "自定义模板"}[self.value]


class CollisionPolicy(str, Enum):
    RENAME = "rename"
    SKIP = "skip"
    OVERWRITE = "overwrite"

    @property
    def label(self) -> str:
        return {"rename": "自动重命名", "skip": "跳过已存在", "overwrite": "覆盖同名文件"}[self.value]


#: Quality presets, calibrated against the measured JPEG curve
#: (q92 -> 41.4 dB / q85 -> 40.3 dB / q75 -> 39.6 dB on the photo fixture).
QUALITY_PRESETS: tuple[tuple[str, int], ...] = (
    ("低", 40),
    ("中", 65),
    ("高", 82),
    ("极高", 92),
)
DEFAULT_QUALITY = 82

#: Palette depth for lossy PNG, by quality. 16 colours at q=1, 256 at q=100;
#: the curve is slightly convex so mid-range quality still keeps rich colour.
_PNG_MIN_COLORS = 16
_PNG_MAX_COLORS = 256


def png_colors_for_quality(quality: int) -> int:
    """Palette size implied by a quality value (lossy PNG).

    The high preset (82) must land on the full 256-colour palette; the old
    curve topped out at 199 there, which posterised smooth photos. Below that
    the curve still falls away quickly so low quality stays genuinely small.
    """
    q = max(1, min(100, int(quality)))
    span = _PNG_MAX_COLORS - _PNG_MIN_COLORS
    ratio = min(1.0, ((q - 1) / 80.0) ** 1.2)
    return int(round(_PNG_MIN_COLORS + span * ratio))


def quality_label(quality: int) -> str:
    """Qualitative band for the quality slider readout."""
    if quality >= 90:
        return "极高"
    if quality >= 75:
        return "高"
    if quality >= 55:
        return "中"
    if quality >= 30:
        return "偏低"
    return "低"


def jpeg_subsampling(quality: int) -> int:
    """4:4:4 from the high preset up, 4:2:0 below it.

    Chroma subsampling is what makes coloured edges on screenshots bleed; the
    high preset is the one users pick when they care about that, so it gets
    full chroma. The file-size cost is modest (measured q82: 22 -> 35 KB on the
    UI fixture) and the PSNR gain on graphics is ~4 dB.
    """
    return 0 if quality >= 80 else 2


@dataclass(frozen=True)
class PlanIssue:
    """Why a mode/format combination cannot run, in user-facing language."""

    code: str
    message: str


@dataclass
class CompressionPlan:
    """Everything the engine needs to compress one file."""

    mode: Mode = Mode.LOSSY
    quality: int = DEFAULT_QUALITY
    scale_percent: float = 100.0
    #: ``None`` keeps the source container; otherwise a key from formats.BY_KEY.
    target_format: str | None = None
    effort: Effort = Effort.BALANCED
    metadata: MetadataPolicy = MetadataPolicy.SLIM
    #: Write the original bytes instead when compression made the file bigger.
    keep_smaller: bool = True
    #: Colour composited under transparent pixels when the target cannot hold
    #: an alpha channel.
    background: tuple[int, int, int] = (255, 255, 255)

    naming: NamingPolicy = NamingPolicy.SUFFIX
    suffix: str = "_min"
    prefix: str = "min_"
    template: str = "{name}_min"
    collision: CollisionPolicy = CollisionPolicy.RENAME
    #: Explicit output directory; ``None`` means "beside the source" (or the
    #: folder chosen in the UI, resolved by naming.resolve_output).
    out_dir: str | None = None
    #: Overwrite the source file in place (explicit opt-in, never a default).
    inplace: bool = False

    #: 0 = auto (min(4, cpu_count)).
    workers: int = 0

    def copy(self, **changes) -> "CompressionPlan":
        return replace(self, **changes)

    # ------------------------------------------------------------ resolution
    def resolved_format(self, source: FormatSpec | None) -> FormatSpec | None:
        """The container this plan will write for a given source format."""
        if self.target_format:
            return formats.BY_KEY.get(self.target_format)
        if source is None:
            return None
        if source.can_write:
            return source
        # Read-only container (HEIC, …): default to JPEG, which is what a photo
        # becomes almost every time. The pipeline re-checks the decoded image
        # and switches to PNG when the picture actually carries transparency.
        if source.key == "heic":
            return formats.JPEG
        return None

    def issue_for(self, target: FormatSpec | None) -> PlanIssue | None:
        """Blocking problem (if any) for this plan against a target format."""
        if target is None:
            return PlanIssue("no-format", "无法识别的图片格式，已跳过")
        if self.target_format and not target.can_write:
            return PlanIssue("read-only", target.read_only_note or f"{target.label} 不支持写出")
        if self.mode is Mode.LOSSLESS and not target.can_lossless:
            return PlanIssue(
                "no-lossless",
                target.lossless_note or f"{target.label} 不支持无损压缩",
            )
        if self.mode is Mode.LOSSY and not target.can_lossy:
            return PlanIssue(
                "no-lossy",
                target.lossy_note or f"{target.label} 不支持有损压缩",
            )
        if self.mode is Mode.LOSSLESS and target.key == "jpeg":
            # Handled at run time instead: a JPEG source keeps its own tables,
            # a non-JPEG source cannot use "keep" at all.
            return None
        return None

    def is_compatible(self, target: FormatSpec | None) -> bool:
        return self.issue_for(target) is None

    def effective_mode(self, target: FormatSpec) -> Mode:
        """Mode actually used for ``target``, degrading gracefully.

        Only reached for plans the UI considered valid; the fallback keeps a
        stale saved setting from hard-failing a whole batch.
        """
        if self.mode is Mode.LOSSLESS and not target.can_lossless:
            return Mode.LOSSY
        if self.mode is Mode.LOSSY and not target.can_lossy:
            return Mode.LOSSLESS
        return self.mode

    # -------------------------------------------------------- encoder params
    def pillow_params(self, target: FormatSpec, source_pillow_format: str | None) -> dict:
        """Keyword arguments for ``PIL.Image.save`` for this plan + target."""
        mode = self.effective_mode(target)
        quality = max(1, min(100, int(self.quality)))

        if target.key == "jpeg":
            if mode is Mode.LOSSLESS:
                if (source_pillow_format or "").upper() in ("JPEG", "MPO"):
                    return {
                        "quality": "keep",
                        "optimize": True,
                        "progressive": True,
                    }
                # Source was not JPEG: "keep" is impossible, so fall back to a
                # high-fidelity re-encode and say so in the result note.
                return {
                    "quality": 95,
                    "subsampling": 0,
                    "optimize": True,
                    "progressive": True,
                }
            return {
                "quality": quality,
                "subsampling": jpeg_subsampling(quality),
                "optimize": True,
                "progressive": True,
            }

        if target.key == "png":
            if mode is Mode.LOSSLESS:
                return {"compress_level": self._png_level()}
            return {"compress_level": self._png_level(), "palette_colors": png_colors_for_quality(quality)}

        if target.key == "webp":
            if mode is Mode.LOSSLESS:
                return {"lossless": True, "method": self._webp_method(), "quality": 100}
            return {"quality": quality, "method": self._webp_method()}

        if target.key == "avif":
            return {"quality": quality, "speed": self._avif_speed()}

        if target.key == "tiff":
            return {"compression": "tiff_deflate"}

        if target.key == "gif":
            return {"optimize": True}

        return {}

    def _png_level(self) -> int:
        return {Effort.FAST: 6, Effort.BALANCED: 9, Effort.MAX: 9}[self.effort]

    def _webp_method(self) -> int:
        return {Effort.FAST: 4, Effort.BALANCED: 6, Effort.MAX: 6}[self.effort]

    def _avif_speed(self) -> int:
        return {Effort.FAST: 8, Effort.BALANCED: 6, Effort.MAX: 4}[self.effort]

    def oxipng_args(self) -> list[str]:
        """Extra oxipng arguments for this plan's effort level."""
        level = {Effort.FAST: "2", Effort.BALANCED: "4", Effort.MAX: "6"}[self.effort]
        return ["--opt", level]

    # -------------------------------------------------------------- readouts
    def summary(self) -> str:
        """One-line human summary (status bar / logs / headless output)."""
        parts = [("无损" if self.mode is Mode.LOSSLESS else f"有损 q{self.quality}")]
        if self.scale_percent != 100.0:
            parts.append(f"缩放 {self.scale_percent:g}%")
        target = formats.BY_KEY.get(self.target_format) if self.target_format else None
        parts.append(f"输出 {target.label}" if target else "保持原格式")
        parts.append(f"力度{self.effort.label}")
        return " · ".join(parts)


def default_plan() -> CompressionPlan:
    return CompressionPlan()


def clamp_quality(value: int) -> int:
    return max(1, min(100, int(value)))


def clamp_scale(value: float) -> float:
    return max(5.0, min(100.0, float(value)))


def resolve_workers(requested: int, file_count: int) -> int:
    """Worker count for a batch: honour the request, else min(4, cpus)."""
    import os

    if requested and requested > 0:
        workers = requested
    else:
        workers = min(4, os.cpu_count() or 1)
    return max(1, min(workers, max(1, file_count)))
