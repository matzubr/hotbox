#label:Color by Type
#group:Network
#textcolor:#ffd59e
#icon:palette.svg

import hou

# First match wins: name prefixes, then node type names. Edit to taste.
BY_NAME = {
    "OUT": (0.1, 0.1, 0.1),
    "RENDER": (0.1, 0.5, 0.1),
    "MERGE": (1.0, 0.71, 0.57),
    "IMPORT": (1.0, 0.71, 0.57),
}
BY_TYPE = {
    ("filecache", "file", "alembic", "alembicarchive", "rop_geometry", "rop_alembic", "usd_rop"): (0.3, 0.6, 0.9),
    ("object_merge", "fetch", "sopimport", "merge"): (1.0, 0.71, 0.57),
    ("attribwrangle", "pointwrangle", "volumewrangle"): (0.95, 0.8, 0.25),
    ("attribvop", "pointvop", "volumevop"): (0.99, 0.93, 0.0),
    ("dopnet", "solver", "pyrosolver", "vellumsolver", "rbdbulletsolver", "flipsolver"): (0.75, 0.4, 0.95),
    ("cam", "hlight", "envlight", "camera", "light"): (1.0, 0.3, 0.3),
}


def colorFor(node):
    name = node.name().upper()
    for prefix, color in BY_NAME.items():
        if name.startswith(prefix):
            return color
    type_name = node.type().nameComponents()[2]
    for types, color in BY_TYPE.items():
        if type_name in types:
            return color
    return None


painted = 0
for node in hou.selectedNodes():
    color = colorFor(node)
    if color is not None:
        node.setColor(hou.Color(*color))
        painted += 1
hou.ui.setStatusMessage(f"Colored {painted} nodes")
