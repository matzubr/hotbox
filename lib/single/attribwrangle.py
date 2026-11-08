#label:Create Wrangle
#textcolor:#ffa700
#hotkey:w

import hou 

def main():
    selNodes = hou.selectedNodes()
    INPUT_LIMIT = 4
    sop = hou.sopNodeTypeCategory()

    if selNodes and all([n.parent().childTypeCategory() == sop for n in selNodes]):
        attribWrangle = selNodes[0].parent().createNode("attribwrangle")
        pos = []

        for i, node in enumerate(selNodes):
            if i < INPUT_LIMIT:
                attribWrangle.setInput(i, node)
                pos.append(node.position())

        posX = sum([x[0] for x in pos]) / len(pos)
        posY = min([x[1] for x in pos])
        attribWrangle.setPosition(hou.Vector2(posX, posY - 1))
        attribWrangle.setColor(hou.Color(0.95,0.8,0.25))
        attribWrangle.setDisplayFlag(True)
        attribWrangle.setRenderFlag(True)
        attribWrangle.setCurrent(True,clear_all_selected=True)


main()