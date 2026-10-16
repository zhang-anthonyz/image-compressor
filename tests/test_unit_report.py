"""Readable number formatting shared by the UI, logs and headless report."""
from __future__ import annotations

from app.core import unit_report as units


def test_human_size_steps_through_binary_units():
    assert units.human_size(0) == "0 B"
    assert units.human_size(512) == "512 B"
    assert units.human_size(1024) == "1.0 KB"
    assert units.human_size(1024 * 1024) == "1.0 MB"
    assert units.human_size(3 * 1024**3) == "3.0 GB"


def test_human_size_handles_none():
    assert units.human_size(None) == "—"


def test_human_size_drops_decimals_from_three_digits_up():
    assert units.human_size(512 * 1024) == "512 KB"
    assert units.human_size(99 * 1024) == "99.0 KB"


def test_saved_percent_uses_a_real_minus_sign():
    assert units.saved_percent(1000, 250) == "−75.0%"
    assert units.saved_percent(1000, 1200) == "+20.0%"
    assert units.saved_percent(0, 100) == "—"


def test_saved_ratio_is_clamped():
    assert units.saved_ratio(1000, 250) == 0.75
    assert units.saved_ratio(1000, 5000) == 0.0
    assert units.saved_ratio(None, None) == 0.0


def test_size_delta_uses_a_real_minus_sign():
    assert units.size_delta(4 * 1024 * 1024, 1024 * 1024) == "−3.0 MB"


def test_dimensions_uses_a_multiplication_sign():
    assert units.dimensions(6000, 4000) == "6,000 × 4,000"
    assert units.dimensions(0, 0) == "—"


def test_scale_target_never_upscales_or_returns_zero():
    assert units.scale_target((1000, 500), 50) == (500, 250)
    assert units.scale_target((1000, 500), 100) == (1000, 500)
    assert units.scale_target((1000, 500), 120) == (1000, 500)
    assert units.scale_target((3, 3), 5) == (1, 1)


def test_scale_target_rounds_both_axes_independently():
    # 333 * 0.5 = 166.5 -> 166 (banker's rounding avoided by round()).
    assert units.scale_target((333, 111), 50) == (166, 56)


def test_duration_formats_minutes():
    assert units.duration(12.44) == "12.4 s"
    assert units.duration(95) == "1 分 35 秒"
    assert units.duration(None) == "—"
