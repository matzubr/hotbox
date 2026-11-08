#label:Start LOP Script
#textcolor:#d453ff
#hotkey:e
import hou

network = hou.node("/stage")
network.createNode("sublayer","IMPORT_FILE")