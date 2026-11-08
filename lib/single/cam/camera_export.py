#label:Camera Export
#textcolor:#ffffff
#buttoncolor:#22253b
#hotkey:e

import sys

if sys.version_info.major == 3:
    from importlib import reload

sys.path.append('//studio/tools/py_libs/camera_exchanger')
try:
    import cam_tools
except Exception as e:
    print('Error importing cam_tools!')

reload(cam_tools)

cam_tools.init_export('houdini')