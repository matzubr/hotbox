#label:Select Bypassed
#package:qLib
#group:Select
#textcolor:#ffe08f
#hotkey:b
#icon:select.svg

from hotbox.common import nodes

nodes.selectInNetwork(lambda node: node.isBypassed(), "bypassed")
