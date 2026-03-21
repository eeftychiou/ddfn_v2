import xml.etree.ElementTree as ET
import os

def analyze_ase_detail(file_path, target_id):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Efficiently find the specific Ase
    for ase in root.findall('.//Ase'):
        uid = ase.find('AseUid')
        if uid is not None and uid.findtext('codeId') == target_id:
            print(f"--- Detail for {target_id} ---")
            # Recursive print of children
            def print_elem(elem, level=0):
                print("  " * level + f"Tag: {elem.tag}, Attrib: {elem.attrib}, Text: {elem.text.strip() if elem.text else ''}")
                for child in elem:
                    print_elem(child, level + 1)
            
            print_elem(ase)
            break

if __name__ == "__main__":
    # Let's look at LCCCE1 (East Sector 1)
    analyze_ase_detail(os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml"), "LCCCE1")
