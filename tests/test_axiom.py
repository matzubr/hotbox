"""Axiom Cache: the pasted pre/post-render scripts find the solver and switch its simulation."""
import types
from unittest.mock import MagicMock

from hotbox.common import axiom


class N:
    def __init__(self, path, type_name="null", inputs=(), parent=None):
        self.path_, self.type_name, self.inputs_, self.parent_ = path, type_name, list(inputs), parent
        self.parms_ = {"enableSimulation": MagicMock(), "resetSimulation": MagicMock()}
        self.cooked = False

    def path(self):
        return self.path_

    def inputs(self):
        return self.inputs_

    def parent(self):
        return self.parent_

    def type(self):
        return types.SimpleNamespace(nameComponents=lambda: ("", "", self.type_name, "2.0"))

    def parm(self, name):
        return self.parms_.get(name)

    def cook(self, force=False):
        self.cooked = force


def _scene():
    """axiom_solver -> merge -> filecache (its ROP inside, wired to nothing: the subnet input)"""
    root = N("/")
    solver = N("/obj/geo/axiom_solver1", "axiom_solver")
    merge = N("/obj/geo/merge1", "merge", inputs=[N("/obj/geo/box"), solver])
    cache = N("/obj/geo/filecache1", "filecache", inputs=[merge], parent=N("/obj/geo", parent=root))
    rop = N("/obj/geo/filecache1/render", "rop_geometry", parent=cache)
    return solver, rop


def _run(script, pwd):
    """As Houdini runs it: the script imports hou itself, hou.pwd() is the ROP"""
    import sys

    printed = []
    hou = sys.modules["hou"]
    old = hou.__dict__.get("pwd")
    hou.pwd = lambda: pwd
    try:
        exec(script, {"print": lambda *a: printed.append(" ".join(map(str, a)))})  # noqa: S102
    finally:
        if old is None:
            del hou.pwd
        else:
            hou.pwd = old
    return printed


def test_pre_and_post_render_scripts_find_the_solver_through_any_input():
    solver, rop = _scene()
    assert _run(axiom.PRE_RENDER, rop) == []
    solver.parms_["enableSimulation"].set.assert_called_once_with(1)
    _run(axiom.POST_RENDER, rop)
    solver.parms_["enableSimulation"].set.assert_called_with(0)
    solver.parms_["resetSimulation"].pressButton.assert_called_once()
    assert solver.cooked


def test_no_solver_is_reported_not_raised():
    lonely = N("/obj/geo/filecache1/render", parent=N("/obj/geo/filecache1", parent=N("/")))
    assert "no axiom_solver above" in _run(axiom.POST_RENDER, lonely)[0]


def _cache_node(prerender=""):
    parms = {name: MagicMock() for name in ("tprerender", "prerender", "lprerender", "tpostrender", "postrender",
                                             "lpostrender")}
    for name in ("prerender", "postrender"):
        parms[name].name.return_value = name
        parms[name].unexpandedString.return_value = prerender if name == "prerender" else ""
    for name in ("lprerender", "lpostrender"):
        parms[name].menuLabels.return_value = ("Hscript", "Python")
        parms[name].menuItems.return_value = ("hscript", "python")
    node = MagicMock()
    node.name.return_value = "filecache1"
    node.type.return_value.nameComponents.return_value = ("", "", "filecache", "2.0")
    node.parm.side_effect = parms.get
    return node, parms


def test_button_pastes_python_scripts_and_removes_them(hou):
    node, parms = _cache_node()
    assert axiom.setupAxiomCache([node]) == "set"
    parms["prerender"].set.assert_called_with(axiom.PRE_RENDER)
    parms["postrender"].set.assert_called_with(axiom.POST_RENDER)
    parms["tprerender"].set.assert_called_with(1)
    assert parms["lpostrender"].set.call_args.args[0] in (1, "python")

    for name in ("prerender", "postrender"):
        parms[name].unexpandedString.return_value = axiom.MARK + "\n..."
    hou.ui.displayMessage.return_value = 0  # Remove Them
    assert axiom.setupAxiomCache([node]) == "removed"
    parms["prerender"].set.assert_called_with("")
    parms["tpostrender"].set.assert_called_with(0)


def test_own_scripts_are_not_replaced_without_asking(hou):
    node, parms = _cache_node(prerender="print('mine')")
    hou.ui.displayMessage.return_value = 1  # Cancel
    assert axiom.setupAxiomCache([node]) == "kept"
    parms["prerender"].set.assert_not_called()
