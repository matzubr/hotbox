#label:From Picked
#group:USD Collections
#textcolor:#86efac
#hotkey:c
#icon:collection.svg

# The prims picked in the viewer become a collection (a Collection LOP under the displayed one):
# then %name picks them in any prim field
import hou
from hotbox.common import panes, usd

node = usd.displayNode()
picked = usd.pickedPaths()
if node is None or not picked:
    panes.warn("Pick prims in the Scene Viewer (LOPs) first")
else:
    default = picked[0].rstrip("/").rsplit("/", 1)[-1] if len(picked) == 1 else "picked"
    button, text = hou.ui.readInput(f"Collection of {len(picked)} prims", buttons=("OK", "Cancel"),
                                    default_choice=0, close_choice=1, initial_contents=default,
                                    title="Picked to Collection")
    if button == 0:
        name = usd.collectionName(text)
        new, missing = usd.addCollection(node, name, " ".join(picked))
        if missing:
            hou.ui.copyTextToClipboard(" ".join(picked))
            panes.warn(f"{new.name()}: set {', '.join(missing)} by hand (the prims are in the clipboard)")
        else:
            hou.ui.setStatusMessage(f"%{name}: {len(picked)} prims")
