from pathlib import Path
from unittest.mock import MagicMock

import pytest
import shiboken6
from conftest import write_script
from hotbox.utils import scripts


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "lib"
    write_script(lib, "all/Sop/merge_rel.py", "#label:Merge Relative\n#group:Merge\n#hotkey:1\n")
    write_script(lib, "all/Sop/merge_abs.py", "#label:Merge Absolute\n#group:Merge\n#hotkey:2\n")
    write_script(lib, "all/Lop/fetch.py", "#hotkey:1\n")
    write_script(lib, "all/flipbook.py", "#label:Flipbook\n#hotkey:f\n#icon:app_dino_dance.svg\n")
    write_script(lib, "all/save.py", "#label:Save HIP\n")
    write_script(lib, "all/script_manager_test.py", "#label:Third\n")
    return lib


def test_key_codes(qapp):
    from hotbox.utils.qt import Qt
    from hotbox.utils.widgets import keyCode

    assert keyCode("g") == int(Qt.Key_G)
    assert keyCode("G") == int(Qt.Key_G)
    assert keyCode("1") == int(Qt.Key_1)
    assert keyCode("F5") == int(Qt.Key_F5)
    assert keyCode("") is None and keyCode(None) is None


def _columns(grid):
    return [[(name, [b.script.relpath for b in buttons]) for name, buttons in column] for column in grid.columns]


def test_grid_columns_and_groups(houdini, library):
    from hotbox.utils.widgets import GroupBlock, ScriptGrid

    write_script(library, "all/Sop/vdb.py", "#label:Activate VDB\n")
    grid = ScriptGrid(scripts.scanScripts(library / "all"), context="Sop")

    assert _columns(grid) == [
        [("", ["Sop/vdb.py"]), ("Merge", ["Sop/merge_abs.py", "Sop/merge_rel.py"])],
        [("", ["flipbook.py"]), ("", ["save.py"]), ("", ["script_manager_test.py"])],
    ]
    blocks = grid.findChildren(GroupBlock)
    assert len(blocks) == 1
    first, second = grid.columns[0][1][1]
    assert first.parentWidget() is blocks[0] and first.y() == second.y()  # side by side in the group
    assert [b.text() for b in grid.columns[0][1][1]] == ["Merge\nAbsolute (2)", "Merge\nRelative (1)"]


def test_grid_root_only_is_one_column(houdini, library):
    from hotbox.utils.widgets import ScriptGrid

    grid = ScriptGrid(scripts.scanScripts(library / "all"), context="Driver")
    assert len(grid.columns) == 1


def test_broken_ref_button(houdini, library, hou, monkeypatch):
    from hotbox import main  # noqa: F401
    from hotbox.utils import runner

    write_script(library, "all/old.py", "#ref:all/missing.py\n#label:Old\n", body="")
    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, hou, library)
    button = next(b for b in box.scripts_buttons.buttons if b.script.relpath == "old.py")
    assert "not found" in button.toolTip()

    button.click()

    ran.assert_not_called()
    assert "not found" in hou.ui.setStatusMessage.call_args.args[0]


def test_button_hover_and_press_animation(houdini, qapp):
    from hotbox.utils.widgets import Button
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtTest import QTest

    button = Button("x", buttonColor="#222222")
    base = button.background()
    button.enterEvent(QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    QTest.qWait(Button.DURATION + 100)
    assert button.background() == button.hoverColor != base

    button.flash()
    assert button.background() == button.pressedColor
    QTest.qWait(Button.DURATION + 100)
    assert button.background() in (button.baseColor, button.hoverColor)


def _hotbox(monkeypatch, hou, library, context="Sop"):
    from hotbox import main
    from hotbox.utils import utility

    monkeypatch.setattr(utility, "detectContext", lambda: utility.Context("all", context, context, None))
    return main.HotBox(lib_dir=library)


def test_hotkey_runs_script_and_closes(houdini, hou, library, monkeypatch, qapp):
    from hotbox import main  # noqa: F401
    from hotbox.utils import runner
    from hotbox.utils.qt import Qt
    from PySide6.QtTest import QTest

    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, hou, library)
    assert box.isVisible()

    QTest.keyClick(box, Qt.Key_2)
    QTest.keyClick(box, Qt.Key_1)  # only the first hotkey counts
    QTest.qWait(box.HOTKEY_FEEDBACK + 100)

    assert ran.call_count == 1
    assert ran.call_args.args[0] == library / "all" / "Sop" / "merge_abs.py"
    assert not shiboken6.isValid(box) or not box.isVisible()


def test_hotkey_in_russian_layout(houdini, hou, library, monkeypatch):
    from hotbox import main  # noqa: F401
    from hotbox.utils import runner
    from hotbox.utils.qt import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest

    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, hou, library)

    # 'а' is on the F key in the Russian layout; Qt reports the Cyrillic key code
    box.keyPressEvent(QKeyEvent(QEvent.KeyPress, 0x0410, Qt.NoModifier, "а"))
    QTest.qWait(box.HOTKEY_FEEDBACK + 100)

    assert ran.call_args.args[0] == library / "all" / "flipbook.py"


