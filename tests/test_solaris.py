"""SOP / VDB imports into /obj/lopnet1"""
from unittest.mock import MagicMock

import pytest


def _menuParm(name, labels, items, kind="String"):
    parm = MagicMock()
    parm.name.return_value = name
    parm.menuLabels.return_value = labels
    parm.menuItems.return_value = items
    parm.parmTemplate().type().name.return_value = kind
    parm.parmTemplate().label.return_value = name
    return parm


@pytest.fixture
def lopnet(hou, monkeypatch):
    """No /obj/lopnet1 yet: /obj creates it"""
    from hotbox.common import solaris

    obj, network = MagicMock(), MagicMock()
    network.children.return_value = []
    obj.createNode.return_value = network
    monkeypatch.setattr(hou, "node", lambda path: obj if path == "/obj" else None, raising=False)
    monkeypatch.setattr(hou, "Vector2", lambda x, y: (x, y), raising=False)
    monkeypatch.setattr(solaris, "freePosition", lambda network, wanted, *a, **k: wanted)
    monkeypatch.setattr(solaris, "freeColumn", lambda network: MagicMock())
    return obj, network


def test_geometry_and_instance_velocity_blur_set_or_create():
    from hotbox.common import solaris

    blur = ["No Velocity Blur", "Velocity Blur", "Acceleration Blur"], ["off", "on", "accel"]
    controls = ["Set or Create", "Set if Exists", "Do Nothing"], ["set", "setexisting", "none"]
    geo = _menuParm("xn__primvarskarmaobjectvblur_7fbfg", *blur)
    geo_control = _menuParm("xn__primvarskarmaobjectvblur_control_8sbfg", *controls)
    instance = _menuParm("xn__primvarskarmaobjectinstance_vblur_7bfg", *blur)
    instance_control = _menuParm("xn__primvarskarmaobjectinstance_vblur_control_w7bfg", *controls)
    node = MagicMock()
    volume_mode = _menuParm("xn__primvarskarmaobjectvolumevblurmode_iwbfg", ["Lattice Deformation"], ["lattice"])
    node.parms.return_value = [_menuParm("primpattern", [], []), instance_control, geo, volume_mode, instance,
                               geo_control]

    assert solaris.setVelocityBlur(node) == []
    for value in (geo, instance):
        value.set.assert_called_once_with("on")
    for control in (geo_control, instance_control):
        control.set.assert_called_once_with("set")
    volume_mode.set.assert_not_called()


def test_missing_blur_parms_are_named():
    from hotbox.common import solaris

    node = MagicMock()
    node.parms.return_value = []
    assert solaris.setVelocityBlur(node) == ["vblur", "instance_vblur"]


def test_null_goes_to_a_new_lopnet_with_render_geometry_settings(hou, lopnet, monkeypatch):
    from hotbox.common import solaris

    obj, network = lopnet
    sop = MagicMock()
    monkeypatch.setattr(hou, "sopNodeTypeCategory", lambda: sop, raising=False)
    null = MagicMock()
    null.type().category.return_value = sop
    null.name.return_value = "OUT_rock"
    null.path.return_value = "/obj/geo1/OUT_rock"
    sop_import, settings = MagicMock(), MagicMock()
    sop_import.name.return_value = "IMPORT_OUT_rock"
    sop_import.parent.return_value = network
    import_parms = _withParms(sop_import, "soppath", "pathprefix")
    settings_parms = _withParms(settings, "primpattern")
    network.createNode.side_effect = [sop_import, settings]
    settings.relativePathTo.return_value = "../IMPORT_OUT_rock"
    settings.parms.return_value = []

    created = solaris.importSops([null])

    obj.createNode.assert_called_once_with("lopnet", "lopnet1")
    assert created == [(sop_import, settings)]
    network.createNode.assert_any_call("sopimport", "IMPORT_OUT_rock")
    network.createNode.assert_any_call("rendergeometrysettings", "RENDERGEO_OUT_rock")
    import_parms["soppath"].set.assert_called_once_with("/obj/geo1/OUT_rock")
    import_parms["pathprefix"].set.assert_called_once_with("/geo/OUT_rock")
    settings.setInput.assert_called_once_with(0, sop_import)
    settings_parms["primpattern"].set.assert_called_once_with('`chs("../IMPORT_OUT_rock/pathprefix")`')


