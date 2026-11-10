#label:Time-Dep. Badges
#package:qLib
#group:Viewport
#textcolor:#b8e0ff
#hotkey:d
#icon:clock.svg

# Time-dependent badges of the nodes in every Network Editor: normal <-> large
import hou

editors = [tab for tab in hou.ui.paneTabs() if isinstance(tab, hou.NetworkEditor)]
if editors:
    badge = "normal" if editors[0].getPref("badgetimedep") == "large" else "large"
    for editor in editors:
        editor.setPref("badgetimedep", badge)
    hou.ui.setStatusMessage(f"Time-dependent badges: {badge}")
