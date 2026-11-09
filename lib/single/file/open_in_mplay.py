#label:Open in MPlay
#package:qLib
#group:Cache
#textcolor:#8fffc1
#hotkey:p
#icon:play.svg

# The image (sequence) of the node in MPlay
import hou
from hotbox.common import mplay, panes, paths

node = hou.selectedNodes()[0]
parm = paths.mainFileParm(node)
if parm is None or not paths.isImageFile(parm.evalAsString()):
    panes.warn(f"{node.name()} doesn't read images")
else:
    mplay.openInMPlay(parm)
