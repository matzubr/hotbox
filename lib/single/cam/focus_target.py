#label:Focus Target
#package:BeeHou
#group:Camera
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:f
#icon:focus.svg

# A null at the focus distance in front of the camera; the camera's Focus Distance follows it
import hou
from hotbox.common import nodes as node_utils
from hotbox.common import panes


def main():
    camera = hou.selectedNodes()[0]
    focus = camera.parm("focus")
    if focus is None:
        panes.warn("The camera has no Focus Distance parameter")
        return
    network = camera.parent()
    null = network.createNode("null", f"{camera.name()}_focus")
    null.setWorldTransform(hou.hmath.buildTranslate(0, 0, -focus.eval()) * camera.worldTransform())
    if null.parm("controltype") is not None:
        null.parm("controltype").set(1)  # circles: easy to grab in the viewport
    null.setColor(hou.Color(1.0, 0.8, 0.2))
    wanted = camera.position() + hou.Vector2(2, 0)
    null.setPosition(node_utils.freePosition(network, wanted, null.size(), ignore=[null]))
    focus.setExpression(f'vlength(vtorigin("{camera.path()}", "{null.path()}"))', hou.exprLanguage.Hscript)
    null.setCurrent(True, clear_all_selected=True)


main()
