#label:Explode Nodes
#textcolor:#fff048

import hou


def nodes_centroid(nodes):
    sum_pos = hou.Vector2(0, 0)
    for node in nodes:
        sum_pos += node.position()
    return sum_pos / len(nodes)


def explode_nodes(nodes):
    if not nodes:
        return
    centroid = nodes_centroid(nodes)
    for node in nodes:
        node.setPosition((node.position() - centroid) * 2 + centroid)


explode_nodes(hou.selectedNodes())
