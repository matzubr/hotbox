#label:Create Null
#textcolor:#ff8b48
#icon:SOP_null

import hou


def main():
    """OUT_<name> null after each selected node; for one node the name is asked"""
    nodes = hou.selectedNodes()
    if not nodes:
        return
    if len(nodes) == 1:
        button, name = hou.ui.readInput("Name", buttons=("OK", "Cancel"), default_choice=0, close_choice=1)
        if button != 0:
            return
        names = [name.strip() or nodes[0].name()]
    else:
        names = [node.name() for node in nodes]
    for node, name in zip(nodes, names):
        node.createOutputNode("null", f"OUT_{name}")


main()
