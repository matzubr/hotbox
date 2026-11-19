#label:Version Up
#package:AutoCacheOut
#group:Cache
#textcolor:#8fffc1
#hotkey:u
#icon:version-up.svg

# Next cache version (versioning gets turned on): the next write doesn't overwrite the last one
import hou
from hotbox.common import cachetypes, panes

node = hou.selectedNodes()[0]
version = cachetypes.versionUp(node)  # the version parameter: common/cachetypes.py
if version is None:
    panes.warn(f"{node.name()} has no Version parameter")
else:
    hou.ui.setStatusMessage(f"{node.name()}: version {version}")
