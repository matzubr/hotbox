#label:Snippets
#group:Code
#textcolor:#ffa700
#hotkey:e
#icon:snippets.svg

# mnemo (github.com/matzubr/mnemo): search the code snippets and insert one into this node
# (VEX for wrangles, Python for Python nodes)
from hotbox.common import panes

try:
    import mnemo
except ImportError:
    mnemo = None

if mnemo is None:
    panes.warn("mnemo is not installed: put it next to hotbox in python3.11libs")
elif not hasattr(mnemo, "show"):
    # An empty folder imports as an empty namespace package: a new submodule pulled without --init
    panes.warn("mnemo folder is empty: git submodule update --init python3.11libs/mnemo")
else:
    mnemo.show()
