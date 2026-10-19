"""Lossy-output regressions: palette depth, alpha preservation, real PSNR.

These are the failure modes users actually see, not just an encoder returning
``done``:
* RGBA PNGs collapsed to ~60 colours because FASTOCTREE spent the palette on
  alpha, producing hard bands and a visible colour shift;
* the "high" preset (82) only asked for 199 palette entries on RGB PNGs;
* JPEG q82 used 4:2:0, which makes coloured edges on UI screenshots bleed.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

from app.core import pipeline
from app.core.planner import CompressionPlan, Effort, MetadataPolicy, Mode, jpeg_subsampling


def _smooth_rgba(path: Path, size=(240, 180)) -> None:
    width, height = size
    image = Image.new("RGBA", size)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                int(40 + 200 * x / (width - 1)),
                int(30 + 190 * y / (height - 1)),
                int(220 - 120 * x / (width - 1)),
                int(255 * (1 - y / (height - 1))),
            )
    image.save(path, "PNG")


def _smooth_rgb(path: Path, size=(320, 240)) -> None:
    width, height = size
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                int(30 + 200 * x / (width - 1)),
                int(40 + 170 * y / (height - 1)),
                int(230 - 150 * x / (width - 1)),
            )
    image.save(path, "PNG")


def _plan(target: str, quality: int = 82) -> CompressionPlan:
    return CompressionPlan(
        mode=Mode.LOSSY,
        quality=quality,
        target_format=target,
        metadata=MetadataPolicy.SLIM,
        effort=Effort.BALANCED,
        keep_smaller=False,
    )


def _psnr_over_grey(source: Image.Image, output: Image.Image) -> float:
    a = np.asarray(source.convert("RGBA"), dtype=np.float32)
    b = np.asarray(output.convert("RGBA"), dtype=np.float32)
    background = np.array([128, 128, 128], dtype=np.float32)
    av = a[..., :3] * (a[..., 3:4] / 255.0) + background * (1 - a[..., 3:4] / 255.0)
    bv = b[..., :3] * (b[..., 3:4] / 255.0) + background * (1 - b[..., 3:4] / 255.0)
    mse = float(((av - bv) ** 2).mean())
    return float("inf") if mse == 0 else 10.0 * math.log10(255.0**2 / mse)


def test_lossy_rgba_png_keeps_alpha_and_full_colour_palette(tmp_path: Path):
    source_path = tmp_path / "alpha_gradient.png"
    out_path = tmp_path / "alpha_gradient_min.png"
    _smooth_rgba(source_path)

    result = pipeline.compress_file(source_path, _plan("png"), out_path)
    assert result.status == pipeline.STATUS_DONE, result.message

    with Image.open(source_path) as source, Image.open(out_path) as output:
        source_alpha = np.asarray(source.convert("RGBA").getchannel("A"))
        output_alpha = np.asarray(output.convert("RGBA").getchannel("A"))
        assert np.array_equal(source_alpha, output_alpha)
        unique = len(output.convert("RGB").getcolors(maxcolors=10_000_000) or [])
        assert unique >= 200, f"only {unique} colours survived; alpha is eating the palette"
        assert _psnr_over_grey(source, output) > 40.0


def test_lossy_rgb_png_high_preset_uses_the_full_palette(tmp_path: Path):
    source_path = tmp_path / "photo_gradient.png"
    out_path = tmp_path / "photo_gradient_min.png"
    _smooth_rgb(source_path)

    result = pipeline.compress_file(source_path, _plan("png", 82), out_path)
    assert result.status == pipeline.STATUS_DONE, result.message

    with Image.open(out_path) as output:
        assert output.mode == "P"
        unique = len(output.convert("RGB").getcolors(maxcolors=10_000_000) or [])
        assert unique >= 240, f"q82 only produced {unique} colours"


def test_jpeg_high_preset_keeps_full_chroma():
    assert jpeg_subsampling(82) == 0
    assert jpeg_subsampling(79) == 2
