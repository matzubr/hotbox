#label:Sticky Note
#package:qLib
#group:Network
#textcolor:#ffd59e
#hotkey:n
#icon:sticky.svg

# A sticky note signed with the user and the date: at the cursor, or next to the selected node in its color
import hou
from hotbox.common import nodes

nodes.addStickyNote(hou.selectedNodes())
