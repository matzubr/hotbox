"""The scene file: incremental saves, crash files and backups, opening folders."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HIP_SUFFIXES = (".hip", ".hiplc", ".hipnc")
VERSION_PADDING = 3
_VERSION = re.compile(r"([vV])(\d+)(?!.*[vV]\d)")  # the last v012 / V3 in the name


def incrementedPath(path: str | Path) -> Path:
    """shot_v012.hip -> shot_v013.hip (padding kept), shot.hip -> shot_v001.hip"""
    path = Path(path)
    match = _VERSION.search(path.stem)
    if match is None:
        return path.with_name(f"{path.stem}_v{1:0{VERSION_PADDING}d}{path.suffix}")
    digits = match.group(2)
    number = f"{int(digits) + 1:0{len(digits)}d}"
    stem = path.stem[:match.start(2)] + number + path.stem[match.end(2):]
    return path.with_name(stem + path.suffix)


def nextFreePath(path: str | Path) -> Path:
    """Next version of the file that doesn't exist yet (versions saved by someone else are skipped)"""
    candidate = incrementedPath(path)
    for _ in range(10000):
        if not candidate.exists():
            return candidate
        candidate = incrementedPath(candidate)
    raise RuntimeError(f"No free version for {path}")


def isHipFile(path: Path) -> bool:
    return path.suffix.lower() in HIP_SUFFIXES


def recoveryFiles(hip_path: str | Path | None, temp_dir: str | Path | None = None) -> list[Path]:
    """Crash files Houdini wrote to the temp folder and backups of this scene ($HIP/backup), newest first"""
    found: list[Path] = []
    temp = Path(temp_dir or tempfile.gettempdir())
    if temp.is_dir():
        found += [p for p in temp.glob("crash*") if p.is_file() and isHipFile(p)]
    if hip_path:
        hip_path = Path(hip_path)
        backup = hip_path.parent / "backup"
        if backup.is_dir():
            found += [p for p in backup.glob(f"{hip_path.stem}_bak*") if p.is_file() and isHipFile(p)]
    return sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)


def existingFolder(path: str | Path) -> Path | None:
    """The folder itself, the folder of a file, or the nearest parent that exists"""
    path = Path(path)
    if path.is_file():
        path = path.parent
    while not path.is_dir():
        if path.parent == path:
            return None
        path = path.parent
    return path


def openInFileBrowser(path: str | Path) -> Path | None:
    """Finder / Explorer / the Linux file manager on the folder (the nearest existing one). Returns it."""
    folder = existingFolder(path)
    if folder is None:
        return None
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
    return folder
