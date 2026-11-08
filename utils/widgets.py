from PySide2.QtCore import QEvent, QObject
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

from pathlib import Path
from textwrap import wrap as wordWrap
from pprint import pprint as pp

import json
import hou
from colorsys import rgb_to_hsv,hsv_to_rgb
# from webbrowser import open as wbopen
# import hou

FONT_FAMILY = "Josefin Sans"
FONT_SIZE = 16
TEXT_WEIGHT = {
    "normal": QFont.Medium,
    "bold": QFont.Bold
    }

class HexColorGrade:

    def __init__(self,hex:str="#ffffff") -> None:
        self.hex = hex
        self.rgb = self.__hex2rgb(self.hex)
        self.hsv = rgb_to_hsv(self.rgb[0],self.rgb[1],self.rgb[2])

    def __hex2rgb(self,hex_value) -> tuple:
        h = hex_value.strip("#") 
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return rgb

    def __rgb2hex(self,r,g,b) -> str:
        r = int(round(r*255))
        g = int(round(g*255))
        b = int(round(b*255))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def hsvGrade(self,hue:float=0.0,saturation:float=0.0,value:float=0.0):
        
        nhue =        (self.hsv[0]+hue)%1.0
        nsaturation = max(min(self.hsv[1]+saturation,0.9),0.0)
        nvalue =      max(min(self.hsv[2]+value*255,255.0),0.0)
        
        self.hsv = tuple([nhue,nsaturation,nvalue])
        self.rgb = hsv_to_rgb(nhue,nsaturation,nvalue)
        self.hex = self.__rgb2hex(self.rgb[0],self.rgb[1],self.rgb[2])

class Label(QLabel):
    def __init__(self,
                label:str="",
                font:str=FONT_FAMILY,
                size:int=FONT_SIZE,
                weight:str="normal",
                parent=None) -> QLabel:
        
        super().__init__(parent)
        self.setText(label)
        self.setFont(QFont(font,size,weight=TEXT_WEIGHT[weight]))

class Button(QPushButton):
    """
    Button without script
    """
    def __init__(self,
                label:str="ButtonText",
                buttonColor:str="#222222",
                textColor:str="#e8e8e8",
                icon:str=None,
                buttonsize:int=200,
                parent=None) -> QPushButton:
        
        super().__init__(parent)

        if icon:
            if type(icon) in [QIcon,QPixmap]:
                self.setIcon(icon)
            else:
                filepath = Path(__file__).resolve().parents[1] / "icons" / icon
                if filepath.exists():
                    self.setIcon(QIcon(filepath.as_posix()))
                    self.setIconSize(QSize(buttonsize/6,buttonsize/6))
                else:
                    print(f"No Icon found\n{filepath}")

        self.buttonWidth = buttonsize

        self.updateText(label)
        self.setFont(QFont(FONT_FAMILY,FONT_SIZE,weight=TEXT_WEIGHT['bold']))
        self.updateColors(buttonColor,textColor)
        self.setFixedSize(QSize(buttonsize,buttonsize*0.3))
        self.setFlat(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setDefault(False)

    def updateText(self,text:str):
        max_word_width = int(self.buttonWidth * 0.06)
        self.setText("-\n".join(wordWrap(text,max_word_width)))
        # Label(text,parent=self)

    def updateColors(self,buttonColor="#222222",textColor="#e8e8e8"):
        self.setStyleSheet(f'''QPushButton{{
                background-color:{buttonColor};
                color:{textColor};
                border-radius:10px;
                border:none;}}
                QPushButton::hover{{
                background-color:#262626}}
                ''')

class ButtomFromFile(Button):

    def __init__(self, 
                file:Path=None,
                label: str = "ButtonText", 
                buttonColor: str = "#222222", 
                textColor: str = "#e8e8e8", 
                icon: str = None, 
                link:str=None,
                hotkey:str=None,
                buttonsize: int = 200, 
                parent=None) -> QPushButton:
        
        super().__init__(label, buttonColor, textColor, icon, buttonsize, parent)

        # if file==None or type(file)!=Path:
        #     print(f"Wrong type of file in {self} class")

        if hotkey:
            label = f"{label} ({hotkey})" 
        
        self.file = file
        self.hotkey = hotkey
        self.parent=parent
        self.updateText(label)
        self.updateColors(textColor=textColor,buttonColor=buttonColor)
        self.clicked.connect(self.execfile)

    def execfile(self):
        filepath = self.file.as_posix()
        code = self.file.read_text()
        scope = globals().copy()
        scope["__file__"] = filepath
        exec(compile(code, filepath, 'exec'), scope, scope)


class MultipleButtonsFromSchema(QWidget):

    def __init__(self,schema:list=[],context:str=None,parent:QWidget=None):
        super().__init__()
        
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,10)

        row = 0
        column = 0

        columns_names = sorted(list(set([Path(x).parent.name for x in schema if Path(x).parent.name==context or Path(x).parent.name==""])),reverse=True)

        for file in sorted(schema): # bad code , here i should give it proper and sorted schema dict
            file_context = Path(file).parent.name
            if file_context==context or file_context=="":
                cur_file = schema[file]
                name = self.__read_data(cur_file,"label",Path(file).stem)
                tcolor = self.__read_data(cur_file,"textcolor","#e8e8e8")
                bcolor = self.__read_data(cur_file,"buttoncolor","#222222")
                icon = self.__read_data(cur_file,"icon",None)
                hotkey = self.__read_data(cur_file,"hotkey",None)
                filepath = Path(cur_file['file'])
                button = ButtomFromFile(file=filepath,label=name,textColor=tcolor,buttonColor=bcolor,icon=icon,hotkey=hotkey,parent=parent)
                column_index = columns_names.index(file_context)
                if column==column_index:
                    row+=1  
                column=column_index
                layout.addWidget(button,row,column)
        
        self.setLayout(layout)

    def __read_data(self,dictionary, key, value):
        return dictionary.get(key) if dictionary.get(key) != None else value


