#label:Render Node
#textcolor:#ff8b48
#hotkey:1

import hou


def main():
    """RENDER_<name> geo object next to the current one, merging each selected node into it"""
    nodes = hou.selectedNodes()
    if not nodes:
        return
    container = nodes[0].parent()  # the geo object the nodes are in
    rest_pos = container.position() - hou.Vector2(0, 1)
    for i, node in enumerate(nodes):
        name = node.name()
        # Sibling, not createOutputNode: a wired geo object would inherit the source object transform
        geo = container.parent().createNode("geo", f"RENDER_{name}")
        geo.setSelectableInViewport(False)
        geo.setColor(hou.Color(0.1, 0.5, 0.1))
        geo.setPosition(hou.Vector2(rest_pos[0] + i * 1.5, rest_pos[1] - i * 1))

        merge = geo.createNode("object_merge", f"IMPORT_{name}")
        merge.parm("objpath1").set(node.path())
        merge.parm("xformtype").set(1)  # Into This Object


main()
