"""Several lib folders, search, the error window, new scripts."""
from unittest.mock import MagicMock

import pytest
from conftest import write_script
from hotbox.utils import runner, scripts
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "lib"
    write_script(lib, "all/Sop/merge.py", "#label:Merge Relative\n#hotkey:1\n")
    write_script(lib, "all/flipbook.py", "#label:Flipbook\n#hotkey:f\n")
    write_script(lib, "all/save.py", "#label:Save HIP\n")
    write_script(lib, "all/reload.py", "#label:Reload Caches\n")
    return lib


def _hotbox(monkeypatch, library, context="Sop"):
    from hotbox import main
    from hotbox.utils import utility

    monkeypatch.setattr(utility, "detectContext", lambda: utility.Context("all", context, context, None))
    return main.HotBox(lib_dir=library)


def _key(key, text="", modifiers=Qt.NoModifier):
    from hotbox.utils.qt import QEvent

    return QKeyEvent(QEvent.KeyPress, key, modifiers, text)


# --- several lib folders -------------------------------------------------------------------------------------------

def test_lib_roots_from_env(tmp_path, monkeypatch):
    builtin, mine, studio = tmp_path / "builtin", tmp_path / "mine", tmp_path / "studio"
    for folder in (builtin, mine, studio):
        folder.mkdir()
    separator = ";"
    value = f"{mine}{separator}{tmp_path / 'missing'}{separator}{studio}{separator}{mine}"
    assert scripts.libRoots(builtin, value) == [mine, studio, builtin]  # order kept, missing/duplicate dropped
    assert scripts.libRoots(builtin, "") == [builtin]
    monkeypatch.setattr(scripts.sys, "platform", "linux")
    assert scripts.splitPathList(f"{mine}:{studio}") == [str(mine), str(studio)]
    monkeypatch.setattr(scripts.sys, "platform", "win32")
    assert scripts.splitPathList("C:/tools/lib;D:/studio/lib") == ["C:/tools/lib", "D:/studio/lib"]


def test_earlier_folder_hides_the_same_script_and_refs_look_everywhere(tmp_path):
    mine, builtin = tmp_path / "mine", tmp_path / "builtin"
    write_script(builtin, "single/null.py", "#label:Built-in Null\n")
    write_script(builtin, "single/bake.py", "#label:Bake\n")
    write_script(mine, "single/null.py", "#label:My Null\n")
    write_script(mine, "multiple/bake.py", "#ref:single/bake.py\n")  # target only in the built-in lib
    write_script(mine, "multiple/null.py", "#ref:single/null.py\n")  # my version wins for refs too

    single = scripts.scanLibrary([mine, builtin], "single")
    assert [(s.relpath, s.label, s.root) for s in single] == [("bake.py", "Bake", builtin),
                                                             ("null.py", "My Null", mine)]
    multiple = {s.relpath: s for s in scripts.scanLibrary([mine, builtin], "multiple")}
    assert multiple["bake.py"].runPath == (builtin / "single" / "bake.py").resolve()
    assert multiple["null.py"].label == "My Null"
    assert multiple["null.py"].key == "multiple/null.py"
    assert scripts.scriptRefs([mine, builtin]) == ["single/bake.py", "single/null.py"]


def test_hotbox_and_manager_read_every_folder(houdini, tmp_path, monkeypatch):
    from hotbox import main
    from hotbox.utils import utility
    from hotbox.utils.manager import ScriptManager

    mine, builtin = tmp_path / "mine" / "lib", tmp_path / "builtin"
    write_script(builtin, "all/flipbook.py", "#label:Flipbook\n")
    write_script(mine, "all/mine.py", "#label:Mine\n")
    monkeypatch.setattr(main, "LIB_DIR", builtin)
    monkeypatch.setenv(scripts.PATH_ENV, mine.as_posix())
    monkeypatch.setattr(utility, "detectContext", lambda: utility.Context("all", "Sop", "Sop", None))

    box = main.HotBox()
    assert box.lib_roots == [mine, builtin]
    assert sorted(b.script.label for b in box.script_buttons) == ["Flipbook", "Mine"]
    box.close()

    manager = ScriptManager(lib_folder=[mine, builtin])
    names = manager.fileTexts()
    assert names == ["flipbook.py", "mine.py  · mine"]  # where a script comes from, built-in lib unmarked
    manager.close()


# --- search -------------------------------------------------------------------------------------------------------

def test_matches_search():
    assert scripts.matchesSearch("Reload Caches", "rel")
    assert scripts.matchesSearch("Reload Caches", "cach rel")
    assert scripts.matchesSearch("Reload Caches", "кудщ")  # 'relo' typed in the Russian layout
    assert not scripts.matchesSearch("Reload Caches", "save")
    assert not scripts.matchesSearch("Reload Caches", "")


