#label:Set Variant
#group:Solaris
#textcolor:#d8b4fe
#hotkey:v
#icon:variant.svg

# Variants of the prim picked in the viewer (and of its parents): the chosen one goes into a new Set Variant LOP
import hou
from hotbox.common import panes, usd

node = usd.displayNode()
picked = usd.pickedPaths()
if node is None or not picked:
    panes.warn("Pick a prim with variants in the Scene Viewer (LOPs) first")
else:
    choices = usd.variantChoices(node.stage().GetPrimAtPath(picked[0]))
    if not choices:
        panes.warn(f"{picked[0]} and its parents have no variant sets")
    else:
        rows = [f"{path}   {set_name} = {variant}" for path, set_name, variant in choices]
        chosen = hou.ui.selectFromList(rows, exclusive=True, title="Set Variant", column_header="prim   set = variant")
        if chosen:
            new, missing = usd.setVariant(node, *choices[chosen[0]])
            if missing:
                panes.warn(f"{new.name()}: set {', '.join(missing)} by hand")
