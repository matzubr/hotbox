#label:Camera Setup
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:3
#icon:OBJ_camera

import re
from pathlib import Path

import hou

BACK_PLATES_FOLDER = "$JOB/layout/publish/back_plate"


def main():
    selected = hou.selectedNodes()
    if selected:
        source_cam = selected[0]
    else:
        path = hou.ui.selectNode(node_type_filter=hou.nodeTypeFilter.ObjCamera)
        source_cam = hou.node(path) if path else None
    if source_cam is None:
        return

    film, shot_path, shot = hou.getenv("ABBR"), hou.getenv("SHOT"), hou.getenv("SHOTNAME")
    if not (film and shot_path and shot):
        hou.ui.displayMessage("$ABBR, $SHOT and $SHOTNAME must be set", severity=hou.severityType.Error)
        return
    shot_parts = [part for part in re.split(r"[\\/]", shot_path) if part]
    if len(shot_parts) < 3:
        hou.ui.displayMessage(f"Can't find the episode in $SHOT: {shot_path}", severity=hou.severityType.Error)
        return
    episode = shot_parts[-3]

    back_plates_folder = Path(hou.text.expandString(BACK_PLATES_FOLDER))
    versions = sorted(x.name for x in back_plates_folder.iterdir() if x.is_dir() and x.name.startswith("v")) \
        if back_plates_folder.is_dir() else []
    if not versions:
        hou.ui.displayMessage(f"No back plate versions in {back_plates_folder.as_posix()}",
                              severity=hou.severityType.Error)
        return

    source_cam.setSelectableInViewport(False)
    source_cam.setDisplayFlag(False)
    source_cam.setColor(hou.Color(1, 0.1, 0.1))
    source_cam.setName("RENDER_CAMERA", unique_name=True)

    shot_filename = f"{film}_{episode}_{shot}_ACEScg.v001.$F4.exr"
    back_plate_filepath = Path(BACK_PLATES_FOLDER, versions[-1], shot_filename).as_posix()
    source_cam.parm("vm_background").set(back_plate_filepath)


main()
