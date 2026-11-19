"""Cache Network's ROP network: the writer stored in the scene, its interface, the cache registry, old versions."""
import types
from unittest.mock import MagicMock

import pytest

KINDS = types.SimpleNamespace(Button="Button", Toggle="Toggle", Int="Int", String="String", Folder="Folder")


class Template:
    def __init__(self, name, label="", kind="Toggle", tags=None, default=0):
        self.name_, self.label_, self.kind, self.tags_, self.default = name, label, kind, dict(tags or {}), default

    def name(self):
        return self.name_

    def label(self):
        return self.label_

    def setLabel(self, label):
        self.label_ = label

    def tags(self):
        return dict(self.tags_)

    def type(self):
        return self.kind


class Parm:
    def __init__(self, name, value=0, template=None, at_frame=None):
        self.name_, self.value = name, value
        self.template = template or Template(name, kind="Int" if isinstance(value, int) else "String")
        self.at_frame = at_frame
        self.pressed = 0

    def name(self):
        return self.name_

    def eval(self):
        return self.value

    evalAsString = eval

    def evalAtFrame(self, frame):
        return self.at_frame(frame) if self.at_frame else self.value

    def set(self, value):
        self.value = value

    def parmTemplate(self):
        return self.template

    def pressButton(self):
        self.pressed += 1


class Node:
    scene: dict = {}  # noqa: RUF012  the fake scene, reset by the fixture

    def __init__(self, path, parms=(), bypassed=False):
        self.path_ = path
        self.parms_ = {p.name(): p for p in parms}
        self.user = {}
        self.bypassed = bypassed
        self.inputs_ = []
        self.rendered = []
        Node.scene[path] = self

    def path(self):
        return self.path_

    def name(self):
        return self.path_.rsplit("/", 1)[-1]

    def parm(self, name):
        return self.parms_.get(name)

    def parms(self):
        return list(self.parms_.values())

    def evalParm(self, name):
        return self.parms_[name].eval()

    def parmTuple(self, name):
        return (self.parms_.get(f"{name}1"),) if f"{name}1" in self.parms_ else None

    def evalParmTuple(self, name):
        return tuple(self.parms_[f"{name}{i}"].eval() for i in (1, 2, 3))

    def node(self, path):
        return Node.scene.get(path if path.startswith("/") else f"{self.path_}/{path}")

    def inputs(self):
        return list(self.inputs_)

    def setInput(self, index, node):
        while len(self.inputs_) <= index:
            self.inputs_.append(None)
        self.inputs_[index] = node

    def isBypassed(self):
        return self.bypassed

    def bypass(self, on):
        self.bypassed = on

    def userData(self, key):
        return self.user.get(key)

    def setUserData(self, key, value):
        self.user[key] = value

    def render(self, frame_range=None, method=None):
        self.rendered.append(frame_range)

    def setPosition(self, *args, **kwargs):
        pass

    setCurrent = setComment = setGenericFlag = setPosition


@pytest.fixture
def writer(hou, monkeypatch, tmp_path):
    from hotbox.common import cachewriter

    Node.scene = {}
    monkeypatch.setattr(hou, "parmTemplateType", KINDS, raising=False)
    monkeypatch.setattr(hou, "renderMethod", types.SimpleNamespace(RopByRop="RopByRop"), raising=False)
    monkeypatch.setattr(hou, "node", lambda path: Node.scene.get(path), raising=False)
    monkeypatch.setattr(hou, "frame", lambda: 1.0, raising=False)
    return cachewriter


def _rop(path, folder, start=1, end=4):
    return Node(path, [Parm("trange", 1), Parm("f1", start), Parm("f2", end), Parm("f3", 1),
                       Parm("sopoutput", f"{folder}/c.1.bgeo", at_frame=lambda f: f"{folder}/c.{f}.bgeo")])


def _network(cachewriter, tmp_path, names=("sim", "mesh")):
    """/g/write_caches with a Fetch per cache into the Merge, a toggle each, the options"""
    network = Node("/g/write_caches")
    merge = Node(f"/g/write_caches/{cachewriter.MERGE}")
    for k, name in enumerate(names):
        folder = tmp_path / name
        folder.mkdir()
        cache = Node(f"/g/{name}", [Parm("version", 1), Parm("reload", 0, Template("reload", kind="Button"))])
        rop = _rop(f"/g/{name}/render", folder.as_posix())
        fetch = Node(f"/g/write_caches/fetch_{name}", [Parm("source", rop.path())])
        fetch.user = {cachewriter.CACHE_KEY: cache.path(), cachewriter.VERSION_KEY: "version",
                      cachewriter.RELOAD_KEY: "reload"}
        merge.setInput(k, fetch)
        network.parms_[f"write_cache{k + 1}"] = Parm(f"write_cache{k + 1}", 1, Template(
            f"write_cache{k + 1}", name, tags={cachewriter.TOGGLE_TAG: fetch.name()}))
    group = MagicMock()
    network.parmTemplateGroup = lambda: group
    network.setParmTemplateGroup = MagicMock()
    return network, merge.inputs()


