#label:Help to Comment
#package:HelpToComment
#group:Network
#textcolor:#ffd59e
#hotkey:i
#icon:help.svg

# The one-line summary of the node's help page as its comment (shown in the network)
import hou
from hotbox.common import nodes

for node in hou.selectedNodes():
    summary = nodes.nodeHelpSummary(node.type()) or node.type().description()
    node.setComment(summary)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
