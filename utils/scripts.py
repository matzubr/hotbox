"""Script library: find scripts in lib/<mode>/ and read their settings from the header comments.

A script describes its button in the first comment lines:

    #label:Create Null
    #textcolor:#ff8b48
    #buttoncolor:#22253b
    #icon:app_dino_dance.svg
    #hotkey:n

Nothing is cached on disk: headers are read every time the hotbox opens (a few dozen small files),
so the tool folder can be copied between users and machines as is. The old schema.json cache kept
absolute paths of the machine it was created on and broke on every other one.

No hou / Qt imports here: the module is tested without Houdini.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MODES = ("all", "multiple", "single")
SETTINGS = ("label", "textcolor", "buttoncolor", "icon", "link", "hotkey")
DEFAULTS = {"textcolor": "#e8e8e8", "buttoncolor": "#222222"}

_HEADER_LINE = re.compile(r"^#\s*(\w+)\s*:(.*)$")


@dataclass(frozen=True)
class Script:
    path: Path  # absolute path, resolved from the lib folder at scan time
    relpath: str  # posix path inside lib/<mode>, e.g. "Sop/object_merge_relative.py"
    settings: dict = field(default_factory=dict, compare=False)

    @property
    def context(self) -> str:
        """Folder inside lib/<mode>: network type (Sop, Lop...) or node type (cam, null...); '' for the root"""
        parent = Path(self.relpath).parent.as_posix()
        return "" if parent == "." else parent

    @property
    def label(self) -> str:
        return self.settings.get("label") or Path(self.relpath).stem

    @property
    def hotkey(self) -> str | None:
        return self.settings.get("hotkey") or None

    @property
    def icon(self) -> str | None:
        return self.settings.get("icon") or None

    @property
    def textcolor(self) -> str:
        return self.settings.get("textcolor") or DEFAULTS["textcolor"]

    @property
    def buttoncolor(self) -> str:
        return self.settings.get("buttoncolor") or DEFAULTS["buttoncolor"]


def readHeader(path: Path) -> dict:
    """Settings from the leading '#key:value' comment lines (reading stops at the first other line)"""
    settings = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                break
            match = _HEADER_LINE.match(line)
            if not match:
                continue
            key, value = match.group(1).lower(), match.group(2).strip()
            if key in SETTINGS and value and value != "None":
                settings[key] = value
    return settings


def scanScripts(folder: Path, suffixes=(".py",)) -> list[Script]:
    """All scripts in a lib/<mode> folder, sorted by relative path"""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    scripts = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes or "__pycache__" in path.parts:
            continue
        relpath = path.relative_to(folder).as_posix()
        try:
            settings = readHeader(path)
        except OSError as e:
            print(f"HotBox: can't read {path.as_posix()}: {e}")
            continue
        scripts.append(Script(path=path, relpath=relpath, settings=settings))
    return scripts


def scriptsForContext(scripts: list[Script], context: str) -> tuple[list[Script], list[Script]]:
    """(scripts of the context folder, scripts of the root folder).

    Deeper folders (e.g. Lop/Instances) are not shown: they never match a context.
    """
    in_context = [s for s in scripts if context and s.context == context]
    root = [s for s in scripts if s.context == ""]
    return in_context, root


def duplicateHotkeys(scripts: list[Script]) -> dict[str, list[str]]:
    """Hotkeys used by more than one of the shown scripts: {hotkey: [relpath, ...]}"""
    used: dict[str, list[str]] = {}
    for script in scripts:
        if script.hotkey:
            used.setdefault(script.hotkey.lower(), []).append(script.relpath)
    return {key: paths for key, paths in used.items() if len(paths) > 1}


def writeHeader(path: Path, settings: dict) -> None:
    """Replace the '#key:value' settings at the top of a script, keep other comments and the code.

    Empty values are removed from the header.
    """
    path = Path(path)
    with open(path, encoding="utf-8", newline="") as f:  # keep \r\n of Windows files
        text = f.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()

    kept_comments = []
    index = 0
    while index < len(lines) and lines[index].strip().startswith("#"):
        match = _HEADER_LINE.match(lines[index].strip())
        if not (match and match.group(1).lower() in SETTINGS):
            kept_comments.append(lines[index])
        index += 1

    header = [f"#{key}:{str(settings[key]).strip()}" for key in SETTINGS if str(settings.get(key) or "").strip()]
    result = kept_comments + header + lines[index:]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(newline.join(result) + (newline if text.endswith(("\n", "\r")) else ""))


def visibleTogether(a: Script, b: Script) -> bool:
    """Scripts of one mode folder that can be on screen at the same time (root scripts show with every context)"""
    return a.context == b.context or a.context == "" or b.context == ""


def hotkeyConflicts(scripts: list[Script], script: Script, hotkey: str) -> list[str]:
    """Other scripts shown together with this one that already use the hotkey"""
    hotkey = (hotkey or "").strip().lower()
    if not hotkey:
        return []
    return [
        other.relpath
        for other in scripts
        if other.relpath != script.relpath and visibleTogether(script, other) and (other.hotkey or "").lower() == hotkey
    ]


# Russian ЙЦУКЕН -> the Latin letter on the same physical key, so hotkeys work in either keyboard layout
LAYOUT_TO_LATIN = dict(zip("йцукенгшщзхъфывапролджэячсмитьбюё", "qwertyuiop[]asdfghjkl;'zxcvbnm,.`", strict=True))


def latinKey(text: str) -> str | None:
    """Latin character of the same key for a character typed in another layout, None when unknown"""
    return LAYOUT_TO_LATIN.get(text.lower()) if text else None
