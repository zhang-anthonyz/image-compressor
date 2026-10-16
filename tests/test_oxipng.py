"""oxipng wrapper: real optimisation, graceful degradation, size readouts."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.encoders.oxipng_encoder import OxipngEncoder
from app.core.planner import Effort
from tests.conftest import psnr


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", compress_level=9)
    return buffer.getvalue()


def test_missing_binary_is_reported_not_raised(tmp_path):
    encoder = OxipngEncoder(binary=tmp_path / "does-not-exist.exe")
    assert encoder.available() is False
    assert encoder.optimize(b"\x89PNG\r\n\x1a\n" + b"junk", Effort.BALANCED) is None
    assert encoder.version() == ""


def test_garbage_input_returns_none(tmp_path):
    encoder = OxipngEncoder(binary=tmp_path / "missing.exe")
    assert encoder.optimize(b"", Effort.FAST) is None


@pytest.mark.skipif(not OxipngEncoder().available(), reason="vendor/oxipng.exe not present")
def test_real_optimisation_shrinks_without_changing_pixels():
    image = Image.new("RGB", (200, 200))
    for y in range(200):
        for x in range(200):
            image.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    original = _png_bytes(image)

    encoder = OxipngEncoder()
    optimised = encoder.optimize(original, Effort.BALANCED)

    assert optimised is not None
    assert optimised.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(optimised) < len(original)
    assert psnr(image, Image.open(io.BytesIO(optimised))) == float("inf")


@pytest.mark.skipif(not OxipngEncoder().available(), reason="vendor/oxipng.exe not present")
def test_version_is_reported():
    assert "oxipng" in OxipngEncoder().version().lower()
