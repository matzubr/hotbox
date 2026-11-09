#label:Object Merge Relative
#shiftlabel:Object Merge Absolute
#textcolor:#fff492
#buttoncolor:#1f1a12
#hotkey:1
#icon:SOP_object_merge

# Object Merge of every node copied to the clipboard; Shift+click: absolute paths
import hotbox
from hotbox.common import nodes

nodes.pasteMergeNodes("Sop", "object_merge", "objpath1", relative="shift" not in hotbox.modifiers(),
                      extra_parms={"xformtype": 1}, shape="chevron_up", copy_color=True)
