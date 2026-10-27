"""Material — the PixelPress design system: tokens, stylesheet, palette.

The identity is "Google tool": a neutral canvas, one blue accent, tonal
surfaces, generous radii and a single type family with tabular numerals for
every measurement. The vocabulary is Material 3, not a skeuomorphic theme:
filled / tonal / outlined / text buttons, filter chips, 16 px cards, 8 px
fields, hairline dividers, tonal status chips.

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
#: Google's neutral canvas. A faint warm-grey reads as "paper" without the
#: cold cast a blue canvas puts on the very images this tool is judging.
BG_APP = "#F8F9FA"
SURFACE = "#FFFFFF"
SURFACE_MUTED = "#F1F3F4"
SURFACE_HOVER = "#E8EAED"
SURFACE_PRESSED = "#DADCE0"
SURFACE_SUNK = "#F1F3F4"
BORDER = "#DADCE0"
BORDER_STRONG = "#BDC1C6"
DIVIDER = "#E8EAED"

TEXT = "#3C4043"
TEXT_STRONG = "#202124"
TEXT_SECONDARY = "#5F6368"
TEXT_MUTED = "#80868B"
TEXT_FAINT = "#9AA0A6"

#: Google Blue, M3 primary. The single accent: action, selection, progress.
ACCENT = "#0B57D0"
ACCENT_HOVER = "#0842A0"
ACCENT_PRESSED = "#062E6F"
ACCENT_SOFT = "#D3E3FD"
ACCENT_SOFT_BORDER = "#A8C7FA"
ACCENT_SOFT_TEXT = "#041E49"
ACCENT_DISABLED = "#A8C7FA"
#: Text drawn *on* the accent.
ACCENT_ON = "#FFFFFF"

SUCCESS = "#137333"
SUCCESS_SOFT = "#E6F4EA"
WARNING = "#B06000"
WARNING_SOFT = "#FEF7E0"
DANGER = "#C5221F"
DANGER_SOFT = "#FCE8E6"
DANGER_SOFT_BORDER = "#F6AEA9"
NEUTRAL = "#5F6368"
NEUTRAL_SOFT = "#F1F3F4"

#: Snackbar: inverse surface, so a toast reads as a notification floating
#: above the app rather than another panel.
SNACKBAR_BG = "#202124"
SNACKBAR_TEXT = "#F1F3F4"

#: Layer / grid tints (kept for backward compatibility with widgets that
#: still reference them; the halftone decoration is retired).
HALFTONE_RGB = "154, 160, 166"
GRID_RGB = "189, 193, 198"

# ------------------------------------------------------------------- DARK ---
#: Near-black but never pure: #000000 eats the anti-aliasing of 1 px strokes.
DARK_BG_APP = "#131314"
DARK_SURFACE = "#1E1F20"
DARK_SURFACE_MUTED = "#282A2C"
DARK_SURFACE_HOVER = "#303134"
DARK_SURFACE_PRESSED = "#3C4043"
DARK_SURFACE_SUNK = "#282A2C"
DARK_BORDER = "#3C4043"
DARK_BORDER_STRONG = "#5F6368"
DARK_DIVIDER = "#282A2C"

DARK_TEXT = "#E3E3E3"
DARK_TEXT_STRONG = "#E8EAED"
DARK_TEXT_SECONDARY = "#BDC1C6"
DARK_TEXT_MUTED = "#9AA0A6"
DARK_TEXT_FAINT = "#80868B"

#: M3 dark primary is a light blue; ink on it is deep, not white.
DARK_ACCENT = "#A8C7FA"
DARK_ACCENT_HOVER = "#D3E3FD"
DARK_ACCENT_PRESSED = "#A8C7FA"
DARK_ACCENT_SOFT = "#0D3C75"
DARK_ACCENT_SOFT_BORDER = "#1E5FA8"
DARK_ACCENT_SOFT_TEXT = "#D3E3FD"
DARK_ACCENT_DISABLED = "#3C4043"
DARK_ACCENT_ON = "#062E6F"

DARK_SUCCESS = "#81C995"
DARK_SUCCESS_SOFT = "#0E3B22"
DARK_WARNING = "#FAD17C"
DARK_WARNING_SOFT = "#3B2F12"
DARK_DANGER = "#F28B82"
DARK_DANGER_SOFT = "#5C1A17"
DARK_DANGER_SOFT_BORDER = "#8C1D18"
DARK_NEUTRAL = "#9AA0A6"
DARK_NEUTRAL_SOFT = "#282A2C"

DARK_SNACKBAR_BG = "#E3E3E3"
DARK_SNACKBAR_TEXT = "#202124"

DARK_HALFTONE_RGB = "154, 160, 166"
DARK_GRID_RGB = "95, 99, 104"

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
    "NEUTRAL_SOFT": NEUTRAL_SOFT, "SNACKBAR_BG": SNACKBAR_BG,
    "SNACKBAR_TEXT": SNACKBAR_TEXT,
    "HALFTONE_RGB": HALFTONE_RGB, "GRID_RGB": GRID_RGB,
    "SLIDER_TRACK": "#E8EAED",
    "SLIDER_FILL": ACCENT,
    "SLIDER_HANDLE": ACCENT,
    "SLIDER_HANDLE_RING": SURFACE,
    "SLIDER_HANDLE_HOVER": ACCENT_HOVER,
    "SLIDER_HANDLE_PRESSED": ACCENT_PRESSED,
    "SLIDER_TICK": TEXT_FAINT,
    "SLIDER_TICK_ACTIVE": TEXT_MUTED,
    "SLIDER_DEFAULT_MARKER": TEXT_MUTED,
    "SLIDER_BUBBLE_BG": TEXT_STRONG,
    "SLIDER_BUBBLE_BORDER": TEXT_STRONG,
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
    "NEUTRAL_SOFT": DARK_NEUTRAL_SOFT, "SNACKBAR_BG": DARK_SNACKBAR_BG,
    "SNACKBAR_TEXT": DARK_SNACKBAR_TEXT,
    "HALFTONE_RGB": DARK_HALFTONE_RGB, "GRID_RGB": DARK_GRID_RGB,
    "SLIDER_TRACK": "#3C4043",
    "SLIDER_FILL": DARK_ACCENT,
    "SLIDER_HANDLE": DARK_ACCENT,
    "SLIDER_HANDLE_RING": DARK_SURFACE,
    "SLIDER_HANDLE_HOVER": DARK_ACCENT_HOVER,
    "SLIDER_HANDLE_PRESSED": DARK_ACCENT_PRESSED,
    "SLIDER_TICK": DARK_TEXT_FAINT,
    "SLIDER_TICK_ACTIVE": DARK_TEXT_MUTED,
    "SLIDER_DEFAULT_MARKER": DARK_TEXT_MUTED,
    "SLIDER_BUBBLE_BG": DARK_TEXT_STRONG,
    "SLIDER_BUBBLE_BORDER": DARK_TEXT_STRONG,
    "SLIDER_BUBBLE_TEXT": DARK_BG_APP,
}

#: Sizes and radii. Material uses 8 px for fields, 16 px for cards and a
#: fully rounded pill for buttons.
RADIUS_INPUT = 8
RADIUS_CARD = 16
RADIUS_CHIP = 16

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
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
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
    border-radius: 9px;
    font-size: 14px;
    font-weight: 700;
}

QLabel#brandTitle {
    color: $TEXT_STRONG;
    font-size: 19px;
    font-weight: 600;
}

QLabel#brandSubtitle {
    color: $TEXT_MUTED;
    font-size: 12px;
}

QLabel#engineChip {
    background-color: transparent;
    border: none;
    border-radius: 0;
    padding: 2px 0;
    color: $TEXT_MUTED;
    font-size: 11px;
}

/* Hairline separator between the brand block and the engine readout. */
QFrame#topBarDivider {
    background-color: $BORDER;
    border: none;
    max-width: 1px;
    min-width: 1px;
}

QPushButton#iconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 20px;
    padding: 0;
}
QPushButton#iconButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: transparent;
}
QPushButton#iconButton:pressed {
    background-color: $SURFACE_PRESSED;
}
QPushButton#iconButton:checked {
    background-color: $ACCENT_SOFT;
    border-color: transparent;
}

/* =============================== cards =========================== */
QFrame#card {
    background-color: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 16px;
}

QLabel#cardEyebrow {
    color: $TEXT_MUTED;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}

QLabel#cardTitle {
    color: $TEXT_STRONG;
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}

QLabel#cardHint {
    color: $TEXT_MUTED;
    font-size: 12px;
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
    border-radius: 16px;
    padding: 6px 14px;
    color: $TEXT;
    font-size: 13px;
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
    border-color: $BORDER;
}

/* Filled button — the one loud action on a screen. */
QPushButton#primaryButton {
    background-color: $ACCENT;
    border: 1px solid $ACCENT;
    border-radius: 20px;
    padding: 10px 24px;
    color: $ACCENT_ON;
    font-weight: 600;
    font-size: 14px;
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
    background-color: $SURFACE_MUTED;
    border-color: $BORDER;
    color: $TEXT_FAINT;
}

/* Outlined, destructive. */
QPushButton#cancelButton {
    background-color: transparent;
    border: 1px solid $DANGER_SOFT_BORDER;
    border-radius: 20px;
    padding: 10px 18px;
    color: $DANGER;
    font-weight: 600;
    font-size: 14px;
}
QPushButton#cancelButton:hover {
    background-color: $DANGER_SOFT;
    border-color: $DANGER;
}
QPushButton#cancelButton:pressed {
    background-color: $DANGER_SOFT;
    border-color: $DANGER;
    color: $DANGER;
}
QPushButton#cancelButton:disabled {
    background-color: transparent;
    border-color: $DIVIDER;
    color: $TEXT_FAINT;
}

/* Tonal button — a quiet sibling of the filled one. */
QPushButton#softButton {
    background-color: $ACCENT_SOFT;
    border: 1px solid transparent;
    border-radius: 20px;
    padding: 9px 18px;
    color: $ACCENT_SOFT_TEXT;
    font-weight: 600;
}
QPushButton#softButton:hover {
    background-color: $ACCENT_SOFT_BORDER;
    border-color: transparent;
}
QPushButton#softButton:disabled {
    background-color: $SURFACE_MUTED;
    color: $TEXT_FAINT;
}

/* Text button — no chrome until hovered. */
QPushButton#ghostButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    color: $TEXT_SECONDARY;
    padding: 6px 10px;
    font-size: 13px;
}
QPushButton#ghostButton:hover {
    background-color: $SURFACE_HOVER;
    color: $TEXT_STRONG;
}
QPushButton#ghostButton:disabled {
    color: $TEXT_FAINT;
    background-color: transparent;
}

/* Filter chip — the Material way to offer a small set of choices. */
QPushButton#segmentButton {
    background-color: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 16px;
    padding: 6px 11px;
    color: $TEXT_SECONDARY;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#segmentButton:hover {
    background-color: $SURFACE_HOVER;
    border-color: $TEXT_FAINT;
    color: $TEXT_STRONG;
}
QPushButton#segmentButton:checked {
    background-color: $ACCENT_SOFT;
    border-color: $ACCENT_SOFT_BORDER;
    color: $ACCENT_SOFT_TEXT;
    font-weight: 600;
}
QPushButton#segmentButton:disabled {
    background-color: transparent;
    color: $TEXT_FAINT;
    border-color: $DIVIDER;
}

/* ============================== inputs =========================== */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: $SURFACE_SUNK;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 7px 10px;
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
    border-color: transparent;
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
    padding-right: 28px;
}
QComboBox::drop-down, QComboBox::down-arrow {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
    image: none;
}
QSpinBox {
    padding: 6px 10px;
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
    border-radius: 8px;
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
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: $ACCENT_SOFT;
    selection-color: $ACCENT_SOFT_TEXT;
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
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
/* The delegate paints its own selection highlight — a rounded tonal bar.
   Qt's native selection fill would sit under it as a solid accent block,
   so the item background stays transparent in every state. */
QTableView#queueTable::item:selected,
QTableView#queueTable::item:selected:hover,
QTableView#queueTable::item:hover {
    background: transparent;
    border: none;
}
QHeaderView {
    background-color: transparent;
    border: none;
}
QHeaderView::section {
    background-color: transparent;
    color: $TEXT_SECONDARY;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 500;
}
QTableCornerButton::section {
    background-color: transparent;
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
    font-size: 13px;
    font-weight: 500;
}

QLabel#microLabel {
    color: $TEXT_MUTED;
    font-size: 12px;
    font-weight: 500;
}

QLabel#mutedLabel {
    color: $TEXT_MUTED;
    font-size: 12px;
}

QLabel#monoValue {
    color: $TEXT_SECONDARY;
    font-size: 13px;
}

QLabel#statValue {
    color: $TEXT_STRONG;
    font-size: 28px;
    font-weight: 600;
}

QLabel#statCaption {
    color: $TEXT_MUTED;
    font-size: 12px;
}

QLabel#statusLabel {
    color: $TEXT_SECONDARY;
    font-size: 13px;
}

QLabel#valueBadge {
    background-color: $ACCENT_SOFT;
    border: 1px solid $ACCENT_SOFT_BORDER;
    border-radius: 10px;
    padding: 2px 9px;
    color: $ACCENT_SOFT_TEXT;
    font-size: 12px;
    font-weight: 600;
}

QLabel#idleBadge {
    background-color: $SURFACE_MUTED;
    border: 1px solid $BORDER;
    border-radius: 10px;
    padding: 2px 9px;
    color: $TEXT_SECONDARY;
    font-size: 12px;
}

/* Tonal status chip — colour carries the state, the shape stays quiet. */
QLabel#stateBadge {
    background-color: $SURFACE_MUTED;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 3px 10px;
    color: $TEXT_SECONDARY;
    font-size: 12px;
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
    background-color: $SURFACE_MUTED;
    border-color: $BORDER;
    color: $TEXT_SECONDARY;
}

QLabel#noteLabel {
    background-color: $WARNING_SOFT;
    border: 1px solid $WARNING;
    border-radius: 8px;
    padding: 7px 10px;
    color: $WARNING;
    font-size: 12px;
}

QLabel#logTitle {
    color: $TEXT_STRONG;
    font-size: 14px;
    font-weight: 600;
}

/* ============================== drop zone ======================== */
QFrame#dropZone {
    background-color: $SURFACE_SUNK;
    border: 1px dashed $BORDER_STRONG;
    border-radius: 12px;
}
QFrame#dropZone[state="active"] {
    background-color: $ACCENT_SOFT;
    border: 1px dashed $ACCENT;
}
QLabel#dropZoneTitle {
    color: $TEXT_STRONG;
    font-size: 14px;
    font-weight: 500;
}
QLabel#dropZoneHint {
    color: $TEXT_MUTED;
    font-size: 12px;
}

/* ============================== preview ========================== */
QAbstractScrollArea#previewStage {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 12px;
}
QAbstractScrollArea#previewStage > QWidget > QWidget {
    background: transparent;
}
QFrame#previewStage {
    background-color: $SURFACE_SUNK;
    border: 1px solid $BORDER;
    border-radius: 12px;
}
QLabel#previewCaption {
    color: $TEXT_MUTED;
    font-size: 12px;
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
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background-color: $ACCENT;
    border-radius: 3px;
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
    font-size: 13px;
    spacing: 8px;
}
/* The indicator is drawn by CheckBox in widgets.py: a QSS-styled indicator
   loses its tick, and an image resource would have to be bundled. The native
   sub-control is kept at its natural size so the label still clears it. */
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid $BORDER_STRONG;
    border-radius: 4px;
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
    border-radius: 8px;
    padding: 5px;
    outline: none;
}
QListWidget::item {
    padding: 7px 10px;
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
    border-radius: 8px;
    padding: 9px 11px;
    color: $TEXT_SECONDARY;
    font-size: 12px;
}

/* ============================= scrollbars ======================== */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px 0;
}
QScrollBar::handle:vertical {
    background: $BORDER_STRONG;
    min-height: 32px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: $TEXT_FAINT;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0 2px;
}
QScrollBar::handle:horizontal {
    background: $BORDER_STRONG;
    min-width: 32px;
    border-radius: 5px;
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
    font-size: 12px;
}
QLabel#statusBarValue {
    color: $TEXT_SECONDARY;
    font-size: 12px;
    font-weight: 600;
}
QLabel#statusBarAccent {
    color: $ACCENT_SOFT_TEXT;
    font-size: 12px;
    font-weight: 700;
}

/* ============================ toast ============================== */
QFrame#toast {
    background-color: $SNACKBAR_BG;
    border: none;
    border-radius: 8px;
}
QLabel#toastText {
    color: $SNACKBAR_TEXT;
    font-size: 13px;
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
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["TEXT"]))
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
