"""Writes the checked caches of a 'write_caches' ROP network one after another, each over its own frame range.

Stored as text in the network's user data (USER_DATA) and run by the network's buttons (callback()), so they work
in a scene opened without hotbox: only hou and the standard library here, no hotbox imports.

The network: a Fetch per cache into the Merge MERGE (inputs in the write order); a toggle per Fetch (its template
tag TOGGLE_TAG names the Fetch; off = the Fetch bypassed); options (SKIP_EXISTING...). The Fetch user data keeps
its cache node, version parameter and reload button (CACHE_KEY...).
"""
from __future__ import annotations

import os
import time

import hou

USER_DATA = "hotbox_writer"
MERGE = "write_all"
TOGGLE_TAG = "hotbox_fetch"
CACHE_KEY, VERSION_KEY, RELOAD_KEY = "hotbox_cache", "hotbox_version", "hotbox_reload"
SKIP_EXISTING, VERSION_UP, RELOAD_AFTER, KEEP_GOING = "skip_existing", "version_up_first", "reload_after", "keep_going"
OUTPUT_PARMS = ("sopoutput", "filename", "lopoutput", "copoutput", "file", "picture", "vm_picture")
RELOAD_BUTTONS = ("reload", "reloadgeo", "reloadfile")
TITLE = "Write Caches"


def callback(action: str) -> str:
    """Parameter callback running an action of this module (stored in the network) with the callback's kwargs"""
    return f"exec(kwargs['node'].userData('{USER_DATA}'), g := {{'hou': hou}}) or g['run'](kwargs, '{action}')"


# --- the network ----------------------------------------------------------------------------------------------------

def fetches(network) -> list:
    """The Fetches of the Merge, in the write order"""
    merge = network.node(MERGE)
    return [f for f in merge.inputs() if f is not None] if merge is not None else []


def toggles(network) -> dict:
    """{Fetch name: its toggle parameter}"""
    found = {}
    for parm in network.parms():
        name = parm.parmTemplate().tags().get(TOGGLE_TAG)
        if name:
            found[name] = parm
    return found


def sourceRop(fetch):
    return fetch.node(fetch.evalParm("source"))


def cacheNode(fetch):
    path = fetch.userData(CACHE_KEY)
    return hou.node(path) if path else None


def option(network, name: str, default: bool = False) -> bool:
    parm = network.parm(name)
    return bool(parm.eval()) if parm is not None else default


# --- what is on disk ------------------------------------------------------------------------------------------------

def frameStep(rop) -> tuple[list[int], int]:
    """(frames the ROP writes, step): its own range, or the current frame when it renders the current frame"""
    trange = rop.parm("trange")
    if trange is None or trange.eval() == 0 or rop.parmTuple("f") is None:
        return [round(hou.frame())], 1
    start, end, step = rop.evalParmTuple("f")
    step = max(1, round(step))
    return list(range(round(start), round(end) + 1, step)), step


def outputParm(rop):
    for name in OUTPUT_PARMS:
        parm = rop.parm(name)
        if parm is not None and parm.evalAsString():
            return parm
    return None


def _listing(folder: str) -> set:
    try:
        return {os.path.normcase(name) for name in os.listdir(folder or ".")}
    except OSError:
        return set()


def cacheStatus(rop) -> dict:
    """{'frames', 'step', 'missing' (frames without a file), 'size' (bytes), 'files', 'path' (at the current frame)}"""
    frames, step = frameStep(rop)
    parm = outputParm(rop)
    if parm is None:
        return {"frames": frames, "step": step, "missing": list(frames), "size": 0, "files": 0, "path": ""}
    listings: dict[str, set] = {}
    missing, found = [], set()
    for frame in frames:
        path = parm.evalAtFrame(frame)
        folder, name = os.path.split(path)
        if folder not in listings:
            listings[folder] = _listing(folder)
        if os.path.normcase(name) in listings[folder]:
            found.add(path)
        else:
            missing.append(frame)
    size = 0
    for path in found:
        try:
            size += os.path.getsize(path)
        except OSError:
            pass
    return {"frames": frames, "step": step, "missing": missing, "size": size, "files": len(found),
            "path": parm.evalAsString()}


