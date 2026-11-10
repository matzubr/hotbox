"""SOP geometry and VDB caches into Solaris: SOP Import / Volume LOPs in one LOP network."""
from __future__ import annotations

import posixpath

import hou

from . import caches, frames, panes, paths
from .nodes import freePosition

LOPNET = "/obj/lopnet1"  # every import goes here: created when missing
GEO_PREFIX = "/geo"  # SOP Import prims: /geo/<node name>
VOL_PREFIX = "/vol"  # Volume prims: /vol/<node name>
VELOCITY_BLUR = "Velocity Blur"  # Karma 'Geometry Velocity Blur' menu entry
COLUMN_GAP = 1.0


def lopNetwork():
    """The LOP network all imports go to (LOPNET), created at /obj when it is not there"""
    network = hou.node(LOPNET)
    if network is not None:
        return network
    parent_path, name = posixpath.split(LOPNET)
    return hou.node(parent_path).createNode("lopnet", name)


def freeColumn(network):
    """Top of an empty column right of the nodes already in the network"""
    children = list(network.children())
    if not children:
        return hou.Vector2(0, 0)
    right = max(n.position()[0] + n.size()[0] for n in children)
    top = max(n.position()[1] for n in children)
    return hou.Vector2(right + COLUMN_GAP, top)


def _byLabel(items, label: str):
    return next((item for item in items if item.parmTemplate().label() == label), None)


def parmByLabel(node, label: str):
    return _byLabel(node.parms(), label)


def parmTupleByLabel(node, label: str):
    return _byLabel(node.parmTuples(), label)


# --- render geometry settings -------------------------------------------------------------------------------------

BLUR_PROPERTIES = ("geovelocityblur", "instancevelocityblur")  # Karma: Geometry / Instance Velocity Blur
SET_OR_CREATE = "Set or Create"


def _blurParms(node, key: str):
    """(value parm, its control parm) of a Karma blur property; USD property names are encoded (xn__...).
    'geovelocityblur' must not match 'instancevelocityblur' and the other way: the name has to hold ':<key>'"""
    found = [p for p in node.parms() if f"object{key}" in p.name()]
    value = next((p for p in found if "control" not in p.name()), None)
    control = next((p for p in found if "control" in p.name()), None)
    return value, control


def _pickMenu(parm, label: str, fallback) -> bool:
    """Menu entry with the label, else the first entry passing fallback(label lowercased)"""
    if caches.setMenuByLabel(parm, label):
        return True
    labels = [text.lower() for text in parm.menuLabels()]
    index = next((i for i, text in enumerate(labels) if fallback(text)), None)
    if index is None:
        return False
    parm.set(parm.menuItems()[index] if parm.parmTemplate().type().name() == "String" else index)
    return True


def setVelocityBlur(node) -> list[str]:
    """Geometry and Instance Velocity Blur on the Render Geometry Settings: 'Velocity Blur', each control
    'Set or Create'. The properties not found (empty: all set)"""
    missing = []
    for key in BLUR_PROPERTIES:
        value, control = _blurParms(node, key)
        if value is None:
            missing.append(key)
            continue
        if control is not None:
            _pickMenu(control, SET_OR_CREATE, lambda text: text.startswith("set"))
        if not _pickMenu(value, VELOCITY_BLUR, lambda text: "velocity" in text and "no" not in text.split()):
            missing.append(key)
    return missing


def addRenderGeometrySettings(sop_import, name: str | None = None):
    """Render Geometry Settings after the SOP Import: velocity blur on its prims.
    The prim pattern references the import's path prefix: rename the prims there, the settings follow."""
    network = sop_import.parent()
    name = name or sop_import.name().removeprefix("IMPORT_")
    settings = network.createNode("rendergeometrysettings", f"RENDERGEO_{name}")
    settings.setInput(0, sop_import)
    pattern = settings.parm("primpattern") or parmByLabel(settings, "Primitives")
    if pattern is not None:
        pattern.set(f'`chs("{settings.relativePathTo(sop_import)}/pathprefix")`')
    missing = setVelocityBlur(settings)
    if missing:
        hou.ui.setStatusMessage(f"{settings.name()}: not set: {', '.join(missing)}",
                                severity=hou.severityType.Warning)
    wanted = sop_import.position() - hou.Vector2(0, 1)
    settings.setPosition(freePosition(network, wanted, settings.size(), step=0.5, ignore=[settings]))
    settings.setColor(sop_import.color())
    return settings


# --- SOP geometry -------------------------------------------------------------------------------------------------

