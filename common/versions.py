"""The other versions of a cache on disk, to clean up the old ones.

The node's path at its current version is turned into a pattern: the version number (the last one equal to the
version in the path, padded or not) and the frame number become wildcards. Only files matching it are found, so
another cache sharing the version folder is never touched.
"""
from __future__ import annotations

import os
import re

import hou

from . import cachetypes, frames, paths

_VERSION, _FRAME = "\0V\0", "\0F\0"


def _template(node) -> str | None:
    """The node's path with markers for the version and the frame number; None without a version in the path"""
    version_parm, file_parm = cachetypes.versionParm(node), paths.mainFileParm(node)
    if version_parm is None or file_parm is None:
        return None
    pattern = frames.sequencePattern(file_parm)
    if pattern is None:
        head, tail = file_parm.evalAsString().replace("\\", "/"), ""
    else:
        folder, prefix, suffix = pattern
        head, tail = posixJoin(folder, prefix), _FRAME + suffix
    matches = list(re.finditer(rf"(?<!\d)0*{int(version_parm.eval())}(?!\d)", head))
    if not matches:
        return None
    last = matches[-1]
    return head[:last.start()] + _VERSION + head[last.end():] + tail


def posixJoin(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def _regex(part: str):
    pieces = re.split(f"({_VERSION}|{_FRAME})", part)
    rx = "".join(r"(?P<v>\d+)" if p == _VERSION else r"-?\d+" if p == _FRAME else re.escape(p) for p in pieces)
    return re.compile(rx, re.IGNORECASE if os.name == "nt" else 0)


def _walk(base: str, parts: list[str], version: int | None, version_dir: str | None):
    """(file, its version, the version's folder or None) of the files matching the remaining parts"""
    if not parts:
        if version is not None and os.path.isfile(base):
            yield base, version, version_dir
        return
    part, rest = parts[0], parts[1:]
    if "\0" not in part:
        yield from _walk(posixJoin(base, part) if base != "/" else "/" + part, rest, version, version_dir)
        return
    regex = _regex(part)
    try:
        names = sorted(os.listdir(base or "."))
    except OSError:
        return
    for name in names:
        match = regex.fullmatch(name)
        if not match:
            continue
        path = posixJoin(base, name) if base != "/" else "/" + name
        found = match.groupdict().get("v")
        if found is not None:
            yield from _walk(path, rest, int(found), path if rest else None)
        else:
            yield from _walk(path, rest, version, version_dir)


def versionsOnDisk(node) -> dict[int, dict]:
    """{version: {'files': [...], 'size': bytes, 'folder': the version's own folder or None}}"""
    template = _template(node)
    if template is None:
        return {}
    parts = template.split("/")
    first = next(i for i, part in enumerate(parts) if "\0" in part)
    base = "/".join(parts[:first]) or ("/" if template.startswith("/") else "")
    found: dict[int, dict] = {}
    for path, version, folder in _walk(base, parts[first:], None, None):
        entry = found.setdefault(version, {"files": [], "size": 0, "folder": folder})
        entry["files"].append(path)
        try:
            entry["size"] += os.path.getsize(path)
        except OSError:
            pass
    return dict(sorted(found.items()))


def oldVersions(node, keep: int) -> dict[int, dict]:
    """The versions on disk except the newest `keep` ones and the node's current version"""
    found = versionsOnDisk(node)
    version_parm = cachetypes.versionParm(node)
    current = int(version_parm.eval()) if version_parm is not None else None
    newest = set(sorted(found)[-keep:]) if keep > 0 else set()
    return {v: entry for v, entry in found.items() if v not in newest and v != current}


def deleteVersion(entry: dict) -> int:
    """Delete the files, then the folders they leave empty up to the version's folder. Returns bytes freed."""
    freed = 0
    folders = set()
    for path in entry["files"]:
        try:
            size = os.path.getsize(path)
            os.remove(path)
        except OSError:
            continue
        freed += size
        folders.add(os.path.dirname(path))
    top = entry.get("folder")
    if top:
        for folder in sorted(folders, key=len, reverse=True):
            while folder.startswith(top) and len(folder) >= len(top):
                try:
                    os.rmdir(folder)  # only when empty
                except OSError:
                    break
                folder = os.path.dirname(folder)
    return freed


def cleanOldVersions(nodes) -> int:
    """Ask how many versions to keep, show what goes, delete after a confirmation. Returns bytes freed."""
    from . import panes

    nodes = [n for n in nodes if cachetypes.versionParm(n) is not None]
    if not nodes:
        panes.warn("No node with a Version parameter selected")
        return 0
    button, text = hou.ui.readInput("Keep the newest versions (the current one is always kept):",
                                    buttons=("Find Old Versions", "Cancel"), close_choice=1, initial_contents="2",
                                    title="Clean Old Versions")
    if button != 0:
        return 0
    try:
        keep = max(0, int(text))
    except ValueError:
        panes.warn(f"Not a number: {text}")
        return 0
    plan = [(node, oldVersions(node, keep)) for node in nodes]
    plan = [(node, old) for node, old in plan if old]
    if not plan:
        hou.ui.setStatusMessage("Clean Old Versions: nothing to delete")
        return 0
    total = sum(e["size"] for _node, old in plan for e in old.values())
    lines = [f"{node.name()}: " + ", ".join(f"v{v} ({paths.formatSize(e['size'])}, {len(e['files'])} files)"
                                           for v, e in old.items()) for node, old in plan]
    files = "\n".join(path for _node, old in plan for e in old.values() for path in e["files"])
    if hou.ui.displayMessage(f"Delete {paths.formatSize(total)} of old versions?\n\n" + "\n".join(lines),
                             buttons=("Delete", "Cancel"), default_choice=1, close_choice=1, details=files,
                             details_label="Files", severity=hou.severityType.Warning,
                             title="Clean Old Versions") != 0:
        return 0
    freed = sum(deleteVersion(e) for _node, old in plan for e in old.values())
    hou.ui.setStatusMessage(f"Clean Old Versions: {paths.formatSize(freed)} freed")
    return freed