def formatSize(size: float) -> str:
    """1536 -> '1.5 KB'"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def frameText(frames) -> str:
    return f"{frames[0]}-{frames[-1]}" if len(frames) > 1 else str(frames[0])


def describe(status: dict) -> str:
    """'1001-1100, 3.2 GB, written' / '1001-1100, 40/100 frames' / '1001-1100, not written'"""
    total = len(status["frames"])
    have = total - len(status["missing"])
    if not status["path"]:
        state = "no output path"
    elif have == 0:
        state = "not written"
    elif have == total:
        state = "written"
    else:
        state = f"{have}/{total} frames"
    size = [formatSize(status["size"])] if status["size"] else []
    return ", ".join([frameText(status["frames"]), *size, state])


def frameRuns(frames, step: int = 1) -> list[tuple[int, int]]:
    """[1, 2, 3, 7, 8] -> [(1, 3), (7, 8)]: the ranges to write"""
    runs: list[list[int]] = []
    for frame in frames:
        if runs and frame - runs[-1][1] == step:
            runs[-1][1] = frame
        else:
            runs.append([frame, frame])
    return [(a, b) for a, b in runs]


def label(fetch) -> str:
    cache = cacheNode(fetch)
    name = cache.name() if cache is not None else fetch.name()
    rop = sourceRop(fetch)
    return f"{name}   ({describe(cacheStatus(rop)) if rop is not None else 'ROP not found'})"


# --- actions --------------------------------------------------------------------------------------------------------

def sync(network) -> list:
    """Toggles and bypass agree (off wins: a Fetch bypassed in the network unchecks its toggle).
    Returns the checked Fetches in the write order."""
    switches = toggles(network)
    checked = []
    for fetch in fetches(network):
        toggle = switches.get(fetch.name())
        on = not fetch.isBypassed() and (toggle is None or bool(toggle.eval()))
        if toggle is not None and bool(toggle.eval()) != on:
            toggle.set(int(on))
        fetch.bypass(not on)
        if on:
            checked.append(fetch)
    return checked


def refresh(network) -> None:
    """Toggles synced with the bypass flags, their labels with what is on disk"""
    sync(network)
    group = network.parmTemplateGroup()
    for fetch_name, parm in toggles(network).items():
        fetch = network.node(fetch_name)
        if fetch is None:
            continue
        template = parm.parmTemplate()
        template.setLabel(label(fetch))
        group.replace(parm.name(), template)
    network.setParmTemplateGroup(group)


def checkAll(network, on: bool) -> None:
    for fetch_name, parm in toggles(network).items():
        parm.set(int(on))
        fetch = network.node(fetch_name)
        if fetch is not None:
            fetch.bypass(not on)


def versionUp(fetch) -> int | None:
    cache, name = cacheNode(fetch), fetch.userData(VERSION_KEY)
    parm = cache.parm(name) if cache is not None and name else None
    if parm is None:
        return None
    enable = cache.parm("enableversion")
    if enable is not None:
        enable.set(1)
    parm.set(parm.eval() + 1)
    return parm.eval()


def reloadCache(fetch) -> bool:
    """Press the cache node's reload button: it (and what reads it downstream) loads the new files"""
    cache = cacheNode(fetch)
    if cache is None:
        return False
    for name in (fetch.userData(RELOAD_KEY), *RELOAD_BUTTONS):
        parm = cache.parm(name) if name else None
        if parm is not None and parm.parmTemplate().type() == hou.parmTemplateType.Button:
            parm.pressButton()
            return True
    return False


def _seconds(seconds: float) -> str:
    minutes, seconds = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def writeOne(fetch, skip_existing: bool) -> str:
    """Render the cache's own ROP node by node; skip_existing: only the frames without a file. Returns what it did."""
    rop = sourceRop(fetch)
    if rop is None:
        raise hou.OperationFailed(f"ROP not found: {fetch.evalParm('source')}")
    method = hou.renderMethod.RopByRop
    if not skip_existing:
        rop.render(method=method)
        return "written"
    status = cacheStatus(rop)
    runs = frameRuns(status["missing"], status["step"])
    if not runs:
        return "skipped, all frames on disk"
    for start, end in runs:
        rop.render(frame_range=(start, end, status["step"]), method=method)
    written = len(status["missing"])
    return "written" if written == len(status["frames"]) else f"written {written} missing frame(s)"


def write(network) -> list[tuple[str, str, float]]:
    """Write the checked caches in order. Returns [(cache name, what happened, seconds)] and shows it."""
    checked = sync(network)
    if not checked:
        hou.ui.displayMessage("No cache is checked", title=TITLE)
        return []
    skip, version_up = option(network, SKIP_EXISTING), option(network, VERSION_UP)
    reload_after, keep_going = option(network, RELOAD_AFTER, True), option(network, KEEP_GOING, True)
    interrupted = getattr(hou, "OperationInterrupted", None)
    stops = (interrupted, KeyboardInterrupt) if isinstance(interrupted, type) else (KeyboardInterrupt,)
    report, failed, stopped = [], False, False
    for fetch in checked:
        cache = cacheNode(fetch)
        name = cache.name() if cache is not None else fetch.name()
        start = time.time()
        try:
            version = versionUp(fetch) if version_up else None
            done = writeOne(fetch, skip and version is None)  # a new version has nothing on disk yet
            if version is not None:
                done += f" (v{version})"
            if reload_after:
                reloadCache(fetch)
        except stops:
            report.append((name, "stopped", time.time() - start))
            stopped = True
            break
        except hou.OperationFailed as error:
            report.append((name, f"failed: {str(error).strip() or type(error).__name__}", time.time() - start))
            failed = True
            if not keep_going:
                break
            continue
        report.append((name, done, time.time() - start))
    refresh(network)
    _show(report, failed, stopped, len(checked))
    return report


def _show(report, failed: bool, stopped: bool, count: int) -> None:
    total = sum(seconds for *_, seconds in report)
    lines = [f"{name}: {done}  [{_seconds(seconds)}]" for name, done, seconds in report]
    not_run = count - len(report)
    if not_run:
        lines.append(f"not written: {not_run} cache(s) after it")
    headline = "Stopped" if stopped else "Finished with errors" if failed else "Done"
    hou.ui.displayMessage(f"{headline}, {len(report)} of {count} cache(s) in {_seconds(total)}\n\n" + "\n".join(lines),
                          title=TITLE, severity=hou.severityType.Warning if failed or stopped else
                          hou.severityType.Message)


def run(kwargs, action: str):
    """Entry point of the buttons: write, refresh, all, none, toggle"""
    network = kwargs["node"]
    if action == "write":
        return write(network)
    if action == "refresh":
        return refresh(network)
    if action in ("all", "none"):
        return checkAll(network, action == "all")
    if action == "toggle":
        parm = kwargs["parm"]
        fetch = network.node(parm.parmTemplate().tags().get(TOGGLE_TAG, ""))
        if fetch is not None:
            fetch.bypass(not parm.eval())
        return None
    raise ValueError(f"unknown action {action}")
