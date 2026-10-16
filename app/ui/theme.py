"""PRESS — the PixelPress design system: tokens, stylesheet, palette.

The identity is "print room": cool paper canvas, ink text, and a single
vermilion signal accent, with halftone dots as the one decorative motif (it
belongs to printing, which is where image compression comes from).

Two rules earned the hard way and enforced here:

* **No global ``QWidget {}`` rule.** Qt fills any styled widget that does not
  declare a background with the palette's Window colour, which paints grey
  blocks over every label inside a white card. Backgrounds are declared only
  where a surface is actually wanted, and inner widgets are set transparent.
* **Never fight the native indicator.** Once QSS touches a QComboBox, Qt stops
  drawing the drop-down arrow. The arrow is drawn in ``ChevronComboBox``
  instead, and the native subcontrols are zero-sized so they cannot double up.

``letter-spacing`` and ``text-transform`` are *not* supported by Qt stylesheets;
tracking is applied through QFont in ``app.ui.fonts``.
"""
from __future__ import annotations

from string import Template

# ------------------------------------------------------------------ LIGHT ---
#: Cool paper, deliberately not warm: a warm cast interferes with judging the
#: colour of the image being compressed.
BG_APP = "#F0F1F3"
SURFACE = "#FFFFFF"
SURFACE_MUTED = "#E8EAED"
SURFACE_HOVER = "#E2E5E9"
SURFACE_PRESSED = "#D8DCE1"
SURFACE_SUNK = "#EDEFF2"
BORDER = "#D5D9DE"
BORDER_STRONG = "#B4BAC2"
DIVIDER = "#E4E7EA"

TEXT = "#191C21"
TEXT_STRONG = "#0F1216"
TEXT_SECONDARY = "#414852"
TEXT_MUTED = "#6B737E"
TEXT_FAINT = "#9AA1AB"

#: Vermilion — the red pencil of a proofreader. Single accent, used for action,
#: selection and the savings bar; never as decoration.
ACCENT = "#D23B16"
ACCENT_HOVER = "#B72F0E"
ACCENT_PRESSED = "#9C2609"
ACCENT_SOFT = "#FCEAE3"
ACCENT_SOFT_BORDER = "#F0B7A4"
ACCENT_SOFT_TEXT = "#A82A0C"
ACCENT_DISABLED = "#E5A794"
#: Text drawn *on* the accent.
ACCENT_ON = "#FFFFFF"

SUCCESS = "#0F7A3D"
SUCCESS_SOFT = "#E4F3EA"
WARNING = "#8A5A00"
WARNING_SOFT = "#FBF0DC"
DANGER = "#B3261E"
DANGER_SOFT = "#FBE7E5"
DANGER_SOFT_BORDER = "#E8A9A4"
NEUTRAL = "#8A929C"
NEUTRAL_SOFT = "#EEF0F2"

#: Halftone/grid painting colours (see widgets.HalftoneHeader).
HALFTONE_RGB = "120, 128, 138"
GRID_RGB = "154, 161, 171"

# ------------------------------------------------------------------- DARK ---
#: Charcoal, not black: pure #000000 eats the anti-aliasing of 1px strokes and
#: makes the vermilion glare.
DARK_BG_APP = "#14161A"
DARK_SURFACE = "#1B1E23"
DARK_SURFACE_MUTED = "#20242A"
DARK_SURFACE_HOVER = "#242830"
DARK_SURFACE_PRESSED = "#2A2F37"
DARK_SURFACE_SUNK = "#181B20"
DARK_BORDER = "#2C3138"
DARK_BORDER_STRONG = "#3D444D"
DARK_DIVIDER = "#242830"

DARK_TEXT = "#E4E6E9"
DARK_TEXT_STRONG = "#F5F6F8"
DARK_TEXT_SECONDARY = "#B9BFC8"
DARK_TEXT_MUTED = "#8A929C"
DARK_TEXT_FAINT = "#5C636D"

#: Brightened vermilion so it reads on charcoal; text flips to near-black.
DARK_ACCENT = "#FF6A45"
DARK_ACCENT_HOVER = "#FF8566"
DARK_ACCENT_PRESSED = "#E5542F"
DARK_ACCENT_SOFT = "#2A1A14"
DARK_ACCENT_SOFT_BORDER = "#7A3A28"
DARK_ACCENT_SOFT_TEXT = "#FFB59E"
DARK_ACCENT_DISABLED = "#6B3A2C"
DARK_ACCENT_ON = "#14161A"

