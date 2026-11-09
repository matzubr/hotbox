"""Script Manager: browse library scripts and edit them: header settings and the code.

DinoWrite look: frameless rounded window, title bar, dark panels with the gold accent.
Animated buttons (same as the hotbox), a live preview of the edited button and a code panel sliding out.
"""
from __future__ import annotations

from pathlib import Path

import hou

from . import scripts as script_lib
from . import settings
from .editors import ChoiceField, CodeEditor
from .frameless import RoundedWindow, TitleBar
from .newscript import NewScriptWindow
from .packages import PackagesWindow
from .qt import (
    QColor,
    QComboBox,
    QDesktopServices,
    QEasingCurve,
    QGridLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QShortcut,
    Qt,
    QTextCursor,
    QUrl,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import ICONS_DIR, AnimationOverlay, Button, HLayout, buttonFont, keyCode, resolveIcon

ACTION_SIZE = (130, 36)
CODE_WIDTH = 560  # px of the code panel when it is out
CODE_SLIDE_MS = 260

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
    QPushButton#DropDown {{
        background-color: #3b3b3b; color: #dddddd; border: 1px solid {c['border']}; border-radius: 4px;
    }}
    QPushButton#DropDown:hover {{ background-color: rgba(183, 134, 32, 30%); border: 1px solid {c['accent']}; }}
    QMenu {{ background-color: {c['grey-dark']}; color: #eeeeee; border: 1px solid {c['border']}; padding: 4px; }}
    QMenu::item {{ padding: 4px 18px; border-radius: 3px; }}
    QMenu::item:selected {{ background-color: rgba(183, 134, 32, 55%); }}
    QMenu::item:disabled {{ color: #6f6f6f; }}
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
    """Browse library scripts and edit their header settings and code"""

    ROOT_ITEM = "(root)"

    def __init__(self, lib_folder, parent=None):
        """lib_folder: a lib folder or the list of them (HOTBOX_PATH order, the built-in lib last)"""
        super().__init__(parent or hou.qt.mainWindow())
        self.roots = script_lib.asRoots(lib_folder)
        self.scripts: list[script_lib.Script] = []
        self._loading = False
        self._codePath: Path | None = None  # file shown in the code panel
        self._codeDirty = False
        self._codeOpen = 0.0  # 0: hidden, 1: out

        self.setWindowTitle("Script Manager")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()
        self.resize(1000, 520)
        self.initUI()
        self.animationOverlay = AnimationOverlay(self)
        self.fadeIn()
        self.show()

    def initUI(self):
        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(list(script_lib.MODES))
        self.folders_list = QListWidget()
        self.files_list = QListWidget()
        for widget in (self.folders_list, self.files_list):
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            widget.setTextElideMode(Qt.ElideMiddle)

        self.ref_field = ChoiceField(empty_text="No scripts")
        self.ref_lineedit = self.ref_field.lineedit
        self.ref_lineedit.setPlaceholderText("run another script: single/create_null.py")
        self.name_lineedit = QLineEdit()
        self.group_lineedit = QLineEdit()
        self.package_field = ChoiceField(multiple=True, empty_text="No packages yet")
        self.package_lineedit = self.package_field.lineedit
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
        self.code_button = Button("Code ›", buttonColor="#4a4a4a", size=(100, 36), fontSize=12)
        self.code_button.setToolTip("Edit the code here")
        self.new_button = Button("+ New script", buttonColor="#4a4a4a", size=(150, 32), fontSize=12)
        self.new_button.setToolTip("New script file in the library (Ctrl+N)")

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        rows = [
            ("Ref", self.ref_field),
            ("Name", self.name_lineedit),
            ("Group", self.group_lineedit),
            ("Package", self.package_field),
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
        icon_hint = QLabel("Ref, Package: Tab completes, the arrow lists existing values · "
                           "Icon: file in icons/ or a Houdini icon (SOP_null...)")
        icon_hint.setObjectName("Hint")
        icon_hint.setWordWrap(True)

        preview_row = HLayout([self.preview], align=Qt.AlignHCenter)
        actions = HLayout([self.code_button, self.save_button, self.open_button], align=Qt.AlignRight)
        editor = panel(form, icon_hint, self.warning_label, preview_row, actions, title="Button")
        file_row = HLayout([QLabel("File"), self.file_lineedit], align=None)

        self.code_title = QLabel("Code")
        self.code_title.setFont(buttonFont(11))
        self.code_edit = CodeEditor()
        self.code_panel = panel(self.code_title, self.code_edit)
        self.code_panel.setFixedWidth(0)
        self.code_panel.setVisible(False)
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(CODE_SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.valueChanged.connect(self._applySlide)

        lists = HLayout([
            panel(self.mode_combobox, self.folders_list, title="Mode / folder"),
            panel(self.files_list, HLayout([self.new_button], align=Qt.AlignHCenter), title="Scripts"),
        ], align=None)
        columns = HLayout([], align=None)
        columns.addLayout(lists, 1)
        columns.addWidget(editor, 1)
        columns.addWidget(self.code_panel)

        body = QWidget()
        body.setStyleSheet(bodyStyle())
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 4, 12, 12)
        body_layout.addLayout(columns)
        body_layout.addLayout(file_row)
        body_layout.addWidget(self.ref_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Script Manager", on_settings=self.openPackages))
        layout.addWidget(body)

        self.mode_combobox.currentIndexChanged.connect(self.updateScripts)
        self.folders_list.currentRowChanged.connect(self.updateFilesList)
        self.files_list.currentRowChanged.connect(self.updateInfo)
        for lineedit in (self.ref_lineedit, self.name_lineedit, self.group_lineedit, self.package_lineedit,
                         self.icon_lineedit, self.hotkey_lineedit):
            lineedit.textChanged.connect(self.onEdited)
        for swatch in (self.button_color_swatch, self.text_color_swatch):
            signal = getattr(swatch, "colorChanged", None)
            if signal is not None:
                signal.connect(self.onEdited)
        self.code_edit.textChanged.connect(self._onCodeEdited)
        self.save_button.clicked.connect(self.save)
        self.open_button.clicked.connect(self.openFile)
        self.code_button.clicked.connect(self.toggleCode)
        self.new_button.clicked.connect(self.newScript)
        QShortcut(QKeySequence.New, self, self.newScript)
        self.updateChoices()
        self.updateScripts()

    def resizeEvent(self, event):
        overlay = getattr(self, "animationOverlay", None)
        if overlay is not None:
            overlay.setGeometry(self.rect())
            overlay.raise_()
        super().resizeEvent(event)

    # --- lists --------------------------------------------------------------------------------------------------

    def updateChoices(self):
        """Values offered by Tab and ▾: existing scripts for Ref, existing packages for Package"""
        self.ref_field.setChoices(script_lib.scriptRefs(self.roots))
        self.package_field.setChoices(list(script_lib.allPackages(self.roots)))

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
        self.scripts = script_lib.scanLibrary(self.roots, self.mode_combobox.currentText())
        folders = sorted({s.context for s in self.scripts})
        self.folders_list.clear()
        self.folders_list.addItems([folder or self.ROOT_ITEM for folder in folders])
        if folders:
            self.folders_list.setCurrentRow(0)
        else:
            self.updateFilesList()

    def updateFilesList(self):
        row = self.files_list.currentRow()
        self.files_list.clear()
        scripts = self.folderScripts()
        isEnabled = settings.enabledChecker()
        for script in scripts:
            available = script.isAvailable(isEnabled)
            text = script.path.name + self.rootSuffix(script)
            self.files_list.addItem(text if available else f"{text}  — off")
            item = self.files_list.item(self.files_list.count() - 1)
            if not available:
                item.setForeground(QColor("#6f6f6f"))
            icon = resolveIcon(script.icon)
            if icon is not None:
                item.setIcon(icon)
            tooltip = []
            if script.ref:
                tooltip.append(f"#ref → {script.ref}")
            if script.packages:
                tooltip.append(f"package: {', '.join(script.packages)}" + ("" if available else " (turned off)"))
            tooltip.append(script.path.as_posix())
            item.setToolTip("\n".join(tooltip))
        if scripts:
            self.files_list.setCurrentRow(row if 0 <= row < len(scripts) else 0)
        else:
            self.updateInfo()

    def rootName(self, root: Path) -> str:
        root = Path(root)
        return root.parent.name if root.name.lower() == "lib" else root.name

    def rootSuffix(self, script: script_lib.Script) -> str:
        """'  · studio' for scripts from HOTBOX_PATH folders; nothing for the built-in lib"""
        if len(self.roots) < 2 or script.root is None or script.root == self.roots[-1]:
            return ""
        return f"  · {self.rootName(script.root)}"

    def currentScript(self) -> script_lib.Script | None:
        row = self.files_list.currentRow()
        folder_scripts = self.folderScripts()
        return folder_scripts[row] if 0 <= row < len(folder_scripts) else None

    def scriptRefValue(self, script: script_lib.Script) -> str:
        """The script as a #ref value: 'single/create_null.py'"""
        return f"{self.mode_combobox.currentText()}/{script.relpath}"

    # --- editor -------------------------------------------------------------------------------------------------

    def inherited(self) -> tuple[dict, str | None]:
        """(settings inherited through the Ref field as it is now, reference error)"""
        script = self.currentScript()
        ref = self.ref_lineedit.text().strip()
        if script is None or not ref:
            return {}, None
        _target, merged, error = script_lib.resolveRef(script.path, {"ref": ref}, self.roots)
        merged.pop("ref", None)
        return merged, error

    def updateInfo(self):
        """Fields show the script's own header; inherited values (from #ref) are placeholders"""
        self.maybeSaveCode()
        script = self.currentScript()
        own = script.ownSettings if script else {}
        self._loading = True
        for lineedit, key in ((self.ref_lineedit, "ref"), (self.name_lineedit, "label"),
                              (self.group_lineedit, "group"), (self.package_lineedit, "package"),
                              (self.icon_lineedit, "icon"), (self.hotkey_lineedit, "hotkey")):
            lineedit.setText(own.get(key, ""))
        self.ref_field.setChoices([r for r in script_lib.scriptRefs(self.roots)
                                   if script is None or r != self.scriptRefValue(script)])
        self.file_lineedit.setText(script.path.as_posix() if script else "")
        if script:
            self.button_color_swatch.setColor(QColor(script.buttoncolor))
            self.text_color_swatch.setColor(QColor(script.textcolor))
        for widget in (self.save_button, self.open_button, self.code_button):
            widget.setEnabled(script is not None)
        self._lastRef = own.get("ref", "")
        self.loadCode()
        self._loading = False
        self.onEdited()

    def onEdited(self, *args):
        if self._loading:
            return
        script = self.currentScript()
        own = script.ownSettings if script else {}
        inherited, error = self.inherited()
        ref = self.ref_lineedit.text().strip()
        if ref != getattr(self, "_lastRef", ""):  # new target: colors the header doesn't set follow it
            self._lastRef = ref
            self._loading = True
            for swatch, key in ((self.button_color_swatch, "buttoncolor"), (self.text_color_swatch, "textcolor")):
                if key not in own:
                    swatch.setColor(QColor(inherited.get(key) or script_lib.DEFAULTS[key]))
            self._loading = False
        stem = script.path.stem if script else ""
        self.name_lineedit.setPlaceholderText(inherited.get("label") or stem)
        self.group_lineedit.setPlaceholderText(inherited.get("group") or "buttons of one group stand together")
        self.package_lineedit.setPlaceholderText(inherited.get("package") or "shown only when the package is on")
        self.icon_lineedit.setPlaceholderText(inherited.get("icon") or "dino.svg / SOP_null")
        if ref:
            self.ref_label.setText(f"#ref → {ref}" + (f"  ({error})" if error else ""))
        else:
            self.ref_label.setText("")
        self.updateWarnings()
        self.updatePreview()

    def updatePreview(self):
        """Follows the fields as they are typed (no animation: it would blink on every key)"""
        script = self.currentScript()
        if script is None:
            self.preview.setVisible(False)
            return
        self.preview.setVisible(True)
        inherited, _error = self.inherited()
        label = self.name_lineedit.text().strip() or inherited.get("label") or script.path.stem
        hotkey = self.hotkey_lineedit.text().strip()
        self.preview.setButtonIcon(self.icon_lineedit.text().strip() or inherited.get("icon"))
        self.preview.updateColors(self.button_color_swatch.color().name(), self.text_color_swatch.color().name())
        self.preview.updateText(f"{label} ({hotkey})" if hotkey else label)

    def warnings(self) -> list[str]:
        script = self.currentScript()
        if script is None:
            return []
        messages = []
        _inherited, error = self.inherited()
        if error:
            messages.append(error)
        hotkey = self.hotkey_lineedit.text().strip()
        if hotkey and keyCode(hotkey) is None:
            messages.append(f"'{hotkey}' is not a key")
        shown = script_lib.availableScripts(self.scripts, settings.enabledChecker())
        conflicts = script_lib.hotkeyConflicts(shown, script, hotkey)
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
        inherited, _error = self.inherited()
        edited = {
            "ref": self.ref_lineedit.text().strip(),
            "label": self.name_lineedit.text().strip(),
            "group": self.group_lineedit.text().strip(),
            "package": self.package_lineedit.text().strip(),
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

    # --- code panel ---------------------------------------------------------------------------------------------

    def loadCode(self):
        """Code of the script, or of its ref target (that is the code that runs)"""
        script = self.currentScript()
        path = (script.runPath or None) if script else None
        self._codePath = path
        self.code_edit.blockSignals(True)
        self.code_edit.setPlainText(script_lib.readBody(path) if path else "")
        self.code_edit.setExtraSelections([])
        self.code_edit.blockSignals(False)
        self.code_edit.setReadOnly(path is None)
        self._codeDirty = False
        if script is None:
            title = "Code"
        elif path is None:
            title = "Code: broken #ref"
        else:
            title = f"Code · {self.relativeToLib(path)}" + ("  (ref target)" if path != script.path else "")
        self.code_title.setText(title)
        self.code_title.setToolTip(path.as_posix() if path else "")

    def relativeToLib(self, path: Path) -> str:
        for root in self.roots:
            try:
                return Path(path).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
        return Path(path).name

    def _onCodeEdited(self):
        if not self._codeDirty:
            self._codeDirty = True
            self.code_title.setText(self.code_title.text() + "  ●")

    def maybeSaveCode(self):
        """Before showing another script: save or drop unsaved code"""
        if not (self._codeDirty and self._codePath):
            return
        answer = QMessageBox.question(self, "Script Manager",
                                      f"Save the code changes in {self.relativeToLib(self._codePath)}?",
                                      QMessageBox.Save | QMessageBox.Discard, QMessageBox.Save)
        if answer == QMessageBox.Save:
            script_lib.writeBody(self._codePath, self.code_edit.toPlainText())
        self._codeDirty = False

    def toggleCode(self):
        opening = self._codeOpen < 0.5
        if opening:
            self._baseWidth = self.width()
            self.code_panel.setVisible(True)
        self._slide.stop()
        self._slide.setStartValue(self._codeOpen)
        self._slide.setEndValue(1.0 if opening else 0.0)
        self._slide.start()
        self.code_button.updateText("‹ Code" if opening else "Code ›")

    def _applySlide(self, value):
        self._codeOpen = float(value)
        width = int(CODE_WIDTH * self._codeOpen)
        self.code_panel.setFixedWidth(width)
        self.code_panel.setVisible(width > 0)
        base = getattr(self, "_baseWidth", self.width())
        self.resize(base + width + (6 if width else 0), self.height())

    # --- actions ------------------------------------------------------------------------------------------------

    def save(self):
        script = self.currentScript()
        if script is None:
            return
        code = self.code_edit.toPlainText() if self._codeDirty and self._codePath else None
        if code is not None and self._codePath == script.path:
            script_lib.writeHeader(script.path, self.editedSettings(), body=code)
        else:
            script_lib.writeHeader(script.path, self.editedSettings())
            if code is not None:
                script_lib.writeBody(self._codePath, code)
        self._codeDirty = False
        folder_row, file_row = self.folders_list.currentRow(), self.files_list.currentRow()
        self.scripts = script_lib.scanLibrary(self.roots, self.mode_combobox.currentText())
        self.updateChoices()
        self.folders_list.setCurrentRow(folder_row)
        self.updateFilesList()
        self.files_list.setCurrentRow(file_row)
        self.updateInfo()

    def newScript(self):
        """Window for a new script, in the current mode and folder; the new file is selected and its code shown"""
        self.maybeSaveCode()
        folder = self.currentFolder() or ""
        self.new_window = NewScriptWindow(self.roots, mode=self.mode_combobox.currentText(), folder=folder,
                                          stylesheet=bodyStyle(), parent=self)
        self.new_window.created.connect(self.onScriptCreated)
        center = self.mapToGlobal(self.rect().center())
        self.new_window.move(center.x() - self.new_window.width() // 2, center.y() - self.new_window.height() // 2)
        self.new_window.show()
        return self.new_window

    def onScriptCreated(self, path: Path):
        self.updateChoices()
        self.showScript(path)
        self.code_edit.setFocus()
        self.code_edit.moveCursor(QTextCursor.End)

    def openPackages(self):
        """Gear: turn packages on/off; the list greys out scripts of turned off packages"""
        self.packages_window = PackagesWindow(self.roots, parent=self)
        self.packages_window.changed.connect(self.updateFilesList)
        top_right = self.mapToGlobal(self.rect().topRight())  # under the gear, inside the manager
        self.packages_window.move(top_right.x() - self.packages_window.width() - 20, top_right.y() + 50)
        self.packages_window.show()
        return self.packages_window

    def showScript(self, path: Path, line: int | None = None) -> bool:
        """Select the script file (searched in every mode) and show its code at the line (1-based, in the file)"""
        path = Path(path).resolve()
        for mode_index, mode in enumerate(script_lib.MODES):
            scripts = script_lib.scanLibrary(self.roots, mode)
            match = next((s for s in scripts if s.path.resolve() == path), None)
            if match is None:
                continue
            self.mode_combobox.setCurrentIndex(mode_index)
            self.updateScripts()  # also when the mode was already selected: the file may be new
            folders = [self.folders_list.item(i).text() for i in range(self.folders_list.count())]
            self.folders_list.setCurrentRow(folders.index(match.context or self.ROOT_ITEM))
            self.files_list.setCurrentRow([s.relpath for s in self.folderScripts()].index(match.relpath))
            if self._codeOpen < 0.5:
                self.toggleCode()
            if line:
                body_line = line - script_lib.headerLineCount(match.runPath or match.path)
                self.code_edit.showLine(body_line)
            return True
        return False

    def openFile(self):
        script = self.currentScript()
        if script is not None:  # the code: the ref target for a #ref
            path = script.runPath or script.path
            QDesktopServices.openUrl(QUrl.fromLocalFile(path.as_posix()))

    def closeEvent(self, event):
        self.maybeSaveCode()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)
