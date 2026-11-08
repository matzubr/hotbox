from pathlib import Path

import pytest
from conftest import ROOT, write_script
from hotbox.utils import scripts


def test_header_settings(tmp_path):
    path = write_script(tmp_path, "a.py", "#label:Create Null\n#textcolor:#ff8b48\r\n# hotkey: n \n#link:None\nimport hou\n#icon:late.svg\n")
    assert scripts.readHeader(path) == {"label": "Create Null", "textcolor": "#ff8b48", "hotkey": "n"}


def test_header_reads_utf8_and_last_line_without_newline(tmp_path):
    path = tmp_path / "a.py"
    path.write_bytes("#label:Камера".encode())
    assert scripts.readHeader(path) == {"label": "Камера"}


def test_scan_resolves_paths_from_the_folder_it_scans(tmp_path):
    write_script(tmp_path, "root.py", "#label:Root\n")
    write_script(tmp_path, "Sop/merge.py")
    write_script(tmp_path, "Sop/__pycache__/merge.cpython-311.pyc")
    write_script(tmp_path, "notes.txt")

    found = scripts.scanScripts(tmp_path)

    assert [s.relpath for s in found] == ["Sop/merge.py", "root.py"]
    assert found[0].path == tmp_path / "Sop" / "merge.py"
    assert found[0].context == "Sop" and found[1].context == ""
    assert found[0].label == "merge" and found[1].label == "Root"


def test_moved_library_still_works_and_nothing_is_written(tmp_path):
    """The old schema.json cache kept absolute paths: copying the tool to another user broke it."""
    first = tmp_path / "userA" / "lib"
    write_script(first, "Sop/merge.py", "#label:Merge\n")
    second = tmp_path / "userB" / "lib"
    first.parent.rename(second.parent)

    found = scripts.scanScripts(second)

    assert found[0].path.exists() and found[0].label == "Merge"
    assert sorted(p.name for p in second.rglob("*")) == ["Sop", "merge.py"]


def test_scan_missing_folder(tmp_path):
    assert scripts.scanScripts(tmp_path / "nope") == []


def test_context_and_root_scripts():
    make = lambda rel: scripts.Script(Path(rel), rel)
    library = [make("Sop/a.py"), make("Lop/b.py"), make("Lop/Instances/c.py"), make("d.py")]

    in_context, root = scripts.scriptsForContext(library, "Lop")

    assert [s.relpath for s in in_context] == ["Lop/b.py"]
    assert [s.relpath for s in root] == ["d.py"]
    assert scripts.scriptsForContext(library, "")[0] == []


def test_duplicate_hotkeys():
    library = [scripts.Script(Path(r), r, {"hotkey": k}) for r, k in [("a.py", "f"), ("b.py", "F"), ("c.py", "g")]]
    assert scripts.duplicateHotkeys(library) == {"f": ["a.py", "b.py"]}


def test_shipped_library_has_headers_and_compiles():
    for mode in scripts.MODES:
        for script in scripts.scanScripts(ROOT / "lib" / mode):
            compile(script.path.read_text(encoding="utf-8"), script.path.as_posix(), "exec")
            assert script.error is None, f"{mode}/{script.relpath}: {script.error}"
            assert "label" in script.settings, script.relpath


def test_no_machine_specific_cache_in_the_package():
    assert not list(ROOT.joinpath("lib").rglob("schema.json"))


def test_write_header_replaces_settings_and_keeps_code(tmp_path):
    path = write_script(tmp_path, "a.py", "#!/usr/bin/env hython\n#label:Old\n#hotkey:f\n#textcolor:#fff\n",
                        "\nimport hou\n# not a header: #label:Nope\n")
    scripts.writeHeader(path, {"label": "New", "hotkey": "", "buttoncolor": "#123456", "textcolor": "#fff"})

    assert path.read_text(encoding="utf-8") == (
        "#!/usr/bin/env hython\n#label:New\n#textcolor:#fff\n#buttoncolor:#123456\n\nimport hou\n# not a header: #label:Nope\n"
    )
    assert scripts.readHeader(path) == {"label": "New", "textcolor": "#fff", "buttoncolor": "#123456"}


def test_write_header_keeps_crlf(tmp_path):
    path = tmp_path / "a.py"
    path.write_bytes(b"#label:Old\r\nimport hou\r\n")
    scripts.writeHeader(path, {"label": "New"})
    assert path.read_bytes() == b"#label:New\r\nimport hou\r\n"


