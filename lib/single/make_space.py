#label:Make Space Below
#package:LV-Tools
#group:Network
#textcolor:#ffd59e
#hotkey:s
#icon:make-space.svg

# Everything below the selected node moves down two grid rows: room to insert nodes after it
# (several nodes: Explode Nodes spreads them apart)
import hou
from hotbox.common import layout, panes

layout.makeSpace(hou.selectedNodes()[0], panes.networkPane())
