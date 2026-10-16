"""Custom widgets: the pieces Qt's defaults get wrong for this design.

* ``ChevronComboBox`` — QSS styling removes Qt's native drop-down arrow, so it is
  drawn here (measurably present, see scripts/ui_preview.py).
* ``PlusMinusSpinBox`` — same story for the spin buttons, plus it gives the value
  a monospaced, tabular readout.
* ``MicroLabel`` — uppercase section labels with real letter-spacing, which QSS
  cannot express.
* ``SavingsBar`` — the visual motif of the app: a length that *is* the number.
* ``HalftoneHeader`` — the one decorative element, drawn from print technique.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import fonts, icons, theme
from .theme import tokens_for


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
        tokens = tokens_for(theme.current_mode())
        color = QColor(tokens["TEXT_MUTED"] if self.isEnabled() else tokens["TEXT_FAINT"])
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
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover: str | None = None
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # -- geometry helpers
    def _strip_rect(self) -> QRectF:
        return QRectF(self.width() - 20.0, 1.0, 19.0, self.height() - 2.0)

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
        tokens = tokens_for(theme.current_mode())
        strip = self._strip_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["SURFACE_HOVER"]))
            highlight = QRectF(
                strip.left(), strip.top(), strip.width(), strip.height() / 2
            )
            if self._hover == "down":
                highlight.moveTop(strip.center().y())
            painter.drawRoundedRect(highlight, 3, 3)

        active = QColor(tokens["TEXT_SECONDARY"] if self.isEnabled() else tokens["TEXT_FAINT"])
        quiet = QColor(tokens["TEXT_MUTED"] if self.isEnabled() else tokens["TEXT_FAINT"])
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


# ------------------------------------------------------------------ labels ---
class MicroLabel(QLabel):
    """Small uppercase label with genuine letter-spacing."""

    def __init__(self, text: str = "", spacing: float = 1.3, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("microLabel")
        self._spacing = spacing
        self._refresh_font()

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text.upper())
        self._refresh_font()

    def _refresh_font(self) -> None:
        font = QFont(self.font())
        font.setPointSize(8)
        font.setWeight(QFont.Weight.Bold)
        fonts.apply_tracking(font, self._spacing)
        self.setFont(font)


class MonoLabel(QLabel):
    """Label forced into the monospace family (sizes, counts, paths)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("monoValue")
        font = fonts.make_font(size=9, mono=True)
        self.setFont(font)


class StatLabel(QLabel):
    """Big number used by the result summary."""

    def __init__(self, text: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("statValue")
        font = fonts.make_font(size=24, weight=fonts.WEIGHT_BOLD, tracking=-0.4)
        self.setFont(font)


# ------------------------------------------------------------------- cards ---
def make_card(
    title: str,
    hint: str = "",
    *,
    eyebrow: str = "",
    parent: QWidget | None = None,
) -> tuple[QFrame, QVBoxLayout]:
    """Build a card frame and return ``(card, body_layout)``.

    Cards are plain QFrame + QLabel, not QGroupBox: the group-box title styling
    needs subcontrol-origin tricks to stop the title from overlapping the border.
    Each card carries an ``eyebrow`` (uppercase, tracked) because the print-room
    identity lives in that kind of typographic detail.
    """
    card = QFrame(parent)
    card.setObjectName("card")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 14, 16, 16)
    outer.setSpacing(11)

    header = QVBoxLayout()
    header.setSpacing(3)
    if eyebrow:
        header.addWidget(MicroLabel(eyebrow))
    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    title_row.addWidget(title_label)
    title_row.addStretch(1)
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
    body.setSpacing(10)
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
        tokens = tokens_for(theme.current_mode())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = self._bar_height / 2.0
        track = QRectF(0, (self.height() - self._bar_height) / 2.0, self.width(), self._bar_height)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["SURFACE_PRESSED"]))
        painter.drawRoundedRect(track, radius, radius)

        if self._ratio > 0:
            filled = QRectF(track)
            filled.setWidth(max(self._bar_height, track.width() * self._ratio))
            painter.setBrush(QColor(tokens["ACCENT"] if self._accent else tokens["NEUTRAL"]))
            painter.drawRoundedRect(filled, radius, radius)
        painter.end()


# -------------------------------------------------------------- halftone ---
class HalftoneHeader(QWidget):
    """Halftone dot field fading in from the right.

    Halftone is how print represents continuous tone with dots, which is exactly
    what an image compressor does with pixels — so it is the one ornament that
    earns its place rather than being decoration for its own sake.
    """

    def __init__(self, parent: QWidget | None = None, *, rows: int = 3, step: int = 9) -> None:
        super().__init__(parent)
        self._rows = rows
        self._step = step
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMinimumHeight(rows * step)

    def paintEvent(self, event):  # noqa: N802
        tokens = tokens_for(theme.current_mode())
        dot = QColor(
            *(int(part) for part in tokens["HALFTONE_RGB"].split(",")),
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        width = self.width()
        step = self._step
        for row in range(self._rows):
            for column in range(0, max(1, width // step) + 1):
                # Dots grow and darken towards the right: a printed gradient.
                progress = column / max(1.0, width / step)
                radius = step * 0.09 + progress * step * 0.20
                dot.setAlphaF(min(0.42, 0.05 + progress * 0.36))
                painter.setBrush(dot)
                painter.drawEllipse(
                    QRectF(column * step + step / 2 - radius,
                           row * step + step / 2 - radius,
                           radius * 2, radius * 2)
                )
        painter.end()


# --------------------------------------------------------------- drop zone ---
class DropZone(QFrame):
    """Dashed drop target that lights up while files are dragged over."""

    filesDropped = Signal(list)

    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setProperty("state", "idle")
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(11)

        self._glyph = QLabel()
        self._glyph.setPixmap(icons.empty_state_pixmap(theme.tokens_for(theme.current_mode())["HALFTONE_RGB"], 40))
        self._glyph.setFixedSize(40, 40)
        layout.addWidget(self._glyph)

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        self._title = QLabel(title)
        self._title.setObjectName("dropZoneTitle")
        self._hint = QLabel(hint)
        self._hint.setObjectName("dropZoneHint")
        text_column.addWidget(self._title)
        text_column.addWidget(self._hint)
        layout.addLayout(text_column, 1)

    def set_state(self, state: str) -> None:
        self.setProperty("state", state)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def refresh_theme(self) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        self._glyph.setPixmap(icons.empty_state_pixmap(tokens["HALFTONE_RGB"], 40))

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

    Communicates the outcome with a big number and a halftone rule rather than a
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

    def show_idle(self) -> None:
        self._value.setText("—")
        self._caption.setText("等待开始")
        self._bar.set_ratio(0.0)
        self._detail.setText("—")

    def show_progress(self, done: int, total: int, saved_bytes: int) -> None:
        self._value.setText(f"{done}/{total}")
        self._caption.setText("正在压缩")
        self._bar.set_ratio(done / total if total else 0.0)
        from ..core.unit_report import human_size

        self._detail.setText(f"已省 {human_size(saved_bytes)}" if saved_bytes else "…")

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
    """Non-blocking, self-dismissing message anchored to the window bottom."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 9, 13, 9)
        self._label = QLabel("")
        self._label.setObjectName("toastText")
        layout.addWidget(self._label)

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
        y = parent.height() - self.height() - 22
        self.move(max(12, x), max(12, y))

    def refresh_geometry(self) -> None:
        if self.isVisible():
            self._reposition()
