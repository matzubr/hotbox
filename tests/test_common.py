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


@pytest.mark.parametrize(("category", "script", "relative"), [
    ("Sop", "object_merge_relative.py", True), ("Sop", "object_merge_absolute.py", False),
    ("Lop", "fetch_relative.py", True), ("Lop", "fetch_absolute.py", False),
])
def test_merge_scripts_chevron_shape_and_source_color(hou, monkeypatch, category, script, relative):
    from conftest import ROOT
    from hotbox.common import panes
    from hotbox.utils import runner

    network = MagicMock()
    network.childTypeCategory().name.return_value = category
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    sources = {"/obj/a/sim": MagicMock(), "/obj/b/cache": MagicMock()}
    monkeypatch.setattr(hou, "node", lambda path: sources.get(path), raising=False)
    hou.ui.getTextFromClipboard.return_value = "/obj/a/sim /obj/b/cache"
    created = []
    network.createNode.side_effect = lambda *args: created.append(MagicMock()) or created[-1]

    assert runner.runScript(ROOT / "lib" / "all" / category / script)

    assert len(created) == 2
    path_parm = "objpath1" if category == "Sop" else "loppath"
    for node, source in zip(created, sources.values()):
        node.setUserData.assert_called_once_with("nodeshape", "chevron_up")
        node.setColor.assert_called_once_with(source.color())
        expected = node.relativePathTo(source) if relative else source.path()
        node.parm(path_parm).set.assert_any_call(expected)


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


def _item(path, x, y, w=1.0, h=0.3):
    item = MagicMock()
    item.path.return_value = path
    item.position.return_value = (x, y)
    item.size.return_value = (w, h)
    return item


def test_free_position_skips_taken_spots(hou, monkeypatch):
    monkeypatch.setattr(hou, "Vector2", lambda x, y: (x, y), raising=False)
    network = MagicMock()
    network.children.return_value = [_item("/obj/a", 0, -1), _item("/obj/b", 0, -2)]
    assert nodes.freePosition(network, (0, -1), (1, 0.3)) == (0, -3)
    assert nodes.freePosition(network, (3, -1), (1, 0.3)) == (3, -1)  # free column
    assert nodes.freePosition(network, (0, -1), (1, 0.3), ignore=[_item("/obj/a", 0, 0), _item("/obj/b", 0, 0)]) == (0, -1)


def test_render_nodes_go_under_the_object_without_covering_others(hou, monkeypatch):
    from conftest import ROOT
    from hotbox.utils import runner

    monkeypatch.setattr(hou, "Vector2", lambda x, y: (x, y), raising=False)
    container = _item("/obj/geo1", 0, 0)
    network = MagicMock()
    children = [container, _item("/obj/taken", 0, -1)]  # right under geo1
    network.children.side_effect = lambda: list(children)

    def createNode(node_type, name):
        geo = _item(f"/obj/{name}", 0, 0)
        geo.setPosition.side_effect = lambda pos: geo.position.configure_mock(return_value=pos)
        children.append(geo)
        return geo

    network.createNode.side_effect = createNode
    container.parent.return_value = network
    selected = []
    for name in ("a", "b"):
        node = MagicMock()
        node.name.return_value = name
        node.parent.return_value = container
        selected.append(node)
    monkeypatch.setattr(hou, "selectedNodes", lambda: selected, raising=False)

    assert runner.runScript(ROOT / "lib" / "single" / "null" / "create_render_node.py")

    first, second = children[2], children[3]
    assert first.position() == (0, -2)  # (0, -1) is taken
    assert second.position() == (1.5, -1)  # next to it in a row


class _SequenceParm:
    """File parm whose value has the frame in it like $F4"""

    def __init__(self, template):
        self.template = template

    def evalAtFrame(self, frame):
        return self.template.format(frame=f"{frame:04d}")


def test_sequence_frames_found_on_disk(tmp_path):
    from hotbox.common import frames

    for frame in (1001, 1002, 1010):
        (tmp_path / f"geo.{frame:04d}.bgeo.sc").write_text("")
    (tmp_path / "geo.1001.bgeo.sc.tmp").write_text("")
    (tmp_path / "other.1005.bgeo.sc").write_text("")
    parm = _SequenceParm(tmp_path.as_posix() + "/geo.{frame}.bgeo.sc")

    assert frames.sequencePattern(parm) == (tmp_path.as_posix(), "geo.", ".bgeo.sc")
    assert frames.sequenceFrames(parm) == [1001, 1002, 1010]
    assert frames.sequenceFrames(_SequenceParm("/no/such/folder/geo.{frame}.exr")) == []
    assert frames.sequencePattern(_SequenceParm(tmp_path.as_posix() + "/static.bgeo")) is None
    assert frames.sequencePattern(_SequenceParm(tmp_path.as_posix() + "/{frame}/geo.bgeo")) is None  # frame folders


