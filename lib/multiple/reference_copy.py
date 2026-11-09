#label:Reference Copy
#package:qLib
#group:Copy
#textcolor:#c9b8ff
#hotkey:c
#icon:copy-ref.svg

# Copies next to the selected nodes: every parameter references the original, inputs wired the same
import hou
from hotbox.common import nodes

selected = hou.selectedNodes()
if selected:
    copies = nodes.referenceCopy(selected)
    copies[0].setCurrent(True, clear_all_selected=True)
    for copy in copies[1:]:
        copy.setSelected(True)
