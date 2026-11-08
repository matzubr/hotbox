#label:Camera Export
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:e

import sys
from importlib import reload

import hou

CAM_TOOLS = "//studio/tools/py_libs/camera_exchanger"

if CAM_TOOLS not in sys.path:
    sys.path.append(CAM_TOOLS)
try:
    import cam_tools
except ImportError as e:
    hou.ui.displayMessage(f"Can't import cam_tools from {CAM_TOOLS}:\n{e}", severity=hou.severityType.Error)
else:
    reload(cam_tools)
    cam_tools.init_export("houdini")
