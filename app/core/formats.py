"""Format registry: what we can read, what we can write, and each format's
real capabilities.

The capability flags are not aspirational — every ``can_lossless`` /
``can_lossy`` value below reflects a measurement from
``scripts/benchmark_codecs.py`` on Pillow 12.3 (see docs/技术方案.md §4).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FormatSpec:
    """One image container and what it can actually do."""

    key: str
    label: str
    pillow_name: str
    extensions: tuple[str, ...]
    can_lossless: bool
    can_lossy: bool
    supports_alpha: bool
    supports_icc: bool
    supports_exif: bool
    can_write: bool
    #: Shown in the UI when a mode is unavailable, so the reason is never a
    #: mystery (e.g. AVIF has no lossless path in Pillow).
    lossless_note: str = ""
    lossy_note: str = ""
    #: Some formats are input-only (HEIC: decode-only, no encoder shipped).
    read_only_note: str = ""


JPEG = FormatSpec(
    key="jpeg",
    label="JPEG",
    pillow_name="JPEG",
    extensions=(".jpg", ".jpeg", ".jpe", ".jfif"),
    can_lossless=True,
    can_lossy=True,
    supports_alpha=False,
    supports_icc=True,
    supports_exif=True,
    can_write=True,
    lossless_note="视觉无损：沿用原量化表，仅重排熵编码与渐进式（实测 79.7 dB，非逐位相同）",
)
PNG = FormatSpec(
    key="png",
    label="PNG",
    pillow_name="PNG",
    extensions=(".png",),
    can_lossless=True,
    can_lossy=True,
    supports_alpha=True,
    supports_icc=True,
    supports_exif=True,
    can_write=True,
    lossy_note="调色板量化（256→16 色）；纯色/图形类图片常可达成逐位无损",
)
WEBP = FormatSpec(
    key="webp",
    label="WebP",
    pillow_name="WEBP",
    extensions=(".webp",),
    can_lossless=True,
    can_lossy=True,
    supports_alpha=True,
    supports_icc=True,
    supports_exif=True,
    can_write=True,
    lossless_note="真无损；实测图形类比 PNG 无损再小约 90%",
)
AVIF = FormatSpec(
    key="avif",
    label="AVIF",
    pillow_name="AVIF",
    extensions=(".avif",),
    can_lossless=False,
    can_lossy=True,
    supports_alpha=True,
    supports_icc=True,
    supports_exif=True,
    can_write=True,
    lossless_note="Pillow 12 未暴露 AVIF 无损编码，仅支持有损",
)
TIFF = FormatSpec(
    key="tiff",
    label="TIFF",
    pillow_name="TIFF",
    extensions=(".tif", ".tiff"),
    can_lossless=True,
    can_lossy=False,
    supports_alpha=True,
    supports_icc=True,
    supports_exif=True,
    can_write=True,
    lossy_note="TIFF 在本工具中仅作无损归档（deflate / LZW）",
)
GIF = FormatSpec(
    key="gif",
    label="GIF",
    pillow_name="GIF",
    extensions=(".gif",),
    can_lossless=False,
    can_lossy=True,
    supports_alpha=True,
    supports_icc=False,
    supports_exif=False,
    can_write=True,
    lossless_note="GIF 无损重编码等同于调色板重排，无独立无损模式",
)
BMP = FormatSpec(
    key="bmp",
    label="BMP",
    pillow_name="BMP",
    extensions=(".bmp", ".dib"),
    can_lossless=True,
    can_lossy=False,
    supports_alpha=False,
    supports_icc=False,
    supports_exif=False,
    can_write=True,
    lossy_note="BMP 不支持压缩，仅作兼容性输出",
)
ICO = FormatSpec(
    key="ico",
    label="ICON",
    pillow_name="ICO",
    extensions=(".ico",),
    can_lossless=True,
    can_lossy=False,
    supports_alpha=True,
    supports_icc=False,
    supports_exif=False,
    can_write=True,
    lossy_note="图标格式无质量参数",
)
TGA = FormatSpec(
    key="tga",
    label="TGA",
    pillow_name="TGA",
    extensions=(".tga", ".icb", ".vda", ".vst"),
    can_lossless=True,
    can_lossy=False,
    supports_alpha=True,
    supports_icc=False,
    supports_exif=False,
    can_write=True,
    lossy_note="TGA 无压缩质量参数",
)
PPM = FormatSpec(
    key="ppm",
    label="PPM",
    pillow_name="PPM",
    extensions=(".ppm", ".pgm", ".pbm", ".pnm", ".pfm"),
    can_lossless=True,
    can_lossy=False,
    supports_alpha=False,
    supports_icc=False,
    supports_exif=False,
    can_write=True,
    lossy_note="PPM 系列为无压缩位图",
)
HEIC = FormatSpec(
    key="heic",
    label="HEIC",
    pillow_name="HEIF",
    extensions=(".heic", ".heif", ".hif"),
    can_lossless=True,
    can_lossy=True,
    supports_alpha=True,
    supports_icc=True,
    supports_exif=True,
    can_write=False,
    read_only_note="HEIC 仅支持读取：写回需额外授权考量，输出将落到其它格式",
)

ALL_FORMATS: tuple[FormatSpec, ...] = (
    JPEG, PNG, WEBP, AVIF, TIFF, GIF, BMP, ICO, TGA, PPM, HEIC,
)

BY_KEY: dict[str, FormatSpec] = {f.key: f for f in ALL_FORMATS}

_BY_EXT: dict[str, FormatSpec] = {}
for _spec in ALL_FORMATS:
    for _ext in _spec.extensions:
        _BY_EXT.setdefault(_ext, _spec)

#: Formats offered in the "target format" picker, in this order. Reading is
#: broader than writing on purpose: ICO/TGA/PPM are decodable and can round-trip
#: via "keep original format", but they are not useful compression targets.
WRITABLE_KEYS: tuple[str, ...] = ("jpeg", "png", "webp", "avif", "tiff", "gif", "bmp")

#: File-dialog filter, derived from the registry so it can never drift.
DIALOG_EXTENSIONS: tuple[str, ...] = tuple(
    sorted({ext for spec in ALL_FORMATS for ext in spec.extensions})
)


def detect(path: str | Path) -> FormatSpec | None:
    """Registry lookup by file extension (case-insensitive)."""
    return _BY_EXT.get(Path(path).suffix.lower())


def spec_for_key(key: str) -> FormatSpec:
    """Lookup by canonical key. Raises ``KeyError`` for unknown keys."""
    return BY_KEY[key]


def spec_for_pillow_name(name: str | None) -> FormatSpec | None:
    """Map a Pillow format name (e.g. "MPO" / "WEBP") to a registry entry."""
    if not name:
        return None
    wanted = name.upper()
    aliases = {"MPO": "JPEG", "JPG": "JPEG", "HEIF": "HEIF", "TIF": "TIFF"}
    wanted = aliases.get(wanted, wanted)
    for spec in ALL_FORMATS:
        if spec.pillow_name == wanted:
            return spec
    return None


def writable_specs() -> tuple[FormatSpec, ...]:
    """Formats that can appear as a compression target."""
    return tuple(BY_KEY[k] for k in WRITABLE_KEYS)


def available_modes(spec: FormatSpec) -> tuple[bool, bool]:
    """``(lossless_ok, lossy_ok)`` for a format."""
    return spec.can_lossless, spec.can_lossy


def mode_note(spec: FormatSpec, mode: str) -> str:
    """Human explanation for a mode on a format (empty when unremarkable)."""
    if mode == "lossless":
        return spec.lossless_note
    return spec.lossy_note
