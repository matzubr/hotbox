"""Buttons from the AwesomeHoudini libraries and Snap to Grid: helpers in common/ and the lib scripts."""
import os
import time
from unittest.mock import MagicMock

import pytest
from conftest import ROOT
from hotbox.common import hipfile, layout, nodes, paths, wedge
from hotbox.utils import runner, scripts


class Vec(tuple):
    """hou.Vector2 stand-in: indexable, + and -"""

    def __new__(cls, x, y):
        return super().__new__(cls, (float(x), float(y)))

    def __add__(self, other):
        return Vec(self[0] + other[0], self[1] + other[1])

    def __sub__(self, other):
        return Vec(self[0] - other[0], self[1] - other[1])


@pytest.fixture
def vec(hou, monkeypatch):
    monkeypatch.setattr(hou, "Vector2", Vec, raising=False)
    return Vec


def _item(path, x, y, w=1.0, h=0.3):
    item = MagicMock()
    item.path.return_value = path
    item.name.return_value = path.rsplit("/", 1)[-1]
    item.position.return_value = Vec(x, y)
    item.size.return_value = (w, h)
    item.setPosition.side_effect = lambda pos: item.position.configure_mock(return_value=Vec(*pos))
    return item


# --- scene file ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("name", "expected"), [
    ("shot_v012.hip", "shot_v013.hip"),
    ("shot_v9.hiplc", "shot_v10.hiplc"),
    ("shot_V007_comp.hip", "shot_V008_comp.hip"),
    ("v2_shot_v004.hip", "v2_shot_v005.hip"),  # the last version in the name
    ("shot.hip", "shot_v001.hip"),
])
def test_incremented_hip_names(tmp_path, name, expected):
    assert hipfile.incrementedPath(tmp_path / name) == tmp_path / expected


def test_next_free_version_skips_saved_ones(tmp_path):
    (tmp_path / "shot_v002.hip").touch()
    (tmp_path / "shot_v003.hip").touch()
    assert hipfile.nextFreePath(tmp_path / "shot_v001.hip").name == "shot_v004.hip"


def test_recovery_files_newest_first(tmp_path):
    temp, hip = tmp_path / "temp", tmp_path / "shot"
    (hip / "backup").mkdir(parents=True)
    temp.mkdir()
    old = temp / "crash.shot_user_123.hip"
    backup = hip / "backup" / "shot_v003_bak2.hip"
    other = hip / "backup" / "other_bak1.hip"  # backup of another scene
    for i, path in enumerate([old, backup, other, temp / "crash.notes.txt"]):
        path.touch()
        os.utime(path, (time.time() + i, time.time() + i))
    assert hipfile.recoveryFiles(hip / "shot_v003.hip", temp) == [backup, old]
    assert hipfile.recoveryFiles(None, temp) == [old]


def test_existing_folder_of_a_file_not_written_yet(tmp_path):
    assert hipfile.existingFolder(tmp_path / "cache" / "v001" / "geo.0001.bgeo.sc") == tmp_path
    (tmp_path / "a.hip").touch()
    assert hipfile.existingFolder(tmp_path / "a.hip") == tmp_path


# --- grid ----------------------------------------------------------------------------------------------------------

def test_grid_step_from_the_network_editor_prefs():
    pane = MagicMock()
    pane.getPref.side_effect = {"gridxstep": "2.5", "gridystep": "0.5"}.get
    assert layout.gridStep(pane) == (2.5, 0.5)
    pane.getPref.side_effect = {"gridxstep": "", "gridystep": "-1"}.get
    assert layout.gridStep(pane) == layout.DEFAULT_GRID
    assert layout.gridStep(None) == layout.DEFAULT_GRID


def _overlap(a, b):
    return layout._overlaps(a, b, 0)


def test_snap_puts_centers_on_the_nearest_grid_point():
    (x, y), = layout.snapRects([(1.3, 2.2, 1.0, 0.3)], [], (2.0, 1.0))
    assert (x + 0.5, y + 0.15) == pytest.approx((2.0, 2.0))


