"""Fluent — the PixelPress design system: tokens, stylesheet, palette.

The identity is "Fluent tool": layered acrylic surfaces, deep blue-purple
accent, ink-on-paper text contrast, with cards and chips as the only
decorative motif. Born on Windows 11, the visual language blends with the
host system so the app reads as a native tool, not a styled overlay.

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

A module-level QColor cache (``color_for``) keeps paintEvent fast: tokens are
resolved to QColor once per (key, mode) and reused until the mode flips,
which is the single fix for the theme-switch / drag-seam stutter that came
from ``QColor(tokens[...])`` running on every paint frame.
"""
from __future__ import annotations

from string import Template

# ------------------------------------------------------------------ LIGHT ---
#: Cool blue-grey acrylic, deliberately not warm: a warm cast interferes with
#: judging the colour of the image being compressed.
BG_APP = "#EEF3FA"
SURFACE = "#FFFFFF"
SURFACE_MUTED = "#E6EEF8"
SURFACE_HOVER = "#D9E5F4"
SURFACE_PRESSED = "#C5D6EE"
SURFACE_SUNK = "#F2F6FB"
BORDER = "#C8D6E6"
BORDER_STRONG = "#9DB3D0"
DIVIDER = "#D9E2EF"

TEXT = "#1E2A3D"
TEXT_STRONG = "#0C1A2E"
TEXT_SECONDARY = "#3B4D6B"
TEXT_MUTED = "#6B7B95"
TEXT_FAINT = "#99A6BC"

#: Blue-purple — the signal accent of a Fluent tool. Single accent, used for
#: action, selection and the savings bar; never as decoration.
ACCENT = "#185FA5"
ACCENT_HOVER = "#0C447C"
ACCENT_PRESSED = "#042C53"
ACCENT_SOFT = "#E6F1FB"
ACCENT_SOFT_BORDER = "#85B7EB"
ACCENT_SOFT_TEXT = "#0C447C"
ACCENT_DISABLED = "#9DB3D0"
#: Text drawn *on* the accent.
ACCENT_ON = "#FFFFFF"

SUCCESS = "#0F6E56"
SUCCESS_SOFT = "#E1F5EE"
WARNING = "#854F0B"
WARNING_SOFT = "#FAEEDA"
DANGER = "#C83838"
DANGER_SOFT = "#FCEBEB"
DANGER_SOFT_BORDER = "#F09595"
NEUTRAL = "#5F5E5A"
NEUTRAL_SOFT = "#F1EFE8"

#: Layer / grid tints (kept for backward compatibility with widgets that
#: still reference them; halftone decoration is retired in Fluent direction).
HALFTONE_RGB = "24, 95, 165"
GRID_RGB = "157, 179, 208"

# ------------------------------------------------------------------- DARK ---
#: Deep blue-charcoal, not pure black: pure #000000 eats the anti-aliasing of
#: 1px strokes and makes the accent glare.
DARK_BG_APP = "#0A1426"
DARK_SURFACE = "#131F36"
DARK_SURFACE_MUTED = "#1A2742"
DARK_SURFACE_HOVER = "#21314F"
DARK_SURFACE_PRESSED = "#2A3D5E"
DARK_SURFACE_SUNK = "#0F1A2E"
DARK_BORDER = "#2A3D5E"
DARK_BORDER_STRONG = "#3D5478"
DARK_DIVIDER = "#1A2742"

DARK_TEXT = "#D9E2F2"
DARK_TEXT_STRONG = "#F0F4FB"
DARK_TEXT_SECONDARY = "#B5C3D9"
DARK_TEXT_MUTED = "#8A9BB5"
DARK_TEXT_FAINT = "#5A6B85"

#: Brightened blue-purple so it reads on charcoal; text flips to deep ink.
DARK_ACCENT = "#4A90E2"
DARK_ACCENT_HOVER = "#6BA5E8"
DARK_ACCENT_PRESSED = "#378ADD"
DARK_ACCENT_SOFT = "#1A2742"
DARK_ACCENT_SOFT_BORDER = "#3D5478"
DARK_ACCENT_SOFT_TEXT = "#B5C3D9"
DARK_ACCENT_DISABLED = "#2A3D5E"
DARK_ACCENT_ON = "#0A1426"