def test_frame_range_from_keyframes(hou, monkeypatch):
    from hotbox.common import frames

    monkeypatch.setattr(paths, "fileParms", lambda node, include_hidden=False: [])
    keys = [MagicMock(), MagicMock(), MagicMock()]
    for key, frame in zip(keys, (1001.0, 1050.0, 1100.0)):
        key.frame.return_value = frame
    camera = MagicMock()
    camera.parms.return_value = [MagicMock(keyframes=lambda: keys[:2]), MagicMock(keyframes=lambda: keys[2:])]
    static = MagicMock()
    static.parms.return_value = [MagicMock(keyframes=list)]
    monkeypatch.setattr(hou, "selectedNodes", lambda: [camera, static], raising=False)
    monkeypatch.setattr(hou, "playbar", MagicMock(), raising=False)

    assert frames.frameRangeFromSelection() == (1001, 1100)
    hou.playbar.setFrameRange.assert_called_once_with(1001, 1100)
    hou.playbar.setPlaybackRange.assert_called_once_with(1001, 1100)


class _Node:
    """Scene node with file parms {name: (value, write?, sequence template)}"""

    def __init__(self, path, type_name="file", parms=None, children=(), locked=False):
        self._path, self._type, self._children, self._locked = path, type_name, list(children), locked
        self._parms = {}
        for name, (value, write, sequence) in (parms or {}).items():
            parm = MagicMock()
            parm.name.return_value = name
            parm.eval.return_value = value
            parm.isDisabled.return_value = False
            parm.node.return_value = self
            parm.parmTemplate().tags.return_value = {"filechooser_mode": "write"} if write else {}
            parm.evalAtFrame.side_effect = (lambda f, t=sequence: t.format(frame=f)) if sequence else \
                (lambda f, v=value: v)
            self._parms[name] = parm

    def path(self):
        return self._path

    def children(self):
        return self._children

    def isLockedHDA(self):
        return self._locked

    def spareParms(self):
        return ()

    def type(self):
        return MagicMock(nameWithCategory=lambda: f"Sop/{self._type}", category=lambda: "Sop")

    def parm(self, name):
        return self._parms.get(name)


def test_missing_files_skip_outputs_existing_files_and_sequences(hou, monkeypatch, tmp_path):
    (tmp_path / "here.abc").write_text("")
    (tmp_path / "seq.1001.exr").write_text("")
    monkeypatch.setattr(hou, "ropNodeTypeCategory", lambda: "Driver", raising=False)
    looked_up = []

    def templates(node, include_hidden):
        looked_up.append(node.type().nameWithCategory())
        return list(node._parms)

    monkeypatch.setattr(paths, "_fileTemplateNames", templates)
    lost = _Node("/obj/geo/lost", parms={"file": ("/nowhere/lost.bgeo", False, None)})
    inside_asset = _Node("/obj/asset/inner", parms={"file": ("/nowhere/inner.bgeo", False, None)})
    scene = _Node("/", "root", children=[_Node("/obj", "obj", children=[
        lost,
        _Node("/obj/geo/abc", "alembic", parms={"fileName": ((tmp_path / "here.abc").as_posix(), False, None)}),
        _Node("/obj/geo/cache", "filecache", parms={"sopoutput": ("/nowhere/out.bgeo", True, None)}),
        _Node("/obj/geo/seq", parms={"file": ((tmp_path / "seq.0999.exr").as_posix(), False,
                                              tmp_path.as_posix() + "/seq.{frame}.exr")}),
        _Node("/obj/geo/op", parms={"file": ("op:/obj/geo/null1", False, None)}),
        _Node("/obj/asset", "myasset", children=[inside_asset], locked=True),
    ])])
    monkeypatch.setattr(hou, "node", lambda path: scene, raising=False)

    assert paths.missingFiles() == [(lost.parm("file"), "/nowhere/lost.bgeo")]
    assert looked_up.count("Sop/file") == 1  # parm templates once per node type
    assert "/obj/asset/inner" not in [p.node().path() for p in paths.sceneFileParms()]  # locked HDA not entered


