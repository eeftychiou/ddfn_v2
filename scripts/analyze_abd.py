import xml.etree.ElementTree as ET

def analyze_abd(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    abd_elements = root.findall('.//Abd')
    print(f"Found {len(abd_elements)} Abd (Airspace Border) elements.")
    
    for abd in abd_elements[:10]:
        uid = abd.find('AbdUid')
        ase_uid = uid.find('AseUid') if uid is not None else None
        code_id = ase_uid.findtext('codeId') if ase_uid is not None else "N/A"
        
        # Geometry is usually in Avx or Pll or coordinates
        # Let's see some child tags
        children = [c.tag for c in abd]
        print(f"Parent Ase ID: {code_id}, Children: {children}")
        
if __name__ == "__main__":
    analyze_abd(r"g:\My Drive\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml")
