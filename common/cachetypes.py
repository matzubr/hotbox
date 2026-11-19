"""Cache node types: one line per type tells every cache and path tool how to handle it.

Add a studio cache HDA here (any version: the key has no version, s_cache::11.0 -> "s_cache",
bp::filecache::1.0 -> "bp::filecache"):

    rop      where its ROP is: AUTO (the first ROP inside, File Cache's "render"), SELF (the node is a ROP)
             or a path inside the node ("ropnet1/geo")
    paths    its path parameters when they are not file references: () = every string parameter whose value
             looks like a cache file, or the names; None = file reference parameters only (File Cache)
    reload   the button Reload Caches presses ("" = found through its read file parameter)
    version  its version parameter ("" = "version", else an Int parameter labeled Version)
"""
from __future__ import annotations

from dataclasses import dataclass

import hou

AUTO = None
SELF = "."


@dataclass(frozen=True)
class CacheType:
    rop: str | None = AUTO
    paths: tuple[str, ...] | None = None
    reload: str = ""
    version: str = ""


CACHE_TYPES: dict[str, CacheType] = {
    "filecache": CacheType(),
    "labs::filecache": CacheType(),
    "bp::filecache": CacheType(paths=(), reload="reload"),  # studio File Cache, same insides
    "vellumio": CacheType(),
    "s_cache": CacheType(rop="ropnet1/geo", paths=(), reload="reload"),  # studio cache HDA
    "rop_geometry": CacheType(rop=SELF),
    "rop_alembic": CacheType(rop=SELF),
}


def typeKey(node_type) -> str:
    """Type name without the version: 'filecache', 'labs::filecache', 's_cache'"""
    _scope, namespace, name, _version = node_type.nameComponents()
    return f"{namespace}::{name}" if namespace else name


def cacheType(node) -> CacheType | None:
    try:
        return CACHE_TYPES.get(typeKey(node.type()))
    except (AttributeError, TypeError, ValueError, hou.OperationFailed):
        return None


def instances(types=None) -> list:
    """Every node of the types (default: all cache types), any version, in the whole scene"""
    types = CACHE_TYPES if types is None else types
    found = []
    for category in hou.nodeTypeCategories().values():
        for node_type in category.nodeTypes().values():
            if typeKey(node_type) in types:
                found += list(node_type.instances())
    return found


def versionParm(node):
    """The cache version parameter: the listed one, 'version', else an Int parameter labeled Version"""
    cache_type = cacheType(node)
    name = cache_type.version if cache_type and cache_type.version else "version"
    parm = node.parm(name)
    if parm is not None:
        return parm
    return next((p for p in node.parms() if p.parmTemplate().label().strip().casefold() == "version"
                 and p.parmTemplate().type() == hou.parmTemplateType.Int), None)


def versionUp(node) -> int | None:
    """Next version (versioning gets turned on); None when the node has no version parameter"""
    parm = versionParm(node)
    if parm is None:
        return None
    if node.parm("enableversion") is not None:
        node.parm("enableversion").set(1)
    parm.set(parm.eval() + 1)
    return parm.eval()
