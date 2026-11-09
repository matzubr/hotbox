"""Window for a script that failed: the error, the traceback, a way to the line in the Script Manager."""
from __future__ import annotations

import hou

from .frameless import RoundedWindow, TitleBar
from .qt import QFontDatabase, QGuiApplication, QLabel, QPlainTextEdit, Qt, QVBoxLayout, QWidget
from .runner import ScriptError
from .theme import COLORS, PANEL_RADIUS
from .widgets import Button, HLayout, buttonFont

ACTION_SIZE = (230, 36)


class ErrorWindow(RoundedWindow, QWidget):
    """Shown when a hotbox script raises. 'Open in Script Manager' shows the failing line."""

    def __init__(self, error: ScriptError, lib_roots, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.error = error
        self.lib_roots = lib_roots
        self.setWindowTitle("HotBox: script error")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()

        where = error.path.name + (f", line {error.line}" if error.line else "")
        title = QLabel(f"{error.label} failed  ·  {where}")
        title.setFont(buttonFont(12))
        message = QLabel(error.message)
        message.setObjectName("Error")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.traceback_edit = QPlainTextEdit(error.traceback)
        self.traceback_edit.setReadOnly(True)
        self.traceback_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(10)
        self.traceback_edit.setFont(font)

        self.open_button = Button("Open in Script Manager", buttonColor=COLORS["accent"], textColor="#ffffff",
                                  size=ACTION_SIZE, fontSize=12)
        self.copy_button = Button("Copy", buttonColor="#4a4a4a", size=(90, 36), fontSize=12)
        self.close_button = Button("Close", buttonColor="#4a4a4a", size=(90, 36), fontSize=12)
        self.open_button.clicked.connect(self.openInManager)
        self.copy_button.clicked.connect(self.copyTraceback)
        self.close_button.clicked.connect(self.close)

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(
            f"QWidget#Panel {{ background-color:{COLORS['grey']}; border-radius:{PANEL_RADIUS}px; }}"
            f"QLabel {{ background:transparent; color:{COLORS['white']}; }}"
            "QLabel#Error { color:#ff8f8f; }"
            f"QPlainTextEdit {{ background-color:{COLORS['grey-dark']}; color:#d8d8d8;"
            f" border:1px solid {COLORS['border']}; border-radius:6px; padding:4px; }}"
        )
        rows = QVBoxLayout(body)
        rows.setContentsMargins(14, 12, 14, 12)
        rows.setSpacing(8)
        rows.addWidget(title)
        rows.addWidget(message)
        rows.addWidget(self.traceback_edit, 1)
        rows.addLayout(HLayout([self.copy_button, self.close_button, self.open_button], align=Qt.AlignRight))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Script error"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.addAnimationOverlay()
        self.resize(760, 420)
        self.fadeIn()

    def openInManager(self):
        from .manager import ScriptManager

        self.manager = ScriptManager(lib_folder=self.lib_roots)
        self.manager.showScript(self.error.path, self.error.line)
        self.close()
        return self.manager

    def copyTraceback(self):
        QGuiApplication.clipboard().setText(self.error.traceback)

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)


_windows: list = []  # keep the Python side alive while open (the hotbox that ran the script is gone)


def showScriptError(error: ScriptError, lib_roots) -> ErrorWindow:
    window = ErrorWindow(error, lib_roots)
    _windows.append(window)
    window.destroyed.connect(lambda *_: _windows.remove(window) if window in _windows else None)
    window.show()
    return window
