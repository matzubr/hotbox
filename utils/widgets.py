from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import hou

from . import scripts as script_lib
from .qt import (
    QColor,
    QComboBox,
    QDesktopServices,
    QEasingCurve,
    QFont,
    QFontDatabase,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QPixmap,
    QPushButton,
    QSize,
    Qt,
    QUrl,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
ICONS_DIR = PACKAGE_DIR / "icons"
FONT_FILE = PACKAGE_DIR / "fonts" / "JosefinSans.ttf"
FONT_FAMILY = "Josefin Sans"
FONT_SIZE = 16
CLOSE_KEYS = (int(Qt.Key_Escape), int(Qt.Key_QuoteLeft))  # Esc and `

_font_loaded = False


def loadFont() -> None:
    """Register the bundled Josefin Sans (SIL OFL, fonts/OFL.txt) once per Houdini session"""
    global _font_loaded
    if _font_loaded:
        return
    _font_loaded = True
    if QFontDatabase.addApplicationFont(FONT_FILE.as_posix()) < 0:
        print(f"HotBox: can't load {FONT_FILE.as_posix()}, using the system font")


def keyCode(hotkey: str | None) -> int | None:
    """Qt key code of a hotkey string ('g', '1', 'F5'); None when empty or invalid.

    Qt6 returns QKeyCombination from QKeySequence[0], Qt5 an int with modifiers.
    """
    if not hotkey:
        return None
    sequence = QKeySequence(hotkey)
    if sequence.count() == 0:
        return None
    combination = sequence[0]
    if hasattr(combination, "key"):
        return int(combination.key())
    return int(combination) & ~int(Qt.KeyboardModifierMask)


def eventKeyCodes(event) -> list[int]:
    """Key codes to match a key press against: the key itself and, for another keyboard layout
    (Russian), the Latin key on the same physical key"""
    codes = [int(event.key())]
    latin = keyCode(script_lib.latinKey(event.text()))
    if latin is not None and latin not in codes:
        codes.append(latin)
    return codes


def mixColor(color: QColor, other: QColor, amount: float) -> QColor:
    """color moved towards other by amount (0..1)"""
    return QColor(
        round(color.red() + (other.red() - color.red()) * amount),
        round(color.green() + (other.green() - color.green()) * amount),
        round(color.blue() + (other.blue() - color.blue()) * amount),
    )


class Button(QPushButton):
    """Flat rounded button with a wrapped label; background animates on hover and press"""

    HOVER = 0.12  # towards white
    PRESSED = 0.28
    DURATION = 140  # ms

    def __init__(
        self,
        label: str = "ButtonText",
        buttonColor: str = "#222222",
        textColor: str = "#e8e8e8",
        icon=None,
        buttonsize: int = 200,
        parent=None,
    ):
        super().__init__(parent)
        loadFont()
        self.buttonWidth = buttonsize
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(self.DURATION)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._applyBackground)

        if isinstance(icon, (QIcon, QPixmap)):
            self.setIcon(icon)
        elif icon:
            filepath = ICONS_DIR / icon
            if filepath.exists():
                self.setIcon(QIcon(filepath.as_posix()))
                self.setIconSize(QSize(buttonsize // 6, buttonsize // 6))
            else:
                print(f"HotBox: no icon {filepath.as_posix()}")

        self.updateText(label)
        self.updateColors(buttonColor, textColor)
        self.setFixedSize(QSize(buttonsize, int(buttonsize * 0.3)))
        self.setFlat(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setDefault(False)

    MAX_LINES = 2

    def updateText(self, text: str):
        """Wrap to MAX_LINES lines; longer labels get a smaller font so they still fit the button"""
        size = FONT_SIZE
        line_width = int(self.buttonWidth * 0.06)
        lines = wrap(text, line_width)
        if len(lines) > self.MAX_LINES:
            size = FONT_SIZE - 3
            lines = wrap(text, int(line_width * FONT_SIZE / size))
        self.setText("\n".join(lines) or text)
        self.setFont(QFont(FONT_FAMILY, size, QFont.Bold))

    def updateColors(self, buttonColor="#222222", textColor="#e8e8e8"):
        self.baseColor = QColor(buttonColor)
        self.hoverColor = mixColor(self.baseColor, QColor("#ffffff"), self.HOVER)
        self.pressedColor = mixColor(self.baseColor, QColor("#ffffff"), self.PRESSED)
        self.textColor = textColor
        self._applyBackground(self.baseColor)

    def background(self) -> QColor:
        return QColor(self._background)

    def _applyBackground(self, color):
        self._background = QColor(color)
        self.setStyleSheet(
            f"""QPushButton{{
                background-color:{self._background.name()};
                color:{self.textColor};
                border-radius:10px;
                border:none;}}"""
        )

    def animateTo(self, color: QColor):
        self._animation.stop()
        self._animation.setStartValue(self.background())
        self._animation.setEndValue(QColor(color))
        self._animation.start()

    def flash(self):
        """Pressed look fading back: feedback for a hotkey"""
        self._applyBackground(self.pressedColor)
        self.animateTo(self.hoverColor if self.underMouse() else self.baseColor)

    def enterEvent(self, event):
        self.animateTo(self.hoverColor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animateTo(self.baseColor)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._animation.stop()
        self._applyBackground(self.pressedColor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.animateTo(self.hoverColor if self.underMouse() else self.baseColor)
        super().mouseReleaseEvent(event)


class ScriptButton(Button):
    """Button that runs a library script"""

    BROKEN_TEXT = "#ff6b6b"

    def __init__(self, script: script_lib.Script, buttonsize: int = 200, parent=None):
        label = f"{script.label} ({script.hotkey})" if script.hotkey else script.label
        text_color = self.BROKEN_TEXT if script.error else script.textcolor
        super().__init__(label, script.buttoncolor, text_color, script.icon, buttonsize, parent)
        self.script = script
        self.hotkey = script.hotkey
        tooltip = script.relpath
        if script.ref:
            tooltip += f"\n→ {script.ref}"
        if script.error:
            tooltip += f"\n{script.error}"
        self.setToolTip(tooltip)


class GroupBlock(QFrame):
    """Buttons of one #group with a caption, GROUP_COLUMNS buttons per row"""

    GROUP_COLUMNS = 2

    def __init__(self, name: str, buttons: list[ScriptButton], parent=None):
        super().__init__(parent)
        self.setObjectName("GroupBlock")
        self.setStyleSheet("#GroupBlock{background-color:rgba(255,255,255,10); border-radius:12px;}")
        caption = QLabel(name, self)
        caption.setFont(QFont(FONT_FAMILY, FONT_SIZE - 4, QFont.Bold))
        caption.setStyleSheet("color:rgba(232,232,232,150); background:transparent;")

        grid = QGridLayout()
        grid.setSpacing(6)
        for index, button in enumerate(buttons):
            grid.addWidget(button, index // self.GROUP_COLUMNS, index % self.GROUP_COLUMNS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(caption)
        layout.addLayout(grid)


class ScriptGrid(QWidget):
    """Context scripts in the left column, root scripts in the right one.

    Each column is a stack of blocks from the top: single buttons and #group blocks, sorted by name.
    """

    def __init__(self, scripts: list[script_lib.Script], context: str = "", parent: QWidget = None):
        super().__init__(parent)
        in_context, root = script_lib.scriptsForContext(scripts, context)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.buttons: list[ScriptButton] = []
        self.columns: list[list[tuple[str, list[ScriptButton]]]] = []
        for column_scripts in (in_context, root):
            if not column_scripts:
                continue
            column_layout = QVBoxLayout()
            column_layout.setAlignment(Qt.AlignTop)
            column = []
            for name, block_scripts in script_lib.groupBlocks(column_scripts):
                buttons = [ScriptButton(script) for script in block_scripts]
                self.buttons += buttons
                column.append((name, buttons))
                if name:
                    column_layout.addWidget(GroupBlock(name, buttons))
                else:
                    column_layout.addWidget(buttons[0], 0, Qt.AlignLeft)
            self.columns.append(column)
            layout.addLayout(column_layout)
        self.setLayout(layout)

        for key, paths in script_lib.duplicateHotkeys(in_context + root).items():
            print(f"HotBox: hotkey '{key}' is used by several scripts, the last one wins: {', '.join(paths)}")

    def keybindings(self) -> dict[int, ScriptButton]:
        bindings = {}
        for button in self.buttons:
            code = keyCode(button.hotkey)
            if code is not None:
                bindings[code] = button
        return bindings


class HLayout(QHBoxLayout):
    """Layout which aligns all input widgets to the left"""

    def __init__(self, widgets=(), align=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        if align:
            self.setAlignment(align)
        for widget in widgets:
            self.addWidget(widget)


class HSeparator(QFrame):
    """Horizontal line"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)


class ScriptManager(QWidget):
    """Browse library scripts and edit their header settings (written back into the script files)"""

    ROOT_ITEM = "(root)"

    def __init__(self, lib_folder: Path, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.lib = Path(lib_folder)
        self.scripts: list[script_lib.Script] = []

        self.setWindowTitle("Script Manager")
        self.setGeometry(300, 300, 1000, 400)
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.initUI()

    def initUI(self):
        main_layout = QHBoxLayout()
        main_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(list(script_lib.MODES))
        self.folders_list = QListWidget()
        self.files_list = QListWidget()

        fc_layout = QVBoxLayout()
        fc_layout.addWidget(self.mode_combobox)
        fc_layout.addWidget(self.folders_list)

        sc_layout = QVBoxLayout()
        sc_layout.addWidget(self.files_list)

        self.name_lineedit = QLineEdit()
        self.group_lineedit = QLineEdit()
        self.group_lineedit.setPlaceholderText("buttons of one group stand together")
        self.button_color_swatch = hou.qt.ColorSwatchButton()
        self.text_color_swatch = hou.qt.ColorSwatchButton()
        self.icon_lineedit = QLineEdit()
        self.icon_lineedit.setPlaceholderText("file name in icons/")
        self.hotkey_lineedit = QLineEdit()
        self.hotkey_lineedit.setPlaceholderText("g, 1, F5...")
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setReadOnly(True)
        self.ref_label = QLabel()
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color:#ffb04a")
        self.warning_label.setWordWrap(True)
        self.save_button = QPushButton("Save")
        self.open_button = QPushButton("Open file")

        tc_layout = QVBoxLayout()
        tc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        tc_layout.addLayout(HLayout([QLabel("Name"), self.name_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Group"), self.group_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Button Color"), self.button_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Text Color"), self.text_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Icon"), self.icon_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Hotkey"), self.hotkey_lineedit]))
        tc_layout.addWidget(self.warning_label)
        tc_layout.addLayout(HLayout([self.save_button, self.open_button]))
        tc_layout.addWidget(HSeparator())
        tc_layout.addLayout(HLayout([QLabel("File"), self.file_lineedit]))
        tc_layout.addWidget(self.ref_label)

        main_layout.addLayout(fc_layout)
        main_layout.addLayout(sc_layout)
        main_layout.addLayout(tc_layout)
        self.setLayout(main_layout)

        self.mode_combobox.currentIndexChanged.connect(self.updateScripts)
        self.folders_list.currentRowChanged.connect(self.updateFilesList)
        self.files_list.currentRowChanged.connect(self.updateInfo)
        self.hotkey_lineedit.textChanged.connect(self.updateWarnings)
        self.icon_lineedit.textChanged.connect(self.updateWarnings)
        self.save_button.clicked.connect(self.save)
        self.open_button.clicked.connect(self.openFile)
        self.updateScripts()
        self.show()

    def currentFolder(self) -> str | None:
        item = self.folders_list.currentItem()
        if item is None:
            return None
        return "" if item.text() == self.ROOT_ITEM else item.text()

    def folderScripts(self) -> list[script_lib.Script]:
        folder = self.currentFolder()
        if folder is None:
            return []
        return [s for s in self.scripts if s.context == folder]

    def updateScripts(self):
        self.scripts = script_lib.scanScripts(self.lib / self.mode_combobox.currentText())
        folders = sorted({s.context for s in self.scripts})
        self.folders_list.clear()
        self.folders_list.addItems([folder or self.ROOT_ITEM for folder in folders])
        if folders:
            self.folders_list.setCurrentRow(0)
        else:
            self.updateFilesList()

    def updateFilesList(self):
        self.files_list.clear()
        files = [s.path.name for s in self.folderScripts()]
        self.files_list.addItems(files)
        if files:
            self.files_list.setCurrentRow(0)
        else:
            self.updateInfo()

    def currentScript(self) -> script_lib.Script | None:
        row = self.files_list.currentRow()
        folder_scripts = self.folderScripts()
        return folder_scripts[row] if 0 <= row < len(folder_scripts) else None

    def updateInfo(self):
        """Fields show the script's own header; inherited values (from #ref) are placeholders"""
        script = self.currentScript()
        own = script.ownSettings if script else {}
        merged = script.settings if script else {}
        for lineedit, key in ((self.name_lineedit, "label"), (self.group_lineedit, "group"),
                              (self.icon_lineedit, "icon"), (self.hotkey_lineedit, "hotkey")):
            lineedit.setText(own.get(key, ""))
        self.name_lineedit.setPlaceholderText(script.label if script else "")
        self.group_lineedit.setPlaceholderText(merged.get("group", "") or "buttons of one group stand together")
        self.icon_lineedit.setPlaceholderText(merged.get("icon", "") or "file name in icons/")
        self.file_lineedit.setText(script.path.as_posix() if script else "")
        if script and script.ref:
            self.ref_label.setText(f"#ref → {script.ref}" + (f"  ({script.error})" if script.error else ""))
        else:
            self.ref_label.setText("")
        if script:
            self.button_color_swatch.setColor(QColor(script.buttoncolor))
            self.text_color_swatch.setColor(QColor(script.textcolor))
        for widget in (self.save_button, self.open_button):
            widget.setEnabled(script is not None)
        self.updateWarnings()

    def warnings(self) -> list[str]:
        script = self.currentScript()
        if script is None:
            return []
        messages = []
        hotkey = self.hotkey_lineedit.text().strip()
        if hotkey and keyCode(hotkey) is None:
            messages.append(f"'{hotkey}' is not a key")
        conflicts = script_lib.hotkeyConflicts(self.scripts, script, hotkey)
        if conflicts:
            messages.append(f"Hotkey '{hotkey}' is also used by: {', '.join(conflicts)}")
        icon = self.icon_lineedit.text().strip()
        if icon and not (ICONS_DIR / icon).exists():
            messages.append(f"No icon icons/{icon}")
        return messages

    def updateWarnings(self):
        self.warning_label.setText("\n".join(self.warnings()))

    def editedSettings(self) -> dict:
        """The script's own header after editing. Values equal to the inherited/default ones that the
        header didn't set are not written: a #ref stub stays a stub."""
        script = self.currentScript()
        if script is None:
            return {}
        own = dict(script.ownSettings)
        inherited = {k: v for k, v in script.settings.items() if k not in own}
        edited = {
            "label": self.name_lineedit.text().strip(),
            "group": self.group_lineedit.text().strip(),
            "buttoncolor": self.button_color_swatch.color().name(),
            "textcolor": self.text_color_swatch.color().name(),
            "icon": self.icon_lineedit.text().strip(),
            "hotkey": self.hotkey_lineedit.text().strip(),
        }
        for key, value in edited.items():
            fallback = inherited.get(key) or script_lib.DEFAULTS.get(key, "")
            if key not in own and value.lower() == fallback.lower():
                continue
            own[key] = value
        return own

    def save(self):
        script = self.currentScript()
        if script is None:
            return
        script_lib.writeHeader(script.path, self.editedSettings())
        folder_row, file_row = self.folders_list.currentRow(), self.files_list.currentRow()
        self.scripts = script_lib.scanScripts(self.lib / self.mode_combobox.currentText())
        self.folders_list.setCurrentRow(folder_row)
        self.files_list.setCurrentRow(file_row)
        self.updateInfo()

    def openFile(self):
        script = self.currentScript()
        if script is not None:  # the code: the ref target for a #ref
            path = script.runPath or script.path
            QDesktopServices.openUrl(QUrl.fromLocalFile(path.as_posix()))

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)
