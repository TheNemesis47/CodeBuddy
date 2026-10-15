"""Sprout, placeholder version (G8 has the real design), drawn with QPainter in a 100 x 100 box.
A port of `SproutDrawing` in `notch/Sources/CodeBuddy/SproutView.swift`."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from codebuddy_overlay.model import Mood

SEED = QColor.fromRgbF(0.78, 0.56, 0.33)
SEED_SHADE = QColor.fromRgbF(0.55, 0.37, 0.20, 0.35)
LEAF = QColor.fromRgbF(0.42, 0.80, 0.42)
STEM = QColor.fromRgbF(0.30, 0.62, 0.32)
INK = QColor.fromRgbF(0, 0, 0, 0.8)

GROWTH = {Mood.IDLE: 0.0, Mood.THINKING: 0.6, Mood.HAPPY: 1.0, Mood.WORRIED: 0.25}


def draw_sprout(painter: QPainter, mood: Mood, t: float) -> None:
    """Draw in the current 100 x 100 unit space at time `t` (seconds)."""
    g = GROWTH[mood]
    breathe = 1 + 0.035 * math.sin(t * 2.2)
    wobble = 6 * math.sin(t * 5) if mood is Mood.THINKING else 2 * math.sin(t * 1.3)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(0, -22 * (1 - g))  # a bare seed would sit low: centre it

    if g > 0.02:
        top = QPointF(50 + wobble * 0.4, 52 - 34 * g)
        stem = QPainterPath(QPointF(50, 56))
        stem.quadTo(QPointF(50 + wobble, 56 - 18 * g), top)
        pen = QPen(STEM, 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.strokePath(stem, pen)
        _leaf(painter, top, 20 * g, -35 + wobble)
        _leaf(painter, top, 20 * g * 0.85, 215 + wobble)

    w, h = 48 * breathe, 40 / breathe
    seed = QRectF(50 - w / 2, 92 - h, w, h)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(SEED)
    painter.drawEllipse(seed)
    painter.setBrush(SEED_SHADE)
    painter.drawEllipse(seed.adjusted(6, 10, -6, -10).translated(2, 8))

    blink = (t % 4.2) < 0.12
    eye_y = seed.center().y() - 2
    painter.setBrush(INK)
    for dx in (-9.0, 9.0):
        eye_h = 1.6 if blink else 8
        painter.drawRoundedRect(QRectF(50 + dx - 3, eye_y - eye_h / 2, 6, eye_h), 3, 3)
    pen = QPen(INK, 2.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if mood is Mood.WORRIED:
        painter.drawLine(QPointF(37, eye_y - 9), QPointF(45, eye_y - 6))
        painter.drawLine(QPointF(63, eye_y - 9), QPointF(55, eye_y - 6))
    elif mood is Mood.HAPPY:
        painter.drawArc(QRectF(45, eye_y + 2, 10, 10), 200 * 16, 140 * 16)
    painter.restore()


def _leaf(painter: QPainter, base: QPointF, size: float, angle: float) -> None:
    if size <= 0.5:
        return
    path = QPainterPath(QPointF(0, 0))
    path.quadTo(QPointF(size * 0.5, -size * 0.55), QPointF(size, 0))
    path.quadTo(QPointF(size * 0.5, size * 0.55), QPointF(0, 0))
    painter.save()
    painter.translate(base)
    painter.rotate(angle)
    painter.fillPath(path, LEAF)
    painter.restore()


class SproutWidget(QWidget):
    """Animated at ~30 fps while visible. `frozen_at` fixes the time (snapshots, tests)."""

    def __init__(self, size: int = 22, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.mood = Mood.IDLE
        self.frozen_at: float | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def set_mood(self, mood: Mood) -> None:
        if mood is not self.mood:
            self.mood = mood
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.scale(self.width() / 100, self.height() / 100)
        draw_sprout(
            painter, self.mood, self.frozen_at if self.frozen_at is not None else time.time()
        )
        painter.end()
