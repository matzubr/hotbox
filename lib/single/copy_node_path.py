#label:Copy Node Path
#group:Copy
#textcolor:#c9b8ff
#icon:copy.svg

# Paths of the selected nodes, one per line (Object Merge Paste / Fetch read them back)
import hou

nodes = hou.selectedNodes()
if nodes:
    hou.ui.copyTextToClipboard("\n".join(node.path() for node in nodes))
    hou.ui.setStatusMessage(f"Copied: {', '.join(node.path() for node in nodes)}")
