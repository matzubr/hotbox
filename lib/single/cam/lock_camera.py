#label:Lock Camera
#package:Aelib
#group:View
#textcolor:#d6f5a3
#hotkey:p
#icon:lock.svg

# Look through the camera / light with "lock camera to view" on: tumbling the viewport moves it. Again: unlocks
import hou
from hotbox.common import panes


def main():
    viewer = panes.sceneViewer()
    if viewer is None:
        panes.warn("No Scene Viewer")
        return
    node = hou.selectedNodes()[0]
    viewport = viewer.curViewport()
    current = viewport.camera()
    if current is None or current.path() != node.path():
        viewport.setCamera(node)
        viewport.lockCameraToView(True)
    else:
        viewport.lockCameraToView(not viewport.isCameraLockedToView())
    state = "locked to" if viewport.isCameraLockedToView() else "unlocked from"
    hou.ui.setStatusMessage(f"{node.name()} {state} the view")


main()
