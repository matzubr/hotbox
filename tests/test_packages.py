import json
from unittest.mock import MagicMock

import pytest
from conftest import ROOT, write_script
from hotbox.utils import scripts, settings


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "lib"
    write_script(lib, "all/save.py", "#label:Save HIP\n#package:Trehmer\n")
    write_script(lib, "all/Object/cam_import.py", "#label:Camera Import\n#package:blackpoint\n#hotkey:w\n")
    write_script(lib, "all/Object/alembic.py", "#label:Last Alembic\n#package:blackpoint, other\n")
    write_script(lib, "all/flipbook.py", "#label:Flipbook\n")
    write_script(lib, "multiple/cam.py", "#ref:all/Object/cam_import.py\n", body="")
    return lib


def test_packages_are_off_by_default_and_saved_per_user(user_settings):
    assert not settings.isPackageEnabled("blackpoint")
    settings.setPackageEnabled("blackpoint", True)
    assert settings.isPackageEnabled("BlackPoint")
    assert json.loads(user_settings.read_text())["packages"] == {"blackpoint": True}


def test_env_turns_packages_on_unless_the_user_turned_them_off(monkeypatch):
    monkeypatch.setenv("HOTBOX_PACKAGES", "blackpoint, Trehmer")
    assert settings.isPackageEnabled("trehmer") and settings.isPackageEnabled("blackpoint")
    settings.setPackageEnabled("blackpoint", False)
    assert not settings.isPackageEnabled("blackpoint")


def test_broken_settings_file_means_defaults(user_settings):
    user_settings.write_text("{not json")
    assert settings.load() == {} and not settings.isPackageEnabled("blackpoint")


def test_available_scripts_and_inherited_package(library):
    found = scripts.scanScripts(library / "all")
    on = {"blackpoint"}
    shown = [s.relpath for s in scripts.availableScripts(found, lambda name: name.casefold() in on)]
    assert shown == ["Object/alembic.py", "Object/cam_import.py", "flipbook.py"]
    only_other = [s.relpath for s in scripts.availableScripts(found, lambda name: name == "other")]
    assert only_other == ["Object/alembic.py", "flipbook.py"]  # one of several packages is enough

    (ref,) = scripts.scanScripts(library / "multiple")
    assert ref.packages == ["blackpoint"]  # a #ref belongs to the package of its target


def test_all_packages(library):
    assert scripts.allPackages(library) == {
        "blackpoint": ["all/Object/alembic.py", "all/Object/cam_import.py", "multiple/cam.py"],
        "other": ["all/Object/alembic.py"],
        "Trehmer": ["all/save.py"],
    }


def test_shipped_studio_scripts_are_in_packages():
    packages = scripts.allPackages(ROOT / "lib")
    assert "all/Object/camera_import.py" in packages["blackpoint"]
    assert "all/Object/save_project.py" in packages["trehmer"]


def _hotbox(monkeypatch, library):
    from hotbox import main
    from hotbox.utils import utility

    monkeypatch.setattr(utility, "detectContext", lambda: utility.Context("all", "Object", "Object", None))
    return main.HotBox(lib_dir=library)


def test_hotbox_hides_turned_off_packages(houdini, library, monkeypatch):
    labels = lambda box: sorted(b.script.label for b in box.scripts_buttons.buttons)
    assert labels(_hotbox(monkeypatch, library)) == ["Flipbook"]

    settings.setPackageEnabled("blackpoint", True)
    box = _hotbox(monkeypatch, library)
    assert labels(box) == ["Camera Import", "Flipbook", "Last Alembic"]
    assert box.keybindings  # hotkeys of package scripts work when the package is on


def test_packages_window_toggles_and_manager_follows(houdini, library):
    from hotbox.utils.manager import ScriptManager
    from PySide6.QtTest import QTest

    manager = ScriptManager(lib_folder=library)
    manager.folders_list.setCurrentRow([manager.folders_list.item(i).text()
                                        for i in range(manager.folders_list.count())].index("Object"))
    items = lambda: [manager.files_list.item(i).text() for i in range(manager.files_list.count())]
    assert items() == ["alembic.py  — off", "cam_import.py  — off"]
    assert "blackpoint, other (turned off)" in manager.files_list.item(0).toolTip()

    window = manager.openPackages()
    assert list(window.toggles) == ["blackpoint", "other", "Trehmer"]
    assert not any(t.isChecked() for t in window.toggles.values())
    changed = MagicMock()
    window.changed.connect(changed)

    window.toggles["blackpoint"].click()
    QTest.qWait(window.toggles["blackpoint"].DURATION + 50)

    assert settings.isPackageEnabled("blackpoint") and changed.called
    assert window.toggles["blackpoint"].position == 1.0  # knob slid over
    assert items() == ["alembic.py", "cam_import.py"]
    window.close()
    manager.close()


def test_manager_writes_package_field(houdini, library):
    from hotbox.utils.manager import ScriptManager

    manager = ScriptManager(lib_folder=library)
    assert manager.files_list.item(0).text() == "flipbook.py"
    manager.package_lineedit.setText("trehmer")
    manager.save()
    assert (library / "all" / "flipbook.py").read_text(encoding="utf-8") == "#label:Flipbook\n#package:trehmer\npass\n"
    manager.close()
