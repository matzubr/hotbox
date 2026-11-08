"""Pane tabs under the cursor."""
from __future__ import annotations

import hou


def paneOfType(pane_type):
    """Pane tab of the type: the one under the cursor, else the first one in the desktop, else None"""
    cursor_panetab = hou.ui.paneTabUnderCursor()
    if cursor_panetab and cursor_panetab.type() == pane_type:
        return cursor_panetab
    return hou.ui.paneTabOfType(pane_type)


def networkPane():
    return paneOfType(hou.paneTabType.NetworkEditor)


def sceneViewer():
    return paneOfType(hou.paneTabType.SceneViewer)


def warn(message: str) -> None:
    hou.ui.setStatusMessage(message, severity=hou.severityType.Warning)
