"""ROP / TOP networks that write cache nodes (File Cache and friends) one after another."""
from __future__ import annotations

from pathlib import Path

import hou

from . import cachetypes, cachewriter
from .nodes import freePosition

AUTO, SELF = cachetypes.AUTO, cachetypes.SELF


def typeKey(node) -> str:
    """Type name without the version: 'filecache', 'labs::filecache', 'rop_geometry'"""
    return cachetypes.typeKey(node.type())


def _isRop(node) -> bool:
    return isinstance(node, hou.RopNode)


def ropOf(node, cache_types: dict | None = None):
    """The ROP that writes the cache of the node: how to find it is cache_types[type] (default: the rop of
    cachetypes.CACHE_TYPES); None for other nodes"""
    if cache_types is None:
        cache_types = {key: t.rop for key, t in cachetypes.CACHE_TYPES.items()}
    key = typeKey(node)
    if key not in cache_types:
        return None
    where = cache_types[key]
    if where == SELF:
        return node
    if where:
        return node.node(where)
    if _isRop(node):
        return node
    ropes = [child for child in node.allSubChildren() if _isRop(child)]
    return next((r for r in ropes if r.name() == "render"), ropes[0] if ropes else None)


def dependencyOrder(nodes) -> list:
    """Upstream caches first (a cache that reads another one is written after it), else the selection order"""
    nodes = list(nodes)
    paths = {n.path() for n in nodes}
    upstream = {n.path(): {a.path() for a in n.inputAncestors()} & paths for n in nodes}
    ordered, done = [], set()
    while len(ordered) < len(nodes):
        ready = [n for n in nodes if n.path() not in done and upstream[n.path()] <= done]
        if not ready:  # a loop: keep the rest in the selection order
            ready = [n for n in nodes if n.path() not in done]
        ordered.append(ready[0])
        done.add(ready[0].path())
    return ordered


def _setPath(node, names, labels, value) -> bool:
    """Set the first parameter that exists of names, else the first with one of the labels"""
    for name in names:
        if node.parm(name) is not None:
            node.parm(name).set(value)
            return True
    for parm in node.parms():
        if parm.parmTemplate().label() in labels:
            parm.set(value)
            return True
    return False


FRAME_GENERATION = "ROP Node Configuration"  # ROP Fetch: frames from the cache node's own ROP


def setMenuByLabel(parm, label: str) -> bool:
    """Pick the menu entry with the label (the tokens are not the same in every version)"""
    if parm is None:
        return False
    labels = list(parm.menuLabels())
    if label not in labels:
        return False
    index = labels.index(label)
    items = list(parm.menuItems())
    parm.set(items[index] if parm.parmTemplate().type().name() == "String" else index)
    return True


def _container(nodes, node_type: str, name: str):
    network = nodes[0].parent()
    container = network.createNode(node_type, name)
    right = max(n.position()[0] for n in nodes) + 3
    top = max(n.position()[1] for n in nodes)
    container.setPosition(freePosition(network, hou.Vector2(right, top), container.size(), ignore=[container]))
    return container


STACK_X = 4.0  # right of the scheduler a new TOP network comes with


def _stack(nodes) -> None:
    """One under the other"""
    for k, node in enumerate(nodes):
        node.setPosition(hou.Vector2(STACK_X, -1.5 * k))


WRITE_BUTTON = "write_node_by_node"
WRITE_LABEL = "Write Checked, Node by Node"
WRITE_TOGGLE = "write_cache"  # write_cache1, write_cache2...: which caches the button writes
INTERFACE = "hotbox_write"  # the folder with the buttons on top of the network's parameters
OPTIONS = (  # (parameter, label, default, help)
    (cachewriter.SKIP_EXISTING, "Skip Frames on Disk", False,
     "Write only the frames that have no file yet; a cache with every frame on disk is skipped"),
    (cachewriter.VERSION_UP, "Version Up First", False,
     "Each cache goes to its next version before writing: the last one isn't overwritten"),
    (cachewriter.RELOAD_AFTER, "Reload After Writing", True,
     "Press the cache node's Reload after it is written: the next cache reads the new files"),
    (cachewriter.KEEP_GOING, "Continue After an Error", True,
     "A cache that fails doesn't stop the ones after it"),
)


def writerSource() -> str:
    """The writer the network's buttons run, stored in the scene (works without hotbox)"""
    return Path(cachewriter.__file__).read_text(encoding="utf-8")


