#label:Jump to Material
#group:Materials
#textcolor:#f5a3d6
#hotkey:q
#icon:jump.svg

# The material of the prim picked in the viewer: selects the node that makes it (inside a Material Library:
# the material node itself) and frames it in the network
import hou
from hotbox.common import nodes, panes, usd

node = usd.displayNode()
picked = usd.pickedPaths()
if node is None or not picked:
    panes.warn("Pick a prim in the Scene Viewer (LOPs) first")
else:
    stage = node.stage()
    prim = stage.GetPrimAtPath(picked[0])
    material = usd.boundMaterial(prim) if prim and prim.IsValid() else None
    if material is None:
        panes.warn(f"{picked[0]} has no material")
    else:
        source = usd.authoringNode(node, material)
        if source is None:
            panes.warn(f"{material}: no node above {node.name()} makes it")
        else:
            inside = source.node(material.rsplit("/", 1)[-1]) if source.isNetwork() else None
            target = inside or source
            nodes.showInNetwork(target)
            hou.ui.setStatusMessage(f"{material} ← {target.path()}")