def test_snapped_nodes_never_overlap_each_other_or_other_nodes():
    step = (2.0, 1.0)
    rects = [(0.1, 0.0, 1.0, 0.3), (0.3, 0.1, 1.0, 0.3), (-0.2, -0.1, 1.2, 0.4)]  # all want the point (0, 0)
    obstacle = (-0.5, -1.15, 1.0, 0.3)  # a node already on the point (0, -1)
    placed = layout.snapRects(rects, [obstacle], step)
    boxes = [(x, y, w, h) for (x, y), (_, _, w, h) in zip(placed, rects)]
    for i, a in enumerate(boxes):
        assert not _overlap(a, obstacle)
        for b in boxes[i + 1:]:
            assert not _overlap(a, b)
        cx, cy = a[0] + a[2] / 2, a[1] + a[3] / 2
        assert cx / step[0] == pytest.approx(round(cx / step[0]))
        assert cy / step[1] == pytest.approx(round(cy / step[1]))
    assert boxes[1][0] + 0.5 == pytest.approx(0.0)  # the top one keeps the nearest point
    assert max(abs(b[0] + b[2] / 2) for b in boxes) <= 2.0  # the others go to neighbour points


def test_snap_to_grid_moves_only_the_selected_items(hou, vec):
    a, b = _item("/obj/geo1/a", 0.3, 0.1), _item("/obj/geo1/b", 0.2, -0.05)
    other = _item("/obj/geo1/other", -0.5, -1.15)
    parent = MagicMock()
    parent.children.return_value = [a, b, other]
    parent.networkDots.return_value = []
    for item in (a, b, other):
        item.parent.return_value = parent
    pane = MagicMock()
    pane.getPref.side_effect = {"gridxstep": "2", "gridystep": "1"}.get

    assert layout.snapToGrid([a, b], pane) == 2
    other.setPosition.assert_not_called()
    rects = [layout.itemRect(i) for i in (a, b, other)]
    assert not any(_overlap(rects[i], rects[j]) for i in range(3) for j in range(i + 1, 3))


def test_make_space(hou, vec):
    a, b, c = _item("/n/a", 0, 0), _item("/n/b", 0, -1), _item("/n/c", 4, -3)
    parent = MagicMock()
    parent.children.return_value = [a, b, c]
    parent.networkDots.return_value = []
    a.parent.return_value = parent
    layout.makeSpace(a)  # everything below goes down two rows
    assert a.position() == (0, 0)
    assert b.position() == (0, -3)
    assert c.position() == (4, -5)


# --- nodes ---------------------------------------------------------------------------------------------------------

def test_node_from_clipboard_text(hou, monkeypatch):
    geo = MagicMock(name="geo")
    found = {"/obj/geo1": geo}
    parm = MagicMock()
    monkeypatch.setattr(hou, "node", found.get, raising=False)
    monkeypatch.setattr(hou, "parm", {"/obj/geo1/tx": parm}.get, raising=False)
    assert nodes.nodeFromText("/obj/geo1") is geo
    assert nodes.nodeFromText('ch("/obj/geo1/tx")') is parm.node.return_value
    assert nodes.nodeFromText("hello") is None
    assert nodes.nodeFromText("") is None


def test_help_summary_and_page_names():
    text = '= Null =\n\n#type: node\n\n"""Does nothing:\n   passes the geometry."""\n\nMore.'
    assert nodes.helpSummary(text) == "Does nothing: passes the geometry."
    assert nodes.helpSummary("no summary") is None
    node_type = MagicMock()
    node_type.category.return_value.name.return_value = "Sop"
    node_type.nameComponents.return_value = ("", "", "filecache", "2.0")
    assert nodes.helpFileNames(node_type) == ["sop/filecache-2.0.txt", "sop/filecache.txt"]
    node_type.nameComponents.return_value = ("", "labs", "tool", "1.0")
    assert nodes.helpFileNames(node_type) == ["sop/labs--tool-1.0.txt", "sop/labs--tool.txt", "sop/tool.txt"]


