from pathlib import Path
from unittest.mock import MagicMock

import pytest
import shiboken6
from conftest import write_script
from hotbox.utils import scripts
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor


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
    from hotbox.utils.widgets import ScriptGrid

    write_script(library, "all/Sop/vdb.py", "#label:Activate VDB\n")
    grid = ScriptGrid(scripts.scanScripts(library / "all"), context="Sop")
    grid.adjustSize()

    assert _columns(grid) == [
        [("", ["Sop/vdb.py"]), ("Merge", ["Sop/merge_abs.py", "Sop/merge_rel.py"])],
        [("", ["flipbook.py"]), ("", ["save.py"]), ("", ["script_manager_test.py"])],
    ]
    vdb, (merge_abs, merge_rel) = grid.columns[0][0][1][0], grid.columns[0][1][1]
    flipbook, save, third = (block[1][0] for block in grid.columns[1])
    # every column goes down at its own pace: plain buttons with the small gap, no holes for another column's groups
    assert vdb.y() == flipbook.y() == 0
    assert save.y() - flipbook.geometry().bottom() - 1 == third.y() - save.geometry().bottom() - 1 == ScriptGrid.ROW_GAP
    assert merge_abs.x() == merge_rel.x() < flipbook.x()
    # group frame with its caption fits in the gap above the group, below the previous button
    frame = grid.groupFrame([merge_abs, merge_rel])
    assert frame.top() > vdb.visualRect().translated(vdb.pos()).bottom()


def test_grid_long_columns_wrap(houdini, tmp_path):
    from hotbox.utils.widgets import ScriptGrid

    for i in range(ScriptGrid.MAX_ROWS + 2):
        write_script(tmp_path, f"all/s{i}.py", f"#label:Script {i}\n")
    grid = ScriptGrid(scripts.scanScripts(tmp_path / "all"))
    assert [sum(len(b) for _, b in column) for column in grid.columns] == [ScriptGrid.MAX_ROWS, 2]


def test_grid_root_only_is_one_column(houdini, library):
    from hotbox.utils.widgets import ScriptGrid

    grid = ScriptGrid(scripts.scanScripts(library / "all"), context="Driver")
    assert len(grid.columns) == 1


def test_broken_ref_button(houdini, library, hou, monkeypatch):
    from hotbox import main  # noqa: F401
    from hotbox.utils import runner
    from PySide6.QtTest import QTest

    write_script(library, "all/old.py", "#ref:all/missing.py\n#label:Old\n", body="")
    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, hou, library)
    button = next(b for b in box.scripts_buttons.buttons if b.script.relpath == "old.py")
    assert "not found" in button.toolTip()

    button.click()
    QTest.qWait(box.FADE_OUT + 150)

    ran.assert_not_called()
    assert "not found" in hou.ui.setStatusMessage.call_args.args[0]


