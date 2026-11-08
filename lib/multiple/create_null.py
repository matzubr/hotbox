#label:Create Null
#textcolor:#ff8b48

import hou 

def main():
    nodes = hou.selectedNodes()
    
    if len(nodes)==0:
        return
    
    if len(nodes)==1:
        node = nodes[0]
        input,name = hou.ui.readInput("Name")
        if len(name)==0:
            name = node.name()
        node.createOutputNode("null",f"OUT_{name}")
    else:
        for node in nodes:
            name = node.name()
            node.createOutputNode("null",f"OUT_{name}")


main()