#label:Render Node
#textcolor:#ff8b48
#hotkey:1
#icon:OBJ_geo

import hou
from hotbox.common import nodes as node_utils


def main():
    """RENDER_<name> geo object under the current one, merging each selected node into it.
    Several selected nodes give a row of geo objects; spots taken by other nodes are skipped."""
    nodes = hou.selectedNodes()
    if not nodes:
        return
    container = nodes[0].parent()  # the geo object the nodes are in
    network = container.parent()
    start = container.position()
    width = container.size()[0] + 0.5
    for i, node in enumerate(nodes):
        name = node.name()
        # Sibling, not createOutputNode: a wired geo object would inherit the source object transform
        geo = network.createNode("geo", f"RENDER_{name}")
        geo.setSelectableInViewport(False)
        geo.setColor(hou.Color(0.1, 0.5, 0.1))
        wanted = hou.Vector2(start[0] + i * width, start[1] - 1)
        geo.setPosition(node_utils.freePosition(network, wanted, geo.size(), ignore=[geo]))

        merge = geo.createNode("object_merge", f"IMPORT_{name}")
        merge.parm("objpath1").set(node.path())
        merge.parm("xformtype").set(1)  # Into This Object


main()
