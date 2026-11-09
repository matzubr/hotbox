#label:Select Same Type
#package:qLib
#group:Select
#textcolor:#ffe08f
#hotkey:t
#icon:select.svg

# Every node of the network with the type of a selected node
import hou
from hotbox.common import nodes

types = {node.type().name() for node in hou.selectedNodes()}
nodes.selectInNetwork(lambda node: node.type().name() in types, "of the same type")
