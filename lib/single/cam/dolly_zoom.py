#label:Dolly Zoom
#package:qLib
#group:Camera
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:d
#icon:dolly.svg

# Vertigo: a new focal length, the camera moves along its view so that what is at the focus distance
# keeps its size in frame
import hou
from hotbox.common import panes


def main():
    camera = hou.selectedNodes()[0]
    focal, focus = camera.parm("focal"), camera.parm("focus")
    if focal is None or focus is None:
        panes.warn("The camera has no Focal Length / Focus Distance")
        return
    button, text = hou.ui.readInput(f"New focal length (now {focal.eval():g})", buttons=("OK", "Cancel"),
                                    default_choice=0, close_choice=1, initial_contents=f"{focal.eval() * 2:g}")
    if button != 0:
        return
    try:
        new_focal = float(text)
    except ValueError:
        panes.warn(f"Not a number: {text}")
        return
    distance = focus.eval()
    new_distance = distance * new_focal / focal.eval()
    camera.setWorldTransform(hou.hmath.buildTranslate(0, 0, new_distance - distance) * camera.worldTransform())
    focal.set(new_focal)
    if not focus.keyframes():  # driven focus (Focus Target, keys) is left alone
        focus.set(new_distance)
    hou.ui.setStatusMessage(f"Focal {new_focal:g}, the camera moved {new_distance - distance:+.3g} along its view")


main()
