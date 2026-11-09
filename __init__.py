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

__version__ = "2.1.0"

_PACKAGE_DIR = Path(__file__).resolve().parent
_loaded_at = time.time()


def reload_modules():
    """Forget every loaded hotbox module and import the package again: changed modules, modules added since
    Houdini started, and this file too. (Reloading one by one from a fixed list missed new modules: they kept
    the old code and the old classes they imported.)"""
    prefix = __name__ + "."
    for name in [name for name in sys.modules if name.startswith(prefix)]:
        del sys.modules[name]
    importlib.invalidate_caches()
    importlib.reload(sys.modules[__name__])  # new __init__ code, _loaded_at is now


def _filesChangedSinceLoad() -> bool:
    tool_files = [f for folder in ("", "utils", "common") for f in _PACKAGE_DIR.joinpath(folder).glob("*.py")]
    return max((f.stat().st_mtime for f in tool_files), default=0) > _loaded_at


def manager(reload=False):
    """Open the Script Manager on its own (shelf tool 'HotBox Scripts')"""
    if reload or _filesChangedSinceLoad():
        reload_modules()
    import hou

    from .main import LIB_DIR
    from .utils import scripts
    from .utils.manager import ScriptManager

    return ScriptManager(lib_folder=scripts.libRoots(LIB_DIR, hou.getenv(scripts.PATH_ENV)))


def show(reload=False):
    """Open the hotbox under the mouse"""
    if reload or _filesChangedSinceLoad():
        reload_modules()
    from .main import HotBox

    return HotBox()
