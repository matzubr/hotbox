#label:Recover Crash
#package:qLib
#group:Hip
#textcolor:#ff8f8f
#hotkey:r
#icon:recover.svg

import datetime

import hou
from hotbox.common import hipfile


def main():
    """Pick a crash file (Houdini's temp folder) or a backup of this scene ($HIP/backup) and open it"""
    hip = None if hou.hipFile.isNewFile() else hou.hipFile.path()
    files = hipfile.recoveryFiles(hip, hou.getenv("HOUDINI_TEMP_DIR"))
    if not files:
        hou.ui.setStatusMessage("No crash files or backups found", severity=hou.severityType.Message)
        return
    choices = [f"{datetime.datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}   {p.name}   ({p.parent})"
               for p in files]
    picked = hou.ui.selectFromList(choices, exclusive=True, title="Recover crash", column_header="Saved   file",
                                   message="Newest first. The picked file opens (you'll be asked to save this one).",
                                   width=900, height=400)
    if not picked:
        return
    path = files[picked[0]]
    hou.hipFile.load(path.as_posix())
    hou.ui.setStatusMessage(f"Opened {path.name}: save it under the shot name (File > Save As)",
                            severity=hou.severityType.Warning)


main()
