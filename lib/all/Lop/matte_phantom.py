#label:Matte & Phantom
#group:Solaris
#textcolor:#5eead4
#hotkey:h
#icon:matte.svg

# Under the displayed LOP: Assign Material -> Prune -> Render Geometry Settings with Karma Holdout Mode = Matte
# -> Render Geometry Settings with Render Visibility = Phantom (not seen by the camera, still in reflections,
# shadows and GI). Each control 'Set or Create'; fill in the prim patterns
import hou
from hotbox.common import panes, solaris, usd

node = usd.displayNode()
if node is None:
    panes.warn("No LOP network under the cursor")
else:
    created, missing = solaris.holdoutChain(node)
    if missing:
        panes.warn("Set by hand: " + ", ".join(missing))
    else:
        hou.ui.setStatusMessage(f"{' -> '.join(n.name() for n in created)}: fill in the prim patterns")