DARK_SUCCESS = "#4ADE80"
DARK_SUCCESS_SOFT = "#16281E"
DARK_WARNING = "#FBBF24"
DARK_WARNING_SOFT = "#2A2312"
DARK_DANGER = "#F87171"
DARK_DANGER_SOFT = "#2A1719"
DARK_DANGER_SOFT_BORDER = "#7F3A3A"
DARK_NEUTRAL = "#6B737E"
DARK_NEUTRAL_SOFT = "#232830"

DARK_HALFTONE_RGB = "150, 158, 168"
DARK_GRID_RGB = "70, 78, 88"

#: Per-level log colours, tuned for the surface each is read on (all >= AA).
LOG_LEVEL_COLORS = {
    "info": TEXT_MUTED,
    "success": SUCCESS,
    "warning": WARNING,
    "error": DANGER,
}
DARK_LOG_LEVEL_COLORS = {
    "info": DARK_TEXT_MUTED,
    "success": DARK_SUCCESS,
    "warning": DARK_WARNING,
    "error": DARK_DANGER,
}

LIGHT_TOKENS: dict[str, str] = {
    "BG_APP": BG_APP, "SURFACE": SURFACE, "SURFACE_MUTED": SURFACE_MUTED,
    "SURFACE_HOVER": SURFACE_HOVER, "SURFACE_PRESSED": SURFACE_PRESSED,
    "SURFACE_SUNK": SURFACE_SUNK, "BORDER": BORDER, "BORDER_STRONG": BORDER_STRONG,
    "DIVIDER": DIVIDER, "TEXT": TEXT, "TEXT_STRONG": TEXT_STRONG,
    "TEXT_SECONDARY": TEXT_SECONDARY, "TEXT_MUTED": TEXT_MUTED, "TEXT_FAINT": TEXT_FAINT,
    "ACCENT": ACCENT, "ACCENT_HOVER": ACCENT_HOVER, "ACCENT_PRESSED": ACCENT_PRESSED,
    "ACCENT_SOFT": ACCENT_SOFT, "ACCENT_SOFT_BORDER": ACCENT_SOFT_BORDER,
    "ACCENT_SOFT_TEXT": ACCENT_SOFT_TEXT, "ACCENT_DISABLED": ACCENT_DISABLED,
    "ACCENT_ON": ACCENT_ON,
    "SUCCESS": SUCCESS, "SUCCESS_SOFT": SUCCESS_SOFT, "WARNING": WARNING,
    "WARNING_SOFT": WARNING_SOFT, "DANGER": DANGER, "DANGER_SOFT": DANGER_SOFT,
    "DANGER_SOFT_BORDER": DANGER_SOFT_BORDER, "NEUTRAL": NEUTRAL,
    "NEUTRAL_SOFT": NEUTRAL_SOFT,
    "HALFTONE_RGB": HALFTONE_RGB, "GRID_RGB": GRID_RGB,
}

DARK_TOKENS: dict[str, str] = {
    "BG_APP": DARK_BG_APP, "SURFACE": DARK_SURFACE, "SURFACE_MUTED": DARK_SURFACE_MUTED,
    "SURFACE_HOVER": DARK_SURFACE_HOVER, "SURFACE_PRESSED": DARK_SURFACE_PRESSED,
    "SURFACE_SUNK": DARK_SURFACE_SUNK, "BORDER": DARK_BORDER,
    "BORDER_STRONG": DARK_BORDER_STRONG, "DIVIDER": DARK_DIVIDER, "TEXT": DARK_TEXT,
    "TEXT_STRONG": DARK_TEXT_STRONG, "TEXT_SECONDARY": DARK_TEXT_SECONDARY,
    "TEXT_MUTED": DARK_TEXT_MUTED, "TEXT_FAINT": DARK_TEXT_FAINT,
    "ACCENT": DARK_ACCENT, "ACCENT_HOVER": DARK_ACCENT_HOVER,
    "ACCENT_PRESSED": DARK_ACCENT_PRESSED, "ACCENT_SOFT": DARK_ACCENT_SOFT,
    "ACCENT_SOFT_BORDER": DARK_ACCENT_SOFT_BORDER, "ACCENT_SOFT_TEXT": DARK_ACCENT_SOFT_TEXT,
    "ACCENT_DISABLED": DARK_ACCENT_DISABLED, "ACCENT_ON": DARK_ACCENT_ON,
    "SUCCESS": DARK_SUCCESS, "SUCCESS_SOFT": DARK_SUCCESS_SOFT, "WARNING": DARK_WARNING,
    "WARNING_SOFT": DARK_WARNING_SOFT, "DANGER": DARK_DANGER, "DANGER_SOFT": DARK_DANGER_SOFT,
    "DANGER_SOFT_BORDER": DARK_DANGER_SOFT_BORDER, "NEUTRAL": DARK_NEUTRAL,
    "NEUTRAL_SOFT": DARK_NEUTRAL_SOFT,
    "HALFTONE_RGB": DARK_HALFTONE_RGB, "GRID_RGB": DARK_GRID_RGB,
}

