"""Packages panel of the Script Manager: an animated switch per package found in lib/."""
from __future__ import annotations

from pathlib import Path

from . import scripts as script_lib
from . import settings
from .frameless import RoundedWindow, TitleBar
from .qt import (
    QAbstractButton,
    QColor,
    QEasingCurve,
    QLabel,
    QPainter,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
    Signal,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import HLayout, buttonFont, mixColor


class Toggle(QAbstractButton):
    """On/off switch: the knob slides and the track fills with the accent color"""

    WIDTH, HEIGHT = 40, 22
    DURATION = 160

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(QSize(self.WIDTH, self.HEIGHT))
        self.position = 1.0 if checked else 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._move)
        self.toggled.connect(self._animate)

    def _move(self, value):
        self.position = float(value)
        self.update()

    def _animate(self, checked: bool):
        self._animation.stop()
        self._animation.setStartValue(self.position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        track = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(mixColor(QColor("#4a4a4a"), QColor(COLORS["accent"]), self.position))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        diameter = track.height() - 6
        x = track.left() + 3 + (track.width() - diameter - 6) * self.position
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, track.top() + 3, diameter, diameter))
        painter.end()


class PackagesWindow(RoundedWindow, QWidget):
    """Turn packages on/off; saved per user right away (settings.py)"""

    changed = Signal()

    def __init__(self, lib_folder: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HotBox Packages")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()
        self.toggles: dict[str, Toggle] = {}

        packages = script_lib.allPackages(lib_folder)
        data = settings.load()

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(
            f"QWidget#Panel {{ background-color:{COLORS['grey']}; border-radius:{PANEL_RADIUS}px; }}"
            f"QLabel {{ background:transparent; color:{COLORS['white']}; }} QLabel#Hint {{ color:#8a8a8a; }}"
        )
        rows = QVBoxLayout(body)
        rows.setContentsMargins(14, 12, 14, 12)
        rows.setSpacing(10)
        for name, members in packages.items():
            toggle = Toggle(settings.isPackageEnabled(name, data))
            toggle.toggled.connect(lambda checked, n=name: self.setEnabled_(n, checked))
            self.toggles[name] = toggle
            label = QLabel(name)
            label.setFont(buttonFont(12))
            count = QLabel(f"{len(members)} script{'s' if len(members) != 1 else ''}")
            count.setObjectName("Hint")
            row = HLayout([toggle, label, count], align=None)
            row.setSpacing(10)
            row.addStretch(1)
            row_widget = QWidget()
            row_widget.setLayout(row)
            row_widget.setToolTip("\n".join(members))
            rows.addWidget(row_widget)
        if not packages:
            empty = QLabel("No packages yet: add  #package:<name>  to a script header")
            empty.setObjectName("Hint")
            rows.addWidget(empty)
        path = settings.settingsPath()
        hint = QLabel(f"Saved for you only: {path.parent.name}/{path.name} in your Houdini prefs.\n"
                      f"Packages listed in ${settings.PACKAGES_ENV} are on by default.")
        hint.setObjectName("Hint")
        rows.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Packages"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.setMinimumWidth(380)
        self.adjustSize()
        self.fadeIn()

    def setEnabled_(self, name: str, enabled: bool):
        settings.setPackageEnabled(name, enabled)
        self.changed.emit()

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)
