#label:Save HIP
#textcolor:#6efb09

import re
from pathlib import Path

import hou

FRAME_PATTERN = re.compile(r"\.(\d+)\.")  # ".1001."


def main():
    job, activity, user = hou.getenv("JOB"), hou.getenv("ACTIVITY"), hou.getenv("CEREBRO_USER_NAME")
    if not (job and activity and user):
        hou.ui.displayMessage("$JOB, $ACTIVITY and $CEREBRO_USER_NAME must be set")
        return

    shot = Path(job).stem
    userdir = Path(job, activity, "work", user)
    if not userdir.exists():
        hou.ui.displayMessage(f"No user dir found:\n{userdir.as_posix()}")
        return

    filepath = Path(userdir, "houdini", f"{shot}_{activity}_v001.hip")
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        hou.hipFile.save(filepath.as_posix())

    hires_folder = Path(job, "source", "hires")
    hires_folders = sorted(x for x in hires_folder.iterdir() if x.is_dir()) if hires_folder.is_dir() else []
    if not hires_folders:
        hou.ui.displayMessage(f"No hires in {hires_folder.as_posix()}")
        return

    frames = [int(m.group(1)) for x in hires_folders[-1].iterdir() if (m := FRAME_PATTERN.search(x.name))]
    if not frames:
        hou.ui.displayMessage(f"No frames in {hires_folders[-1].as_posix()}")
        return
    hou.playbar.setFrameRange(min(frames), max(frames))
    hou.playbar.setRealTime(True)


main()