#: Sizes and radii, also used by widgets that paint themselves.
RADIUS_INPUT = 6
RADIUS_CARD = 10
RADIUS_CHIP = 5

_STYLESHEET = Template(
    r"""
/* ============================== base ============================== */
QMainWindow, QWidget#appRoot, QWidget#contentArea, QWidget#pageBody {
    background-color: $BG_APP;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}

QDialog, QMessageBox {
    background-color: $SURFACE;
}
QMessageBox QLabel {
    color: $TEXT;
    font-size: 13px;
}
QMessageBox QPushButton {
    min-width: 80px;
}

QToolTip {
    background-color: $TEXT_STRONG;
    color: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 4px;
    padding: 5px 9px;
    font-size: 12px;
}

/* ============================== top bar ========================== */
QFrame#topBar {
    background-color: $SURFACE;
    border: none;
    border-bottom: 1px solid $BORDER;
}

QLabel#brandMark {
    background-color: $ACCENT;
    color: $ACCENT_ON;
    border-radius: 5px;
    font-size: 14px;
    font-weight: 800;
}

QLabel#brandTitle {
    color: $TEXT_STRONG;
    font-size: 15px;
    font-weight: 700;
}

QLabel#brandSubtitle {
    color: $TEXT_MUTED;
    font-size: 11px;
}

QLabel#engineChip {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    border-radius: 4px;
    padding: 5px 9px;
    color: $TEXT_SECONDARY;
    font-size: 11px;
}

QPushButton#iconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0;
}
QPushButton#iconButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: $BORDER;
}
QPushButton#iconButton:checked {
    background-color: $ACCENT_SOFT;
    border-color: $ACCENT_SOFT_BORDER;
}

/* =============================== cards =========================== */
QFrame#card {
    background-color: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 10px;
}

QLabel#cardEyebrow {
    color: $ACCENT;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}

QLabel#cardTitle {
    color: $TEXT_STRONG;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}

QLabel#cardHint {
    color: $TEXT_MUTED;
    font-size: 11px;
    background: transparent;
}

QFrame#cardDivider {
    background-color: $DIVIDER;
    border: none;
}

QFrame#headerRule {
    background-color: $BORDER;
    border: none;
}

/* ============================== buttons ========================== */
QPushButton {
    background-color: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 6px;
    padding: 6px 12px;
    color: $TEXT_SECONDARY;
    font-weight: 500;
}
QPushButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: $TEXT_FAINT;
    color: $TEXT_STRONG;
}
QPushButton:pressed {
    background-color: $SURFACE_PRESSED;
}
QPushButton:focus {
    border-color: $ACCENT;
    outline: none;
}
QPushButton:disabled {
    background-color: $SURFACE_MUTED;
    color: $TEXT_FAINT;
    border-color: $DIVIDER;
}

QPushButton#primaryButton {
    background-color: $ACCENT;
    border: 1px solid $ACCENT;
    border-radius: 6px;
    padding: 9px 22px;
    color: $ACCENT_ON;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#primaryButton:hover {
    background-color: $ACCENT_HOVER;
    border-color: $ACCENT_HOVER;
}
QPushButton#primaryButton:pressed {
    background-color: $ACCENT_PRESSED;
    border-color: $ACCENT_PRESSED;
}
QPushButton#primaryButton:disabled {
    background-color: $ACCENT_DISABLED;
    border-color: $ACCENT_DISABLED;
    color: $ACCENT_ON;
}

QPushButton#cancelButton {
    padding: 9px 20px;
}
QPushButton#cancelButton:hover {
    background-color: $DANGER_SOFT;
    border-color: $DANGER_SOFT_BORDER;
    color: $DANGER;
}

QPushButton#softButton {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    color: $TEXT_SECONDARY;
}
QPushButton#softButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: $BORDER_STRONG;
    color: $TEXT_STRONG;
}

QPushButton#ghostButton {
    background-color: transparent;
    border: 1px solid transparent;
    color: $TEXT_MUTED;
    padding: 5px 9px;
}
QPushButton#ghostButton:hover {
    background-color: $SURFACE_HOVER;
    color: $TEXT_STRONG;
}

/* Segmented control: lossless / lossy, quality presets, scale presets. */
QPushButton#segmentButton {
    background-color: transparent;
    border: 1px solid $BORDER;
    border-radius: 5px;
    padding: 5px 12px;
    color: $TEXT_SECONDARY;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#segmentButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: $BORDER_STRONG;
    color: $TEXT_STRONG;
}
QPushButton#segmentButton:checked {
    background-color: $ACCENT_SOFT;
    border-color: $ACCENT_SOFT_BORDER;
    color: $ACCENT_SOFT_TEXT;
    font-weight: 600;
}
QPushButton#segmentButton:disabled {
    background-color: $SURFACE_MUTED;
    color: $TEXT_FAINT;
    border-color: $DIVIDER;
}

/* ============================== inputs =========================== */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 6px 9px;
    color: $TEXT;
    selection-background-color: $ACCENT;
    selection-color: $ACCENT_ON;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover {
    border-color: $BORDER_STRONG;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border-color: $ACCENT;
    background-color: $SURFACE;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QPlainTextEdit:disabled {
    background-color: $SURFACE_MUTED;
    color: $TEXT_FAINT;
    border-color: $DIVIDER;
}
QLineEdit::placeholder {
    color: $TEXT_FAINT;
}

/* Native subcontrols are zero-sized: ChevronComboBox / PlusMinusSpinBox draw
   their own glyphs, and leaving the originals visible would double them up. */
QComboBox {
    padding-right: 26px;
}
QComboBox::drop-down, QComboBox::down-arrow {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
    image: none;
}
QSpinBox {
    padding-right: 22px;
}
QSpinBox::up-button, QSpinBox::down-button,
QSpinBox::up-arrow, QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
    image: none;
}

QComboBox QAbstractItemView {
    background-color: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: $ACCENT_SOFT;
    selection-color: $ACCENT_SOFT_TEXT;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 9px;
    border-radius: 4px;
    color: $TEXT_SECONDARY;
}
QComboBox QAbstractItemView::item:hover {
    background-color: $SURFACE_HOVER;
    color: $TEXT_STRONG;
}

/* ============================ queue table ======================== */
QTableView#queueTable {
    background-color: transparent;
    border: none;
    gridline-color: transparent;
    outline: none;
    selection-background-color: transparent;
    alternate-background-color: transparent;
}
QTableView#queueTable::item {
    border: none;
    padding: 0;
}
QHeaderView {
    background-color: transparent;
    border: none;
}
QHeaderView::section {
    background-color: $SURFACE_SUNK;
    color: $TEXT_MUTED;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 600;
}
QHeaderView::section:first {
    border-top-left-radius: 6px;
}
QHeaderView::section:last {
    border-top-right-radius: 6px;
}
QTableCornerButton::section {
    background-color: $SURFACE_SUNK;
    border: none;
    border-bottom: 1px solid $BORDER;
}

/* ============================== labels =========================== */
QLabel {
    background: transparent;
    color: $TEXT;
}

QLabel#fieldLabel {
    color: $TEXT_SECONDARY;
    font-size: 12px;
    font-weight: 500;
}

QLabel#microLabel {
    color: $TEXT_MUTED;
    font-size: 10px;
    font-weight: 700;
}

QLabel#mutedLabel {
    color: $TEXT_MUTED;
    font-size: 11px;
}

QLabel#monoValue {
    color: $TEXT_SECONDARY;
    font-size: 12px;
}

QLabel#statValue {
    color: $TEXT_STRONG;
    font-size: 26px;
    font-weight: 700;
}

QLabel#statCaption {
    color: $TEXT_MUTED;
    font-size: 11px;
}

QLabel#statusLabel {
    color: $TEXT_SECONDARY;
    font-size: 12px;
}

QLabel#valueBadge {
    background-color: $ACCENT_SOFT;
    border: 1px solid $ACCENT_SOFT_BORDER;
    border-radius: 4px;
    padding: 1px 7px;
    color: $ACCENT_SOFT_TEXT;
    font-size: 11px;
    font-weight: 600;
}

QLabel#idleBadge {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    border-radius: 4px;
    padding: 1px 7px;
    color: $TEXT_MUTED;
    font-size: 11px;
}

QLabel#noteLabel {
    background-color: $WARNING_SOFT;
    border: 1px solid $WARNING;
    border-radius: 5px;
    padding: 6px 9px;
    color: $WARNING;
    font-size: 11px;
}

QLabel#logTitle {
    color: $TEXT_STRONG;
    font-size: 13px;
    font-weight: 700;
}

/* ============================== drop zone ======================== */
QFrame#dropZone {
    background-color: $SURFACE_SUNK;
    border: 1px dashed $BORDER_STRONG;
    border-radius: 8px;
}
QFrame#dropZone[state="active"] {
    background-color: $ACCENT_SOFT;
    border: 1px dashed $ACCENT;
}
QLabel#dropZoneTitle {
    color: $TEXT_SECONDARY;
    font-size: 12px;
    font-weight: 600;
}
QLabel#dropZoneHint {
    color: $TEXT_MUTED;
    font-size: 11px;
}

/* ============================== preview ========================== */
QFrame#previewStage {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 8px;
}
QLabel#previewCaption {
    color: $TEXT_MUTED;
    font-size: 11px;
}

/* ============================= progress ========================== */
QProgressBar {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background-color: $ACCENT;
    border-radius: 2px;
}
QProgressBar[state="done"]::chunk {
    background-color: $SUCCESS;
}
QProgressBar[state="failed"]::chunk {
    background-color: $DANGER;
}

/* ============================== slider =========================== */
QSlider {
    background: transparent;
    min-height: 22px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: $SURFACE_PRESSED;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: $ACCENT;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: $SURFACE_PRESSED;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: $SURFACE;
    border: 2px solid $ACCENT;
    width: 13px;
    height: 13px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: $ACCENT_SOFT;
}
QSlider::handle:horizontal:pressed {
    background: $ACCENT;
}
QSlider:disabled::handle:horizontal {
    border-color: $NEUTRAL;
    background: $SURFACE_MUTED;
}
QSlider:disabled::sub-page:horizontal {
    background: $BORDER_STRONG;
}

/* ============================= checkbox ========================== */
QCheckBox {
    background: transparent;
    color: $TEXT_SECONDARY;
    font-size: 12px;
    spacing: 7px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid $BORDER_STRONG;
    border-radius: 3px;
    background-color: $SURFACE;
}
QCheckBox::indicator:hover {
    border-color: $ACCENT;
}
QCheckBox::indicator:checked {
    background-color: $ACCENT;
    border-color: $ACCENT;
    image: none;
}
QCheckBox::indicator:disabled {
    background-color: $SURFACE_MUTED;
    border-color: $DIVIDER;
}

/* =============================== lists =========================== */
QListWidget {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 5px;
    outline: none;
}
QListWidget::item {
    padding: 6px 9px;
    border-radius: 5px;
    color: $TEXT_SECONDARY;
}
QListWidget::item:hover {
    background-color: $SURFACE_HOVER;
    color: $TEXT_STRONG;
}
QListWidget::item:selected {
    background-color: $ACCENT_SOFT;
    color: $ACCENT_SOFT_TEXT;
}

/* ============================== log view ========================= */
QPlainTextEdit#logView {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 6px;
    padding: 8px 10px;
    color: $TEXT_SECONDARY;
    font-size: 12px;
}

/* ============================= scrollbars ======================== */
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px 0;
}
QScrollBar::handle:vertical {
    background: $BORDER_STRONG;
    min-height: 32px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: $TEXT_FAINT;
}
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
    margin: 0 2px;
}
QScrollBar::handle:horizontal {
    background: $BORDER_STRONG;
    min-width: 32px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: $TEXT_FAINT;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: transparent;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

/* ============================ status bar ========================= */
QFrame#statusBar {
    background-color: $SURFACE;
    border: none;
    border-top: 1px solid $BORDER;
}
QLabel#statusBarText {
    color: $TEXT_MUTED;
    font-size: 11px;
}
QLabel#statusBarValue {
    color: $TEXT_SECONDARY;
    font-size: 11px;
    font-weight: 600;
}
QLabel#statusBarAccent {
    color: $ACCENT_SOFT_TEXT;
    font-size: 11px;
    font-weight: 700;
}

/* ============================ toast ============================== */
QFrame#toast {
    background-color: $TEXT_STRONG;
    border: 1px solid $BORDER_STRONG;
    border-radius: 7px;
}
QLabel#toastText {
    color: $SURFACE;
    font-size: 12px;
}
"""
)


