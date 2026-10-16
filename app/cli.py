"""Packaging self-check: exercises the engine end to end without any UI.

This is not a user-facing CLI (that was explicitly out of scope); it exists so a
frozen build can prove its encoder stack works before anyone looks at a window.
``PixelPress.exe --headless`` must exit 0.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from . import APP_NAME, APP_VERSION
from .core import formats, pipeline
from .core.encoders import registry
from .core.planner import CompressionPlan, Effort, MetadataPolicy, Mode

#: Format/mode pairs the self-check must be able to run.
MATRIX: tuple[tuple[str, Mode], ...] = (
    ("png", Mode.LOSSLESS),
    ("png", Mode.LOSSY),
    ("jpeg", Mode.LOSSY),
    ("jpeg", Mode.LOSSLESS),
    ("webp", Mode.LOSSLESS),
    ("webp", Mode.LOSSY),
    ("avif", Mode.LOSSY),
    ("tiff", Mode.LOSSLESS),
    ("gif", Mode.LOSSY),
    ("bmp", Mode.LOSSLESS),
)


def _sample_image(folder: Path) -> Path:
    """A source with the properties that break naive pipelines."""
    image = Image.new("RGB", (320, 240), (246, 247, 249))
    draw = ImageDraw.Draw(image)
    for index in range(24):
        draw.rectangle(
            [8 + index * 12, 40, 16 + index * 12, 220],
            fill=(20 + index * 9, 90 + (index * 5) % 120, 200 - index * 7),
        )
    draw.ellipse([120, 90, 210, 180], fill=(214, 59, 22))
    path = folder / "sample.png"
    image.save(path, "PNG", compress_level=9)
    return path


def _identical(first: Image.Image, second: Image.Image) -> bool:
    """Exact pixel identity via Pillow only (no numpy in the bundle).

    Stronger than a PSNR threshold: a lossless encoder must return the same
    pixels, not merely similar ones.
    """
    if first.size != second.size:
        return False
    from PIL import ImageChops

    first_rgb = first.convert("RGB")
    second_rgb = second.convert("RGB")
    return ImageChops.difference(first_rgb, second_rgb).getbbox() is None


def _psnr(first: Image.Image, second: Image.Image) -> float:
    """PSNR when numpy happens to be available, else NaN.

    Only used for JPEG's "visually lossless" mode, which is quantified, not
    bit-exact — so this is informational and never fails the run.
    """
    if first.size != second.size:
        return float("-inf")
    try:
        import numpy as np
    except ImportError:
        return float("nan")
    x = np.asarray(first.convert("RGB"), dtype=np.float64)
    y = np.asarray(second.convert("RGB"), dtype=np.float64)
    mse = float(((x - y) ** 2).mean())
    return float("inf") if mse == 0 else 10.0 * math.log10(255.0**2 / mse)


_qt_app = None


def _font_report() -> dict:
    """Load the bundled fonts and report them.

    QFontDatabase needs a live QGuiApplication, so the self-check creates one
    (offscreen) when it runs without a window. That has a second benefit: it
    proves Qt itself and its platform plugin load correctly in the frozen build,
    which "the process is alive" would not have shown.
    """
    global _qt_app
    from PySide6.QtCore import QCoreApplication

    if QCoreApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication

        _qt_app = QGuiApplication([])

    from .ui import fonts

    report = fonts.font_report()
    return {
        "display": report["display"],
        "mono": report["mono"],
        "bundled": list(report["bundled"].keys()),
        "display_is_bundled": report["display_is_bundled"],
        "mono_is_bundled": report["mono_is_bundled"],
    }


def run_checks() -> dict:
    """Execute the matrix; return a JSON-serialisable report."""
    report: dict = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "engine": registry.engine_report(),
        "fonts": _font_report(),
        "formats": {spec.key: spec.label for spec in formats.ALL_FORMATS},
        "cases": [],
        "failures": [],
    }
    if not report["fonts"]["display_is_bundled"] or not report["fonts"]["mono_is_bundled"]:
        report["failures"].append(
            f"随包字体未生效：display={report['fonts']['display']} mono={report['fonts']['mono']}"
        )

    with tempfile.TemporaryDirectory(prefix="pixelpress-headless-") as tmp:
        folder = Path(tmp)
        source = _sample_image(folder)
        original = Image.open(source)
        original.load()
        original_size = source.stat().st_size

        # Formats the matrix asks for may legitimately be unsupported; treat a
        # declared-unavailable combination as a skip, not a failure.
        available_heif = registry.heif_available()
        report["heif_available"] = available_heif

        for key, mode in MATRIX:
            target = formats.BY_KEY[key]
            plan = CompressionPlan(
                mode=mode, quality=80, target_format=key,
                metadata=MetadataPolicy.SLIM, effort=Effort.BALANCED,
            )
            if not plan.is_compatible(target):
                report["cases"].append(
                    {"format": key, "mode": mode.value, "status": "unavailable",
                     "reason": plan.issue_for(target).message}
                )
                continue

            destination = folder / f"out_{key}_{mode.value}{target.extensions[0]}"
            result = pipeline.compress_file(source, plan, destination)
            case = {
                "format": key,
                "mode": mode.value,
                "status": result.status,
                "encoder": result.encoder,
                "original_size": result.original_size,
                "new_size": result.new_size,
                "saved_percent": round(result.ratio * 100, 1),
                "message": result.message,
            }
            if result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED) and destination.is_file():
                with Image.open(destination) as check:
                    check.load()
                    case["dimensions_ok"] = check.size == original.size
                    if mode is Mode.LOSSLESS:
                        exact = _identical(original, check)
                        case["bit_identical"] = exact
                        if key == "jpeg":
                            # JPEG "lossless" is table-preserving re-encoding.
                            score = _psnr(original, check)
                            case["psnr"] = (
                                "inf" if score == float("inf")
                                else "n/a" if score != score
                                else round(score, 2)
                            )
                        elif key != "gif" and not exact:
                            report["failures"].append(
                                f"{key} 无损输出并非逐位一致"
                            )
                if not case.get("dimensions_ok"):
                    report["failures"].append(f"{key}/{mode.value} 输出尺寸不一致")
            elif result.status == pipeline.STATUS_FAILED:
                report["failures"].append(f"{key}/{mode.value} 失败：{result.message}")
            report["cases"].append(case)

        # Alpha must be flattened rather than turning black.
        alpha = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(alpha)
        draw.rectangle([16, 16, 48, 48], fill=(214, 59, 22, 255))
        alpha_path = folder / "alpha.png"
        alpha.save(alpha_path, "PNG")
        flattened = folder / "alpha_flat.jpg"
        result = pipeline.compress_file(
            alpha_path,
            CompressionPlan(mode=Mode.LOSSY, quality=92, target_format="jpeg"),
            flattened,
        )
        corner = Image.open(flattened).convert("RGB").getpixel((2, 2)) if flattened.is_file() else None
        report["alpha_flatten"] = {
            "status": result.status,
            "corner_rgb": corner,
            "ok": bool(corner and min(corner) > 235),
        }
        if corner is None or min(corner) <= 235:
            report["failures"].append(f"透明铺底未生效：corner={corner}")

        # Orientation must be baked, not left in EXIF.
        oriented = Image.new("RGB", (200, 100), (40, 80, 160))
        exif = Image.Exif()
        exif[274] = 6
        oriented_path = folder / "oriented.jpg"
        oriented.save(oriented_path, "JPEG", quality=90, exif=exif.tobytes())
        rotated = folder / "rotated.jpg"
        result = pipeline.compress_file(
            oriented_path,
            CompressionPlan(mode=Mode.LOSSY, quality=85, metadata=MetadataPolicy.FULL),
            rotated,
        )
        baked = result.new_dimensions == (100, 200)
        report["orientation"] = {
            "status": result.status, "new_dimensions": list(result.new_dimensions), "ok": baked,
        }
        if not baked:
            report["failures"].append(f"方向未烘焙：{result.new_dimensions}")

        report["sample"] = {"original_size": original_size}

    report["ok"] = not report["failures"]
    return report


def _configure_console() -> None:
    """Make redirected output UTF-8 so the self-check report is always readable.

    A frozen windowed exe writing into a file uses the console codepage (CP936
    here), which turns the Chinese report into mojibake for anything that reads
    it as UTF-8. When attached to a real console the codepage is left alone, so
    the report still renders correctly in a cmd window.
    """
    stream = sys.stdout
    try:
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    parser = argparse.ArgumentParser(prog=f"{APP_NAME} --headless")
    parser.add_argument("--headless", action="store_true", help="运行自检并退出")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args, _unknown = parser.parse_known_args(argv)

    report = run_checks()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        engine = report["engine"]
        print(f"{APP_NAME} {report['version']} 自检")
        print(f"  Pillow {engine['pillow']} · oxipng {engine['oxipng'] or '未内置'} "
              f"· HEIC {'可用' if report.get('heif_available') else '不可用'}")
        print(f"  字体 界面={report['fonts']['display']} 数值={report['fonts']['mono']}")
        for case in report["cases"]:
            saved = case.get("saved_percent")
            detail = f"{saved:5.1f}%" if saved is not None else "  —  "
            print(f"  {case['format']:5s} {case['mode']:9s} {case['status']:9s} {detail} "
                  f"{case.get('psnr', '')} {case.get('message', '')}".rstrip())
        print(f"  透明铺底: {'OK' if report['alpha_flatten']['ok'] else 'FAIL'}")
        print(f"  方向烘焙: {'OK' if report['orientation']['ok'] else 'FAIL'}")
        if report["failures"]:
            print("\n失败项:")
            for failure in report["failures"]:
                print(f"  ! {failure}")
        else:
            print("\n全部检查通过")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
