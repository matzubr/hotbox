"""Creating and placing nodes."""
from __future__ import annotations

import os
import re
import zipfile

import hou

from . import panes

INPUT_LIMIT = 4


def clipboardNodes() -> list:
    """Nodes whose paths are in the clipboard (Ctrl+C on nodes copies their paths, space separated)"""
    nodes = [hou.node(path) for path in hou.ui.getTextFromClipboard().split()]
    return [node for node in nodes if node is not None]


def createAttribNode(node_type: str, color: tuple[float, float, float]):
    """Node below the selected SOPs with them as inputs (up to 4), display/render flags on it"""
    nodes = hou.selectedNodes()
    if not nodes or any(n.parent().childTypeCategory() != hou.sopNodeTypeCategory() for n in nodes):
        panes.warn("Select SOP nodes")
        return None

    node = nodes[0].parent().createNode(node_type)
    inputs = nodes[:INPUT_LIMIT]
    for i, source in enumerate(inputs):
        node.setInput(i, source)

    positions = [n.position() for n in inputs]
    x = sum(p[0] for p in positions) / len(positions)
    y = min(p[1] for p in positions)
    node.setPosition(hou.Vector2(x, y - 1))
    node.setColor(hou.Color(*color))
    node.setDisplayFlag(True)
    node.setRenderFlag(True)
    node.setCurrent(True, clear_all_selected=True)
    return node


def styleLikeSource(node, source, shape: str | None = None) -> None:
    """Node shape (Network Editor shapes: 'chevron_up', 'circle'...) and the color of the source node"""
    if shape:
        node.setUserData("nodeshape", shape)
    node.setColor(source.color())


def pasteMergeNodes(category: str, node_type: str, path_parm: str, relative: bool, extra_parms=None,
                    shape: str | None = None, copy_color: bool = False, prefix: str = "MERGE_") -> list:
    """Object Merge / Fetch / SOP Import for each node in the clipboard, at the cursor of the Network Editor.

    category: network type the tool works in ("Sop", "Lop");
    extra_parms: {name: value} set on each node, a callable value gets the source node: {"pathprefix": f(source)};
    shape / copy_color: node shape of the created nodes, color taken from the copied node;
    prefix: name of the created node is prefix + source name.
    """
    pane = panes.networkPane()
    if pane is None:
        panes.warn("No Network Editor")
        return []
    network = pane.pwd()
    if network.childTypeCategory().name() != category:
        panes.warn(f"Works in {category} networks only")
        return []
    sources = clipboardNodes()
    if not sources:
        panes.warn("No node paths in the clipboard: copy nodes first")
        return []

    created = []
    for i, source in enumerate(sources):
        node = network.createNode(node_type, f"{prefix}{source.name()}")
        node.setPosition(pane.cursorPosition() + hou.Vector2(i * 3, 0) - hou.Vector2(0.5, 0))
        node.parm(path_parm).set(node.relativePathTo(source) if relative else source.path())
        for name, value in (extra_parms or {}).items():
            node.parm(name).set(value(source) if callable(value) else value)
        if copy_color:
            styleLikeSource(node, source, shape)
        elif shape:
            node.setUserData("nodeshape", shape)
        created.append(node)
    return created


def _overlaps(position, size, item, pad: float) -> bool:
    other, other_size = item.position(), item.size()
    return (position[0] < other[0] + other_size[0] + pad and other[0] < position[0] + size[0] + pad
            and position[1] < other[1] + other_size[1] + pad and other[1] < position[1] + size[1] + pad)


def freePosition(network, position, size=(1.0, 0.3), step: float = 1.0, pad: float = 0.2, ignore=()):
    """First spot at or below position where a node of this size doesn't cover any item of the network"""
    ignore = {item.path() for item in ignore}
    items = [item for item in network.children() if item.path() not in ignore]
    x, y = position[0], position[1]
    for _ in range(1000):
        if not any(_overlaps((x, y), size, item, pad) for item in items):
            break
        y -= step
    return hou.Vector2(x, y)


# --- clipboard paths ----------------------------------------------------------------------------------------------

_PATH = re.compile(r"/[\w.\-/:]*\w")


