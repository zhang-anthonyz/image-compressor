"""Theme integrity: both palettes must stay structurally identical."""
from __future__ import annotations

import re

from app.ui import theme


def test_both_palettes_expose_the_same_token_keys():
    assert set(theme.LIGHT_TOKENS) == set(theme.DARK_TOKENS)


def test_every_token_is_substituted():
    for mode in ("light", "dark"):
        qss = theme.build_stylesheet(mode)
        assert "$" not in qss, f"{mode} 样式表仍有未替换的占位符"
        assert "{" in qss and "}" in qss


def test_stylesheets_are_structurally_identical():
    """A selector present in one mode but not the other is a drift bug."""
    def selectors(qss: str) -> set[str]:
        return {
            match.group(1).strip()
            for match in re.finditer(r"([^{}]+)\{", qss)
            if not match.group(1).strip().startswith("/*")
        }

    light = selectors(theme.build_stylesheet("light"))
    dark = selectors(theme.build_stylesheet("dark"))
    assert light == dark


def test_no_pure_black_or_pure_white_canvas():
    """Pure black eats anti-aliasing on 1px strokes and glares the accent."""
    for mode in ("light", "dark"):
        tokens = theme.tokens_for(mode)
        assert tokens["BG_APP"].lower() != "#000000"
        assert len(tokens["BG_APP"]) == 7


def test_canvas_and_surface_match_the_documented_tokens():
    light = theme.tokens_for("light")
    assert light["BG_APP"] == "#EEF3FA"
    assert light["SURFACE"] == "#FFFFFF"
    assert light["ACCENT"] == "#185FA5"
    dark = theme.tokens_for("dark")
    assert dark["BG_APP"] == "#0A1426"
    assert dark["ACCENT"] == "#4A90E2"


def test_no_palette_leak_rule_for_qwidget_exists():
    """A global QWidget{} rule fills every label with the palette's grey."""
    qss = theme.build_stylesheet("light")
    assert not re.search(r"^\s*QWidget\s*\{", qss, re.MULTILINE)
    assert "QWidget#appRoot" in qss


def test_labels_declare_transparent_backgrounds():
    qss = theme.build_stylesheet("light")
    assert "QLabel {\n    background: transparent;" in qss
    assert "QCheckBox {\n    background: transparent;" in qss
    assert "QSlider {\n    background: transparent;" in qss


def test_native_combo_and_spin_subcontrols_are_zero_sized():
    qss = theme.build_stylesheet("light")
    assert "QComboBox::drop-down" in qss and "QComboBox::down-arrow" in qss
    assert "QSpinBox::up-button" in qss and "QSpinBox::down-button" in qss


def test_log_level_colours_cover_every_level_and_differ_per_mode():
    from app.core import task_log

    for mode in ("light", "dark"):
        colors = theme.log_level_colors(mode)
        for level in (task_log.LEVEL_INFO, task_log.LEVEL_SUCCESS,
                      task_log.LEVEL_WARNING, task_log.LEVEL_ERROR):
            assert level in colors
            assert colors[level].startswith("#") and len(colors[level]) == 7


def test_resolve_mode_passes_through_concrete_modes():
    assert theme.resolve_mode("light") == "light"
    assert theme.resolve_mode("dark") == "dark"
    assert theme.resolve_mode("system", "dark") == "dark"
    assert theme.resolve_mode("system", "light") == "light"
    assert theme.resolve_mode("system") in ("light", "dark")


def test_set_current_mode_rejects_unknown_values():
    import pytest

    with pytest.raises(ValueError):
        theme.set_current_mode("neon")
    theme.set_current_mode("light")
    assert theme.current_mode() == "light"


def test_palette_is_built_from_tokens():
    from PySide6.QtGui import QColor, QPalette

    palette = theme.build_palette("dark")
    assert palette.color(QPalette.ColorRole.Window) == QColor(theme.DARK_BG_APP)
    assert palette.color(QPalette.ColorRole.Highlight) == QColor(theme.DARK_ACCENT)
