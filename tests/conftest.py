"""Test setup: HotBox is imported as the `hotbox` package with a stubbed `hou` module.

Unknown hou attributes resolve to MagicMock, so GUI code can be constructed offscreen.
"""
import contextlib
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
assert ROOT.name == "hotbox", "tests expect the repo folder to be named hotbox (the package name)"
sys.path.insert(0, ROOT.parent.as_posix())

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class OperationFailed(Exception):
    pass


def _make_hou():
    hou = types.ModuleType("hou")
    hou.OperationFailed = OperationFailed
    hou.undos = types.SimpleNamespace(group=lambda label: contextlib.nullcontext())
    hou.severityType = types.SimpleNamespace(Error="Error", Message="Message")
    hou.ui = MagicMock(name="hou.ui")
    hou.__getattr__ = lambda name: MagicMock(name=f"hou.{name}")
    return hou


sys.modules["hou"] = _make_hou()


@pytest.fixture
def hou():
    hou = sys.modules["hou"]
    hou.ui.reset_mock()
    return hou


@pytest.fixture
def qapp():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ColorSwatch:
    """Stand-in for hou.qt.ColorSwatchButton"""

    def __new__(cls):
        from PySide6 import QtWidgets

        class _Swatch(QtWidgets.QPushButton):
            def setColor(self, color):
                self._color = color

            def color(self):
                return self._color

        return _Swatch()


@pytest.fixture
def houdini(hou, qapp, monkeypatch):
    """Fake Houdini session with a real QWidget as the main window"""
    from PySide6 import QtWidgets

    main_window = QtWidgets.QWidget()
    qt = types.SimpleNamespace(mainWindow=lambda: main_window, Icon=lambda name: None, ColorSwatchButton=ColorSwatch)
    monkeypatch.setattr(hou, "qt", qt, raising=False)
    yield main_window
    main_window.deleteLater()


def write_script(folder: Path, relpath: str, header: str = "", body: str = "pass\n") -> Path:
    path = folder / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body, encoding="utf-8")
    return path
