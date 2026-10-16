"""The file queue: model + delegate.

Painted rather than composed from widgets because a queue can hold thousands of
rows — one delegate beats thousands of QWidgets — and because the savings bar
and the checkbox need pixel control that Qt's default item rendering does not
give (a QSS-styled indicator loses its check mark, for instance).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ..core import pipeline
from ..core.unit_report import dimensions, human_size, saved_percent
from . import fonts, theme

COL_ENABLED = 0
COL_NAME = 1
COL_DIMENSIONS = 2
COL_ORIGINAL = 3
COL_RESULT = 4
COL_SAVINGS = 5

HEADERS = ("", "文件名", "尺寸", "原始", "压缩后", "节省")

#: Status -> (label, token name for the pill colour)
STATUS_META = {
    pipeline.STATUS_PENDING: ("待处理", "TEXT_MUTED"),
    pipeline.STATUS_RUNNING: ("处理中", "ACCENT"),
    pipeline.STATUS_DONE: ("完成", "SUCCESS"),
    pipeline.STATUS_UNCHANGED: ("已优化", "WARNING"),
    pipeline.STATUS_SKIPPED: ("已跳过", "NEUTRAL"),
    pipeline.STATUS_FAILED: ("失败", "DANGER"),
}


@dataclass
class QueueItem:
    """One row: what we know about a file before and after compressing it."""

    path: Path
    probe: pipeline.Probe | None = None
    enabled: bool = True
    status: str = pipeline.STATUS_PENDING
    result: pipeline.FileResult | None = None
    message: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def original_size(self) -> int:
        if self.result is not None and self.result.original_size:
            return self.result.original_size
        if self.probe is not None:
            return self.probe.size_bytes
        return 0

    @property
    def new_size(self) -> int:
        if self.result is not None and self.result.new_size:
            return self.result.new_size
        return 0

    @property
    def dimensions_text(self) -> str:
        original = (0, 0)
        if self.result is not None and self.result.original_dimensions[0]:
            original = self.result.original_dimensions
        elif self.probe is not None:
            original = self.probe.dimensions
        if not original[0]:
            return "—"
        target = self.result.new_dimensions if self.result is not None else (0, 0)
        if target and target[0] and target != original:
            return f"{dimensions(*original)} → {dimensions(*target)}"
        return dimensions(*original)

    @property
    def ratio(self) -> float:
        if self.result is None:
            return 0.0
        return self.result.ratio

    @property
    def status_label(self) -> str:
        return STATUS_META.get(self.status, (self.status, "TEXT_MUTED"))[0]

    @property
    def is_animatable(self) -> bool:
        return self.probe is not None and self.probe.ok


class QueueModel(QAbstractTableModel):
    """Table model over :class:`QueueItem` objects."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[QueueItem] = []

    # ------------------------------------------------------------ Qt plumbing
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == COL_ENABLED:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == COL_NAME:
                return item.name
            if column == COL_DIMENSIONS:
                return item.dimensions_text
            if column == COL_ORIGINAL:
                return human_size(item.original_size) if item.original_size else "—"
            if column == COL_RESULT:
                if item.result is not None and item.new_size:
                    return human_size(item.new_size)
                # Status is shown as a pill in the last column only: repeating it
                # here as text produced two status indicators per row.
                return "—"
            if column == COL_SAVINGS:
                if item.result is not None and item.new_size:
                    return saved_percent(item.original_size, item.new_size)
                return ""
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (COL_DIMENSIONS, COL_ORIGINAL, COL_RESULT, COL_SAVINGS):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.FontRole and column in (COL_DIMENSIONS, COL_ORIGINAL, COL_RESULT, COL_SAVINGS):
            return fonts.make_font(size=9, mono=True)

        if role == Qt.ItemDataRole.ToolTipRole:
            lines = [str(item.path)]
            if item.probe is not None and not item.probe.ok:
                lines.append(item.probe.error)
            if item.message:
                lines.append(item.message)
            if item.notes:
                lines.append("；".join(item.notes))
            if item.probe is not None and item.probe.animated:
                lines.append("动图暂不支持")
            return "\n".join(lines)

        if role == Qt.ItemDataRole.ForegroundRole:
            tokens = theme.tokens_for(theme.current_mode())
            if item.status == pipeline.STATUS_FAILED:
                return QColor(tokens["DANGER"])
            if item.status == pipeline.STATUS_SKIPPED:
                return QColor(tokens["TEXT_FAINT"])
            if column == COL_NAME:
                return QColor(tokens["TEXT_STRONG"] if item.enabled else tokens["TEXT_FAINT"])
            return QColor(tokens["TEXT_SECONDARY"])

        return None

    # ---------------------------------------------------------------- content
    def items(self) -> list[QueueItem]:
        return list(self._items)

    def item(self, row: int) -> QueueItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def paths(self) -> list[Path]:
        return [item.path for item in self._items]

    def enabled_items(self) -> list[QueueItem]:
        return [item for item in self._items if item.enabled and item.status != pipeline.STATUS_SKIPPED]

    def add_paths(self, paths: list[Path], probes: dict[Path, pipeline.Probe]) -> int:
        """Append paths we do not already hold. Returns how many were added."""
        known = {item.path for item in self._items}
        added = 0
        self.beginResetModel()
        for path in paths:
            if path in known:
                continue
            probe = probes.get(path)
            status = pipeline.STATUS_PENDING
            message = ""
            if probe is None or not probe.ok:
                status = pipeline.STATUS_FAILED
                message = probe.error if probe is not None else "无法读取文件"
            elif probe.animated:
                status = pipeline.STATUS_SKIPPED
                message = "动图暂不支持（GIF/WebP 多帧）"
            self._items.append(
                QueueItem(path=path, probe=probe, status=status, message=message)
            )
            known.add(path)
            added += 1
        self.endResetModel()
        return added

    def toggle_row(self, row: int) -> None:
        item = self.item(row)
        if item is None:
            return
        item.enabled = not item.enabled
        top = self.index(row, COL_ENABLED)
        bottom = self.index(row, COL_SAVINGS)
        self.dataChanged.emit(top, bottom)

    def set_enabled_all(self, enabled: bool) -> None:
        for item in self._items:
            item.enabled = enabled
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._items) - 1, len(HEADERS) - 1)
            )

    def remove_rows(self, rows: list[int]) -> int:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self._items):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()
        return len(self._items)

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def reset_results(self) -> None:
        """Return every row to "pending" (before a new batch)."""
        for item in self._items:
            if item.status in (pipeline.STATUS_SKIPPED, pipeline.STATUS_FAILED):
                continue
            item.status = pipeline.STATUS_PENDING
            item.result = None
            item.message = ""
            item.notes = []
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._items) - 1, len(HEADERS) - 1)
            )

    def apply_running(self, row: int) -> None:
        item = self.item(row)
        if item is None:
            return
        item.status = pipeline.STATUS_RUNNING
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(HEADERS) - 1))

    def apply_result(self, row: int, result: pipeline.FileResult) -> None:
        item = self.item(row)
        if item is None:
            return
        item.result = result
        item.status = result.status
        item.message = result.message
        item.notes = list(result.notes)
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(HEADERS) - 1))

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict[str, int | float]:
        total_original = 0
        total_new = 0
        saved = 0
        done = unchanged = skipped = failed = running = 0
        for item in self._items:
            if item.status == pipeline.STATUS_DONE:
                done += 1
            elif item.status == pipeline.STATUS_UNCHANGED:
                unchanged += 1
            elif item.status == pipeline.STATUS_SKIPPED:
                skipped += 1
            elif item.status == pipeline.STATUS_FAILED:
                failed += 1
            elif item.status == pipeline.STATUS_RUNNING:
                running += 1
            if item.status in (pipeline.STATUS_DONE, pipeline.STATUS_UNCHANGED):
                total_original += item.original_size
                total_new += item.new_size
                saved += max(0, item.original_size - item.new_size)
        ratio = (saved / total_original) if total_original else 0.0
        return {
            "count": len(self._items),
            "enabled": len(self.enabled_items()),
            "done": done,
            "unchanged": unchanged,
            "skipped": skipped,
            "failed": failed,
            "running": running,
            "processed": done + unchanged,
            "original": total_original,
            "new": total_new,
            "saved": saved,
            "ratio": ratio,
        }