def test_frames_text_and_runs(writer):
    assert writer.frameRuns([1, 2, 3, 7, 8, 10]) == [(1, 3), (7, 8), (10, 10)]
    assert writer.frameRuns([1, 3, 5, 9], step=2) == [(1, 5), (9, 9)]
    assert writer.formatSize(1536) == "1.5 KB"
    status = {"frames": [1, 2, 3, 4], "missing": [3], "size": 2048, "path": "/x"}
    assert writer.describe(status) == "1-4, 2.0 KB, 3/4 frames"
    assert writer.describe({**status, "missing": []}) == "1-4, 2.0 KB, written"
    assert writer.describe({**status, "missing": [1, 2, 3, 4], "size": 0}) == "1-4, not written"


def test_cache_status_reads_the_folder(writer, tmp_path):
    for frame in (1, 2, 4):
        (tmp_path / f"c.{frame}.bgeo").write_bytes(b"x" * 10)
    status = writer.cacheStatus(_rop("/g/r", tmp_path.as_posix()))
    assert status["missing"] == [3] and status["size"] == 30 and status["files"] == 3 and status["step"] == 1
    current = _rop("/g/r2", tmp_path.as_posix())
    current.parms_["trange"].value = 0  # renders the current frame only
    assert writer.cacheStatus(current)["frames"] == [1]


def test_toggles_and_bypass_agree_off_wins(writer, tmp_path):
    network, (sim, mesh) = _network(writer, tmp_path)
    mesh.bypassed = True  # bypassed by hand in the network
    assert writer.sync(network) == [sim]
    assert network.parm("write_cache2").eval() == 0
    network.parm("write_cache1").set(0)
    assert writer.sync(network) == [] and sim.bypassed
    writer.checkAll(network, True)
    assert writer.sync(network) == [sim, mesh] and not mesh.bypassed


def test_write_checked_in_order_with_options(writer, hou, tmp_path):
    network, (_sim, _mesh) = _network(writer, tmp_path)
    sim_rop, mesh_rop = Node.scene["/g/sim/render"], Node.scene["/g/mesh/render"]
    for frame in (1, 2, 4):
        (tmp_path / "sim" / f"c.{frame}.bgeo").write_bytes(b"x")
    for frame in (1, 2, 3, 4):
        (tmp_path / "mesh" / f"c.{frame}.bgeo").write_bytes(b"x")
    network.parms_[writer.SKIP_EXISTING] = Parm(writer.SKIP_EXISTING, 1)

    report = writer.write(network)

    assert sim_rop.rendered == [(3, 3, 1)], "only the missing frame"
    assert mesh_rop.rendered == []
    assert [(name, done) for name, done, _ in report] == [("sim", "written 1 missing frame(s)"),
                                                          ("mesh", "skipped, all frames on disk")]
    assert Node.scene["/g/sim"].parm("reload").pressed == 1, "reloaded after writing"
    assert "Done, 2 of 2" in hou.ui.displayMessage.call_args.args[0]
    network.setParmTemplateGroup.assert_called()  # labels refreshed

    # version up first: everything written to the new version; unchecked caches are left alone
    network.parms_[writer.VERSION_UP] = Parm(writer.VERSION_UP, 1)
    network.parm("write_cache2").set(0)
    sim_rop.rendered.clear()
    report = writer.write(network)
    assert sim_rop.rendered == [None] and mesh_rop.rendered == []
    assert report[0][1] == "written (v2)" and Node.scene["/g/sim"].parm("version").eval() == 2


def test_write_goes_on_after_an_error_or_stops(writer, hou, tmp_path):
    network, (_sim, _mesh) = _network(writer, tmp_path)
    sim_rop, mesh_rop = Node.scene["/g/sim/render"], Node.scene["/g/mesh/render"]
    sim_rop.render = MagicMock(side_effect=hou.OperationFailed("Render failed"))
    report = writer.write(network)
    assert [done for _, done, _ in report] == ["failed: Render failed", "written"]
    assert mesh_rop.rendered == [None]
    assert "Finished with errors" in hou.ui.displayMessage.call_args.args[0]

    network.parms_[writer.KEEP_GOING] = Parm(writer.KEEP_GOING, 0)
    mesh_rop.rendered.clear()
    report = writer.write(network)
    assert len(report) == 1 and mesh_rop.rendered == []
    assert "not written: 1 cache(s) after it" in hou.ui.displayMessage.call_args.args[0]


