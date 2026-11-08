"""Frame ranges of nodes: file sequences, Alembic files, keyframes."""
from __future__ import annotations

import os
import posixpath
import re

import hou

from . import panes, paths

# Two frames that give different digits in every position, also with $F4 padding
_PROBE_FRAMES = (123456, 654321)


def sequencePattern(parm) -> tuple[str, str, str] | None:
    """(folder, file prefix, file suffix) of a file sequence parameter: the frame number goes between
    prefix and suffix. None when the value doesn't change with the frame or the frame is in the folder."""
    first, second = (parm.evalAtFrame(frame).replace("\\", "/") for frame in _PROBE_FRAMES)
    if first == second:
        return None
    start = len(posixpath.commonprefix([first, second]))
    end = len(posixpath.commonprefix([first[::-1], second[::-1]]))
    # The probe frames differ in every digit and are longer than any padding: the number is exactly the middle
    prefix, suffix = first[:start], first[len(first) - end:] if end else ""
    folder, file_prefix = posixpath.split(prefix)
    if "/" in suffix:
        return None
    return folder, file_prefix, suffix


def sequenceFrames(parm) -> list[int]:
    """Frames of a file sequence that exist on disk, sorted"""
    pattern = sequencePattern(parm)
    if pattern is None:
        return []
    folder, prefix, suffix = pattern
    try:
        names = os.listdir(folder or ".")
    except OSError:
        return []
    regex = re.compile(re.escape(prefix) + r"(-?\d+)" + re.escape(suffix) + "$")
    return sorted(int(m.group(1)) for name in names if (m := regex.match(name)))


def alembicRange(path: str) -> tuple[int, int] | None:
    """Frame range of an animated Alembic file, None for a static one or a missing file"""
    if not os.path.isfile(path):
        return None
    try:
        import _alembic_hom_extensions as alembic
    except ImportError:
        return None
    time_range = alembic.alembicTimeRange(path)
    if not time_range:
        return None
    fps = hou.fps()
    start, end = (round(seconds * fps) for seconds in time_range)
    return (start, end) if end > start else None


def keyframeRange(node) -> tuple[int, int] | None:
    """First and last keyframe over all parameters of the node"""
    frames = [key.frame() for parm in node.parms() for key in parm.keyframes()]
    if len(frames) < 2 or min(frames) == max(frames):
        return None
    return int(min(frames)), int(max(frames))


def frameRange(node) -> tuple[int, int] | None:
    """Frame range of the node's data: Alembic file, file sequence on disk, else its keyframes"""
    for parm_name in paths.fileParms(node, include_hidden=True):
        parm = node.parm(parm_name)
        if parm is None:
            continue
        path = parm.eval()
        if path.lower().endswith(".abc"):
            result = alembicRange(path)
        else:
            frames = sequenceFrames(parm)
            result = (frames[0], frames[-1]) if len(frames) > 1 else None
        if result:
            return result
    return keyframeRange(node)


def setFrameRange(start: int, end: int) -> None:
    """Scene frame range and playback range"""
    hou.playbar.setFrameRange(start, end)
    hou.playbar.setPlaybackRange(start, end)


def frameRangeFromSelection() -> tuple[int, int] | None:
    """Scene range from the selected nodes (all their ranges together)"""
    ranges = [r for node in hou.selectedNodes() if (r := frameRange(node))]
    if not ranges:
        panes.warn("No frame range: no Alembic animation, file sequence or keyframes on the selected nodes")
        return None
    start, end = min(r[0] for r in ranges), max(r[1] for r in ranges)
    setFrameRange(start, end)
    hou.ui.setStatusMessage(f"Frame range {start}-{end}", severity=hou.severityType.Message)
    return start, end
