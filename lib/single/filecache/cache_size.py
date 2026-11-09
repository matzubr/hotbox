#label:Cache Size
#package:LV-Tools
#group:Cache
#textcolor:#8fffc1
#hotkey:z
#icon:size.svg

# Size of the cache on disk (every frame of the sequence) in the node comment
import os

import hou
from hotbox.common import panes, paths

node = hou.selectedNodes()[0]
parm = paths.mainFileParm(node)
files = paths.cacheFiles(parm) if parm is not None else []
if not files:
    panes.warn("Nothing on disk yet")
else:
    size = paths.formatSize(sum(os.path.getsize(f) for f in files))
    frames = f", {len(files)} files" if len(files) > 1 else ""
    node.setComment(f"{size}{frames}")
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    hou.ui.setStatusMessage(f"{node.name()}: {size}{frames}")