DARK_SUCCESS = "#5DCAA5"
DARK_SUCCESS_SOFT = "#0C2A1F"
DARK_WARNING = "#FAC775"
DARK_WARNING_SOFT = "#2A2312"
DARK_DANGER = "#F09595"
DARK_DANGER_SOFT = "#2A1719"
DARK_DANGER_SOFT_BORDER = "#7F3A3A"
DARK_NEUTRAL = "#5A6B85"
DARK_NEUTRAL_SOFT = "#1A2742"

DARK_HALFTONE_RGB = "150, 158, 168"
DARK_GRID_RGB = "61, 84, 120"

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
    "SLIDER_TRACK": SURFACE_PRESSED,
    "SLIDER_FILL": ACCENT,
    "SLIDER_HANDLE": SURFACE,
    "SLIDER_HANDLE_RING": ACCENT,
    "SLIDER_HANDLE_HOVER": ACCENT_SOFT,
    "SLIDER_HANDLE_PRESSED": ACCENT,
    "SLIDER_TICK": TEXT_FAINT,
    "SLIDER_TICK_ACTIVE": TEXT_MUTED,
    "SLIDER_DEFAULT_MARKER": TEXT_MUTED,
    "SLIDER_BUBBLE_BG": TEXT_STRONG,
    "SLIDER_BUBBLE_BORDER": BORDER_STRONG,
    "SLIDER_BUBBLE_TEXT": SURFACE,
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
    "SLIDER_TRACK": DARK_SURFACE_PRESSED,
    "SLIDER_FILL": DARK_ACCENT,
    "SLIDER_HANDLE": DARK_SURFACE,
    "SLIDER_HANDLE_RING": DARK_ACCENT,
    "SLIDER_HANDLE_HOVER": DARK_ACCENT_SOFT,
    "SLIDER_HANDLE_PRESSED": DARK_ACCENT,
    "SLIDER_TICK": DARK_TEXT_FAINT,
    "SLIDER_TICK_ACTIVE": DARK_TEXT_MUTED,
    "SLIDER_DEFAULT_MARKER": DARK_TEXT_MUTED,
    "SLIDER_BUBBLE_BG": DARK_TEXT_STRONG,
    "SLIDER_BUBBLE_BORDER": DARK_BORDER_STRONG,
    "SLIDER_BUBBLE_TEXT": DARK_SURFACE,
}

#: Sizes and radii, also used by widgets that paint themselves.
#: Fluent favours slightly larger radii for layered card surfaces.
RADIUS_INPUT = 6
RADIUS_CARD = 12
RADIUS_CHIP = 6

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
    border-radius: 6px;
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
    border-radius: 12px;
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
    background-color: $DANGER_SOFT;
    border: 1px solid $DANGER_SOFT_BORDER;
    border-radius: 6px;
    padding: 9px 16px;
    color: $DANGER;
    font-weight: 600;
}
QPushButton#cancelButton:hover {
    background-color: $DANGER;
    border-color: $DANGER;
    color: $ACCENT_ON;
}
QPushButton#cancelButton:pressed {
    background-color: $DANGER_SOFT_BORDER;
    border-color: $DANGER_SOFT_BORDER;
    color: $DANGER;
}
QPushButton#cancelButton:disabled {
    background-color: $SURFACE_MUTED;
    border-color: $DIVIDER;
    color: $TEXT_FAINT;
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
    border-radius: 6px;
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
   their own glyphs, and leaving the originals visible would double them up.
   PlusMinusSpinBox keeps the button *symbols* registered on purpose: with
   NoButtons, QStyleSheetStyle collapses its internal line edit to 1 px and the
   value disappears. QSS only controls the size, not the symbol setting. */
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
    padding: 6px 9px;
}
QSpinBox::up-button, QSpinBox::down-button,
QSpinBox::up-arrow, QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
    image: none;
}
/* The numeric readout beside a slider is a value, not a form field; a filled
   box made the slider row look like two unrelated controls. Keep it transparent
   and use a hairline only on hover/focus. */
QSpinBox {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
}
QSpinBox:hover {
    background: transparent;
    border-color: $BORDER;
}
QSpinBox:focus {
    background: transparent;
    border-color: $ACCENT;
}
QSpinBox:disabled {
    background: transparent;
    border-color: transparent;
    color: $TEXT_FAINT;
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

QLabel#stateBadge {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    border-radius: 4px;
    padding: 2px 8px;
    color: $TEXT_MUTED;
    font-size: 11px;
    font-weight: 600;
}
QLabel#stateBadge[state="running"] {
    background-color: $ACCENT_SOFT;
    border-color: $ACCENT_SOFT_BORDER;
    color: $ACCENT_SOFT_TEXT;
}
QLabel#stateBadge[state="cancelling"] {
    background-color: $WARNING_SOFT;
    border-color: $WARNING;
    color: $WARNING;
}
QLabel#stateBadge[state="done"] {
    background-color: $SUCCESS_SOFT;
    border-color: $SUCCESS;
    color: $SUCCESS;
}
QLabel#stateBadge[state="cancelled"] {
    background-color: $NEUTRAL_SOFT;
    border-color: $BORDER_STRONG;
    color: $TEXT_SECONDARY;
}

