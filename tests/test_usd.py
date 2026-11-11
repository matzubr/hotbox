"""USD helpers that don't need pxr"""
from unittest.mock import MagicMock


def _node(path, inputs=(), modified=()):
    node = MagicMock()
    node.path.return_value = path
    node.inputs.return_value = list(inputs)
    node.lastModifiedPrims.return_value = list(modified)
    return node


def test_authoring_node_is_the_nearest_above(hou):
    from hotbox.common import usd

    matlib = _node("/stage/matlib", modified=["/materials/red"])
    older = _node("/stage/old", modified=["/materials/red"])
    matlib.inputs.return_value = [older]
    merge = _node("/stage/merge", inputs=[_node("/stage/geo"), matlib])

    assert [n.path() for n in usd.ancestors(merge)] == ["/stage/merge", "/stage/geo", "/stage/matlib", "/stage/old"]
    assert usd.authoringNode(merge, "/materials/red") is matlib
    assert usd.authoringNode(merge, "/materials/blue") is None


def test_material_use_and_report(hou):
    from hotbox.common import usd

    used, unbound = usd.materialUse([("/a", "/mtl/red"), ("/b", None), ("/c", "/mtl/red"), ("/d", "/mtl/blue")])

    assert used == {"/mtl/red": ["/a", "/c"], "/mtl/blue": ["/d"]} and unbound == ["/b"]
    report = usd.materialReport(used, unbound)
    assert report.splitlines()[0].split() == ["2", "/mtl/red"]  # most used first
    assert "No material: 1" in report and "/b" in report


def test_udim_textures_exist_when_any_tile_does(hou, tmp_path):
    from hotbox.common import usd

    (tmp_path / "wood.1001.exr").write_text("")
    assert usd.assetExists((tmp_path / "wood.<UDIM>.exr").as_posix())
    assert not usd.assetExists((tmp_path / "metal.<UDIM>.exr").as_posix())
    assert not usd.assetExists("")


def test_dependency_report_puts_missing_first(hou):
    from hotbox.common import usd

    found = [("layer", "shot.usd", "/show/shot.usd"), ("asset", "tex/a.exr", "")]
    text, missing = usd.dependencyReport(found, exists=lambda path: bool(path))

    assert missing == 1
    assert text.splitlines()[0] == "MISSING (1)" and "tex/a.exr" in text.splitlines()[1]


def test_variant_choices_current_first_with_parents(hou):
    from hotbox.common import usd

    def prim(path, sets, parent=None):
        p = MagicMock()
        p.IsValid.return_value = True
        p.GetPath.return_value = path
        p.GetParent.return_value = parent
        p.GetVariantSets().GetNames.return_value = list(sets)
        p.GetVariantSets().GetVariantSet.side_effect = lambda name: sets[name]
        return p

    def variant_set(current, names):
        s = MagicMock()
        s.GetVariantSelection.return_value = current
        s.GetVariantNames.return_value = names
        return s

    root = prim("/", {})
    asset = prim("/tree", {"lod": variant_set("high", ["low", "high"])}, parent=root)
    leaf = prim("/tree/leaf", {}, parent=asset)

    assert usd.variantChoices(leaf) == [("/tree", "lod", "high"), ("/tree", "lod", "low")]
