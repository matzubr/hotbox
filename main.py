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
    FADE_OUT = widgets.Button.PRESS_MS  # the menu fades together with the pressed button

    def __init__(self, lib_dir: Path = LIB_DIR):
        super().__init__(hou.qt.mainWindow())
        self.lib_dir = Path(lib_dir)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._triggered = False

        self.context = utility.detectContext()
        self.initUI()
        self.adjustSize()
        self.setPositionFromMouse()
        self.fadeIn()
        self.show()

    def _fade(self, start: float, end: float, duration: int, finished=None):
        self._fadeAnimation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fadeAnimation.setDuration(duration)
        self._fadeAnimation.setStartValue(start)
        self._fadeAnimation.setEndValue(end)
        self._fadeAnimation.setEasingCurve(QEasingCurve.OutCubic)
        if finished is not None:
            self._fadeAnimation.finished.connect(finished)
        self._fadeAnimation.start()

    def fadeIn(self):
        self.setWindowOpacity(0.0)
        self._fade(0.0, 1.0, self.FADE_IN)

    @property
    def mode(self) -> str:
        return self.context.mode

    def initUI(self):
        library = scripts.scanScripts(self.lib_dir / self.mode)
        self.scripts_buttons = widgets.ScriptGrid(library, context=self.context.context, parent=self)
        self.keybindings = self.scripts_buttons.keybindings()

        self.open_hotbox_button = widgets.Button("Open HotBox folder")
        self.central_button = widgets.Button(self.context.title, icon=self.context.icon)
        self.script_manager_button = widgets.Button("Script Manager")

        central_layout = widgets.HLayout([self.open_hotbox_button, self.central_button, self.script_manager_button])
        central_layout.setSpacing(widgets.ScriptGrid.COLUMN_GAP)
        central_layout.setAlignment(Qt.AlignHCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.scripts_buttons, 0, Qt.AlignHCenter)
        layout.addLayout(central_layout)
        self.setLayout(layout)

        actions = {button: (lambda s=button.script: self.runScript(s)) for button in self.scripts_buttons.buttons}
        actions[self.open_hotbox_button] = self.openHotboxFolder
        actions[self.central_button] = None  # just close
        actions[self.script_manager_button] = self.startManager
        for button, action in actions.items():
            button.clicked.connect(lambda checked=False, b=button, a=action: self.trigger(b, a))

    def trigger(self, button, action=None):
        """Pressed button grows and fades out, the menu fades out with it, then the action runs.

        The hotbox is closed before the action: scripts open dialogs, select nodes in the viewport, etc.
        Only the first trigger counts.
        """
        if self._triggered:
            return
        self._triggered = True

        def finish():
            self.hide()
            try:
                if action is not None:
                    action()
            finally:
                self.close()

        button.playPress()
        self._fade(self.windowOpacity(), 0.0, self.FADE_OUT, finish)

    def runScript(self, script):
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
            button.startHover()
            self.trigger(button, lambda s=button.script: self.runScript(s))
            return
        super().keyPressEvent(event)

    def openHotboxFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(PACKAGE_DIR.as_posix()))

    def startManager(self):
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

