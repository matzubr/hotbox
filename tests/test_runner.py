from conftest import write_script
from hotbox.utils import runner


def test_script_runs_as_main_in_clean_namespace(tmp_path, hou):
    out = tmp_path / "out.txt"
    path = write_script(tmp_path, "s.py", body=(
        "import pathlib\n"
        f"pathlib.Path({out.as_posix()!r}).write_text(__name__ + ' ' + str('QPushButton' in globals()) + ' ' + __file__)\n"
    ))
    assert runner.runScript(path)
    assert out.read_text() == f"__main__ False {path.as_posix()}"


def test_sys_exit_just_stops_the_script(tmp_path, hou):
    path = write_script(tmp_path, "s.py", body="import sys\nsys.exit()\nraise RuntimeError\n")
    assert runner.runScript(path)


def test_errors_are_reported_not_raised(tmp_path, hou, capsys):
    path = write_script(tmp_path, "s.py", body="1 / 0\n")
    assert not runner.runScript(path)
    assert "ZeroDivisionError" in capsys.readouterr().err
    assert "s.py failed" in hou.ui.setStatusMessage.call_args.args[0]


def test_one_undo_group_per_script(tmp_path, hou, monkeypatch):
    import contextlib

    labels = []
    monkeypatch.setattr(hou.undos, "group", lambda label: labels.append(label) or contextlib.nullcontext())
    runner.runScript(write_script(tmp_path, "s.py"), label="Create Null")
    assert labels == ["HotBox: Create Null"]
