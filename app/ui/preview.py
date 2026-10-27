"""Before/after comparison: one image, one draggable seam, real scrolling.

Both sides are drawn from the same transform, so panning and zooming cannot
desynchronise them — the only way to compare compression honestly is to look at
identical pixels.

The view is a ``QAbstractScrollArea``, not a bare widget: a wide window with a
short preview used to force "fit both", which shrank a 1600 px photo to a
thumbnail and left no way to inspect it. The default is now fit-width, so the
image fills the stage and the vertical scrollbar exposes the rest of it; at
100 % both scrollbars behave like any image viewer.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QSizePolicy,
    QStyle,
)

from . import fonts, theme
from .theme import color_for

#: Default fit mode: fill the stage width, scroll vertically. Fit-all is kept
#: for the "适应" toolbar action when the caller wants the whole frame.
FIT_WIDTH = "width"
FIT_ALL = "all"


class CompareView(QAbstractScrollArea):
    """Split view: compressed result left of the seam, original right of it."""

    zoomChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("previewStage")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumSize(220, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.viewport().setAutoFillBackground(False)
        self.viewport().setMouseTracking(True)
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)

        self._before: QPixmap | None = None
        self._after: QPixmap | None = None
        self._before_caption = ""
        self._after_caption = ""
        self._split = 0.5
        self._scale = 1.0
        self._fit_mode = FIT_WIDTH
        self._auto_fit = True
        self._dragging_seam = False
        self._panning = False
        self._pan_origin = QPoint()
        self._pan_scroll_origin = (0, 0)
        self._placeholder = "选择队列中的文件以查看对比"
        self._checker: QPixmap | None = None
        self._checker_key: str | None = None
        #: Baked caption chips (background + text) keyed by (text, mode) so
        #: the per-frame drawRoundedRect + drawText cost during seam drag is
        #: replaced by a single drawPixmap. Invalidated on theme switch.
        self._caption_cache: dict[tuple[str, str], QPixmap] = {}
        self._caption_cache_mode: str | None = None

        self.horizontalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())
        self.verticalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())

    # ------------------------------------------------------------------ data
    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.viewport().update()

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
        self._split = 0.5
        self._auto_fit = True
        self._panning = False
        self._dragging_seam = False
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)
        self._apply_fit()
        self.viewport().update()

    def clear(self) -> None:
        self.set_images(None, None, "", "")

    @property
    def has_image(self) -> bool:
        return self._before is not None or self._after is not None

    @property
    def fit_mode(self) -> str:
        return self._fit_mode

    def set_fit_mode(self, mode: str) -> None:
        if mode not in (FIT_WIDTH, FIT_ALL):
            raise ValueError(f"unknown fit mode: {mode}")
        self._fit_mode = mode
        self.reset_view()

    # ------------------------------------------------------------- transform
    def _base_pixmap(self) -> QPixmap | None:
        return self._before or self._after

    def _scrollbar_extent(self) -> int:
        return max(
            8,
            self.verticalScrollBar().sizeHint().width(),
            self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent),
        )

    def _fit_scale(self) -> float:
        pixmap = self._base_pixmap()
        if pixmap is None or pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
            return 1.0
        pad = 16
        available_w = max(1, self.viewport().width() - pad)
        available_h = max(1, self.viewport().height() - pad)
        if self._fit_mode == FIT_WIDTH:
            scale = min(available_w / pixmap.width(), 1.0)
            if pixmap.height() * scale > available_h:
                # A vertical scrollbar is about to take width away; fitting to
                # the unreduced width would immediately summon a horizontal one.
                scale = min(
                    max(1, available_w - self._scrollbar_extent()) / pixmap.width(),
                    1.0,
                )
            return max(0.01, scale)
        return max(
            0.01,
            min(available_w / pixmap.width(), available_h / pixmap.height(), 1.0),
        )

    def _apply_fit(self) -> None:
        pixmap = self._base_pixmap()
        if pixmap is None:
            self._scale = 1.0
            self._sync_scrollbars()
            self.zoomChanged.emit(self._scale)
            return
        self._scale = self._fit_scale()
        self._sync_scrollbars()
        self.zoomChanged.emit(self._scale)
        self.viewport().update()

    def _content_size(self) -> QSize:
        pixmap = self._base_pixmap()
        if pixmap is None:
            return QSize()
        return QSize(
            max(1, int(round(pixmap.width() * self._scale))),
            max(1, int(round(pixmap.height() * self._scale))),
        )

    def _sync_scrollbars(self) -> None:
        content = self._content_size()
        view_w = self.viewport().width()
        view_h = self.viewport().height()
        horizontal = self.horizontalScrollBar()
        vertical = self.verticalScrollBar()
        horizontal.setRange(0, max(0, content.width() - view_w))
        vertical.setRange(0, max(0, content.height() - view_h))
        horizontal.setPageStep(max(20, int(view_w * 0.92)))
        vertical.setPageStep(max(20, int(view_h * 0.92)))
        horizontal.setSingleStep(40)
        vertical.setSingleStep(40)

    def _image_rect(self) -> QRectF:
        content = self._content_size()
        if content.isEmpty():
            return QRectF()
        view_w = self.viewport().width()
        view_h = self.viewport().height()
        x = (
            (view_w - content.width()) / 2.0
            if content.width() <= view_w
            else -self.horizontalScrollBar().value()
        )
        y = (
            (view_h - content.height()) / 2.0
            if content.height() <= view_h
            else -self.verticalScrollBar().value()
        )
        return QRectF(x, y, content.width(), content.height())

    def _effective_scale(self) -> float:
        return self._scale if self._base_pixmap() is not None else 1.0

    def zoom_percent(self) -> int:
        return int(round(self._effective_scale() * 100))

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        """Set an absolute scale (1.0 = 100 % of source pixels)."""
        if self._base_pixmap() is None:
            return
        target = max(0.02, min(8.0, float(zoom)))
        if abs(target - self._scale) < 1e-9:
            return
        old_rect = self._image_rect()
        self._scale = target
        self._auto_fit = False
        self._sync_scrollbars()
        if anchor is not None and old_rect.width() > 0 and old_rect.height() > 0:
            u = (anchor.x() - old_rect.left()) / old_rect.width()
            v = (anchor.y() - old_rect.top()) / old_rect.height()
            content = self._content_size()
            view_w = self.viewport().width()
            view_h = self.viewport().height()
            if content.width() > view_w:
                desired_left = anchor.x() - u * content.width()
                self.horizontalScrollBar().setValue(int(round(-desired_left)))
            if content.height() > view_h:
                desired_top = anchor.y() - v * content.height()
                self.verticalScrollBar().setValue(int(round(-desired_top)))
        self.zoomChanged.emit(self._scale)
        self.viewport().update()

    def zoom_in(self) -> None:
        center = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
        self.set_zoom(self._scale * 1.25, anchor=center)

    def zoom_out(self) -> None:
        center = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
        self.set_zoom(self._scale / 1.25, anchor=center)

    def actual_size(self) -> None:
        center = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
        self.set_zoom(1.0, anchor=center)

    def reset_view(self) -> None:
        self._auto_fit = True
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)
        self._apply_fit()

    # --------------------------------------------------------------- events
    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self._auto_fit:
            self._scale = self._fit_scale()
            self.zoomChanged.emit(self._scale)
        self._sync_scrollbars()
        self.viewport().update()

    def _seam_x(self) -> float:
        return self.viewport().width() * self._split

    def _can_pan(self) -> bool:
        content = self._content_size()
        return (
            content.width() > self.viewport().width()
            or content.height() > self.viewport().height()
        )

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self.has_image:
            super().mousePressEvent(event)
            return
        self.setFocus()
        position = event.position()
        if self._after is not None and abs(position.x() - self._seam_x()) <= 10:
            self._dragging_seam = True
            self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
        elif self._can_pan():
            self._panning = True
            self._pan_origin = position.toPoint()
            self._pan_scroll_origin = (
                self.horizontalScrollBar().value(),
                self.verticalScrollBar().value(),
            )
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        position = event.position()
        if self._dragging_seam:
            width = max(1, self.viewport().width())
            self._split = min(0.995, max(0.005, position.x() / width))
            self.viewport().update()
            return
        if self._panning:
            delta = position.toPoint() - self._pan_origin
            self.horizontalScrollBar().setValue(self._pan_scroll_origin[0] - delta.x())
            self.verticalScrollBar().setValue(self._pan_scroll_origin[1] - delta.y())
            return
        if self.has_image:
            near = self._after is not None and abs(position.x() - self._seam_x()) <= 10
            self.viewport().setCursor(
                Qt.CursorShape.SplitHCursor if near else Qt.CursorShape.OpenHandCursor
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._dragging_seam = False
        self._panning = False
        if self.has_image:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.reset_view()

    def wheelEvent(self, event):  # noqa: N802
        if not self.has_image:
            return
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.set_zoom(self._scale * (1.12 ** steps), anchor=event.position())
                event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            steps = event.angleDelta().y() / 120.0
            if steps:
                bar = self.horizontalScrollBar()
                bar.setValue(bar.value() - int(steps * 60))
                event.accept()
            return
        super().wheelEvent(event)

    # ---------------------------------------------------------------- paint
    def _checker_brush(self) -> QBrush:
        mode = theme.current_mode()
        if self._checker is None or self._checker_key != mode:
            surface = color_for("SURFACE", mode)
            surface_pressed = color_for("SURFACE_PRESSED", mode)
            tile = QPixmap(18, 18)
            tile.fill(surface)
            painter = QPainter(tile)
            painter.fillRect(0, 0, 9, 9, surface_pressed)
            painter.fillRect(9, 9, 9, 9, surface_pressed)
            painter.end()
            self._checker = tile
            self._checker_key = mode
        return QBrush(self._checker)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        view_rect = QRectF(self.viewport().rect())
        painter.fillRect(view_rect, color_for("SURFACE_SUNK"))

        target = self._image_rect()
        if target.isEmpty():
            self._paint_placeholder(painter, view_rect)
            painter.end()
            return

        before = self._before
        after = self._after
        visible = target.intersected(view_rect)

        # Checkerboard shows through transparent source pixels.
        if visible.width() > 0 and visible.height() > 0:
            painter.fillRect(visible, self._checker_brush())

        if after is not None and not after.isNull():
            # With a result the seam divides the same transform: compressed
            # left, original right.
            seam = self._seam_x()
            painter.save()
            painter.setClipRect(
                QRectF(view_rect.left(), view_rect.top(), seam - view_rect.left(), view_rect.height())
            )
            painter.drawPixmap(target, after, QRectF(after.rect()))
            painter.restore()
            if before is not None and not before.isNull():
                painter.save()
                painter.setClipRect(
                    QRectF(seam, view_rect.top(), view_rect.right() - seam, view_rect.height())
                )
                painter.drawPixmap(target, before, QRectF(before.rect()))
                painter.restore()
                self._paint_seam(painter, view_rect, seam)
        elif before is not None and not before.isNull():
            # Nothing to compare yet: showing half a checkerboard made the
            # before-state look broken. Show the whole original instead.
            painter.drawPixmap(target, before, QRectF(before.rect()))

        self._paint_captions(painter, view_rect)
        painter.end()

    def _paint_seam(self, painter: QPainter, canvas: QRectF, seam: float) -> None:
        """The comparison seam: a light divider with a round grab handle.

        Google Photos / Squoosh draw the seam as a pale line over the image
        with a white disc on it — the handle has to read as *above* the
        picture, so it is drawn with a soft shadow rather than a filled bar.
        """
        # Divider: a translucent white line stays visible over both a light
        # and a dark photo without recolouring the image underneath it.
        divider = QPen(QColor(255, 255, 255, 200), 2.0)
        painter.setPen(divider)
        painter.drawLine(QPointF(seam, canvas.top()), QPointF(seam, canvas.bottom()))

        radius = 15.0
        centre = QPointF(seam, canvas.center().y())
        # Shadow, then the disc: a soft drop shadow is what lifts the handle
        # off the photo instead of letting it blend into the pixels.
        shadow = QColor(0, 0, 0, 60)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(centre, radius + 1.0, radius + 1.0)

        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawEllipse(centre, radius, radius)

        # Chevrons pointing outwards: the whole point of the handle is that
        # it can be dragged, so the affordance must show the direction.
        arrow = QPen(QColor(60, 64, 67), 1.8)
        arrow.setCapStyle(Qt.PenCapStyle.RoundCap)
        arrow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(arrow)
        for direction in (-1.0, 1.0):
            x = centre.x() + direction * 4.0
            path = QPainterPath()
            path.moveTo(x - direction * 2.0, centre.y() - 4.5)
            path.lineTo(x + direction * 2.0, centre.y())
            path.lineTo(x - direction * 2.0, centre.y() + 4.5)
            painter.drawPath(path)

    def _paint_captions(self, painter: QPainter, canvas: QRectF) -> None:
        if self._after is not None:
            entries = ((self._after_caption, True), (self._before_caption, False))
        else:
            entries = ((self._before_caption, True),)
        for text, aligned_left in entries:
            if not text:
                continue
            chip = self._caption_chip(text)
            width = chip.width()
            x = canvas.left() + 9 if aligned_left else canvas.right() - width - 9
            painter.drawPixmap(QPointF(x, canvas.top() + 9), chip)

    def _caption_chip(self, text: str) -> QPixmap:
        """Bake a caption (background pill + text) once per (text, mode).

        During seam drag the paintEvent runs every mouse-move frame; the
        previous implementation rebuilt the rounded-rect + text twice per
        frame. Caching the chip turns that into a single drawPixmap call,
        and the cache is dropped automatically when the active mode flips.
        """
        from PySide6.QtGui import QFontMetrics

        mode = theme.current_mode()
        if mode != self._caption_cache_mode:
            self._caption_cache.clear()
            self._caption_cache_mode = mode
        key = (text, mode)
        cached = self._caption_cache.get(key)
        if cached is not None:
            return cached

        font = fonts.make_font(size=9, weight=fonts.WEIGHT_SEMIBOLD)
        metrics = QFontMetrics(font)
        text_w = metrics.horizontalAdvance(text)
        width = text_w + 18
        height = 24
        chip = QPixmap(width, height)
        chip.fill(Qt.GlobalColor.transparent)
        cpainter = QPainter(chip)
        cpainter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cpainter.setFont(font)
        # Material's scrim: a translucent black pill that reads over any photo
        # without picking up its colour.
        background = QColor(0, 0, 0, 170)
        cpainter.setBrush(background)
        cpainter.setPen(Qt.PenStyle.NoPen)
        cpainter.drawRoundedRect(QRectF(0, 0, width, height), 12, 12)
        cpainter.setPen(QColor(255, 255, 255))
        cpainter.drawText(QRectF(0, 0, width, height), int(Qt.AlignmentFlag.AlignCenter), text)
        cpainter.end()
        self._caption_cache[key] = chip
        return chip

    def _paint_placeholder(self, painter: QPainter, canvas: QRectF) -> None:
        painter.setPen(color_for("TEXT_MUTED"))
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
