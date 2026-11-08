from unittest.mock import MagicMock

import pytest
from hotbox.common import nodes, paths


@pytest.mark.parametrize(("path", "root", "ignore_case", "expected"), [
    ("/proj/shot/geo", "/proj/shot", False, "$JOB/geo"),
    ("/proj/shot", "/proj/shot/", False, "$JOB"),
    ("/proj/shot_v2/geo", "/proj/shot", False, None),  # not a folder boundary
    ("/other/proj/shot/geo", "/proj/shot", False, None),  # only the start of the path
    ("D:\\Proj\\Shot\\geo", "d:/proj/shot", True, "$JOB/geo"),  # Windows: slashes and case
    ("/Proj/Shot/geo", "/proj/shot", False, None),  # case matters elsewhere
    ("/proj/geo", "", False, None),
])
def test_replace_prefix(path, root, ignore_case, expected):
    assert paths.replacePrefix(path, root, "$JOB", ignore_case=ignore_case) == expected


def _file_node(hou, raw, evaluated, monkeypatch):
    for name in ("parmTemplateType", "stringParmType"):
        monkeypatch.setattr(hou, name, MagicMock(), raising=False)
    template = MagicMock()
    template.name.return_value = "file"
    template.type.return_value = hou.parmTemplateType.String
    template.stringType.return_value = hou.stringParmType.FileReference
    template.isHidden.return_value = False
    parm = MagicMock()
    parm.rawValue.return_value = raw
    parm.eval.return_value = evaluated
    parm.name.return_value = "file"
    node = MagicMock()
    node.name.return_value = "cache"
    node.parmTemplateGroup().parmTemplates.return_value = [template]
    node.parm.return_value = parm
    monkeypatch.setattr(hou, "selectedNodes", lambda: [node], raising=False)
    return parm


def test_convert_paths_keeps_frame_variables(hou, monkeypatch):
    monkeypatch.setattr(hou, "text", MagicMock(expandString=lambda s: "/proj/shot"), raising=False)
    parm = _file_node(hou, "/proj/shot/cache/geo.$F4.bgeo.sc", "/proj/shot/cache/geo.1001.bgeo.sc", monkeypatch)

    assert paths.convertPaths("$JOB") == {"cache": ["file"]}
    parm.set.assert_called_once_with("$JOB/cache/geo.$F4.bgeo.sc")


def test_convert_paths_variable_not_set(hou, monkeypatch):
    monkeypatch.setattr(hou, "text", MagicMock(expandString=lambda s: s), raising=False)
    parm = _file_node(hou, "/a/b.bgeo", "/a/b.bgeo", monkeypatch)
    assert paths.convertPaths("$FILM") == {}
    parm.set.assert_not_called()


def test_paste_merge_nodes_from_clipboard(hou, monkeypatch):
    from hotbox.common import panes

    network = MagicMock()
    network.childTypeCategory().name.return_value = "Sop"
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    source = MagicMock()
    source.name.return_value = "sim"
    monkeypatch.setattr(hou, "node", lambda path: source if path == "/obj/geo1/sim" else None, raising=False)
    hou.ui.getTextFromClipboard.return_value = "/obj/geo1/sim  /not/a/node\n"

    created = nodes.pasteMergeNodes("Sop", "object_merge", "objpath1", relative=False, extra_parms={"xformtype": 1})

    assert len(created) == 1
    network.createNode.assert_called_once_with("object_merge", "MERGE_sim")
    created[0].parm("objpath1").set.assert_any_call(source.path())
    created[0].setUserData.assert_not_called()  # plain paste: default look


@pytest.mark.parametrize("script", ["object_merge_relative.py", "object_merge_absolute.py"])
def test_object_merge_scripts_chevron_shape_and_source_color(hou, monkeypatch, script):
    from conftest import ROOT
    from hotbox.common import panes
    from hotbox.utils import runner

    network = MagicMock()
    network.childTypeCategory().name.return_value = "Sop"
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    sources = {"/obj/a/sim": MagicMock(), "/obj/b/cache": MagicMock()}
    monkeypatch.setattr(hou, "node", lambda path: sources.get(path), raising=False)
    hou.ui.getTextFromClipboard.return_value = "/obj/a/sim /obj/b/cache"
    created = []
    network.createNode.side_effect = lambda *args: created.append(MagicMock()) or created[-1]

    assert runner.runScript(ROOT / "lib" / "all" / "Sop" / script)

    assert len(created) == 2
    for node, source in zip(created, sources.values()):
        node.setUserData.assert_called_once_with("nodeshape", "chevron_up")
        node.setColor.assert_called_once_with(source.color())


def test_paste_merge_nodes_wrong_network(hou, monkeypatch):
    from hotbox.common import panes

    pane = MagicMock()
    pane.pwd().childTypeCategory().name.return_value = "Object"
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    assert nodes.pasteMergeNodes("Sop", "object_merge", "objpath1", relative=True) == []
    pane.pwd().createNode.assert_not_called()


def test_render_node_is_not_parented_to_the_source_object(hou, monkeypatch, tmp_path):
    from conftest import ROOT
    from hotbox.utils import runner

    node = MagicMock()
    node.name.return_value = "OUT_sim"
    monkeypatch.setattr(hou, "selectedNodes", lambda: [node], raising=False)
    container = node.parent.return_value

    assert runner.runScript(ROOT / "lib" / "single" / "null" / "create_render_node.py")

    container.parent.return_value.createNode.assert_called_once_with("geo", "RENDER_OUT_sim")
    container.createOutputNode.assert_not_called()
