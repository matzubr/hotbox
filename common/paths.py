"""File parameters and path conversion."""
from __future__ import annotations

import os
import posixpath
import sys

import hou


def replacePrefix(path: str, root: str, variable: str, ignore_case: bool | None = None) -> str | None:
    """'D:\\Proj/geo' with root 'd:/proj' -> '$JOB/geo'. None when path is not inside root.

    Only the start of the path is replaced; slashes are normalized; case is ignored on Windows.
    """
    if ignore_case is None:
        ignore_case = sys.platform == "win32"
    path = path.replace("\\", "/")
    root = root.replace("\\", "/").rstrip("/")
    if not root:
        return None
    compare_path, compare_root = (path.casefold(), root.casefold()) if ignore_case else (path, root)
    if compare_path == compare_root or compare_path.startswith(compare_root + "/"):
        return variable + path[len(root):]
    return None


def convertPaths(variable: str = "$JOB") -> dict:
    """Rewrite file parameters of the selected nodes to start with the variable ($JOB, $FILM...)"""
    nodes = hou.selectedNodes()
    if not nodes:
        hou.ui.displayMessage("No node selected")
        return {}

    root = hou.text.expandString(variable)
    if not root or root == variable:
        hou.ui.displayMessage(f"{variable} is not set")
        return {}

    changed: dict[str, list[str]] = {}
    for node in nodes:
        for parm_name in fileParms(node):
            parm = node.parm(parm_name)
            raw = parm.rawValue()
            # Directory from the evaluated value, file name from the raw one (keeps $F4 etc.)
            directory = replacePrefix(posixpath.dirname(parm.eval().replace("\\", "/")), root, variable)
            if directory is None:
                continue
            new_value = posixpath.join(directory, posixpath.basename(raw.replace("\\", "/")))
            if new_value != raw:
                parm.set(new_value)
                changed.setdefault(node.name(), []).append(parm_name)

    if changed:
        lines = [f"Node: {name}\n" + "".join(f"\t- {p}\n" for p in parms) for name, parms in changed.items()]
        hou.ui.displayMessage("Paths changed in:\n" + "".join(lines))
    return changed


def _allParmTemplates(group_or_folder):
    for parm_template in group_or_folder.parmTemplates():
        yield parm_template
        if parm_template.type() == hou.parmTemplateType.Folder:
            yield from _allParmTemplates(parm_template)


def fileParms(node, include_hidden: bool = False) -> list[str]:
    """Names of the file reference parameters (visible ones by default), multiparm instances expanded"""
    names = [
        t.name()
        for t in _allParmTemplates(node.parmTemplateGroup())
        if t.type() == hou.parmTemplateType.String
        and t.stringType() == hou.stringParmType.FileReference
        and (include_hidden or not t.isHidden())
    ]
    result = [name for name in names if "#" not in name]
    for name in names:
        if "#" not in name:
            continue
        first = node.parm(name.replace("#", "1"))
        if not first:
            continue
        for i in range(1, first.parentMultiParm().eval() + 1):
            parm = node.parm(name.replace("#", str(i)))
            if parm:
                result.append(parm.name())
    return result


NOT_FILES = ("op:", "opdef:", "oplib:", "temp:", "stage:")


def isOutputParm(parm) -> bool:
    """Parameter a node writes to (ROP output, cache output): its file may not exist yet"""
    try:
        if parm.node().type().category() == hou.ropNodeTypeCategory():
            return True
        return parm.parmTemplate().tags().get("filechooser_mode") == "write"
    except hou.OperationFailed:
        return False


def sceneFileParms() -> list:
    """Every file parameter of the scene that reads a file: no outputs, no disabled ones, nothing inside locked HDAs"""
    result, seen = [], set()
    for parm, _ in hou.fileReferences():
        if parm is None or parm.path() in seen:
            continue
        seen.add(parm.path())
        node = parm.node()
        if node.isInsideLockedHDA() or parm.isDisabled() or isOutputParm(parm):
            continue
        result.append(parm)
    return result


def missingFiles() -> list[tuple]:
    """(parm, evaluated path) of the read files that don't exist; a sequence counts as found if any frame exists"""
    from . import frames

    missing = []
    for parm in sceneFileParms():
        path = parm.eval()
        if not path or path.startswith(NOT_FILES) or "://" in path or os.path.exists(path):
            continue
        if frames.sequenceFrames(parm):
            continue
        missing.append((parm, path))
    return missing


RELOAD_BUTTONS = ("reload", "reloadgeo", "reloadfile")


def reloadFileNodes() -> list:
    """Press the Reload button of every node that reads files (File, Alembic, File Cache, Sublayer...).
    Returns the reloaded nodes."""
    try:
        import _alembic_hom_extensions as alembic
        alembic.alembicClearArchiveCache()  # files rewritten outside: drop the cached archives first
    except (ImportError, AttributeError):
        pass
    reloaded, seen = [], set()
    for parm in sceneFileParms():
        node = parm.node()
        if node.path() in seen:
            continue
        seen.add(node.path())
        for name in RELOAD_BUTTONS:
            button = node.parm(name)
            if button is not None and button.parmTemplate().type() == hou.parmTemplateType.Button:
                button.pressButton()
                reloaded.append(node)
                break
    return reloaded
