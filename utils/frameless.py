"""Frameless windows in the DinoWrite look: rounded antialiased background, draggable title bar, fade in."""
from __future__ import annotations

from .qt import (
    QColor,
    QEasingCurve,
    QIcon,
    QLabel,
    QPainter,
    QPixmap,
    QPropertyAnimation,
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QWidget,
)
from .theme import COLORS, TITLE_BUTTON_SIZE, WINDOW_RADIUS
from .widgets import ICONS_DIR, HLayout, buttonFont


class RoundedWindow:
    """Mixin for a QWidget: translucent frameless window painting an antialiased rounded rect.

    Call setupRoundedWindow() in __init__ after setting the window flags.
    """

    FADE_IN = 160  # ms

    def setupRoundedWindow(self):
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["grey-bright"]))
        painter.drawRoundedRect(QRectF(self.rect()), WINDOW_RADIUS, WINDOW_RADIUS)
        painter.end()

    def fadeIn(self):
        self.setWindowOpacity(0.0)
        self._fadeAnimation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fadeAnimation.setDuration(self.FADE_IN)
        self._fadeAnimation.setStartValue(0.0)
        self._fadeAnimation.setEndValue(1.0)
        self._fadeAnimation.setEasingCurve(QEasingCurve.OutCubic)
        self._fadeAnimation.start()


class TitleBar(QWidget):
    """Dino icon, title (drag the window by it) and close button"""

    def __init__(self, window: QWidget, title: str, icon: str = "app_dino_dance.svg", on_close=None, on_settings=None):
        super().__init__()
        self.window_ = window

        dino = QLabel()
        dino.setPixmap(QIcon((ICONS_DIR / icon).as_posix()).pixmap(QSize(34, 34)))
        dino.setStyleSheet("background:transparent;")

        self.title = QLabel(title)
        self.title.setFont(buttonFont(12))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFixedHeight(30)
        self.title.setStyleSheet(f"background-color:{COLORS['grey']}; border-radius:10px; color:{COLORS['white']};")
        self.title.setCursor(Qt.OpenHandCursor)

        items = [dino, self.title]
        if on_settings is not None:
            self.settings_button = self._roundButton("gear.svg", COLORS["grey"], COLORS["orange"], icon_size=14)
            self.settings_button.setToolTip("Packages")
            self.settings_button.clicked.connect(on_settings)
            items.append(self.settings_button)

        self.close_button = QPushButton()
        self.close_button.setFixedSize(TITLE_BUTTON_SIZE, TITLE_BUTTON_SIZE)
        self.close_button.setIcon(QIcon(QPixmap((ICONS_DIR / "close.svg").as_posix())))
        self.close_button.setIconSize(QSize(12, 12))
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip("Close")
        self.close_button.setStyleSheet(
            f"QPushButton {{background-color:{COLORS['crimson']}; border:none;"
            f" border-radius:{TITLE_BUTTON_SIZE // 2}px;}}"
            f"QPushButton:hover {{background-color:{COLORS['red']};}}"
        )
        self.close_button.clicked.connect(on_close or window.close)

        items.append(self.close_button)
        layout = HLayout(items, align=None)
        layout.setContentsMargins(15, 10, 15, 4)
        layout.setStretch(1, 1)
        self.setLayout(layout)
        self._drag_offset = None

    @staticmethod
    def _roundButton(icon: str, color: str, hover: str, icon_size: int = 12) -> QPushButton:
        button = QPushButton()
        button.setFixedSize(TITLE_BUTTON_SIZE, TITLE_BUTTON_SIZE)
        button.setIcon(QIcon(QPixmap((ICONS_DIR / icon).as_posix())))
        button.setIconSize(QSize(icon_size, icon_size))
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton {{background-color:{color}; border:none; border-radius:{TITLE_BUTTON_SIZE // 2}px;}}"
            f"QPushButton:hover {{background-color:{hover};}}"
        )
        return button

    def mousePressEvent(self, event):
        self._drag_offset = self.mapToGlobal(event.pos()) - self.window_.pos()
        self.title.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.window_.move(self.mapToGlobal(event.pos()) - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self.title.setCursor(Qt.OpenHandCursor)
