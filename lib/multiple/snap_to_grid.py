#label:Snap to Grid
#group:Network
#textcolor:#ffd59e
#hotkey:a
#icon:snap-grid.svg

# Selected nodes and dots onto the Network Editor grid (its X/Y step), each on the nearest free point:
# no node ends up on top of another one
import hou
from hotbox.common import layout, panes

items = layout.snappable(hou.selectedItems())
moved = layout.snapToGrid(items, panes.networkPane())
hou.ui.setStatusMessage(f"Snapped {moved} of {len(items)} to the grid")
