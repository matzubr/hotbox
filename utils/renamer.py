"""Multi Rename window: the rule fields, a live preview (old -> new, problems in red), Rename."""
from __future__ import annotations

from dataclasses import asdict

import hou

from ..common import rename
from .frameless import RoundedWindow, TitleBar
from .qt import (
    QAbstractItemView,
    QBrush,
    QCheckBox,
    QColor,
    QComboBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .theme import COLORS
from .widgets import Button, HLayout, buttonFont

LAST = rename.Rule()  # the fields of the last rename, for the next one in this session
PROBLEM_COLOR, CHANGED_COLOR, SAME_COLOR = "#ff8f8f", "#8fffc1", "#8a8a8a"


class RenameWindow(RoundedWindow, QWidget):
    def __init__(self, nodes, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        from .manager import bodyStyle

        self.nodes = list(nodes)
        self.changes: list[rename.Change] = []
        self.setWindowTitle("Multi Rename")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()

        def line(text, placeholder):
            edit = QLineEdit(text)
            edit.setPlaceholderText(placeholder)
            edit.textChanged.connect(self.preview)
            edit.returnPressed.connect(self.rename)
            return edit

        def spin(value):
            box = QSpinBox()
            box.setRange(-100000, 100000)
            box.setValue(value)
            box.valueChanged.connect(self.preview)
            return box

        def combo(items, current):
            box = QComboBox()
            box.addItems(list(items))
            box.setCurrentText(current)
            box.currentIndexChanged.connect(self.preview)
            return box

        last = LAST
        self.pattern = line(last.pattern, "{name}   ·   # number, ### = 001   ·   {type}")
        self.find = line(last.find, "text to replace")
        self.replace = line(last.replace, "replace with")
        self.regex = QCheckBox("Regex")
        self.regex.setChecked(last.regex)
        self.regex.toggled.connect(self.preview)
        self.prefix = line(last.prefix, "prefix")
        self.suffix = line(last.suffix, "suffix")
        self.start, self.step = spin(last.start), spin(last.step)
        self.case = combo(rename.CASES, last.case)
        self.order = combo(rename.ORDERS, last.order)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        rows = [("Name", [self.pattern]), ("Find", [self.find, self.regex]), ("Replace", [self.replace]),
                ("Prefix, suffix", [self.prefix, self.suffix]), ("Numbers", [QLabel("start"), self.start, QLabel("step"),
                                                                    self.step, QLabel("order"), self.order]),
                ("Case", [self.case])]
        for row, (text, widgets) in enumerate(rows):
            label = QLabel(text)
            label.setFont(buttonFont(10))
            form.addWidget(label, row, 0)
            form.addLayout(HLayout(widgets, align=None), row, 1)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(("Now", "New name"))
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.status = QLabel()
        self.status.setObjectName("Hint")
        self.rename_button = Button("Rename", buttonColor=COLORS["accent"], textColor="#ffffff", size=(120, 36),
                                    fontSize=12)
        cancel = Button("Cancel", buttonColor="#4a4a4a", size=(100, 36), fontSize=12)
        self.rename_button.clicked.connect(self.rename)
        cancel.clicked.connect(self.close)

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(bodyStyle() + (
            f"QTableWidget {{ background-color:{COLORS['grey-dark']}; color:#ddd; border:1px solid {COLORS['border']};"
            " gridline-color:#262626; }"
            f"QHeaderView::section {{ background-color:{COLORS['grey']}; color:#9a9a9a; border:none;"
            f" border-bottom:1px solid {COLORS['border']}; padding:2px 6px; }}"
            f"QSpinBox {{ background-color:{COLORS['grey-dark']}; color:#eee; border:1px solid {COLORS['border']};"
            " border-radius:4px; padding:3px 4px; }"
            f"QCheckBox {{ color:{COLORS['white']}; background:transparent; }}"
            f"QCheckBox::indicator {{ width:12px; height:12px; border:1px solid #6e6e6e; border-radius:3px;"
            f" background:{COLORS['grey-dark']}; }}"
            f"QCheckBox::indicator:checked {{ background:{COLORS['accent']}; border:1px solid {COLORS['accent']}; }}"))
        column = QVBoxLayout(body)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(8)
        column.addLayout(form)
        column.addWidget(self.table, 1)
        column.addWidget(self.status)
        column.addLayout(HLayout([cancel, self.rename_button], align=Qt.AlignRight))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Multi Rename"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.addAnimationOverlay()
        self.resize(620, 560)
        self.preview()
        self.fadeIn()
        self.pattern.setFocus()

    def rule(self) -> rename.Rule:
        return rename.Rule(pattern=self.pattern.text(), find=self.find.text(), replace=self.replace.text(),
                           regex=self.regex.isChecked(), prefix=self.prefix.text(), suffix=self.suffix.text(),
                           start=self.start.value(), step=self.step.value(), case=self.case.currentText(),
                           order=self.order.currentText())

    def preview(self, *_args):
        try:
            self.changes = rename.plan(self.nodes, self.rule())
        except ValueError as e:
            self.changes = []
            self.status.setText(str(e))
            self.rename_button.setEnabled(False)
            return
        self.table.setRowCount(len(self.changes))
        for row, change in enumerate(self.changes):
            old, new = QTableWidgetItem(change.old), QTableWidgetItem(change.new or "(empty)")
            color = PROBLEM_COLOR if change.problem else SAME_COLOR if change.new == change.old else CHANGED_COLOR
            new.setForeground(QBrush(QColor(color)))
            tip = f"{change.node.path()}" + (f"\n{change.problem}" if change.problem else "")
            old.setToolTip(tip)
            new.setToolTip(tip)
            self.table.setItem(row, 0, old)
            self.table.setItem(row, 1, new)
        problems = [c for c in self.changes if c.problem]
        changed = sum(c.new != c.old for c in self.changes)
        if problems:
            self.status.setText(f"{len(problems)} name(s) in red: {problems[0].problem}")
        else:
            self.status.setText(f"{changed} of {len(self.changes)} node(s) get a new name")
        self.rename_button.setEnabled(not problems and changed > 0)

    def rename(self):
        if not self.rename_button.isEnabled():
            return
        count = rename.apply(self.changes)
        global LAST
        LAST = rename.Rule(**asdict(self.rule()))
        hou.ui.setStatusMessage(f"Multi Rename: {count} node(s) renamed")
        self.close()

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)


_windows: list = []


def showRename(nodes) -> RenameWindow | None:
    if not nodes:
        hou.ui.setStatusMessage("Multi Rename: select nodes first", severity=hou.severityType.Warning)
        return None
    window = RenameWindow(nodes)
    _windows.append(window)
    window.destroyed.connect(lambda *_: _windows.remove(window) if window in _windows else None)
    window.show()
    return window
