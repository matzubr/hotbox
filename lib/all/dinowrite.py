#label:Flipbook
#group:Output
#textcolor:#5bff77
#buttoncolor:#0d121b
#icon:app_dino_dance.svg
#hotkey:f

# DinoWrite: https://github.com/matzubr/DinoWrite (folder DinoWrite next to hotbox in python3.11libs)
import hou

try:
    import DinoWrite
except ImportError:
    hou.ui.displayMessage("DinoWrite is not installed: put the DinoWrite folder into python3.11libs",
                          severity=hou.severityType.Error)
else:
    DinoWrite.show({"pane": hou.ui.paneTabUnderCursor()})
