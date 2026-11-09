#label:Load Wedges
#package:LV-Tools
#textcolor:#ffa0e6
#hotkey:l
#icon:SOP_file

# File nodes for the files this ROP Geometry Output wrote: one per wedge (`@wedgeindex` in the path), the ones on disk
# (none yet: as many as the Wedge Count above), and a Switch to flip through them. Next to the TOP network.
import hou
from hotbox.common import panes, wedge

try:
    files = wedge.loadWedges(hou.selectedNodes()[0])
    hou.ui.setStatusMessage(f"{len(files)} file node(s) in {files[0].parent().path()}")
except ValueError as e:
    panes.warn(str(e))
