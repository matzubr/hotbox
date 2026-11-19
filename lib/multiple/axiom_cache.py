#label:Axiom Cache
#group:Cache
#textcolor:#8fffc1
#hotkey:p
#icon:clock.svg

# Simulate the Axiom Solver above only while the selected caches write: Pre-Render Script (Python) turns its
# simulation on, Post-Render Script turns it off, resets it and recooks. Pressed again: removes the scripts.
# Any cache node with Pre/Post-Render Script parameters (its own or its ROP's): File Cache, s_cache, ROP Geometry...
import hou
from hotbox.common import axiom

axiom.setupAxiomCache(hou.selectedNodes())
