#label:Fetch Relative
#textcolor:#fff492
#buttoncolor:#1f1a12
#hotkey:1

import hou


def getPane():
    cursor_panetab = hou.ui.paneTabUnderCursor()
    if cursor_panetab and cursor_panetab.type() == hou.paneTabType.NetworkEditor:
        return cursor_panetab
    return hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)


def main():
    network_panetab = getPane()
    if not network_panetab:
        print("No Network Editor found")
        return
    network_node = network_panetab.pwd()
    if network_node.childTypeCategory().name() != "Lop":
        hou.ui.setStatusMessage("Works in Lop networks only", severity=hou.severityType.Warning)
        return

    # Copied nodes are in the clipboard as space separated paths
    paths = [path for path in hou.ui.getTextFromClipboard().split() if hou.node(path)]
    if not paths:
        hou.ui.setStatusMessage("No node paths in the clipboard: copy nodes first", severity=hou.severityType.Warning)
        return

    for i, path in enumerate(paths):
        source = hou.node(path)
        node = network_node.createNode("fetch", f"MERGE_{source.name()}")
        node.setPosition(network_panetab.cursorPosition() + hou.Vector2(i * 3, 0) - hou.Vector2(0.5, 0))
        node.parm("loppath").set(node.relativePathTo(source))


main()
