"""Frameless windows in the DinoWrite look: rounded antialiased background, draggable title bar,
opening/closing animation like the hotbox buttons (grow in from the center with a spring, shrink away)."""
from __future__ import annotations

from .qt import (
    QApplication,
    QColor,
    QEasingCurve,
    QIcon,
    QLabel,
    QPainter,
    QPixmap,
    QPoint,
    QPushButton,
    QRectF,
    QRegion,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    QWidget,
)
from .theme import COLORS, TITLE_BUTTON_SIZE, WINDOW_RADIUS
from .widgets import ICONS_DIR, HLayout, buttonFont


class PopProxy(QWidget):
    """Snapshot of a window drawn scaled about its center: Qt can't scale a live window, so its picture plays the
    animation in a click-through window on top while the real one is invisible."""

    MARGIN = 0.06  # room around the window for the spring overshoot, of its size

    def __init__(self, pixmap: QPixmap, geometry, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
                            | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.pixmap = pixmap
        self.scale = 0.0
        pad_x, pad_y = int(geometry.width() * self.MARGIN) + 2, int(geometry.height() * self.MARGIN) + 2
        self.setGeometry(geometry.adjusted(-pad_x, -pad_y, pad_x, pad_y))

    def setScale(self, value):
        self.scale = float(value)
        self.update()

    def paintEvent(self, event):
        if self.scale <= 0.005:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(self.scale, self.scale)
        size = self.pixmap.deviceIndependentSize() if hasattr(self.pixmap, "deviceIndependentSize") else \
            QSize(self.pixmap.width(), self.pixmap.height()) / self.pixmap.devicePixelRatio()
        painter.drawPixmap(QRectF(-size.width() / 2, -size.height() / 2, size.width(), size.height()),
                           self.pixmap, QRectF(self.pixmap.rect()))
        painter.end()


class RoundedWindow:
    """Mixin for a QWidget: translucent frameless window painting an antialiased rounded rect.

    Call setupRoundedWindow() in __init__ after setting the window flags, and fadeIn() before showing it:
    the window then grows in from its center with a spring (like the hotbox buttons) and shrinks away on close.
    """

    POP_IN_MS, POP_OUT_MS = 340, 220
    POP_IN_OVERSHOOT = 0.9  # spring past full size; smaller than the buttons': windows are big
    POP_OUT_OVERSHOOT = 0.9  # swell before shrinking

    def setupRoundedWindow(self):
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["grey-bright"]))
        painter.drawRoundedRect(QRectF(self.rect()), WINDOW_RADIUS, WINDOW_RADIUS)
        painter.end()

    # --- opening / closing animation ------------------------------------------------------------------------------

    def fadeIn(self):
        """Grow in from the center when shown (the name is kept from the old fade)"""
        self._popPending = True
        self._popClosed = False
        self.setWindowOpacity(0.0)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_popPending", False):
            QTimer.singleShot(0, self._startPopIn)  # after the first layout: the snapshot is complete

    def snapshot(self) -> QPixmap:
        """The window as it looks, transparent outside the rounded rect"""
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(self.size() * ratio)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        self.render(pixmap, QPoint(), QRegion(), QWidget.DrawChildren)
        return pixmap

    def _playPop(self, start: float, end: float, duration: int, curve, finished):
        self._stopPop()
        self._popProxy = PopProxy(self.snapshot(), self.geometry(), self.parentWidget())
        self._popProxy.setScale(start)
        self._popProxy.show()
        self._popAnimation = QVariantAnimation(self._popProxy)
        self._popAnimation.setDuration(duration)
        self._popAnimation.setEasingCurve(curve)
        self._popAnimation.setStartValue(float(start))
        self._popAnimation.setEndValue(float(end))
        self._popAnimation.valueChanged.connect(self._popProxy.setScale)
        self._popAnimation.finished.connect(finished)
        self._popAnimation.start()

    def _stopPop(self):
        proxy = getattr(self, "_popProxy", None)
        if proxy is not None:
            self._popAnimation.stop()
            proxy.close()
            proxy.deleteLater()
        self._popProxy = None

    def _startPopIn(self):
        if not getattr(self, "_popPending", False) or not self.isVisible():
            return  # finishPopIn() came first, or closed already
        self._popPending = False
        spring = QEasingCurve(QEasingCurve.OutBack)
        spring.setOvershoot(self.POP_IN_OVERSHOOT)
        self._playPop(0.0, 1.0, self.POP_IN_MS, spring, self.finishPopIn)

    def finishPopIn(self):
        """The real window in place of its picture (also: skip the animation, for screenshots and tests)"""
        self._popPending = False
        self.setWindowOpacity(1.0)
        self._stopPop()

    def closeEvent(self, event):
        """Shrink away first, then really close"""
        if getattr(self, "_popClosed", True) or not self.isVisible() or QApplication.closingDown():
            self._stopPop()
            super().closeEvent(event)
            return
        event.ignore()
        if getattr(self, "_popClosing", False):
            return
        self._popClosing = True
        anticipation = QEasingCurve(QEasingCurve.InBack)
        anticipation.setOvershoot(self.POP_OUT_OVERSHOOT)
        # Closed while still opening: shrink from the size it has reached
        start = self._popProxy.scale if getattr(self, "_popProxy", None) is not None else 1.0
        self._playPop(start, 0.0, self.POP_OUT_MS, anticipation, self._closeNow)
        self.setWindowOpacity(0.0)

    def _closeNow(self):
        self._popClosed = True
        self.close()


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
