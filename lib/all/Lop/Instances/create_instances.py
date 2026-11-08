#label:Start LOP Script
#textcolor:#d453ff
#hotkey:f
import hou

network = hou.node("/stage")
network.createNode("sublayer","IMPORT_FILE")