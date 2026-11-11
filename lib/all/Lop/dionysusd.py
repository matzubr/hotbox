#label:Prim Paths
#group:Solaris
#textcolor:#5eead4
#hotkey:p
#icon:prim-tree.svg

# DionysUSD (github.com/matzubr/DionysUSD) on this LOP network: every prim path parameter in one tree,
# rename a branch in all of them at once
from hotbox.common import panes

try:
    import DionysUSD
except ImportError:
    DionysUSD = None

if DionysUSD is None:
    panes.warn("DionysUSD is not installed: put it next to hotbox in python3.11libs")
elif not hasattr(DionysUSD, "show"):
    # An empty folder imports as an empty namespace package: a new submodule pulled without --init
    panes.warn("DionysUSD folder is empty: git submodule update --init python3.11libs/DionysUSD")
else:
    pane = panes.networkPane()
    DionysUSD.show(pane.pwd().path() if pane is not None else None)
