#label:Version Up
#package:AutoCacheOut
#group:Cache
#textcolor:#8fffc1
#hotkey:u
#icon:version-up.svg

# Next cache version (versioning gets turned on): the next write doesn't overwrite the last one
import hou
from hotbox.common import panes

node = hou.selectedNodes()[0]
version = node.parm("version")
if version is None:
    panes.warn(f"{node.name()} has no Version parameter")
else:
    if node.parm("enableversion") is not None:
        node.parm("enableversion").set(1)
    version.set(version.eval() + 1)
    hou.ui.setStatusMessage(f"{node.name()}: version {version.eval()}")
