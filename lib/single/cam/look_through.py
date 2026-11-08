#label:Look Through
#group:View
#textcolor:#d6f5a3
#hotkey:l
#icon:eye.svg

import hou
from hotbox.common import panes


def main():
    """The viewport looks through the selected camera / light; again on the same one: back to perspective"""
    viewer = panes.sceneViewer()
    nodes = hou.selectedNodes()
    if viewer is None or not nodes:
        panes.warn("No Scene Viewer")
        return
    node = nodes[0]
    viewport = viewer.curViewport()
    current = viewport.camera()
    if current is not None and current.path() == node.path():
        viewport.useDefaultCamera()
        hou.ui.setStatusMessage("Viewport: perspective")
    else:
        viewport.setCamera(node)
        hou.ui.setStatusMessage(f"Viewport: through {node.name()}")


main()
