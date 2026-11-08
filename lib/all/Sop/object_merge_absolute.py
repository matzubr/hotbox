#label:Object Merge Absolute
#group:Object Merge
#textcolor:#ffb492
#buttoncolor:#1f1a12
#hotkey:2
#icon:SOP_object_merge

from hotbox.common import nodes

nodes.pasteMergeNodes("Sop", "object_merge", "objpath1", relative=False, extra_parms={"xformtype": 1})
