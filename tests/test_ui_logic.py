"""Pure UI logic: control linkage rules and label text, without a window."""
from __future__ import annotations

from app.core.planner import CompressionPlan, Mode, NamingPolicy
from app.ui import ui_logic


def test_format_options_start_with_keep_original():
    options = ui_logic.format_options()
    assert options[0][0] == ui_logic.KEEP_FORMAT_VALUE
    keys = [value for value, _ in options]
    assert "png" in keys and "avif" in keys
    assert "heic" not in keys, "HEIC is read-only and must not be a target"


def test_mode_availability_disables_avif_lossless_with_a_reason():
    from app.core import formats

    avif = formats.BY_KEY["avif"]
    availability = ui_logic.mode_availability(avif)
    assert availability[ui_logic.MODE_LOSSLESS][0] is False
    assert "无损" in availability[ui_logic.MODE_LOSSLESS][1]
    assert availability[ui_logic.MODE_LOSSY][0] is True


def test_mode_availability_disables_tiff_lossy():
    from app.core import formats

    availability = ui_logic.mode_availability(formats.BY_KEY["tiff"])
    assert availability[ui_logic.MODE_LOSSY][0] is False
    assert availability[ui_logic.MODE_LOSSLESS][0] is True


def test_mode_availability_is_permissive_without_context():
    availability = ui_logic.mode_availability(None)
    assert availability[ui_logic.MODE_LOSSLESS][0] and availability[ui_logic.MODE_LOSSY][0]


def test_effective_target_follows_keep_or_explicit_choice():
    assert ui_logic.effective_target("png", ui_logic.KEEP_FORMAT_VALUE).key == "png"
    assert ui_logic.effective_target("png", "webp").key == "webp"
    assert ui_logic.effective_target("heic", ui_logic.KEEP_FORMAT_VALUE).key == "jpeg"
    assert ui_logic.effective_target(None, ui_logic.KEEP_FORMAT_VALUE) is None


def test_quality_only_applies_to_lossy_capable_formats():
    from app.core import formats

    assert ui_logic.quality_applies(ui_logic.MODE_LOSSLESS, formats.BY_KEY["jpeg"]) is False
    assert ui_logic.quality_applies(ui_logic.MODE_LOSSY, formats.BY_KEY["jpeg"]) is True
    assert ui_logic.quality_applies(ui_logic.MODE_LOSSY, formats.BY_KEY["tiff"]) is False
    assert ui_logic.quality_applies(ui_logic.MODE_LOSSY, None) is False


def test_quality_hint_explains_png_palette_size():
    from app.core import formats
    from app.core.planner import png_colors_for_quality

    hint = ui_logic.quality_hint(formats.BY_KEY["png"], ui_logic.MODE_LOSSY, 70)
    assert str(png_colors_for_quality(70)) in hint


def test_quality_hint_quotes_the_lossless_note():
    from app.core import formats

    hint = ui_logic.quality_hint(formats.BY_KEY["jpeg"], ui_logic.MODE_LOSSLESS, 82)
    assert "视觉无损" in hint


def test_scale_readout_shows_target_pixels_and_keeps_original():
    assert ui_logic.scale_readout(50, (6000, 4000)) == "→ 3,000 × 2,000"
    assert "保持" in ui_logic.scale_readout(100, (6000, 4000))
    assert ui_logic.scale_readout(50, None).startswith("→")


def test_preset_matching_is_exact():
    from app.core.planner import QUALITY_PRESETS

    for _label, value in QUALITY_PRESETS:
        assert ui_logic.preset_for_quality(value) == str(value)
    assert ui_logic.preset_for_quality(77) == ""


def test_plan_from_widget_values_maps_every_control():
    plan = ui_logic.plan_from_widget_values(
        {
            "mode": ui_logic.MODE_LOSSLESS,
            "quality": 91,
            "scale_percent": 75,
            "target_format": ui_logic.KEEP_FORMAT_VALUE,
            "metadata": "strip",
            "naming": "prefix",
            "prefix": "min_",
            "collision": "skip",
            "effort": "max",
            "keep_smaller": False,
            "inplace": True,
            "workers": 3,
        }
    )
    assert plan.mode is Mode.LOSSLESS
    assert plan.quality == 91 and plan.scale_percent == 75
    assert plan.target_format is None
    assert plan.naming is NamingPolicy.PREFIX and plan.prefix == "min_"
    assert plan.collision.value == "skip" and plan.effort.value == "max"
    assert plan.keep_smaller is False and plan.inplace is True and plan.workers == 3


def test_naming_preview_reflects_the_policy():
    plan = CompressionPlan(naming=NamingPolicy.SUFFIX, suffix="_min")
    assert ui_logic.naming_preview(plan, "photo.jpg").endswith(".jpg")
    assert "photo_min" in ui_logic.naming_preview(plan, "photo.jpg")

    prefix = CompressionPlan(naming=NamingPolicy.PREFIX, prefix="min_")
    assert ui_logic.naming_preview(prefix, "photo.jpg").startswith("min_photo")

    templated = CompressionPlan(naming=NamingPolicy.TEMPLATE, template="{name}_{quality}")
    assert "photo_82" in ui_logic.naming_preview(templated, "photo.jpg")


def test_naming_preview_follows_a_converted_extension():
    from app.core import formats

    plan = CompressionPlan(naming=NamingPolicy.SUFFIX, suffix="_min", target_format="webp")
    assert ui_logic.naming_preview(plan, "photo.png", formats.BY_KEY["webp"]).endswith(".webp")


def test_summary_line_handles_an_empty_queue():
    text = ui_logic.summary_line({"count": 0})
    assert "队列为空" in text


def test_summary_line_reports_savings_and_problems():
    text = ui_logic.summary_line(
        {"count": 5, "enabled": 4, "original": 1000, "new": 250, "saved": 750,
         "failed": 1, "skipped": 2},
        running=True,
    )
    assert "5 个文件" in text and "已选 4" in text
    assert "总节省" in text and "1 个失败" in text and "2 个跳过" in text
    assert "正在压缩" in text
