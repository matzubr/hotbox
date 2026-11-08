"""Script library: find scripts in lib/<mode>/ and read their settings from the header comments.

A script describes its button in the first comment lines:

    #label:Create Null
    #textcolor:#ff8b48
    #buttoncolor:#22253b
    #icon:app_dino_dance.svg
    #hotkey:n
    #group:Nodes

Buttons with the same #group stand together in one block with a caption.

    #package:blackpoint

makes the script part of a package (several: comma separated): it is shown only while the package is
turned on (Script Manager -> gear, see settings.py). Scripts without a package are always shown.

The same tool in another mode/context: a file with only a header and a reference

    #ref:single/create_null.py
    #hotkey:n

runs the referenced script (path inside lib/). The reference takes the label, colors, icon and group of the
target, its own header overrides them. The hotkey is not inherited: hotkeys are chosen per context.

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
SETTINGS = ("ref", "label", "group", "package", "textcolor", "buttoncolor", "icon", "link", "hotkey")
NOT_INHERITED = ("ref", "hotkey")
MAX_REF_DEPTH = 8
DEFAULTS = {"textcolor": "#e8e8e8", "buttoncolor": "#222222"}

_HEADER_LINE = re.compile(r"^#\s*(\w+)\s*:(.*)$")


@dataclass(frozen=True)
class Script:
    path: Path  # absolute path, resolved from the lib folder at scan time
    relpath: str  # posix path inside lib/<mode>, e.g. "Sop/object_merge_relative.py"
    settings: dict = field(default_factory=dict, compare=False)  # own header merged over the referenced ones
    own: dict | None = field(default=None, compare=False)  # header of this file only (None: same as settings)
    target: Path | None = field(default=None, compare=False)  # file to run (the ref target or the script itself)
    error: str | None = field(default=None, compare=False)  # broken reference

    @property
    def ownSettings(self) -> dict:
        return self.settings if self.own is None else self.own

    @property
    def ref(self) -> str | None:
        return self.ownSettings.get("ref")

    @property
    def runPath(self) -> Path | None:
        """Script to execute; None for a broken reference"""
        if self.error:
            return None
        return self.target or self.path

    @property
    def group(self) -> str:
        return self.settings.get("group") or ""

    @property
    def packages(self) -> list[str]:
        return [name.strip() for name in (self.settings.get("package") or "").split(",") if name.strip()]

    def isAvailable(self, isEnabled) -> bool:
        """Shown in the hotbox: no package, or one of its packages is on"""
        packages = self.packages
        return not packages or any(isEnabled(name) for name in packages)

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
            own = readHeader(path)
        except OSError as e:
            print(f"HotBox: can't read {path.as_posix()}: {e}")
            continue
        if "ref" not in own:
            scripts.append(Script(path=path, relpath=relpath, settings=own))
            continue
        target, settings, error = resolveRef(path, own, folder.parent)
        if error:
            print(f"HotBox: {relpath}: {error}")
        scripts.append(Script(path=path, relpath=relpath, settings=settings, own=own, target=target, error=error))
    return scripts


def resolveRef(path: Path, own: dict, lib_root: Path) -> tuple[Path | None, dict, str | None]:
    """Follow #ref (also chains) from a script. Returns (target file, merged settings, error)."""
    lib_root = Path(lib_root).resolve()
    seen = {Path(path).resolve()}
    chain = [own]
    current = own
    target = None
    while "ref" in current:
        ref = current["ref"].replace("\\", "/").lstrip("/")
        candidate = (lib_root / ref).resolve()
        if lib_root not in candidate.parents:
            return None, _merge([own]), f"#ref:{current['ref']} points outside lib/"
        if candidate in seen:
            return None, _merge([own]), f"#ref:{current['ref']} makes a loop"
        if not candidate.is_file():
            return None, _merge([own]), f"#ref:{current['ref']} not found (lib/{ref})"
        if len(seen) > MAX_REF_DEPTH:
            return None, _merge([own]), "#ref chain is too long"
        seen.add(candidate)
        target = candidate
        current = readHeader(candidate)
        chain.append(current)
    return target, _merge(chain), None


def _merge(chain: list[dict]) -> dict:
    """chain[0] is the script's own header, the rest are the referenced ones (nearest first)"""
    merged = {}
    for settings in reversed(chain[1:]):
        merged.update({k: v for k, v in settings.items() if k not in NOT_INHERITED})
    merged.update(chain[0])
    return merged


def groupBlocks(scripts: list[Script]) -> list[tuple[str, list[Script]]]:
    """Blocks of buttons in a column: (group name, scripts) for each #group, ('', [script]) for ungrouped ones.

    Blocks are sorted by group name / label, scripts in a group by label: the order doesn't depend on file names.
    A group with one script is shown as a plain button.
    """
    groups: dict[str, list[Script]] = {}
    blocks: list[tuple[str, list[Script]]] = []
    for script in scripts:
        if script.group:
            groups.setdefault(script.group, []).append(script)
        else:
            blocks.append(("", [script]))
    for name, members in groups.items():
        if len(members) == 1:  # a group of one is just a button
            blocks.append(("", members))
        else:
            blocks.append((name, sorted(members, key=lambda s: s.label.casefold())))
    return sorted(blocks, key=lambda block: (block[0] or block[1][0].label).casefold())


def availableScripts(scripts: list[Script], isEnabled) -> list[Script]:
    """Scripts of the turned on packages (and the ones without a package)"""
    return [script for script in scripts if script.isAvailable(isEnabled)]


def allPackages(lib_root: Path) -> dict[str, list[str]]:
    """{package: ["mode/relpath", ...]} over all modes of lib/; names as written in the first script"""
    packages: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for mode in MODES:
        for script in scanScripts(Path(lib_root) / mode):
            for name in script.packages:
                key = names.setdefault(name.casefold(), name)
                packages.setdefault(key, []).append(f"{mode}/{script.relpath}")
    return dict(sorted(packages.items(), key=lambda item: item[0].casefold()))


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
