#label:Clean Old Versions
#group:Cache
#textcolor:#8fffc1
#hotkey:d
#icon:prune.svg

# Delete the old versions of the selected caches from disk: all but the newest N (asked) and the current one,
# after a confirmation listing them. Only each cache's own files go (another cache in the same version folder stays).
import hou
from hotbox.common import versions

versions.cleanOldVersions(hou.selectedNodes())
