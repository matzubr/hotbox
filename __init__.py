"""HotBox - popup launcher for your Houdini Python scripts.

Hotkey / shelf tool:
    import hotbox
    hotbox.show()

Code updated on disk (git pull, new copy) is reloaded on the next show(), no Houdini restart needed.
Scripts in lib/ are read from disk every time anyway.
"""
import importlib
import sys
import time
from pathlib import Path

__version__ = "2.0.0"

_PACKAGE_DIR = Path(__file__).resolve().parent
_loaded_at = time.time()

# Dependency order: modules are reloaded top to bottom
_SUBMODULES = (
    "utils.qt",
    "utils.scripts",
    "utils.settings",
    "utils.runner",
    "utils.utility",
    "utils.theme",
    "utils.widgets",
    "utils.frameless",
    "utils.packages",
    "utils.manager",
    "common.panes",
    "common.nodes",
    "common.paths",
    "common.frames",
    "main",
)


def reload_modules():
    global _loaded_at
    for name in _SUBMODULES:
        module = sys.modules.get(f"{__name__}.{name}")
        if module is not None:
            importlib.reload(module)
    _loaded_at = time.time()


def _filesChangedSinceLoad() -> bool:
    tool_files = [f for folder in ("", "utils", "common") for f in _PACKAGE_DIR.joinpath(folder).glob("*.py")]
    return max((f.stat().st_mtime for f in tool_files), default=0) > _loaded_at


def show(reload=False):
    """Open the hotbox under the mouse"""
    if reload or _filesChangedSinceLoad():
        reload_modules()
    from .main import HotBox

    return HotBox()
