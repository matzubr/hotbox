"""Opening images in MPlay."""
from __future__ import annotations

import os
import subprocess

import hou

from . import frames


def sequenceArgument(parm) -> str:
    """Path for MPlay: a sequence as prefix$F4suffix (padding of the first frame on disk), else the file"""
    pattern = frames.sequencePattern(parm)
    if pattern is None:
        return parm.evalAsString()
    folder, prefix, suffix = pattern
    existing = frames.sequenceFrames(parm)
    name = os.path.basename(parm.evalAtFrame(existing[0]).replace("\\", "/")) if existing else ""
    width = len(name) - len(prefix) - len(suffix) if existing else 4
    return os.path.join(folder, f"{prefix}$F{max(width, 1)}{suffix}").replace("\\", "/")


def mplayExecutable() -> str:
    hfs = hou.getenv("HFS") or ""
    for name in ("mplay", "mplay.exe"):
        path = os.path.join(hfs, "bin", name)
        if os.path.isfile(path):
            return path
    return "mplay"


def openInMPlay(parm) -> None:
    subprocess.Popen([mplayExecutable(), sequenceArgument(parm)])
