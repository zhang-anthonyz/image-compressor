"""Codec/quality capability benchmark for the image-compressor design.

Answers, with measurements rather than assumptions:

1. Which Pillow-native encoders actually compress well, per format and mode.
2. What "lossless" can mean for each container (and where it cannot exist).
3. What quality level costs in bytes vs. fidelity (PSNR / SSIM-ish).
4. Whether pure-Pillow output is competitive enough to skip vendored
   binaries (pngquant / oxipng / mozjpeg) that would add bundle size and
   license obligations.

Run:  python scripts/benchmark_codecs.py [--out benchmarks/codecs.md]
"""
from __future__ import annotations

import argparse
import io
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None


# --------------------------------------------------------------- fixtures ---
def photo_like(size=(1600, 1200)) -> Image.Image:
    """Smooth gradients + fine grain + mild blur: the hard case for lossless
    PNG, and the normal case for a camera JPEG."""
    w, h = size
    base = Image.new("RGB", size)
    px = base.load()
    for y in range(h):
        for x in range(0, w, 1):
            r = int(120 + 90 * math.sin(x / 190.0) * math.cos(y / 260.0))
            g = int(110 + 70 * math.sin((x + y) / 150.0))
            b = int(100 + 80 * math.cos((x - y) / 210.0))
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    base = base.filter(ImageFilter.GaussianBlur(1.2))
    # Deterministic grain via a noise image blended in.
    noise = Image.effect_noise(size, 26).convert("L")
    base = Image.blend(base, Image.merge("RGB", (noise, noise, noise)), 0.10)
    return base


def screenshot_like(size=(1400, 900)) -> Image.Image:
    """Flat fills, hard edges, dark text: the normal case for UI captures and
    the best case for palette quantization."""
    img = Image.new("RGB", size, (246, 247, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size[0], 64], fill=(32, 38, 52))
    d.rectangle([40, 100, 560, 460], fill=(255, 255, 255), outline=(210, 216, 226))
    d.rectangle([600, 100, 1120, 460], fill=(240, 244, 250), outline=(210, 216, 226))
    d.rectangle([1160, 100, 1360, 460], fill=(37, 99, 235))
    for i in range(14):  # text-like bars
        d.rectangle([70, 140 + i * 22, 300 + (i * 37) % 200, 148 + i * 22], fill=(70, 80, 100))
    for i in range(7):
        d.rectangle([630, 130 + i * 44, 1080, 160 + i * 44], fill=(28, 34, 48))
    return img


FIXTURES = {"photo": photo_like, "screenshot": screenshot_like}


# ---------------------------------------------------------------- metrics ---
def psnr(a: Image.Image, b: Image.Image) -> float:
    """PSNR in dB over RGB. >42 dB is usually visually transparent."""
    import numpy as np

    x = np.asarray(a.convert("RGB"), dtype=np.float64)
    y = np.asarray(b.convert("RGB"), dtype=np.float64)
    if x.shape != y.shape:
        return float("nan")
    mse = float(((x - y) ** 2).mean())
    return float("inf") if mse == 0 else 10.0 * math.log10(255.0**2 / mse)


