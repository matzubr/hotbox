"""Axiom Solver caching: the cache node's pre-render script turns the solver's simulation on, the post-render script
turns it off, resets it and recooks (the scene stays light while you work).

The scripts are pasted into the cache node's Pre/Post-Render Script parameters (Python), so they run without
hotbox. They run in the ROP that writes (inside the cache node): the solver is looked for upstream of it, then
upstream of the nodes it sits in (the cache node's inputs), the nearest one first, through every input.
"""
from __future__ import annotations

import hou

from .caches import ropOf, setMenuByLabel

SOLVER_TYPE = "axiom_solver"
MARK = "# hotbox: Axiom cache script"

_FIND = f'''{MARK}
import hou

SOLVER_TYPE = "{SOLVER_TYPE}"


def upstream(node):
    """Every node above, nearest first, through all inputs"""
    seen, queue = set(), list(node.inputs())
    while queue:
        node = queue.pop(0)
        if node is None or node.path() in seen:
            continue
        seen.add(node.path())
        yield node
        queue.extend(node.inputs())


def axiomSolver():
    """The nearest Axiom Solver above the ROP running this script, or above the nodes it is in (the cache node)"""
    node = hou.pwd()
    while node is not None and node.path() != "/":
        for above in upstream(node):
            if above.type().nameComponents()[2] == SOLVER_TYPE:
                return above
        node = node.parent()
    return None


def setParm(node, name, value):
    parm = node.parm(name)
    if parm is None:
        print(f"Axiom cache script: {{node.path()}} has no {{name}} parameter")
    else:
        parm.set(value)
    return parm


solver = axiomSolver()
if solver is None:
    print(f"Axiom cache script: no {{SOLVER_TYPE}} above {{hou.pwd().path()}}")
'''

PRE_RENDER = _FIND + '''else:
    setParm(solver, "enableSimulation", 1)
'''

POST_RENDER = _FIND + '''else:
    setParm(solver, "enableSimulation", 0)
    reset = solver.parm("resetSimulation")
    if reset is not None:
        reset.pressButton()
    solver.cook(force=True)
'''

# (enable toggle, script, language) per script; the label is used when the names differ (studio cache HDAs)
SLOTS = {
    "pre": ("tprerender", "prerender", "lprerender", "Pre-Render Script"),
    "post": ("tpostrender", "postrender", "lpostrender", "Post-Render Script"),
}


def _byLabel(node, label: str):
    return next((p for p in node.parms() if p.parmTemplate().label().strip() == label), None)


def _owners(node):
    yield node
    try:
        rop = ropOf(node)
    except (AttributeError, TypeError, ValueError, hou.OperationFailed):
        rop = None
    if rop is not None and rop is not node:
        yield rop


def scriptParms(node) -> dict | None:
    """{'pre': (toggle, script, language), 'post': ...} of the node, else of its ROP; None when neither has them"""
    for owner in _owners(node):
        found = {}
        for key, (toggle, script, language, label) in SLOTS.items():
            parm = owner.parm(script) or _byLabel(owner, label)
            if parm is None:
                break
            found[key] = (owner.parm(toggle), parm, owner.parm(language))
        else:
            return found
    return None


def isSet(parms: dict) -> bool:
    return all(MARK in script.unexpandedString() for _toggle, script, _language in parms.values())


def setScripts(parms: dict, on: bool = True) -> None:
    """Paste (on) or clear the scripts, Python, their toggles on/off"""
    texts = {"pre": PRE_RENDER, "post": POST_RENDER}
    for key, (toggle, script, language) in parms.items():
        script.set(texts[key] if on else "")
        if language is not None and on and not setMenuByLabel(language, "Python"):
            language.set("python")
        if toggle is not None:
            toggle.set(int(on))


def setupAxiomCache(nodes) -> str:
    """The button on one or more cache nodes: paste the scripts (asks before replacing other scripts), or remove them
    when every node already has them. Returns what it did."""
    from . import panes

    found = [(node, scriptParms(node)) for node in nodes]
    missing = [node.name() for node, parms in found if parms is None]
    found = [(node, parms) for node, parms in found if parms is not None]
    if not found:
        panes.warn(f"No Pre/Post-Render Script parameters on {', '.join(missing) or 'the selection'}")
        return "none"
    names = ", ".join(node.name() for node, _parms in found)
    if all(isSet(parms) for _node, parms in found):
        if hou.ui.displayMessage(f"{names}: the Axiom cache scripts are already there.", title="Axiom Cache",
                                 buttons=("Remove Them", "Keep"), default_choice=1, close_choice=1) != 0:
            return "kept"
        for _node, parms in found:
            setScripts(parms, on=False)
        hou.ui.setStatusMessage(f"Axiom cache scripts removed: {names}")
        return "removed"
    own = [f"{node.name()} ({script.name()})" for node, parms in found if not isSet(parms)
           for _t, script, _l in parms.values() if script.unexpandedString().strip() and MARK not in
           script.unexpandedString()]
    if own and hou.ui.displayMessage("Replace their own scripts?\n" + "\n".join(own), title="Axiom Cache",
                                     buttons=("Replace", "Cancel"), default_choice=1, close_choice=1,
                                     severity=hou.severityType.Warning) != 0:
        return "kept"
    failed = []
    for node, parms in found:
        try:
            setScripts(parms)
        except hou.OperationFailed as e:  # a ROP inside a locked asset
            failed.append(f"{node.name()}: {e}")
    message = f"Simulate {SOLVER_TYPE} only while writing: {names}"
    if missing:
        message += f"; no script parameters: {', '.join(missing)}"
    if failed:
        panes.warn("\n".join(failed))
        return "failed"
    hou.ui.setStatusMessage(message, severity=hou.severityType.Warning if missing else hou.severityType.Message)
    return "set"
