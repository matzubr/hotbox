from PySide2.QtCore import QEvent, QObject
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

import platform
import hou
import re
import sys

from pathlib import Path
from pprint import pprint as pp
from webbrowser import open as wbopen
from .utils import widgets,utility

if sys.version_info.major == 3:
    from importlib import reload

reload(widgets)
reload(utility)

PLATFORM_SYSTEM = platform.system()


def start():
    HotBox()
    # widgets.ScriptManager(lib_folder=Path(__file__).parent / "lib")

class HotBox(QWidget):
    def __init__(self) -> None:
        super().__init__(hou.qt.mainWindow())
        # QDir.addSearchPath("icons",Path(__file__,"../icons").resolve().as_posix())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        # self.setWindowFlag(Qt.WindowStaysOnTopHint)
        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        #enable transparency on Linux
        # if PLATFORM_SYSTEM not in ['Darwin','Windows']:
            # self.setAttribute(Qt.WA_PaintOnScreen)
        
        self.HouPanes = utility.HouPanes()
        self.initUI()
        self.adjustSize()
        # self.installEventFilter(self)
        
    def initUI(self):
        
        lib_folder = Path(__file__).parent / "lib"

        #set context
        nodes = self.HouPanes.getSelectedNodes()
        nodes_count = len(nodes)

        central_widget_icon = self.HouPanes.network_icon
        node_network = self.HouPanes.network.pwd().childTypeCategory().name()
        if nodes_count==0:
            self.mode = "all"
            central_widget_name = node_network
        elif nodes_count>1:
            self.mode = "multiple"
            central_widget_name = "Multiple"
        else:
            self.mode = "single"
            central_widget_name = nodes[0].type().nameComponents()[2]
            central_widget_icon = self.HouPanes.getNodeIcon(nodes[0])
            node_network = nodes[0].type().nameComponents()[2]

        lib_context_folder = lib_folder / self.mode

        #Procces schema
        schema_resolver = utility.JsonResolver(lib_context_folder)

        self.scripts_buttons = widgets.MultipleButtonsFromSchema(schema=schema_resolver.schema,context=node_network,parent=self)

        self.keybindings={}
        for child in self.scripts_buttons.children():
            if type(child) is widgets.ButtomFromFile:
                key = QKeySequence(child.hotkey)
                if key.count()>0:
                    self.keybindings[key[0]]=child

        self.open_hotbox_button = widgets.Button("Open HotBox folder")
        self.central_button = widgets.Button(central_widget_name,icon=central_widget_icon)
        self.script_manager_button = widgets.Button("Script Manager")

        central_layout = widgets.HLayout([self.open_hotbox_button,self.central_button,self.script_manager_button])

        layout = QVBoxLayout()
        layout.addWidget(self.scripts_buttons)
        layout.addLayout(central_layout)

        self.open_hotbox_button.clicked.connect(self.openhotboxfolder)
        self.central_button.clicked.connect(self.close)
        self.script_manager_button.clicked.connect(self.startManager)

        self.setLayout(layout)

        self.show()
        self.setPositionFromMouse()
        self.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:

        if event.type() in [QEvent.Type.KeyPress]:
            if event.key() in self.keybindings.keys():
                button = self.keybindings[event.key()]
                # button.execfile()
                button.animateClick()

        return super().eventFilter(watched, event)

    def openhotboxfolder(self):
        executed_script = Path(__file__)
        hotbox_folder = executed_script.parent
        wbopen(hotbox_folder.as_posix())

    def startManager(self,parent=None):
        widgets.ScriptManager(lib_folder=Path(__file__).parent / "lib")

    def setPositionFromMouse(self):
        mouse_pos = QCursor.pos()
        center_pos = mouse_pos - QPoint(self.width()//2,self.height()//2)
        self.move(center_pos)

    def keyPressEvent(self, event: QKeyEvent) -> None:

        if event.key() in [16777216,96]: # 96 - ` , 16777216 - escape
            self.close()

        return super().keyReleaseEvent(event)