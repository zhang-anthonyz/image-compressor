"""Plan policy: mode/format legality, quality mapping, effort mapping."""
from __future__ import annotations

import pytest

from app.core import formats
from app.core.planner import (
    CompressionPlan,
    Effort,
    Mode,
    MetadataPolicy,
    NamingPolicy,
    jpeg_subsampling,
    png_colors_for_quality,
    quality_label,
    resolve_workers,
)

AVIF = formats.BY_KEY["avif"]
JPEG = formats.BY_KEY["jpeg"]
PNG = formats.BY_KEY["png"]
TIFF = formats.BY_KEY["tiff"]


def test_avif_lossless_is_rejected_with_reason():
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="avif")
    issue = plan.issue_for(AVIF)
    assert issue is not None
    assert "无损" in issue.message


def test_avif_lossy_is_allowed():
    plan = CompressionPlan(mode=Mode.LOSSY, target_format="avif")
    assert plan.issue_for(AVIF) is None


def test_tiff_lossy_is_rejected():
    plan = CompressionPlan(mode=Mode.LOSSY, target_format="tiff")
    assert plan.issue_for(TIFF) is not None


def test_read_only_container_cannot_be_a_target():
    plan = CompressionPlan(target_format="heic")
    issue = plan.issue_for(formats.BY_KEY["heic"])
    assert issue is not None
    assert "HEIC" in issue.message


def test_heic_source_falls_back_to_a_writable_container():
    heic = formats.BY_KEY["heic"]
    plan = CompressionPlan()
    assert plan.resolved_format(heic).key == "jpeg"
    assert plan.resolved_format(heic).can_write


def test_keep_format_resolves_to_source_container():
    plan = CompressionPlan()
    assert plan.resolved_format(PNG).key == "png"
    assert plan.resolved_format(JPEG).key == "jpeg"


def test_png_palette_depth_is_monotonic_and_bounded():
    values = [png_colors_for_quality(q) for q in range(1, 101)]
    assert values == sorted(values)
    assert values[0] >= 16 and values[-1] == 256
    # The high preset is the one most users leave selected; it must use the
    # whole palette instead of stopping at ~199 colours.
    assert png_colors_for_quality(82) == 256


def test_png_colors_clamp_out_of_range_input():
    assert png_colors_for_quality(-50) == png_colors_for_quality(1)
    assert png_colors_for_quality(9999) == 256


def test_jpeg_subsampling_switches_to_444_from_the_high_preset():
    assert jpeg_subsampling(95) == 0
    assert jpeg_subsampling(90) == 0
    assert jpeg_subsampling(82) == 0
    assert jpeg_subsampling(65) == 2


@pytest.mark.parametrize(
    "quality,expected",
    [(95, "极高"), (82, "高"), (60, "中"), (40, "偏低"), (10, "低")],
)
def test_quality_bands(quality, expected):
    assert quality_label(quality) == expected


def test_effort_maps_to_slower_encoder_settings():
    fast = CompressionPlan(effort=Effort.FAST)
    balanced = CompressionPlan(effort=Effort.BALANCED)
    maximum = CompressionPlan(effort=Effort.MAX)
    assert fast.oxipng_args() == ["--opt", "2"]
    assert balanced.oxipng_args() == ["--opt", "4"]
    assert maximum.oxipng_args() == ["--opt", "6"]
    assert balanced._webp_method() >= fast._webp_method()
    assert maximum._avif_speed() < fast._avif_speed()


def test_lossless_jpeg_uses_keep_only_for_jpeg_sources():
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="jpeg")
    keep = plan.pillow_params(JPEG, "JPEG")
    assert keep["quality"] == "keep"
    fallback = plan.pillow_params(JPEG, "PNG")
    assert fallback["quality"] == 95 and fallback["subsampling"] == 0


def test_lossy_png_carries_palette_size():
    plan = CompressionPlan(mode=Mode.LOSSY, quality=70, target_format="png")
    params = plan.pillow_params(PNG, "PNG")
    assert params["palette_colors"] == png_colors_for_quality(70)
    lossless = CompressionPlan(mode=Mode.LOSSLESS, target_format="png").pillow_params(PNG, "PNG")
    assert "palette_colors" not in lossless


def test_tiff_plan_uses_deflate():
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="tiff")
    assert plan.pillow_params(TIFF, "TIFF")["compression"] == "tiff_deflate"


def test_effective_mode_degrades_instead_of_failing():
    plan = CompressionPlan(mode=Mode.LOSSLESS, target_format="avif")
    assert plan.effective_mode(AVIF) is Mode.LOSSY


def test_workers_are_bounded_by_batch_size_and_never_zero():
    assert resolve_workers(0, 1) == 1
    assert resolve_workers(8, 3) == 3
    assert resolve_workers(4, 100) == 4
    assert resolve_workers(0, 100) >= 1


def test_summary_reads_like_a_sentence():
    plan = CompressionPlan(
        mode=Mode.LOSSY, quality=82, scale_percent=50, effort=Effort.BALANCED,
        metadata=MetadataPolicy.SLIM, naming=NamingPolicy.SUFFIX,
    )
    text = plan.summary()
    assert "有损 q82" in text and "缩放 50%" in text and "保持原格式" in text


def test_copy_returns_a_new_plan():
    plan = CompressionPlan()
    other = plan.copy(quality=41)
    assert other.quality == 41 and plan.quality == 82
