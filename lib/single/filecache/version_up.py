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
# File Cache: "version"; studio cache HDAs (s_cache) may name it otherwise: a number parameter labeled Version
version = node.parm("version") or next(
    (p for p in node.parms() if p.parmTemplate().label().strip().casefold() == "version"
     and p.parmTemplate().type() == hou.parmTemplateType.Int), None)
if version is None:
    panes.warn(f"{node.name()} has no Version parameter")
else:
    if node.parm("enableversion") is not None:
        node.parm("enableversion").set(1)
    version.set(version.eval() + 1)
    hou.ui.setStatusMessage(f"{node.name()}: version {version.eval()}")