def test_help_summary_from_houdini_help_archive(hou, monkeypatch, tmp_path):
    import zipfile

    archive = tmp_path / "houdini" / "help" / "nodes.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("sop/null.txt", '"""Does nothing."""')
    monkeypatch.setattr(hou, "getenv", lambda name, default=None: str(tmp_path) if name == "HFS" else default)
    node_type = MagicMock()
    node_type.embeddedHelp.return_value = ""
    node_type.category.return_value.name.return_value = "Sop"
    node_type.nameComponents.return_value = ("", "", "null", "")
    assert nodes.nodeHelpSummary(node_type) == "Does nothing."


def test_toggle_bypass():
    a, b = MagicMock(), MagicMock()
    a.isBypassed.return_value, b.isBypassed.return_value = True, False
    assert nodes.toggleBypass([a, b]) is True
    a.bypass.assert_called_with(True)
    b.isBypassed.return_value = True
    assert nodes.toggleBypass([a, b]) is False
    assert nodes.toggleBypass([]) is None


def test_select_modified_adds_the_next_older_node(hou, monkeypatch):
    network = MagicMock()
    ages = {"new": 30, "mid": 20, "old": 10}
    children = []
    for name, stamp in ages.items():
        node = _item(f"/obj/{name}", 0, 0)
        node.modificationTime.return_value = stamp
        node.parent.return_value = network
        children.append(node)
    network.children.return_value = children
    pane = MagicMock()
    pane.pwd.return_value = network
    monkeypatch.setattr(nodes.panes, "networkPane", lambda: pane)
    new, mid, _old = children
    assert nodes.selectModified([]) == [new]
    assert nodes.selectModified([new]) == [new, mid]


def test_compile_block_wraps_a_chain(hou, vec, monkeypatch):
    """in -> a -> b -> out: a and b get a Compile Begin from 'in' and a Compile End into 'out'"""
    sop = object()
    monkeypatch.setattr(hou, "sopNodeTypeCategory", lambda: sop, raising=False)
    network = MagicMock()
    network.childTypeCategory.return_value = sop
    created = []

    def node(name, x=0, y=0):
        n = _item(f"/obj/geo1/{name}", x, y)
        n.parent.return_value = network
        n.type.return_value.name.return_value = name.rstrip("0123456789")
        n.inputs_ = {}
        n.setInput.side_effect = lambda i, src, out=0: n.inputs_.__setitem__(i, src)
        return n

    def connection(src, dst, index=0):
        c = MagicMock()
        c.inputItem.return_value = c.inputNode.return_value = src
        c.outputNode.return_value = dst
        c.inputIndex.return_value, c.outputIndex.return_value = index, 0
        return c

    source, a, b, out = node("in", 0, 2), node("a", 0, 1), node("b", 0, 0), node("out", 0, -1)
    a.inputConnections.return_value = [connection(source, a)]
    b.inputConnections.return_value = [connection(a, b)]
    a.outputs.return_value, b.outputs.return_value = [b], [out]
    b.outputConnections.return_value = [connection(b, out)]

    def createNode(node_type):
        n = node(f"{node_type}{len(created) + 1}")
        created.append(n)
        return n

    network.createNode.side_effect = createNode
    network.children.side_effect = lambda: [source, a, b, out, *created]

    begins, end = nodes.compileBlock([a, b])
    assert len(begins) == 1
    assert end.inputs_[0] is b and out.inputs_[0] is end
    assert a.inputs_[0] is begins[0] and begins[0].inputs_[0] is source
    begins[0].parm.return_value.set.assert_called_once()


def test_compile_block_needs_one_end(hou, monkeypatch):
    sop = object()
    monkeypatch.setattr(hou, "sopNodeTypeCategory", lambda: sop, raising=False)
    network = MagicMock()
    network.childTypeCategory.return_value = sop
    a, b = _item("/x/a", 0, 0), _item("/x/b", 1, 0)
    for n in (a, b):
        n.parent.return_value = network
        n.outputs.return_value = []
    with pytest.raises(ValueError, match="one node"):
        nodes.compileBlock([a, b])


# --- files ---------------------------------------------------------------------------------------------------------

class _Parm:
    def __init__(self, template):
        self.template = template

    def evalAtFrame(self, frame):
        return self.template.format(frame=f"{frame:04d}")

    def evalAsString(self):
        return self.evalAtFrame(1)


def test_cache_files_and_size(tmp_path):
    for frame in (1, 2, 3):
        (tmp_path / f"geo.{frame:04d}.bgeo.sc").write_bytes(b"x" * 1024)
    (tmp_path / "geo_other.0001.bgeo.sc").write_bytes(b"x")
    files = paths.cacheFiles(_Parm(f"{tmp_path.as_posix()}/geo.{{frame}}.bgeo.sc"))
    assert len(files) == 3
    single = tmp_path / "static.bgeo.sc"
    single.write_bytes(b"x")
    assert paths.cacheFiles(_Parm(single.as_posix())) == [single.as_posix()]
    assert paths.formatSize(3 * 1024) == "3.0 KB"
    assert paths.formatSize(12) == "12 B"
    assert paths.formatSize(5 * 1024 ** 3) == "5.0 GB"


def test_mplay_sequence_argument(tmp_path):
    from hotbox.common import mplay

    for frame in (1, 2):
        (tmp_path / f"beauty.{frame:04d}.exr").touch()
    assert mplay.sequenceArgument(_Parm(f"{tmp_path.as_posix()}/beauty.{{frame}}.exr")) == \
        f"{tmp_path.as_posix()}/beauty.$F4.exr"
    assert paths.isImageFile("a/b.0001.EXR")
    assert not paths.isImageFile("a/b.bgeo.sc")


def test_wedge_finds_parameters_by_label():
    def tuple_(name, label, kind="Float"):
        t = MagicMock()
        t.name.return_value = name
        t.parmTemplate.return_value.label.return_value = label
        t.parmTemplate.return_value.type.return_value.name.return_value = kind
        return t

    node = MagicMock()
    node.parmTuples.return_value = [tuple_("wedgecount", "Wedge Count", "Int"), tuple_("name1", "Attribute Name", "String"),
                                    tuple_("name12", "Attribute Name", "String")]
    assert wedge.parmByLabel(node, "Attribute Name", 12).name() == "name12"
    assert wedge.parmByLabel(node, "Attribute Name", 1).name() == "name1"
    assert wedge.parmByLabel(node, "Attribute Name", 2) is None
    assert wedge.parmByLabel(node, "Wedge Count").name() == "wedgecount"


# --- the lib -------------------------------------------------------------------------------------------------------

NEW_PACKAGES = {"qLib", "Aelib", "LV-Tools", "BeeHou", "AutoCacheOut", "HelpToComment"}


@pytest.mark.parametrize("mode", scripts.MODES)
def test_lib_scripts_compile_refs_resolve_and_hotkeys_dont_clash(mode):
    lib = ROOT / "lib"
    library = scripts.scanLibrary([lib], mode)
    for script in library:
        assert script.error is None, f"{script.relpath}: {script.error}"
        compile(script.runPath.read_text(encoding="utf-8"), str(script.runPath), "exec")
        if script.hotkey:
            assert scripts.hotkeyConflicts(library, script, script.hotkey) == [], f"{mode}/{script.relpath}"
        for package in script.packages:
            assert package in NEW_PACKAGES | {"blackpoint", "trehmer"}
        icon = script.icon or ""
        if icon.endswith(".svg"):
            assert (ROOT / "icons" / icon).is_file(), icon


def test_snap_to_grid_script_runs(hou, vec, monkeypatch):
    item = _item("/obj/geo1/a", 0.3, 0.1)
    item.outputs.return_value = []
    parent = MagicMock()
    parent.children.return_value = [item]
    parent.networkDots.return_value = []
    item.parent.return_value = parent
    monkeypatch.setattr(hou, "selectedItems", lambda: [item], raising=False)
    monkeypatch.setattr(nodes.panes, "networkPane", lambda: None)
    assert runner.runScript(ROOT / "lib" / "multiple" / "snap_to_grid.py")
    assert item.position() == pytest.approx((-0.5 + 0.0625, -0.15))  # the drawn body centered on the line


def test_snap_keeps_nudged_items_in_place():
    """An item already snapped (nudged) stays where it is"""
    nudge = layout.BODY_NUDGE
    rect = (-0.5 + nudge[0], -0.15, 1.0, 0.3)
    assert layout.snapRects([rect], [], (2.0, 1.0), nudge=nudge) == [pytest.approx(rect[:2])]


def _tuple(name, label, kind="Float"):
    t = MagicMock()
    t.name.return_value = name
    t.parmTemplate.return_value.label.return_value = label
    t.parmTemplate.return_value.type.return_value.name.return_value = kind
    return t


def test_wedge_target_parameter_turns_on_its_checkbox():
    checkbox, field = _tuple("exportchannel2", "", "Toggle"), _tuple("channel2", "Target Parameter", "String")
    other = _tuple("channel1", "Target Parameter", "String")
    wedge_node = MagicMock()
    wedge_node.parmTuples.return_value = [other, checkbox, field]
    assert wedge.setTargetParameter(wedge_node, 2, "/obj/geo1/box1/sizex")
    field.set.assert_called_once_with(("/obj/geo1/box1/sizex",))
    checkbox.set.assert_called_once_with((1,))
    other.set.assert_not_called()


def test_wedge_overwrite_toggle_and_connection(vec):
    overwrite = _tuple("overwritetarget", "Overwrite Target Parameter on  Work Item Selection", "Toggle")
    node = MagicMock()
    node.parmTuples.return_value = [overwrite]
    assert wedge.setToggle(node, wedge.OVERWRITE_LABEL)
    overwrite.set.assert_called_once_with((1,))



def test_wedge_chain_geometry_import_wedge_rop(hou, vec, monkeypatch):
    sop = object()
    monkeypatch.setattr(hou, "sopNodeTypeCategory", lambda: sop, raising=False)
    importer, scheduler = MagicMock(), MagicMock()
    importer.type.return_value.name.return_value = "geometryimport"
    scheduler.type.return_value.name.return_value = "localscheduler"
    importer.position.return_value = Vec(0, 0)
    topnet = MagicMock()
    topnet.children.return_value = [scheduler, importer]
    rop = MagicMock()
    rop.childTypeCategory.return_value = sop
    external, output = _tuple("usesoppath", "Use External SOP", "Toggle"), _tuple("sopoutput", "Output File", "String")
    rop.parmTuples.return_value = [external, output]
    topnet.createNode.return_value = rop
    wedge_node = MagicMock()
    wedge_node.position.return_value = Vec(0, -1.5)
    node = MagicMock()
    node.type.return_value.category.return_value = sop
    node.parent.return_value.displayNode.return_value.name.return_value = "OUT"
    node.parent.return_value.displayNode.return_value.path.return_value = "/obj/geo1/OUT"

    assert wedge.buildChain(topnet, wedge_node, node) == []
    wedge_node.setInput.assert_called_once_with(0, importer)
    rop.setInput.assert_called_once_with(0, wedge_node)
    external.set.assert_called_once_with((0,))
    output.set.assert_called_once_with(("$HIP/geo/wedge/OUT/OUT.`@wedgeindex`.$F4.bgeo.sc",))
    rop.createNode.assert_called_once_with("object_merge", "IMPORT_OUT")
    rop.createNode.return_value.parm.return_value.set.assert_called_once_with("/obj/geo1/OUT")


def test_wedge_indices_found_on_disk(tmp_path):
    folder = tmp_path / "geo" / "wedge" / "OUT"
    folder.mkdir(parents=True)
    for index in (0, 1, 3):
        for frame in (1, 2):
            (folder / f"OUT.{index}.{frame:04d}.bgeo.sc").touch()
    (folder / "OUT.x.0001.bgeo.sc").touch()
    raw = "$HIP/geo/wedge/OUT/OUT.`@wedgeindex`.$F4.bgeo.sc"
    expand = lambda text: text.replace("$HIP", tmp_path.as_posix())
    assert wedge.wedgeIndicesOnDisk(raw, expand) == [0, 1, 3]
    assert wedge.wedgePath(raw, 3) == "$HIP/geo/wedge/OUT/OUT.3.$F4.bgeo.sc"
    assert wedge.wedgeIndicesOnDisk("$HIP/static.bgeo.sc", expand) == []


def test_load_wedges_makes_file_nodes_and_a_switch(hou, vec, monkeypatch):
    sop = object()
    monkeypatch.setattr(hou, "sopNodeTypeCategory", lambda: sop, raising=False)
    monkeypatch.setattr(wedge, "wedgeIndicesOnDisk", lambda raw: [0, 2])
    output = _tuple("sopoutput", "Output File", "String")
    output.__getitem__ = lambda self, i: output_parm
    output_parm = MagicMock()
    output_parm.unexpandedString.return_value = "$HIP/w/OUT.`@wedgeindex`.$F4.bgeo.sc"
    rop = MagicMock()
    rop.parmTuples.return_value = [output]
    network = rop.parent.return_value.parent.return_value
    network.childTypeCategory.return_value = sop
    network.children.return_value = []
    rop.parent.return_value.position.return_value = Vec(0, 0)
    created = []

    def createNode(node_type, name):
        node = _item(f"/obj/geo1/{name}", 0, 0)
        node.type_ = node_type
        created.append(node)
        return node

    network.createNode.side_effect = createNode
    files = wedge.loadWedges(rop)
    assert [n.name() for n in files] == ["wedge_0", "wedge_2"]
    files[1].parm.return_value.set.assert_called_with("$HIP/w/OUT.2.$F4.bgeo.sc")
    switch = created[-1]
    assert switch.type_ == "switch"
    switch.setInput.assert_any_call(1, files[1])
