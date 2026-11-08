#label:Camera Bake Keyframes
#textcolor:#ffffff
#buttoncolor:#16182b
#hotkey:2

import hou
import toolutils


def bake_selected(baking_node, chop_export_node):
    bake_attrs = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'focal', 'aperture', 'shutter', 'focus', 'fstop', 'aspect']
    bake_data = {}
    for cur_attr in bake_attrs:
        cur_attr_data = []

        for cur_frame in range(int(hou.playbar.playbackRange()[0]), int(hou.playbar.playbackRange()[1] + 1)):
            cur_time = hou.frameToTime(float(cur_frame))
            cur_attr_data.append(hou.Keyframe(baking_node.parm(cur_attr).evalAtTime(cur_time), cur_time))
        bake_data[cur_attr] = cur_attr_data

    chop_export_node.setExportFlag(0)

    for attr in bake_data:
        baking_node.parm(attr).deleteAllKeyframes()
        baking_node.parm(attr).setKeyframes(bake_data[attr])


def main():
    selected_nodes = hou.selectedNodes()
    if not selected_nodes or selected_nodes[0].type().name() != 'cam':
        hou.ui.displayMessage('Select a "Camera" node', severity=hou.severityType.Error)
        return
    bake_camera(selected_nodes[0].path())


def bake_camera(source_cam):
    node_cam_baked = hou.node("/obj").createNode("cam", "RENDER_CAMERA_baked")
    node_cam_baked.setParmExpressions({"shutter": f"ch('{source_cam}/shutter')",
                                       "focus": f"ch('{source_cam}/focus')",
                                       "fstop": f"ch('{source_cam}/fstop')",
                                       "aspect": f"ch('{source_cam}/aspect')"})

    node_cam_baked.setColor(hou.Color((1, 0.1, 0.1)))
    node_cam_baked.moveToGoodPosition()

    chopnet = node_cam_baked.createNode("chopnet")

    chop_object = chopnet.createNode("object")
    chop_object.setParms({"targetpath": source_cam,
                          "compute": "transrot",
                          "range": "full",
                          "left": "slope",
                          "right": "slope"})

    chop_fetch = chopnet.createNode("fetch")
    chop_fetch.setParms({"nodepath": source_cam,
                         "path": "focal aperture",
                         "range": "user",
                         "units": "frames",
                         "start": hou.playbar.playbackRange()[0],
                         "end": hou.playbar.playbackRange()[1]})

    chop_merge = chop_object.createOutputNode("merge")
    chop_merge.setInput(1, chop_fetch, 0)

    chop_export = chop_merge.createOutputNode("export")
    chop_export.setParms({"nodepath": node_cam_baked.path(),
                          "path": "t[xyz] r[xyz] focal aperture"})

    chopnet.layoutChildren()
    chop_export.setExportFlag(1)
    chop_export.setCurrentFlag(1)
    chop_export.cook()

    bake_selected(node_cam_baked, chop_export)
    chopnet.destroy()

    scene_view = toolutils.sceneViewer()
    viewport = scene_view.curViewport()
    viewport.setCamera(node_cam_baked)

    hou.ui.displayMessage('Selected camera succesfully baked to %s' % node_cam_baked.name())


main()
