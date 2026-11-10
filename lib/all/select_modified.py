#label:Select Modified
#package:qLib
#group:Select
#textcolor:#ffe08f
#hotkey:m
#icon:select.svg

# Nothing selected: the node changed last. Again (with the selection): adds the next older one, and so on
import hou
from hotbox.common import nodes

nodes.selectModified(hou.selectedNodes())
