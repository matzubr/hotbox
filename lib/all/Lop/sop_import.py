#label:SOP Import
#group:Fetch
#textcolor:#a8f0c6
#buttoncolor:#1f1a12
#hotkey:3
#icon:sop-import.svg

# SOP Import of every node copied to the clipboard (Ctrl+C on SOP nodes or geo objects), prims at /$OS (the import node name),
# each followed by Render Geometry Settings with Karma geometry + instance velocity blur (Set or Create) on those prims
from hotbox.common import nodes, solaris

created = nodes.pasteMergeNodes("Lop", "sopimport", "soppath", relative=False,
                                extra_parms={"pathprefix": "/$OS"},
                                shape="chevron_up", copy_color=True, prefix="IMPORT_")
for sop_import in created:
    solaris.addRenderGeometrySettings(sop_import)
