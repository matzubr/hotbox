#label:Material Report
#group:Materials
#textcolor:#f5a3d6
#hotkey:w
#icon:list.svg

# Which materials the geometry of the shown stage uses (and how many prims each);
# the prims without a material get picked in the viewer
import hou
from hotbox.common import panes, usd

node = usd.displayNode()
if node is None:
    panes.warn("No LOP network under the cursor")
else:
    pairs = [(str(prim.GetPath()), usd.boundMaterial(prim)) for prim in usd.geometryPrims(node.stage())]
    used, unbound = usd.materialUse(pairs)
    if unbound:
        usd.pick(unbound)
    summary = f"{len(pairs)} geometry prims, {len(used)} materials, {len(unbound)} without a material"
    hou.ui.displayMessage(summary + (" (picked in the viewer)" if unbound else ""), title="Material Report",
                          details=usd.materialReport(used, unbound), details_expanded=True)
