"""Shared code of the library scripts (lib/single and lib/multiple call the same tools).

In a script:
    from hotbox import lib_common
    lib_common.createNull()

Updated on disk, it is reloaded on the next hotbox.show() like the rest of the tool.
"""
from __future__ import annotations

import posixpath
import sys

import hou

INPUT_LIMIT = 4


# --- Attribute VOP / Wrangle -------------------------------------------------------------------------------------


def createAttribNode(node_type: str, color: tuple[float, float, float]):
    """Node below the selected SOPs with them as inputs (up to 4), display/render flags on it"""
    nodes = hou.selectedNodes()
    if not nodes or any(n.parent().childTypeCategory() != hou.sopNodeTypeCategory() for n in nodes):
        hou.ui.setStatusMessage("Select SOP nodes", severity=hou.severityType.Warning)
        return None

    node = nodes[0].parent().createNode(node_type)
    inputs = nodes[:INPUT_LIMIT]
    for i, source in enumerate(inputs):
        node.setInput(i, source)

    positions = [n.position() for n in inputs]
    x = sum(p[0] for p in positions) / len(positions)
    y = min(p[1] for p in positions)
    node.setPosition(hou.Vector2(x, y - 1))
    node.setColor(hou.Color(*color))
    node.setDisplayFlag(True)
    node.setRenderFlag(True)
    node.setCurrent(True, clear_all_selected=True)
    return node


# --- Null -------------------------------------------------------------------------------------------------------


def createNull():
    """OUT_<name> null after each selected node; for one node the name is asked"""
    nodes = hou.selectedNodes()
    if not nodes:
        return []

    if len(nodes) == 1:
        button, name = hou.ui.readInput("Name", buttons=("OK", "Cancel"), default_choice=0, close_choice=1)
        if button != 0:
            return []
        names = [name.strip() or nodes[0].name()]
    else:
        names = [node.name() for node in nodes]
    return [node.createOutputNode("null", f"OUT_{name}") for node, name in zip(nodes, names)]


# --- Render node ------------------------------------------------------------------------------------------------


def createRenderNodes():
    """RENDER_<name> geo object next to the current one, merging each selected node into it"""
    nodes = hou.selectedNodes()
    if not nodes:
        return []

    network = nodes[0].parent()  # the geo object the nodes are in
    rest_pos = network.position() - hou.Vector2(0, 1)
    created = []
    for i, node in enumerate(nodes):
        name = node.name()
        # Sibling, not createOutputNode: a wired geo object would inherit the source object's transform
        geo = network.parent().createNode("geo", f"RENDER_{name}")
        geo.setSelectableInViewport(False)
        geo.setColor(hou.Color(0.1, 0.5, 0.1))
        geo.setPosition(hou.Vector2(rest_pos[0] + i * 1.5, rest_pos[1] - i * 1))

        merge = geo.createNode("object_merge", f"IMPORT_{name}")
        merge.parm("objpath1").set(node.path())
        merge.parm("xformtype").set(1)  # Into This Object
        created.append(geo)
    return created


# --- Convert file paths to $JOB / $FILM -------------------------------------------------------------------------


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


def convertPaths(variable: str = "$JOB"):
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


def fileParms(node) -> list[str]:
    """Names of the visible file reference parameters, multiparm instances expanded"""
    names = [
        t.name()
        for t in _allParmTemplates(node.parmTemplateGroup())
        if t.type() == hou.parmTemplateType.String
        and t.stringType() == hou.stringParmType.FileReference
        and not t.isHidden()
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
