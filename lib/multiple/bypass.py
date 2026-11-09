#label:Bypass
#package:qLib
#group:Network
#textcolor:#ffd59e
#hotkey:x
#icon:bypass.svg

# Bypass the selected nodes; when all of them are bypassed already: turn bypass off
import hou
from hotbox.common import nodes

state = nodes.toggleBypass(hou.selectedNodes())
if state is not None:
    hou.ui.setStatusMessage("Bypassed" if state else "Bypass off")
