#label:Open HIP Folder
#package:Aelib
#group:Hip
#textcolor:#9ad0ff
#hotkey:o
#icon:folder.svg

import hou
from hotbox.common import hipfile, panes

folder = hipfile.openInFileBrowser(hou.getenv("HIP") or "")
if folder is None:
    panes.warn("$HIP folder not found")
