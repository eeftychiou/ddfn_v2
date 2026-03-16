import xml.etree.ElementTree as ET

def analyze_ase(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    ase_elements = root.findall('.//Ase')
    print(f"Found {len(ase_elements)} Ase (Airspace) elements.")
    
    for ase in ase_elements[:20]:
        uid = ase.find('AseUid')
        code_id = uid.findtext('codeId') if uid is not None else "N/A"
        code_type = uid.findtext('codeType') if uid is not None else "N/A"
        
        name = ase.findtext('txtName')
        
        print(f"ID: {code_id}, Type: {code_type}, Name: {name}")
        
if __name__ == "__main__":
    analyze_ase(r"g:\My Drive\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml")
