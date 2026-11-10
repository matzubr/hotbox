#label:Prim Paths
#group:Solaris
#textcolor:#d8b4fe
#hotkey:p
#icon:prim-tree.svg

# DionysUSD (github.com/matzubr/DionysUSD) on this LOP network: every prim path parameter in one tree,
# rename a branch in all of them at once
from hotbox.common import panes

try:
    import DionysUSD
except ImportError:
    panes.warn("DionysUSD is not installed: put it next to hotbox in python3.11libs")
else:
    pane = panes.networkPane()
    DionysUSD.show(pane.pwd().path() if pane is not None else None)
