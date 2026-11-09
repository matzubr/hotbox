"""Run a library script inside Houdini."""
from __future__ import annotations

import builtins
import traceback
from dataclasses import dataclass
from pathlib import Path

import hou

_modifiers: frozenset[str] = frozenset()


def modifiers() -> frozenset[str]:
    """Keys held when the running script's button was clicked: {'shift', 'ctrl', 'alt'} (ctrl is Cmd on macOS).
    Scripts read it as hotbox.modifiers()."""
    return _modifiers


@dataclass
class ScriptError:
    path: Path  # the file that ran
    label: str
    message: str  # "NameError: name 'x' is not defined"
    traceback: str
    line: int | None  # line in the script file where it failed (1-based, header included)


def errorLine(tb, filepath: str) -> int | None:
    """Last line of the traceback that is in the script itself (not in hou or a helper module)"""
    line = None
    for frame in traceback.extract_tb(tb):
        if frame.filename == filepath:
            line = frame.lineno
    return line


def scriptTraceback(e: BaseException) -> str:
    """Traceback without the runner's own frame: it starts in the script"""
    tb = e.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(e), e, tb))


def runScript(path: Path, label: str = "", modifiers=(), on_error=None) -> bool:
    """Execute a script file as if it was run directly. Returns True when it finished without errors.

    - clean namespace with __name__ == "__main__" (scripts don't see HotBox internals)
    - one undo step for everything the script did
    - sys.exit() in a script just stops it, errors are printed and shown in the status bar
      instead of escaping into the Qt event loop; on_error(ScriptError) is called too (the error window)
    - modifiers: keys held on the click, hotbox.modifiers() while the script runs
    """
    global _modifiers
    path = Path(path)
    filepath = path.as_posix()
    scope = {"__name__": "__main__", "__file__": filepath, "__builtins__": builtins}
    _modifiers = frozenset(modifiers)
    try:
        code = compile(path.read_text(encoding="utf-8"), filepath, "exec")
        with hou.undos.group(f"HotBox: {label or path.stem}"):
            exec(code, scope)  # noqa: S102  running library scripts is the point
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001  any script error must not break the hotbox
        traceback.print_exc()
        status(f"HotBox: {path.name} failed: {e}", error=True)
        if on_error is not None:
            line = e.lineno if isinstance(e, SyntaxError) and e.filename == filepath else \
                errorLine(e.__traceback__, filepath)
            error = ScriptError(path, label or path.stem, f"{type(e).__name__}: {e}", scriptTraceback(e), line)
            try:
                on_error(error)
            except Exception:  # noqa: BLE001  the error window must not hide the original error
                traceback.print_exc()
        return False
    finally:
        _modifiers = frozenset()
    return True


def status(message: str, error: bool = False) -> None:
    try:
        severity = hou.severityType.Error if error else hou.severityType.Message
        hou.ui.setStatusMessage(message, severity=severity)
    except Exception:  # noqa: BLE001
        print(message)
