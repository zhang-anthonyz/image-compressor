"""Bundled fonts must resolve — this is what the sibling project got wrong.

Qt needs a live QGuiApplication before QFontDatabase can be queried, so the whole
module runs under an offscreen one.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui import fonts  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_bundled_fonts_register(qt_app):
    registered = fonts.load_bundled_fonts()
    assert "DM Sans" in registered, "DM Sans 未随包生效"
    assert "Roboto Mono" in registered, "Roboto Mono 未随包生效"


def test_variable_font_exposes_multiple_weights(qt_app):
    styles = fonts.load_bundled_fonts()["DM Sans"]
    assert len(styles) >= 4, f"DM Sans 变量字体只解析出 {styles}"


def test_display_and_mono_resolve_to_the_bundled_families(qt_app):
    assert fonts.display_family() == fonts.DISPLAY_FAMILY
    assert fonts.mono_family() == fonts.MONO_FAMILY


def test_family_chains_include_a_cjk_face(qt_app):
    """Without a CJK family in the chain, Chinese renders as tofu boxes."""
    for chain in (fonts.display_families(), fonts.mono_families()):
        assert chain[0] in (fonts.DISPLAY_FAMILY, fonts.MONO_FAMILY)
        assert any("YaHei" in name or "Noto" in name or "SimSun" in name for name in chain)


def test_chains_have_no_duplicates(qt_app):
    for chain in (fonts.display_families(), fonts.mono_families()):
        assert len(chain) == len(set(chain))


def test_make_font_carries_the_whole_chain(qt_app):
    font = fonts.make_font(size=11, weight=fonts.WEIGHT_SEMIBOLD)
    families = list(font.families())
    assert families[0] == fonts.DISPLAY_FAMILY
    assert len(families) > 1
    assert font.pointSize() == 11


def test_mono_font_starts_with_the_mono_family(qt_app):
    font = fonts.make_font(size=9, mono=True)
    assert list(font.families())[0] == fonts.MONO_FAMILY


def test_tracking_is_applied_as_absolute_spacing(qt_app):
    font = QFont()
    fonts.apply_tracking(font, 1.4)
    assert font.letterSpacingType() == QFont.SpacingType.AbsoluteSpacing
    # Qt stores letter spacing as a fixed-point 8.8 value, so 1.4 comes back as
    # 1.390625 — quantisation, not a bug.
    assert font.letterSpacing() == pytest.approx(1.4, abs=0.02)


def test_qss_family_stacks_are_quoted_lists(qt_app):
    assert fonts.display_stack().startswith('"DM Sans"')
    assert '"Microsoft YaHei UI"' in fonts.display_stack()
    assert fonts.mono_stack().startswith('"Roboto Mono"')


def test_font_report_flags_bundled_usage(qt_app):
    report = fonts.font_report()
    assert report["display_is_bundled"] is True
    assert report["mono_is_bundled"] is True
