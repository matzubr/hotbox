#label:Network Box
#group:Network
#textcolor:#ffd59e
#hotkey:b
#icon:network-box.svg

import hou
from hotbox.common import layout
from hotbox.utils import settings

SCRIPT = "network_box"
DEFAULT_PADDING = 15  # screen pixels around the nodes at the current zoom


def main():
    """Network box around the selected nodes: name, padding (remembered) and color (default: the palette grey after black, a bit lighter than the network)"""
    nodes = hou.selectedNodes()
    if not nodes:
        return
    padding = settings.scriptSetting(SCRIPT, "padding", DEFAULT_PADDING)
    button, (name, padding_text) = hou.ui.readMultiInput(
        "Network box", ("Name", "Padding, px"), buttons=("OK", "Color...", "Cancel"), default_choice=0,
        close_choice=2, initial_contents=(nodes[0].name(), str(padding)))
    if button == 2:
        return
    try:
        padding = max(0.0, float(padding_text.replace(",", ".")))
    except ValueError:
        padding = DEFAULT_PADDING
    settings.setScriptSetting(SCRIPT, "padding", int(padding) if padding == int(padding) else padding)
    color = hou.ui.selectColor(layout.boxColor()) if button == 1 else None  # None: the palette grey
    layout.networkBox(nodes, name, padding, color)


main()
