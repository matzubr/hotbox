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

Several libraries: HOTBOX_PATH lists more lib folders (';' separated, ':' too on Linux/macOS), searched in
order before the built-in lib/. A script in an earlier folder hides the one with the same mode/relpath in a
later folder; #ref targets are looked up the same way. Personal and studio scripts live outside the tool folder.

Nothing is cached on disk: headers are read every time the hotbox opens (a few dozen small files),
so the tool folder can be copied between users and machines as is. The old schema.json cache kept
absolute paths of the machine it was created on and broke on every other one.

No hou / Qt imports here: the module is tested without Houdini.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MODES = ("all", "multiple", "single")
SETTINGS = ("ref", "label", "group", "package", "textcolor", "buttoncolor", "icon", "link", "hotkey")
PATH_ENV = "HOTBOX_PATH"
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
    root: Path | None = field(default=None, compare=False)  # lib folder the script comes from

    @property
    def key(self) -> str:
        """'mode/relpath': the same in every lib folder (lib/single/null/x.py -> 'single/null/x.py')"""
        return f"{self.path.relative_to(self.root).parts[0]}/{self.relpath}" if self.root else self.relpath

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
    def mode(self) -> str | None:
        """all / multiple / single: the lib/<mode> folder the file is in"""
        if self.root is None:
            return None
        try:
            return Path(self.path).relative_to(self.root).parts[0]
        except ValueError:
            return None

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


def splitPathList(value: str) -> list[str]:
    """HOTBOX_PATH items: ';' separated; on Linux/macOS ':' too (Windows drive letters keep their ':')"""
    separators = r";" if sys.platform == "win32" else r"[;:]"
    return [item.strip() for item in re.split(separators, value or "") if item.strip()]


def libRoots(builtin: Path, value: str | None = None) -> list[Path]:
    """Lib folders to read, first wins: HOTBOX_PATH folders, then the built-in lib/.
    Folders that don't exist are skipped (with a message), duplicates are dropped."""
    value = os.environ.get(PATH_ENV, "") if value is None else value
    roots: list[Path] = []
    for item in splitPathList(value):
        folder = Path(os.path.expandvars(os.path.expanduser(item)))
        if not folder.is_dir():
            print(f"HotBox: {PATH_ENV}: no folder {folder.as_posix()}")
            continue
        roots.append(folder)
    roots.append(Path(builtin))
    unique, seen = [], set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(root)
    return unique


def asRoots(lib_roots) -> list[Path]:
    """A lib folder or a list of them -> list of Paths"""
    if isinstance(lib_roots, (str, Path)):
        return [Path(lib_roots)]
    return [Path(root) for root in lib_roots]


def scanLibrary(lib_roots, mode: str) -> list[Script]:
    """Scripts of a mode over all lib folders; a script hides the same relpath in later folders"""
    roots = asRoots(lib_roots)
    found: dict[str, Script] = {}
    for root in roots:
        for script in scanScripts(root / mode, lib_roots=roots):
            found.setdefault(script.relpath, script)
    return sorted(found.values(), key=lambda script: script.relpath)


def scanScripts(folder: Path, suffixes=(".py",), lib_roots=None) -> list[Script]:
    """All scripts in a lib/<mode> folder, sorted by relative path.
    lib_roots: all lib folders, for #ref lookup (default: only the one this folder is in)"""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    root = folder.parent
    roots = asRoots(lib_roots) if lib_roots is not None else [root]
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
            scripts.append(Script(path=path, relpath=relpath, settings=own, root=root))
            continue
        target, settings, error = resolveRef(path, own, roots)
        if error:
            print(f"HotBox: {relpath}: {error}")
        scripts.append(Script(path=path, relpath=relpath, settings=settings, own=own, target=target, error=error,
                              root=root))
    return scripts


def findRef(ref: str, lib_roots) -> tuple[Path | None, str | None]:
    """File of a #ref value in the first lib folder that has it. (path, error)"""
    ref = ref.replace("\\", "/").lstrip("/")
    for root in asRoots(lib_roots):
        root = root.resolve()
        candidate = (root / ref).resolve()
        if root not in candidate.parents:
            return None, "points outside lib/"
        if candidate.is_file():
            return candidate, None
    return None, f"not found (lib/{ref})"


