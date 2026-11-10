#label:Material Library
#group:Materials
#textcolor:#f5a3d6
#hotkey:l
#icon:material.svg

import hou
from hotbox.common import panes


def selectedPrims() -> list[str]:
    """Prims selected in the Solaris viewport"""
    viewer = panes.sceneViewer()
    try:
        return list(viewer.currentSceneGraphSelection()) if viewer is not None else []
    except (AttributeError, hou.OperationFailed):
        return []


def main():
    """Material Library + Assign Material after the selected LOP node (or the display node),
    the assign gets the prims selected in the viewport"""
    pane = panes.networkPane()
    network = pane.pwd() if pane is not None else None
    if network is None or network.childTypeCategory() != hou.lopNodeTypeCategory():
        panes.warn("Works in LOP networks only")
        return
    selected = hou.selectedNodes()
    source = selected[-1] if selected else network.displayNode()

    if source is not None:
        library = source.createOutputNode("materiallibrary", "materials")
    else:
        library = network.createNode("materiallibrary", "materials")
        library.setPosition(pane.cursorPosition())
    assign = library.createOutputNode("assignmaterial", "assign_materials")
    prims = selectedPrims()
    if prims:
        assign.parm("primpattern1").set(" ".join(prims))
    assign.setDisplayFlag(True)
    library.setCurrent(True, clear_all_selected=True)


main()