def test_search_dims_other_buttons_and_enter_runs_the_match(houdini, library, monkeypatch):
    from PySide6.QtTest import QTest

    ran = MagicMock()
    monkeypatch.setattr(runner, "runScript", ran)
    box = _hotbox(monkeypatch, library)
    QTest.keyClick(box, Qt.Key_Tab)
    assert box.searchText == ""
    assert box.central_button.label == "Type to find…"

    box.keyPressEvent(_key(Qt.Key_F, "f"))
    box.keyPressEvent(_key(Qt.Key_L, "l"))
    dimmed = {b.script.label: b.dimmed for b in box.script_buttons}
    assert dimmed == {"Merge Relative": True, "Flipbook": False, "Save HIP": True, "Reload Caches": True}
    assert box.central_button.label == "Find: fl_"
    assert ran.call_count == 0  # 'f' is Flipbook's hotkey, but search eats the letters

    box.keyPressEvent(_key(Qt.Key_Backspace))
    box.keyPressEvent(_key(Qt.Key_Backspace))
    assert not any(b.dimmed for b in box.script_buttons)
    box.keyPressEvent(_key(Qt.Key_R, "r"))
    box.keyPressEvent(_key(Qt.Key_E, "e"))
    box.keyPressEvent(_key(Qt.Key_L, "l"))
    assert box._searchMatch.script.label == "Merge Relative"  # the first match in the menu order
    box.keyPressEvent(_key(Qt.Key_O, "o"))
    box.keyPressEvent(_key(Qt.Key_Return))
    QTest.qWait(box.FADE_OUT + 150)
    assert ran.call_args.args[0] == library / "all" / "reload.py"


def test_escape_ends_search_before_closing(houdini, library, monkeypatch):
    box = _hotbox(monkeypatch, library)
    box.keyPressEvent(_key(Qt.Key_Tab))
    box.keyPressEvent(_key(Qt.Key_S, "s"))
    box.keyPressEvent(_key(Qt.Key_Escape))
    assert box.searchText is None
    assert box.isVisible()
    assert box.central_button.label == "Network: Sop"
    assert not any(b.dimmed for b in box.script_buttons)
    box.close()


# --- errors -------------------------------------------------------------------------------------------------------

def test_error_reports_the_line_in_the_script(tmp_path, hou):
    path = write_script(tmp_path, "lib/all/bad.py", "#label:Bad\n#hotkey:b\n", "x = 1\n\nmissing_name\n")
    errors = []
    assert not runner.runScript(path, label="Bad", on_error=errors.append)
    error = errors[0]
    assert error.line == 5  # 2 header lines + 3
    assert error.message == "NameError: name 'missing_name' is not defined"
    assert "missing_name" in error.traceback

    write_script(tmp_path, "lib/all/syntax.py", "", "def broken(:\n")
    assert not runner.runScript(tmp_path / "lib/all/syntax.py", on_error=errors.append)
    assert errors[1].line == 1


def test_error_window_opens_the_line_in_the_manager(houdini, tmp_path):
    from hotbox.utils import errors

    lib = tmp_path / "lib"
    write_script(lib, "single/other.py", "#label:Other\n")
    path = write_script(lib, "single/cam/bad.py", "#label:Bad\n#hotkey:b\n", "x = 1\n\nmissing_name\n")
    reported = []
    runner.runScript(path, on_error=reported.append)

    window = errors.showScriptError(reported[0], [lib])
    assert any("bad.py, line 5" in label.text() for label in window.findChildren(QLabel))
    manager = window.openInManager()
    assert manager.mode_combobox.currentText() == "single"
    assert manager.currentScript().relpath == "cam/bad.py"
    assert manager._codeOpen > 0 or manager._slide.state()
    cursor = manager.code_edit.textCursor()
    assert cursor.block().text() == "missing_name"
    assert len(manager.code_edit.extraSelections()) == 1
    manager.close()


# --- new scripts --------------------------------------------------------------------------------------------------

def test_new_script_names_and_checks(tmp_path):
    assert scripts.scriptFileName("Bake Camera!") == "bake_camera.py"
    assert scripts.scriptFileName("  ") == ""
    lib = tmp_path / "lib"
    write_script(lib, "single/cam/bake.py", "#label:Bake\n")
    assert scripts.newScriptPath(lib, "single", "cam", "Bake")[1] == "single/cam/bake.py already exists"
    assert scripts.newScriptPath(lib, "single", "cam/deeper", "x")[1].startswith("Folder: one level only")
    assert scripts.newScriptPath(lib, "single", "..", "x")[1].startswith("Folder")
    assert scripts.newScriptPath(lib, "single", "", "")[1] == "Give the script a name"
    assert scripts.newScriptPath(lib, "single", "/cam/", "New One") == (lib / "single" / "cam" / "new_one.py", None)

    path = scripts.createScript(lib, "multiple", "Sop", "split.py", "Split Pieces")
    assert path.read_text() == "#label:Split Pieces\n\n" + scripts.SCRIPT_TEMPLATES["multiple"]
    assert scripts.scanLibrary(lib, "multiple")[0].label == "Split Pieces"


