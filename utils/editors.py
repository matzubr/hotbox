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
    QKeySequence,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSize,
    QStringListModel,
    QSyntaxHighlighter,
    Qt,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
    QTextFormat,
    QWidget,
)
from .theme import COLORS
from .widgets import ICONS_DIR, keycapText


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


# Keys a hotbox hotkey can't be: the hotbox itself uses them
_NOT_HOTKEYS = {int(Qt.Key_Return), int(Qt.Key_Enter), int(Qt.Key_Space), int(Qt.Key_QuoteLeft),
                int(Qt.Key_Tab), int(Qt.Key_Backtab)}
_MODIFIER_KEYS = {int(Qt.Key_Shift), int(Qt.Key_Control), int(Qt.Key_Alt), int(Qt.Key_Meta), int(Qt.Key_AltGr)}


def hotkeyFromEvent(event) -> str | None:
    """The hotkey a key press means: 'K', '1', 'F5'; the Latin key for the Russian layout; None for other keys"""
    from . import scripts as script_lib

    key = int(event.key())
    if key in _NOT_HOTKEYS or key in _MODIFIER_KEYS:
        return None
    latin = script_lib.latinKey(event.text())
    if latin:
        return keycapText(latin)
    text = QKeySequence(key).toString()
    if len(text) == 1 and text.isalnum():
        return text.upper()
    if re.fullmatch(r"F\d{1,2}", text):
        return text
    return None


class HotkeyEdit(QLineEdit):
    """Click and press the key: the key is the value, shown as its keycap (K, 1, F5). Backspace / Delete clear it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("click, then press a key")
        self.setToolTip("Click here and press the key: a letter, a digit or F1..F12. Backspace clears it.\n"
                        "It works in the Russian keyboard layout too (the same physical key).")
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def keyPressEvent(self, event):
        key = int(event.key())
        if key in (int(Qt.Key_Backspace), int(Qt.Key_Delete)):
            self.setText("")
        elif key == int(Qt.Key_Escape):
            self.clearFocus()  # not the window's Esc (close)
        else:
            hotkey = hotkeyFromEvent(event)
            if hotkey:
                self.setText(hotkey)
        event.accept()


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

    def showLine(self, line: int) -> None:
        """Cursor on the line (1-based) and the line highlighted, e.g. where a script failed"""
        block = self.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(236, 60, 72, 70))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = cursor
        self.setExtraSelections([selection])

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
