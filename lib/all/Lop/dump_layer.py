#label:Show as USDA
#group:Solaris
#textcolor:#5eead4
#hotkey:y
#icon:file-code.svg

# What the displayed LOP writes (its active layer) or the whole flattened stage, as a .usda text file in your
# editor: quick to read what really ends up in the USD
import hou
from hotbox.common import panes, usd

node = usd.displayNode()
if node is None:
    panes.warn("No LOP network under the cursor")
else:
    choice = hou.ui.displayMessage(f"Show {node.name()} as USDA:", buttons=("Its Layer", "Whole Stage", "Cancel"),
                                   default_choice=0, close_choice=2, title="Show as USDA")
    if choice == 0:
        path = usd.dumpPath(node, "layer")
        path.write_text(node.activeLayer().ExportToString(), encoding="utf-8")
        usd.openFile(path)
    elif choice == 1:
        path = usd.dumpPath(node, "stage")
        node.stage().Flatten().Export(path.as_posix())
        usd.openFile(path)
