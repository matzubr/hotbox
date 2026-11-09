#label:Background
#package:qLib
#group:Viewport
#textcolor:#b8e0ff
#hotkey:k
#icon:background.svg

import hou

SCHEMES = [getattr(hou.viewportColorScheme, name) for name in ("Dark", "DarkGrey", "Grey", "Light")
           if hasattr(hou.viewportColorScheme, name)]


def main():
    """Next viewport color scheme (dark, dark grey, grey, light) in every viewport"""
    viewports = [v for tab in hou.ui.paneTabs() if isinstance(tab, hou.SceneViewer) for v in tab.viewports()]
    if not viewports:
        return
    current = viewports[0].settings().colorScheme()
    scheme = SCHEMES[(SCHEMES.index(current) + 1) % len(SCHEMES)] if current in SCHEMES else SCHEMES[0]
    for viewport in viewports:
        viewport.settings().setColorScheme(scheme)
    hou.ui.setStatusMessage(f"Viewport background: {scheme.name()}")


main()
