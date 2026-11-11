#label:From Pattern
#group:USD Collections
#textcolor:#86efac
#hotkey:x
#icon:pattern.svg

# A collection from a prim pattern (/geo/*/RENDER_*, %type:Mesh, ...): shows how many prims it picks on the
# displayed stage before the Collection LOP is made. Picked prims fill the pattern in to start from
import hou
from hotbox.common import panes, usd

PREVIEW_LINES = 15

node = usd.displayNode()
if node is None:
    panes.warn("No LOP network under the cursor")
else:
    pattern, name = " ".join(usd.pickedPaths()) or "/", "collection"
    while True:
        button, (name, pattern) = hou.ui.readMultiInput(
            "Collection from a prim pattern", ("Name", "Pattern"), buttons=("Check", "Cancel"), default_choice=0,
            close_choice=1, initial_contents=(name, pattern), title="Collection from Pattern")
        if button != 0 or not pattern.strip():
            break
        paths = usd.expandPattern(node, pattern)
        shown = "\n".join(paths[:PREVIEW_LINES]) + (f"\n… and {len(paths) - PREVIEW_LINES} more"
                                                    if len(paths) > PREVIEW_LINES else "")
        choice = hou.ui.displayMessage(f"{pattern}\npicks {len(paths)} prims", buttons=("Create", "Edit", "Cancel"),
                                       default_choice=0 if paths else 1, close_choice=2, details=shown or None,
                                       details_expanded=bool(paths), title="Collection from Pattern")
        if choice == 0:
            new, missing = usd.addCollection(node, usd.collectionName(name), pattern)
            if missing:
                panes.warn(f"{new.name()}: set {', '.join(missing)} by hand")
            break
        if choice == 2:
            break
