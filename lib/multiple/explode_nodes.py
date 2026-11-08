#label:Explode Nodes
#textcolor:#fff048

import hou
nodes = hou.selectedNodes()

def nodes_centroid(nodes):
    sum_pos = hou.Vector2(0,0)
    for node in nodes:
        sum_pos += node.position()
    sum_pos /= len(nodes)
    return sum_pos    
    
def explode_nodes(nodes):
    centroid = nodes_centroid(nodes)
    
    [x.setPosition( ( x.position()-centroid ) * 2 + centroid) for x in nodes]
   
explode_nodes(nodes)
