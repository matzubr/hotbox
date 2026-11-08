#label:Reload Caches
#group:Scene
#textcolor:#8fffc1
#icon:reload.svg

# Reload of every node that reads files: caches rewritten by a farm or another scene show up
import hou
from hotbox.common import paths

reloaded = paths.reloadFileNodes()
hou.ui.setStatusMessage(f"Reloaded {len(reloaded)} nodes", severity=hou.severityType.Message)