def nodeFromText(text: str):
    """First node named in the text: a node path, a parameter path (its node), a path inside an expression"""
    for token in [t.strip("\"'`(),;") for t in (text or "").split()] + _PATH.findall(text or ""):
        if not token.startswith("/"):
            continue
        node = hou.node(token)
        if node is not None:
            return node
        parm = hou.parm(token)
        if parm is not None:
            return parm.node()
    return None


def showInNetwork(node, pane=None) -> None:
    """The Network Editor goes into the node's network, selects it and frames it"""
    pane = pane or panes.networkPane()
    node.setCurrent(True, clear_all_selected=True)
    if pane is not None:
        pane.setCurrentNode(node)
        pane.homeToSelection()


# --- copies and blocks --------------------------------------------------------------------------------------------

def referenceCopy(nodes) -> list:
    """Copies of the nodes with every parameter channel-referencing the original, wired to the same inputs"""
    nodes = [n for n in nodes if n.parent() == nodes[0].parent()]
    parent = nodes[0].parent()
    copies = list(parent.copyItems(nodes, channel_reference_originals=True))
    originals = {n.path() for n in nodes}
    for original, copy in zip(nodes, copies):
        copy.setPosition(original.position() + hou.Vector2(3, 0))
        for connection in original.inputConnections():
            source = connection.inputItem()
            if getattr(source, "path", lambda: None)() in originals:
                continue  # wired inside the copied group already
            if copy.input(connection.inputIndex()) is None:
                copy.setInput(connection.inputIndex(), source, connection.outputIndex())
    return copies


def _place(network, node, wanted) -> None:
    node.setPosition(freePosition(network, wanted, node.size(), step=0.5, ignore=[node]))


def compileBlock(nodes) -> tuple:
    """Compile Begin before every input coming into the SOPs, one Compile End after them. (begins, end)

    The selection must end in one node. For-each blocks inside get Multithread turned on (they compile then).
    """
    nodes = list(nodes)
    selected = {n.path() for n in nodes}
    parent = nodes[0].parent()
    if any(n.parent() != parent for n in nodes) or parent.childTypeCategory() != hou.sopNodeTypeCategory():
        raise ValueError("Select SOP nodes of one network")
    bottoms = [n for n in nodes if not any(o.path() in selected for o in n.outputs())]
    if len(bottoms) != 1:
        raise ValueError(f"The selection must end in one node, it ends in {len(bottoms)}")
    bottom = bottoms[0]

    outputs = [c for c in bottom.outputConnections() if c.outputNode().path() not in selected]
    end = parent.createNode("compile_end")
    end.setInput(0, bottom)
    for connection in outputs:
        connection.outputNode().setInput(connection.inputIndex(), end, 0)
    _place(parent, end, bottom.position() - hou.Vector2(0, 1))

    begins = {}
    for node in nodes:
        for connection in node.inputConnections():
            source = connection.inputItem()
            if getattr(source, "path", lambda: None)() in selected:
                continue
            key = (id(source) if not hasattr(source, "path") else source.path(), connection.outputIndex())
            if key not in begins:
                begin = parent.createNode("compile_begin")
                begin.setInput(0, source, connection.outputIndex())
                begin.parm("blockpath").set(begin.relativePathTo(end))
                _place(parent, begin, node.position() + hou.Vector2(0, 1))
                begins[key] = begin
            node.setInput(connection.inputIndex(), begins[key], 0)
        if node.type().name() == "block_end" and node.parm("multithread") is not None:
            node.parm("multithread").set(1)
    return list(begins.values()), end


# --- help ---------------------------------------------------------------------------------------------------------

_SUMMARY = re.compile(r'"""(.*?)"""', re.DOTALL)


def helpFileNames(node_type) -> list[str]:
    """Candidate names of the type's page in $HFS/houdini/help/nodes.zip: sop/null.txt, sop/filecache-2.0.txt,
    sop/labs--tool-1.0.txt (namespace--name-version), then the plain name"""
    category = node_type.category().name().lower()
    try:
        _scope, namespace, name, version = node_type.nameComponents()
    except (AttributeError, ValueError, TypeError):
        _scope, namespace, name, version = "", "", node_type.name(), ""
    full = (f"{namespace}--" if namespace else "") + name + (f"-{version}" if version else "")
    names = [full, f"{namespace}--{name}" if namespace else name, name]
    return [f"{category}/{n}.txt" for n in dict.fromkeys(names)]


