#label:Make Space
#package:LV-Tools
#group:Network
#textcolor:#ffd59e
#hotkey:s
#icon:make-space.svg

# Several nodes: spread them apart vertically. One node: everything below it moves down two grid rows
import hou
from hotbox.common import layout, panes

layout.makeSpace(hou.selectedNodes(), panes.networkPane())