def test_button_hover_and_press_animation(houdini, qapp):
    from hotbox.utils.widgets import Button
    from PySide6.QtCore import QPointF
    from PySide6.QtTest import QTest

    button = Button("x", buttonColor="#222222")
    base = button.background()
    assert button.scale() == 1.0

    button.startHover(QPointF(30, 20))
    QTest.qWait(Button.HOVER_MS // 3)
    assert 0 < button.ripple < 1  # wave is spreading from the cursor
    QTest.qWait(Button.RIPPLE_MS + 100)
    assert button.hover == 1.0 and button.ripple == 1.0
    assert button.background().lightness() > base.lightness() and button.scale() == Button.HOVER_SCALE
    button.grab()  # paints without errors

    done = []
    button.playPress(lambda: done.append(True))
    QTest.qWait(Button.PRESS_MS + 100)
    assert done and button.press == 1.0 and button.scale() == Button.PRESS_SCALE

    assert button.size().width() == Button.WIDTH  # no empty space around buttons any more


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
    QTest.qWait(box.FADE_OUT + 150)

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
    QTest.qWait(box.FADE_OUT + 150)

    assert ran.call_args.args[0] == library / "all" / "flipbook.py"


def test_bundled_font_is_used(houdini):
    from hotbox.utils import widgets
    from hotbox.utils.qt import QFontDatabase

    widgets.Button("x")
    assert widgets.FONT_FAMILY in QFontDatabase.families()
    assert widgets.buttonFont().weight() == widgets.QFont.ExtraBold


def test_escape_closes(houdini, hou, library, monkeypatch):
    from hotbox.utils.qt import Qt
    from PySide6.QtTest import QTest

    box = _hotbox(monkeypatch, hou, library)
    QTest.keyClick(box, Qt.Key_Escape)
    assert box.isVisible()  # the closing animation plays first
    QTest.qWait(box.FADE_OUT + 150)
    assert not shiboken6.isValid(box) or not box.isVisible()


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
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    folders = [manager.folders_list.item(i).text() for i in range(manager.folders_list.count())]
    assert folders == ["(root)", "Lop", "Sop"]
    assert manager.name_lineedit.text() == "Flipbook"
    assert Path(manager.file_lineedit.toolTip()) == library / "all" / "flipbook.py"
    assert manager.file_lineedit.text() == f"{library.parent.name}/lib/all/flipbook.py"

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
    from hotbox.utils.manager import ScriptManager

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
    from hotbox.utils.manager import ScriptManager

    stub = write_script(library, "multiple/merge.py", "#ref:all/Sop/merge_abs.py\n", body="")
    manager = ScriptManager(lib_folder=library)
    manager.mode_combobox.setCurrentText("multiple")
    assert manager.name_lineedit.text() == "" and manager.name_lineedit.placeholderText() == "Merge Absolute"
    assert "all/Sop/merge_abs.py" in manager.ref_label.text()

    manager.hotkey_lineedit.setText("m")
    manager.save()

    assert stub.read_text(encoding="utf-8") == "#ref:all/Sop/merge_abs.py\n#hotkey:m\n"
    manager.close()


def test_zoomed_button_is_painted_by_the_overlay(houdini, hou, library, monkeypatch):
    from hotbox.utils.widgets import Button
    from PySide6.QtTest import QTest

    box = _hotbox(monkeypatch, hou, library)
    button = box.scripts_buttons.buttons[0]
    painted = []
    original = Button.paintTo
    monkeypatch.setattr(Button, "paintTo", lambda self, painter, rect: (painted.append((self, rect)),
                                                                        original(self, painter, rect)))
    button.startHover()
    QTest.qWait(Button.HOVER_MS + 50)
    painted.clear()
    box.animationOverlay.repaint()

    # the zoomed button is painted once, by the overlay, in window coordinates (its own paintEvent skips it)
    rects = [rect for b, rect in painted if b is button]
    assert len(rects) == 1
    assert rects[0].topLeft().toPoint() == button.mapTo(box, QPoint(0, 0)) != QPoint(0, 0)
    # the press zoom fits in the hotbox margins
    margin = box.layout().contentsMargins().left()
    assert Button.WIDTH * (Button.PRESS_SCALE - 1) / 2 <= margin


def test_gaps_between_buttons_and_around_groups(houdini, library):
    from hotbox.utils.widgets import ScriptGrid

    write_script(library, "all/Sop/vdb.py", "#label:Activate VDB\n")
    grid = ScriptGrid(scripts.scanScripts(library / "all"), context="Sop")
    grid.adjustSize()
    vdb, (merge_abs, merge_rel) = grid.columns[0][0][1][0], grid.columns[0][1][1]
    flipbook, save, third = (block[1][0] for block in grid.columns[1])

    assert third.y() - save.geometry().bottom() - 1 == ScriptGrid.ROW_GAP  # plain buttons: small gap
    assert merge_rel.y() - merge_abs.geometry().bottom() - 1 == ScriptGrid.ROW_GAP  # inside a group too
    frame = grid.groupFrame([merge_abs, merge_rel])
    # space between the frame and the button above it, and between the frame and its buttons
    assert frame.top() - (vdb.geometry().bottom() + 1) >= ScriptGrid.FRAME_GAP
    assert merge_abs.x() - frame.left() == ScriptGrid.FRAME_PAD
    assert flipbook.x() - frame.right() >= ScriptGrid.COLUMN_GAP


def test_click_between_buttons_closes(houdini, hou, library, monkeypatch):
    from hotbox import main  # noqa: F401
    from hotbox.utils import runner
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, hou, library)
    grid = box.scripts_buttons
    save = grid.columns[1][1][1][0]
    gap = QPoint(save.geometry().center().x(), save.geometry().bottom() + grid.ROW_GAP // 2)
    assert grid.childAt(gap) is None

    QTest.mouseClick(grid, Qt.LeftButton, pos=gap)
    QTest.qWait(box.FADE_OUT + 150)

    assert not shiboken6.isValid(box) or not box.isVisible()
    ran.assert_not_called()


def test_icons_from_files_and_houdini(houdini, hou, monkeypatch, qapp):
    from hotbox.utils import widgets
    from PySide6.QtGui import QIcon, QPixmap

    pixmap = QPixmap(8, 8)
    pixmap.fill()
    houdini_icons = {"SOP_null": QIcon(pixmap)}
    monkeypatch.setattr(hou.qt, "Icon", lambda name: houdini_icons.get(name, QIcon()))

    assert widgets.resolveIcon("app_dino_dance.svg") is not None
    assert widgets.resolveIcon("SOP_null") is houdini_icons["SOP_null"]
    assert widgets.resolveIcon("SOP_nope") is None and widgets.resolveIcon("") is None
    assert not widgets.Button("x", icon="SOP_null").icon().isNull()


def test_shipped_icons_exist_or_are_houdini_names():
    import re

    from conftest import ROOT
    from hotbox.utils.widgets import ICONS_DIR

    for mode in scripts.MODES:
        for script in scripts.scanScripts(ROOT / "lib" / mode):
            if script.icon:
                assert (ICONS_DIR / script.icon).is_file() or re.fullmatch(r"[A-Z]+_\w+", script.icon), script.relpath


def test_script_manager_preview_follows_edits(houdini, library, discard_changes):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    manager.name_lineedit.setText("Renamed")
    manager.hotkey_lineedit.setText("k")
    assert manager.preview.label == "Renamed"  # the hotkey is in the keycap, not in the text
    assert manager.preview.keycapLabel() == "K"
    assert manager.preview.baseColor == QColor("#222222")
    manager.close()


def _select(manager, folder, name):
    folders = [manager.folders_list.item(i).text() for i in range(manager.folders_list.count())]
    manager.folders_list.setCurrentRow(folders.index(folder))
    files = manager.fileTexts()
    manager.files_list.setCurrentRow(files.index(name))


def test_script_manager_ref_field(houdini, library):
    from hotbox.utils.manager import ScriptManager

    stub = write_script(library, "multiple/merge.py", "#ref:all/Sop/merge_abs.py\n", body="")
    manager = ScriptManager(lib_folder=library)
    manager.mode_combobox.setCurrentText("multiple")
    assert manager.ref_lineedit.text() == "all/Sop/merge_abs.py"
    assert "multiple/merge.py" not in manager.ref_lineedit.choices  # not itself
    assert "all/flipbook.py" in manager.ref_lineedit.choices

    manager.ref_lineedit.setText("all/flipbook.py")  # another target: placeholders and preview follow
    assert manager.name_lineedit.placeholderText() == "Flipbook"
    assert manager.preview.label == "Flipbook"
    manager.ref_lineedit.setText("all/missing.py")
    assert "not found" in manager.warning_label.text()

    manager.ref_lineedit.setText("all/flipbook.py")
    manager.save()
    assert stub.read_text(encoding="utf-8") == "#ref:all/flipbook.py\n"
    manager.close()


def test_preview_does_not_blink_while_typing(houdini, library, discard_changes):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    for text in ("R", "Re", "Ren"):
        manager.name_lineedit.setText(text)
        assert manager.preview.ripple == 1.0 and manager.preview.hover == 0.0
    assert manager.preview.label == "Ren" and manager.preview.hotkey == "f"  # the flipbook fixture has hotkey f
    manager.close()


def test_code_panel_slides_out_and_saves_code(houdini, library):
    from hotbox.utils import manager as manager_module
    from hotbox.utils.manager import ScriptManager
    from PySide6.QtTest import QTest

    path = library / "all" / "flipbook.py"
    path.write_text("#label:Flipbook\n#hotkey:f\n\nimport hou\nprint('flip')\n", encoding="utf-8")
    manager = ScriptManager(lib_folder=library)
    _select(manager, "(root)", "flipbook.py")
    width = manager.width()
    assert not manager.code_panel.isVisible()

    manager.toggleCode()
    QTest.qWait(manager_module.CODE_SLIDE_MS + 100)
    assert manager.code_panel.isVisible() and manager.code_panel.width() == manager_module.CODE_WIDTH
    assert manager.width() > width
    assert manager.code_edit.toPlainText() == "\nimport hou\nprint('flip')"
    assert "all/flipbook.py" in manager.code_title.text()

    manager.code_edit.setPlainText("\nimport hou\nprint('flop')")
    assert "●" in manager.code_title.text()
    manager.hotkey_lineedit.setText("g")
    manager.save()
    assert path.read_text(encoding="utf-8") == "#label:Flipbook\n#hotkey:g\n\nimport hou\nprint('flop')\n"

    manager.toggleCode()
    QTest.qWait(manager_module.CODE_SLIDE_MS + 100)
    assert not manager.code_panel.isVisible() and manager.width() == width
    manager.close()


def test_code_of_a_ref_is_the_target_code(houdini, library):
    from hotbox.utils.manager import ScriptManager

    target = library / "all" / "Sop" / "merge_abs.py"
    stub = write_script(library, "multiple/merge.py", "#ref:all/Sop/merge_abs.py\n#hotkey:m\n", body="")
    manager = ScriptManager(lib_folder=library)
    manager.mode_combobox.setCurrentText("multiple")
    assert manager.code_edit.toPlainText() == "pass"
    assert "all/Sop/merge_abs.py  (ref target)" in manager.code_title.text()

    manager.code_edit.setPlainText("print('merge')")
    manager.save()
    assert stub.read_text(encoding="utf-8") == "#ref:all/Sop/merge_abs.py\n#hotkey:m\n"
    assert target.read_text(encoding="utf-8").endswith("#hotkey:2\nprint('merge')\n")
    manager.close()


def test_unsaved_code_is_asked_about_when_switching(houdini, library, monkeypatch):
    from hotbox.utils import manager as manager_module
    from hotbox.utils.manager import ScriptManager

    asked = []
    monkeypatch.setattr(manager_module.QMessageBox, "question",
                        lambda *args, **kwargs: asked.append(args[2]) or manager_module.QMessageBox.Save)
    manager = ScriptManager(lib_folder=library)
    _select(manager, "(root)", "flipbook.py")
    manager.code_edit.setPlainText("print('changed')")

    _select(manager, "(root)", "save.py")

    assert asked and "all/flipbook.py" in asked[0]
    assert (library / "all" / "flipbook.py").read_text(encoding="utf-8").endswith("print('changed')\n")
    assert manager.code_edit.toPlainText() == "pass"
    manager.close()


@pytest.mark.parametrize("label", ["karmarendersettings", "labs::karma_render_settings_extended::2.0",
                                   "Camera Bake Keyframes Extra Long Name (2)"])
def test_long_labels_fit_the_button(houdini, label):
    from hotbox.utils.widgets import Button
    from PySide6.QtGui import QFontMetrics

    for icon in (None, "app_dino_dance.svg"):
        button = Button(label, icon=icon)
        icon_width = Button.ICON_SIZE + 6 if icon else 0
        metrics = QFontMetrics(button.labelFont)
        assert len(button.lines) <= 2
        assert all(metrics.horizontalAdvance(line) <= Button.WIDTH - 24 - icon_width for line in button.lines)
        assert metrics.height() * len(button.lines) <= Button.HEIGHT


def test_short_label_keeps_the_full_font(houdini):
    from hotbox.utils.widgets import FONT_SIZE, Button

    button = Button("Sop")
    assert button.lines == ["Sop"] and button.labelFont.pointSizeF() == FONT_SIZE


def test_buttons_grow_in_from_the_cursor(houdini, hou, library, monkeypatch, qapp):
    from hotbox.utils.widgets import Button
    from PySide6.QtTest import QTest

    box = _hotbox(monkeypatch, hou, library)
    buttons = box.findChildren(Button)
    origin = box.central_button.mapTo(box, box.central_button.rect().center())
    box.playAppear(origin)
    assert all(b.appear == 0 for b in buttons)
    assert all(b.scale() == 0 and b.isAnimated() for b in buttons)  # nothing painted yet

    delays = {b: b._appearTimer.remainingTime() for b in buttons}
    nearest = min(buttons, key=lambda b: (b.mapTo(box, b.rect().center()) - origin).manhattanLength())
    assert delays[nearest] == min(delays.values())
    assert max(delays.values()) <= box.APPEAR_MAX_DELAY

    peak = {}
    for _ in range(40):
        QTest.qWait(20)
        for b in buttons:
            peak[b] = max(peak.get(b, 0), b.appear)
    assert all(b.appear == 1.0 and not b.isAnimated() for b in buttons)
    assert all(value > 1.0 for value in peak.values())  # the spring overshoots before settling
    box.finishAppear()
    box.close()


def test_closing_shrinks_buttons_farthest_first(houdini, hou, library, monkeypatch, qapp):
    from hotbox.utils.widgets import Button
    from PySide6.QtTest import QTest

    box = _hotbox(monkeypatch, hou, library)
    box.finishAppear()
    buttons = box.findChildren(Button)
    origin = box.central_button.mapTo(box, box.central_button.rect().center())
    closed = MagicMock()
    box.playDisappear(closed, origin=origin)

    delays = {b: b._disappearTimer.remainingTime() for b in buttons}
    distance = {b: (b.mapTo(box, b.rect().center()) - origin).manhattanLength() for b in buttons}
    assert delays[box.central_button] == max(delays.values())  # at the cursor: last
    assert delays[max(buttons, key=distance.get)] <= 1  # farthest: right away

    QTest.qWait(box.FADE_OUT + 150)
    assert all(b.appear == 0 and b.scale() == 0 for b in buttons)
    closed.assert_called_once()
    box._closeAnimated = True
    box.close()


def test_script_manager_grows_in_and_shrinks_away(houdini, library, qapp):
    from hotbox.utils.frameless import PopProxy
    from hotbox.utils.manager import ScriptManager
    from PySide6.QtTest import QTest

    manager = ScriptManager(lib_folder=library)
    assert manager.windowOpacity() == 0 or manager._popPending  # invisible until its picture has grown in
    QTest.qWait(30)
    proxy = manager._popProxy
    assert isinstance(proxy, PopProxy) and proxy.isVisible()
    assert proxy.geometry().contains(manager.geometry())  # room for the spring
    peak = 0.0
    for _ in range(30):
        QTest.qWait(20)
        if manager._popProxy is not None:
            peak = max(peak, manager._popProxy.scale)
    assert peak > 1.0  # spring overshoot
    assert manager._popProxy is None
    assert manager.isVisible()

    manager.close()
    assert manager.isVisible()  # shrinking first
    assert manager._popProxy is not None and manager._popProxy.scale == 1.0
    QTest.qWait(manager.POP_OUT_MS + 150)
    assert not shiboken6.isValid(manager) or not manager.isVisible()


def test_finish_pop_in_skips_the_animation(houdini, library, qapp):
    from hotbox.utils.manager import ScriptManager
    from PySide6.QtTest import QTest

    manager = ScriptManager(lib_folder=library)
    manager.finishPopIn()
    QTest.qWait(30)
    assert manager._popProxy is None
    manager._popClosed = True
    manager.close()


def test_reload_picks_up_every_module(tmp_path):
    """In a fresh interpreter: after reload_modules() no hotbox module keeps old classes, new ones included"""
    import os
    import subprocess
    import sys
    import textwrap

    from conftest import ROOT

    script = tmp_path / "reload_check.py"
    script.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT / "tests")!r})
        import conftest  # hou stub, hotbox on sys.path
        import hotbox
        from hotbox.utils import iconbrowser, widgets
        old_button, old_loaded = widgets.Button, hotbox._loaded_at
        hotbox.reload_modules()
        from hotbox.utils import iconbrowser as new_iconbrowser
        from hotbox.utils import widgets as new_widgets
        assert new_widgets.Button is not old_button
        assert new_iconbrowser.Button is new_widgets.Button  # not the stale class
        assert new_iconbrowser is not iconbrowser
        assert hotbox._loaded_at >= old_loaded
        print("ok")
    """))
    result = subprocess.run([sys.executable, script.as_posix()], capture_output=True, text=True, timeout=60,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=False)
    assert result.stdout.strip().endswith("ok"), result.stderr


# --- second UI pass: fixed font, group stripes, Script Manager states ---------------------------------------------

def test_row_labels_keep_the_font_size_and_are_cut(houdini):
    from hotbox.utils.widgets import ScriptButton

    script = scripts.Script(Path("x.py"), "x.py", {"label": "Select Every Time-Dependent Node Here", "hotkey": "a"})
    button = ScriptButton(script)
    assert button.labelFont.pointSizeF() == ScriptButton.FONT
    assert button.lines[0].endswith("…") and button.toolTip()


def test_group_stripe_is_the_group_color_and_lone_groups_are_framed(houdini, hou, tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    write_script(lib, "all/a.py", "#label:A\n#group:G\n#textcolor:#ff0000\n")
    write_script(lib, "all/b.py", "#label:B\n#group:G\n#textcolor:#00ff00\n")
    write_script(lib, "all/c.py", "#label:C\n#group:Lone\n")
    box = _hotbox(monkeypatch, hou, lib)
    by_label = {b.script.label: b for b in box.scripts_buttons.buttons}
    assert by_label["B"].stripeColor == QColor("#ff0000") and by_label["B"].accentColor == QColor("#00ff00")
    assert [name for name, _ in box.scripts_buttons.groups] == ["G", "Lone"]
    assert box.central_button.label == "Network: Sop" and box.central_button.keycapLabel() == "Esc"
    box.close()


def _press(widget, key, text=""):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text))


def test_hotkey_field_captures_the_key(houdini):
    from hotbox.utils.editors import HotkeyEdit

    field = HotkeyEdit()
    _press(field, Qt.Key_K, "k")
    assert field.text() == "K"
    _press(field, Qt.Key_A, "ф")  # Russian layout: the same physical key
    assert field.text() == "A"
    _press(field, Qt.Key_F5)
    assert field.text() == "F5"
    _press(field, Qt.Key_Return, "\r")  # not a hotkey: unchanged
    assert field.text() == "F5"
    _press(field, Qt.Key_Backspace)
    assert field.text() == ""


def test_manager_save_is_active_only_with_changes(houdini, library, discard_changes):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    assert not manager.save_button.isEnabled() and "●" not in manager.title_bar.title.text()
    assert manager.hotkey_lineedit.text() == "F"  # shown as the keycap
    manager.name_lineedit.setText("Flip")
    assert manager.save_button.isEnabled() and "●" in manager.title_bar.title.text()
    manager.save()
    assert not manager.save_button.isEnabled()
    assert (library / "all" / "flipbook.py").read_text(encoding="utf-8").startswith("#label:Flip\n#icon:app_dino_dance.svg\n#hotkey:f\n")
    manager.close()


def test_manager_hotkey_conflict_names_the_button(houdini, library):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    _select(manager, "Sop", "merge_abs.py")
    manager.hotkey_lineedit.setText("1")
    assert "1 is taken: Merge Relative (Sop/merge_rel.py)" in manager.warning_label.text()
    manager.hotkey_lineedit.setText("2")
    manager.close()


def test_manager_asks_before_dropping_header_edits(houdini, library, monkeypatch):
    from hotbox.utils import manager as manager_module
    from hotbox.utils.manager import ScriptManager

    asked = []
    monkeypatch.setattr(manager_module.QMessageBox, "question",
                        lambda *args, **kwargs: asked.append(args[2]) or manager_module.QMessageBox.Save)
    manager = ScriptManager(lib_folder=library)
    _select(manager, "(root)", "flipbook.py")
    manager.group_lineedit.setText("Output")
    _select(manager, "(root)", "save.py")
    assert asked == ["Save the changes in all/flipbook.py?"]
    assert "#group:Output" in (library / "all" / "flipbook.py").read_text(encoding="utf-8")
    assert manager.name_lineedit.text() == "Save HIP"
    manager.close()


def test_manager_list_search_duplicate_delete(houdini, library, monkeypatch):
    from hotbox.utils import manager as manager_module
    from hotbox.utils.manager import FILE_ROLE, HOTKEY_ROLE, ScriptManager

    write_script(library, "multiple/flip.py", "#ref:all/flipbook.py\n", body="")
    manager = ScriptManager(lib_folder=library)
    item = manager.files_list.item(0)
    assert (item.text(), item.data(FILE_ROLE), item.data(HOTKEY_ROLE)) == ("Flipbook", "flipbook.py", "F")

    manager.search_lineedit.setText("merge")  # every folder of the mode
    assert manager.fileTexts() == ["Sop/merge_abs.py", "Sop/merge_rel.py"]
    assert manager.currentScript().relpath == "Sop/merge_abs.py"
    manager.search_lineedit.setText("")

    _select(manager, "(root)", "flipbook.py")
    copy = manager.duplicateScript()
    assert copy.name == "flipbook_copy.py" and manager.currentScript().path == copy
    text = copy.read_text(encoding="utf-8")
    assert "#label:Flipbook Copy" in text and "#hotkey" not in text
    asked = []
    monkeypatch.setattr(manager_module.QMessageBox, "question",
                        lambda *args, **kwargs: asked.append(args[2]) or manager_module.QMessageBox.Yes)
    assert manager.deleteScript() and not copy.exists()
    _select(manager, "(root)", "flipbook.py")
    assert manager.deleteScript()
    assert "multiple/flip.py" in asked[-1]  # its #ref breaks
    manager.close()
