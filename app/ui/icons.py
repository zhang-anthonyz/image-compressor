"""Vector icons drawn with QPainter.

No image files: QSS ``url()`` icons and bundled PNG/SVG assets would have to be
registered in the PyInstaller spec, and every one of them is a chance for the
frozen build to lose an icon. Strokes are drawn at a consistent weight so the
whole set reads as one family.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

STROKE = 1.7


def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pixmap, painter


def _pen(color: str, width: float = STROKE) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw(name: str, size: int, color: str) -> QPixmap:
    pixmap, painter = _canvas(size)
    painter.setPen(_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    s = size
    m = s * 0.5

    if name == "add-file":
        painter.drawRoundedRect(QRectF(s * 0.20, s * 0.16, s * 0.60, s * 0.68), 2.5, 2.5)
        painter.drawLine(QPointF(m, s * 0.38), QPointF(m, s * 0.66))
        painter.drawLine(QPointF(s * 0.36, s * 0.52), QPointF(s * 0.64, s * 0.52))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(s * 0.14, s * 0.30)
        path.lineTo(s * 0.14, s * 0.76)
        path.lineTo(s * 0.86, s * 0.76)
        path.lineTo(s * 0.86, s * 0.34)
        path.lineTo(m, s * 0.34)
        path.lineTo(s * 0.40, s * 0.24)
        path.lineTo(s * 0.20, s * 0.24)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "remove":
        painter.drawLine(QPointF(s * 0.22, s * 0.30), QPointF(s * 0.78, s * 0.30))
        painter.drawLine(QPointF(s * 0.40, s * 0.30), QPointF(s * 0.42, s * 0.20))
        painter.drawLine(QPointF(s * 0.60, s * 0.30), QPointF(s * 0.58, s * 0.20))
        painter.drawLine(QPointF(s * 0.42, s * 0.20), QPointF(s * 0.58, s * 0.20))
        painter.drawRoundedRect(QRectF(s * 0.28, s * 0.30, s * 0.44, s * 0.48), 2.0, 2.0)
        painter.drawLine(QPointF(s * 0.43, s * 0.42), QPointF(s * 0.43, s * 0.66))
        painter.drawLine(QPointF(s * 0.57, s * 0.42), QPointF(s * 0.57, s * 0.66))
    elif name == "clear":
        painter.drawRoundedRect(QRectF(s * 0.22, s * 0.26, s * 0.56, s * 0.52), 3.0, 3.0)
        painter.drawLine(QPointF(s * 0.36, s * 0.40), QPointF(s * 0.64, s * 0.64))
        painter.drawLine(QPointF(s * 0.64, s * 0.40), QPointF(s * 0.36, s * 0.64))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(s * 0.34, s * 0.24)
        path.lineTo(s * 0.78, m)
        path.lineTo(s * 0.34, s * 0.76)
        path.closeSubpath()
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
    elif name == "stop":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40), 1.5, 1.5)
    elif name == "sun":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(m, m), s * 0.20, s * 0.20)
        painter.setPen(_pen(color, STROKE * 0.9))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index in range(8):
            angle = index * math.pi / 4
            painter.drawLine(
                QPointF(m + math.cos(angle) * s * 0.28, m + math.sin(angle) * s * 0.28),
                QPointF(m + math.cos(angle) * s * 0.38, m + math.sin(angle) * s * 0.38),
            )
    elif name == "moon":
        path = QPainterPath()
        path.moveTo(s * 0.66, s * 0.22)
        path.arcTo(QRectF(s * 0.22, s * 0.22, s * 0.52, s * 0.52), 60, 260)
        path.closeSubpath()
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
    elif name == "settings":
        painter.drawEllipse(QPointF(m, m), s * 0.16, s * 0.16)
        painter.setPen(_pen(color, STROKE * 0.95))
        for index in range(6):
            angle = index * math.pi / 3
            painter.drawLine(
                QPointF(m + math.cos(angle) * s * 0.25, m + math.sin(angle) * s * 0.25),
                QPointF(m + math.cos(angle) * s * 0.34, m + math.sin(angle) * s * 0.34),
            )
        painter.drawEllipse(QPointF(m, m), s * 0.34, s * 0.34)
    elif name == "info":
        painter.drawEllipse(QPointF(m, m), s * 0.34, s * 0.34)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(m, s * 0.36), s * 0.035, s * 0.035)
        painter.setPen(_pen(color, STROKE))
        painter.drawLine(QPointF(m, s * 0.46), QPointF(m, s * 0.68))
    elif name == "split":
        painter.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.56), 2.5, 2.5)
        painter.setPen(_pen(color, STROKE * 0.9))
        painter.drawLine(QPointF(m, s * 0.22), QPointF(m, s * 0.78))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(s * 0.18, s * 0.22, s * 0.32, s * 0.56))
    elif name == "log":
        painter.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.56), 2.5, 2.5)
        painter.setPen(_pen(color, STROKE * 0.9))
        for offset in (0.36, 0.50, 0.64):
            painter.drawLine(QPointF(s * 0.30, s * offset), QPointF(s * 0.70, s * offset))
    elif name == "check":
        painter.setPen(_pen(color, STROKE * 1.1))
        path = QPainterPath()
        path.moveTo(s * 0.26, s * 0.52)
        path.lineTo(s * 0.44, s * 0.70)
        path.lineTo(s * 0.76, s * 0.32)
        painter.drawPath(path)
    elif name == "warning":
        path = QPainterPath()
        path.moveTo(m, s * 0.20)
        path.lineTo(s * 0.82, s * 0.76)
        path.lineTo(s * 0.18, s * 0.76)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(m, s * 0.62), s * 0.035, s * 0.035)
        painter.setPen(_pen(color, STROKE))
        painter.drawLine(QPointF(m, s * 0.36), QPointF(m, s * 0.54))
    elif name == "image":
        painter.drawRoundedRect(QRectF(s * 0.18, s * 0.24, s * 0.64, s * 0.52), 2.5, 2.5)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s * 0.38, s * 0.40), s * 0.055, s * 0.055)
        painter.setPen(_pen(color, STROKE * 0.9))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(s * 0.24, s * 0.72)
        path.lineTo(s * 0.46, s * 0.50)
        path.lineTo(s * 0.76, s * 0.72)
        painter.drawPath(path)
    elif name == "open-folder":
        painter.drawRoundedRect(QRectF(s * 0.14, s * 0.34, s * 0.72, s * 0.42), 2.5, 2.5)
        painter.drawLine(QPointF(s * 0.14, s * 0.34), QPointF(s * 0.34, s * 0.22))
        painter.drawLine(QPointF(s * 0.34, s * 0.22), QPointF(s * 0.86, s * 0.22))
    else:
        painter.drawEllipse(QPointF(m, m), s * 0.30, s * 0.30)

    painter.end()
    return pixmap


_CACHE: dict[tuple[str, int, str], QIcon] = {}


def icon(name: str, color: str, size: int = 18) -> QIcon:
    """Cached QIcon for ``name`` drawn in ``color``."""
    key = (name, size, color)
    if key not in _CACHE:
        _CACHE[key] = QIcon(_draw(name, size, color))
    return _CACHE[key]


def pixmap(name: str, color: str, size: int = 18) -> QPixmap:
    return _draw(name, size, color)


def empty_state_pixmap(color: str, size: int = 64) -> QPixmap:
    """Halftone dot sheet used by the empty queue state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    dot = QColor(color)
    step = size / 6.0
    for row in range(6):
        for column in range(6):
            # Diagonal ramp: dots fade out toward the top-left.
            strength = (row + column) / 10.0
            dot.setAlphaF(min(0.55, 0.10 + strength * 0.42))
            painter.setBrush(dot)
            painter.setPen(Qt.PenStyle.NoPen)
            radius = step * 0.16 * (0.6 + strength)
            painter.drawEllipse(
                QPointF(step * (column + 0.5), step * (row + 0.5)), radius, radius
            )
    painter.end()
    return pixmap
