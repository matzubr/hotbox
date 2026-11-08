"""Houdini side: panes, selection and the hotbox context."""
from __future__ import annotations

from dataclasses import dataclass

import hou

PANE_TYPES = {
    "network": "NetworkEditor",
    "viewer": "SceneViewer",
}


def getPane(pane: str = "network"):
    """Pane tab of the given kind: the one under the cursor, else the first one in the desktop, else None"""
    pane_type = getattr(hou.paneTabType, PANE_TYPES[pane])
    cursor_panetab = hou.ui.paneTabUnderCursor()
    if cursor_panetab and cursor_panetab.type() == pane_type:
        return cursor_panetab
    return hou.ui.paneTabOfType(pane_type)


def nodeIcon(node):
    """Qt icon of a node type, None when the type has no icon"""
    if node is None:
        return None
    try:
        return hou.qt.Icon(node.type().icon())
    except hou.OperationFailed:
        return None


@dataclass
class Context:
    mode: str  # lib folder: all | multiple | single
    context: str  # sub folder to show next to the root scripts
    title: str  # central button text
    icon: object = None


def detectContext() -> Context:
    """What the hotbox shows:
    - nothing selected: lib/all, column of the current network type (Sop, Lop, Object...)
    - several nodes:    lib/multiple, column of their network type
    - one node:         lib/single, column of the node type (cam, null...)
    """
    nodes = hou.selectedNodes()
    network_pane = getPane("network")
    network = network_pane.pwd() if network_pane else None

    if len(nodes) == 1:
        node = nodes[0]
        node_type = node.type().nameComponents()[2]
        return Context("single", node_type, node_type, nodeIcon(node))
    if len(nodes) > 1:
        parent = nodes[0].parent()
        return Context("multiple", parent.childTypeCategory().name(), "Multiple", nodeIcon(parent))
    if network is None:
        return Context("all", "", "No Network", None)
    category = network.childTypeCategory().name()
    return Context("all", category, category, nodeIcon(network))
