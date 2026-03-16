import xml.etree.ElementTree as ET
from collections import Counter

def categorize_ase(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    types = []
    for ase in root.findall('.//Ase'):
        uid = ase.find('AseUid')
        if uid is not None:
            code_type = uid.findtext('codeType')
            types.append(code_type)
            
    print(Counter(types))

if __name__ == "__main__":
    categorize_ase(r"g:\My Drive\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml")
