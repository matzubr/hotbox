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
        toggles = [t for t in wedge.parmTuples() if t.parmTemplate().label() == "Target Parameter"
                   and _instance(t.name()) == i]
        for tuple_ in toggles:
            kind = tuple_.parmTemplate().type().name()
            tuple_.set((1,) if kind == "Toggle" else (parm.path(),))
        if not toggles:
            problems.append(f"Target Parameter #{i} = {parm.path()}")
    return wedge, problems
