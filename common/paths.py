"""File parameters and path conversion."""
from __future__ import annotations

import os
import posixpath
import re
import sys

import hou

from . import cachewriter
from .cachetypes import CACHE_TYPES, typeKey


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
            if hasExpression(parm):
                continue  # computed (a cache HDA builds its path): rewriting would replace the expression
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


def _fileTemplateNames(node, include_hidden: bool) -> list[str]:
    """Names of the file reference parm templates of the node ('file#' for multiparms)"""
    return [
        t.name()
        for t in _allParmTemplates(node.parmTemplateGroup())
        if t.type() == hou.parmTemplateType.String
        and t.stringType() == hou.stringParmType.FileReference
        and (include_hidden or not t.isHidden())
    ]


def _expandMultiparms(node, names: list[str]) -> list[str]:
    """'file#' -> 'file1', 'file2'... as many as the node has"""
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


# Cache HDAs whose path is not a file reference parameter (built from parts, a plain string...), from
# cachetypes.CACHE_TYPES: type key -> the names of its path parameters; empty: every string parameter whose value
# looks like a cache file (CACHE_SUFFIXES)
CACHE_PATH_TYPES: dict[str, tuple[str, ...]] = {k: t.paths for k, t in CACHE_TYPES.items() if t.paths is not None}
CACHE_SUFFIXES = (".bgeo.sc", ".bgeo", ".bgeo.gz", ".bgeo.lzma", ".geo", ".vdb", ".abc", ".usd", ".usdc", ".usda",
                  ".usdz", ".sim", ".simdata", ".obj", ".fbx", ".ply", ".bhclassic", ".hclassic", ".rs", ".ass")


def looksLikeCacheFile(path: str) -> bool:
    return path.lower().endswith(CACHE_SUFFIXES)


def _cachePathParms(node, include_hidden: bool) -> list[str]:
    """Path parameters of a CACHE_PATH_TYPES node: the listed names, else guessed from the values"""
    try:
        names = CACHE_PATH_TYPES.get(typeKey(node.type()))
    except (AttributeError, TypeError, ValueError, hou.OperationFailed):
        return []
    if names is None:
        return []
    if names:
        return [name for name in names if node.parm(name) is not None]
    found = []
    for parm in node.parms():
        template = parm.parmTemplate()
        if template.type() != hou.parmTemplateType.String or (template.isHidden() and not include_hidden):
            continue
        try:
            value = parm.evalAsString()
        except hou.OperationFailed:
            continue
        if looksLikeCacheFile(value) and not value.startswith(NOT_FILES):
            found.append(parm.name())
    return found


def fileParms(node, include_hidden: bool = False) -> list[str]:
    """Names of the file reference parameters (visible ones by default), multiparm instances expanded;
    for CACHE_PATH_TYPES nodes also their path parameters"""
    names = _expandMultiparms(node, _fileTemplateNames(node, include_hidden))
    return list(dict.fromkeys(names + _cachePathParms(node, include_hidden)))


def hasExpression(parm) -> bool:
    try:
        parm.expression()
    except hou.OperationFailed:
        return False
    return True


NOT_FILES = ("op:", "opdef:", "oplib:", "temp:", "stage:")


def isOutputParm(parm) -> bool:
    """Parameter a node writes to (ROP output, cache output): its file may not exist yet"""
    try:
        if parm.node().type().category() == hou.ropNodeTypeCategory():
            return True
        return parm.parmTemplate().tags().get("filechooser_mode") == "write"
    except hou.OperationFailed:
        return False


def walkNodes(root=None):
    """Every node under root (default: the whole scene), depth first.
    Locked HDAs are not entered: their insides belong to the asset and are often huge."""
    stack = [root or hou.node("/")]
    while stack:
        node = stack.pop()
        yield node
        if node is not root and node.isLockedHDA():
            continue
        stack.extend(reversed(node.children()))


def sceneFileParms(root=None) -> list:
    """Every file parameter of the scene that reads a file: no outputs, no disabled ones, nothing inside locked HDAs.

    Walks the nodes itself instead of hou.fileReferences(), which can crash Houdini on very large scenes.
    The file parm templates are looked up once per node type (per node only when it has spare parameters).
    """
    by_type: dict[str, list[str]] = {}
    result = []
    for node in walkNodes(root):
        if node.spareParms():
            names = _fileTemplateNames(node, include_hidden=False)
        else:
            key = node.type().nameWithCategory()
            if key not in by_type:
                by_type[key] = _fileTemplateNames(node, include_hidden=False)
            names = by_type[key]
        if not names:
            continue
        for name in _expandMultiparms(node, names):
            parm = node.parm(name)
            if parm is not None and not parm.isDisabled() and not isOutputParm(parm):
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
# Cache nodes found by type, not by a file parameter (their path is an output, hidden or built from parts), from
# cachetypes.CACHE_TYPES: type key -> their reload button
RELOAD_TYPES = {k: t.reload for k, t in CACHE_TYPES.items() if t.reload}


def typedReloadNodes(types=None) -> list[tuple]:
    """[(node, reload button name)] of every node of a RELOAD_TYPES type, any version"""
    types = RELOAD_TYPES if types is None else types
    found = []
    for category in hou.nodeTypeCategories().values():
        for node_type in category.nodeTypes().values():
            name = types.get(typeKey(node_type))
            if name:
                found += [(node, name) for node in node_type.instances()]
    return found


def _press(node, name: str) -> bool:
    button = node.parm(name)
    if button is None or button.parmTemplate().type() != hou.parmTemplateType.Button:
        return False
    button.pressButton()
    return True


def reloadFileNodes() -> list:
    """Press the Reload button of every node that reads files (File, Alembic, File Cache, Sublayer...) and of the
    RELOAD_TYPES nodes. Returns the reloaded nodes."""
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
        if any(_press(node, name) for name in RELOAD_BUTTONS):
            reloaded.append(node)
    done = {node.path() for node in reloaded}
    for node, name in typedReloadNodes():
        if node.path() not in done and _press(node, name):
            done.add(node.path())
            reloaded.append(node)
    return reloaded


# --- the file of one node -----------------------------------------------------------------------------------------

MAIN_FILE_PARMS = ("sopoutput", "file", "filename", "fileName", "lopoutput", "copoutput", "picture", "vm_picture")
IMAGE_SUFFIXES = (".exr", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".tga", ".pic", ".rat", ".hdr", ".dpx", ".cin",
                  ".bmp", ".sgi", ".rgb")


def mainFileParm(node):
    """The parameter with the node's file: the cache / output / read path (the first one that is set)"""
    names = list(MAIN_FILE_PARMS) + fileParms(node, include_hidden=True)
    for name in dict.fromkeys(names):
        parm = node.parm(name)
        if parm is None:
            continue
        try:
            value = parm.evalAsString()
        except hou.OperationFailed:
            continue
        if value and not value.startswith(NOT_FILES):
            return parm
    return None


def cacheFiles(parm) -> list[str]:
    """Files on disk of the parameter: every frame of a sequence, or the one file"""
    from . import frames

    pattern = frames.sequencePattern(parm)
    if pattern is None:
        path = parm.evalAsString()
        return [path] if os.path.isfile(path) else []
    folder, prefix, suffix = pattern
    regex = re.compile(re.escape(prefix) + r"-?\d+" + re.escape(suffix) + "$")
    try:
        names = sorted(os.listdir(folder or "."))
    except OSError:
        return []
    return [os.path.join(folder, name) for name in names if regex.match(name)]


formatSize = cachewriter.formatSize  # 1536 -> '1.5 KB'


def isImageFile(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_SUFFIXES
