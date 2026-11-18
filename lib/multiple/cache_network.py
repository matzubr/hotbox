#label:Cache Network
#group:Cache
#textcolor:#8fffc1
#hotkey:f
#icon:size.svg

# A TOP or ROP network next to the selected cache nodes that writes them one after another
# (upstream caches first): TOP network = ROP Fetch per cache with Wait for All between; ROP network = Fetch per cache
# into a Merge, written by the network's "Write All, Node by Node" button (a ROP's Render button goes frame by frame).
# Each one runs the cache node's own ROP, so its path, version and frame range are used.
import hou
from hotbox.common import caches, panes

# Cache node types: type name without the version -> where its ROP is.
#   caches.AUTO  the first ROP inside the node (File Cache: its "render")
#   caches.SELF  the node is a ROP itself
#   "path"       a path inside the node, e.g. "render" or "subnet1/write"
CACHE_TYPES = {
    "filecache": caches.AUTO,
    "labs::filecache": caches.AUTO,
    "vellumio": caches.AUTO,
    "s_cache": "ropnet1/geo",  # studio cache HDA, any version (s_cache::11.0): the Geometry ROP in its ropnet
    "rop_geometry": caches.SELF,
    "rop_alembic": caches.SELF,
}


def main():
    selected = hou.selectedNodes()
    if not selected:
        return
    choice = hou.ui.displayMessage(f"Write {len(selected)} cache node(s) with:", buttons=("TOP network", "ROP network",
                                   "Cancel"), default_choice=0, close_choice=2, title="Cache Network")
    if choice == 2:
        return
    try:
        network, created, skipped = caches.buildCacheNetwork(selected, ("top", "rop")[choice], CACHE_TYPES)
    except ValueError as e:
        panes.warn(str(e))
        return
    message = f"{network.path()}: {len(created)} cache(s)"
    if choice == 1:
        message += f", write with '{caches.WRITE_LABEL}' on it"
    if skipped:
        message += f", skipped (no ROP found, see CACHE_TYPES): {', '.join(n.name() for n in skipped)}"
    hou.ui.setStatusMessage(message, severity=hou.severityType.Warning if skipped else hou.severityType.Message)


main()
