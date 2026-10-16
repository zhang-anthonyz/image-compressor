"""Before/after comparison: one image, one draggable seam.

Both sides are drawn from the same transform, so panning and zooming cannot
desynchronise them — the only way to compare compression honestly is to look at
identical pixels.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import fonts, theme


class CompareView(QWidget):
    """Split view: original on the left of the seam, compressed on the right."""

    zoomChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewStage")
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._before: QPixmap | None = None
        self._after: QPixmap | None = None
        self._before_caption = ""
        self._after_caption = ""
        self._split = 0.5
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._fit_zoom = 1.0
        self._dragging_seam = False
        self._panning = False
        self._pan_origin = QPoint()
        self._pan_offset_origin = QPointF()
        self._placeholder = "选择队列中的文件以查看对比"

    # ------------------------------------------------------------------ data
    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def set_images(
        self,
        before: QPixmap | None,
        after: QPixmap | None,
        before_caption: str = "",
        after_caption: str = "",
    ) -> None:
        self._before = before
        self._after = after
        self._before_caption = before_caption
        self._after_caption = after_caption
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._recompute_fit()
        self.update()

    def clear(self) -> None:
        self.set_images(None, None, "", "")

    @property
    def has_image(self) -> bool:
        return self._before is not None or self._after is not None

    # ------------------------------------------------------------- transform
    def _base_pixmap(self) -> QPixmap | None:
        return self._before or self._after

    def _recompute_fit(self) -> None:
        pixmap = self._base_pixmap()
        if pixmap is None or pixmap.isNull():
            self._fit_zoom = 1.0
            return
        available_w = max(1, self.width() - 24)
        available_h = max(1, self.height() - 24)
        self._fit_zoom = min(available_w / pixmap.width(), available_h / pixmap.height())

    def _effective_scale(self) -> float:
        if self._base_pixmap() is None:
            return 1.0
        return self._fit_zoom * self._zoom

    def _target_rect(self) -> QRectF:
        pixmap = self._base_pixmap()
        if pixmap is None:
            return QRectF()
        scale = self._effective_scale()
        width = pixmap.width() * scale
        height = pixmap.height() * scale
        center = QPointF(self.width() / 2.0, self.height() / 2.0) + self._offset
        return QRectF(center.x() - width / 2.0, center.y() - height / 2.0, width, height)

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.1, min(12.0, zoom))
        self.update()
        self.zoomChanged.emit(self._zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.25)

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self.update()
        self.zoomChanged.emit(self._zoom)

    def zoom_percent(self) -> int:
        return int(round(self._effective_scale() * 100))

    # --------------------------------------------------------------- events
    def resizeEvent(self, event):  # noqa: N802
        self._recompute_fit()
        super().resizeEvent(event)

    def _seam_x(self) -> float:
        return self.width() * self._split

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self.has_image:
            return
        if abs(event.position().x() - self._seam_x()) <= 9:
            self._dragging_seam = True
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self._pan_offset_origin = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._dragging_seam:
            self._split = min(0.995, max(0.005, event.position().x() / max(1, self.width())))
            self.update()
            return
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._offset = self._pan_offset_origin + QPointF(delta.x(), delta.y())
            self.update()
            return
        if self.has_image:
            near = abs(event.position().x() - self._seam_x()) <= 9
            self.setCursor(
                Qt.CursorShape.SplitHCursor if near else Qt.CursorShape.OpenHandCursor
            )

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._dragging_seam = False
        self._panning = False
        if self.has_image:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.reset_view()

    def wheelEvent(self, event):  # noqa: N802
        if not self.has_image:
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        self.set_zoom(self._zoom * (1.12 ** steps))
        event.accept()

    # ---------------------------------------------------------------- paint
    def paintEvent(self, event):  # noqa: N802
        tokens = theme.tokens_for(theme.current_mode())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        canvas = QRectF(self.rect())
        painter.setBrush(QColor(tokens["SURFACE_SUNK"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(canvas.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        target = self._target_rect()
        if target.isEmpty():
            self._paint_placeholder(painter, canvas, tokens)
            painter.end()
            return

        # Checkerboard behind transparency so the flattened/kept alpha is visible.
        painter.save()
        painter.setClipRect(canvas.adjusted(1, 1, -1, -1))
        self._paint_checkerboard(painter, target)

        before = self._before
        after = self._after
        seam = self._seam_x()

        # Left of the seam: the compressed result. Right: the original.
        if after is not None and not after.isNull():
            painter.save()
            painter.setClipRect(QRectF(canvas.left(), canvas.top(), seam - canvas.left(), canvas.height()))
            painter.drawPixmap(target, after, QRectF(after.rect()))
            painter.restore()
        if before is not None and not before.isNull():
            painter.save()
            painter.setClipRect(QRectF(seam, canvas.top(), canvas.right() - seam, canvas.height()))
            painter.drawPixmap(target, before, QRectF(before.rect()))
            painter.restore()

        if before is not None and after is not None:
            self._paint_seam(painter, canvas, seam, tokens)
        self._paint_captions(painter, canvas, tokens)
        painter.restore()
        painter.end()

    def _paint_checkerboard(self, painter: QPainter, target: QRectF) -> None:
        tokens = theme.tokens_for(theme.current_mode())
        light = QColor(tokens["SURFACE"])
        tile = 9
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(light)
        painter.drawRect(target)
        painter.setBrush(QColor(tokens["SURFACE_PRESSED"]))
        rows = int(target.height() // tile) + 2
        columns = int(target.width() // tile) + 2
        for row in range(rows):
            for column in range(columns):
                if (row + column) % 2:
                    continue
                painter.drawRect(
                    QRectF(
                        target.left() + column * tile,
                        target.top() + row * tile,
                        tile,
                        tile,
                    )
                )

    def _paint_seam(self, painter: QPainter, canvas: QRectF, seam: float, tokens) -> None:
        pen = QPen(QColor(tokens["ACCENT"]), 1.4)
        painter.setPen(pen)
        painter.drawLine(int(seam), int(canvas.top()) + 2, int(seam), int(canvas.bottom()) - 2)

        handle = QRectF(seam - 11, canvas.center().y() - 16, 22, 32)
        painter.setBrush(QColor(tokens["ACCENT"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(handle, 5, 5)

        glyph = QPen(QColor(tokens["ACCENT_ON"]), 1.4)
        glyph.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glyph)
        for offset in (-4.0, 4.0):
            painter.drawLine(
                QPointF(handle.center().x() + offset - 2, handle.center().y() - 5),
                QPointF(handle.center().x() + offset - 2, handle.center().y() + 5),
            )

    def _paint_captions(self, painter: QPainter, canvas: QRectF, tokens) -> None:
        font = fonts.make_font(size=9, weight=fonts.WEIGHT_SEMIBOLD)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        for text, aligned_left in (
            (self._after_caption, True),
            (self._before_caption, False),
        ):
            if not text:
                continue
            width = metrics.horizontalAdvance(text) + 16
            height = 21.0
            x = canvas.left() + 9 if aligned_left else canvas.right() - width - 9
            rect = QRectF(x, canvas.top() + 9, width, height)
            background = QColor(tokens["TEXT_STRONG"])
            background.setAlpha(215)
            painter.setBrush(background)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor(tokens["SURFACE"]))
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)

    def _paint_placeholder(self, painter: QPainter, canvas: QRectF, tokens) -> None:
        painter.setPen(QColor(tokens["TEXT_MUTED"]))
        painter.setFont(fonts.make_font(size=10))
        painter.drawText(canvas, int(Qt.AlignmentFlag.AlignCenter), self._placeholder)


def load_pixmap(path: Path | str, *, max_edge: int = 4200) -> QPixmap | None:
    """Load an image for display through *Pillow*, not Qt's plugins.

    Qt's image plugins cover JPEG/PNG/WebP/TIFF but not AVIF or HEIC, so loading
    previews with ``QPixmap.load`` would silently show nothing for exactly the
    modern formats this tool is about. Pillow decodes every format the engine
    supports, and the array is copied into a QPixmap here.

    Sizes above ``max_edge`` are downscaled first: a 100 MP source would otherwise
    allocate gigabytes for a preview nobody looks at above ~4K.
    """
    from PIL import Image

    try:
        with Image.open(path) as image:
            image.draft("RGB", (max_edge, max_edge))
            frame = image.convert("RGBA") if _has_alpha(image) else image.convert("RGB")
    except Exception:
        return None

    if max(frame.size) > max_edge:
        frame.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    if frame.mode == "RGBA":
        buffer = frame.tobytes("raw", "RGBA")
        qimage = QImage(
            buffer, frame.width, frame.height, frame.width * 4, QImage.Format.Format_RGBA8888
        )
    else:
        buffer = frame.tobytes("raw", "RGB")
        qimage = QImage(
            buffer, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888
        )
    # QImage does not own `buffer`, and the local goes out of scope on return.
    return QPixmap.fromImage(qimage.copy())


def _has_alpha(image) -> bool:
    if image.mode in ("RGBA", "LA", "PA", "RGBa", "La"):
        return True
    return image.mode == "P" and "transparency" in image.info
