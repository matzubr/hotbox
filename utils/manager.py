"""Script Manager: browse library scripts and edit their header settings (written back into the files).

DinoWrite look: frameless rounded window, title bar, dark panels with the gold accent.
Animated buttons (same as the hotbox) and a live preview of the edited button.
"""
from __future__ import annotations

from pathlib import Path

import hou

from . import scripts as script_lib
from .frameless import RoundedWindow, TitleBar
from .qt import (
    QColor,
    QComboBox,
    QDesktopServices,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    Qt,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import ICONS_DIR, AnimationOverlay, Button, HLayout, buttonFont, keyCode, resolveIcon

ACTION_SIZE = (130, 36)


def bodyStyle() -> str:
    c = COLORS
    return f"""
    QLabel {{ background: transparent; color: {c['white']}; }}
    QLabel#Hint {{ color: #8a8a8a; }}
    QLabel#Warning {{ color: {c['warning']}; }}
    QWidget#Panel {{ background-color: {c['grey']}; border-radius: {PANEL_RADIUS}px; }}
    QLineEdit, QComboBox {{
        background-color: {c['grey-dark']}; color: #eeeeee; border: 1px solid {c['border']};
        border-radius: 4px; padding: 4px 6px; selection-background-color: {c['accent']};
    }}
    QLineEdit:hover, QComboBox:hover {{ border: 1px solid #5a4210; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c['accent']}; }}
    QLineEdit:read-only {{ color: #9a9a9a; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['grey-dark']}; color: #eeeeee; border: 1px solid {c['border']};
        selection-background-color: rgba(183, 134, 32, 60%);
    }}
    QListWidget {{
        background-color: {c['grey-dark']}; color: #dddddd; border: 1px solid {c['border']};
        border-radius: 6px; padding: 4px; outline: none;
    }}
    QListWidget::item {{ padding: 5px 8px; border-radius: 4px; }}
    QListWidget::item:hover {{ background-color: rgba(183, 134, 32, 20%); }}
    QListWidget::item:selected {{ background-color: rgba(183, 134, 32, 55%); color: #ffffff; }}
    QToolTip {{ background-color: {c['grey-dark']}; color: {c['white']}; border: 1px solid {c['border']}; }}
    QScrollBar:vertical {{ background: {c['grey-dark']}; width: 10px; border: none; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #4a4a4a; border-radius: 4px; min-height: 20px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    """


def panel(*widgets_or_layouts, title: str = "") -> QWidget:
    widget = QWidget()
    widget.setObjectName("Panel")
    widget.setAttribute(Qt.WA_StyledBackground)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(10, 8, 10, 10)
    if title:
        caption = QLabel(title)
        caption.setFont(buttonFont(11))
        layout.addWidget(caption)
    for item in widgets_or_layouts:
        if isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    return widget


class ScriptManager(RoundedWindow, QWidget):
    """Browse library scripts and edit their header settings"""

    ROOT_ITEM = "(root)"

    def __init__(self, lib_folder: Path, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.lib = Path(lib_folder)
        self.scripts: list[script_lib.Script] = []

        self.setWindowTitle("Script Manager")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()
        self.resize(1000, 480)
        self.initUI()
        self.animationOverlay = AnimationOverlay(self)
        self.fadeIn()
        self.show()

    def initUI(self):
        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(list(script_lib.MODES))
        self.folders_list = QListWidget()
        self.files_list = QListWidget()

        self.name_lineedit = QLineEdit()
        self.group_lineedit = QLineEdit()
        self.button_color_swatch = hou.qt.ColorSwatchButton()
        self.text_color_swatch = hou.qt.ColorSwatchButton()
        self.icon_lineedit = QLineEdit()
        self.hotkey_lineedit = QLineEdit()
        self.hotkey_lineedit.setPlaceholderText("g, 1, F5...")
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setReadOnly(True)
        self.ref_label = QLabel()
        self.ref_label.setObjectName("Hint")
        self.warning_label = QLabel()
        self.warning_label.setObjectName("Warning")
        self.warning_label.setWordWrap(True)

        self.preview = Button("Preview")
        self.preview.setToolTip("How the button looks in the hotbox")
        self.save_button = Button("Save", buttonColor=COLORS["accent"], textColor="#ffffff", size=ACTION_SIZE,
                                  fontSize=12)
        self.open_button = Button("Open file", buttonColor="#4a4a4a", size=ACTION_SIZE, fontSize=12)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        rows = [
            ("Name", self.name_lineedit),
            ("Group", self.group_lineedit),
            ("Button color", self.button_color_swatch),
            ("Text color", self.text_color_swatch),
            ("Icon", self.icon_lineedit),
            ("Hotkey", self.hotkey_lineedit),
        ]
        for row, (text, widget) in enumerate(rows):
            label = QLabel(text)
            label.setFont(buttonFont(10))
            form.addWidget(label, row, 0)
            form.addWidget(widget, row, 1)
        icon_hint = QLabel("file in icons/ or a Houdini icon: SOP_null, OBJ_camera...")
        icon_hint.setObjectName("Hint")

        preview_row = HLayout([self.preview], align=Qt.AlignHCenter)
        actions = HLayout([self.save_button, self.open_button], align=Qt.AlignRight)
        editor = panel(form, icon_hint, self.warning_label, preview_row, actions, title="Button")
        file_row = HLayout([QLabel("File"), self.file_lineedit], align=None)

        lists = HLayout([
            panel(self.mode_combobox, self.folders_list, title="Mode / folder"),
            panel(self.files_list, title="Scripts"),
        ], align=None)
        columns = HLayout([], align=None)
        columns.addLayout(lists, 1)
        columns.addWidget(editor, 1)

        body = QWidget()
        body.setStyleSheet(bodyStyle())
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 4, 12, 12)
        body_layout.addLayout(columns)
        body_layout.addLayout(file_row)
        body_layout.addWidget(self.ref_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Script Manager"))
        layout.addWidget(body)

        self.mode_combobox.currentIndexChanged.connect(self.updateScripts)
        self.folders_list.currentRowChanged.connect(self.updateFilesList)
        self.files_list.currentRowChanged.connect(self.updateInfo)
        for lineedit in (self.name_lineedit, self.group_lineedit, self.icon_lineedit, self.hotkey_lineedit):
            lineedit.textChanged.connect(self.onEdited)
        for swatch in (self.button_color_swatch, self.text_color_swatch):
            signal = getattr(swatch, "colorChanged", None)
            if signal is not None:
                signal.connect(self.onEdited)
        self.save_button.clicked.connect(self.save)
        self.open_button.clicked.connect(self.openFile)
        self.updateScripts()

    def resizeEvent(self, event):
        overlay = getattr(self, "animationOverlay", None)
        if overlay is not None:
            overlay.setGeometry(self.rect())
            overlay.raise_()
        super().resizeEvent(event)

    # --- lists --------------------------------------------------------------------------------------------------

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
        scripts = self.folderScripts()
        for script in scripts:
            self.files_list.addItem(script.path.name)
            item = self.files_list.item(self.files_list.count() - 1)
            icon = resolveIcon(script.icon)
            if icon is not None:
                item.setIcon(icon)
            if script.ref:
                item.setToolTip(f"#ref → {script.ref}")
        if scripts:
            self.files_list.setCurrentRow(0)
        else:
            self.updateInfo()

    def currentScript(self) -> script_lib.Script | None:
        row = self.files_list.currentRow()
        folder_scripts = self.folderScripts()
        return folder_scripts[row] if 0 <= row < len(folder_scripts) else None

    # --- editor -------------------------------------------------------------------------------------------------

    def updateInfo(self):
        """Fields show the script's own header; inherited values (from #ref) are placeholders"""
        script = self.currentScript()
        own = script.ownSettings if script else {}
        merged = script.settings if script else {}
        self._loading = True
        for lineedit, key in ((self.name_lineedit, "label"), (self.group_lineedit, "group"),
                              (self.icon_lineedit, "icon"), (self.hotkey_lineedit, "hotkey")):
            lineedit.setText(own.get(key, ""))
        self.name_lineedit.setPlaceholderText(script.label if script else "")
        self.group_lineedit.setPlaceholderText(merged.get("group", "") or "buttons of one group stand together")
        self.icon_lineedit.setPlaceholderText(merged.get("icon", "") or "dino.svg / SOP_null")
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
        self._loading = False
        self.onEdited()

    def onEdited(self, *args):
        if getattr(self, "_loading", False):
            return
        self.updateWarnings()
        self.updatePreview()

    def updatePreview(self):
        script = self.currentScript()
        if script is None:
            self.preview.setVisible(False)
            return
        self.preview.setVisible(True)
        label = self.name_lineedit.text().strip() or script.label
        hotkey = self.hotkey_lineedit.text().strip()
        self.preview.setButtonIcon(self.icon_lineedit.text().strip() or script.settings.get("icon"))
        self.preview.updateColors(self.button_color_swatch.color().name(), self.text_color_swatch.color().name())
        self.preview.updateText(f"{label} ({hotkey})" if hotkey else label)
        # A short wave shows that the preview follows the edit
        self.preview.startHover()
        QTimer.singleShot(Button.HOVER_MS + 120, self.preview.endHover)

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
        if icon and resolveIcon(icon) is None:
            messages.append(f"No icon '{icon}': not in {ICONS_DIR.name}/ and not a Houdini icon")
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
        self.updateFilesList()
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
