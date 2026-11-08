#label:Convert to $JOB
#textcolor:#a0ceff

from pathlib import Path
import hou

def main():
    sel_nodes = hou.selectedNodes()
    if len(sel_nodes)==0:
        hou.ui.displayMessage("No node selected")
        return 0

    var_to_change = "$JOB"
    var_expanded = hou.text.expandString(var_to_change).rstrip("/")
    if not var_expanded or var_expanded == var_to_change:
        hou.ui.displayMessage(f"{var_to_change} is not set")
        return 0
    
    log_dict={}

    for node in sel_nodes:
        unfiltered_parms = filter_file_reference_parm(allParmTemplates(node.parmTemplateGroup()))
        parms = filter_multiparms(unfiltered_parms,node)

        if len(unfiltered_parms)>0:
            log_dict[node.name()]=[]
            for parm_name in parms:
                parm_object = node.parm(parm_name)
                path_dir = Path(parm_object.eval()).parent.as_posix()
                name = Path(parm_object.rawValue()).name
                # new_dir = path_dir.replace(var_expanded+"/",var_to_change+"/")
                new_dir = path_dir.replace(var_expanded,var_to_change)
                if path_dir==new_dir:
                    continue
                else:
                    new_filepath = Path(new_dir,name).as_posix()
                    if parm_object.rawValue()==new_filepath:
                        continue
                    parm_object.set(new_filepath)
                    log_dict[node.name()].append(parm_object.name())
        else:
            continue
    
    log_string=""
    for key in log_dict:
        values = log_dict[key]
        if len(values)>0:
            log_string+=f"Node: {key}\n"
            for val in values:
                log_string+=f"\t- {val}\n"

    if log_string!="":
        hou.ui.displayMessage(f"Paths changed in:\n{log_string}")

def allParmTemplates(group_or_folder):
    for parm_template in group_or_folder.parmTemplates():
        yield parm_template

        if parm_template.type() == hou.parmTemplateType.Folder:
            for sub_parm_template in allParmTemplates(parm_template):
                yield sub_parm_template

def filter_file_reference_parm(generator):
    return [x.name() for x in generator if x.type() == hou.parmTemplateType.String and x.stringType() == hou.stringParmType.FileReference and not x.isHidden()]

def filter_multiparms(parms_names_list,node):
    multiparms = [x for x in parms_names_list if x.endswith("#")]
    normal = [x for x in parms_names_list if not x.endswith("#")]
    
    for parm_name in multiparms:
        parm_object = node.parm(parm_name.replace("#","1"))
        if not parm_object:
            continue
        
        multiparm_folder = parm_object.parentMultiParm()
        for i in range(1,multiparm_folder.eval()+1):
            parm = node.parm(parm_name.replace("#",str(i))).name()
            normal.append(parm)
    
    return normal

main()