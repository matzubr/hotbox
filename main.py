"""HotBox: popup under the mouse with buttons for the scripts in lib/<mode>/.

Shelf tool / hotkey (see README):
    import hotbox
    hotbox.show()

The old entry point `from hotbox import main; main.start()` still works.
"""
from __future__ import annotations

import math
from pathlib import Path

import hou

from .utils import errors, manager, runner, scripts, settings, utility, widgets
from .utils.qt import (
    QCursor,
    QDesktopServices,
    QEasingCurve,
    QEvent,
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
    """Keys: hotkeys run their script, Shift shows the #shiftlabel texts (Shift+click runs that variant),
    Tab starts search (type, Enter runs the first match, Esc/Tab ends it), Esc and ` close."""

    FADE_IN = 120  # ms
    FADE_OUT = widgets.Button.PRESS_MS  # the menu fades together with the pressed button
    SEARCH_KEYS = (int(Qt.Key_Tab), int(Qt.Key_Backtab))

    def __init__(self, lib_dir: Path | None = None):
        """lib_dir: only this lib folder (tests, images); default: HOTBOX_PATH folders + the built-in lib/"""
        super().__init__(hou.qt.mainWindow())
        if lib_dir is not None:
            self.lib_roots = [Path(lib_dir)]
        else:
            self.lib_roots = scripts.libRoots(LIB_DIR, hou.getenv(scripts.PATH_ENV))
        self.lib_dir = self.lib_roots[0]
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._triggered = False
        self._modifiers: frozenset[str] = frozenset()
        self.searchText: str | None = None  # None: not searching
        self._searchMatch = None

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
        # Scripts of turned off packages are not shown (Script Manager -> gear)
        data = settings.load()
        library = scripts.availableScripts(scripts.scanLibrary(self.lib_roots, self.mode),
                                           settings.enabledChecker(data))
        self.scripts_buttons = widgets.ScriptGrid(library, context=self.context.context, parent=self)
        self.keybindings = self.scripts_buttons.keybindings()
        self.recent_row = self.recentRow(library, data)
        self.script_buttons = self.scripts_buttons.buttons + (self.recent_row.buttons if self.recent_row else [])

        self.open_hotbox_button = widgets.Button("Open HotBox folder")
        self.central_button = widgets.Button(self.context.title, icon=self.context.icon)
        self.script_manager_button = widgets.Button("Script Manager")

        central_layout = widgets.HLayout([self.open_hotbox_button, self.central_button, self.script_manager_button])
        central_layout.setSpacing(widgets.ScriptGrid.COLUMN_GAP)
        central_layout.setAlignment(Qt.AlignHCenter)

        layout = QVBoxLayout()
        # Room around the buttons for the press zoom (painted by the overlay)
        margin = math.ceil(widgets.Button.WIDTH * (widgets.Button.PRESS_SCALE - 1) / 2) + 2
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(widgets.ScriptGrid.ROW_GAP * 2)
        layout.addWidget(self.scripts_buttons, 0, Qt.AlignHCenter)
        if self.recent_row is not None:
            layout.addWidget(self.recent_row, 0, Qt.AlignHCenter)
        layout.addLayout(central_layout)
        self.setLayout(layout)
        self.animationOverlay = widgets.AnimationOverlay(self)

        actions = {button: (lambda s=button.script: self.runScript(s)) for button in self.script_buttons}
        actions[self.open_hotbox_button] = self.openHotboxFolder
        actions[self.central_button] = None  # just close
        actions[self.script_manager_button] = self.startManager
        for button, action in actions.items():
            button.clicked.connect(lambda checked=False, b=button, a=action: self.trigger(b, a))
        if QGuiApplication.queryKeyboardModifiers() & Qt.ShiftModifier:  # opened with Shift held
            self.setShifted(True)

    def recentRow(self, library, data):
        """Row of the last run scripts that make sense here (shown in this context), None if there are none"""
        count = settings.recentCount(data)
        in_context, root = scripts.scriptsForContext(library, self.context.context)
        shown = {script.relpath: script for script in in_context + root}
        recent = [shown[relpath] for relpath in settings.recentScripts(self.mode, data) if relpath in shown][:count]
        return widgets.RecentRow(recent, parent=self) if recent else None

    def mousePressEvent(self, event):
        """A click inside the hotbox but not on a button closes it, like a click outside.
        Buttons take their clicks; empty space (gaps, group frames, margins) passes them up to here."""
        self.close()

    def resizeEvent(self, event):
        self.animationOverlay.setGeometry(self.rect())
        self.animationOverlay.raise_()
        super().resizeEvent(event)

    def trigger(self, button, action=None):
        """Pressed button grows and fades out, the menu fades out with it, then the action runs.

        The hotbox is closed before the action: scripts open dialogs, select nodes in the viewport, etc.
        Only the first trigger counts.
        """
        if self._triggered:
            return
        self._triggered = True
        self._modifiers = widgets.modifierNames(QGuiApplication.keyboardModifiers())

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
        settings.addRecent(self.mode, script.relpath)
        label = (script.shiftLabel if "shift" in self._modifiers else None) or script.label
        runner.runScript(script.runPath, label=label, modifiers=self._modifiers,
                         on_error=lambda error: errors.showScriptError(error, self.lib_roots))

    # --- keys ---------------------------------------------------------------------------------------------------

    def event(self, event):
        """Tab would move the focus between buttons: here it starts/ends search"""
        if event.type() == QEvent.KeyPress and int(event.key()) in self.SEARCH_KEYS:
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = int(event.key())
        if key == int(Qt.Key_Shift):
            self.setShifted(True)
            return
        if key in self.SEARCH_KEYS:
            self.setSearch(None if self.searchText is not None else "")
            return
        if self.searchText is not None:
            self.searchKey(event)
            return
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

    def keyReleaseEvent(self, event):
        if int(event.key()) == int(Qt.Key_Shift):
            self.setShifted(False)
            return
        super().keyReleaseEvent(event)

    def setShifted(self, shifted: bool):
        for button in self.script_buttons:
            button.setShifted(shifted)

    # --- search -------------------------------------------------------------------------------------------------

    def searchKey(self, event):
        key = int(event.key())
        if key == int(Qt.Key_Escape):
            self.setSearch(None)
        elif key in (int(Qt.Key_Return), int(Qt.Key_Enter)):
            if self._searchMatch is not None:
                button = self._searchMatch
                self.trigger(button, lambda s=button.script: self.runScript(s))
        elif key == int(Qt.Key_Backspace):
            self.setSearch(self.searchText[:-1])
        elif event.text() and event.text().isprintable():
            self.setSearch(self.searchText + event.text())

    def setSearch(self, text: str | None):
        """None ends the search. Buttons that don't match fade out, the first match is highlighted."""
        self.searchText = text
        match = None
        for button in self.script_buttons:
            labels = f"{button.script.label} {button.script.shiftLabel or ''}"
            matches = not text or scripts.matchesSearch(labels, text)
            button.setDimmed(not matches)
            if matches and text and match is None:
                match = button
        if self._searchMatch is not None and self._searchMatch is not match:
            self._searchMatch.endHover()
        if match is not None and match is not self._searchMatch:
            match.startHover()
        self._searchMatch = match
        if text is None:
            self.central_button.updateText(self.context.title)
        else:
            self.central_button.updateText(f"Find: {text}_" if text else "Type to find…")

    def openHotboxFolder(self):
        """The first lib folder: your own one when HOTBOX_PATH is set, else the tool folder"""
        folder = self.lib_roots[0] if self.lib_roots[0] != LIB_DIR else PACKAGE_DIR
        QDesktopServices.openUrl(QUrl.fromLocalFile(Path(folder).as_posix()))

    def startManager(self):
        return manager.ScriptManager(lib_folder=self.lib_roots)

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

