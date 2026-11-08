"""HotBox: popup under the mouse with buttons for the scripts in lib/<mode>/.

Shelf tool / hotkey (see README):
    import hotbox
    hotbox.show()

The old entry point `from hotbox import main; main.start()` still works.
"""
from __future__ import annotations

from pathlib import Path

import hou

from .utils import runner, scripts, utility, widgets
from .utils.qt import (
    QCursor,
    QDesktopServices,
    QEasingCurve,
    QGuiApplication,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
)

PACKAGE_DIR = Path(__file__).resolve().parent
LIB_DIR = PACKAGE_DIR / "lib"


def start():
    return HotBox()


class HotBox(QWidget):
    FADE_IN = 120  # ms
    HOTKEY_FEEDBACK = 90  # ms the pressed button is visible before the script runs

    def __init__(self, lib_dir: Path = LIB_DIR):
        super().__init__(hou.qt.mainWindow())
        self.lib_dir = Path(lib_dir)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.context = utility.detectContext()
        self.initUI()
        self.adjustSize()
        self.setPositionFromMouse()
        self._triggered = False
        self.fadeIn()
        self.show()

    def fadeIn(self):
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(self.FADE_IN)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.start()

    @property
    def mode(self) -> str:
        return self.context.mode

    def initUI(self):
        library = scripts.scanScripts(self.lib_dir / self.mode)
        self.scripts_buttons = widgets.ScriptGrid(library, context=self.context.context, parent=self)
        for button in self.scripts_buttons.buttons:
            button.clicked.connect(lambda checked=False, b=button: self.runScript(b.script))
        self.keybindings = self.scripts_buttons.keybindings()

        self.open_hotbox_button = widgets.Button("Open HotBox folder")
        self.central_button = widgets.Button(self.context.title, icon=self.context.icon)
        self.script_manager_button = widgets.Button("Script Manager")

        central_layout = widgets.HLayout([self.open_hotbox_button, self.central_button, self.script_manager_button])

        layout = QVBoxLayout()
        layout.addWidget(self.scripts_buttons)
        layout.addLayout(central_layout)
        self.setLayout(layout)

        self.open_hotbox_button.clicked.connect(self.openHotboxFolder)
        self.central_button.clicked.connect(self.close)
        self.script_manager_button.clicked.connect(self.startManager)

    def runScript(self, script):
        # Close first: scripts open dialogs, select nodes in the viewport, etc.
        self.close()
        if script.runPath is None:
            runner.status(f"HotBox: {script.relpath}: {script.error}", error=True)
            return
        runner.runScript(script.runPath, label=script.label)

    def keyPressEvent(self, event):
        codes = widgets.eventKeyCodes(event)
        if any(code in widgets.CLOSE_KEYS for code in codes):
            self.close()
            return
        button = next((self.keybindings[code] for code in codes if code in self.keybindings), None)
        if button is not None and not event.isAutoRepeat():
            if not self._triggered:  # one script per hotbox
                self._triggered = True
                button.flash()
                QTimer.singleShot(self.HOTKEY_FEEDBACK, button.click)
            return
        super().keyPressEvent(event)

    def openHotboxFolder(self):
        self.close()
        QDesktopServices.openUrl(QUrl.fromLocalFile(PACKAGE_DIR.as_posix()))

    def startManager(self):
        self.close()
        return widgets.ScriptManager(lib_folder=self.lib_dir)

    def setPositionFromMouse(self):
        """Center under the mouse, kept inside the screen"""
        mouse_pos = QCursor.pos()
        pos = mouse_pos - QPoint(self.width() // 2, self.height() // 2)
        screen = QGuiApplication.screenAt(mouse_pos) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = min(max(pos.x(), area.left()), max(area.left(), area.right() - self.width()))
            y = min(max(pos.y(), area.top()), max(area.top(), area.bottom() - self.height()))
            pos = QPoint(x, y)
        self.move(pos)