def resolveRef(path: Path, own: dict, lib_roots) -> tuple[Path | None, dict, str | None]:
    """Follow #ref (also chains) from a script. Returns (target file, merged settings, error).
    lib_roots: a lib folder or the list of them (HOTBOX_PATH order)."""
    seen = {Path(path).resolve()}
    chain = [own]
    current = own
    target = None
    while "ref" in current:
        candidate, error = findRef(current["ref"], lib_roots)
        if error:
            return None, _merge([own]), f"#ref:{current['ref']} {error}"
        if candidate in seen:
            return None, _merge([own]), f"#ref:{current['ref']} makes a loop"
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
    A group with one script is framed too: every #group has its caption.
    """
    groups: dict[str, list[Script]] = {}
    blocks: list[tuple[str, list[Script]]] = []
    for script in scripts:
        if script.group:
            groups.setdefault(script.group, []).append(script)
        else:
            blocks.append(("", [script]))
    for name, members in groups.items():
        blocks.append((name, sorted(members, key=lambda s: s.label.casefold())))
    return sorted(blocks, key=lambda block: (block[0] or block[1][0].label).casefold())


def availableScripts(scripts: list[Script], isEnabled) -> list[Script]:
    """Scripts of the turned on packages (and the ones without a package)"""
    return [script for script in scripts if script.isAvailable(isEnabled)]


def allPackages(lib_roots) -> dict[str, list[str]]:
    """{package: ["mode/relpath", ...]} over all modes of the lib folders; names as written in the first script"""
    packages: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for mode in MODES:
        for script in scanLibrary(lib_roots, mode):
            for name in script.packages:
                key = names.setdefault(name.casefold(), name)
                packages.setdefault(key, []).append(f"{mode}/{script.relpath}")
    return dict(sorted(packages.items(), key=lambda item: item[0].casefold()))


def scriptsForContext(scripts: list[Script], context: str) -> tuple[list[Script], list[Script]]:
    """(scripts of the context folder, scripts of the root folder).

    Deeper folders (e.g. Lop/Instances) are not shown: they never match a context.
    A root script of a #group the context also has joins the context one: one frame, one caption.
    """
    in_context = [s for s in scripts if context and s.context == context]
    root = [s for s in scripts if s.context == ""]
    shared = {s.group for s in in_context if s.group}
    return in_context + [s for s in root if s.group in shared], [s for s in root if s.group not in shared]


def duplicateHotkeys(scripts: list[Script]) -> dict[str, list[str]]:
    """Hotkeys used by more than one of the shown scripts: {hotkey: [relpath, ...]}"""
    used: dict[str, list[str]] = {}
    for script in scripts:
        if script.hotkey:
            used.setdefault(script.hotkey.lower(), []).append(script.relpath)
    return {key: paths for key, paths in used.items() if len(paths) > 1}


def _readText(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:  # keep \r\n of Windows files
        return f.read()


def _splitHeader(lines: list[str]) -> int:
    """Index of the first line after the leading comment block"""
    index = 0
    while index < len(lines) and lines[index].strip().startswith("#"):
        index += 1
    return index


def readBody(path: Path) -> str:
    """The code after the header comments ('\n' newlines)"""
    lines = _readText(path).splitlines()
    return "\n".join(lines[_splitHeader(lines):])


def writeHeader(path: Path, settings: dict, body: str | None = None) -> None:
    """Replace the '#key:value' settings at the top of a script, keep other comments and the code
    (or replace the code with body). Empty values are removed from the header.
    """
    path = Path(path)
    text = _readText(path)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    end = _splitHeader(lines)

    kept_comments = []
    for line in lines[:end]:
        match = _HEADER_LINE.match(line.strip())
        if not (match and match.group(1).lower() in SETTINGS):
            kept_comments.append(line)

    header = [f"#{key}:{str(settings[key]).strip()}" for key in SETTINGS if str(settings.get(key) or "").strip()]
    code = lines[end:] if body is None else body.splitlines()
    ends_with_newline = text.endswith(("\n", "\r")) if body is None else True
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(newline.join(kept_comments + header + code) + (newline if ends_with_newline else ""))


def writeBody(path: Path, body: str) -> None:
    """Replace the code of a script, keep its header as it is"""
    writeHeader(path, readHeader(path), body=body)


def scriptRefs(lib_roots) -> list[str]:
    """Every script as a #ref value ('single/create_null.py'), scripts that are refs themselves excluded"""
    return [f"{mode}/{s.relpath}" for mode in MODES for s in scanLibrary(lib_roots, mode) if not s.ref]


# --- new scripts ---------------------------------------------------------------------------------------------------

NETWORK_FOLDERS = ("Sop", "Object", "Lop", "Dop", "Cop", "Top", "Driver", "Chop", "Vop")  # context folders of all/multiple
SCRIPT_TEMPLATES = {
    "all": "import hou\n\n",
    "multiple": "import hou\n\nfor node in hou.selectedNodes():\n    pass\n",
    "single": "import hou\n\nnode = hou.selectedNodes()[0]\n",
}
_FOLDER_NAME = re.compile(r"^[\w.-]*$")


def scriptFileName(name: str) -> str:
    """'Bake Camera!' -> 'bake_camera.py'"""
    stem = re.sub(r"[^\w-]+", "_", name.strip().removesuffix(".py")).strip("_").lower()
    return f"{stem}.py" if stem else ""


