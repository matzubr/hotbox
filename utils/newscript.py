"""Script Manager: the 'New script' window."""
from __future__ import annotations

from pathlib import Path

import hou

from . import scripts as script_lib
from .editors import ChoiceField
from .frameless import RoundedWindow, TitleBar
from .qt import QComboBox, QGridLayout, QLabel, QLineEdit, Qt, QVBoxLayout, QWidget, Signal
from .theme import COLORS, PANEL_RADIUS
from .widgets import Button, HLayout, buttonFont


def selectedNodeType() -> str | None:
    """Type of the selected node in Houdini (the single/<type> folder for it), None without a selection"""
    try:
        nodes = hou.selectedNodes()
        name = nodes[0].type().nameComponents()[2] if nodes else None
    except Exception:  # noqa: BLE001  outside Houdini / no UI
        return None
    return name if isinstance(name, str) and name else None


def rootName(root: Path) -> str:
    root = Path(root)
    return root.parent.name if root.name.lower() == "lib" else root.name


class NewScriptWindow(RoundedWindow, QWidget):
    """Name, mode, folder (and lib folder with HOTBOX_PATH) of a new script; created(path) when it is written"""

    created = Signal(object)

    def __init__(self, lib_roots, mode: str = "all", folder: str = "", stylesheet: str = "", parent=None):
        super().__init__(parent)
        self.roots = script_lib.asRoots(lib_roots)
        self._fileEdited = False
        self.setWindowTitle("New script")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()

        self.label_lineedit = QLineEdit()
        self.label_lineedit.setPlaceholderText("Button text: Bake Camera")
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setPlaceholderText("bake_camera.py")
        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(list(script_lib.MODES))
        self.mode_combobox.setCurrentText(mode)
        self.folder_field = ChoiceField(empty_text="No folders yet")
        self.folder_lineedit = self.folder_field.lineedit
        self.folder_lineedit.setText(folder)
        self.root_combobox = QComboBox()
        for root in self.roots:
            self.root_combobox.addItem(self.rootLabel(root), root)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("Hint")
        self.hint_label.setWordWrap(True)
        self.warning_label = QLabel()
        self.warning_label.setObjectName("Warning")
        self.warning_label.setWordWrap(True)
        self.create_button = Button("Create", buttonColor=COLORS["accent"], textColor="#ffffff", size=(120, 36),
                                    fontSize=12)
        self.cancel_button = Button("Cancel", buttonColor="#4a4a4a", size=(100, 36), fontSize=12)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        rows = [("Name", self.label_lineedit), ("File", self.file_lineedit), ("Mode", self.mode_combobox),
                ("Folder", self.folder_field)]
        if len(self.roots) > 1:
            rows.append(("Save in", self.root_combobox))
        for row, (text, widget) in enumerate(rows):
            label = QLabel(text)
            label.setFont(buttonFont(10))
            form.addWidget(label, row, 0)
            form.addWidget(widget, row, 1)

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(stylesheet + f"QWidget#Panel {{ background-color:{COLORS['grey']};"
                                        f" border-radius:{PANEL_RADIUS}px; }}")
        rows_layout = QVBoxLayout(body)
        rows_layout.setContentsMargins(14, 12, 14, 12)
        rows_layout.setSpacing(8)
        rows_layout.addLayout(form)
        rows_layout.addWidget(self.hint_label)
        rows_layout.addWidget(self.warning_label)
        rows_layout.addLayout(HLayout([self.cancel_button, self.create_button], align=Qt.AlignRight))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "New script"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.setMinimumWidth(460)

        self.label_lineedit.textEdited.connect(self._labelEdited)
        self.file_lineedit.textEdited.connect(self._fileEditedByHand)
        self.mode_combobox.currentIndexChanged.connect(self.updateFolders)
        self.folder_lineedit.textChanged.connect(self.validate)
        self.root_combobox.currentIndexChanged.connect(self.validate)
        self.create_button.clicked.connect(self.create)
        self.cancel_button.clicked.connect(self.close)
        self.updateFolders()
        self.addAnimationOverlay()
        self.adjustSize()
        self.fadeIn()
        self.label_lineedit.setFocus()

    # --- fields -------------------------------------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self.mode_combobox.currentText()

    @property
    def root(self) -> Path:
        return self.root_combobox.currentData() or self.roots[0]

    def rootLabel(self, root: Path) -> str:
        return "built-in lib" if Path(root) == self.roots[-1] else rootName(root)

    def _labelEdited(self, text: str):
        if not self._fileEdited:  # the file name follows the label until it is typed by hand
            self.file_lineedit.setText(script_lib.scriptFileName(text))
        self.validate()

    def _fileEditedByHand(self, text: str):
        self._fileEdited = bool(text.strip())
        self.validate()

    def folderChoices(self) -> list[str]:
        """Existing folders of the mode, the selected node type (single) or the network types (all/multiple)"""
        existing = {s.context for s in script_lib.scanLibrary(self.roots, self.mode) if s.context}
        if self.mode == "single":
            suggested = [t for t in [selectedNodeType()] if t]
        else:
            suggested = list(script_lib.NETWORK_FOLDERS)
        return list(dict.fromkeys(suggested + sorted(existing, key=str.casefold)))

    def updateFolders(self):
        self.folder_field.setChoices(self.folderChoices())
        hints = {
            "all": "Nothing selected. Folder: network type (Sop, Lop, Object...), empty: every network.",
            "multiple": "Several nodes selected. Folder: their network type, empty: every network.",
            "single": "One node selected. Folder: its node type (cam, null, alembic...), empty: any node.",
        }
        self.hint_label.setText(hints[self.mode])
        self.validate()

    def target(self) -> tuple[Path | None, str | None]:
        return script_lib.newScriptPath(self.root, self.mode, self.folder_lineedit.text(), self.file_lineedit.text())

    def validate(self) -> bool:
        path, error = self.target()
        messages = [error] if error and (self.label_lineedit.text() or self.file_lineedit.text()) else []
        if path is not None:
            key = path.relative_to(self.root).as_posix()
            hidden_by, hides = script_lib.overrides(self.roots, self.root, key)
            messages += [f"Hidden by the same script in {self.rootLabel(r)}" for r in hidden_by]
            messages += [f"Replaces {key} of the {self.rootLabel(r)}" for r in hides]
        self.warning_label.setText("\n".join(messages))
        self.create_button.setEnabled(path is not None)
        return path is not None

    # --- actions ------------------------------------------------------------------------------------------------

    def create(self) -> Path | None:
        if not self.validate():
            return None
        label = self.label_lineedit.text().strip()
        try:
            path = script_lib.createScript(self.root, self.mode, self.folder_lineedit.text(),
                                           self.file_lineedit.text(), label)
        except (OSError, ValueError) as e:
            self.warning_label.setText(str(e))
            return None
        self.created.emit(path)
        self.close()
        return path

    def keyPressEvent(self, event):
        key = int(event.key())
        if key == int(Qt.Key_Escape):
            self.close()
            return
        if key in (int(Qt.Key_Return), int(Qt.Key_Enter)):
            self.create()
            return
        super().keyPressEvent(event)
