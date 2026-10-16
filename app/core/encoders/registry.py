"""Encoder selection: Pillow always, oxipng additionally for PNG.

The registry is the single place that knows which backends exist, so the UI can
report "oxipng + Pillow 12.3" and the pipeline can stay backend-agnostic.
"""
from __future__ import annotations

from PIL import Image

from .base import EncodeRequest, EncodeResult
from .oxipng_encoder import OxipngEncoder
from .pillow_encoder import PillowEncoder

_pillow = PillowEncoder()
_oxipng = OxipngEncoder()


def pillow_encoder() -> PillowEncoder:
    return _pillow


def oxipng_encoder() -> OxipngEncoder:
    return _oxipng


def oxipng_available() -> bool:
    return _oxipng.available()


def engine_badge() -> str:
    """Short engine description for the header chip."""
    pillow_version = getattr(Image, "__version__", "?")
    if _oxipng.available():
        return f"oxipng · Pillow {pillow_version}"
    return f"Pillow {pillow_version}（仅内置编码器）"


def engine_report() -> dict:
    """Structured engine state for the settings page and ``--headless``."""
    return {
        "pillow": getattr(Image, "__version__", "?"),
        "oxipng": _oxipng.version(),
        "oxipng_available": _oxipng.available(),
        "oxipng_path": str(_oxipng.binary),
        "heif_available": heif_available(),
    }


def heif_available() -> bool:
    """Whether HEIC/HEIF decoding was registered successfully."""
    from ..imaging import heif_available as _heif

    return _heif()


def encode(request: EncodeRequest) -> EncodeResult:
    """Encode ``request`` with the best backend available for its target.

    PNG output gets a second pass through oxipng (which is lossless for both
    our lossless and quantized results); every other format is Pillow only.
    """
    result = _pillow.encode(request)

    if request.target.key == "png" and _oxipng.available():
        optimised = _oxipng.optimize(result.data, request.effort)
        if optimised is not None:
            saved = len(result.data) - len(optimised)
            result = EncodeResult(
                data=optimised,
                encoder="oxipng",
                notes=result.notes + [f"oxipng 再压缩省 {saved / 1024:.0f} KB"],
            )
    return result