QLabel#noteLabel {
    background-color: $WARNING_SOFT;
    border: 1px solid $WARNING;
    border-radius: 6px;
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
QAbstractScrollArea#previewStage {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 8px;
}
QAbstractScrollArea#previewStage > QWidget > QWidget {
    background: transparent;
}
QFrame#previewStage {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 8px;
}
QLabel#previewCaption {
    color: $TEXT_MUTED;
    font-size: 11px;
}

/* ============================= splitters ========================= */
QSplitter {
    background: transparent;
}
QSplitter::handle {
    background: transparent;
}
QSplitter::handle:hover {
    background: $SURFACE_HOVER;
    border-radius: 3px;
}
QSplitter::handle:pressed {
    background: $ACCENT_SOFT;
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
QProgressBar[state="running"]::chunk {
    background-color: $ACCENT;
}
QProgressBar[state="cancelling"]::chunk {
    background-color: $WARNING;
}
QProgressBar[state="cancelled"]::chunk {
    background-color: $NEUTRAL;
}
QProgressBar[state="done"]::chunk {
    background-color: $SUCCESS;
}
QProgressBar[state="failed"]::chunk {
    background-color: $DANGER;
}

/* ============================== slider =========================== */
/* PressSlider subclasses QSlider and paints itself in paintEvent. The native
   sub-controls (groove / handle) are *not* zeroed here: zeroing them breaks
   QStyle::sliderValueFromPosition, which QSlider's mousePressEvent used to
   rely on. PressSlider now overrides mousePressEvent to use its own
   _x_to_value mapping (see widgets.PressSlider), so the look and the click
   behaviour are both custom — but the canvas still needs to be transparent so
   Qt does not paint a grey slab behind the hand-drawn track. */
QSlider {
    background: transparent;
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
    border-radius: 6px;
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


# ----------------------------------------------------- QColor cache layer ---
#: Resolved QColor instances are cached per (key, mode) so paintEvent never
#: pays for QColor parsing on every frame. The cache is invalidated as a whole
#: whenever the mode flips — see ``set_current_mode``.
_color_cache: dict[tuple[str, str], object] = {}


def color_for(key: str, mode: str | None = None) -> object:
    """Return a cached ``QColor`` for ``key`` under ``mode`` (default current).

    Widgets should call this instead of ``QColor(tokens_for(mode)[key])`` so
    the per-frame QColor allocation that caused theme-switch / drag-seam stutter
    is amortised to one allocation per (key, mode) pair.
    """
    from PySide6.QtGui import QColor

    if mode is None:
        mode = _current_mode
    cache_key = (key, mode)
    cached = _color_cache.get(cache_key)
    if cached is not None:
        return cached
    tokens = tokens_for(mode)
    if key not in tokens:
        raise KeyError(f"unknown theme token: {key}")
    resolved = QColor(tokens[key])
    _color_cache[cache_key] = resolved
    return resolved


def _invalidate_color_cache() -> None:
    """Drop every cached QColor — called when the active mode changes."""
    _color_cache.clear()


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
    if mode != _current_mode:
        _invalidate_color_cache()
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
    """Force live widgets to re-read the stylesheet immediately.

    The previous implementation iterated every widget in the application and
    ran ``unpolish`` / ``polish`` / ``update`` on each — the single biggest
    cause of theme-switch lag on a populated main window. Polish is only
    needed where a styled widget subclass keeps internal state; for a normal
    QSS refresh Qt already re-evaluates rules on ``setStyleSheet``. We keep
    the unpolish/polish pair only on top-level windows (the small set that
    actually holds the QSS context) and rely on a single ``update`` sweep
    over visible children. ``instantiate_widgets`` is rare; live switches are
    not, so optimising for the switch path is the right trade.
    """
    for window in app.topLevelWidgets():
        if window is None:
            continue
        style = window.style()
        style.unpolish(window)
        style.polish(window)
        window.update()
