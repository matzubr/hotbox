#label:USD Files
#group:Solaris
#textcolor:#d8b4fe
#hotkey:u
#icon:file-missing.svg

# Every file the shown stage reads: layers, references, payloads, textures and other asset paths.
# The missing ones first (Missing Files sees only node parameters, not what is inside the USD)
import hou
from hotbox.common import panes, usd

node = usd.displayNode()
if node is None:
    panes.warn("No LOP network under the cursor")
else:
    found = usd.dependencies(node.stage())
    text, missing = usd.dependencyReport(found)
    summary = f"{len(found)} files, {missing} missing" if missing else f"{len(found)} files, none missing"
    hou.ui.displayMessage(summary, title="USD Files", details=text, details_expanded=True,
                          severity=hou.severityType.Warning if missing else hou.severityType.Message)
