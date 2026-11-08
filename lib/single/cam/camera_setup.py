#label:Camera Setup
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:3

import hou,sys
from pathlib import Path

source_cam = hou.selectedNodes()

if len(source_cam) == 0:
    source_cam = hou.ui.selectNode()
else: 
    source_cam = source_cam[0]

source_cam.setSelectableInViewport(False)
source_cam.setDisplayFlag(False)
source_cam.setColor(hou.Color(1,0.1,0.1))
source_cam.setName("RENDER_CAMERA",unique_name=True)

back_plates_folder = "$JOB/layout/publish/back_plate"
back_plates_folder_raw = hou.text.expandString(back_plates_folder)
back_plates_versions = sorted([x for x in Path(back_plates_folder_raw).iterdir() if x.name.startswith("v")])
back_plates_last_version = back_plates_versions[-1].name

film = hou.getenv("ABBR")
episode = hou.getenv("SHOT").split("\\")[-3]
shot = hou.getenv("SHOTNAME")

shot_filename = f"{film}_{episode}_{shot}_ACEScg.v001.$F4.exr"
back_plate_filepath = Path(back_plates_folder,back_plates_last_version,shot_filename).as_posix()

source_cam.parm("vm_background").set(back_plate_filepath)