def test_bundled_font_is_used(houdini):
    from hotbox.utils import widgets
    from hotbox.utils.qt import QFontDatabase

    widgets.Button("x")
    assert widgets.FONT_FAMILY in QFontDatabase.families()


def test_escape_closes(houdini, hou, library, monkeypatch):
    from hotbox.utils.qt import Qt
    from PySide6.QtTest import QTest

    box = _hotbox(monkeypatch, hou, library)
    QTest.keyClick(box, Qt.Key_Escape)
    assert not box.isVisible()


def test_hotbox_stays_on_screen(houdini, hou, library, monkeypatch, qapp):
    from hotbox.utils.qt import QCursor, QGuiApplication, QPoint

    monkeypatch.setattr(QCursor, "pos", staticmethod(lambda: QPoint(-5000, -5000)))
    box = _hotbox(monkeypatch, hou, library)
    area = QGuiApplication.primaryScreen().availableGeometry()
    assert box.x() >= area.left() and box.y() >= area.top()


def test_detect_context(hou, monkeypatch):
    from hotbox.utils import utility

    network = MagicMock()
    network.childTypeCategory().name.return_value = "Sop"
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(utility, "getPane", lambda kind="network": pane)
    cam = MagicMock()
    cam.type().nameComponents.return_value = ("", "", "cam", "")
    cam.parent.return_value = network

    monkeypatch.setattr(hou, "selectedNodes", list, raising=False)
    assert (utility.detectContext().mode, utility.detectContext().context) == ("all", "Sop")
    monkeypatch.setattr(hou, "selectedNodes", lambda: [cam], raising=False)
    assert (utility.detectContext().mode, utility.detectContext().context) == ("single", "cam")
    monkeypatch.setattr(hou, "selectedNodes", lambda: [cam, cam], raising=False)
    assert (utility.detectContext().mode, utility.detectContext().context) == ("multiple", "Sop")

    monkeypatch.setattr(utility, "getPane", lambda kind="network": None)
    monkeypatch.setattr(hou, "selectedNodes", list, raising=False)
    assert utility.detectContext().title == "No Network"


def test_script_manager_browses_without_errors(houdini, library):
    from hotbox.utils.widgets import ScriptManager

    manager = ScriptManager(lib_folder=library)
    folders = [manager.folders_list.item(i).text() for i in range(manager.folders_list.count())]
    assert folders == ["(root)", "Lop", "Sop"]
    assert manager.name_lineedit.text() == "Flipbook"
    assert Path(manager.file_lineedit.text()) == library / "all" / "flipbook.py"

    manager.folders_list.setCurrentRow(2)
    assert manager.name_lineedit.text() == "Merge Absolute"

    manager.mode_combobox.setCurrentText("single")  # empty mode folder
    assert manager.folders_list.count() == 0 and manager.name_lineedit.text() == ""
    manager.close()


def test_show_reloads_changed_code(houdini, hou, monkeypatch):
    import time

    import hotbox

    reloaded = []
    monkeypatch.setattr(hotbox, "reload_modules", lambda: reloaded.append(True))
    monkeypatch.setattr(hotbox, "_loaded_at", time.time() + 3600)
    assert not hotbox._filesChangedSinceLoad()
    monkeypatch.setattr(hotbox, "_loaded_at", 0)
    assert hotbox._filesChangedSinceLoad()


def test_script_manager_saves_header(houdini, library):
    from hotbox.utils.widgets import ScriptManager

    manager = ScriptManager(lib_folder=library)
    manager.folders_list.setCurrentRow(2)  # Sop: merge_abs.py ("2"), merge_rel.py ("1")
    manager.hotkey_lineedit.setText("1")
    assert "Sop/merge_rel.py" in manager.warning_label.text()

    manager.hotkey_lineedit.setText("3")
    manager.name_lineedit.setText("Merge Abs")
    manager.icon_lineedit.setText("missing.svg")
    assert "No icon" in manager.warning_label.text()
    manager.icon_lineedit.setText("")
    manager.save()

    path = library / "all" / "Sop" / "merge_abs.py"
    assert path.read_text(encoding="utf-8") == "#label:Merge Abs\n#group:Merge\n#hotkey:3\npass\n"  # default colors not written
    assert manager.currentScript().relpath == "Sop/merge_abs.py" and manager.hotkey_lineedit.text() == "3"
    manager.close()


def test_script_manager_keeps_ref_stub_a_stub(houdini, library):
    from hotbox.utils.widgets import ScriptManager

    stub = write_script(library, "multiple/merge.py", "#ref:all/Sop/merge_abs.py\n", body="")
    manager = ScriptManager(lib_folder=library)
    manager.mode_combobox.setCurrentText("multiple")
    assert manager.name_lineedit.text() == "" and manager.name_lineedit.placeholderText() == "Merge Absolute"
    assert "all/Sop/merge_abs.py" in manager.ref_label.text()

    manager.hotkey_lineedit.setText("m")
    manager.save()

    assert stub.read_text(encoding="utf-8") == "#ref:all/Sop/merge_abs.py\n#hotkey:m\n"
    manager.close()
