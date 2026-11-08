#label:Save HIP
#textcolor:#6efb09

from pathlib import Path
import re
import hou

def main():
    job = hou.getenv("JOB")
    activity = hou.getenv("ACTIVITY")
    user = hou.getenv("CEREBRO_USER_NAME")
    
    shot = Path(job).stem
    
    name = f"{shot}_{activity}_v001.hip"
    userdir = Path(job,activity,"work",user)
    
    if not userdir.exists():
        hou.ui.displayMessage("No user dir found")
        return 0
    
    filepath = Path(userdir,"houdini",name)
    
    if not filepath.exists():
        hou.hipFile.save(filepath.as_posix())
    
    hires_folder = Path(job,"source","hires")
    
    hires_folders = [x for x in hires_folder.iterdir() if x.is_dir()]
    if len(hires_folders)==0:
        hou.ui.displayMessage("No hires")
        return 0
        
    hires_folder_source = sorted(hires_folders)[-1]
    source_folder = hires_folder / hires_folder_source
    
    pattern = r"\.\d+\." #find string like ".1001."
    frame_ranges=[int(re.search(pattern,x.name).group()[1:-1]) for x in source_folder.iterdir() if re.search(pattern,x.name)]
    hou.playbar.setFrameRange(min(frame_ranges),max(frame_ranges))
    hou.playbar.setRealTime(True)

main()