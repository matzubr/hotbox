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


def builtInSopNetwork(rop):
    """The SOP network inside a ROP Geometry Output TOP (used with Use External SOP off)"""
    if rop.childTypeCategory() == hou.sopNodeTypeCategory():
        return rop
    return next((c for c in rop.children() if c.childTypeCategory() == hou.sopNodeTypeCategory()), None)


def buildChain(topnet, wedge, node) -> list[str]:
    """Geometry Import -> Wedge -> ROP Geometry Output. The ROP writes one file per wedge with its built-in SOP
    network (Use External SOP off), an Object Merge of the result inside. Returns what couldn't be set."""
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

    network = builtInSopNetwork(rop)
    if network is None:
        problems.append(f"Inside {rop.name()}: Object Merge of {written.path()}")
        return problems
    merge = network.createNode("object_merge", f"IMPORT_{written.name()}")
    merge.parm("objpath1").set(written.path())
    merge.setDisplayFlag(True)
    merge.setRenderFlag(True)
    return problems
