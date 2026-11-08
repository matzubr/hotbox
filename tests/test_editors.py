from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


def test_inline_completion_and_tab(qapp):
    from hotbox.utils.editors import CompletingLineEdit

    edit = CompletingLineEdit()
    edit.setChoices(["blackpoint", "trehmer"])
    edit.show()
    edit.setFocus()
    QTest.keyClicks(edit, "bl")
    assert edit.text() == "blackpoint" and edit.selectedText() == "ackpoint"

    QTest.keyClick(edit, Qt.Key_Tab)  # accepts, focus stays
    assert edit.text() == "blackpoint" and not edit.hasSelectedText() and edit.cursorPosition() == len("blackpoint")


def test_multiple_values_complete_the_last_item(qapp):
    from hotbox.utils.editors import CompletingLineEdit

    edit = CompletingLineEdit(multiple=True)
    edit.setChoices(["blackpoint", "trehmer"])
    edit.setText("blackpoint")
    edit.end(False)
    QTest.keyClicks(edit, ", Tr")
    QTest.keyClick(edit, Qt.Key_Tab)
    assert edit.text() == "blackpoint, Trehmer"  # typed case is kept, the rest comes from the choice

    edit.addChoice("blackpoint")  # already there
    edit.addChoice("other")
    assert edit.text().endswith(", other") and edit.text().count("blackpoint") == 1


def test_choice_menu_groups_paths_by_mode(qapp):
    from hotbox.utils.editors import ChoiceField

    field = ChoiceField()
    field.setChoices(["all/flip.py", "single/cam/bake.py", "single/null.py"])
    menu = field.buildMenu()
    submenus = {action.text(): [a.text() for a in action.menu().actions()] for action in menu.actions()}
    assert submenus == {"all": ["flip.py"], "single": ["cam/bake.py", "null.py"]}

    menu.actions()[1].menu().actions()[0].trigger()  # single -> cam/bake.py
    assert field.lineedit.text() == "single/cam/bake.py"

    empty = ChoiceField(empty_text="No packages yet")
    assert [a.text() for a in empty.buildMenu().actions()] == ["No packages yet"]


def test_code_editor_indents(qapp):
    from hotbox.utils.editors import CodeEditor

    editor = CodeEditor()
    editor.show()
    QTest.keyClicks(editor, "def main():")
    QTest.keyClick(editor, Qt.Key_Return)
    QTest.keyClick(editor, Qt.Key_Tab)
    QTest.keyClicks(editor, "x = 1")
    QTest.keyClick(editor, Qt.Key_Return)
    QTest.keyClicks(editor, "y")
    # Enter after ':' indents, Tab adds 4 spaces, the next line keeps the indentation
    assert editor.toPlainText() == "def main():\n        x = 1\n        y"
