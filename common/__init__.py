"""Helpers for the library scripts, split by topic:

    from hotbox.common import nodes, panes, paths

panes  - Network Editor / Scene Viewer under the cursor
nodes  - creating and placing nodes, node paths from the clipboard
paths  - file parameters, $JOB/$FILM path conversion

Whole tools live in lib/ as scripts; the same tool in another mode is a #ref, not a function here.
Updated on disk, these modules are reloaded on the next hotbox.show().
"""
