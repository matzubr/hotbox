"""Wedge TOP for picked parameters. Parameters of the Wedge are found by their labels (as in the docs):
their internal names are not documented, labels are what the user sees."""
from __future__ import annotations

import re

import hou

NUMBER_TYPES = ("Float", "Int")


def wedgeableParms(node) -> list:
    """Visible float / int parameters of the node that are not driven by an expression or keys"""
    result = []
    for parm in node.parms():
        template = parm.parmTemplate()
        if template.type().name() not in NUMBER_TYPES or template.isHidden() or parm.isLocked():
            continue
        if parm.keyframes():
            continue
        result.append(parm)
    return result


def _instance(name: str) -> int | None:
    """Multiparm instance number at the end of a parameter name: name3 -> 3"""
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else None


def parmByLabel(node, label: str, instance: int | None = None, kinds=None):
    """Parameter (tuple) of the node with the label; of the multiparm instance when given"""
    for tuple_ in node.parmTuples():
        template = tuple_.parmTemplate()
        if template.label() != label:
            continue
        if kinds and template.type().name() not in kinds:
            continue
        if instance is not None and _instance(tuple_.name()) != instance:
            continue
        return tuple_
    return None


def attributeName(parm) -> str:
    return f"{parm.node().name()}_{parm.name()}"


def _topNetwork(near):
    parent = near.parent()
    try:
        topnet = parent.createNode("topnet", f"wedge_{near.name()}")
    except hou.OperationFailed:
        topnet = hou.node("/tasks").createNode("topnet", f"wedge_{near.name()}")
    if topnet.parent() == parent:
        from .nodes import freePosition

        wanted = near.position() + hou.Vector2(3, 0)
        topnet.setPosition(freePosition(parent, wanted, topnet.size(), ignore=[topnet]))
    return topnet


def buildWedge(parms, count: int) -> tuple:
    """TOP network next to the first node with one Wedge: an attribute per parameter, from its value to 2x,
    pushed into the parameter (Target Parameter). (wedge node, settings it couldn't set)"""
    topnet = _topNetwork(parms[0].node())
    wedge = topnet.createNode("wedge", "wedge")
    problems = []

    def setByLabel(label, value, instance=None, kinds=None):
        tuple_ = parmByLabel(wedge, label, instance, kinds)
        if tuple_ is None:
            problems.append(f"{label}" + (f" #{instance}" if instance else "") + f" = {value}")
            return False
        try:
            values = value if isinstance(value, (tuple, list)) else (value,) * len(tuple_)
            tuple_.set(values[:len(tuple_)])
        except (hou.OperationFailed, TypeError):
            problems.append(f"{label} = {value}")
            return False
        return True

    setByLabel("Wedge Count", count)
    setByLabel("Wedge Attributes", len(parms))
    for i, parm in enumerate(parms, start=1):
        value = parm.eval()
        end = value * 2 if value else 1
        setByLabel("Attribute Name", attributeName(parm), i, kinds=("String",))
        range_label = next((label for label in ("Start/End", "Range") if parmByLabel(wedge, label, i)), "Start/End")
        setByLabel(range_label, (value, end), i)
        if not setTargetParameter(wedge, i, parm.path()):
            problems.append(f"Target Parameter #{i} = {parm.path()} (turned on)")
    if not setToggle(wedge, OVERWRITE_LABEL):
        problems.append(f"{OVERWRITE_LABEL}: on")
    problems += buildChain(topnet, wedge, parms[0].node())
    return wedge, problems


OVERWRITE_LABEL = "Overwrite Target Parameter on Work Item Selection"


def _isToggle(tuple_) -> bool:
    return tuple_.parmTemplate().type().name() == "Toggle"


def setToggle(node, label: str) -> bool:
    """Turn on the toggle with the label (case and spaces don't matter)"""
    wanted = " ".join(label.lower().split())
    for tuple_ in node.parmTuples():
        if _isToggle(tuple_) and " ".join(tuple_.parmTemplate().label().lower().split()) == wanted:
            tuple_.set((1,))
            return True
    return False


def setTargetParameter(wedge, instance: int, path: str) -> bool:
    """Target Parameter of the wedge attribute: the path into its field and its checkbox on.
    The checkbox is a separate toggle in front of the field (often without a label of its own)."""
    tuples = list(wedge.parmTuples())
    field = toggle = None
    for k, tuple_ in enumerate(tuples):
        if tuple_.parmTemplate().label() != "Target Parameter" or _instance(tuple_.name()) != instance:
            continue
        if _isToggle(tuple_):
            toggle = tuple_
        elif field is None:
            field = tuple_
            before = tuples[k - 1] if k else None
            if toggle is None and before is not None and _isToggle(before) and _instance(before.name()) == instance:
                toggle = before
    if field is not None:
        field.set((path,))
    if toggle is not None:
        toggle.set((1,))
    return field is not None and toggle is not None


OUTPUT_FILE = "$HIP/geo/wedge/{name}/{name}.`@wedgeindex`.$F4.bgeo.sc"


def outputSop(node):
    """What the wedge writes: the display node of the SOP network of the wedged node"""
    try:
        if node.type().category() == hou.sopNodeTypeCategory():
            return node.parent().displayNode() or node
    except (AttributeError, hou.OperationFailed):
        pass
    return node


def _childOf(topnet, type_name: str, exclude=()):
    return next((c for c in topnet.children() if c.type().name() == type_name and c not in exclude), None)


