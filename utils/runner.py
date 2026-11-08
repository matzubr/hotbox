"""Run a library script inside Houdini."""
from __future__ import annotations

import builtins
import traceback
from pathlib import Path

import hou


def runScript(path: Path, label: str = "") -> bool:
    """Execute a script file as if it was run directly. Returns True when it finished without errors.

    - clean namespace with __name__ == "__main__" (scripts don't see HotBox internals)
    - one undo step for everything the script did
    - sys.exit() in a script just stops it, errors are printed and shown in the status bar
      instead of escaping into the Qt event loop
    """
    path = Path(path)
    filepath = path.as_posix()
    scope = {"__name__": "__main__", "__file__": filepath, "__builtins__": builtins}
    try:
        code = compile(path.read_text(encoding="utf-8"), filepath, "exec")
        with hou.undos.group(f"HotBox: {label or path.stem}"):
            exec(code, scope)  # noqa: S102  running library scripts is the point
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001  any script error must not break the hotbox
        traceback.print_exc()
        status(f"HotBox: {path.name} failed: {e}", error=True)
        return False
    return True


def status(message: str, error: bool = False) -> None:
    try:
        severity = hou.severityType.Error if error else hou.severityType.Message
        hou.ui.setStatusMessage(message, severity=severity)
    except Exception:  # noqa: BLE001
        print(message)
