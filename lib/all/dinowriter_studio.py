#label:Flipbook Studio
#textcolor:#5bff77
#buttoncolor:#0d121b
#icon:app_dino_dance.svg
#link:None
#hotkey:f

import hou
from importlib import reload
from dinowriter import ui
reload(ui)
kwargs = {"pane":hou.ui.paneTabUnderCursor()}
ui.DinoWriter(kwargs)