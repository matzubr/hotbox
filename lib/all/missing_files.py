#label:Missing Files
#group:Scene
#hotkey:i
#textcolor:#ff8f8f
#icon:file-missing.svg

import hou
from hotbox.common import panes, paths


def main():
    """Files the scene reads but that don't exist; picked ones are selected in the Network Editor"""
    missing = paths.missingFiles()
    if not missing:
        hou.ui.setStatusMessage("Missing files: none, all files are found", severity=hou.severityType.Message)
        return
    choices = [f"{parm.node().path()}  ({parm.name()})   {path}" for parm, path in missing]
    picked = hou.ui.selectFromList(choices, exclusive=False, title="Missing files", column_header="Node (parm)   file",
                                   message=f"{len(missing)} missing. Pick to select the nodes:", width=900, height=500)
    nodes = [missing[i][0].node() for i in picked]
    if not nodes:
        return
    pane = panes.networkPane()
    if pane is not None:
        pane.setCurrentNode(nodes[0])
    nodes[0].setCurrent(True, clear_all_selected=True)
    for node in nodes[1:]:
        if node.parent() == nodes[0].parent():
            node.setSelected(True)


main()
