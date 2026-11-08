from unittest.mock import MagicMock

import pytest
from hotbox import lib_common


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
    assert lib_common.replacePrefix(path, root, "$JOB", ignore_case=ignore_case) == expected


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

    assert lib_common.convertPaths("$JOB") == {"cache": ["file"]}
    parm.set.assert_called_once_with("$JOB/cache/geo.$F4.bgeo.sc")


def test_convert_paths_variable_not_set(hou, monkeypatch):
    monkeypatch.setattr(hou, "text", MagicMock(expandString=lambda s: s), raising=False)
    parm = _file_node(hou, "/a/b.bgeo", "/a/b.bgeo", monkeypatch)
    assert lib_common.convertPaths("$FILM") == {}
    parm.set.assert_not_called()


def test_render_node_is_not_parented_to_the_source_object(hou, monkeypatch):
    node = MagicMock()
    node.name.return_value = "OUT_sim"
    monkeypatch.setattr(hou, "selectedNodes", lambda: [node], raising=False)
    container = node.parent.return_value

    lib_common.createRenderNodes()

    container.parent.return_value.createNode.assert_called_once_with("geo", "RENDER_OUT_sim")
    container.createOutputNode.assert_not_called()