def test_sop_import_prims_under_the_import_node_name(hou, monkeypatch):
    from conftest import ROOT
    from hotbox.common import panes
    from hotbox.utils import runner

    network = MagicMock()
    network.childTypeCategory().name.return_value = "Lop"
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    source = MagicMock()
    source.name.return_value = "OUT_rock"
    monkeypatch.setattr(hou, "node", lambda path: source, raising=False)
    hou.ui.getTextFromClipboard.return_value = "/obj/geo1/OUT_rock"
    created = MagicMock()
    network.createNode.return_value = created

    assert runner.runScript(ROOT / "lib" / "all" / "Lop" / "sop_import.py")

    network.createNode.assert_called_once_with("sopimport", "IMPORT_OUT_rock")
    created.parm("pathprefix").set.assert_any_call("/$OS")
    created.setUserData.assert_called_once_with("nodeshape", "chevron_up")


def _boxScene(hou, monkeypatch, answer):
    from conftest import ROOT
    from hotbox.common import panes

    pane = MagicMock()
    pane.visibleBounds().size.return_value = (10.0, 5.0)
    pane.screenBounds().size.return_value = (1000.0, 500.0)  # 100 px per unit
    monkeypatch.setattr(panes, "networkPane", lambda: pane)
    monkeypatch.setattr(hou, "Vector2", lambda x, y: (x, y), raising=False)
    parent = MagicMock()
    node, other = MagicMock(), MagicMock()
    node.name.return_value = "OUT"
    for item, position in ((node, (0.0, 0.0)), (other, (3.0, 1.7))):
        item.parent.return_value = parent
        item.position.return_value = position
        item.size.return_value = (1.0, 0.3)
    box = parent.createNetworkBox.return_value
    monkeypatch.setattr(hou, "selectedNodes", lambda: [node, other], raising=False)
    hou.ui.readMultiInput.return_value = answer
    return ROOT / "lib" / "single" / "network_box.py", node, box


def test_network_box_padding_in_pixels_remembered(hou, monkeypatch):
    from hotbox.common import layout
    from hotbox.utils import runner, settings

    monkeypatch.setattr(layout, "boxColor", lambda: "grey")

    script, node, box = _boxScene(hou, monkeypatch, (0, ("FX", "20")))
    assert runner.runScript(script)
    box.setComment.assert_called_once_with("FX")
    box.setPosition.assert_called_once_with((-0.2, -0.2))
    box.setAutoFit.assert_called_once_with(False)
    node.setPosition.assert_called_once_with((0.0, 0.0))  # back where it was after the box moved
    assert box.setSize.call_args.args[0] == pytest.approx((4.4, 2.0 + 0.4 + 0.22))  # + the 22 px title bar
    box.setColor.assert_called_once_with(layout.boxColor())
    assert settings.scriptSetting("network_box", "padding") == 20
    hou.ui.selectColor.assert_not_called()


def test_network_box_default_padding_and_picked_color(hou, monkeypatch):
    from hotbox.common import layout
    from hotbox.utils import runner

    monkeypatch.setattr(layout, "boxColor", lambda: "grey")

    script, _node, box = _boxScene(hou, monkeypatch, (1, ("FX", "15")))
    assert runner.runScript(script)
    assert hou.ui.readMultiInput.call_args.kwargs["initial_contents"] == ("OUT", "15")
    hou.ui.selectColor.assert_called_once_with(layout.boxColor())
    box.setColor.assert_called_once_with(hou.ui.selectColor.return_value)


def test_palette_color_after_black(hou, tmp_path, monkeypatch):
    from hotbox.common import layout

    palette = tmp_path / "opColorPalette.def"
    palette.write_text("3\n0 0 0\n0.188 0.188 0.188\n1 0 0\n", encoding="utf-8")
    monkeypatch.setattr(hou, "findFile", lambda name: palette.as_posix(), raising=False)
    monkeypatch.setattr(hou, "Color", lambda *rgb: rgb, raising=False)
    assert layout.boxColor() == (0.188, 0.188, 0.188)
    assert layout.paletteColors("0 0 0 255 51 0") == [(0, 0, 0), (1.0, 0.2, 0)]

    monkeypatch.setattr(hou, "findFile", lambda name: (_ for _ in ()).throw(hou.OperationFailed()), raising=False)
    assert layout.boxColor() == layout.BOX_GREY


def test_sticky_note_is_a_white_label(hou, monkeypatch):
    from hotbox.common import nodes

    monkeypatch.setattr(hou, "Color", lambda *rgb: rgb, raising=False)
    network = MagicMock()
    pane = MagicMock()
    pane.pwd.return_value = network
    note = nodes.addStickyNote([], pane)
    note.setDrawBackground.assert_called_once_with(False)
    note.setTextColor.assert_called_once_with((1.0, 1.0, 1.0))
    note.setTextSize.assert_called_once_with(nodes.NOTE_TEXT_SIZE)
