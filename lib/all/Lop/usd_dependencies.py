#label:Stage Files
#group:Solaris
#textcolor:#5eead4
#hotkey:u
#icon:layers.svg

# USD dependencies: every file the shown stage reads: layers, references, payloads, textures and other asset paths.
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
    hou.ui.displayMessage(summary, title="Stage Files", details=text, details_expanded=True,
                          severity=hou.severityType.Warning if missing else hou.severityType.Message)
