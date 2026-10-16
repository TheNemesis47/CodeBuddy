"""Compose the installers' images from the Draw Things art in packaging/assets/raw/.

  uv run --project overlay python packaging/make_art.py

raw/icon.png (1024², the app icon, used as is), raw/scene.png (a wide scene, any size): writes
assets/icon.png, assets/dmg-background.png (660 × 440) and @2x, assets/wizard.png (410 × 797).
Text and the arrow are drawn here, not by the image model, so they are sharp and in Italian.
Without raw/scene.png a dark gradient stands in. The prompts are in packaging/assets/README.md.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

ASSETS = Path(__file__).resolve().parent / "assets"
RAW = ASSETS / "raw"


def scene(width: int, height: int) -> QImage:
    """The raw scene cropped to fill width × height, or a dark green gradient."""
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    source = QImage(str(RAW / "scene.png"))
    if not source.isNull():
        scaled = source.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawImage(
            0, 0, scaled, (scaled.width() - width) // 2, (scaled.height() - height) // 2
        )
    else:
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor(18, 32, 24))
        gradient.setColorAt(1, QColor(6, 10, 8))
        painter.fillRect(0, 0, width, height, gradient)
    painter.end()
    return image


def dmg_background(scale: int) -> QImage:
    w, h = 660 * scale, 440 * scale
    image = scene(w, h)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Finder draws the icon labels in black: the icons sit on a light card so they stay readable.
    card = QPainterPath()
    card.addRoundedRect(
        QRectF(40 * scale, 112 * scale, 580 * scale, 270 * scale),
        22 * scale,
        22 * scale,
    )
    p.fillPath(card, QColor(244, 248, 245, 232))
    # Arrow from the app (165, 172) to Applications (495, 172), in dmg points.
    pen = QPen(
        QColor(46, 125, 70), 5 * scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
    )
    p.setPen(pen)
    y = 162 * scale
    p.drawLine(QPointF(250 * scale, y), QPointF(400 * scale, y))
    head = QPainterPath(QPointF(412 * scale, y))
    head.lineTo(392 * scale, y - 13 * scale)
    head.lineTo(392 * scale, y + 13 * scale)
    head.closeSubpath()
    p.fillPath(head, QColor(46, 125, 70))
    title = QFont("Helvetica Neue", 22 * scale, QFont.Weight.Bold)
    p.setFont(title)
    p.setPen(QColor(255, 255, 255))
    p.drawText(
        QRectF(0, 30 * scale, w, 40 * scale), Qt.AlignmentFlag.AlignCenter, "CodeBuddy"
    )
    p.setFont(QFont("Helvetica Neue", 13 * scale))
    p.setPen(QColor(235, 245, 238))
    p.drawText(
        QRectF(0, 68 * scale, w, 26 * scale),
        Qt.AlignmentFlag.AlignCenter,
        "Trascina CodeBuddy in Applicazioni",
    )
    p.setFont(QFont("Helvetica Neue", 11 * scale))
    p.setPen(QColor(220, 230, 224))
    p.drawText(
        QRectF(0, 398 * scale, w, 22 * scale),
        Qt.AlignmentFlag.AlignCenter,
        "Il plugin per PyCharm: Settings → Plugins → ⚙ → Install Plugin from Disk…",
    )
    p.end()
    return image


def wizard() -> QImage:
    w, h = 410, 797
    image = scene(w, h)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    icon = QImage(str(ASSETS / "icon.png"))
    if not icon.isNull():
        size = 220
        p.drawImage(
            QRectF((w - size) / 2, 140, size, size),
            icon.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
    p.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(0, 400, w, 60), Qt.AlignmentFlag.AlignCenter, "CodeBuddy")
    p.setFont(QFont("Segoe UI", 16))
    p.setPen(QColor(225, 240, 230))
    p.drawText(QRectF(30, 465, w - 60, 90), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
               "Il tutor che spiega,\nnon scrive il codice al posto tuo")  # fmt: skip
    p.end()
    return image


def squircle(raw: QImage) -> QImage:
    """The model paints the rounded square on a white page: keep only the inside, transparent
    corners, at 1024 px."""
    size = 1024
    src = raw.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)  # fmt: skip
    icon = QImage(size, size, QImage.Format.Format_ARGB32)
    icon.fill(QColor(0, 0, 0, 0))
    p = QPainter(icon)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    inset = 12
    clip.addRoundedRect(
        QRectF(inset, inset, size - 2 * inset, size - 2 * inset), 210, 210
    )
    p.setClipPath(clip)
    p.drawImage(0, 0, src)
    p.end()
    return icon


def main() -> int:
    QGuiApplication(sys.argv[:1])
    raw_icon = QImage(str(RAW / "icon.png"))
    if not raw_icon.isNull():
        squircle(raw_icon).save(str(ASSETS / "icon.png"))
    dmg_background(1).save(str(ASSETS / "dmg-background.png"))
    dmg_background(2).save(str(ASSETS / "dmg-background@2x.png"))
    wizard().save(str(ASSETS / "wizard.png"))
    for name in (
        "icon.png",
        "dmg-background.png",
        "dmg-background@2x.png",
        "wizard.png",
    ):
        path = ASSETS / name
        print(
            f"{path}: {path.stat().st_size // 1024} KB"
            if path.exists()
            else f"{path}: (none)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
