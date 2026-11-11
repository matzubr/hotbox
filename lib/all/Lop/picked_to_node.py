#label:Picked Prims to…
#group:Solaris
#textcolor:#5eead4
#hotkey:z
#icon:prim-pick.svg

# The prims picked in the viewer go into the Primitives field of a new node under the displayed one:
# Prune, Configure Primitive, Edit Properties, Edit (transform) or Collection
import hou
from hotbox.common import panes, usd

NODES = [("Prune", "prune"), ("Configure Primitive", "configureprimitive"), ("Edit Properties", "editproperties"),
         ("Edit", "edit"), ("Collection", "collection")]

node = usd.displayNode()
picked = usd.pickedPaths()
if node is None or not picked:
    panes.warn("Pick prims in the Scene Viewer (LOPs) first")
else:
    chosen = hou.ui.selectFromList([label for label, _ in NODES], exclusive=True, title=f"{len(picked)} prims to",
                                   column_header="New node")
    if chosen:
        new = usd.appendNode(node, NODES[chosen[0]][1])
        if not usd.setPrims(new, picked):
            panes.warn(f"{new.name()}: no Primitives field, paste the prims by hand")
            hou.ui.copyTextToClipboard(" ".join(picked))
