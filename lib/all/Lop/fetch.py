#label:Fetch Relative
#shiftlabel:Fetch Absolute
#group:Fetch
#textcolor:#fff492
#buttoncolor:#1f1a12
#hotkey:1
#icon:LOP_fetch

# Fetch of every LOP node copied to the clipboard; Shift+click: absolute paths
import hotbox
from hotbox.common import nodes

nodes.pasteMergeNodes("Lop", "fetch", "loppath", relative="shift" not in hotbox.modifiers(), shape="chevron_up",
                      copy_color=True)
