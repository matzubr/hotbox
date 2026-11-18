"""ROP / TOP networks that write cache nodes (File Cache and friends) one after another."""
from __future__ import annotations

import hou

from .nodes import freePosition

AUTO = None  # the ROP inside the cache node is found by itself (the first ROP among its children)
SELF = "."  # the node is a ROP itself (ROP Geometry Output SOP)


def typeKey(node) -> str:
    """Type name without the version: 'filecache', 'labs::filecache', 'rop_geometry'"""
    _scope, namespace, name, _version = node.type().nameComponents()
    return f"{namespace}::{name}" if namespace else name


def _isRop(node) -> bool:
    return isinstance(node, hou.RopNode)


def ropOf(node, cache_types: dict):
    """The ROP that writes the cache of the node: how to find it is cache_types[type]; None for other nodes"""
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
WRITE_LABEL = "Write All, Node by Node"
WRITE_TOGGLE = "write_cache"  # write_cache1, write_cache2...: which caches the button writes


def writeCallback(merge_name: str) -> str:
    """Button callback: the ROP behind each Fetch of the merge, in input order, over its own frame range (like Save
    to Disk on each cache); bypassed Fetches (toggles off) are skipped. Plain hou, no hotbox: the button works in a
    scene opened without it.
    Not the Merge itself: its Render button goes frame by frame (Houdini's -I), and dependencies may get the
    downstream frame range instead of their own."""
    return (f"[f.node(f.evalParm('source')).render(method=hou.renderMethod.RopByRop) "
            f"for f in kwargs['node'].node('{merge_name}').inputs() if f is not None and not f.isBypassed()]")


def toggleCallback(fetch_name: str) -> str:
    """Toggle callback: off bypasses the Fetch (the write button skips it, the network shows it)"""
    return f"kwargs['node'].node({fetch_name!r}).bypass(not kwargs['parm'].eval())"


def toggleName(index: int) -> str:
    return f"{WRITE_TOGGLE}{index + 1}"


def addWriteButton(network, merge, toggles=()) -> None:
    """On top of the network's parameters: the button that writes the caches node by node (writeCallback) and a
    toggle per cache, toggles = [(fetch, label)]: which ones the button writes"""
    group = network.parmTemplateGroup()
    templates = [hou.ButtonParmTemplate(
        WRITE_BUTTON, WRITE_LABEL, script_callback=writeCallback(merge.name()),
        script_callback_language=hou.scriptLanguage.Python,
        help="Writes the checked caches one after another, each over its own frame range (Esc stops)")]
    for k, (fetch, label) in enumerate(toggles):
        templates.append(hou.ToggleParmTemplate(
            toggleName(k), label, default_value=True, script_callback=toggleCallback(fetch.name()),
            script_callback_language=hou.scriptLanguage.Python,
            help=f"Write {label} with '{WRITE_LABEL}' (off bypasses {fetch.name()})"))
    if toggles:
        templates.append(hou.SeparatorParmTemplate(f"{WRITE_BUTTON}_sep"))
    entries = group.entries()
    for template in templates:
        if entries:
            group.insertBefore(entries[0], template)
        else:
            group.append(template)
    network.setParmTemplateGroup(group)


def _ropNetwork(caches, pairs, skipped) -> tuple:
    """A Fetch per cache side by side into a Merge (inputs in the write order), the node by node button and a toggle
    per cache"""
    network = _container(caches, "ropnet", "write_caches")
    created = []
    for k, (cache, rop) in enumerate(pairs):
        fetch = network.createNode("fetch", f"fetch_{cache.name()}")
        _setPath(fetch, ("source",), ("Source",), rop.path())
        fetch.setPosition(hou.Vector2(STACK_X + 3.0 * k, 0))
        created.append(fetch)
    merge = network.createNode("merge", "write_all")
    for k, fetch in enumerate(created):
        merge.setInput(k, fetch)
    merge.setPosition(hou.Vector2(STACK_X + 1.5 * (len(created) - 1), -2))
    merge.setComment(f"Write with '{WRITE_LABEL}' on {network.name()}:\nits Render button goes frame by frame")
    merge.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    addWriteButton(network, merge, [(fetch, cache.name()) for fetch, (cache, _rop) in zip(created, pairs)])
    merge.setCurrent(True, clear_all_selected=True)
    network.setCurrent(True, clear_all_selected=True)
    return network, created, skipped


def buildCacheNetwork(caches, kind: str, cache_types: dict) -> tuple:
    """kind 'rop': a ROP network with a Fetch per cache into a Merge, written node by node by its button.
    kind 'top': a TOP network with a ROP Fetch per cache, Wait for All between them.
    The network goes next to the caches. Returns (network, [created nodes], [caches skipped, no ROP])."""
    pairs, skipped = [], []
    for cache in dependencyOrder(caches):
        rop = ropOf(cache, cache_types)
        if rop is None:
            skipped.append(cache)
        else:
            pairs.append((cache, rop))
    if not pairs:
        raise ValueError("No cache ROP found in the selected nodes (see CACHE_TYPES in the script)")

    if kind == "rop":
        return _ropNetwork(caches, pairs, skipped)

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
    return network, created, skipped
