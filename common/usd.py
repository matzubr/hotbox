"""USD stage helpers for the LOP scripts: the stage the network shows, prims picked in the viewer, materials,
variants, asset dependencies. pxr is imported inside the functions: the pure parts are tested without it."""
from __future__ import annotations

import glob
import os
import re
import tempfile
from pathlib import Path

import hou

from . import panes
from .solaris import parmByLabel

UDIM = re.compile(r"<UDIM>|%\(UDIM\)d|_MAPID_|<UVTILE>", re.IGNORECASE)
PRIMS_PARM = "Primitives"  # label of the prim pattern of Prune, Configure Primitive, Edit Properties...


# --- what is shown -------------------------------------------------------------------------------------------------

def displayNode():
    """The LOP with the display flag in the network under the cursor (None outside LOPs)"""
    pane = panes.networkPane()
    network = pane.pwd() if pane is not None else None
    if network is None or network.childTypeCategory() != hou.lopNodeTypeCategory():
        return None
    return network.displayNode()


def pickedPaths() -> list[str]:
    """Prim paths selected in the Scene Viewer (LOPs)"""
    viewer = panes.sceneViewer()
    if viewer is None:
        return []
    try:
        return [str(path) for path in viewer.currentSceneGraphSelection()]
    except (AttributeError, hou.OperationFailed):
        return []


def pick(paths) -> bool:
    """Select prims in the Scene Viewer"""
    viewer = panes.sceneViewer()
    if viewer is None:
        return False
    try:
        viewer.setCurrentSceneGraphSelection([str(p) for p in paths])
    except (AttributeError, hou.OperationFailed):
        return False
    return True


def ancestors(node) -> list:
    """The node and every node above it (inputs first, breadth first), each once"""
    found, queue, seen = [], [node], set()
    while queue:
        current = queue.pop(0)
        if current is None or current.path() in seen:
            continue
        seen.add(current.path())
        found.append(current)
        queue += list(current.inputs())
    return found


def authoringNode(node, prim_path: str):
    """The nearest node above (or) node that last changed the prim (lastModifiedPrims)"""
    for current in ancestors(node):
        try:
            modified = {str(p) for p in current.lastModifiedPrims()}
        except (AttributeError, hou.OperationFailed):
            continue
        if prim_path in modified:
            return current
    return None


def appendNode(node, node_type: str, name: str | None = None):
    """A new LOP under node (wired, displayed, selected)"""
    new = node.createOutputNode(node_type, name) if name else node.createOutputNode(node_type)
    new.moveToGoodPosition()
    new.setDisplayFlag(True)
    new.setSelected(True, clear_all_selected=True)
    return new


def setPrims(node, paths) -> bool:
    """The 'Primitives' pattern of a LOP (by label: the parm name differs between nodes)"""
    parm = parmByLabel(node, PRIMS_PARM) or node.parm("primpattern")
    if parm is None:
        return False
    parm.set(" ".join(paths))
    return True


# --- materials -----------------------------------------------------------------------------------------------------

def boundMaterial(prim) -> str | None:
    from pxr import UsdShade

    material, _relationship = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
    return str(material.GetPath()) if material else None


def geometryPrims(stage):
    from pxr import Usd, UsdGeom

    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.Gprim):
            yield prim


def materialUse(pairs) -> tuple[dict[str, list[str]], list[str]]:
    """[(prim path, material or None)] -> ({material: [prims]}, [prims without a material])"""
    used: dict[str, list[str]] = {}
    unbound = []
    for prim_path, material in pairs:
        if material:
            used.setdefault(material, []).append(prim_path)
        else:
            unbound.append(prim_path)
    return used, unbound


def materialReport(used: dict[str, list[str]], unbound: list[str], limit: int = 40) -> str:
    lines = [f"{len(prims):>5}  {material}" for material, prims in sorted(used.items(), key=lambda i: -len(i[1]))]
    if unbound:
        lines += ["", f"No material: {len(unbound)}", *(f"       {p}" for p in unbound[:limit])]
        if len(unbound) > limit:
            lines.append(f"       … and {len(unbound) - limit} more")
    return "\n".join(lines)


# --- variants ------------------------------------------------------------------------------------------------------

def variantChoices(prim) -> list[tuple[str, str, str]]:
    """[(prim path, variant set, variant)] of the prim and its ancestors with variant sets, the current one first"""
    choices = []
    while prim and prim.IsValid() and str(prim.GetPath()) != "/":
        sets = prim.GetVariantSets()
        for set_name in sets.GetNames():
            variant_set = sets.GetVariantSet(set_name)
            current = variant_set.GetVariantSelection()
            names = variant_set.GetVariantNames()
            for name in sorted(names, key=lambda n: n != current):
                choices.append((str(prim.GetPath()), set_name, name))
        prim = prim.GetParent()
    return choices


