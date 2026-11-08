"""Script Manager inputs: a line edit with completion and a menu of choices, a Python code editor."""
from __future__ import annotations

import keyword
import re
from typing import ClassVar

from .qt import (
    QColor,
    QCompleter,
    QEvent,
    QFont,
    QFontDatabase,
    QHBoxLayout,
    QIcon,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSize,
    QStringListModel,
    QSyntaxHighlighter,
    Qt,
    QTextCharFormat,
    QWidget,
)
from .theme import COLORS
from .widgets import ICONS_DIR


class CompletingLineEdit(QLineEdit):
    """Completion inline while typing (like DinoWrite); Tab accepts it instead of moving the focus.

    With multiple=True the value is a comma separated list and only the last item is completed.
    """

    def __init__(self, multiple: bool = False, parent=None):
        super().__init__(parent)
        self.multiple = multiple
        self.choices: list[str] = []
        self._model = QStringListModel()
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.InlineCompletion)
        self._completer.setWidget(self)
        self.textEdited.connect(self._complete)

    def setChoices(self, choices: list[str]):
        self.choices = list(choices)
        self._model.setStringList(self.choices)

    def _prefix(self) -> tuple[str, str]:
        """(text before the completed item, the item being typed)"""
        text = self.text()
        if not self.multiple or "," not in text:
            return "", text
        head, _, last = text.rpartition(",")
        return head + ", ", last.strip()

    def _complete(self, _text: str):
        head, item = self._prefix()
        if not item:
            return
        self._completer.setCompletionPrefix(item)
        completion = self._completer.currentCompletion()
        if completion and completion.casefold().startswith(item.casefold()) and completion != item:
            self.setText(head + item + completion[len(item):])
            self.setSelection(len(head) + len(item), len(completion) - len(item))  # the completed tail

    def acceptCompletion(self) -> bool:
        if not self.hasSelectedText():
            return False
        self.deselect()
        self.end(False)
        return True

    def event(self, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Tab and self.acceptCompletion():
            return True
        return super().event(event)

    def addChoice(self, choice: str):
        """From the menu: replace the value, or add to the list with multiple=True"""
        if self.multiple:
            items = [item.strip() for item in self.text().split(",") if item.strip()]
            if choice.casefold() not in (item.casefold() for item in items):
                items.append(choice)
            self.setText(", ".join(items))
        else:
            self.setText(choice)
        self.textEdited.emit(self.text())


class ChoiceField(QWidget):
    """CompletingLineEdit + arrow button with a menu of the existing values"""

    def __init__(self, multiple: bool = False, empty_text: str = "Nothing yet", parent=None):
        super().__init__(parent)
        self.lineedit = CompletingLineEdit(multiple=multiple)
        self.empty_text = empty_text
        self.button = QPushButton()
        self.button.setIcon(QIcon((ICONS_DIR / "angle-down.svg").as_posix()))
        self.button.setIconSize(QSize(12, 12))
        self.button.setObjectName("DropDown")
        self.button.setFixedSize(QSize(28, 28))
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setToolTip("Existing values")
        self.button.clicked.connect(self.showMenu)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.lineedit)
        layout.addWidget(self.button)

    def setChoices(self, choices: list[str]):
        self.lineedit.setChoices(choices)

    def buildMenu(self) -> QMenu:
        menu = QMenu(self)
        groups: dict[str, list[str]] = {}
        for choice in self.lineedit.choices:
            # 'single/cam/bake.py' -> submenu 'single'; plain names stay flat
            group = choice.partition("/")[0] if "/" in choice else ""
            groups.setdefault(group, []).append(choice)
        for group, choices in groups.items():
            target = menu.addMenu(group) if group else menu
            for choice in choices:
                label = choice[len(group) + 1:] if group else choice
                target.addAction(label, lambda c=choice: self.lineedit.addChoice(c))
        if not self.lineedit.choices:
            menu.addAction(self.empty_text).setEnabled(False)
        return menu

    def showMenu(self):
        self.menu = self.buildMenu()
        self.menu.popup(self.button.mapToGlobal(self.button.rect().bottomLeft()))


BUILTINS = ("print", "len", "range", "enumerate", "zip", "str", "int", "float", "list", "dict", "set", "tuple",
            "sorted", "min", "max", "sum", "any", "all", "isinstance", "open", "hou")


class PythonHighlighter(QSyntaxHighlighter):
    """Keywords, builtins, strings, comments, numbers, decorators"""

    COLORS: ClassVar[dict[str, str]] = {
        "keyword": "#ff8b48",
        "builtin": "#a0ceff",
        "string": "#9ddb6a",
        "comment": "#7a7a7a",
        "number": "#f1d018",
        "decorator": "#d453ff",
        "self": "#ffb492",
    }

    def __init__(self, document):
        super().__init__(document)
        builtins_ = r"\b(?:" + "|".join(BUILTINS) + r")\b"
        self.rules = [
            (re.compile(r"\b(?:" + "|".join(keyword.kwlist) + r")\b"), self._format("keyword", bold=True)),
            (re.compile(builtins_), self._format("builtin")),
            (re.compile(r"\bself\b"), self._format("self")),
            (re.compile(r"\b\d+(?:\.\d+)?\b"), self._format("number")),
            (re.compile(r"^\s*@\w+"), self._format("decorator")),
            (re.compile(r"[rbfu]*(\"\"\"|'''|\"|')(?:\\.|(?!\1).)*\1", re.IGNORECASE), self._format("string")),
            (re.compile(r"#[^\n]*"), self._format("comment", italic=True)),
        ]

    def _format(self, name: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(self.COLORS[name]))
        if bold:
            text_format.setFontWeight(QFont.Bold)
        text_format.setFontItalic(italic)
        return text_format

    def highlightBlock(self, text: str):
        for pattern, text_format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), text_format)


class CodeEditor(QPlainTextEdit):
    """Monospace editor: Tab inserts 4 spaces, Enter keeps the indentation"""

    INDENT = "    "

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setStyleSheet(f"QPlainTextEdit {{ background-color:{COLORS['grey-dark']}; color:#e8e8e8;"
                           f" border:1px solid {COLORS['border']}; border-radius:6px; padding:4px; }}"
                           f"QPlainTextEdit:focus {{ border:1px solid {COLORS['accent']}; }}")
        self.highlighter = PythonHighlighter(self.document())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and not event.modifiers():
            self.insertPlainText(self.INDENT)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            line = self.textCursor().block().text()
            indent = line[: len(line) - len(line.lstrip())]
            if line.rstrip().endswith(":"):
                indent += self.INDENT
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(event)
