"""Custom widgets: the pieces Qt's defaults get wrong for this design.

* ``ChevronComboBox`` — QSS styling removes Qt's native drop-down arrow, so it is
  drawn here (measurably present, see scripts/ui_preview.py).
* ``PlusMinusSpinBox`` — same story for the spin buttons, plus it gives the value
  a monospaced, tabular readout.
* ``CheckBox`` — the Material tick is drawn by hand: a QSS-styled indicator
  loses its check mark, and an image resource would have to be bundled.
* ``SavingsBar`` — the visual motif of the app: a length that *is* the number.
* ``PressSlider`` — the numeric slider is painted by hand so it can carry the
  Material treatment (rounded track, filled handle with a surface ring, tick
  scale, a value label on drag) instead of inheriting Qt's flat gray ribbon.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QSplitterHandle,
    QVBoxLayout,
    QWidget,
)

from . import fonts, icons, theme
from .theme import color_for, tokens_for


# ------------------------------------------------------------------ inputs ---
class ChevronComboBox(QComboBox):
    """QComboBox that draws its own chevron.

    Qt stops painting the native arrow as soon as a stylesheet touches the
    combo box; the QSS zero-sizes the native subcontrol and this paints the
    replacement so the affordance never disappears.
    """

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = color_for("TEXT_MUTED" if self.isEnabled() else "TEXT_FAINT")
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = self.width() - 15
        center_y = self.height() / 2.0
        path = QPainterPath()
        path.moveTo(center_x - 4.0, center_y - 1.8)
        path.lineTo(center_x, center_y + 2.4)
        path.lineTo(center_x + 4.0, center_y - 1.8)
        painter.drawPath(path)
        painter.end()


class PlusMinusSpinBox(QSpinBox):
    """QSpinBox with hand-drawn +/- glyphs in the right-hand strip.

    The value is drawn in the monospace family so a column of numbers does not
    shift by a pixel as digits change.

    ``setButtonSymbols(NoButtons)`` is deliberately **not** used: together with
    any stylesheet on ``QSpinBox`` Qt's QStyleSheetStyle collapses the internal
    line edit to one pixel (measured 74 px wide field -> 1 px edit), which makes
    the value invisible even though it is still there. The native buttons stay
    registered (so the edit field keeps its width) but are zero-sized by QSS;
    the glyphs below are the only affordance the user sees.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover: str | None = None
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # The line edit's rect spans the whole field under QSS; keep the text
        # clear of the painted +/- strip on the right.
        self.lineEdit().setTextMargins(10, 0, 26, 0)

    # -- geometry helpers
    def _strip_rect(self) -> QRectF:
        return QRectF(self.width() - 22.0, 1.0, 21.0, self.height() - 2.0)

    def _half_index(self, position: QPoint) -> str | None:
        if not self._strip_rect().contains(position):
            return None
        return "up" if position.y() < self.height() / 2 else "down"

    # -- events
    def mouseMoveEvent(self, event):  # noqa: N802
        hover = self._half_index(event.position().toPoint())
        if hover != self._hover:
            self._hover = hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        half = self._half_index(event.position().toPoint())
        if half == "up":
            self.stepUp()
            event.accept()
            return
        if half == "down":
            self.stepDown()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):  # noqa: N802
        # Wheel belongs to the page, not to a spin box the cursor happens to cross.
        event.ignore()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        strip = self._strip_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color_for("SURFACE_HOVER"))
            highlight = QRectF(
                strip.left(), strip.top(), strip.width(), strip.height() / 2
            )
            if self._hover == "down":
                highlight.moveTop(strip.center().y())
            painter.drawRoundedRect(highlight, 3, 3)

        active = color_for("TEXT_SECONDARY" if self.isEnabled() else "TEXT_FAINT")
        quiet = color_for("TEXT_MUTED" if self.isEnabled() else "TEXT_FAINT")
        center_x = strip.center().x()
        top_y = strip.top() + strip.height() * 0.30
        bottom_y = strip.top() + strip.height() * 0.70

        pen = QPen(active if self._hover == "up" else quiet, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(int(center_x - 3.5), int(top_y), int(center_x + 3.5), int(top_y))
        painter.drawLine(int(center_x), int(top_y - 3.5), int(center_x), int(top_y + 3.5))

        pen.setColor(active if self._hover == "down" else quiet)
        painter.setPen(pen)
        painter.drawLine(int(center_x - 3.5), int(bottom_y), int(center_x + 3.5), int(bottom_y))
        painter.end()


# ------------------------------------------------------------------ slider ---
class PressSlider(QSlider):
    """Numeric slider painted in the Material 3 idiom.

    Three things distinguish it from a styled QSlider:

    * The track is a rounded bar whose filled portion is the primary colour,
      and the handle is a filled disc separated from the track by a surface
      coloured gap — the Material slider, not Qt's flat gray ribbon.
    * The value is shown above the handle while the cursor is over the track or
      the handle is being dragged, in a tonal label that carries the configured
      suffix (e.g. ``75 %``), so the readout beside the slider does not have to
      be glanced at mid-drag.
    * Tick marks under the track give the scale; the optional
      ``set_default_value(...)`` marks the recommended position with a muted
      tick so it reads as "suggested", not as another scale division.

    Keyboard and click-on-track behaviour still come from QSlider — only the
    painting is custom.
    """

    _TRACK_HEIGHT = 6
    _HANDLE_RADIUS = 9  # 18 px diameter at rest
    _HANDLE_RADIUS_HOVER = 10  # 20 px on hover/press
    _HANDLE_RING = 2
    _LABEL_PAD_X = 9
    _LABEL_PAD_Y = 4
    _TICK_HEIGHT = 4
    _TICK_WIDTH = 1.4
    _DEFAULT_MARKER_WIDTH = 1.4
    _AREA_TOP = 22  # vertical space reserved for the value label
    _TICK_GAP = 3

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._hover = False
        self._pressed = False
        self._default_value: int | None = None
        self._tick_values: list[int] = []
        self._suffix: str = ""
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # -- configuration
    def set_default_value(self, value: int | None) -> None:
        self._default_value = value if value is not None else None
        self.update()

    def set_tick_values(self, values: list[int]) -> None:
        self._tick_values = sorted({int(v) for v in values})
        self.update()

    def set_suffix(self, text: str) -> None:
        self._suffix = text
        self.update()

    def suffix(self) -> str:
        return self._suffix

    # -- state tracking
    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            # Hit-test against the same geometry paintEvent uses, so the value
            # the user sees is the value the click lands on. QSlider's default
            # sliderValueFromPosition uses a different groove rect (no AREA_TOP
            # offset, no handle-radius inset) and silently offset clicks near
            # the track edges — the root cause of "click lands on wrong value".
            target = self._x_to_value(event.position().x())
            self.setValue(target)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        # Drag-follow: while the left button is held, the handle tracks the
        # cursor using the same _x_to_value mapping. Without this QSlider
        # would page-step towards the cursor instead of following it.
        if self._pressed and event.buttons() & Qt.MouseButton.LeftButton:
            target = self._x_to_value(event.position().x())
            self.setValue(target)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(event)

    # -- geometry
    def _track_rect(self) -> QRectF:
        h = float(self._TRACK_HEIGHT)
        cy = self._area_top() + (self.height() - self._area_top()) / 2.0
        x = self._handle_radius()
        width = max(2.0 * self._handle_radius(), float(self.width()) - 2.0 * self._handle_radius())
        return QRectF(x, cy - h / 2.0, width, h)

    def _handle_radius(self) -> float:
        return float(self._HANDLE_RADIUS_HOVER if (self._hover or self._pressed) else self._HANDLE_RADIUS)

    def _area_top(self) -> float:
        return float(self._AREA_TOP)

    def _value_to_x(self, value: int) -> float:
        track = self._track_rect()
        span = max(1, self.maximum() - self.minimum())
        return track.left() + (value - self.minimum()) / span * track.width()

    def _x_to_value(self, x: float) -> int:
        track = self._track_rect()
        span = max(1, self.maximum() - self.minimum())
        ratio = max(0.0, min(1.0, (x - track.left()) / max(1.0, track.width())))
        return int(round(self.minimum() + ratio * span))

    def _bubble_text(self) -> str:
        value = self.value()
        text = str(value) + self._suffix
        return text

    def _show_bubble(self) -> bool:
        return self.isEnabled() and (self._hover or self._pressed)

    # -- paint
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = self._track_rect()
        radius = track.height() / 2.0

        if not self.isEnabled():
            track_color = color_for("SURFACE_MUTED")
            fill_color = color_for("BORDER")
            handle_fill = color_for("SURFACE")
            handle_ring = color_for("SURFACE")
            tick_color = color_for("DIVIDER")
            default_color = color_for("DIVIDER")
            label_bg = color_for("SURFACE_MUTED")
            label_border = color_for("DIVIDER")
            label_text = color_for("TEXT_FAINT")
        else:
            track_color = color_for("SLIDER_TRACK")
            fill_color = color_for("SLIDER_FILL")
            handle_fill = color_for("SLIDER_HANDLE")
            handle_ring = color_for("SLIDER_HANDLE_RING")
            tick_color = color_for("SLIDER_TICK")
            default_color = color_for("SLIDER_DEFAULT_MARKER")
            # Material labels the drag value in the primary container, not in an
            # inverted ink block, so the readout reads as part of the control.
            label_bg = color_for("ACCENT_SOFT")
            label_border = color_for("ACCENT_SOFT_BORDER")
            label_text = color_for("ACCENT_SOFT_TEXT")

        # Track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, radius, radius)

        # Filled portion (from track left to handle)
        handle_x = self._value_to_x(self.value())
        if handle_x > track.left():
            filled = QRectF(track)
            filled.setRight(handle_x)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(filled, radius, radius)

        # Tick marks under the track: the scale, quiet enough to ignore.
        tick_y_top = track.bottom() + self._TICK_GAP
        tick_y_bot = tick_y_top + self._TICK_HEIGHT
        painter.setPen(
            QPen(tick_color, self._TICK_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        ticks = {self.minimum(), self.maximum(), *self._tick_values}
        for tick_value in ticks:
            if tick_value < self.minimum() or tick_value > self.maximum():
                continue
            x = self._value_to_x(tick_value)
            painter.drawLine(QPointF(x, tick_y_top), QPointF(x, tick_y_bot))

        # Default marker: a muted tick at the recommended position. It is
        # deliberately dimmer than the scale ticks so it reads as a suggestion
        # rather than another division.
        if self._default_value is not None and self.minimum() <= self._default_value <= self.maximum():
            marker_x = self._value_to_x(self._default_value)
            painter.setPen(
                QPen(
                    default_color,
                    self._DEFAULT_MARKER_WIDTH,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(
                QPointF(marker_x, tick_y_top + 1.5), QPointF(marker_x, tick_y_bot + 1.5)
            )

        # Handle: a filled disc with a surface-coloured gap around it, so it
        # reads as sitting *on* the track instead of being glued to it.
        handle_r = self._handle_radius()
        handle_rect = QRectF(
            handle_x - handle_r,
            track.center().y() - handle_r,
            handle_r * 2,
            handle_r * 2,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(handle_ring)
        painter.drawEllipse(
            handle_rect.adjusted(
                -self._HANDLE_RING, -self._HANDLE_RING, self._HANDLE_RING, self._HANDLE_RING
            )
        )
        painter.setBrush(handle_fill)
        painter.drawEllipse(handle_rect)

        # Value label above the handle, only while hovered or pressed.
        if self._show_bubble():
            self._draw_label(painter, handle_x, label_bg, label_border, label_text)
        painter.end()

    def _draw_label(
        self,
        painter: QPainter,
        anchor_x: float,
        bg: QColor,
        border: QColor,
        text: QColor,
    ) -> None:
        text_str = self._bubble_text()
        font = QFont(self.font())
        font.setPointSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(font)
        text_w = metrics.horizontalAdvance(text_str)
        label_w = text_w + 2 * self._LABEL_PAD_X
        label_h = metrics.height() + 2 * self._LABEL_PAD_Y
        # Anchor the label so its centre sits above the handle, clamped so it
        # never spills past the widget edges.
        margin = self._LABEL_PAD_X
        center_x = max(label_w / 2 + margin, min(self.width() - label_w / 2 - margin, anchor_x))
        label_x = center_x - label_w / 2
        label_y = 2.0
        label_rect = QRectF(label_x, label_y, label_w, label_h)

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(label_rect, 6, 6)

        painter.setPen(text)
        painter.setFont(font)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, text_str)

    # Hint that the label area is reserved even when not painted, so layouts
    # that depend on sizeHint do not jump as the label appears.
    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        return QSize(max(160, hint.width()), 38)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, 38)


# ------------------------------------------------------------------ labels ---
class MicroLabel(QLabel):
    """Small caption label above a card title.

    Material uses these as plain sentence-case captions (not tracked
    uppercase): the eyebrow reads as a quiet category marker rather than a
    typographic flourish.
    """

    def __init__(self, text: str = "", spacing: float = 0.0, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("microLabel")
        self._spacing = spacing
        self._refresh_font()

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self._refresh_font()

    def _refresh_font(self) -> None:
        font = QFont(self.font())
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Medium)
        if self._spacing:
            fonts.apply_tracking(font, self._spacing)
        self.setFont(font)


class MonoLabel(QLabel):
    """Label forced into the monospace family (sizes, counts, paths)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("monoValue")
        font = fonts.make_font(size=9, mono=True)
        self.setFont(font)


class ElidedLabel(QLabel):
    """Single-line label that elides instead of forcing the layout wider.

    Status sentences and preview hints are allowed to be long, but they must
    never push the controls beside them out of the window. The full sentence is
    kept as a tooltip whenever it had to be shortened.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        self._full_text = text
        super().__init__("", parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._apply_elision()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full_text = text
        self._apply_elision()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply_elision()

    def sizeHint(self) -> QSize:  # noqa: N802
        # The layout should not reserve the full sentence's width; the stretch
        # factor decides how much room the row can spare.
        hint = super().sizeHint()
        return QSize(min(hint.width(), 260), hint.height())

    def _apply_elision(self) -> None:
        width = max(0, self.width() - 2)
        metrics = self.fontMetrics()
        shown = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        super().setText(shown)
        self.setToolTip(self._full_text if shown != self._full_text else "")


class StatLabel(QLabel):
    """Big number used by the result summary."""

    def __init__(self, text: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("statValue")
        font = fonts.make_font(size=20, weight=fonts.WEIGHT_SEMIBOLD, tracking=-0.3)
        self.setFont(font)


# ------------------------------------------------------------------- cards ---
def make_card(
    title: str,
    hint: str = "",
    *,
    eyebrow: str = "",
    header_right: QWidget | None = None,
    parent: QWidget | None = None,
) -> tuple[QFrame, QVBoxLayout]:
    """Build a card frame and return ``(card, body_layout)``.

    Cards are plain QFrame + QLabel, not QGroupBox: the group-box title styling
    needs subcontrol-origin tricks to stop the title from overlapping the border.
    The optional ``eyebrow`` is a quiet caption above the title.
    """
    card = QFrame(parent)
    card.setObjectName("card")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 14, 16, 16)
    outer.setSpacing(12)

    header = QVBoxLayout()
    header.setSpacing(2)
    if eyebrow:
        header.addWidget(MicroLabel(eyebrow))
    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    title_row.addWidget(title_label)
    title_row.addStretch(1)
    if header_right is not None:
        title_row.addWidget(header_right)
    header.addLayout(title_row)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("cardHint")
        hint_label.setWordWrap(True)
        header.addWidget(hint_label)
    outer.addLayout(header)

    divider = QFrame()
    divider.setObjectName("cardDivider")
    divider.setFixedHeight(1)
    outer.addWidget(divider)

    body = QVBoxLayout()
    body.setSpacing(11)
    outer.addLayout(body)
    return card, body


def make_header_row(title_widget: QWidget, *right_widgets: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(title_widget)
    row.addStretch(1)
    for widget in right_widgets:
        row.addWidget(widget)
    return row


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("cardDivider")
    line.setFixedHeight(1)
    return line


# -------------------------------------------------------------- savings bar ---
class SavingsBar(QWidget):
    """Horizontal bar whose length is the fraction of bytes saved.

    This is the app's signature element: a percentage you can compare at a
    glance instead of reading.
    """

    def __init__(self, parent: QWidget | None = None, *, height: int = 8) -> None:
        super().__init__(parent)
        self._ratio = 0.0
        self._accent = True
        self._bar_height = height
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_ratio(self, ratio: float, accent: bool = True) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._accent = accent
        self.update()

    def ratio(self) -> float:
        return self._ratio

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, self._bar_height)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = self._bar_height / 2.0
        track = QRectF(0, (self.height() - self._bar_height) / 2.0, self.width(), self._bar_height)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color_for("SURFACE_MUTED"))
        painter.drawRoundedRect(track, radius, radius)

        if self._ratio > 0:
            filled = QRectF(track)
            filled.setWidth(max(self._bar_height, track.width() * self._ratio))
            painter.setBrush(color_for("ACCENT" if self._accent else "NEUTRAL"))
            painter.drawRoundedRect(filled, radius, radius)
        painter.end()


# -------------------------------------------------------------- halftone ---
# The halftone ornament is retired in the Material direction: the tonal disc
# (TonalBadge) and the accent rule carry the same job with meaning attached.
# The class is kept out of the module entirely rather than left as dead code.


# --------------------------------------------------------------- drop zone ---
class TonalBadge(QWidget):
    """A circular tonal disc holding a single glyph.

    Material's signature container: a filled circle in the primary container
    colour with the icon in the matching on-container colour. It replaces the
    old halftone decoration — a quiet, meaningful mark instead of an ornament.
    """

    def __init__(
        self,
        name: str,
        size: int = 40,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        self._active = False
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def refresh_theme(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self._active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color_for("ACCENT"))
            disc = rect
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color_for("ACCENT_SOFT"))
            disc = rect

        icon_size = int(self._size * 0.48)
        glyph = icons.pixmap(
            self._name,
            "#FFFFFF" if self._active else color_for("ACCENT_SOFT_TEXT").name(),
            icon_size,
        )
        # The disc is drawn around the glyph, not behind the whole widget, so
        # the glyph stays optically centred even when its box is not square.
        painter.drawEllipse(disc)
        x = (self.width() - glyph.width()) / 2
        y = (self.height() - glyph.height()) / 2
        painter.drawPixmap(int(x), int(y), glyph)
        painter.end()


class DropZone(QFrame):
    """Dashed drop target that lights up while files are dragged over.

    Material's empty state: a tonal disc holding an upload glyph, the action
    in medium type, and the formats in a muted line below it.
    """

    filesDropped = Signal(list)

    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setProperty("state", "idle")
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        self._badge = TonalBadge("upload", 44)
        layout.addWidget(self._badge)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        self._title = QLabel(title)
        self._title.setObjectName("dropZoneTitle")
        self._hint = QLabel(hint)
        self._hint.setObjectName("dropZoneHint")
        self._hint.setWordWrap(True)
        text_column.addWidget(self._title)
        text_column.addWidget(self._hint)
        layout.addLayout(text_column, 1)

    def set_state(self, state: str) -> None:
        self.setProperty("state", state)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self._badge.set_active(state == "active")
        self.update()

    def refresh_theme(self) -> None:
        self._badge.refresh_theme()

    # drag & drop
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            self.set_state("active")
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.set_state("idle")

    def dropEvent(self, event):  # noqa: N802
        self.set_state("idle")
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
        event.acceptProposedAction()


# ------------------------------------------------------------- micro parts ---
class GripSplitter(QSplitter):
    """Splitter with a visible grip.

    A transparent 10 px gap looks like a plain margin, so users never discover
    that the queue/preview and workspace/settings proportions can be dragged.
    The grip is a single short bar: enough to read as a handle, quiet enough for
    the print-room palette.
    """

    def createHandle(self):  # noqa: N802 (Qt naming)
        return GripHandle(self.orientation(), self)


class GripHandle(QSplitterHandle):
    def __init__(self, orientation, parent) -> None:
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(
            Qt.CursorShape.SplitHCursor
            if orientation == Qt.Orientation.Horizontal
            else Qt.CursorShape.SplitVCursor
        )

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.underMouse():
            painter.fillRect(self.rect(), color_for("SURFACE_HOVER"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color_for("ACCENT" if self.underMouse() else "TEXT_FAINT"))
        width = self.width()
        height = self.height()
        if self.orientation() == Qt.Orientation.Horizontal:
            grip = QRectF(width / 2 - 1.5, height / 2 - 9, 3, 18)
        else:
            grip = QRectF(width / 2 - 9, height / 2 - 1.5, 18, 3)
        painter.drawRoundedRect(grip, 1.5, 1.5)
        painter.end()


class IconButton(QPushButton):
    """Square icon-only button."""

    def __init__(self, name: str, tooltip: str, parent: QWidget | None = None, *, size: int = 28) -> None:
        super().__init__(parent)
        self.setObjectName("iconButton")
        self._name = name
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tooltip)
        self.refresh_icon()

    def refresh_icon(self) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        color = tokens["TEXT_SECONDARY"] if self.isEnabled() else tokens["TEXT_FAINT"]
        self.setIcon(icons.icon(self._name, color, 18))
        self.setIconSize(QSize(18, 18))


class SegmentedControl(QWidget):
    """Row of mutually exclusive buttons that reads as one control.

    Used for lossless/lossy, quality presets and scale presets — a popup menu
    would hide the options, and these are decisions worth showing at all times.
    """

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QButtonGroup

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._disabled_reason: dict[str, str] = {}

        for value, label in options:
            button = QPushButton(label)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setProperty("segmentValue", value)
            button.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self._group.addButton(button)
            layout.addWidget(button)
            self._buttons[value] = button
        if options:
            self._buttons[options[0][0]].setChecked(True)
        layout.addStretch(1)

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return ""

    def set_value(self, value: str, *, notify: bool = False) -> None:
        button = self._buttons.get(value)
        if button is None or button.isChecked():
            return
        button.setChecked(True)
        if notify:
            self.changed.emit(value)

    def set_options_enabled(self, enabled: dict[str, bool]) -> None:
        for value, allowed in enabled.items():
            button = self._buttons.get(value)
            if button is not None:
                button.setEnabled(allowed)
                button.setToolTip("" if allowed else (self._disabled_reason.get(value) or ""))

    def set_disabled_reason(self, value: str, reason: str) -> None:
        self._disabled_reason[value] = reason
        button = self._buttons.get(value)
        if button is not None and not button.isEnabled():
            button.setToolTip(reason)

    def buttons(self) -> dict[str, QPushButton]:
        return dict(self._buttons)


class TaskSummary(QFrame):
    """The result block shown after a batch finishes.

    Communicates the outcome with a big number and a bar rather than a
    paragraph of text — the same idea as the savings bar, one level up.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._value = StatLabel("—")
        self._caption = QLabel("等待开始")
        self._caption.setObjectName("statCaption")
        self._bar = SavingsBar(height=6)
        self._detail = MonoLabel("—")
        self._detail.setObjectName("cardHint")

        layout.addWidget(self._value)
        layout.addWidget(self._caption)
        layout.addWidget(self._bar)
        layout.addWidget(self._detail)

    def set_show_bar(self, show: bool) -> None:
        """Hide the ratio bar while the live progress bar owns the row.

        Two bars stacked in one card read as two different quantities; only
        one of them is ever the real one at a time.
        """
        self._bar.setVisible(show)

    def show_idle(self) -> None:
        # A 28 px em-dash reads as a rule across the card, not as a missing
        # value; a mid-dot at a smaller size says "nothing yet" quietly.
        self._value.setText("·")
        self._caption.setText("等待开始")
        self._bar.set_ratio(0.0)
        self._detail.setText("—")

    def show_ready(self, enabled: int) -> None:
        self._value.setText(str(enabled))
        self._caption.setText("个文件待压缩")
        self._bar.set_ratio(0.0)
        self._detail.setText("压缩设置已就绪")

    def show_progress(self, done: int, total: int, saved_bytes: int) -> None:
        self._value.setText(f"{done}/{total}")
        self._caption.setText("正在压缩")
        self._bar.set_ratio(done / total if total else 0.0)
        from ..core.unit_report import human_size

        self._detail.setText(f"已省 {human_size(saved_bytes)}" if saved_bytes else "…")

    def show_cancelling(self, done: int, total: int) -> None:
        self._value.setText(f"{done}/{total}")
        self._caption.setText("正在取消…")
        self._bar.set_ratio(done / total if total else 0.0)
        self._detail.setText("等待当前文件完成")

    def show_result(self, total: int, saved_bytes: int, ratio: float, duration_text: str, failures: int) -> None:
        from ..core.unit_report import human_size

        self._value.setText(f"−{ratio * 100:.1f}%")
        self._caption.setText(f"{total} 个文件 · 共省 {human_size(saved_bytes)}")
        self._bar.set_ratio(ratio)
        detail = f"用时 {duration_text}"
        if failures:
            detail += f" · {failures} 个失败"
        self._detail.setText(detail)

    def show_cancelled(self, done: int, total: int) -> None:
        self._value.setText(f"{done}/{total}")
        self._caption.setText("已取消")
        self._bar.set_ratio(done / total if total else 0.0)
        self._detail.setText("已完成的部分结果已写入磁盘")


class Toast(QFrame):
    """Material snackbar: a self-dismissing message above the bottom edge."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel("")
        self._label.setObjectName("toastText")
        layout.addWidget(self._label)

        # A snackbar floats above the app, so it needs a shadow to read as
        # detached from the content behind it.
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()
        self._timer_id = 0

    def show_message(self, text: str) -> None:
        from PySide6.QtCore import QTimer

        self._label.setText(text)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        QTimer.singleShot(2600, self._dismiss)

    def _dismiss(self) -> None:
        if self.isVisible():
            self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 44
        self.move(max(12, x), max(12, y))

    def refresh_geometry(self) -> None:
        if self.isVisible():
            self._reposition()