def toggleName(index: int) -> str:
    return f"{WRITE_TOGGLE}{index + 1}"


def _button(name: str, label: str, action: str, help_text: str = "", join: bool = False):
    return hou.ButtonParmTemplate(name, label, script_callback=cachewriter.callback(action),
                                  script_callback_language=hou.scriptLanguage.Python, help=help_text,
                                  join_with_next=join)


def buildInterface(network) -> None:
    """(Re)build the folder on top of the network's parameters: write / refresh buttons, options, Select All /
    Deselect All and a toggle per Fetch of the Merge labeled with what is on disk. Options keep their values, the
    toggles follow the bypass flags. The writer the buttons run is stored (updated) in the network's user data."""
    group = network.parmTemplateGroup()
    old = {name: network.parm(name).eval() for name, *_ in OPTIONS if network.parm(name) is not None}
    if group.find(INTERFACE) is not None:
        group.remove(INTERFACE)
    folder = hou.FolderParmTemplate(INTERFACE, "Write Caches", folder_type=hou.folderType.Simple)
    folder.addParmTemplate(_button(WRITE_BUTTON, WRITE_LABEL, "write", join=True, help_text=(
        "Writes the checked caches one after another, each over its own frame range (Esc stops)")))
    folder.addParmTemplate(_button(f"{INTERFACE}_refresh", "Refresh", "refresh",
                                   "Update the toggles: frames and size on disk, bypassed Fetches unchecked"))
    for name, label, default, help_text in OPTIONS:
        folder.addParmTemplate(hou.ToggleParmTemplate(name, label, default_value=default, help=help_text))
    folder.addParmTemplate(hou.SeparatorParmTemplate(f"{INTERFACE}_sep"))
    folder.addParmTemplate(_button(f"{WRITE_TOGGLE}_select_all", "Select All", "all", join=True))
    folder.addParmTemplate(_button(f"{WRITE_TOGGLE}_deselect_all", "Deselect All", "none"))
    fetches = cachewriter.fetches(network)
    for k, fetch in enumerate(fetches):
        folder.addParmTemplate(hou.ToggleParmTemplate(
            toggleName(k), cachewriter.label(fetch), default_value=True, tags={cachewriter.TOGGLE_TAG: fetch.name()},
            script_callback=cachewriter.callback("toggle"), script_callback_language=hou.scriptLanguage.Python,
            help=f"Write it with '{WRITE_LABEL}' (off bypasses {fetch.name()})"))
    entries = group.entries()
    if entries:
        group.insertBefore(entries[0], folder)
    else:
        group.append(folder)
    network.setParmTemplateGroup(group)
    for name, value in old.items():  # a parameter added again may come back with its default
        network.parm(name).set(value)
    for k, fetch in enumerate(fetches):
        network.parm(toggleName(k)).set(int(not fetch.isBypassed()))
    network.setUserData(cachewriter.USER_DATA, writerSource())


def isWriteNetwork(node) -> bool:
    try:
        return isinstance(node.userData(cachewriter.USER_DATA), str)
    except (AttributeError, hou.OperationFailed):
        return False


def writeNetworks(parent) -> list:
    """The ROP networks Cache Network made in the network"""
    return [node for node in parent.children() if isWriteNetwork(node)]


def addToRopNetwork(network, pairs) -> tuple[list, list]:
    """A Fetch per (cache, ROP) into the Merge, after the ones there; a cache already in it is left out.
    Returns ([new Fetches], [caches already in the network])."""
    merge = network.node(cachewriter.MERGE)
    if merge is None:
        merge = network.createNode("merge", cachewriter.MERGE)
        merge.setComment(f"Write with '{WRITE_LABEL}' on {network.name()}:\nits Render button goes frame by frame")
        merge.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    have = {fetch.evalParm("source") for fetch in cachewriter.fetches(network)}
    created, already = [], []
    for cache, rop in pairs:
        if rop.path() in have:
            already.append(cache)
            continue
        fetch = network.createNode("fetch", f"fetch_{cache.name()}")
        _setPath(fetch, ("source",), ("Source",), rop.path())
        cache_type = cachetypes.cacheType(cache)
        version = cachetypes.versionParm(cache) if cache_type is None or cache_type.rop != cachetypes.SELF else None
        fetch.setUserData(cachewriter.CACHE_KEY, cache.path())
        fetch.setUserData(cachewriter.VERSION_KEY, version.name() if version is not None else "")
        fetch.setUserData(cachewriter.RELOAD_KEY, cache_type.reload if cache_type is not None else "")
        index = len(merge.inputs())
        merge.setInput(index, fetch)
        fetch.setPosition(hou.Vector2(STACK_X + 3.0 * index, 0))
        created.append(fetch)
    merge.setPosition(hou.Vector2(STACK_X + 1.5 * (len(merge.inputs()) - 1), -2))
    buildInterface(network)
    merge.setCurrent(True, clear_all_selected=True)
    network.setCurrent(True, clear_all_selected=True)
    return created, already


