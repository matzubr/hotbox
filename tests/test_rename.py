"""Multi Rename: the rule, the problems, the swap-safe apply, the window."""
from unittest.mock import MagicMock

import pytest
from hotbox.common import rename


def _node(name, x=0.0, y=0.0, parent=None, type_name="null"):
    node = MagicMock()
    node.name.return_value = name
    node.path.return_value = f"/obj/geo/{name}"
    node.position.return_value = (x, y)
    node.type.return_value.name.return_value = type_name
    node.parent.return_value = parent
    node.setName.side_effect = lambda new, unique_name=False: node.name.configure_mock(return_value=new)
    return node


def _parent(*names):
    parent = MagicMock()
    parent.path.return_value = "/obj/geo"
    nodes = [_node(n, x=k, y=-k, parent=parent) for k, n in enumerate(names)]
    parent.children.return_value = nodes
    return parent, nodes


@pytest.mark.parametrize(("rule", "expected"), [
    (rename.Rule(find="box", replace="sphere"), "sphere_object1"),
    (rename.Rule(find=r"\d+$", replace="", regex=True), "box_object"),
    (rename.Rule(pattern="geo_###"), "geo_003"),
    (rename.Rule(pattern="{name}_#", start=10, step=5), "box_object1_20"),
    (rename.Rule(pattern="{type}_{name}"), "null_box_object1"),
    (rename.Rule(prefix="OUT_", suffix=" v2", case="UPPER"), "OUT_BOX_OBJECT1_V2"),
    (rename.Rule(find="box", replace="a b-c"), "a_b_c_object1"),
])
def test_new_name(rule, expected):
    assert rename.newName("box_object1", "null", 2, rule) == expected


def test_broken_regex_is_a_value_error():
    with pytest.raises(ValueError, match="Find"):
        rename.newName("a", "null", 0, rename.Rule(find="(", regex=True))


def test_order_and_problems():
    _parent_node, (a, b, c, _other) = _parent("a", "b", "c", "other")
    changes = rename.plan([c, a, b], rename.Rule(pattern="n#", order="Name"))
    assert [(ch.old, ch.new) for ch in changes] == [("a", "n1"), ("b", "n2"), ("c", "n3")]
    assert [ch.old for ch in rename.plan([c, a, b], rename.Rule(order="Top to bottom"))] == ["a", "b", "c"]

    problems = {ch.old: ch.problem for ch in rename.plan([a, b, c], rename.Rule(pattern="x"))}
    assert set(problems.values()) == {"same name twice"}
    assert rename.plan([a], rename.Rule(pattern="other"))[0].problem == "taken by another node"
    assert rename.plan([a], rename.Rule(pattern="#"))[0].problem == "starts with a digit"
    assert rename.plan([a], rename.Rule(find="a", replace=""))[0].problem == "empty name"
    assert rename.plan([a, b], rename.Rule(pattern="b", find="", order="Selection"))[0].problem == "same name twice"


def test_swapped_names_apply_through_temporary_ones():
    _parent_node, (a, b) = _parent("a", "b")
    changes = [rename.Change(a, "a", "b"), rename.Change(b, "b", "a")]  # a <-> b: a direct rename would clash
    assert rename.apply(changes) == 2
    assert (a.name(), b.name()) == ("b", "a")
    assert a.setName.call_args_list[0].kwargs == {"unique_name": True}
    changes[0].problem = "same name twice"
    changes[0].new = "zzz"
    with pytest.raises(ValueError):
        rename.apply(changes)


def test_rename_window_previews_and_renames(houdini, hou):
    from hotbox.utils import renamer

    _parent_node, nodes = _parent("box1", "box2", "keep")
    window = renamer.RenameWindow(nodes[:2], parent=houdini)
    window.find.setText("box")
    window.replace.setText("rock_")
    assert [window.table.item(r, 1).text() for r in range(2)] == ["rock_1", "rock_2"]
    assert window.rename_button.isEnabled()
    window.pattern.setText("keep")
    assert not window.rename_button.isEnabled() and "red" in window.status.text()
    window.pattern.setText("")
    window.rename()
    assert [n.name() for n in nodes[:2]] == ["rock_1", "rock_2"]
    assert renamer.LAST.find == "box", "fields kept for the next rename"
    renamer.LAST = rename.Rule()
