"""Creating and placing nodes."""
from __future__ import annotations

import hou

from . import panes

INPUT_LIMIT = 4


def clipboardNodes() -> list:
    """Nodes whose paths are in the clipboard (Ctrl+C on nodes copies their paths, space separated)"""
    nodes = [hou.node(path) for path in hou.ui.getTextFromClipboard().split()]
    return [node for node in nodes if node is not None]


def createAttribNode(node_type: str, color: tuple[float, float, float]):
    """Node below the selected SOPs with them as inputs (up to 4), display/render flags on it"""
    nodes = hou.selectedNodes()
    if not nodes or any(n.parent().childTypeCategory() != hou.sopNodeTypeCategory() for n in nodes):
        panes.warn("Select SOP nodes")
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


def styleLikeSource(node, source, shape: str | None = None) -> None:
    """Node shape (Network Editor shapes: 'chevron_up', 'circle'...) and the color of the source node"""
    if shape:
        node.setUserData("nodeshape", shape)
    node.setColor(source.color())


def pasteMergeNodes(category: str, node_type: str, path_parm: str, relative: bool, extra_parms=None,
                    shape: str | None = None, copy_color: bool = False) -> list:
    """Object Merge / Fetch for each node in the clipboard, at the cursor of the Network Editor.

    category: network type the tool works in ("Sop", "Lop"); extra_parms: {name: value} set on each node;
    shape / copy_color: node shape of the created nodes, color taken from the copied node.
    """
    pane = panes.networkPane()
    if pane is None:
        panes.warn("No Network Editor")
        return []
    network = pane.pwd()
    if network.childTypeCategory().name() != category:
        panes.warn(f"Works in {category} networks only")
        return []
    sources = clipboardNodes()
    if not sources:
        panes.warn("No node paths in the clipboard: copy nodes first")
        return []

    created = []
    for i, source in enumerate(sources):
        node = network.createNode(node_type, f"MERGE_{source.name()}")
        node.setPosition(pane.cursorPosition() + hou.Vector2(i * 3, 0) - hou.Vector2(0.5, 0))
        node.parm(path_parm).set(node.relativePathTo(source) if relative else source.path())
        for name, value in (extra_parms or {}).items():
            node.parm(name).set(value)
        if copy_color:
            styleLikeSource(node, source, shape)
        elif shape:
            node.setUserData("nodeshape", shape)
        created.append(node)
    return created
