#label:Camera Import
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:w

import os
import sys
from importlib import reload

import hou

# Studio camera exchanger folder: set CAM_TOOLS_PATH in houdini.env (not stored in the repo)
CAM_TOOLS = os.environ.get("CAM_TOOLS_PATH", "")

if CAM_TOOLS and CAM_TOOLS not in sys.path:
    sys.path.append(CAM_TOOLS)
try:
    import cam_tools
except ImportError as e:
    hou.ui.displayMessage(f"Can't import cam_tools from {CAM_TOOLS}:\n{e}", severity=hou.severityType.Error)
else:
    reload(cam_tools)
    cam_tools.init_import("houdini")
