#label:Compile Block
#package:qLib
#group:Network
#textcolor:#ffd59e
#hotkey:k
#icon:SOP_compile_end

# Compile Begin on every input into the selected SOPs, Compile End after them (for-each blocks get Multithread)
import hou
from hotbox.common import nodes, panes

try:
    begins, end = nodes.compileBlock(hou.selectedNodes())
    end.setCurrent(True, clear_all_selected=True)
    hou.ui.setStatusMessage(f"Compiled block: {len(begins)} begin node(s), {end.name()}")
except ValueError as e:
    panes.warn(str(e))
