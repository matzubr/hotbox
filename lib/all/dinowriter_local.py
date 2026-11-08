#label:Flipbook Local
#textcolor:#88ff9c
#buttoncolor:#0c1424
#icon:app_dino_dance.svg
#link:None
#hotkey:g

import hou
from importlib import reload
from dinowriter_dev import ui
reload(ui)
kwargs = {"pane":hou.ui.paneTabUnderCursor()}
ui.DinoWriter(kwargs)