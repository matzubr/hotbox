#label:Guides
#package:qLib
#group:Viewport
#textcolor:#b8e0ff
#hotkey:g
#icon:guides.svg

# Node guides (handles of lights, cameras, SOP guide geometry) in every viewport: on <-> off
import hou

shown = not getattr(hou.session, "hotbox_guides", True)
hou.session.hotbox_guides = shown
state = "on" if shown else "off"
hou.hscript(f"viewdisplay -g {state} *")
hou.ui.setStatusMessage(f"Guides: {state}")