def run(encode, img, fmt, **kw):
    """Encode, time it, decode back, measure. Returns (bytes, ms, psnr, error)."""
    buf = io.BytesIO()
    t0 = time.perf_counter()
    try:
        encode(buf, fmt, **kw)
    except Exception as exc:  # capability we do not have — record, don't crash
        return None, 0.0, float("nan"), f"{type(exc).__name__}: {exc}"
    ms = (time.perf_counter() - t0) * 1000.0
    size = buf.tell()
    try:
        back = Image.open(io.BytesIO(buf.getvalue()))
        back.load()
        score = psnr(img, back)
    except Exception as exc:
        score = float("nan")
    return size, ms, score, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="write a markdown table here")
    args = ap.parse_args()

    rows: list[tuple] = []
    for name, factory in FIXTURES.items():
        img = factory()
        # A reference JPEG as the "original" for a photo-like source.
        raw = {"png9": None}
        buf = io.BytesIO()
        img.save(buf, "PNG", compress_level=9, optimize=False)
        raw["png9"] = buf.tell()
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=92, subsampling=0)
        raw["jpg92"] = buf.tell()
        print(f"\n=== {name} {img.size} — reference PNG(9)={raw['png9']:,}B  JPEG(q92,4:4:4)={raw['jpg92']:,}B")

        cases = [
            ("PNG  lossless  cz=9 optimize", "PNG", dict(compress_level=9, optimize=True)),
            ("PNG  lossless  optimize+dpi", "PNG", dict(compress_level=9, optimize=True, dpi=(96, 96))),
            ("PNG  lossy q=100 (quantize 256 median)", "PNG", dict(quantize=(256, "mediancut"))),
            ("PNG  lossy q=100 (quantize 256 octree)", "PNG", dict(quantize=(256, "fastoctree"))),
            ("PNG  lossy q=100 (quantize 128 median)", "PNG", dict(quantize=(128, "mediancut"))),
            ("PNG  lossy q=100 (quantize  64 median)", "PNG", dict(quantize=(64, "mediancut"))),
            ("JPEG q=100 sub=0 optimize", "JPEG", dict(quality=100, subsampling=0, optimize=True, progressive=True)),
            ("JPEG q=  92 sub=0 optimize", "JPEG", dict(quality=92, subsampling=0, optimize=True, progressive=True)),
            ("JPEG q=  85 sub=0 optimize", "JPEG", dict(quality=85, subsampling=0, optimize=True, progressive=True)),
            ("JPEG q=  85 sub=2 optimize", "JPEG", dict(quality=85, subsampling=2, optimize=True, progressive=True)),
            ("JPEG q=  75 sub=2 optimize", "JPEG", dict(quality=75, subsampling=2, optimize=True, progressive=True)),
            ("JPEG q=  60 sub=2 optimize", "JPEG", dict(quality=60, subsampling=2, optimize=True, progressive=True)),
            ("JPEG q=  40 sub=2 optimize", "JPEG", dict(quality=40, subsampling=2, optimize=True, progressive=True)),
            ("WEBP lossless m6", "WEBP", dict(lossless=True, method=6)),
            ("WEBP q=100 m6", "WEBP", dict(quality=100, method=6)),
            ("WEBP q=  90 m6", "WEBP", dict(quality=90, method=6)),
            ("WEBP q=  80 m6", "WEBP", dict(quality=80, method=6)),
            ("WEBP q=  60 m6", "WEBP", dict(quality=60, method=6)),
            ("WEBP q=  40 m4", "WEBP", dict(quality=40, method=4)),
            ("AVIF q=100 (near-lossless)", "AVIF", dict(quality=100, speed=6)),
            ("AVIF q=  90 speed6", "AVIF", dict(quality=90, speed=6)),
            ("AVIF q=  80 speed6", "AVIF", dict(quality=80, speed=6)),
            ("AVIF q=  60 speed6", "AVIF", dict(quality=60, speed=6)),
            ("AVIF q=  50 speed8", "AVIF", dict(quality=50, speed=8)),
            ("TIFF lossless deflate", "TIFF", dict(compression="tiff_deflate")),
            ("TIFF lossless lzw", "TIFF", dict(compression="tiff_lzw")),
            ("GIF  (quantize 256)", "GIF", dict(optimize=True)),
            ("BMP  (no compression)", "BMP", dict()),
        ]

        for label, fmt, kw in cases:
            size, ms, score, err = run(
                lambda b, f, i=img, **k: i.save(b, f, **k), img, fmt, **kw
            )
            if "quantize" in kw:
                # Pillow has no PNG quantize kwarg: emulate the real path.
                colors, method = kw["quantize"]
                m = {"mediancut": Image.Quantize.MEDIANCUT, "fastoctree": Image.Quantize.FASTOCTREE}[method]
                t0 = time.perf_counter()
                q = img.quantize(colors=colors, method=m)
                buf = io.BytesIO()
                q.save(buf, "PNG", optimize=True, compress_level=9)
                ms = (time.perf_counter() - t0) * 1000.0
                size = buf.tell()
                back = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
                score = psnr(img, back)
                err = None
            if err:
                print(f"  {label:42s} UNSUPPORTED  {err[:70]}")
                rows.append((name, label, None, ms, score, err[:60]))
                continue
            pct = 100.0 * size / raw["jpg92"]
            print(
                f"  {label:42s} {size:>9,}B  {pct:5.1f}% of q92  "
                f"{ms:7.0f}ms  PSNR {score:6.2f}dB"
            )
            rows.append((name, label, size, ms, score, ""))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["| fixture | case | bytes | ms | PSNR dB | note |", "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(
                f"| {r[0]} | {r[1]} | {'' if r[2] is None else format(r[2], ',')} "
                f"| {r[3]:.0f} | {'' if math.isnan(r[4]) else format(r[4], '.2f')} | {r[5]} |"
            )
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
