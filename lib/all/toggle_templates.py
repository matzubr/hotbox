#label:Templates
#package:qLib
#group:Viewport
#textcolor:#b8e0ff
#hotkey:t
#icon:templates.svg

# Templated geometry (and selectable templates) in every viewport: on <-> off
import hou

shown = not getattr(hou.session, "hotbox_templates", True)
hou.session.hotbox_templates = shown
state = "on" if shown else "off"
hou.hscript(f"viewdisplay -T {state} -i {state} *")
hou.ui.setStatusMessage(f"Templates: {state}")