def helpSummary(text: str) -> str | None:
    """The one line summary of a help page: the first \"\"\"...\"\"\" block"""
    match = _SUMMARY.search(text or "")
    summary = " ".join(match.group(1).split()) if match else ""
    return summary or None


def nodeHelpSummary(node_type) -> str | None:
    """Summary of the node's help: the asset's own help, else the page in Houdini's help archive"""
    try:
        summary = helpSummary(node_type.embeddedHelp())
    except (AttributeError, hou.OperationFailed):
        summary = None
    if summary:
        return summary
    archive = os.path.join(hou.getenv("HFS") or "", "houdini", "help", "nodes.zip")
    if not os.path.isfile(archive):
        return None
    with zipfile.ZipFile(archive) as zip_file:
        names = set(zip_file.namelist())
        for name in helpFileNames(node_type):
            if name in names:
                return helpSummary(zip_file.read(name).decode("utf-8", "replace"))
    return None


# --- selection ----------------------------------------------------------------------------------------------------

def _network(selected=None):
    """Network of the selected nodes, else the one the Network Editor shows"""
    selected = hou.selectedNodes() if selected is None else selected
    if selected:
        return selected[0].parent()
    pane = panes.networkPane()
    return pane.pwd() if pane is not None else None


def selectNodes(found) -> None:
    hou.clearAllSelected()
    for node in found:
        node.setSelected(True)
    if found:
        found[0].setCurrent(True, clear_all_selected=False)


def selectInNetwork(predicate, what: str) -> list:
    """Select the nodes of the current network that pass the predicate"""
    network = _network()
    if network is None:
        return []
    found = [node for node in network.children() if predicate(node)]
    selectNodes(found)
    hou.ui.setStatusMessage(f"{len(found)} {what} node(s) in {network.path()}")
    return found


def selectModified(selected) -> list:
    """Nothing selected: the node of the network changed last. Selected: plus the next older one"""
    network = _network(selected)
    if network is None:
        return []
    by_date = sorted(network.children(), key=lambda n: n.modificationTime(), reverse=True)
    chosen = {n.path() for n in selected}
    found = [n for n in by_date if n.path() in chosen]
    rest = [n for n in by_date if n.path() not in chosen]
    if rest:
        oldest = min((n.modificationTime() for n in found), default=None)
        older = [n for n in rest if oldest is None or n.modificationTime() <= oldest]
        found.append((older or rest)[0])
    selectNodes(found)
    return found


def toggleBypass(nodes) -> bool | None:
    """Bypass all; when all are bypassed already: un-bypass. The new state, None without nodes"""
    nodes = list(nodes)
    if not nodes:
        return None
    state = not all(node.isBypassed() for node in nodes)
    for node in nodes:
        try:
            node.bypass(state)
        except hou.OperationFailed:  # nodes without a bypass flag (some OBJ / ROP types)
            pass
    return state


# --- sticky notes -------------------------------------------------------------------------------------------------

def noteHeader() -> str:
    import datetime
    import getpass

    return f"{getpass.getuser()}  {datetime.datetime.now():%Y-%m-%d %H:%M}"


def addStickyNote(selected, pane=None):
    """A note signed with the user and date: at the cursor, or right of the selected node in its color"""
    pane = pane or panes.networkPane()
    node = selected[0] if selected else None
    network = node.parent() if node is not None else (pane.pwd() if pane is not None else None)
    if network is None:
        return None
    note = network.createStickyNote()
    note.setSize(hou.Vector2(4, 1.5))
    if node is not None:
        note.setText(f"{noteHeader()}\n{node.name()}: ")
        note.setColor(node.color())
        wanted = node.position() + hou.Vector2(node.size()[0] + 0.5, 0)
        note.setPosition(freePosition(network, wanted, note.size(), step=0.5, ignore=[note]))
    else:
        note.setText(f"{noteHeader()}\n")
        if pane is not None:
            note.setPosition(pane.cursorPosition() - hou.Vector2(0, note.size()[1]))
    return note
