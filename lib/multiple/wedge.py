#label:Wedge
#package:LV-Tools
#textcolor:#ffa0e6
#hotkey:g
#icon:TOP_wedge

# A TOP network with a Wedge for the parameters you pick on the selected nodes:
# from the current value to twice it. Target Parameter and "Overwrite Target Parameter on Work Item Selection" are on:
# picking a work item shows its values in the node. Wedge -> ROP Geometry Output: the ROP cooks the network
# (Use External SOP on, SOP Path = its display node) with each wedge's values, files in $HIP/geo/wedge/<name>/
import hou
from hotbox.common import panes, wedge


def main():
    parms = [parm for node in hou.selectedNodes() for parm in wedge.wedgeableParms(node)]
    if not parms:
        panes.warn("No float or integer parameters to wedge")
        return
    choices = [f"{parm.node().name()}  {parm.description()}  ({parm.name()} = {parm.eval():g})" for parm in parms]
    picked = hou.ui.selectFromList(choices, exclusive=False, title="Wedge", column_header="Node  parameter",
                                   message="Parameters to wedge", width=600, height=500)
    if not picked:
        return
    button, count = hou.ui.readInput("Wedge count", buttons=("OK", "Cancel"), default_choice=0, close_choice=1,
                                     initial_contents="5")
    if button != 0:
        return
    node, problems = wedge.buildWedge([parms[i] for i in picked], max(int(count or 5), 2))
    node.setCurrent(True, clear_all_selected=True)
    if problems:
        hou.ui.displayMessage("Wedge is built, set these by hand:\n" + "\n".join(problems), title="Wedge")


main()
