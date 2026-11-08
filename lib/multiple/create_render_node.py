#label:Render Node
#textcolor:#ff8b48

import hou
import re

def main():
    nodes = hou.selectedNodes()
    
    if len(nodes)==0:
        return
    
    network = nodes[0].parent()
    
    for i,node in enumerate(nodes):
        name = node.name()

        geo = network.createOutputNode("geo",f"RENDER_{name}")
        geo.setSelectableInViewport(False)
        geo.setColor(hou.Color(0.1,0.5,0.1))
        rest_pos = network.position() - hou.Vector2(0,1)
        geo.setPosition(hou.Vector2(rest_pos[0] + i*1.5,rest_pos[1] - i*1))
        
        objm = geo.createNode("object_merge",f"IMPORT_{name}")
        objm.parm("objpath1").set(node.path())
        objm.parm("xformtype").set(1)

main()