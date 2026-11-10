#label:Object Merge Relative
#group:Object Merge
#textcolor:#fff492
#buttoncolor:#1f1a12
#hotkey:1
#icon:object-merge.svg

from hotbox.common import nodes

nodes.pasteMergeNodes("Sop", "object_merge", "objpath1", relative=True, extra_parms={"xformtype": 1},
                      shape="chevron_up", copy_color=True)
