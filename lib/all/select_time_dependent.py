#label:Select Animated
#package:qLib
#group:Select
#textcolor:#ffe08f
#hotkey:a
#icon:select.svg

# Time-dependent nodes of the network: keyframes, $F / $T expressions, simulations and what reads them
from hotbox.common import nodes

nodes.selectInNetwork(lambda node: node.isTimeDependent(), "time-dependent")
