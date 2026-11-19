#label:Cache Report
#group:Scene
#textcolor:#8fffc1
#icon:list.svg

# Every cache node of the scene (types: common/cachetypes.py) with its version, frame range, frames and size on
# disk; picked rows: select, open the folder, Cache Network, Clean Old Versions
from hotbox.utils import cachereport

cachereport.showCacheReport()
