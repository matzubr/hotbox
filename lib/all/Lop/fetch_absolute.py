#label:Fetch Absolute
#textcolor:#ffb492
#buttoncolor:#1f1a12
#hotkey:2

import hou 
from tkinter import Tk

def main():
    nodes_string = Tk().clipboard_get()

    network_panetab = getPane()
    network_node = network_panetab.pwd()
        
    if not network_panetab:
        return

    for i,node in enumerate(nodes_string.split(" ")):

        if not hou.node(node):
            break

        if network_node.childTypeCategory().name() in ["Lop"]:
            objm = network_node.createNode("fetch",f"MERGE_{node.split('/')[-1]}")
            objm.setPosition(network_panetab.cursorPosition() + hou.Vector2(i*3,0) - hou.Vector2(0.5,0))
            objm.parm("loppath").set(node)

def getPane():
    cursor_panetab = hou.ui.paneTabUnderCursor()
    if cursor_panetab and cursor_panetab.type() == hou.paneTabType.NetworkEditor:
        return cursor_panetab
    else:
        network_panetab = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
        if network_panetab:
            return network_panetab
        else:
            print(f"No Pane found")
            return None

main()