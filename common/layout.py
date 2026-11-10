"""Placing nodes in the Network Editor: the grid, snapping without overlaps, making space."""
from __future__ import annotations

import math

import hou

from . import panes

DEFAULT_GRID = (2.0, 1.0)  # Houdini's Network Editor grid: gridxstep / gridystep prefs
GAP = 0.05  # snapped items keep at least this much space between them
SEARCH_RADIUS = 12  # grid cells around the nearest one tried before giving up
# Network Editor draws a node 1/16 narrower than its size(): the body starts at position() but its middle is
# 1/16 left of position + size / 2. Snapping centers the drawn body on the grid line.
BODY_NUDGE = (0.0625, 0.0)


def gridStep(pane=None) -> tuple[float, float]:
    """Grid spacing of the Network Editor (Display Options -> Grid), Houdini's default without one"""
    step = []
    for pref, default in zip(("gridxstep", "gridystep"), DEFAULT_GRID):
        try:
            value = float(pane.getPref(pref)) if pane is not None else default
        except (TypeError, ValueError, AttributeError, hou.OperationFailed):
            value = default
        step.append(value if value > 0 else default)
    return step[0], step[1]


def _overlaps(a, b, gap: float) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw + gap and bx < ax + aw + gap and ay < by + bh + gap and by < ay + ah + gap


def _cellOffsets(step, radius: int) -> list[tuple[int, int]]:
    """Grid cells around (0, 0), nearest first; on a tie lower (further down the network) before higher"""
    cells = [(i, j) for i in range(-radius, radius + 1) for j in range(-radius, radius + 1)]
    return sorted(cells, key=lambda c: (math.hypot(c[0] * step[0], c[1] * step[1]), c[1] > 0, abs(c[0])))


def snapRects(rects, obstacles, step, gap: float = GAP, radius: int = SEARCH_RADIUS,
              nudge=(0.0, 0.0)) -> list[tuple[float, float]]:
    """New lower-left corners for rects (x, y, w, h): each centered on the nearest free grid point.
    nudge: added to the corners, the drawn middle of an item is that far from the middle of its rect.

    Rects are placed top to bottom, left to right, each avoiding the obstacles and the rects placed before it.
    A rect with no free point within the radius keeps its place.
    """
    offsets = _cellOffsets(step, radius)
    order = sorted(range(len(rects)), key=lambda k: (-rects[k][1], rects[k][0]))
    taken = list(obstacles)
    result: list[tuple[float, float] | None] = [None] * len(rects)
    for k in order:
        x, y, w, h = rects[k]
        cell = (round((x - nudge[0] + w / 2) / step[0]), round((y - nudge[1] + h / 2) / step[1]))
        result[k] = (x, y)
        for di, dj in offsets:
            cx, cy = (cell[0] + di) * step[0], (cell[1] + dj) * step[1]
            candidate = (cx - w / 2 + nudge[0], cy - h / 2 + nudge[1], w, h)
            if not any(_overlaps(candidate, other, gap) for other in taken):
                result[k] = (candidate[0], candidate[1])
                break
        taken.append((*result[k], w, h))
    return result


def itemRect(item) -> tuple[float, float, float, float]:
    position, size = item.position(), item.size()
    return position[0], position[1], size[0], size[1]


def networkItems(parent) -> list:
    """Nodes and dots of a network: the things snapping must not cover (boxes and sticky notes can be covered)"""
    items = list(parent.children())
    try:
        items += list(parent.networkDots())
    except AttributeError:
        pass
    return items


NOT_SNAPPED = ("StickyNote", "NetworkBox", "SubnetIndirectInput")


def snappable(items) -> list:
    """Nodes and dots: sticky notes and network boxes keep their place"""
    return [item for item in items if type(item).__name__ not in NOT_SNAPPED]


def snapToGrid(items, pane=None) -> int:
    """Move the items onto the grid of the Network Editor, never on top of another node. Returns how many moved."""
    items = list(items)
    if not items:
        return 0
    moving = {item.path() if hasattr(item, "path") else id(item) for item in items}
    parent = items[0].parent()
    obstacles = [itemRect(i) for i in networkItems(parent)
                 if (i.path() if hasattr(i, "path") else id(i)) not in moving]
    positions = snapRects([itemRect(i) for i in items], obstacles, gridStep(pane), nudge=BODY_NUDGE)
    moved = 0
    for item, (x, y) in zip(items, positions):
        old = item.position()
        if abs(old[0] - x) > 1e-6 or abs(old[1] - y) > 1e-6:
            item.setPosition(hou.Vector2(x, y))
            moved += 1
    return moved


def makeSpace(node, pane=None) -> None:
    """Everything below the node (nodes, dots) moves down two grid rows"""
    shift = 2 * gridStep(pane)[1]
    for item in networkItems(node.parent()):
        if item.position()[1] < node.position()[1] - 1e-6:
            item.setPosition(item.position() - hou.Vector2(0, shift))


# --- network boxes ------------------------------------------------------------------------------------------------

PIXELS_PER_UNIT = 100.0  # without a Network Editor


def pixelsToUnits(pixels: float, pane=None) -> float:
    """Screen pixels of the Network Editor at its current zoom in network units"""
    pane = pane or panes.networkPane()
    scale = PIXELS_PER_UNIT
    if pane is not None:
        try:
            visible, screen = pane.visibleBounds(), pane.screenBounds()
            if visible.size()[0] > 0:
                scale = screen.size()[0] / visible.size()[0]
        except (AttributeError, hou.OperationFailed):
            pass
    return pixels / scale


def networkBox(nodes, name: str, padding_px: float = 15, color=None, pane=None):
    """Network box around the nodes (those in the first node's network) with padding_px screen pixels around
    them at the current zoom; color: hou.Color, default the first node's"""
    parent = nodes[0].parent()
    box = parent.createNetworkBox()
    box.setComment(name.strip())
    for node in nodes:
        if node.parent() == parent:
            box.addItem(node)
    box.fitAroundContents()
    pad = pixelsToUnits(padding_px, pane)
    if pad:
        bounds = box.bounds()
        low, high = bounds.min(), bounds.max()
        box.setBounds(hou.BoundingRect(low[0] - pad, low[1] - pad, high[0] + pad, high[1] + pad))
    box.setColor(color if color is not None else nodes[0].color())
    return box
