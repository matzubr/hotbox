"""Cache Report: every cache node of the scene (common/cachetypes.py) with its version, frame range and what is on
disk; the picked ones can be selected, opened, written with Cache Network or cleaned of old versions."""
from __future__ import annotations

import hou

from ..common import caches, cachetypes, cachewriter, hipfile, nodes, paths, versions
from .frameless import RoundedWindow, TitleBar
from .qt import (
    QAbstractItemView,
    QBrush,
    QColor,
    QHeaderView,
    QLabel,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .theme import COLORS, PANEL_RADIUS
from .widgets import Button, HLayout, buttonFont

COLUMNS = ("Node", "Type", "Version", "Frames", "On disk", "Size", "Path")
STATE_COLORS = {"written": "#8fffc1", "partial": COLORS["warning"], "missing": "#ff8f8f", "none": "#8a8a8a"}


def cacheRow(node) -> dict:
    """What the report shows of one cache node"""
    version = cachetypes.versionParm(node)
    rop = caches.ropOf(node)
    row = {"node": node, "path": node.path(), "name": node.name(), "type": caches.typeKey(node),
           "version": str(version.eval()) if version is not None else "", "frames": "", "disk": "ROP not found",
           "size": 0, "file": "", "state": "none"}
    if rop is None:
        return row
    status = cachewriter.cacheStatus(rop)
    total, have = len(status["frames"]), len(status["frames"]) - len(status["missing"])
    row.update(frames=cachewriter.frameText(status["frames"]), size=status["size"], file=status["path"],
               disk=f"{have}/{total}" if total > 1 else ("yes" if have else "no"),
               state="none" if not status["path"] else "written" if have == total else "partial" if have else "missing")
    return row


def sceneCaches() -> list[dict]:
    return sorted((cacheRow(node) for node in cachetypes.instances()), key=lambda row: row["path"])


class _SizeItem(QTableWidgetItem):
    """Sorted by bytes, shown as '3.2 GB'"""

    def __lt__(self, other):
        return (self.data(Qt.UserRole) or 0) < (other.data(Qt.UserRole) or 0)


class CacheReport(RoundedWindow, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.setWindowTitle("Cache Report")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupRoundedWindow()

        self.summary = QLabel()
        self.summary.setFont(buttonFont(11))
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(lambda _item: self.showNode())

        small = {"buttonColor": "#4a4a4a", "size": (130, 32), "fontSize": 11}
        actions = [("Refresh", self.refresh), ("Select", self.selectNodes), ("Open Folder", self.openFolder),
                   ("Cache Network", self.cacheNetwork), ("Clean Old Versions", self.cleanVersions)]
        self.buttons = {}
        for text, slot in actions:
            self.buttons[text] = Button(text, **small)
            self.buttons[text].clicked.connect(slot)
        close = Button("Close", **small)
        close.clicked.connect(self.close)

        body = QWidget()
        body.setObjectName("Panel")
        body.setAttribute(Qt.WA_StyledBackground)
        body.setStyleSheet(
            f"QWidget#Panel {{ background-color:{COLORS['grey']}; border-radius:{PANEL_RADIUS}px; }}"
            f"QLabel {{ background:transparent; color:{COLORS['white']}; }}"
            f"QTableWidget {{ background-color:{COLORS['grey-dark']}; color:#ddd; border:1px solid {COLORS['border']};"
            " gridline-color:#262626; selection-background-color:#2b3a4a; selection-color:#fff; }"
            f"QHeaderView::section {{ background-color:{COLORS['grey']}; color:#9a9a9a; border:none;"
            f" border-bottom:1px solid {COLORS['border']}; padding:2px 6px; }}"
        )
        rows = QVBoxLayout(body)
        rows.setContentsMargins(14, 12, 14, 12)
        rows.setSpacing(8)
        rows.addWidget(self.summary)
        rows.addWidget(self.table, 1)
        rows.addLayout(HLayout([*self.buttons.values(), close], align=Qt.AlignRight))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(TitleBar(self, "Cache Report"))
        content = QVBoxLayout()
        content.setContentsMargins(12, 4, 12, 12)
        content.addWidget(body)
        layout.addLayout(content)
        self.addAnimationOverlay()
        self.resize(1100, 520)
        self.refresh()
        self.fadeIn()

    # --- rows -----------------------------------------------------------------------------------------------------

    def refresh(self):
        self.rows = sceneCaches()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row in self.rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            texts = (row["path"], row["type"], row["version"], row["frames"], row["disk"],
                     paths.formatSize(row["size"]) if row["size"] else "", row["file"])
            for column, text in enumerate(texts):
                item = _SizeItem(text) if column == 5 else QTableWidgetItem(text)
                item.setData(Qt.UserRole, row["size"] if column == 5 else row["path"])
                if column == 4:
                    item.setForeground(QBrush(QColor(STATE_COLORS[row["state"]])))
                item.setToolTip(text)
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
        total = sum(row["size"] for row in self.rows)
        written = sum(row["state"] == "written" for row in self.rows)
        self.summary.setText(f"{len(self.rows)} cache node(s), {written} fully written, {paths.formatSize(total)} on "
                             "disk  ·  double-click a row to show the node")

    def pickedNodes(self) -> list:
        picked = sorted({index.row() for index in self.table.selectedIndexes()})
        found = [hou.node(self.table.item(row, 0).data(Qt.UserRole)) for row in picked]
        return [node for node in found if node is not None]

    # --- actions --------------------------------------------------------------------------------------------------

    def _need(self, picked) -> bool:
        if not picked:
            hou.ui.setStatusMessage("Cache Report: pick rows first", severity=hou.severityType.Warning)
        return bool(picked)

    def showNode(self):
        picked = self.pickedNodes()
        if picked:
            nodes.showInNetwork(picked[0])

    def selectNodes(self):
        picked = self.pickedNodes()
        if not self._need(picked):
            return
        nodes.showInNetwork(picked[0])
        for node in picked[1:]:
            node.setSelected(True)

    def openFolder(self):
        for node in self.pickedNodes()[:5]:  # a window per cache: not too many
            parm = paths.mainFileParm(node)
            if parm is not None:
                hipfile.openInFileBrowser(parm.evalAsString())

    def cacheNetwork(self):
        picked = self.pickedNodes()
        if self._need(picked):
            caches.runCacheNetwork(picked)

    def cleanVersions(self):
        picked = self.pickedNodes()
        if self._need(picked) and versions.cleanOldVersions(picked):
            self.refresh()

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)


_windows: list = []


def showCacheReport() -> CacheReport:
    window = CacheReport()
    _windows.append(window)
    window.destroyed.connect(lambda *_: _windows.remove(window) if window in _windows else None)
    window.show()
    return window
