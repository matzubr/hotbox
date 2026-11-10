#label:SOP Import
#group:Fetch
#textcolor:#a8f0c6
#buttoncolor:#1f1a12
#hotkey:3
#icon:sop-import.svg

# SOP Import of every node copied to the clipboard (Ctrl+C on SOP nodes or geo objects), prims at /geo/<name>
from hotbox.common import nodes

nodes.pasteMergeNodes("Lop", "sopimport", "soppath", relative=False, extra_parms={"pathprefix": lambda s: f"/geo/{s.name()}"},
                      shape="chevron_up", copy_color=True, prefix="IMPORT_")
