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


def buildCacheNetwork(caches, kind: str, cache_types: dict) -> tuple:
    """kind 'rop': a ROP network with a Fetch per cache, chained (each one waits for the one before).
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
        raise ValueError("None of the selected nodes is a cache node (see CACHE_TYPES in the script)")

    if kind == "rop":
        network = _container(caches, "ropnet", "write_caches")
        created = []
        for cache, rop in pairs:
            fetch = network.createNode("fetch", f"fetch_{cache.name()}")
            _setPath(fetch, ("source",), ("Source",), rop.path())
            if created:
                fetch.setInput(0, created[-1])
            created.append(fetch)
        _stack(created)
        created[-1].setCurrent(True, clear_all_selected=True)
        return network, created, skipped

    network = _container(caches, "topnet", "write_caches")
    created, chain = [], []
    for cache, rop in pairs:
        fetch = network.createNode("ropfetch", f"write_{cache.name()}")
        _setPath(fetch, ("roppath",), ("ROP Path",), rop.path())
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