class QueueDelegate(QStyledItemDelegate):
    """Draws row backgrounds, the checkbox, the status pill and the savings bar."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        model: QueueModel = index.model()
        item = model.item(index.row())
        if item is None:
            super().paint(painter, option, index)
            return

        tokens = theme.tokens_for(theme.current_mode())
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5)
        row_rect = QRectF(option.rect)

        # --- row background: selection beats hover beats nothing
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(tokens["ACCENT_SOFT"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(row_rect.adjusted(3, 1, -3, -1), 5, 5)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(tokens["SURFACE_HOVER"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(row_rect.adjusted(3, 1, -3, -1), 5, 5)

        painter.setPen(QPen(QColor(tokens["DIVIDER"]), 1))
        painter.drawLine(
            int(row_rect.left()) + 3, int(row_rect.bottom()),
            int(row_rect.right()) - 3, int(row_rect.bottom()),
        )

        if index.column() == COL_ENABLED:
            self._paint_checkbox(painter, rect, item, tokens)
        elif index.column() == COL_SAVINGS:
            # One place for status: the rightmost column shows the savings bar
            # once there is a result, and the status pill until then.
            if item.result is not None and item.new_size:
                self._paint_savings(painter, rect, item, tokens)
            elif item.status != pipeline.STATUS_PENDING:
                self._paint_status_pill(painter, rect, item, tokens)
        else:
            self._paint_text(painter, rect, index, item, tokens)

        painter.restore()

    # ------------------------------------------------------------- primitives
    def _paint_text(self, painter, rect, index, item, tokens) -> None:
        column = index.column()
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text:
            return
        font = index.data(Qt.ItemDataRole.FontRole) or self._base_font()
        painter.setFont(font)
        painter.setPen(index.data(Qt.ItemDataRole.ForegroundRole) or QColor(tokens["TEXT"]))

        align = index.data(Qt.ItemDataRole.TextAlignmentRole) or int(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        alignment = Qt.AlignmentFlag(int(align))
        padding = 10.0 if column == COL_NAME else 8.0
        target = rect.adjusted(padding, 0, -padding + 2, 0)

        metrics = QFontMetrics(font)
        if column == COL_NAME:
            elided = metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, int(target.width()))
            painter.drawText(target, alignment, elided)
        else:
            painter.drawText(target, alignment, text)

    def _paint_checkbox(self, painter, rect, item, tokens) -> None:
        size = 15.0
        box = QRectF(
            rect.center().x() - size / 2 + 2,
            rect.center().y() - size / 2,
            size,
            size,
        )
        if item.status == pipeline.STATUS_SKIPPED:
            checked = False
            color = QColor(tokens["SURFACE_MUTED"])
            border = QColor(tokens["DIVIDER"])
        elif item.enabled:
            checked = True
            color = QColor(tokens["ACCENT"])
            border = QColor(tokens["ACCENT"])
        else:
            checked = False
            color = QColor(tokens["SURFACE"])
            border = QColor(tokens["BORDER_STRONG"])

        painter.setBrush(color)
        painter.setPen(QPen(border, 1.2))
        painter.drawRoundedRect(box, 3, 3)

        if checked:
            pen = QPen(QColor(tokens["ACCENT_ON"]), 1.9)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            # Explicit tick geometry: two strokes keep the check crisp at 15 px
            # in a way a scaled glyph or an icon resource would not.
            painter.drawLine(
                int(box.left() + 3.0), int(box.center().y()),
                int(box.center().x() - 1.0), int(box.bottom() - 4.0),
            )
            painter.drawLine(
                int(box.center().x() - 1.0), int(box.bottom() - 4.0),
                int(box.right() - 3.0), int(box.top() + 4.0),
            )

    def _paint_savings(self, painter, rect, item, tokens) -> None:
        ratio = item.ratio
        text = saved_percent(item.original_size, item.new_size)
        width = rect.width() - 16
        bar_width = max(52.0, width - 52.0)
        bar_height = 7.0
        bar_left = rect.left() + 8
        bar_top = rect.center().y() - bar_height / 2 + 1

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["SURFACE_PRESSED"]))
        painter.drawRoundedRect(QRectF(bar_left, bar_top, bar_width, bar_height), 3.5, 3.5)

        if ratio > 0:
            filled = max(bar_height, bar_width * ratio)
            painter.setBrush(QColor(tokens["ACCENT"]))
            painter.drawRoundedRect(QRectF(bar_left, bar_top, filled, bar_height), 3.5, 3.5)

        font = fonts.make_font(size=9, mono=True, weight=fonts.WEIGHT_SEMIBOLD)
        painter.setFont(font)
        painter.setPen(QColor(tokens["TEXT_STRONG"] if ratio > 0.05 else tokens["TEXT_MUTED"]))
        painter.drawText(
            QRectF(bar_left + bar_width + 6, rect.top(), rect.width() - bar_width - 10, rect.height()),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            text,
        )

    def _paint_status_pill(self, painter, rect, item, tokens) -> None:
        label, token_name = STATUS_META.get(item.status, (item.status, "TEXT_MUTED"))
        color = QColor(tokens[token_name])
        font = fonts.make_font(size=8, weight=fonts.WEIGHT_SEMIBOLD, tracking=0.3)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(label) + 16
        height = 19.0
        pill = QRectF(rect.right() - width - 8, rect.center().y() - height / 2, width, height)

        background = QColor(color)
        background.setAlpha(38)
        painter.setBrush(background)
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setPen(color)
        painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), label)

    def _base_font(self) -> QFont:
        return fonts.make_font(size=10)

    def sizeHint(self, option, index):  # noqa: N802
        hint = super().sizeHint(option, index)
        hint.setHeight(38)
        return hint
