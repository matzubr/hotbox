#label:Camera Bake Chop
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:1

import hou,sys

source_cam = hou.selectedNodes()

if len(source_cam) == 0:
    source_cam = hou.ui.selectNode()
    
else: 
    source_cam = source_cam[0].path()

if source_cam is None:
    sys.exit()

node = hou.node("/obj").createNode("cam", "RENDER_CAMERA")
node.setParmExpressions({"shutter": "ch('" + source_cam + "/shutter')", "focus": "ch('" + source_cam + "/focus')", "fstop": "ch('" + source_cam + "/fstop')"})


color_red = hou.Color((1, 0, 0))
node.setColor(color_red)

chopnet = node.createNode("chopnet")

chop_object = chopnet.createNode("object")
chop_object.setParms({"targetpath": source_cam, "compute": "transrot", "range": "full", "left": "slope", "right": "slope"})

chop_fetch = chopnet.createNode("fetch")
chop_fetch.setParms({"nodepath": source_cam, "path": "focal aperture", "range": "user", "units": "frames", "start": hou.playbar.frameRange()[0], "end": hou.playbar.frameRange()[1]})

chop_merge = chop_object.createOutputNode("merge")
chop_merge.setInput(1, chop_fetch, 0)

chop_export = chop_merge.createOutputNode("export")
chop_export.setParms({"nodepath": node.path(), "path": "t[xyz] r[xyz] focal aperture"})
chopnet.layoutChildren()
chop_export.setExportFlag(1)
chop_export.setCurrentFlag(1)
chop_export.cook()
