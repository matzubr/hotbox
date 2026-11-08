from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import hou

from . import scripts as script_lib
from .qt import (
    QColor,
    QComboBox,
    QFont,
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
    QVBoxLayout,
    QWidget,
)

ICONS_DIR = Path(__file__).resolve().parents[1] / "icons"
FONT_FAMILY = "Josefin Sans"
FONT_SIZE = 16
CLOSE_KEYS = (int(Qt.Key_Escape), int(Qt.Key_QuoteLeft))  # Esc and `


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


class Button(QPushButton):
    """Flat rounded button with a wrapped label"""

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
        self.buttonWidth = buttonsize

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
        self.setFont(QFont(FONT_FAMILY, FONT_SIZE, QFont.Bold))
        self.updateColors(buttonColor, textColor)
        self.setFixedSize(QSize(buttonsize, int(buttonsize * 0.3)))
        self.setFlat(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setDefault(False)

    def updateText(self, text: str):
        max_line_width = int(self.buttonWidth * 0.06)
        self.setText("\n".join(wrap(text, max_line_width)) or text)

    def updateColors(self, buttonColor="#222222", textColor="#e8e8e8"):
        self.setStyleSheet(
            f"""QPushButton{{
                background-color:{buttonColor};
                color:{textColor};
                border-radius:10px;
                border:none;}}
            QPushButton::hover{{
                background-color:#262626}}"""
        )


class ScriptButton(Button):
    """Button that runs a library script"""

    def __init__(self, script: script_lib.Script, buttonsize: int = 200, parent=None):
        label = f"{script.label} ({script.hotkey})" if script.hotkey else script.label
        super().__init__(label, script.buttoncolor, script.textcolor, script.icon, buttonsize, parent)
        self.script = script
        self.hotkey = script.hotkey
        self.setToolTip(script.relpath)


class ScriptGrid(QWidget):
    """Context scripts in the left column, root scripts in the right one; each column fills from the top"""

    def __init__(self, scripts: list[script_lib.Script], context: str = "", parent: QWidget = None):
        super().__init__(parent)
        in_context, root = script_lib.scriptsForContext(scripts, context)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 10)
        self.buttons: list[ScriptButton] = []
        columns = [column for column in (in_context, root) if column]
        for column_index, column in enumerate(columns):
            for row, script in enumerate(column):
                button = ScriptButton(script, parent=self)
                layout.addWidget(button, row, column_index, Qt.AlignTop)
                self.buttons.append(button)
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
    """Browse library scripts and their header settings (read only for now)"""

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
        self.button_color_swatch = hou.qt.ColorSwatchButton()
        self.text_color_swatch = hou.qt.ColorSwatchButton()
        self.icon_lineedit = QLineEdit()
        self.hotkey_lineedit = QLineEdit()
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setReadOnly(True)

        tc_layout = QVBoxLayout()
        tc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        tc_layout.addLayout(HLayout([QLabel("Name"), self.name_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Button Color"), self.button_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Text Color"), self.text_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Icon"), self.icon_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Hotkey"), self.hotkey_lineedit]))
        tc_layout.addWidget(HSeparator())
        tc_layout.addLayout(HLayout([QLabel("File"), self.file_lineedit]))

        main_layout.addLayout(fc_layout)
        main_layout.addLayout(sc_layout)
        main_layout.addLayout(tc_layout)
        self.setLayout(main_layout)

        self.mode_combobox.currentIndexChanged.connect(self.updateScripts)
        self.folders_list.currentRowChanged.connect(self.updateFilesList)
        self.files_list.currentRowChanged.connect(self.updateInfo)
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
        script = self.currentScript()
        self.name_lineedit.setText(script.label if script else "")
        self.icon_lineedit.setText((script.icon or "") if script else "")
        self.hotkey_lineedit.setText((script.hotkey or "") if script else "")
        self.file_lineedit.setText(script.path.as_posix() if script else "")
        if script:
            self.button_color_swatch.setColor(QColor(script.buttoncolor))
            self.text_color_swatch.setColor(QColor(script.textcolor))

    def keyPressEvent(self, event):
        if int(event.key()) in CLOSE_KEYS:
            self.close()
            return
        super().keyPressEvent(event)
