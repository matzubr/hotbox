#label:To Solaris
#group:Solaris
#textcolor:#a8f0c6
#hotkey:l
#icon:sop-import.svg

# SOP Import of the null in /obj/lopnet1 (prims at /geo/<name>) and Render Geometry Settings after it
# with Karma velocity blur on those prims
import hou
from hotbox.common import solaris

solaris.importSops(hou.selectedNodes())