def test_stored_writer_runs_from_the_callback(writer, hou, tmp_path):
    """The buttons exec the source kept in the scene: no hotbox needed"""
    from hotbox.common import caches

    network, (sim, _mesh) = _network(writer, tmp_path)
    network.setUserData(writer.USER_DATA, caches.writerSource())
    toggle = network.parm("write_cache1")
    toggle.set(0)
    exec(writer.callback("toggle"), {"hou": hou, "kwargs": {"node": network, "parm": toggle}})  # noqa: S102
    assert sim.bypassed
    exec(writer.callback("all"), {"hou": hou, "kwargs": {"node": network}})  # noqa: S102
    assert not sim.bypassed and toggle.eval() == 1


def test_interface_rebuilt_with_a_toggle_per_fetch(writer, hou, monkeypatch, tmp_path):
    from hotbox.common import caches

    network, (_sim, mesh) = _network(writer, tmp_path)
    mesh.bypassed = True
    network.parms_[writer.SKIP_EXISTING] = Parm(writer.SKIP_EXISTING, 1)
    made = []

    def template(kind):
        def make(name, label="", **kwargs):
            made.append((kind, name, label, kwargs))
            return MagicMock()
        return make

    for kind in ("ButtonParmTemplate", "ToggleParmTemplate", "SeparatorParmTemplate", "FolderParmTemplate"):
        monkeypatch.setattr(hou, kind, template(kind), raising=False)

    caches.buildInterface(network)

    toggles = [(name, label, kw["tags"]) for kind, name, label, kw in made if kind == "ToggleParmTemplate" and
               "tags" in kw]
    assert [(n, t) for n, _, t in toggles] == [("write_cache1", {writer.TOGGLE_TAG: "fetch_sim"}),
                                               ("write_cache2", {writer.TOGGLE_TAG: "fetch_mesh"})]
    assert toggles[0][1].startswith("sim   (1-4") and "not written" in toggles[0][1]
    buttons = {label: kw["script_callback"] for kind, _, label, kw in made if kind == "ButtonParmTemplate"}
    assert buttons[caches.WRITE_LABEL] == writer.callback("write")
    assert buttons["Select All"] == writer.callback("all") and buttons["Deselect All"] == writer.callback("none")
    assert network.parm(writer.SKIP_EXISTING).eval() == 1, "options keep their values"
    assert network.parm("write_cache2").eval() == 0, "toggles follow the bypass flags"
    assert network.userData(writer.USER_DATA) == caches.writerSource()


def test_new_caches_added_to_an_existing_network(writer, hou, monkeypatch, tmp_path):
    from hotbox.common import caches

    network, (_sim, _mesh) = _network(writer, tmp_path)
    network.createNode = lambda kind, name: Node(f"{network.path()}/{name}", [Parm("source", "")])
    monkeypatch.setattr(caches, "buildInterface", MagicMock())
    monkeypatch.setattr(hou, "Vector2", lambda *a: a, raising=False)
    monkeypatch.setattr(caches.cachetypes, "versionParm", lambda node: node.parm("version"))
    new_cache = Node("/g/foam", [Parm("version", 1)])
    new_rop = _rop("/g/foam/render", tmp_path.as_posix())

    created, already = caches.addToRopNetwork(network, [(Node.scene["/g/sim"], Node.scene["/g/sim/render"]),
                                                        (new_cache, new_rop)])

    assert already == [Node.scene["/g/sim"]]
    assert [f.name() for f in created] == ["fetch_foam"]
    merge = network.node(writer.MERGE)
    assert merge.inputs()[-1] is created[0] and len(merge.inputs()) == 3
    assert created[0].evalParm("source") == "/g/foam/render"
    assert created[0].userData(writer.CACHE_KEY) == "/g/foam" and created[0].userData(writer.VERSION_KEY) == "version"
    caches.buildInterface.assert_called_once_with(network)


def test_existing_network_or_a_new_one(hou, monkeypatch):
    from hotbox.common import caches

    parent, existing = MagicMock(), MagicMock()
    existing.name.return_value = "write_caches"
    monkeypatch.setattr(caches, "writeNetworks", lambda p: [existing])
    for answer, expected in ((0, existing), (1, None), (2, False)):
        hou.ui.displayMessage.return_value = answer
        assert caches.chooseRopNetwork(parent) is expected
    other = MagicMock()
    monkeypatch.setattr(caches, "writeNetworks", lambda p: [existing, other])
    hou.ui.selectFromList.return_value = (2,)
    assert caches.chooseRopNetwork(parent) is other
    hou.ui.selectFromList.return_value = (0,)
    assert caches.chooseRopNetwork(parent) is None
    hou.ui.selectFromList.return_value = ()
    assert caches.chooseRopNetwork(parent) is False
    monkeypatch.setattr(caches, "writeNetworks", lambda p: [])
    assert caches.chooseRopNetwork(parent) is None


