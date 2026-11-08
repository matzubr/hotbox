import copy
import re
import hou
import json
# import zipfile
from pathlib import Path
from pprint import pprint as pp

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *



class HouPanes:
    def __init__(self):
        self.panes_dict = {
        "network": hou.paneTabType.NetworkEditor,
        "viewer": hou.paneTabType.SceneViewer}
        self.network = self.getPane()
        self.viewer =  self.getPane(pane="viewer")
        self.network_icon = self.getNodeIcon()
        self.nodes = self.getSelectedNodes()

    def getPane(self,pane:str="network") -> hou.PaneTab:
        
        cursor_panetab = hou.ui.paneTabUnderCursor()
        if cursor_panetab and cursor_panetab.type() == self.panes_dict[pane]:
            return cursor_panetab
        else:
            network_panetab = hou.ui.paneTabOfType(self.panes_dict[pane])
            if network_panetab:
                return network_panetab
            else:
                print(f"No Pane {pane} found")
                return None

    def getNodeIcon(self,node:hou.Node=None) -> QIcon:
        if node:
            try:
                return hou.qt.Icon(node.type().icon())
            except hou.OperationFailed:
                return None
        else:
            return hou.qt.Icon(self.getPane().pwd().type().icon())
        
    def getSelectedNodes(self):
        return hou.selectedNodes()

class JsonResolver:

    def __init__(self,
                assets_folder:Path=None,
                schema_file:Path=None,
                formats:list=['.py']) -> dict:
        
        if not schema_file:
            schema_file = Path(assets_folder,"schema.json")
        
        self.schema = self.load_json(schema_file.as_posix())
        schema_old =  copy.deepcopy(self.schema)

        self.schema_keys = self.schema.keys()

        self.assets_folder = assets_folder
        self.lib_all_files =   [x for x in assets_folder.rglob("*") if x.is_file() and x.suffix in formats]
        self.lib_files_names = [x.relative_to(self.assets_folder).as_posix() for x in self.lib_all_files]
        
        self.keepFilesInSchema()
        self.updateExistingFilesInSchema()
        self.addNewFilesInSchema()

        if schema_old!=self.schema:
            self.dump_json(schema_file,self.schema)

    def dictFromArray(self,array,reg_pattern):
        d={}
        for w in array:
            d[w]=reg_pattern.format(key=w)
        return d

    def addInfo(self,keys):

        REG_PATTERN = r"^#{key}:(.+)$"
        SCRIPT_SETTINGS = ['label','textcolor','buttoncolor','icon','link','hotkey']

        reg_dict = self.dictFromArray(SCRIPT_SETTINGS,REG_PATTERN)
        
        for key in keys:
            filepath = self.schema[key]['file']
    
            file_settings=[]
            with open(filepath,'r') as f:
                while True:
                    line = f.readline()[:-1]
                    if line.startswith("#"):
                        file_settings.append(line)
                    else:
                        break
            

            # prev_keys = self.schema[key].keys()
            # current_keys = [x for x in reg_dict if re.search(reg_dict[x])]
            
            for reg_name in reg_dict:
                pattern = reg_dict[reg_name]
                for line in file_settings:
                    match = re.search(pattern,line)
                    if match:
                        self.schema[key][reg_name] = match.group(1)

    def listDifference(self,list1,list2):
        return [value for value in list1 if value not in list2]

    def listIntersection(self,list1,list2):
        return [value for value in list1 if value in list2]

    def keepFilesInSchema(self):
        remove_files = self.listDifference(self.schema_keys,self.lib_files_names)
        
        if len(remove_files)>0:
            [self.schema.pop(file) for file in remove_files]

    def updateExistingFilesInSchema(self):
        existing_files = self.listIntersection(self.schema_keys,self.lib_files_names)
        
        if len(existing_files)>0:
            for file in existing_files:
                filepath = Path(self.assets_folder,file)

                file_date = f"{(filepath).stat().st_mtime :.0f}"
                schema_date = self.schema[file]['date']
                
                if file_date!=schema_date:
                    self.schema[file]["date"] = file_date
                    self.addInfo([file])

    def addNewFilesInSchema(self):
        new_files = self.listDifference(self.lib_files_names,self.schema_keys)
        
        if len(new_files)>0:
            for file in new_files:
                filepath = Path(self.assets_folder,file)
                file_date = f"{(filepath).stat().st_mtime :.0f}"
                
                self.schema[file]={}
                self.schema[file]["date"] = file_date
                self.schema[file]["file"] = filepath.as_posix()
            self.addInfo(new_files)

    def load_json(self,file):
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def dump_json(self,file,data):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

# def read_data(self, key, value):
#     return self.data.get(key) if self.data.get(key) != None else value