def buildCacheNetwork(caches, kind: str, cache_types: dict | None = None, network=None) -> tuple:
    """kind 'rop': a ROP network (new, or the given one: added to it) with a Fetch per cache into a Merge,
    written node by node by its button.
    kind 'top': a TOP network with a ROP Fetch per cache, Wait for All between them.
    A new network goes next to the caches. cache_types: type key -> where its ROP is (default cachetypes).
    Returns (network, [created nodes], [caches skipped, no ROP], [caches already in the network])."""
    pairs, skipped = [], []
    for cache in dependencyOrder(caches):
        rop = ropOf(cache, cache_types)
        if rop is None:
            skipped.append(cache)
        else:
            pairs.append((cache, rop))
    if not pairs:
        raise ValueError("No cache ROP found in the selected nodes (see common/cachetypes.py)")

    if kind == "rop":
        network = network or _container(caches, "ropnet", "write_caches")
        created, already = addToRopNetwork(network, pairs)
        return network, created, skipped, already

    network = _container(caches, "topnet", "write_caches")
    created, chain = [], []
    for cache, rop in pairs:
        fetch = network.createNode("ropfetch", f"write_{cache.name()}")
        _setPath(fetch, ("roppath",), ("ROP Path",), rop.path())
        setMenuByLabel(fetch.parm("framegeneration"), FRAME_GENERATION)
        if chain:
            wait = network.createNode("waitforall", f"after_{chain[-1].name()}")
            wait.setInput(0, chain[-1])
            fetch.setInput(0, wait)
            chain.append(wait)
        chain.append(fetch)
        created.append(fetch)
    _stack(chain)
    created[-1].setDisplayFlag(True)
    created[-1].setCurrent(True, clear_all_selected=True)
    return network, created, skipped, []


def chooseRopNetwork(parent):
    """An existing write network of the parent to add to, None for a new one, False when cancelled"""
    existing = writeNetworks(parent)
    if not existing:
        return None
    if len(existing) == 1:
        name = existing[0].name()
        choice = hou.ui.displayMessage(f"{parent.path()} already has the ROP network {name}.", title="Cache Network",
                                       buttons=(f"Add to {name}", "New ROP Network", "Cancel"), default_choice=0,
                                       close_choice=2)
        return (existing[0], None, False)[choice]
    picked = hou.ui.selectFromList(["New ROP network", *(n.name() for n in existing)], exclusive=True,
                                   default_choices=(1,), title="Cache Network", message="Add the caches to:",
                                   column_header="ROP network")
    if not picked:
        return False
    return existing[picked[0] - 1] if picked[0] else None


def runCacheNetwork(nodes) -> None:
    """Cache Network on the nodes: asks TOP / ROP network (and for ROP: a new one or an existing one), builds it"""
    from . import panes

    if not nodes:
        return
    choice = hou.ui.displayMessage(f"Write {len(nodes)} cache node(s) with:", buttons=("TOP network", "ROP network",
                                   "Cancel"), default_choice=0, close_choice=2, title="Cache Network")
    if choice == 2:
        return
    network = None
    if choice == 1:
        network = chooseRopNetwork(nodes[0].parent())
        if network is False:
            return
    try:
        network, created, skipped, already = buildCacheNetwork(nodes, ("top", "rop")[choice], network=network)
    except ValueError as e:
        panes.warn(str(e))
        return
    message = f"{network.path()}: {len(created)} cache(s) added"
    if choice == 1:
        message += f", write with '{WRITE_LABEL}' on it"
    if already:
        message += f", already in it: {', '.join(n.name() for n in already)}"
    if skipped:
        message += f", skipped (no ROP found, see common/cachetypes.py): {', '.join(n.name() for n in skipped)}"
    hou.ui.setStatusMessage(message, severity=hou.severityType.Warning if skipped else hou.severityType.Message)
