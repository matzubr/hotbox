#label:Multi Rename
#group:Network
#hotkey:h
#icon:rename.svg

# Rename the selected nodes at once with a live preview: find / replace (text or regex), a name pattern
# ({name}, {type}, # numbers: ### = 001; numbered in selection, top to bottom, left to right or name order),
# prefix, suffix, case. Clashing names are shown in red; one undo. The fields stay for the next rename.
import hou
from hotbox.utils import renamer

renamer.showRename(hou.selectedNodes())
