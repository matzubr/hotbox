#label:Last Alembic Track
#textcolor:#a0ceff

from pathlib import Path
import re
import hou
from pprint import pprint as pp

def main():
    job = hou.getenv("JOB")
    
    publish_folder = Path(job,"track","publish")
    if not publish_folder.exists():
        print(f"No folder found:\n{publish_folder.as_posix()}")
        return
    
    track_folders = [x for x in publish_folder.iterdir() if re.search(r"v\d+",x.name)]
    
    if len(track_folders)==0:
        hou.ui.displayMessage("no track folder found")
        return 0
        
    track_folder = Path(publish_folder,track_folders[-1])
    alembics = [x for x in track_folder.iterdir() if x.suffix in [".abc"]]
    
    if len(alembics)==0:
        hou.ui.displayMessage("no alembics found")
        return 0
    
    alembic_file = alembics[0]
    network_panetab = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    network = network_panetab.pwd()
    
    null = network.createNode("null","scale")
    null.parm("scale").set(0.01)
    null.setDisplayFlag(False)
    null.setSelectableInViewport(False)
    null.setPosition(network_panetab.cursorPosition())
    null.setColor(hou.Color(0.1, 0.1, 0.1))
    null.setSelected(True, clear_all_selected=True, show_asset_if_selected=False)
    
    alembic = null.createOutputNode("alembicarchive",alembic_file.stem)
    alembic_filepath = alembic_file.as_posix().replace(job,"$JOB")
    alembic.parm("fileName").set(alembic_filepath)
    alembic.setSelectableInViewport(False)
    alembic.parm("buildHierarchy").pressButton()
    alembic.setSelected(True, clear_all_selected=False, show_asset_if_selected=False)
    
main()