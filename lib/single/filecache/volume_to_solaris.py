#label:Volume to Solaris
#group:Solaris
#textcolor:#a8d8f0
#hotkey:l
#icon:volume.svg

# Volume LOP in /obj/lopnet1 reading the node's .vdb cache (prim /vol/<name>),
# sampled over the frames on disk (else the node's frame range)
import hou
from hotbox.common import solaris

solaris.importVolume(hou.selectedNodes()[0])
