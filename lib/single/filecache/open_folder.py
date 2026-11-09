#label:Open Folder
#package:qLib
#group:Cache
#textcolor:#8fffc1
#hotkey:o
#icon:folder.svg

# The folder of the node's file (cache, output or the file it reads) in Finder / Explorer;
# not written yet: the nearest folder that exists
import hou
from hotbox.common import hipfile, panes, paths

node = hou.selectedNodes()[0]
parm = paths.mainFileParm(node)
if parm is None:
    panes.warn(f"{node.name()} has no file")
else:
    folder = hipfile.openInFileBrowser(parm.evalAsString())
    hou.ui.setStatusMessage(f"Opened {folder}" if folder else "Folder not found")