def importSops(nodes) -> list:
    """SOP Import + Render Geometry Settings in LOPNET for each SOP node, prims at /geo/<name>.
    The created pairs, side by side in a new column."""
    nodes = [n for n in nodes if n.type().category() == hou.sopNodeTypeCategory()]
    if not nodes:
        panes.warn("Select SOP nodes")
        return []
    network = lopNetwork()
    start = freeColumn(network)
    created = []
    for i, node in enumerate(nodes):
        name = node.name()
        sop_import = network.createNode("sopimport", f"IMPORT_{name}")
        sop_import.parm("soppath").set(node.path())
        sop_import.parm("pathprefix").set(f"{GEO_PREFIX}/{name}")
        sop_import.setUserData("nodeshape", "chevron_up")
        sop_import.setColor(node.color())
        sop_import.setPosition(start + hou.Vector2(i * 3, 0))
        created.append((sop_import, addRenderGeometrySettings(sop_import, name)))
    hou.ui.setStatusMessage(f"{len(created)} SOP Import(s) in {network.path()}")
    return created


# --- VDB caches ---------------------------------------------------------------------------------------------------

def _shortPath(path: str) -> str:
    """$HIP / $JOB instead of the absolute start of the path when it is inside them"""
    for variable in ("$HIP", "$JOB"):
        root = hou.text.expandString(variable)
        if root and root != variable:
            short = paths.replacePrefix(path, root, variable)
            if short is not None:
                return short
    return path


def sequencePath(parm) -> tuple[str, tuple[int, int] | None]:
    """(path with $F / $F4 in place of the frame, frames on disk (first, last) or None) of a cache file parm;
    a single file: (its path, None). The path is evaluated: no expressions that only work on the cache node."""
    pattern = frames.sequencePattern(parm)
    if pattern is None:
        return _shortPath(parm.evalAsString().replace("\\", "/")), None
    folder, prefix, suffix = pattern
    one = parm.evalAtFrame(1).replace("\\", "/")
    digits = posixpath.basename(one)[len(prefix):len(posixpath.basename(one)) - len(suffix)]
    padding = len(digits) if len(digits) > 1 else 0
    path = _shortPath(posixpath.join(folder, f"{prefix}$F{padding or ''}{suffix}"))
    on_disk = frames.sequenceFrames(parm)
    return path, (on_disk[0], on_disk[-1]) if on_disk else None


def nodeFrameRange(node) -> tuple[int, int] | None:
    """Start/End of the cache node's own frame range parms (File Cache: f1 f2)"""
    start, end = node.parm("f1"), node.parm("f2")
    if start is None or end is None:
        return None
    return int(start.eval()), int(end.eval())


def isVdb(path: str) -> bool:
    return path.lower().endswith(".vdb")


def importVolume(node):
    """Volume LOP in LOPNET reading the node's VDB cache, prim /vol/<name>, sampled over the cache frame range
    (frames on disk, else the node's range). None when the node has no VDB file."""
    parm = paths.mainFileParm(node)
    if parm is None or not isVdb(parm.evalAsString()):
        panes.warn(f"{node.name()} has no .vdb file")
        return None
    path, frame_range = sequencePath(parm)
    if "$F" in path and frame_range is None:
        frame_range = nodeFrameRange(node)

    network = lopNetwork()
    volume = network.createNode("volume", f"VOLUME_{node.name()}")
    file_parm = volume.parm("filepath1") or parmByLabel(volume, "File Path")
    if file_parm is None:
        names = paths.fileParms(volume)
        file_parm = volume.parm(names[0]) if names else None
    if file_parm is None:
        panes.warn(f"{volume.name()}: no File Path parameter")
    else:
        file_parm.set(path)
    prim = volume.parm("primpath") or parmByLabel(volume, "Primitive Path")
    if prim is not None:
        prim.set(f"{VOL_PREFIX}/{node.name()}")
    if "$F" in path and frame_range is not None:
        caches.setMenuByLabel(parmByLabel(volume, "Sampling Behavior"), "Sample Frame Range")
        frame_parms = parmTupleByLabel(volume, "Start/End/Inc")
        if frame_parms is not None:
            frame_parms.set((frame_range[0], frame_range[1], 1))
    volume.setColor(node.color())
    volume.setPosition(freeColumn(network))
    range_text = f" {frame_range[0]}-{frame_range[1]}" if "$F" in path and frame_range else ""
    hou.ui.setStatusMessage(f"{volume.path()}: {path}{range_text}")
    return volume
