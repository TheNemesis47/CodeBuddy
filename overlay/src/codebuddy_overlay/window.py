"""The overlay window: frameless, always on top, never takes focus, centred at the top of the
primary screen. It only draws what `OverlayModel` says; all behaviour lives in the model."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPushButton, QTextBrowser, QWidget

from codebuddy_overlay.answers import Status
from codebuddy_overlay.geometry import EAR_WIDTH, PILL_HEIGHT, Layout, layout, top_center
from codebuddy_overlay.island import State
from codebuddy_overlay.model import OverlayModel
from codebuddy_overlay.protocol import AnswerKind
from codebuddy_overlay.sprout import SproutWidget

BACKGROUND = QColor(0, 0, 0)
CODE_BACKGROUND = QColor(38, 38, 38)
KIND_LABEL = {
    AnswerKind.QUESTION: "DOMANDA",
    AnswerKind.THEORY: "TEORIA",
    AnswerKind.HINT: "SUGGERIMENTO",
}
STATUS_COLOR = {"✓": "#6bcc6b", "!": "#ff8a65", "off": "#ff8a65", "…": "#bbbbbb", "": "#bbbbbb"}
# Qt marks markdown code with the generic "monospace" family, which some platforms resolve to a
# serif face; name real monospace fonts per OS first.
CODE_FONTS = [
    "Menlo",
    "Consolas",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Courier New",
    "monospace",
]
BODY_CSS = """
body { color: #e6e6e6; font-size: 13px; }
code { color: #f5f5f5; background-color: #262626; }
pre { background-color: #1a1a1a; }
"""


class OverlayWindow(QWidget):
    def __init__(self, model: OverlayModel) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar entry
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setWindowTitle("CodeBuddy")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.model = model
        self._layout = layout(State.HIDDEN)

        self.sprout = SproutWidget(22, self)
        self.status = QLabel(self)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview = QLabel(self)
        self.preview.setStyleSheet("color: #e6e6e6; font-size: 12.5px;")
        self.kind = QLabel(self)
        self.kind.setStyleSheet("color: #6bcc6b; font-size: 10px; font-weight: 600;")
        self.title = QLabel(self)
        self.title.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        self.close_button = QPushButton("⌃", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setStyleSheet(
            "QPushButton { color: #ccc; background: #262626; border: none; border-radius: 12px;"
            " font-weight: bold; }"
        )
        self.close_button.clicked.connect(self.model.close)
        self.body = QTextBrowser(self)
        self.body.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.body.setOpenExternalLinks(False)
        self.body.setStyleSheet("QTextBrowser { background: transparent; color: #e6e6e6; }")
        self.body.document().setDefaultStyleSheet(BODY_CSS)
        self.footer = QLabel(self)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSizeF(8.5)
        self.footer.setFont(mono)
        self.footer.setStyleSheet("color: #8a8a8a;")
        self._shown_text: str | None = None

        model.on_change = self.refresh
        self.refresh()

    # What the model says → widgets

    def refresh(self) -> None:
        model = self.model
        state = model.state
        preview = model.peek_preview
        self._layout = layout(state, preview is not None)
        self._place()
        self.sprout.set_mood(model.mood)
        answer = model.answers.current
        hidden, peek, expanded = (state is s for s in (State.HIDDEN, State.PEEK, State.EXPANDED))

        self.sprout.setVisible(True)  # Sprout shows in every state, even in the hidden pill
        status = model.peek_status
        self.status.setText(status)
        self.status.setStyleSheet(
            f"color: {STATUS_COLOR.get(status, '#bbbbbb')}; font-size: 12px; font-weight: 600;"
        )
        self.status.setVisible(peek)
        self.preview.setVisible(peek and preview is not None)
        self.preview.setText(preview or "")
        for widget in (self.kind, self.title, self.close_button, self.body, self.footer):
            widget.setVisible(expanded)

        width, height = self._layout.width, self._layout.height
        if hidden:
            self.sprout.move((width - 22) // 2, (height - 22) // 2)
        elif peek:
            self.sprout.move((EAR_WIDTH - 22) // 2, (PILL_HEIGHT - 22) // 2)
            self.status.setGeometry(width - EAR_WIDTH, 0, EAR_WIDTH, PILL_HEIGHT)
            self.preview.setGeometry(18, PILL_HEIGHT, width - 36, height - PILL_HEIGHT - 4)
        elif expanded:
            self.sprout.move(18, 14)
            self.kind.setGeometry(50, 10, width - 110, 14)
            self.title.setGeometry(50, 24, width - 110, 20)
            self.close_button.move(width - 42, 14)
            self.body.setGeometry(14, 52, width - 28, height - 52 - 30)
            self.footer.setGeometry(18, height - 28, width - 36, 18)
            self.kind.setText(KIND_LABEL[answer.kind] if answer else "CODEBUDDY")
            self.title.setText(answer.title if answer else "Scrivi #? nel codice per chiedere")
            self._show_answer_text(
                answer.text if answer else "",
                answer is not None and answer.status is Status.STREAMING,
            )
            self.footer.setText(_footer(model))
        self.update()

    def _show_answer_text(self, text: str, streaming: bool) -> None:
        if text == self._shown_text:
            return
        self._shown_text = text
        bar = self.body.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.body.setMarkdown(text)
        _use_code_fonts(self.body)
        if streaming and at_bottom:  # follow the stream, unless the student scrolled up
            bar.setValue(bar.maximum())

    def _place(self) -> None:
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        size = self._layout
        if area is not None:
            x, y = top_center(area.x(), area.y(), area.width(), size)
            self.setGeometry(x, y, size.width, size.height)
        else:
            self.resize(size.width, size.height)

    # Drawing and input

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(_island_path(self._layout), BACKGROUND)
        painter.end()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.model.pointer(True)

    def leaveEvent(self, event: object) -> None:
        self.model.pointer(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self.model.state is not State.EXPANDED:
            self.model.click()

    def quit_menu(self) -> QMenu:
        """Right-click: the only way to quit a window with no frame and no taskbar entry."""
        menu = QMenu(self)
        menu.addAction("Esci da CodeBuddy", QApplication.quit)
        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.quit_menu().exec(event.globalPos())


def _use_code_fonts(body: QTextBrowser) -> None:
    """Give inline code and code blocks a real monospace font and a dark background."""
    document = body.document()
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            families = fragment.charFormat().fontFamilies() or []
            if fragment.charFormat().fontFixedPitch() or "monospace" in families:
                cursor = QTextCursor(document)
                cursor.setPosition(fragment.position())
                cursor.setPosition(
                    fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor
                )
                code = QTextCharFormat()
                code.setFontFamilies(CODE_FONTS)
                code.setFontFixedPitch(True)
                code.setBackground(CODE_BACKGROUND)
                cursor.mergeCharFormat(code)
            iterator += 1
        block = block.next()


def _island_path(size: Layout) -> QPainterPath:
    """Flat top (against the screen edge), rounded bottom corners."""
    w, h, r = float(size.width), float(size.height), float(min(size.radius, size.height / 2))
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(w, 0)
    path.lineTo(w, h - r)
    path.arcTo(QRectF(w - 2 * r, h - 2 * r, 2 * r, 2 * r), 0, -90)
    path.lineTo(r, h)
    path.arcTo(QRectF(0, h - 2 * r, 2 * r, 2 * r), -90, -90)
    path.closeSubpath()
    return path


def _footer(model: OverlayModel) -> str:
    answer = model.answers.current
    if answer is None:
        return "in attesa del cervello…" if model.peek_status == "off" else ""
    if answer.status is Status.FAILED:
        return f"errore: {answer.failure}"
    if answer.status is Status.STREAMING:
        return "…"
    first = (
        f"primo token {answer.first_token_ms} ms · " if answer.first_token_ms is not None else ""
    )
    return f"{answer.model} · {first}totale {answer.total_ms} ms"
