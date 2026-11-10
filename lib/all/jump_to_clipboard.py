#label:Jump to Path
#package:qLib
#group:Network
#textcolor:#c9b8ff
#hotkey:j
#icon:jump.svg

# The pair of Copy Node Path: the node (or the node of a parameter path) in the clipboard is shown and selected
import hou
from hotbox.common import nodes, panes

node = nodes.nodeFromText(hou.ui.getTextFromClipboard())
if node is None:
    panes.warn("No node path in the clipboard")
else:
    nodes.showInNetwork(node)