def setVariant(node, prim_path: str, set_name: str, variant: str):
    """A Set Variant LOP under node; the multiparm entry by label, the names as fallback"""
    new = appendNode(node, "setvariant")
    count = new.parm("num_variants") or new.parm("variants")
    if count is not None and count.eval() < 1:
        count.set(1)
    values = {("Primitives", "primpattern1"): prim_path, ("Variant Set", "variantset1"): set_name,
              ("Variant Name", "variantname1"): variant}
    missing = []
    for (label, name), value in values.items():
        parm = new.parm(name) or parmByLabel(new, label)
        if parm is None:
            missing.append(name)
        else:
            parm.set(value)
    return new, missing


# --- asset dependencies --------------------------------------------------------------------------------------------

def assetExists(path: str) -> bool:
    """A file on disk; UDIM / UV tile patterns: any tile"""
    if not path:
        return False
    if UDIM.search(path):
        return bool(glob.glob(UDIM.sub("*", glob.escape(path))))
    return os.path.exists(path)


def _resolve(path: str, layer) -> str:
    from pxr import Ar, Sdf

    if not path:
        return ""
    if UDIM.search(path):  # the resolver doesn't know tiles: anchor it ourselves
        return path if os.path.isabs(path) else Sdf.ComputeAssetPathRelativeToLayer(layer, path)
    return str(Ar.GetResolver().Resolve(Sdf.ComputeAssetPathRelativeToLayer(layer, path)) or "")


def dependencies(stage) -> list[tuple[str, str, str]]:
    """[(kind, path as authored, resolved path or '')]: layers, references, payloads, asset attributes"""
    from pxr import Sdf

    found, seen = [], set()

    def add(kind, authored, resolved):
        key = (kind, resolved or authored)
        if authored and key not in seen:
            seen.add(key)
            found.append((kind, authored, resolved))

    for layer in stage.GetUsedLayers():
        if not layer.anonymous:
            add("layer", layer.identifier, layer.realPath or "")

        def visit(path, layer=layer):
            spec = layer.GetObjectAtPath(path)
            if isinstance(spec, Sdf.PrimSpec):
                for kind, items in (("reference", spec.referenceList.GetAddedOrExplicitItems()),
                                    ("payload", spec.payloadList.GetAddedOrExplicitItems())):
                    for item in items:
                        if item.assetPath:
                            add(kind, item.assetPath, _resolve(item.assetPath, layer))
            elif isinstance(spec, Sdf.AttributeSpec) and spec.typeName == Sdf.ValueTypeNames.Asset:
                values = [spec.default] + [layer.QueryTimeSample(path, t) for t in layer.ListTimeSamplesForPath(path)]
                for value in values:
                    if isinstance(value, Sdf.AssetPath) and value.path:
                        add("asset", value.path, value.resolvedPath or _resolve(value.path, layer))

        layer.Traverse(Sdf.Path.absoluteRootPath, visit)
    return found


def dependencyReport(found, exists=assetExists) -> tuple[str, int]:
    """Missing ones first. (text, number missing)"""
    missing = [d for d in found if not exists(d[2])]
    present = [d for d in found if exists(d[2])]
    lines = []
    if missing:
        lines += [f"MISSING ({len(missing)})", *(f"  {kind:<9} {authored}" for kind, authored, _ in missing), ""]
    lines += [f"Found ({len(present)})", *(f"  {kind:<9} {resolved}" for kind, _, resolved in present)]
    return "\n".join(lines), len(missing)


# --- layers to text ------------------------------------------------------------------------------------------------

def dumpPath(node, what: str) -> Path:
    folder = Path(hou.getenv("HOUDINI_TEMP_DIR") or tempfile.gettempdir()) / "hotbox"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{node.name()}_{what}.usda"


def openFile(path: Path) -> None:
    """The file in the system's app for it"""
    import subprocess
    import sys

    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


# --- collections ---------------------------------------------------------------------------------------------------

def collectionName(text: str) -> str:
    """A valid USD name: 'hero props!' -> 'hero_props'; a leading digit gets '_'"""
    name = re.sub(r"\W+", "_", text.strip()).strip("_") or "collection"
    return f"_{name}" if name[0].isdigit() else name


def _parmLike(node, labels, name_parts):
    """A parm by one of the labels (case-insensitive), else by a part of its name"""
    wanted = {label.casefold() for label in labels}
    parms = node.parms()
    found = next((p for p in parms if p.parmTemplate().label().casefold() in wanted), None)
    return found or next((p for p in parms if any(part in p.name() for part in name_parts)), None)


def addCollection(node, name: str, pattern: str):
    """A Collection LOP under node: the collection name and its include pattern. (the node, parms not found)"""
    new = appendNode(node, "collection", f"COLLECTION_{name}")
    missing = []
    for value, labels, parts in ((name, ("Collection Name", "Name"), ("collectionname",)),
                                 (pattern, ("Includes", "Include Pattern", "Include", PRIMS_PARM),
                                  ("includepattern", "primpattern"))):
        parm = _parmLike(new, labels, parts)
        if parm is None:
            missing.append(labels[0])
        else:
            parm.set(value)
    return new, missing


def expandPattern(node, pattern: str) -> list[str]:
    """Prim paths a pattern picks on the node's stage (the same rule the LOP fields use)"""
    try:
        return [str(p) for p in hou.LopSelectionRule(pattern).expandedPaths(lopnode=node)]
    except hou.OperationFailed:
        return []