def test_existing_lopnet_is_reused(hou, monkeypatch):
    from hotbox.common import solaris

    existing = MagicMock()
    monkeypatch.setattr(hou, "node", lambda path: existing if path == "/obj/lopnet1" else None, raising=False)
    assert solaris.lopNetwork() is existing


def _withParms(node, *names):
    """node.parm(name): a separate mock per name"""
    parms = {name: MagicMock(name=name) for name in names}
    node.parm.side_effect = parms.get
    return parms


def _sequenceParm(tmp_path, pattern):
    parm = MagicMock()
    parm.evalAtFrame.side_effect = lambda frame: pattern.format(frame=frame)
    parm.evalAsString.return_value = pattern.format(frame=1)
    return parm


def test_sequence_path_keeps_padding_and_the_hip_variable(hou, tmp_path, monkeypatch):
    from hotbox.common import solaris

    folder = tmp_path / "geo"
    folder.mkdir()
    for frame in (1001, 1002, 1040):
        (folder / f"smoke.{frame:04d}.vdb").touch()
    monkeypatch.setattr(hou, "text", MagicMock(expandString=lambda v: tmp_path.as_posix() if v == "$HIP" else v),
                        raising=False)
    parm = _sequenceParm(tmp_path, folder.as_posix() + "/smoke.{frame:04d}.vdb")

    assert solaris.sequencePath(parm) == ("$HIP/geo/smoke.$F4.vdb", (1001, 1040))


def test_unpadded_sequence_and_single_file(hou, tmp_path, monkeypatch):
    from hotbox.common import solaris

    monkeypatch.setattr(hou, "text", MagicMock(expandString=lambda v: v), raising=False)
    path, frames = solaris.sequencePath(_sequenceParm(tmp_path, "/cache/fire.{frame}.vdb"))
    assert (path, frames) == ("/cache/fire.$F.vdb", None)

    single = MagicMock()
    single.evalAtFrame.return_value = "/cache/still.vdb"
    single.evalAsString.return_value = "/cache/still.vdb"
    assert solaris.sequencePath(single) == ("/cache/still.vdb", None)


def test_volume_needs_a_vdb(hou, monkeypatch):
    from hotbox.common import panes, paths, solaris

    warnings = []
    monkeypatch.setattr(panes, "warn", warnings.append)
    parm = MagicMock()
    parm.evalAsString.return_value = "/cache/rock.bgeo.sc"
    monkeypatch.setattr(paths, "mainFileParm", lambda node: parm)
    node = MagicMock()
    node.name.return_value = "rock"

    assert solaris.importVolume(node) is None
    assert warnings == ["rock has no .vdb file"]


def test_volume_reads_the_cache_over_its_frame_range(hou, lopnet, monkeypatch):
    from hotbox.common import caches, paths, solaris

    _obj, network = lopnet
    parm = MagicMock()
    parm.evalAsString.return_value = "/cache/smoke.0001.vdb"
    monkeypatch.setattr(paths, "mainFileParm", lambda node: parm)
    monkeypatch.setattr(solaris, "sequencePath", lambda parm: ("$HIP/smoke.$F4.vdb", None))
    picked = []
    monkeypatch.setattr(caches, "setMenuByLabel", lambda parm, label: picked.append(label) or True)
    node = MagicMock()
    node.name.return_value = "smoke"
    node_parms = _withParms(node, "f1", "f2")
    node_parms["f1"].eval.return_value = 1001
    node_parms["f2"].eval.return_value = 1100
    volume = MagicMock()
    volume_parms = _withParms(volume, "filepath1", "primpath")
    network.createNode.return_value = volume
    frame_tuple = MagicMock()
    frame_tuple.parmTemplate().label.return_value = "Start/End/Inc"
    volume.parmTuples.return_value = [frame_tuple]

    assert solaris.importVolume(node) is volume
    network.createNode.assert_called_once_with("volume", "VOLUME_smoke")
    volume_parms["filepath1"].set.assert_called_once_with("$HIP/smoke.$F4.vdb")
    volume_parms["primpath"].set.assert_called_once_with("/vol/smoke")
    assert picked == ["Sample Frame Range"]
    frame_tuple.set.assert_called_once_with((1001, 1100, 1))
