import xml.etree.ElementTree as ET
import os

def find_ase_parents(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    for ase in root.findall('.//Ase'):
        uid = ase.find('AseUid')
        if uid is not None:
            code_id = uid.findtext('codeId')
            # Check for any parent reference tags like AseUidPar or similar
            # In AIXM 4.5 it might be AseUid/AseUidPar
            parent = ase.find('AseUid/AseUidPar')
            if parent is not None:
                parent_id = parent.findtext('codeId')
                print(f"Sector: {code_id} -> Parent: {parent_id}")

if __name__ == "__main__":
    find_ase_parents(os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml"))