def tokens_for(mode: str) -> dict[str, str]:
    return DARK_TOKENS if mode == "dark" else LIGHT_TOKENS


def build_stylesheet(mode: str = "light") -> str:
    """Generate the QSS for ``mode`` ("light" / "dark")."""
    return _STYLESHEET.substitute(tokens_for(mode))


def log_level_colors(mode: str) -> dict[str, str]:
    return DARK_LOG_LEVEL_COLORS if mode == "dark" else LOG_LEVEL_COLORS


APP_STYLESHEET = build_stylesheet("light")
DARK_APP_STYLESHEET = build_stylesheet("dark")

_current_mode = "light"


def current_mode() -> str:
    """Last applied mode, for widgets that paint themselves."""
    return _current_mode


def set_current_mode(mode: str) -> None:
    global _current_mode
    if mode not in ("light", "dark"):
        raise ValueError(f"unknown theme mode: {mode}")
    _current_mode = mode


def resolve_mode(mode: str, resolved: str | None = None) -> str:
    """Collapse "system" into a concrete "light" / "dark"."""
    if mode != "system":
        return mode
    if resolved in ("light", "dark"):
        return resolved
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    return "light"


def build_palette(mode: str = "light"):
    """QPalette matching the tokens, so native dialogs match the theme."""
    from PySide6.QtGui import QColor, QPalette

    tokens = tokens_for(mode)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens["BG_APP"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["TEXT"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens["SURFACE"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["SURFACE_MUTED"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens["TEXT"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens["SURFACE"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["TEXT_SECONDARY"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(tokens["ACCENT_ON"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["ACCENT"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["ACCENT_ON"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens["TEXT_STRONG"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens["SURFACE"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["TEXT_FAINT"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(tokens["ACCENT"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(tokens["BORDER_STRONG"]))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(tokens["DIVIDER"]))
    palette.setColor(QPalette.ColorRole.Light, QColor(tokens["SURFACE"]))
    palette.setColor(QPalette.ColorRole.Dark, QColor(tokens["BORDER_STRONG"]))

    disabled = QPalette.ColorGroup.Disabled
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(disabled, role, QColor(tokens["TEXT_FAINT"]))
    palette.setColor(disabled, QPalette.ColorRole.Base, QColor(tokens["SURFACE_MUTED"]))
    palette.setColor(disabled, QPalette.ColorRole.Button, QColor(tokens["SURFACE_MUTED"]))
    palette.setColor(disabled, QPalette.ColorRole.Highlight, QColor(tokens["BORDER_STRONG"]))
    return palette


def apply_app_theme(app, mode: str = "light", resolved: str | None = None) -> str:
    """Apply Fusion + palette + fonts + stylesheet. Returns the concrete mode.

    Safe to call again at runtime for a live theme switch.
    """
    from . import fonts

    concrete = resolve_mode(mode, resolved)
    set_current_mode(concrete)
    fonts.load_bundled_fonts()

    app.setStyle("Fusion")
    app.setPalette(build_palette(concrete))
    app.setFont(fonts.make_font(size=10))
    app.setStyleSheet(build_stylesheet(concrete))
    repolish(app)
    return concrete


def repolish(app) -> None:
    """Force live widgets to re-read the stylesheet immediately."""
    for widget in app.allWidgets():
        if widget is None:
            continue
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
    for window in app.topLevelWidgets():
        if window is not None:
            window.update()
