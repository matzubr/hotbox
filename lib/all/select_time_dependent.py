#label:Select Time-Dependent
#package:qLib
#group:Select
#textcolor:#ffe08f
#hotkey:a
#icon:select.svg

from hotbox.common import nodes

nodes.selectInNetwork(lambda node: node.isTimeDependent(), "time-dependent")
