"""Shared fixtures: real encoded images with the awkward properties."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _gradient_photo(size=(320, 240)) -> Image.Image:
    """Smooth gradient + grain: the case where lossless PNG is weak."""
    import math

    width, height = size
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            r = int(120 + 90 * math.sin(x / 40.0) * math.cos(y / 55.0))
            g = int(110 + 70 * math.sin((x + y) / 32.0))
            b = int(100 + 80 * math.cos((x - y) / 45.0))
            pixels[x, y] = (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
            )
    noise = Image.effect_noise(size, 24).convert("L")
    return Image.blend(image, Image.merge("RGB", (noise, noise, noise)), 0.10)


def _flat_graphic(size=(300, 200)) -> Image.Image:
    """Flat fills and hard edges: the case where palette quantizing wins."""
    image = Image.new("RGB", size, (246, 247, 249))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, size[0], 40], fill=(32, 38, 52))
    draw.rectangle([20, 60, 140, 170], fill=(255, 255, 255), outline=(210, 216, 226))
    draw.rectangle([160, 60, 280, 170], fill=(37, 99, 235))
    for i in range(6):
        draw.rectangle([30, 75 + i * 14, 120 + (i * 11) % 40, 81 + i * 14], fill=(70, 80, 100))
    return image


@pytest.fixture
def photo_jpeg(tmp_path: Path) -> Path:
    path = tmp_path / "photo.jpg"
    _gradient_photo().save(path, "JPEG", quality=92, subsampling=0)
    return path


@pytest.fixture
def photo_png(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    _gradient_photo().save(path, "PNG", compress_level=9)
    return path


@pytest.fixture
def graphic_png(tmp_path: Path) -> Path:
    path = tmp_path / "graphic.png"
    _flat_graphic().save(path, "PNG", compress_level=9)
    return path


@pytest.fixture
def alpha_png(tmp_path: Path) -> Path:
    """Transparent border with an opaque centre — catches alpha flattening."""
    image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([20, 20, 100, 100], fill=(210, 59, 22, 255))
    path = tmp_path / "alpha.png"
    image.save(path, "PNG")
    return path


@pytest.fixture
def oriented_jpeg(tmp_path: Path) -> Path:
    """JPEG tagged Orientation=6 (rotate 90) so baking is observable."""
    image = _flat_graphic((240, 120))
    exif = Image.Exif()
    exif[274] = 6
    path = tmp_path / "oriented.jpg"
    image.save(path, "JPEG", quality=90, exif=exif.tobytes())
    return path


@pytest.fixture
def icc_png(tmp_path: Path) -> Path:
    """PNG carrying an ICC profile, to prove colour config survives."""
    image = _flat_graphic((80, 60))
    path = tmp_path / "icc.png"
    image.save(path, "PNG", icc_profile=_synthetic_icc())
    return path


@pytest.fixture
def animated_gif(tmp_path: Path) -> Path:
    frames = [Image.new("RGB", (60, 40), color) for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    path = tmp_path / "anim.gif"
    frames[0].save(path, "GIF", save_all=True, append_images=frames[1:], duration=120, loop=0)
    return path


@pytest.fixture
def corrupt_file(tmp_path: Path) -> Path:
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image at all" * 10)
    return path


def _synthetic_icc() -> bytes:
    """Minimal but structurally valid ICC profile (sRGB-ish gray)."""
    profile = bytearray(128)
    profile[0:4] = (132).to_bytes(4, "big")  # declared size
    profile[4:8] = b"none"
    profile[8:12] = (0x04300000).to_bytes(4, "big")  # version 4.3
    profile[12:16] = b"mntr"
    profile[16:20] = b"RGB "
    profile[20:24] = b"XYZ "
    profile[36:40] = b"acsp"
    return bytes(profile)


def psnr(a: Image.Image, b: Image.Image) -> float:
    """PSNR over RGB; ``inf`` when the images are pixel-identical."""
    import math

    import numpy as np

    if a.size != b.size:
        return float("-inf")
    x = np.asarray(a.convert("RGB"), dtype=np.float64)
    y = np.asarray(b.convert("RGB"), dtype=np.float64)
    mse = float(((x - y) ** 2).mean())
    return float("inf") if mse == 0 else 10.0 * math.log10(255.0**2 / mse)


def reopen(path: Path) -> Image.Image:
    image = Image.open(io.BytesIO(Path(path).read_bytes()))
    image.load()
    return image
