#label:Save Incremental
#package:Aelib
#group:Hip
#textcolor:#6efb09
#hotkey:s
#icon:save-plus.svg

import hou
from hotbox.common import hipfile, panes


def main():
    """Save the scene as the next version: shot_v012.hip -> shot_v013.hip (shot.hip -> shot_v001.hip)"""
    if hou.hipFile.isNewFile():
        panes.warn("The scene was never saved: save it once with a name first")
        return
    path = hipfile.nextFreePath(hou.hipFile.path())
    hou.hipFile.save(path.as_posix())
    hou.ui.setStatusMessage(f"Saved {path.name}", severity=hou.severityType.Message)


main()