def test_hotkey_conflicts_only_between_scripts_shown_together():
    make = lambda rel, key: scripts.Script(Path(rel), rel, {"hotkey": key})
    library = [make("Sop/a.py", "1"), make("Lop/b.py", "1"), make("c.py", "F"), make("Sop/d.py", "")]

    assert scripts.hotkeyConflicts(library, library[3], "1") == ["Sop/a.py"]  # Lop/b.py is never on screen with Sop
    assert scripts.hotkeyConflicts(library, library[3], "f") == ["c.py"]  # root shows with every context
    assert scripts.hotkeyConflicts(library, library[2], "1") == ["Sop/a.py", "Lop/b.py"]
    assert scripts.hotkeyConflicts(library, library[0], "1") == []  # own hotkey
    assert scripts.hotkeyConflicts(library, library[0], "") == []


def test_russian_layout_maps_to_the_same_physical_key():
    assert scripts.latinKey("а") == "f"
    assert scripts.latinKey("Ц") == "w"
    assert scripts.latinKey("ё") == "`"
    assert scripts.latinKey("f") is None and scripts.latinKey("") is None


def test_ref_inherits_target_header_except_hotkey(tmp_path):
    write_script(tmp_path, "single/cam/bake.py", "#label:Bake\n#group:Camera\n#hotkey:b\n#textcolor:#fff\n")
    stub = write_script(tmp_path, "multiple/bake.py", "#ref:/single/cam/bake.py\n#textcolor:#000\n", body="")

    (script,) = scripts.scanScripts(tmp_path / "multiple")

    assert script.path == stub and script.runPath == tmp_path / "single" / "cam" / "bake.py"
    assert script.settings == {"label": "Bake", "group": "Camera", "textcolor": "#000", "ref": "/single/cam/bake.py"}
    assert script.hotkey is None and script.ownSettings == {"ref": "/single/cam/bake.py", "textcolor": "#000"}


def test_ref_chain(tmp_path):
    write_script(tmp_path, "single/a.py", "#label:A\n")
    write_script(tmp_path, "multiple/b.py", "#ref:single/a.py\n#group:G\n", body="")
    write_script(tmp_path, "all/c.py", "#ref:multiple/b.py\n", body="")
    (script,) = scripts.scanScripts(tmp_path / "all")
    assert script.runPath == tmp_path / "single" / "a.py" and script.label == "A" and script.group == "G"


@pytest.mark.parametrize(("ref", "error"), [
    ("single/missing.py", "not found"),
    ("../../etc/passwd", "outside lib"),
    ("all/loop.py", "loop"),
])
def test_broken_refs(tmp_path, ref, error):
    write_script(tmp_path, "all/loop.py", f"#ref:{ref}\n#label:Loop\n", body="")
    (script,) = scripts.scanScripts(tmp_path / "all")
    assert error in script.error and script.runPath is None and script.label == "Loop"


def test_group_blocks_sorted_by_name():
    make = lambda rel, label, group="": scripts.Script(Path(rel), rel, {"label": label, "group": group})
    library = [make("z.py", "Zeta", "Merge"), make("a.py", "Alpha", "Merge"), make("n.py", "Null"), make("c.py", "Bake")]
    blocks = scripts.groupBlocks(library)
    assert [(name, [s.label for s in members]) for name, members in blocks] == [
        ("", ["Bake"]), ("Merge", ["Alpha", "Zeta"]), ("", ["Null"]),
    ]


def test_read_and_write_body_keep_the_header(tmp_path):
    path = write_script(tmp_path, "a.py", "#!/usr/bin/env hython\n#label:A\n#hotkey:a\n", "\nimport hou\nprint(1)\n")
    assert scripts.readBody(path) == "\nimport hou\nprint(1)"

    scripts.writeBody(path, "\nimport hou\nprint(2)")
    assert path.read_text(encoding="utf-8") == "#!/usr/bin/env hython\n#label:A\n#hotkey:a\n\nimport hou\nprint(2)\n"

    scripts.writeHeader(path, {"label": "B"}, body="print(3)")
    assert path.read_text(encoding="utf-8") == "#!/usr/bin/env hython\n#label:B\nprint(3)\n"


def test_script_refs_lists_real_scripts_only(tmp_path):
    write_script(tmp_path, "single/cam/bake.py", "#label:Bake\n")
    write_script(tmp_path, "multiple/bake.py", "#ref:single/cam/bake.py\n", body="")
    write_script(tmp_path, "all/flip.py")
    assert scripts.scriptRefs(tmp_path) == ["all/flip.py", "single/cam/bake.py"]


def test_shipped_blackpoint_package():
    packages = scripts.allPackages(ROOT / "lib")["blackpoint"]
    for path in ("single/cam/camera_setup.py", "single/convert_path_to_film.py", "multiple/convert_path_to_film.py"):
        assert path in packages
