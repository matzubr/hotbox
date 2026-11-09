#label:Transfer Transform
#package:LV-Tools
#textcolor:#ffb0b0
#hotkey:e
#icon:transfer.svg

# Two objects: the second takes the world transform of the first, the first is reset and parented to the second
# (nothing moves in the viewport: the transform now lives on the parent)
import hou
from hotbox.common import panes

nodes = hou.selectedNodes()
if len(nodes) != 2:
    panes.warn("Select two objects: the one with the transform, then the new parent")
else:
    source, target = nodes
    target.setWorldTransform(source.worldTransform())
    source.parmTuple("t").set((0, 0, 0))
    source.parmTuple("r").set((0, 0, 0))
    source.parmTuple("s").set((1, 1, 1))
    source.setInput(0, target)
    hou.ui.setStatusMessage(f"{source.name()}: transform moved to {target.name()}")
