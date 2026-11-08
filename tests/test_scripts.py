from pathlib import Path

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
            assert "label" in script.settings, script.relpath


def test_no_machine_specific_cache_in_the_package():
    assert not list(ROOT.joinpath("lib").rglob("schema.json"))