def newScriptPath(root: Path, mode: str, folder: str, filename: str) -> tuple[Path | None, str | None]:
    """Where a new script goes: (path, None) or (None, why it can't be created)"""
    folder = folder.strip().strip("/")
    filename = scriptFileName(filename)
    if mode not in MODES:
        return None, f"Mode must be one of {', '.join(MODES)}"
    if not filename:
        return None, "Give the script a name"
    if not _FOLDER_NAME.match(folder) or folder in (".", ".."):
        return None, "Folder: one level only (a network type like Sop, or a node type like cam)"
    path = Path(root) / mode / folder / filename
    if path.exists():
        return None, f"{mode}/{(Path(folder) / filename).as_posix()} already exists"
    return path, None


def createScript(root: Path, mode: str, folder: str, filename: str, label: str = "") -> Path:
    """New script file with a #label header and a starting body for the mode"""
    path, error = newScriptPath(root, mode, folder, filename)
    if error:
        raise ValueError(error)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"#label:{label.strip()}\n\n" if label.strip() else ""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + SCRIPT_TEMPLATES[mode])
    return path


def freeCopyPath(path: Path) -> Path:
    """'x.py' -> 'x_copy.py' next to it, 'x_copy2.py'... when taken"""
    path = Path(path)
    for number in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_copy{'' if number == 1 else number}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"No free name for a copy of {path.name}")


def refUsers(lib_roots, path: Path) -> list[str]:
    """Scripts ('multiple/x.py') that run the file through #ref"""
    path = Path(path).resolve()
    return [f"{mode}/{s.relpath}" for mode in MODES for s in scanLibrary(lib_roots, mode)
            if s.ref and s.runPath is not None and Path(s.runPath).resolve() == path]


def overrides(lib_roots, root: Path, key: str) -> tuple[list[Path], list[Path]]:
    """For a script key ('single/cam/x.py') in root: (earlier roots that hide it, later roots it hides)"""
    roots = asRoots(lib_roots)
    index = next((i for i, r in enumerate(roots) if Path(r).resolve() == Path(root).resolve()), len(roots))
    has = [r for r in roots if (Path(r) / key).is_file()]
    return [r for r in has if roots.index(r) < index], [r for r in has if roots.index(r) > index]


def headerLineCount(path: Path) -> int:
    """Lines of the leading comment block (readBody drops them)"""
    return _splitHeader(_readText(path).splitlines())


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


def matchesSearch(label: str, query: str) -> bool:
    """Every word of the query is in the label (case ignored); a query typed in the Russian layout
    is also tried as the Latin keys it was typed on"""
    label = label.casefold()
    candidates = {query.casefold(), "".join(LAYOUT_TO_LATIN.get(c, c) for c in query.casefold())}
    return any(all(word in label for word in candidate.split()) for candidate in candidates if candidate.strip())


# Russian ЙЦУКЕН -> the Latin letter on the same physical key, so hotkeys work in either keyboard layout
LAYOUT_TO_LATIN = dict(zip("йцукенгшщзхъфывапролджэячсмитьбюё", "qwertyuiop[]asdfghjkl;'zxcvbnm,.`", strict=True))


def latinKey(text: str) -> str | None:
    """Latin character of the same key for a character typed in another layout, None when unknown"""
    return LAYOUT_TO_LATIN.get(text.lower()) if text else None


# --- tooltips -------------------------------------------------------------------------------------------------------

DESCRIPTION_LIMIT = 220


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= DESCRIPTION_LIMIT else text[:DESCRIPTION_LIMIT - 1].rstrip() + "…"


def scriptDescription(path: Path | None) -> str | None:
    """What the script does: the comment block at the top of its code, else the docstring of main() / the module"""
    import ast

    if path is None:
        return None
    try:
        lines = _readText(Path(path)).splitlines()
    except OSError:
        return None
    start = 0
    while start < len(lines) and (match := _HEADER_LINE.match(lines[start].strip())) and match.group(1) in SETTINGS:
        start += 1  # the #label:... header
    body = "\n".join(lines[start:])
    comment = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped and not comment:
            continue
        if not stripped.startswith("#"):
            break
        text = stripped.lstrip("#").strip()
        if text and not text.lower().startswith(("noqa", "type:", "pylint")):
            comment.append(text)
    if comment:
        return _shorten(" ".join(comment))
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return None
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    main = next((f for f in functions if f.name == "main"), functions[0] if functions else None)
    for node in (main, tree):
        docstring = ast.get_docstring(node) if node is not None else None
        if docstring:
            return _shorten(docstring)
    return None


def worksOn(script: Script) -> str:
    """When the button is shown: the selection and the network / node type"""
    context = script.context
    mode = script.mode
    if mode == "all":
        return f"Nothing selected, in {context} networks" if context else "Nothing selected, any network"
    if mode == "multiple":
        return f"Several selected nodes in {context} networks" if context else "Several selected nodes"
    if mode == "single":
        return f"One selected {context} node" if context else "One selected node"
    return ""
