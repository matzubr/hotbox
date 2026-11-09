#label:Copy Node Path
#shiftlabel:Copy File Path
#textcolor:#c9b8ff
#icon:copy.svg

# Paths of the selected nodes, one per line (Object Merge / Fetch read them back).
# Shift+click: the files of their file parameters, variables expanded ($HIP, $JOB...)
import hotbox
import hou
from hotbox.common import panes, paths


def main():
    nodes = hou.selectedNodes()
    if "shift" not in hotbox.modifiers():
        values = [node.path() for node in nodes]
    else:
        values = []
        for node in nodes:
            for name in paths.fileParms(node):
                value = node.parm(name).eval()
                if value and value not in values:
                    values.append(value)
        if not values:
            panes.warn("No file parameters on the selected nodes")
            return
    if values:
        hou.ui.copyTextToClipboard("\n".join(values))
        hou.ui.setStatusMessage(f"Copied: {', '.join(values)}")


main()
