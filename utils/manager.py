"""Script Manager: browse library scripts and edit them: header settings and the code.

DinoWrite look: frameless rounded window, title bar, dark panels with the gold accent.
Animated buttons (same as the hotbox), a live preview of the edited button and a code panel sliding out.
"""
from __future__ import annotations

from pathlib import Path

import hou

from . import scripts as script_lib
from . import settings
from .editors import ChoiceField, CodeEditor, HotkeyEdit
from .frameless import RoundedWindow, TitleBar
from .iconbrowser import IconBrowser
from .newscript import NewScriptWindow
from .packages import PackagesWindow
from .qt import (
    QColor,
    QComboBox,
    QDesktopServices,
    QEasingCurve,
    QFont,
    QFontMetrics,
    QGridLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPainter,
    QPushButton,
    QRectF,
    QShortcut,
    QSize,
    QStyle,
    QStyledItemDelegate,
    Qt,
    QTextCursor,
    QUrl,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import (
    ICONS_DIR,
    NEUTRAL_TEXT,
    AnimationOverlay,
    Button,
    HLayout,
    ScriptButton,
    buttonFont,
    keycapFont,
    keycapText,
    keyCode,
    resolveIcon,
    setIconFolders,
)

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
        selection-background-color: rgba(255, 255, 255, 16%);
    }}
    QListWidget {{
        background-color: {c['grey-dark']}; color: #dddddd; border: 1px solid {c['border']};
        border-radius: 6px; padding: 4px; outline: none;
    }}
    QListWidget::item {{ padding: 5px 8px; border-radius: 4px; }}
    QListWidget::item:hover {{ background-color: rgba(255, 255, 255, 6%); }}
    QListWidget::item:selected {{ background-color: rgba(255, 255, 255, 16%); color: #ffffff; }}
    QPushButton#Fold {{ background: transparent; color: #9a9a9a; border: none; text-align: left; padding: 2px 0; }}
    QPushButton#Fold:hover {{ color: {c['white']}; }}
    QPushButton#DropDown {{
        background-color: #3b3b3b; color: #dddddd; border: 1px solid {c['border']}; border-radius: 4px;
    }}
    QPushButton#DropDown:hover {{ background-color: rgba(183, 134, 32, 30%); border: 1px solid {c['accent']}; }}
    QMenu {{ background-color: {c['grey-dark']}; color: #eeeeee; border: 1px solid {c['border']}; padding: 4px; }}
    QMenu::item {{ padding: 4px 18px; border-radius: 3px; }}
    QMenu::item:selected {{ background-color: rgba(255, 255, 255, 16%); }}
    QMenu::item:disabled {{ color: #6f6f6f; }}
    QToolTip {{ background-color: {c['grey-dark']}; color: {c['white']}; border: 1px solid {c['border']}; }}
    QScrollBar:vertical {{ background: {c['grey-dark']}; width: 10px; border: none; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #4a4a4a; border-radius: 4px; min-height: 20px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollBar:horizontal {{ background: {c['grey-dark']}; height: 10px; border: none; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: #4a4a4a; border-radius: 4px; min-width: 20px; }}
    QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    """


MODE_TIPS = ("all: nothing is selected", "multiple: several nodes are selected", "single: one node is selected")


def swatchRow(swatch) -> QWidget:
    """A color swatch of its own size, left aligned in the form"""
    row = QWidget()
    layout = HLayout([swatch])
    layout.setContentsMargins(0, 0, 0, 0)
    row.setLayout(layout)
    row.setToolTip(swatch.toolTip())
    swatch.setFixedWidth(64)
    return row


LABEL_WIDTH, LABEL_GAP = 78, 10
FIELD_INDENT = LABEL_WIDTH + LABEL_GAP  # left edge of the fields in a form


def formGrid(rows) -> QGridLayout:
    """Label | field rows"""
    form = QGridLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(LABEL_GAP)
    form.setVerticalSpacing(6)
    form.setColumnMinimumWidth(0, LABEL_WIDTH)
    for row, (text, widget) in enumerate(rows):
        label = QLabel(text)
        label.setFont(buttonFont(10))
        label.setToolTip(widget.toolTip())
        form.addWidget(label, row, 0)
        form.addWidget(widget, row, 1)
    return form


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
        if isinstance(item, int):
            layout.addStretch(item)  # a number: room that grows
        elif isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    return widget


FILE_ROLE = int(Qt.UserRole) + 1  # second line of a script in the list: file name (· lib folder, — off)
HOTKEY_ROLE = int(Qt.UserRole) + 2


class ScriptItemDelegate(QStyledItemDelegate):
    """A script in the list as the user thinks of it: icon, button name, the file in grey under it, the keycap"""

    ROW_HEIGHT = 40
    KEYCAP_HEIGHT = 18

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(1, 1, -1, -1)
        selected = bool(option.state & QStyle.State_Selected)
        if selected or option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 40 if selected else 14))
            painter.drawRoundedRect(rect, 5, 5)

        x = rect.left() + 8
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, int(x), int(rect.center().y() - 9), 18, 18)
        x += 26

        right = rect.right() - 8
        hotkey = index.data(HOTKEY_ROLE) or ""
        if hotkey:
            font = keycapFont(8.5)
            width = max(float(self.KEYCAP_HEIGHT), QFontMetrics(font).horizontalAdvance(hotkey) + 10.0)
            cap = QRectF(right - width, rect.center().y() - self.KEYCAP_HEIGHT / 2, width, self.KEYCAP_HEIGHT)
            painter.setPen(QColor(255, 255, 255, 60))
            painter.setBrush(QColor(0, 0, 0, 60))
            painter.drawRoundedRect(cap.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            painter.setFont(font)
            painter.setPen(QColor(230, 230, 230, 200))
            painter.drawText(cap, Qt.AlignCenter, hotkey)
            right = cap.left() - 8

        foreground = index.data(Qt.ForegroundRole)
        color = foreground.color() if hasattr(foreground, "color") else QColor("#e6e6e6")
        width = max(0.0, right - x)
        half = rect.height() / 2
        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(color)
        name = QFontMetrics(name_font).elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, int(width))
        painter.drawText(QRectF(x, rect.top() + 2, width, half), Qt.AlignLeft | Qt.AlignBottom, name)
        file_font = QFont(option.font)
        file_font.setPointSizeF(max(7.0, option.font.pointSizeF() * 0.85))
        painter.setFont(file_font)
        painter.setPen(QColor("#7d7d7d"))
        file = QFontMetrics(file_font).elidedText(index.data(FILE_ROLE) or "", Qt.ElideMiddle, int(width))
        painter.drawText(QRectF(x, rect.top() + half, width, half - 2), Qt.AlignLeft | Qt.AlignTop, file)
        painter.restore()


def normalizedHeader(header: dict) -> dict:
    """Header settings compared for 'unsaved changes': case and empty values don't count"""
    return {key: str(value).strip().lower() for key, value in header.items() if str(value).strip()}


class ScriptManager(RoundedWindow, QWidget):
    """Browse library scripts and edit their header settings and code"""

    ROOT_ITEM = "(root)"

    def __init__(self, lib_folder, parent=None):
        """lib_folder: a lib folder or the list of them (HOTBOX_PATH order, the built-in lib last)"""
        super().__init__(parent or hou.qt.mainWindow())
        self.roots = script_lib.asRoots(lib_folder)
        setIconFolders(self.roots)
        self.scripts: list[script_lib.Script] = []
        self.listed: list[script_lib.Script] = []  # rows of the scripts list
        self._shown: script_lib.Script | None = None  # the script in the fields
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
        for index, tip in enumerate(MODE_TIPS):
            self.mode_combobox.setItemData(index, tip, Qt.ToolTipRole)
        self.mode_combobox.setToolTip("Mode: which hotbox the scripts are for (what is selected when it opens)")
        self.folders_list = QListWidget()
        self.folders_list.setToolTip("(root): shown everywhere in the mode; a folder: shown for that network / "
                                     "node type")
        self.files_list = QListWidget()
        self.files_list.setItemDelegate(ScriptItemDelegate(self.files_list))
        self.files_list.setMouseTracking(True)
        self.files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        for widget in (self.folders_list, self.files_list):
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            widget.setTextElideMode(Qt.ElideMiddle)
        self.search_lineedit = QLineEdit()
        self.search_lineedit.setPlaceholderText("Search by name or file")
        self.search_lineedit.setToolTip("Scripts of every folder of the mode whose name or file has the text")
        self.search_lineedit.setClearButtonEnabled(True)
        self.search_lineedit.addAction(QIcon((ICONS_DIR / "search.svg").as_posix()), QLineEdit.LeadingPosition)

        self.ref_field = ChoiceField(empty_text="No scripts")
        self.ref_lineedit = self.ref_field.lineedit
        self.ref_lineedit.setPlaceholderText("run another script: single/create_null.py")
        self.ref_field.setToolTip("#ref: the button runs another script and takes its settings (the fields here "
                                  "override them).\nTab completes, the arrow lists the scripts.")
        self.name_lineedit = QLineEdit()
        self.group_lineedit = QLineEdit()
        self.group_lineedit.setToolTip("#group: buttons of one group stand together in a frame with this caption")
        self.package_field = ChoiceField(multiple=True, empty_text="No packages yet")
        self.package_lineedit = self.package_field.lineedit
        self.package_field.setToolTip("#package: the button is shown only when the package is on (the gear in the "
                                      "title bar).\nTab completes, the arrow lists the packages.")
        self.button_color_swatch = hou.qt.ColorSwatchButton()
        self.button_color_swatch.setToolTip("#buttoncolor: the button background")
        self.text_color_swatch = hou.qt.ColorSwatchButton()
        self.text_color_swatch.setToolTip("#textcolor: the stripe and the line icon of the button (the text is "
                                          "neutral).\nIn a group the stripe has the color of the group's first "
                                          "button.")
        self.icon_lineedit = QLineEdit()
        self.icon_lineedit.setToolTip("A file in icons/ (line svg icons take the Accent color) or a Houdini icon "
                                      "name (SOP_null...).\nThe grid button browses them.")
        self.icon_browse_button = QPushButton()
        self.icon_browse_button.setObjectName("DropDown")
        self.icon_browse_button.setIcon(QIcon((ICONS_DIR / "grid.svg").as_posix()))
        self.icon_browse_button.setIconSize(QSize(13, 13))
        self.icon_browse_button.setFixedSize(QSize(28, 28))
        self.icon_browse_button.setCursor(Qt.PointingHandCursor)
        self.icon_browse_button.setToolTip("Browse Houdini and HotBox icons")
        icon_row = HLayout([self.icon_lineedit, self.icon_browse_button], align=None)
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(4)
        self.icon_field = QWidget()
        self.icon_field.setLayout(icon_row)
        self.hotkey_lineedit = HotkeyEdit()
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setReadOnly(True)
        self.ref_label = QLabel()
        self.ref_label.setObjectName("Hint")
        self.warning_label = QLabel()
        self.warning_label.setObjectName("Warning")
        self.warning_label.setWordWrap(True)

        self.preview = Button("Preview", style="row", size=ScriptButton.SIZE, fontSize=ScriptButton.FONT)
        self.preview.setToolTip("How the button looks in the hotbox")
        self.save_button = Button("Save", buttonColor=COLORS["accent"], textColor="#ffffff", size=ACTION_SIZE,
                                  fontSize=12)
        self.save_button.DISABLED_OPACITY = 1.0  # greyed by its colors instead
        self.save_button.setToolTip("Save the button and the code into the file (Ctrl+S)")
        self.open_button = Button("Open file", buttonColor="#4a4a4a", size=ACTION_SIZE, fontSize=12)
        self.code_button = Button("Code ›", buttonColor="#4a4a4a", size=(100, 36), fontSize=12)
        self.code_button.setToolTip("Edit the code here")
        self.new_button = Button("+ New script", buttonColor="#4a4a4a", size=(150, 32), fontSize=12)
        self.new_button.setToolTip("New script file in the library (Ctrl+N)")

        form = formGrid([
            ("Name", self.name_lineedit),
            ("Group", self.group_lineedit),
            ("Hotkey", self.hotkey_lineedit),
            ("Icon", self.icon_field),
            ("Accent", swatchRow(self.text_color_swatch)),
            ("Background", swatchRow(self.button_color_swatch)),
        ])
        # Rarely needed: folded away, opened by itself for a script that uses them
        self.advanced_button = QPushButton()
        self.advanced_button.setObjectName("Fold")
        self.advanced_button.setCursor(Qt.PointingHandCursor)
        self.advanced_button.setFont(buttonFont(10))
        self.advanced = QWidget()
        self.advanced.setLayout(formGrid([("Ref", self.ref_field), ("Package", self.package_field)]))
        self.setAdvancedOpen(False)

        preview_caption = QLabel("Preview")
        preview_caption.setFont(buttonFont(10))
        preview_caption.setStyleSheet("color:#8a8a8a;")
        preview_row = HLayout([self.preview], align=Qt.AlignLeft)
        indent = FIELD_INDENT
        preview_row.setContentsMargins(indent, 0, 0, 0)
        preview_caption.setContentsMargins(indent, 0, 0, 0)
        actions = HLayout([self.code_button, self.open_button, self.save_button], align=Qt.AlignRight)
        editor = panel(form, self.advanced_button, self.advanced, self.warning_label, preview_caption,
                       preview_row, actions, 1, title="Button")
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

        mode_label = QLabel("Mode")
        mode_label.setFont(buttonFont(10))
        mode_row = HLayout([mode_label, self.mode_combobox], align=None)
        mode_row.setStretch(1, 1)
        lists = HLayout([
            panel(mode_row, self.folders_list, title="Folders"),
            panel(self.search_lineedit, self.files_list, HLayout([self.new_button], align=Qt.AlignHCenter),
                  title="Scripts"),
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
        self.title_bar = TitleBar(self, "Script Manager", on_settings=self.openPackages)
        layout.addWidget(self.title_bar)
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
        self.icon_browse_button.clicked.connect(self.browseIcons)
        self.advanced_button.clicked.connect(lambda: self.setAdvancedOpen(not self.advanced.isVisibleTo(self)))
        self.search_lineedit.textChanged.connect(lambda _text: self.updateFilesList())
        self.files_list.customContextMenuRequested.connect(self.showScriptMenu)
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

    def searchText(self) -> str:
        return self.search_lineedit.text().strip()

    def listedScripts(self) -> list[script_lib.Script]:
        """The folder's scripts; while searching, the matching scripts of every folder of the mode"""
        query = self.searchText()
        if not query:
            return self.folderScripts()
        return [s for s in self.scripts
                if script_lib.matchesSearch(f"{s.label} {s.path.name} {s.context}", query)]

    def updateScripts(self):
        self.scripts = script_lib.scanLibrary(self.roots, self.mode_combobox.currentText())
        folders = sorted({s.context for s in self.scripts})
        self.folders_list.clear()
        self.folders_list.addItems([folder or self.ROOT_ITEM for folder in folders])
        if folders:
            self.folders_list.setCurrentRow(0)
        else:
            self.updateFilesList()

    def fileText(self, script: script_lib.Script, available: bool = True) -> str:
        """Second line of a list row: 'flipbook.py', 'mine.py  · mine' (lib folder), '…  — off' (package off);
        while searching with the folder: 'Sop/merge.py'"""
        name = script.relpath if self.searchText() and script.context else script.path.name
        return name + self.rootSuffix(script) + ("" if available else "  — off")

    def fileTexts(self) -> list[str]:
        return [self.files_list.item(i).data(FILE_ROLE) for i in range(self.files_list.count())]

    def updateFilesList(self):
        current = self.currentScript()
        row = self.files_list.currentRow()
        self.files_list.blockSignals(True)
        self.files_list.clear()
        self.listed = self.listedScripts()
        isEnabled = settings.enabledChecker()
        for script in self.listed:
            available = script.isAvailable(isEnabled)
            self.files_list.addItem(script.label)
            item = self.files_list.item(self.files_list.count() - 1)
            item.setData(FILE_ROLE, self.fileText(script, available))
            item.setData(HOTKEY_ROLE, keycapText(script.hotkey))
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
        self.files_list.blockSignals(False)
        if self.listed:
            keys = [s.key for s in self.listed]
            if current is not None and current.key in keys:
                row = keys.index(current.key)
            self.files_list.setCurrentRow(row if 0 <= row < len(self.listed) else 0)
            selected = self.currentScript()
            if self._shown is not None and selected.key == self._shown.key:
                self._shown = selected  # the same script rescanned (packages, search): the fields stay
                self.onEdited()
            else:
                self.updateInfo()
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
        return self.listed[row] if 0 <= row < len(self.listed) else None

    def scriptRefValue(self, script: script_lib.Script) -> str:
        """The script as a #ref value: 'single/create_null.py'"""
        return f"{self.mode_combobox.currentText()}/{script.relpath}"

    def showScriptMenu(self, pos):
        """Right click on a script: duplicate, delete, open"""
        item = self.files_list.itemAt(pos)
        if item is None:
            return
        self.files_list.setCurrentItem(item)
        script = self.currentScript()
        if script is None:
            return
        menu = QMenu(self)
        menu.addAction("Duplicate", self.duplicateScript)
        menu.addAction("Open file", self.openFile)
        menu.addSeparator()
        menu.addAction("Delete…", self.deleteScript)
        menu.exec_(self.files_list.viewport().mapToGlobal(pos)) if hasattr(menu, "exec_") else \
            menu.exec(self.files_list.viewport().mapToGlobal(pos))

    def duplicateScript(self) -> Path | None:
        """Copy next to the script ('name_copy.py'), named '<label> Copy', without the hotkey (it would conflict)"""
        script = self.currentScript()
        if script is None or not self.maybeSave():
            return None
        copy = script_lib.freeCopyPath(script.path)
        copy.write_bytes(script.path.read_bytes())
        header = dict(script.ownSettings)
        header["label"] = f"{script.label} Copy"
        header.pop("hotkey", None)
        script_lib.writeHeader(copy, header)
        self._shown = None
        self.updateChoices()
        self.selectScript(copy)
        return copy

    def deleteScript(self, confirm: bool = True) -> bool:
        """Delete the file after asking; the question names the scripts that #ref it (they break)"""
        script = self.currentScript()
        if script is None:
            return False
        users = script_lib.refUsers(self.roots, script.path)
        question = f"Delete '{script.label}' ({self.relativeToLib(script.path)})?"
        if users:
            question += "\n\nThese scripts run it with #ref and will be broken:\n" + "\n".join(users)
        if confirm:
            answer = QMessageBox.question(self, "Script Manager", question, QMessageBox.Yes | QMessageBox.No,
                                          QMessageBox.No)
            if answer != QMessageBox.Yes:
                return False
        script.path.unlink()
        if self._codePath is not None and Path(self._codePath) == script.path:
            self._codeDirty = False
        self._shown = None
        row = self.files_list.currentRow()
        self.scripts = script_lib.scanLibrary(self.roots, self.mode_combobox.currentText())
        self.updateChoices()
        self.files_list.setCurrentRow(max(0, row - 1))
        self.updateFilesList()
        return True

    # --- editor -------------------------------------------------------------------------------------------------

    def setAdvancedOpen(self, opened: bool):
        self.advanced.setVisible(opened)
        self.advanced_button.setText(("▾" if opened else "▸") + "  Advanced: Ref, Package")

    def inherited(self) -> tuple[dict, str | None]:
        """(settings inherited through the Ref field as it is now, reference error)"""
        script = self._shown
        ref = self.ref_lineedit.text().strip()
        if script is None or not ref:
            return {}, None
        _target, merged, error = script_lib.resolveRef(script.path, {"ref": ref}, self.roots)
        merged.pop("ref", None)
        return merged, error

    def updateInfo(self):
        """Fields show the script's own header; inherited values (from #ref) are placeholders"""
        if not self.maybeSave():
            return
        script = self.currentScript()
        self._shown = script
        own = script.ownSettings if script else {}
        self._loading = True
        for lineedit, key in ((self.ref_lineedit, "ref"), (self.name_lineedit, "label"),
                              (self.group_lineedit, "group"), (self.package_lineedit, "package"),
                              (self.icon_lineedit, "icon")):
            lineedit.setText(own.get(key, ""))
        self.hotkey_lineedit.setText(keycapText(own.get("hotkey", "")))
        if own.get("ref") or own.get("package"):
            self.setAdvancedOpen(True)
        self.ref_field.setChoices([r for r in script_lib.scriptRefs(self.roots)
                                   if script is None or r != self.scriptRefValue(script)])
        self.file_lineedit.setText(self.displayPath(script.path) if script else "")
        self.file_lineedit.setToolTip(script.path.as_posix() if script else "")
        if script:
            self.button_color_swatch.setColor(QColor(script.buttoncolor))
            self.text_color_swatch.setColor(QColor(script.textcolor))
        for widget in (self.open_button, self.code_button):
            widget.setEnabled(script is not None)
        self._lastRef = own.get("ref", "")
        self.loadCode()
        self._loading = False
        self.onEdited()

    def displayPath(self, path: Path) -> str:
        """'hotbox/lib/all/flipbook.py': the lib folder's parent and the path in it (the tooltip has the full one)"""
        for root in self.roots:
            root = Path(root).resolve()
            try:
                relative = Path(path).resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            return f"{root.parent.name}/{root.name}/{relative}"
        return Path(path).as_posix()

    def onEdited(self, *args):
        if self._loading:
            return
        script = self._shown
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
        self.group_lineedit.setPlaceholderText(inherited.get("group") or "e.g. Network")
        self.package_lineedit.setPlaceholderText(inherited.get("package") or "shown only when the package is on")
        self.icon_lineedit.setPlaceholderText(inherited.get("icon") or "dino.svg / SOP_null")
        self.hotkey_lineedit.setPlaceholderText(keycapText(inherited.get("hotkey")) or "click, then press a key")
        if ref:
            self.ref_label.setText(f"#ref → {ref}" + (f"  ({error})" if error else ""))
        else:
            self.ref_label.setText("")
        self.updateWarnings()
        self.updatePreview()
        self.updateDirty()

    def updatePreview(self):
        """Follows the fields as they are typed (no animation: it would blink on every key)"""
        script = self._shown
        if script is None:
            self.preview.setVisible(False)
            return
        self.preview.setVisible(True)
        inherited, _error = self.inherited()
        label = self.name_lineedit.text().strip() or inherited.get("label") or script.path.stem
        hotkey = self.hotkey_lineedit.text().strip() or inherited.get("hotkey", "")
        self.preview.setButtonIcon(self.icon_lineedit.text().strip() or inherited.get("icon"))
        self.preview.updateColors(self.button_color_swatch.color().name(), NEUTRAL_TEXT)
        self.preview.setAccent(self.text_color_swatch.color().name())
        self.preview.hotkey = hotkey.lower() if len(hotkey) == 1 else (hotkey or None)
        self.preview.updateText(label)

    def warnings(self) -> list[str]:
        script = self._shown
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
            labels = {s.relpath: s.label for s in shown}
            taken = ", ".join(f"{labels.get(relpath, relpath)} ({relpath})" for relpath in conflicts)
            messages.append(f"{keycapText(hotkey)} is taken: {taken}")
        icon = self.icon_lineedit.text().strip()
        if icon and resolveIcon(icon) is None:
            messages.append(f"No icon '{icon}': not in the icons/ folders and not a Houdini icon")
        return messages

    def updateWarnings(self):
        self.warning_label.setText("\n".join(self.warnings()))

    def editedSettings(self) -> dict:
        """The script's own header after editing. Values equal to the inherited/default ones that the
        header didn't set are not written: a #ref stub stays a stub."""
        script = self._shown
        if script is None:
            return {}
        own = dict(script.ownSettings)
        inherited, _error = self.inherited()
        hotkey = self.hotkey_lineedit.text().strip()
        edited = {
            "ref": self.ref_lineedit.text().strip(),
            "label": self.name_lineedit.text().strip(),
            "group": self.group_lineedit.text().strip(),
            "package": self.package_lineedit.text().strip(),
            "buttoncolor": self.button_color_swatch.color().name(),
            "textcolor": self.text_color_swatch.color().name(),
            "icon": self.icon_lineedit.text().strip(),
            "hotkey": hotkey.lower() if len(hotkey) == 1 else hotkey,  # the header keeps 'k', the field shows K
        }
        for key, value in edited.items():
            fallback = inherited.get(key) or script_lib.DEFAULTS.get(key, "")
            if key not in own and value.lower() == fallback.lower():
                continue
            own[key] = value
        return own

    def headerDirty(self) -> bool:
        script = self._shown
        return script is not None and normalizedHeader(self.editedSettings()) != normalizedHeader(script.ownSettings)

    def isDirty(self) -> bool:
        """Unsaved changes: the header fields or the code"""
        return self.headerDirty() or bool(self._codeDirty and self._codePath)

    def updateDirty(self):
        """A dot in the title and Save active only when there is something to save"""
        dirty = self.isDirty()
        self.save_button.setEnabled(dirty)
        self.save_button.updateColors(*((COLORS["accent"], "#ffffff") if dirty else ("#3a3a3a", "#7a7a7a")))
        self.title_bar.title.setText("Script Manager" + ("  ●" if dirty else ""))

    # --- code panel ---------------------------------------------------------------------------------------------

    def loadCode(self):
        """Code of the script, or of its ref target (that is the code that runs)"""
        script = self._shown
        path = (script.runPath or None) if script else None
        self._codePath = path
        self.code_edit.blockSignals(True)
        body = script_lib.readBody(path) if path else ""
        code = body.lstrip("\n")
        self._codeLead = body[:len(body) - len(code)]  # blank lines after the header: kept in the file
        self.code_edit.setPlainText(code)
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
        self.updateDirty()

    def maybeSave(self) -> bool:
        """Before showing another script or closing: save or drop the unsaved header / code of the shown one"""
        script = self._shown
        header = self.headerDirty()
        code = bool(self._codeDirty and self._codePath)
        if not (header or code):
            return True
        where = self.relativeToLib(script.path if header or self._codePath is None else self._codePath)
        answer = QMessageBox.question(self, "Script Manager", f"Save the changes in {where}?",
                                      QMessageBox.Save | QMessageBox.Discard, QMessageBox.Save)
        if answer == QMessageBox.Save:
            self.writeChanges(script, header=header)
        self._codeDirty = False
        self._shown = None  # its fields are not the file any more
        return True

    def writeChanges(self, script, header: bool = True):
        """The header fields (header=True) and the edited code into the files"""
        code = self.code_edit.toPlainText() if self._codeDirty and self._codePath else None
        if code is not None:
            code = getattr(self, "_codeLead", "") + code
        if code is not None and self._codePath == script.path:
            script_lib.writeHeader(script.path, self.editedSettings() if header else script.ownSettings, body=code)
        else:
            if header:
                script_lib.writeHeader(script.path, self.editedSettings())
            if code is not None:
                script_lib.writeBody(self._codePath, code)
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
        script = self._shown
        if script is None:
            return
        self.writeChanges(script)
        self._shown = None  # reloaded from the file
        self.scripts = script_lib.scanLibrary(self.roots, self.mode_combobox.currentText())
        self.updateChoices()
        self.updateFilesList()

    def newScript(self):
        """Window for a new script, in the current mode and folder; the new file is selected and its code shown"""
        self.maybeSave()
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

    def browseIcons(self):
        """Icon browser on the current icon; the chosen name goes into the Icon field"""
        inherited, _error = self.inherited()
        current = self.icon_lineedit.text().strip() or inherited.get("icon", "")
        self.icon_browser = IconBrowser(current=current, stylesheet=bodyStyle(), parent=self)
        self.icon_browser.chosen.connect(self.icon_lineedit.setText)
        center = self.mapToGlobal(self.rect().center())
        self.icon_browser.move(center.x() - self.icon_browser.width() // 2,
                               center.y() - self.icon_browser.height() // 2)
        self.icon_browser.show()
        return self.icon_browser

    def openPackages(self):
        """Gear: turn packages on/off; the list greys out scripts of turned off packages"""
        self.packages_window = PackagesWindow(self.roots, parent=self)
        self.packages_window.changed.connect(self.updateFilesList)
        top_right = self.mapToGlobal(self.rect().topRight())  # under the gear, inside the manager
        self.packages_window.move(top_right.x() - self.packages_window.width() - 20, top_right.y() + 50)
        self.packages_window.show()
        return self.packages_window

    def selectScript(self, path: Path):
        """Select the script file (searched in every mode, the search field cleared); the script or None"""
        path = Path(path).resolve()
        for mode_index, mode in enumerate(script_lib.MODES):
            scripts = script_lib.scanLibrary(self.roots, mode)
            match = next((s for s in scripts if s.path.resolve() == path), None)
            if match is None:
                continue
            self.search_lineedit.blockSignals(True)
            self.search_lineedit.clear()
            self.search_lineedit.blockSignals(False)
            self.mode_combobox.blockSignals(True)
            self.mode_combobox.setCurrentIndex(mode_index)
            self.mode_combobox.blockSignals(False)
            self.updateScripts()  # also when the mode was already selected: the file may be new
            folders = [self.folders_list.item(i).text() for i in range(self.folders_list.count())]
            self.folders_list.setCurrentRow(folders.index(match.context or self.ROOT_ITEM))
            self.files_list.setCurrentRow([s.relpath for s in self.listed].index(match.relpath))
            return match
        return None

    def showScript(self, path: Path, line: int | None = None) -> bool:
        """Select the script file and show its code at the line (1-based, in the file)"""
        match = self.selectScript(path)
        if match is None:
            return False
        if self._codeOpen < 0.5:
            self.toggleCode()
        if line:
            body_line = line - script_lib.headerLineCount(match.runPath or match.path)
            self.code_edit.showLine(body_line)
        return True

    def openFile(self):
        script = self.currentScript()
        if script is not None:  # the code: the ref target for a #ref
            path = script.runPath or script.path
            QDesktopServices.openUrl(QUrl.fromLocalFile(path.as_posix()))

    def closeEvent(self, event):
        self.maybeSave()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)