class HLayout(QHBoxLayout):
    """
    Procedural layout which align all input widgets to the left
    """

    def __init__(self, widgets:list=[],align=Qt.AlignLeft,parent=None) -> QHBoxLayout:
        super().__init__(parent)

        if align:
            self.setAlignment(align)
        
        for w in widgets:
            self.addWidget(w)

class HSeparator(QFrame):
    """
    Horizontal Separator (line)
    """
    def __init__(self,parent=None) -> QFrame:
        super().__init__(parent)

        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)

class ScriptManager(QWidget):

    def __init__(self,lib_folder:Path=None,script_file:str="schema.json",parent=None):
        super().__init__(parent=hou.qt.mainWindow())

        self.lib = lib_folder
        self.filename = script_file

        self.setWindowTitle("Script Manager")
        self.setGeometry(300,300,1000,400)
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.initUI()

    def initUI(self):

        main_layout = QHBoxLayout()
        main_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # FIRST COLUMN
        fc_layout = QVBoxLayout()
        fc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(["all","multiple","single"])
        self.mode_combobox.currentIndexChanged.connect(self.updateSchema)

        self.folders_list = QListWidget()
        self.files_list = QListWidget()
        self.folders_list.itemClicked.connect(self.updateFilesList)
        self.files_list.itemClicked.connect(self.updateInfo)
        
        self.updateSchema()
        # self.updateFoldersList()
        self.updateFilesList()

        fc_layout.addWidget(self.mode_combobox)
        fc_layout.addWidget(self.folders_list)

        # SECOND COLUMN

        sc_layout = QVBoxLayout()
        sc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        sc_layout.addWidget(self.files_list)

        # THIRD WINDOW

        tc_layout = QVBoxLayout()
        tc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        name_label = QLabel("Name")
        self.name_lineedit = QLineEdit()
        name_layout = HLayout([name_label,self.name_lineedit])

        button_color_label = QLabel("Button Color")
        button_color_swatch = hou.qt.ColorSwatchButton()
        button_color_layout = HLayout([button_color_label,button_color_swatch])

        text_color_label = QLabel("Text Color")
        text_color_swatch = hou.qt.ColorSwatchButton()
        text_color_layout = HLayout([text_color_label,text_color_swatch])

        icon_label = QLabel("Icon")
        icon_lineedit = QLineEdit()
        icon_layout = HLayout([icon_label,icon_lineedit])

        hotkey_label = QLabel("Hotkey")
        hotkey_lineedit = QLineEdit()
        hotkey_layout = HLayout([hotkey_label,hotkey_lineedit])

        code_layout = QVBoxLayout()
        code_lineedit = QLineEdit()
        code_layout.addWidget(code_lineedit)

        tc_layout.addLayout(name_layout)
        tc_layout.addLayout(button_color_layout)
        tc_layout.addLayout(text_color_layout)
        tc_layout.addLayout(icon_layout)
        tc_layout.addLayout(hotkey_layout)
        tc_layout.addWidget(HSeparator())
        tc_layout.addLayout(code_layout)

        main_layout.addLayout(fc_layout)
        main_layout.addLayout(sc_layout)
        main_layout.addLayout(tc_layout)

        self.setLayout(main_layout)
        self.show()

    def updateSchema(self):
        mode = self.mode_combobox.currentText()
        schema_filepath = Path(self.lib,mode,self.filename)
        self.schema_json = self.load_json(schema_filepath.as_posix())
        self.updateFoldersList()

    def updateFoldersList(self):
        self.folders_list.clear()
        entry_folders = sorted(list(set([Path(x).parts[0] for x in self.schema_json])))
        self.folders_list.addItems(entry_folders)
        
        if len(entry_folders)>0:
            self.folders_list.setCurrentRow(0)

    def updateFilesList(self):
        self.files_list.clear()
        context = self.folders_list.currentItem().text()
        context_files = [Path(x).name for x in self.schema_json if Path(x).parts[0]==context]
        self.files_list.addItems(context_files)

        if len(context_files)>0:
            self.files_list.setCurrentRow(0)

    def updateInfo(self):
        context = self.folders_list.currentItem().text()
        file = self.files_list.currentItem().text()
        file_info = self.schema_json[f"{context}/{file}"]

        name = self.read_data(file_info,"label","")
        
        self.name_lineedit.setText(name)

    def read_data(self,dictionary, key, value):
        return dictionary.get(key) if dictionary.get(key) != None else value

    def load_json(self,file):
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def keyPressEvent(self, event: QKeyEvent) -> None:

        if event.key() in [16777216,96]: # 96 - ` , 16777216 - escape
            self.close()

        return super().keyReleaseEvent(event)

