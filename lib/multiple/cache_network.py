#label:Cache Network
#group:Cache
#textcolor:#8fffc1
#hotkey:f
#icon:size.svg

# A TOP or ROP network next to the selected cache nodes that writes them one after another
# (upstream caches first): TOP network = ROP Fetch per cache with Wait for All between; ROP network = Fetch per cache
# into a Merge, written by the network's "Write Checked, Node by Node" button, the caches checked under it (a toggle per
# cache; off bypasses its Fetch). A ROP's Render button goes frame by frame.
# A ROP network already made here can get the new caches instead of a new one.
# Each one runs the cache node's own ROP, so its path, version and frame range are used.
# The cache node types and where their ROP is: common/cachetypes.py
import hou
from hotbox.common import caches

caches.runCacheNetwork(hou.selectedNodes())