def buildChain(topnet, wedge, node) -> list[str]:
    """Geometry Import -> Wedge -> ROP Geometry Output. The geometry comes from the Geometry Import (its SOP Path),
    the ROP writes it per wedge (Use External SOP off). Returns what couldn't be set."""
    problems = []
    source = _childOf(topnet, "geometryimport") or topnet.createNode("geometryimport")
    rop = _childOf(topnet, "ropgeometry") or topnet.createNode("ropgeometry", f"write_{node.name()}")
    wedge.setInput(0, source)
    rop.setInput(0, wedge)
    wedge.setPosition(source.position() - hou.Vector2(0, 1.5))
    rop.setPosition(wedge.position() - hou.Vector2(0, 1.5))
    rop.setDisplayFlag(True)

    external = parmByLabel(rop, "Use External SOP", kinds=("Toggle",))
    if external is not None:
        external.set((0,))
    else:
        problems.append("Use External SOP: off")
    written = outputSop(node)
    output = parmByLabel(rop, "Output File", kinds=("String",))
    if output is not None:
        output.set((OUTPUT_FILE.format(name=written.name()),))
    else:
        problems.append(f"Output File = {OUTPUT_FILE.format(name=written.name())}")
    return problems
    merge = network.createNode("object_merge", f"IMPORT_{written.name()}")
    merge.parm("objpath1").set(written.path())
    merge.setDisplayFlag(True)
    merge.setRenderFlag(True)
    return problems


# --- loading the written wedges -----------------------------------------------------------------------------------

_WEDGE_TOKEN = re.compile(r"`?@wedgeindex`?")
_FRAME_TOKEN = re.compile(r"\$\{?F\d*\}?|\$FF")
_WEDGE_MARK, _FRAME_MARK = "HOTBOXWEDGEMARK", "HOTBOXFRAMEMARK"


def outputFileParm(rop):
    """Output File of a ROP Geometry Output TOP"""
    tuple_ = parmByLabel(rop, "Output File", kinds=("String",))
    return tuple_[0] if tuple_ is not None else None


def wedgePath(raw: str, index: int) -> str:
    """The output path of one wedge: `@wedgeindex` replaced, $HIP / $F4 kept"""
    return _WEDGE_TOKEN.sub(str(index), raw)


def wedgeIndicesOnDisk(raw: str, expand=None) -> list[int]:
    """Wedge indices that have files on disk for the output path (any frame)"""
    import glob

    expand = expand or hou.text.expandString
    marked = _FRAME_TOKEN.sub(_FRAME_MARK, _WEDGE_TOKEN.sub(_WEDGE_MARK, raw))
    expanded = expand(marked).replace("\\", "/")
    if _WEDGE_MARK not in expanded:
        return []
    pattern = re.escape(expanded).replace(_WEDGE_MARK, r"(\d+)").replace(_FRAME_MARK, r"-?\d+")
    regex = re.compile(pattern + "$")
    found = set()
    for path in glob.glob(expanded.replace(_WEDGE_MARK, "*").replace(_FRAME_MARK, "*")):
        match = regex.match(path.replace("\\", "/"))
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def upstreamWedgeCount(rop) -> int | None:
    """Wedge Count of the first Wedge above the ROP"""
    stack, seen = list(rop.inputs()), set()
    while stack:
        node = stack.pop(0)
        if node is None or node.path() in seen:
            continue
        seen.add(node.path())
        if node.type().name() == "wedge":
            count = parmByLabel(node, "Wedge Count")
            return int(count[0].eval()) if count is not None else None
        stack.extend(node.inputs())
    return None


def loadWedges(rop) -> list:
    """File SOP per written wedge (the ones on disk, else Wedge Count of them) and a Switch to flip through them,
    in the SOP network the TOP network is in (else a new geo object). Returns the file nodes."""
    parm = outputFileParm(rop)
    if parm is None:
        raise ValueError(f"{rop.name()} has no Output File")
    raw = parm.unexpandedString()
    if not _WEDGE_TOKEN.search(raw):
        indices = [None]
    else:
        indices = wedgeIndicesOnDisk(raw) or list(range(upstreamWedgeCount(rop) or 0))
        if not indices:
            raise ValueError("No wedges on disk and no Wedge Count above the ROP")

    topnet = rop.parent()
    network = topnet.parent()
    if network.childTypeCategory() != hou.sopNodeTypeCategory():
        network = hou.node("/obj").createNode("geo", f"wedges_{rop.name()}")
        start = hou.Vector2(0, 0)
    else:
        start = topnet.position() + hou.Vector2(3, 0)

    from .nodes import freePosition

    files = []
    for k, index in enumerate(indices):
        name = rop.name() if index is None else f"wedge_{index}"
        node = network.createNode("file", name)
        node.parm("file").set(raw if index is None else wedgePath(raw, index))
        wanted = start + hou.Vector2(k * 2, 0)
        node.setPosition(freePosition(network, wanted, node.size(), ignore=[node]))
        files.append(node)
    if len(files) > 1:
        switch = network.createNode("switch", f"switch_{rop.name()}")
        for k, node in enumerate(files):
            switch.setInput(k, node)
        lowest = min(n.position()[1] for n in files)
        middle = sum(n.position()[0] for n in files) / len(files)
        switch.setPosition(freePosition(network, hou.Vector2(middle, lowest - 1.5), switch.size(), ignore=[switch]))
        switch.setCurrent(True, clear_all_selected=True)
    else:
        files[0].setCurrent(True, clear_all_selected=True)
    return files
