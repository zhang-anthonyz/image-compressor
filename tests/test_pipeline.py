"""End-to-end pipeline behaviour on real encoded images."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core import formats, pipeline
from app.core.encoders import registry
from app.core.planner import CompressionPlan, MetadataPolicy, Mode, NamingPolicy
from tests.conftest import psnr, reopen


def out_dir(tmp_path: Path) -> Path:
    target = tmp_path / "out"
    target.mkdir()
    return target


# ---------------------------------------------------------------- happy path
def test_lossy_jpeg_shrinks_and_keeps_dimensions(photo_jpeg, tmp_path):
    dst = out_dir(tmp_path) / "out.jpg"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=70, target_format="jpeg")
    result = pipeline.compress_file(photo_jpeg, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    assert result.new_size < result.original_size
    assert result.new_dimensions == result.original_dimensions
    assert reopen(dst).size == result.original_dimensions
    assert result.ratio > 0.3


def test_lossless_png_is_pixel_identical(photo_png, tmp_path):
    dst = out_dir(tmp_path) / "out.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png")
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED)
    assert psnr(reopen(photo_png), reopen(dst)) == float("inf")


def test_lossless_webp_is_pixel_identical(photo_png, tmp_path):
    dst = out_dir(tmp_path) / "out.webp"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="webp")
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    assert psnr(reopen(photo_png), reopen(dst)) == float("inf")
    # The whole reason WebP is the headline lossless target.
    assert result.new_size < result.original_size


def test_lossy_png_quantizes_and_stays_viewable(graphic_png, tmp_path):
    dst = out_dir(tmp_path) / "out.png"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=50, target_format="png")
    result = pipeline.compress_file(graphic_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    assert reopen(dst).size == reopen(graphic_png).size
    assert result.new_size <= result.original_size


def test_scale_percent_preserves_aspect_ratio(photo_jpeg, tmp_path):
    dst = out_dir(tmp_path) / "half.jpg"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=80, scale_percent=50)
    result = pipeline.compress_file(photo_jpeg, plan, dst)
    width, height = result.original_dimensions
    assert result.new_dimensions == (max(1, round(width * 0.5)), max(1, round(height * 0.5)))
    assert reopen(dst).size == result.new_dimensions


def test_conversion_to_another_container(photo_png, tmp_path):
    dst = out_dir(tmp_path) / "converted.jpg"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=85, target_format="jpeg")
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    assert reopen(dst).format == "JPEG"


def test_output_directory_is_created(tmp_path, graphic_png):
    dst = tmp_path / "deeply" / "nested" / "out.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png")
    result = pipeline.compress_file(graphic_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED)
    assert dst.is_file()


# ------------------------------------------------------------------- alpha
def test_transparency_is_flattened_onto_the_chosen_background(alpha_png, tmp_path):
    dst = out_dir(tmp_path) / "flat.jpg"
    plan = CompressionPlan(
        mode=Mode.LOSSY, quality=92, target_format="jpeg", background=(255, 255, 255),
    )
    result = pipeline.compress_file(alpha_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    corner = reopen(dst).convert("RGB").getpixel((2, 2))
    assert min(corner) > 240, f"transparent corner became {corner}, expected near-white"
    assert "铺底" in result.note_text()


def test_transparency_is_flattened_onto_a_custom_background(alpha_png, tmp_path):
    dst = out_dir(tmp_path) / "flat_red.jpg"
    plan = CompressionPlan(
        mode=Mode.LOSSY, quality=92, target_format="jpeg", background=(12, 12, 12),
    )
    result = pipeline.compress_file(alpha_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE
    corner = reopen(dst).convert("RGB").getpixel((2, 2))
    assert max(corner) < 60, f"corner {corner} did not take the custom background"


def test_alpha_survives_a_format_that_supports_it(alpha_png, tmp_path):
    dst = out_dir(tmp_path) / "kept.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png")
    result = pipeline.compress_file(alpha_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED)
    assert reopen(dst).convert("RGBA").getpixel((2, 2))[3] < 10


# ---------------------------------------------------------------- metadata
def test_orientation_is_baked_not_left_in_exif(oriented_jpeg, tmp_path):
    dst = out_dir(tmp_path) / "oriented.jpg"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=85, metadata=MetadataPolicy.FULL)
    result = pipeline.compress_file(oriented_jpeg, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    width, height = result.original_dimensions
    assert result.new_dimensions == (height, width), "orientation 6 must swap the axes"
    with Image.open(dst) as check:
        assert 274 not in check.getexif()


def test_icc_profile_survives_the_slim_policy(icc_png, tmp_path):
    dst = out_dir(tmp_path) / "icc_out.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png", metadata=MetadataPolicy.SLIM)
    result = pipeline.compress_file(icc_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED)
    with Image.open(dst) as check:
        assert check.info.get("icc_profile"), "slim policy must keep colour management"


def test_strip_policy_removes_icc(icc_png, tmp_path):
    dst = out_dir(tmp_path) / "stripped.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png", metadata=MetadataPolicy.STRIP)
    result = pipeline.compress_file(icc_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED)
    with Image.open(dst) as check:
        assert not check.info.get("icc_profile")


def test_full_policy_keeps_other_exif_tags(tmp_path):
    source = tmp_path / "tagged.jpg"
    image = Image.new("RGB", (80, 60), (200, 120, 60))
    exif = Image.Exif()
    exif[271] = "PixelPress"  # Make
    exif[274] = 1
    image.save(source, "JPEG", quality=90, exif=exif.tobytes())

    dst = tmp_path / "keep_exif.jpg"
    plan = CompressionPlan(mode=Mode.LOSSY, quality=90, metadata=MetadataPolicy.FULL)
    result = pipeline.compress_file(source, plan, dst)
    assert result.status == pipeline.STATUS_DONE, result.message
    with Image.open(dst) as check:
        assert check.getexif().get(271) == "PixelPress"


# ----------------------------------------------------------- odd inputs
def test_animated_gif_is_skipped_with_a_reason(animated_gif, tmp_path):
    dst = out_dir(tmp_path) / "anim.gif"
    result = pipeline.compress_file(animated_gif, CompressionPlan(mode=Mode.LOSSY), dst)
    assert result.status == pipeline.STATUS_SKIPPED
    assert "动图" in result.message
    assert not dst.exists()


def test_corrupt_file_fails_without_raising(corrupt_file, tmp_path):
    dst = out_dir(tmp_path) / "broken.png"
    result = pipeline.compress_file(corrupt_file, CompressionPlan(), dst)
    assert result.status == pipeline.STATUS_FAILED
    assert result.message


def test_unreadable_path_fails_without_raising(tmp_path):
    result = pipeline.compress_file(tmp_path / "missing.png", CompressionPlan(), tmp_path / "o.png")
    assert result.status == pipeline.STATUS_FAILED
    assert not (tmp_path / "o.png").exists()


def test_pixel_guard_refuses_absurd_dimensions(photo_png, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_PIXELS", 100)
    dst = out_dir(tmp_path) / "big.png"
    result = pipeline.compress_file(photo_png, CompressionPlan(mode=Mode.LOSSLESS), dst)
    assert result.status == pipeline.STATUS_SKIPPED
    assert "过大" in result.message


def test_incompatible_plan_skips_rather_than_writes_junk(photo_png, tmp_path):
    dst = out_dir(tmp_path) / "out.avif"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="avif")
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status == pipeline.STATUS_SKIPPED
    assert "无损" in result.message
    assert not dst.exists()


# ------------------------------------------------------------- keep_smaller
def test_keep_smaller_writes_the_original_bytes(photo_png, tmp_path, monkeypatch):
    """When the encoder output is not smaller, the source wins."""

    class Bloated:
        """Stands in for a pathological encoder result."""

        def encode(self, request):
            from app.core.encoders.base import EncodeResult

            return EncodeResult(data=b"x" * (len(request.image.tobytes()) + 4096), encoder="test")

    monkeypatch.setattr(pipeline, "encode", Bloated().encode)
    dst = out_dir(tmp_path) / "bloat.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, keep_smaller=True)
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status == pipeline.STATUS_UNCHANGED
    assert dst.read_bytes() == photo_png.read_bytes()
    assert result.saved_bytes == 0


def test_keep_smaller_disabled_still_writes_larger_output(photo_png, tmp_path, monkeypatch):
    class Bloated:
        """A valid but deliberately uncompressed PNG: bigger, still loadable."""

        def encode(self, request):
            import io as _io

            from app.core.encoders.base import EncodeResult

            buffer = _io.BytesIO()
            request.image.save(buffer, "PNG", compress_level=0)
            return EncodeResult(data=buffer.getvalue(), encoder="test")

    monkeypatch.setattr(pipeline, "encode", Bloated().encode)
    dst = out_dir(tmp_path) / "small.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, keep_smaller=False)
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status == pipeline.STATUS_DONE
    assert result.new_size > result.original_size
    assert reopen(dst).size == result.original_dimensions


# ---------------------------------------------------------------- oxipng
@pytest.mark.skipif(not registry.oxipng_available(), reason="vendor/oxipng.exe not present")
def test_png_lossless_uses_the_bundled_oxipng(graphic_png, tmp_path):
    dst = out_dir(tmp_path) / "oxi.png"
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="png")
    result = pipeline.compress_file(graphic_png, plan, dst)
    assert result.encoder == "oxipng"
    assert "oxipng" in result.note_text()
    assert result.new_size < result.original_size


# ------------------------------------------------------------------ probe
def test_probe_reads_header_details(photo_jpeg, animated_gif, corrupt_file):
    good = pipeline.probe(photo_jpeg)
    assert good.ok and good.format_key == "jpeg" and good.width == 320
    assert not good.animated

    anim = pipeline.probe(animated_gif)
    assert anim.ok and anim.animated

    bad = pipeline.probe(corrupt_file)
    assert not bad.ok and bad.error


def test_probe_marks_transparency(alpha_png, photo_jpeg):
    assert pipeline.probe(alpha_png).has_alpha
    assert not pipeline.probe(photo_jpeg).has_alpha


def test_probe_reports_missing_file(tmp_path):
    assert not pipeline.probe(tmp_path / "nope.png").ok


# ------------------------------------------------------------- full matrix
@pytest.mark.parametrize("target_key", ["jpeg", "png", "webp", "avif", "tiff", "bmp"])
@pytest.mark.parametrize("mode", [Mode.LOSSLESS, Mode.LOSSY])
def test_every_legal_combination_produces_a_loadable_file(photo_png, tmp_path, target_key, mode):
    target = formats.BY_KEY[target_key]
    plan = CompressionPlan(mode=mode, quality=80, target_format=target_key)
    if not plan.is_compatible(target):
        pytest.skip(f"{mode.value}+{target_key} is intentionally unavailable")
    extension = target.extensions[0]
    dst = out_dir(tmp_path) / f"matrix_{target_key}_{mode.value}{extension}"
    result = pipeline.compress_file(photo_png, plan, dst)
    assert result.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED), result.message
    with Image.open(dst) as check:
        check.load()
        assert check.size == result.new_dimensions