def test_new_script_overrides_between_lib_folders(tmp_path):
    mine, builtin = tmp_path / "mine", tmp_path / "builtin"
    write_script(builtin, "single/null.py")
    assert scripts.overrides([mine, builtin], mine, "single/null.py") == ([], [builtin])
    write_script(mine, "single/null.py")
    assert scripts.overrides([mine, builtin], builtin, "single/null.py") == ([mine], [])


def test_new_script_window_creates_and_manager_shows_it(houdini, tmp_path):
    from hotbox.utils.manager import ScriptManager

    lib = tmp_path / "lib"
    write_script(lib, "single/cam/bake.py", "#label:Bake\n")
    manager = ScriptManager(lib_folder=lib)
    manager.mode_combobox.setCurrentText("single")
    window = manager.newScript()
    assert window.mode == "single" and window.folder_lineedit.text() == "cam"  # where the manager is
    assert not window.create_button.isEnabled()

    window.label_lineedit.setText("Look Through")
    window.label_lineedit.textEdited.emit("Look Through")
    assert window.file_lineedit.text() == "look_through.py"  # follows the label
    assert window.create_button.isEnabled()
    window.file_lineedit.setText("bake.py")
    window.file_lineedit.textEdited.emit("bake.py")
    assert "already exists" in window.warning_label.text() and not window.create_button.isEnabled()
    window.file_lineedit.setText("look.py")
    window.file_lineedit.textEdited.emit("look.py")
    window.label_lineedit.setText("Look Through Cam")
    window.label_lineedit.textEdited.emit("Look Through Cam")
    assert window.file_lineedit.text() == "look.py"  # typed by hand: no longer follows

    path = window.create()
    assert path == lib / "single" / "cam" / "look.py"
    assert manager.currentScript().relpath == "cam/look.py"
    assert manager.name_lineedit.text() == "Look Through Cam"
    assert "node = hou.selectedNodes()[0]" in manager.code_edit.toPlainText()
    assert manager._codeOpen > 0 or manager._slide.state()
    manager.close()


# --- icon browser -------------------------------------------------------------------------------------------------

