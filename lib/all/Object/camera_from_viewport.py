#label:Camera from View
#group:Camera
#textcolor:#d6f5a3
#hotkey:c
#icon:camera.svg

import hou
from hotbox.common import panes

# Copied from the camera the viewport looks through, if any
CAMERA_PARMS = ("resx", "resy", "aspect", "focal", "aperture", "near", "far")


def main():
    """New camera at the current view of the viewport; the viewport then looks through it"""
    viewer = panes.sceneViewer()
    if viewer is None:
        panes.warn("No Scene Viewer")
        return
    viewport = viewer.curViewport()

    pane = panes.networkPane()
    network = pane.pwd() if pane is not None else None
    if network is None or network.childTypeCategory() != hou.objNodeTypeCategory():
        network, pane = hou.node("/obj"), None

    camera = network.createNode("cam", "cam_view")
    current = viewport.camera()
    if current is not None and current.type().name() == "cam":
        for name in CAMERA_PARMS:
            if current.parm(name) is not None:
                camera.parm(name).set(current.parm(name).eval())
    viewport.saveViewToCamera(camera)

    if pane is not None:
        camera.setPosition(pane.cursorPosition())
    else:
        camera.moveToGoodPosition()
    camera.setCurrent(True, clear_all_selected=True)
    viewport.setCamera(camera)


main()
