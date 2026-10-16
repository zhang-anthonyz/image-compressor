"""Optional codec registration.

Pillow handles everything PixelPress needs except HEIC/HEIF, which comes from
``pillow-heif``. That package only participates once ``register_heif_opener()``
has been called, and forgetting the call is invisible in source mode (the import
succeeds) while the feature is silently absent — the packaged build reported
"HEIC 不可用" with the DLLs sitting right there in the bundle.

Registration is therefore attempted at package import time.
"""
from __future__ import annotations

from PIL import Image

_registration: dict[str, bool] | None = None


def enable_optional_codecs() -> dict[str, bool]:
    """Register optional decoders once. Returns what ended up available."""
    global _registration
    if _registration is not None:
        return _registration

    heif = False
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        heif = "HEIF" in Image.OPEN or "HEIC" in Image.OPEN
    except Exception:
        # A missing or broken optional plugin must never stop the app.
        heif = False

    _registration = {"heif": heif}
    return _registration


def heif_available() -> bool:
    """Whether HEIC/HEIF decoding is registered and usable."""
    return enable_optional_codecs().get("heif", False)


def codec_report() -> dict[str, object]:
    """Availability of optional and core codecs, for the UI and self-check."""
    from PIL import features

    return {
        "heif": heif_available(),
        "webp": features.check("webp"),
        "avif": features.check("avif"),
        "jpg": features.check("jpg"),
        "zlib": features.check("zlib"),
        "libtiff": features.check("libtiff"),
    }
