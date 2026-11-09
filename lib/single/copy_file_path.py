#label:Copy File Path
#group:Copy
#textcolor:#c9b8ff
#icon:copy-file.svg

# Files of the selected nodes with the variables expanded ($HIP, $JOB...), one per line
import hou
from hotbox.common import panes, paths

files = []
for node in hou.selectedNodes():
    for name in paths.fileParms(node):
        value = node.parm(name).eval()
        if value and value not in files:
            files.append(value)
if files:
    hou.ui.copyTextToClipboard("\n".join(files))
    hou.ui.setStatusMessage(f"Copied: {', '.join(files)}")
else:
    panes.warn("No file parameters on the selected nodes")