@pytest.fixture
def icons_zip(tmp_path, monkeypatch):
    import zipfile

    from hotbox.utils import iconbrowser

    path = tmp_path / "houdini" / "config" / "Icons" / "icons.zip"
    path.parent.mkdir(parents=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in ("SOP/null.svg", "SOP/object_merge.svg", "OBJ/camera.svg", "LOP/fetch.svg", "MISC/python.svg",
                     "SOP/", "SOP/deeper/skip.svg", "readme.txt", "OBJ/notes.txt"):
            archive.writestr(name, "" if name.endswith("/") else "<svg/>")
    monkeypatch.setenv("HFS", (tmp_path).as_posix())
    iconbrowser.houdiniIconNames.cache_clear()
    return path


def test_houdini_icon_names_from_the_archive(icons_zip):
    from hotbox.utils import iconbrowser

    assert iconbrowser.houdiniIconsZip() == icons_zip
    names = iconbrowser.houdiniIconNames(icons_zip)
    assert names == {"SOP": ["SOP_null", "SOP_object_merge"], "OBJ": ["OBJ_camera"], "LOP": ["LOP_fetch"],
                     "MISC": ["MISC_python"]}
    assert iconbrowser.orderedCategories(names) == ["SOP", "OBJ", "LOP", "MISC"]
    assert iconbrowser.houdiniIconNames(None) == {}
    assert "save.svg" in iconbrowser.hotboxIconNames()


def test_icon_browser_search_and_choose(houdini, icons_zip, library, discard_changes):
    from hotbox.utils.iconbrowser import IconBrowser
    from hotbox.utils.manager import ScriptManager

    browser = IconBrowser(current="OBJ_camera")
    assert browser.categories_list.currentItem().text() == "OBJ"  # opens where the current icon is
    assert browser.currentName() == "OBJ_camera"

    browser.categories_list.setCurrentRow(browser.categories.index("All"))
    browser.search_lineedit.setText("object_merge")
    assert browser.model.names == ["SOP_object_merge"]
    browser.search_lineedit.setText("")
    assert "save.svg" in browser.model.names and "LOP_fetch" in browser.model.names
    browser.close()

    manager = ScriptManager(lib_folder=library)
    window = manager.browseIcons()
    window.select("SOP_null")
    assert window.choose() == "SOP_null"
    assert manager.icon_lineedit.text() == "SOP_null"  # into the field; the preview and warnings follow
    manager.close()


def test_icon_browser_without_houdini_icons(houdini, monkeypatch):
    from hotbox.utils import iconbrowser

    monkeypatch.setattr(iconbrowser, "houdiniIconsZip", lambda: None)
    browser = iconbrowser.IconBrowser(current="SOP_null")
    assert browser.categories == ["All", "HotBox"]
    assert browser.model.names == browser.hotbox
    browser.close()


def test_buttons_of_a_child_window_use_their_own_overlay(houdini, library, icons_zip):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    browser = manager.browseIcons()
    for button in (browser.choose_button, browser.cancel_button, browser.add_button):
        assert button.overlay() is browser.animationOverlay  # not the manager's: it would paint into another window
    window = manager.newScript()
    assert window.create_button.overlay() is window.animationOverlay
    manager.close()


def test_add_icon_files(tmp_path):
    from hotbox.utils.iconbrowser import addIconFiles

    source = tmp_path / "src"
    source.mkdir()
    (source / "tool.svg").write_text("<svg>new</svg>")
    (source / "photo.png").write_bytes(b"png")
    (source / "notes.txt").write_text("not an icon")
    folder = tmp_path / "icons"
    (folder).mkdir()
    (folder / "tool.svg").write_text("<svg>old</svg>")

    asked = []
    added = addIconFiles([source / "tool.svg", source / "photo.png", source / "notes.txt"], folder,
                         replace=lambda name: asked.append(name) or False)
    assert added == ["photo.png"] and asked == ["tool.svg"]
    assert (folder / "tool.svg").read_text() == "<svg>old</svg>"  # kept: not replaced

    assert addIconFiles([source / "tool.svg"], folder, replace=lambda name: True) == ["tool.svg"]
    assert (folder / "tool.svg").read_text() == "<svg>new</svg>"
    assert addIconFiles([folder / "tool.svg"], folder) == ["tool.svg"]  # already there


def test_added_icons_go_to_your_lib_folder_and_are_found(houdini, tmp_path, icons_zip, monkeypatch, discard_changes):
    from hotbox.utils import widgets
    from hotbox.utils.iconbrowser import userIconFolder
    from hotbox.utils.manager import ScriptManager

    mine, builtin = tmp_path / "mine", widgets.BUILTIN_LIB_DIR
    write_script(mine, "all/a.py", "#label:A\n")
    manager = ScriptManager(lib_folder=[mine, builtin])
    assert widgets.iconFolders() == [mine / "icons", widgets.ICONS_DIR]
    assert userIconFolder() == mine / "icons"  # not into the tool folder

    picture = tmp_path / "my_tool.svg"
    picture.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 2"><rect width="2" height="2"/></svg>')
    browser = manager.browseIcons()
    assert browser.addIcons([picture]) == ["my_tool.svg"]
    assert (mine / "icons" / "my_tool.svg").is_file()
    assert browser.categories_list.currentItem().text() == "HotBox"
    assert browser.currentName() == "my_tool.svg"
    assert widgets.resolveIcon("my_tool.svg") is not None  # buttons find it
    browser.choose()
    assert manager.icon_lineedit.text() == "my_tool.svg"
    manager.close()
    widgets.setIconFolders([builtin])


def test_icons_without_hotbox_path_go_to_the_tool_icons(houdini, library):
    from hotbox.utils import widgets
    from hotbox.utils.iconbrowser import userIconFolder

    widgets.setIconFolders([widgets.BUILTIN_LIB_DIR])
    assert userIconFolder() == widgets.ICONS_DIR


def test_add_icons_button_opens_the_file_picker(houdini, tmp_path, icons_zip, monkeypatch):
    from hotbox.utils import widgets
    from hotbox.utils.iconbrowser import IconBrowser
    from PySide6.QtTest import QTest

    widgets.setIconFolders([tmp_path / "mine", widgets.BUILTIN_LIB_DIR])
    picture = tmp_path / "clicked.svg"
    picture.write_text("<svg/>")
    browser = IconBrowser()
    picked = []
    monkeypatch.setattr(browser, "pickFiles", lambda: picked.append(True) or [picture.as_posix()])

    QTest.mouseClick(browser.add_button, Qt.LeftButton)

    assert picked == [True]  # the dialog was asked for
    assert (tmp_path / "mine" / "icons" / "clicked.svg").is_file()
    assert browser.currentName() == "clicked.svg"
    browser.close()
    widgets.setIconFolders([widgets.BUILTIN_LIB_DIR])
