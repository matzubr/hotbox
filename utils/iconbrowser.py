"""Icon browser for the Script Manager: Houdini's own icons (by the names #icon takes) and the files in icons/.

Houdini keeps its icons in $HFS/houdini/config/Icons/icons.zip as 'SOP/null.svg', 'OBJ/camera.svg'...;
hou.qt.Icon() takes them as 'SOP_null', 'OBJ_camera'. Only the names are read from the archive, the icons
themselves are made when they scroll into view.
"""
from __future__ import annotations

import os
import shutil
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

import hou

from .frameless import RoundedWindow, TitleBar
from .qt import (
    QAbstractListModel,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QMessageBox,
    QModelIndex,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import ICON_SUFFIXES, Button, HLayout, buttonFont, iconFolders, resolveIcon

ICONS_ZIP = "config/Icons/icons.zip"
HOTBOX_CATEGORY = "HotBox"
ALL_CATEGORY = "All"
FILE_SUFFIXES = ICON_SUFFIXES
FILE_FILTER = "Icons (*.svg *.png *.jpg *.jpeg)"
# The useful ones first in the list, the rest alphabetically
CATEGORY_ORDER = ("SOP", "OBJ", "LOP", "DOP", "COP", "VOP", "TOP", "ROP", "CHOP", "MISC", "BUTTONS", "NETWORKS")


def houdiniIconsZip() -> Path | None:
    """icons.zip of the running Houdini: $HFS, else searched in HOUDINI_PATH"""
    candidates = []
    hfs = os.environ.get("HFS") or hou.getenv("HFS")
    if hfs:
        candidates.append(Path(hfs) / "houdini" / ICONS_ZIP)
    try:
        found = hou.findFile(ICONS_ZIP)
    except Exception:  # noqa: BLE001  hou.OperationFailed when not found
        found = None
    if isinstance(found, str):
        candidates.append(Path(found))
    return next((path for path in candidates if path.is_file()), None)


@lru_cache(maxsize=4)
def houdiniIconNames(zip_path: Path | None) -> dict[str, list[str]]:
    """{category: ['SOP_null', ...]} from the archive ('SOP/null.svg' -> 'SOP_null'); {} without it"""
    if zip_path is None:
        return {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            files = archive.namelist()
    except (OSError, zipfile.BadZipFile) as e:
        print(f"HotBox: can't read {Path(zip_path).as_posix()}: {e}")
        return {}
    categories: dict[str, set[str]] = {}
    for file in files:
        path = PurePosixPath(file)
        if len(path.parts) != 2 or path.suffix.lower() not in FILE_SUFFIXES:
            continue
        category = path.parts[0]
        categories.setdefault(category, set()).add(f"{category}_{path.stem}")
    return {name: sorted(icons, key=str.casefold) for name, icons in categories.items()}


def hotboxIconNames() -> list[str]:
    """Icon files of HotBox: icons/ of the HOTBOX_PATH lib folders and the built-in hotbox/icons ('save.svg')"""
    names = set()
    for folder in iconFolders():
        if folder.is_dir():
            names.update(f.name for f in folder.iterdir() if f.is_file() and f.suffix.lower() in FILE_SUFFIXES)
    return sorted(names, key=str.casefold)


def userIconFolder() -> Path:
    """Where added icons go: icons/ of your first HOTBOX_PATH lib folder, else the built-in hotbox/icons"""
    return iconFolders()[0]


def addIconFiles(files, folder: Path, replace=lambda name: True) -> list[str]:
    """Copy icon files into the folder; replace(name) decides about an existing file with other content.
    Returns the names as #icon takes them ('my_tool.svg')."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    added = []
    for file in map(Path, files):
        if not file.is_file() or file.suffix.lower() not in FILE_SUFFIXES:
            continue
        target = folder / file.name
        if target.resolve() == file.resolve():
            added.append(file.name)  # already there
            continue
        if target.exists() and target.read_bytes() != file.read_bytes() and not replace(file.name):
            continue
        shutil.copyfile(file, target)
        added.append(file.name)
    return added


def orderedCategories(categories) -> list[str]:
    known = [c for c in CATEGORY_ORDER if c in categories]
    return known + sorted((c for c in categories if c not in CATEGORY_ORDER), key=str.casefold)


class IconModel(QAbstractListModel):
    """Icon names; the QIcon of a row is made the first time the view paints it"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.names: list[str] = []
        self._icons: dict[str, object] = {}

    def setNames(self, names: list[str]):
        self.beginResetModel()
        self.names = list(names)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: B008  Qt's signature
        return 0 if parent.isValid() else len(self.names)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        name = self.names[index.row()]
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return name
        if role == Qt.DecorationRole:
            if name not in self._icons:
                self._icons[name] = resolveIcon(name)
            return self._icons[name]
        return None


class IconBrowser(RoundedWindow, QWidget):
    """Pick an icon: categories on the left, search, a grid of icons; double click or Choose sends chosen(name)"""

    chosen = Signal(str)
    ICON_SIZE = 32
    CELL = QSize(118, 74)

    def __init__(self, current: str = "", stylesheet: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icons")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()

        self.houdini = houdiniIconNames(houdiniIconsZip())
        self.hotbox = hotboxIconNames()
        self.categories = [ALL_CATEGORY, HOTBOX_CATEGORY] + orderedCategories(self.houdini)

        self.search_lineedit = QLineEdit()
        self.search_lineedit.setPlaceholderText("Search: camera, null, merge...")
        self.search_lineedit.setClearButtonEnabled(True)
        self.categories_list = QListWidget()
        self.categories_list.addItems(self.categories)
        self.categories_list.setFixedWidth(130)
        self.model = IconModel(self)
        self.icons_view = QListView()
        self.icons_view.setModel(self.model)
        self.icons_view.setViewMode(QListView.IconMode)
        self.icons_view.setResizeMode(QListView.Adjust)
        self.icons_view.setMovement(QListView.Static)
        self.icons_view.setUniformItemSizes(True)  # the view only asks for the visible icons
        self.icons_view.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.icons_view.setGridSize(self.CELL)
        self.icons_view.setWordWrap(True)
        self.icons_view.setTextElideMode(Qt.ElideMiddle)
        self.icons_view.setSpacing(2)
        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")
        self.selected_label = QLabel()
        self.selected_label.setFont(buttonFont(11))
        self.add_button = Button("+ Add icons…", buttonColor="#4a4a4a", size=(140, 36), fontSize=12)
        self.add_button.setToolTip(f"Copy .svg / .png / .jpg files into {userIconFolder().as_posix()}")
        self.choose_button = Button("Choose", buttonColor=COLORS["accent"], textColor="#ffffff", size=(110, 36),
                                    fontSize=12)
        self.cancel_button = Button("Cancel", buttonColor="#4a4a4a", size=(100, 36), fontSize=12)

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(
            stylesheet
            + f"QWidget#Panel {{ background-color:{COLORS['grey']}; border-radius:{PANEL_RADIUS}px; }}"
            + f"QListView {{ background-color:{COLORS['grey-dark']}; color:#cfcfcf; border:1px solid {COLORS['border']};"
            " border-radius:6px; padding:4px; outline:none; }"
            "QListView::item { border-radius:6px; padding:2px; }"
            "QListView::item:hover { background-color: rgba(183, 134, 32, 20%); }"
            "QListView::item:selected { background-color: rgba(183, 134, 32, 55%); color:#ffffff; }"
        )
        rows = QVBoxLayout(body)
        rows.setContentsMargins(14, 12, 14, 12)
        rows.setSpacing(8)
        rows.addWidget(self.search_lineedit)
        lists = HLayout([self.categories_list, self.icons_view], align=None)
        lists.setStretch(1, 1)
        rows.addLayout(lists, 1)
        footer = HLayout([self.add_button, self.selected_label, self.count_label], align=None)
        footer.addStretch(1)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.choose_button)
        rows.addLayout(footer)
        if not self.houdini:
            hint = QLabel("Houdini icons not found ($HFS/houdini/config/Icons/icons.zip): only HotBox icons")
            hint.setObjectName("Warning")
            rows.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Icons"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.addAnimationOverlay()
        self.resize(820, 560)

        self.search_lineedit.textChanged.connect(self.updateIcons)
        self.categories_list.currentRowChanged.connect(self.updateIcons)
        self.icons_view.doubleClicked.connect(lambda index: self.choose())
        self.icons_view.clicked.connect(lambda index: self.updateSelected())
        self.choose_button.clicked.connect(self.choose)
        self.add_button.clicked.connect(lambda checked=False: self.addIcons())  # not clicked(checked) as files
        self.cancel_button.clicked.connect(self.close)
        self.select(current)
        self.fadeIn()
        self.search_lineedit.setFocus()

    # --- lists --------------------------------------------------------------------------------------------------

    def namesOf(self, category: str) -> list[str]:
        if category == HOTBOX_CATEGORY:
            return self.hotbox
        if category == ALL_CATEGORY:
            return self.hotbox + [name for c in orderedCategories(self.houdini) for name in self.houdini[c]]
        return self.houdini.get(category, [])

    def updateIcons(self, *args):
        item = self.categories_list.currentItem()
        category = item.text() if item else ALL_CATEGORY
        words = self.search_lineedit.text().casefold().split()
        names = [n for n in self.namesOf(category) if all(word in n.casefold() for word in words)]
        self.model.setNames(names)
        self.count_label.setText(f"{len(names)} icons")
        if names:
            self.icons_view.setCurrentIndex(self.model.index(0))
        self.updateSelected()

    def currentName(self) -> str | None:
        index = self.icons_view.currentIndex()
        return self.model.names[index.row()] if index.isValid() and index.row() < len(self.model.names) else None

    def updateSelected(self):
        name = self.currentName()
        self.selected_label.setText(name or "")
        self.choose_button.setEnabled(name is not None)

    def select(self, name: str):
        """Open on the category of the current icon with it selected"""
        name = (name or "").strip()
        category = ALL_CATEGORY
        if name in self.hotbox:
            category = HOTBOX_CATEGORY
        elif "_" in name and name.split("_", 1)[0] in self.houdini:
            category = name.split("_", 1)[0]
        self.categories_list.setCurrentRow(self.categories.index(category))
        self.updateIcons()
        if name in self.model.names:
            index = self.model.index(self.model.names.index(name))
            self.icons_view.setCurrentIndex(index)
            self.icons_view.scrollTo(index, QListView.PositionAtCenter)
            self.updateSelected()

    # --- actions ------------------------------------------------------------------------------------------------

    def pickFiles(self) -> list[str]:
        files, _filter = QFileDialog.getOpenFileNames(self, "Add icons", "", FILE_FILTER)
        return files

    def confirmReplace(self, name: str) -> bool:
        answer = QMessageBox.question(self, "Icons", f"{name} already exists with another picture. Replace it?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def addIcons(self, files=None) -> list[str]:
        """Copy the picked files into your icon folder; they show in HotBox, the last one selected"""
        files = self.pickFiles() if files is None else files
        if not files:
            return []
        try:
            added = addIconFiles(files, userIconFolder(), replace=self.confirmReplace)
        except OSError as e:
            QMessageBox.warning(self, "Icons", f"Can't copy the icons:\n{e}")
            return []
        self.model._icons.clear()  # a replaced file has a new picture
        self.hotbox = hotboxIconNames()
        if added:
            self.search_lineedit.clear()
            self.select(added[-1])
        else:
            self.updateIcons()
        return added

    def choose(self) -> str | None:
        name = self.currentName()
        if name is None:
            return None
        self.chosen.emit(name)
        self.close()
        return name

    def keyPressEvent(self, event):
        key = int(event.key())
        if key == int(Qt.Key_Escape):
            self.close()
            return
        if key in (int(Qt.Key_Return), int(Qt.Key_Enter)):
            self.choose()
            return
        super().keyPressEvent(event)
