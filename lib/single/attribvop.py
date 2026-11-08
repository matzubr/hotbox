#label:Create Vop
#textcolor:#ffe910
#hotkey:v

import hou 

def main():
    selNodes = hou.selectedNodes()
    INPUT_LIMIT = 4
    sop = hou.sopNodeTypeCategory()

    if selNodes and all([n.parent().childTypeCategory() == sop for n in selNodes]):
        attribVop = selNodes[0].parent().createNode("attribvop")
        pos = []

        for i, node in enumerate(selNodes):
            if i < INPUT_LIMIT:
                attribVop.setInput(i, node)
                pos.append(node.position())

        posX = sum([x[0] for x in pos]) / len(pos)
        posY = min([x[1] for x in pos])
        attribVop.setPosition(hou.Vector2(posX, posY - 1))
        attribVop.setColor(hou.Color(0.99,0.93,0))
        attribVop.setDisplayFlag(True)
        attribVop.setRenderFlag(True)
        attribVop.setCurrent(True,clear_all_selected=True)


main()