def test_registry_feeds_every_tool():
    from hotbox.common import caches, cachetypes, paths

    for key in ("filecache", "bp::filecache", "s_cache"):
        assert key in cachetypes.CACHE_TYPES
    assert paths.RELOAD_TYPES == {"bp::filecache": "reload", "s_cache": "reload"}
    assert paths.CACHE_PATH_TYPES == {"bp::filecache": (), "s_cache": ()}
    node = MagicMock()
    node.type.return_value.nameComponents.return_value = ("", "bp", "filecache", "1.0")
    assert caches.typeKey(node) == "bp::filecache"
    node.type.return_value.nameComponents.return_value = ("", "", "s_cache", "11.0")
    assert caches.ropOf(node) is node.node.return_value
    node.node.assert_called_with("ropnet1/geo")


# --- old versions ---------------------------------------------------------------------------------------------------

def _versioned(tmp_path, monkeypatch, current=3):
    from hotbox.common import cachetypes, paths, versions

    for version in (1, 2, 3):
        folder = tmp_path / "geo" / f"v{version:03d}"
        folder.mkdir(parents=True)
        for frame in (1001, 1002):
            (folder / f"sim.{frame}.bgeo.sc").write_bytes(b"x" * 100)
    (tmp_path / "geo" / "v001" / "other.1001.bgeo.sc").write_bytes(b"keep")  # another cache, same folder
    node = MagicMock()
    version = Parm("version", current)
    file_parm = Parm("sopoutput", "", at_frame=lambda f: f"{tmp_path.as_posix()}/geo/v{version.eval():03d}/sim.{f}.bgeo.sc")
    file_parm.evalAsString = lambda: file_parm.evalAtFrame(1001)
    monkeypatch.setattr(cachetypes, "versionParm", lambda n: version)
    monkeypatch.setattr(paths, "mainFileParm", lambda n: file_parm)
    return versions, node, version


def test_versions_on_disk_and_the_old_ones(tmp_path, monkeypatch):
    versions, node, version = _versioned(tmp_path, monkeypatch)
    found = versions.versionsOnDisk(node)
    assert sorted(found) == [1, 2, 3]
    assert len(found[1]["files"]) == 2 and found[1]["size"] == 200, "only this cache's files"
    assert sorted(versions.oldVersions(node, keep=1)) == [1, 2]
    assert sorted(versions.oldVersions(node, keep=2)) == [1]
    version.set(1)  # the current version is always kept
    assert sorted(versions.oldVersions(node, keep=1)) == [2]


def test_delete_version_keeps_other_caches(tmp_path, monkeypatch):
    versions, node, _ = _versioned(tmp_path, monkeypatch)
    old = versions.oldVersions(node, keep=1)
    freed = sum(versions.deleteVersion(entry) for entry in old.values())
    assert freed == 400
    assert not (tmp_path / "geo" / "v002").exists(), "emptied version folder removed"
    assert [p.name for p in (tmp_path / "geo" / "v001").iterdir()] == ["other.1001.bgeo.sc"]
    assert len(list((tmp_path / "geo" / "v003").iterdir())) == 2


def test_clean_old_versions_asks_first(hou, tmp_path, monkeypatch):
    versions, node, _ = _versioned(tmp_path, monkeypatch)
    hou.ui.readInput.return_value = (0, "1")
    hou.ui.displayMessage.return_value = 1  # Cancel
    assert versions.cleanOldVersions([node]) == 0
    assert (tmp_path / "geo" / "v002").exists()
    assert "Delete 400 B of old versions" in hou.ui.displayMessage.call_args.args[0]
    hou.ui.displayMessage.return_value = 0
    assert versions.cleanOldVersions([node]) == 400


# --- Cache Report ---------------------------------------------------------------------------------------------------

def test_cache_report_lists_the_scene_caches(houdini, monkeypatch):
    from hotbox.utils import cachereport

    rows = [{"node": None, "path": "/obj/geo/sim", "name": "sim", "type": "filecache", "version": "3",
             "frames": "1001-1100", "disk": "100/100", "size": 3 * 1024 ** 3, "file": "/c/sim.$F.bgeo.sc",
             "state": "written"},
            {"node": None, "path": "/obj/geo/mesh", "name": "mesh", "type": "s_cache", "version": "1",
             "frames": "1001-1100", "disk": "0/100", "size": 0, "file": "/c/mesh.$F.bgeo.sc", "state": "missing"}]
    monkeypatch.setattr(cachereport, "sceneCaches", lambda: rows)
    window = cachereport.CacheReport(parent=houdini)
    assert window.table.rowCount() == 2
    texts = {window.table.item(r, 0).text(): window.table.item(r, 5).text() for r in range(2)}
    assert texts == {"/obj/geo/sim": "3.0 GB", "/obj/geo/mesh": ""}
    assert "2 cache node(s), 1 fully written, 3.0 GB" in window.summary.text()
    window.close()
