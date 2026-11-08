#label:Network Box
#group:Network
#textcolor:#ffd59e
#hotkey:b
#icon:network-box.svg

import hou


def main():
    """Network box around the selected nodes, named, in the color of the first node"""
    nodes = hou.selectedNodes()
    if not nodes:
        return
    button, name = hou.ui.readInput("Network box name", buttons=("OK", "Cancel"), default_choice=0, close_choice=1,
                                    initial_contents=nodes[0].name())
    if button != 0:
        return
    parent = nodes[0].parent()
    box = parent.createNetworkBox()
    box.setComment(name.strip())
    for node in nodes:
        if node.parent() == parent:
            box.addItem(node)
    box.fitAroundContents()
    box.setColor(nodes[0].color())


main()
